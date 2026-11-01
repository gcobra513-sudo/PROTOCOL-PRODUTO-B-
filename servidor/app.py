"""
A aplicação HTTP do portal.

O QUE NUNCA ENTRA NO LOG: CPF, código de acesso, token de sessão, nome,
endereço, e-mail e conteúdo de arquivo. O log registra o que aconteceu, com o
marcador HMAC do CPF quando precisa correlacionar dois eventos. Log é a fuga
de dados pessoais mais comum que existe, porque ninguém o trata como se fosse
um banco de dados — e ele é, só que sem controle de acesso e com backup
automático.

O QUE A RESPOSTA NUNCA DIZ: se um CPF está ou não no rol da entidade. Pedir
código devolve a mesma coisa nos dois casos. A diferença é que num deles sai
e-mail. Qualquer outra escolha transforma o portal numa consulta de filiação.

Essa frase já foi falsa por um ramo. A falha de ENTREGA virava 502, e o 502
só era alcançável quando o CPF está num dos róis — o de fora já tinha
voltado 202 antes. Hoje a falha de entrega vai para o log e a resposta não
muda. FICA UM CANAL ABERTO, e é melhor dizer do que esconder: o ramo de quem
está no rol executa a entrega DENTRO do pedido, então ele demora mais.
Medido com o remetente mais barato que existe, a diferença de mediana foi de
0,855 ms; com SMTP de verdade é maior. Fechar isso exige tirar a entrega do
caminho do pedido, e isso é mudança de desenho, não ajuste de ramo.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import pathlib
import re
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# `conta` e não `cadastro`: `entidades.Cadastro` já ocupa esse nome aqui,
# e a colisão deixava o módulo do contrato invisível em silêncio.
from nucleo import cadastro as conta
from nucleo import entendimentos, leitura, motor, panorama
from nucleo import participacao, pendencia

from . import (
    acervo,
    agenda,
    documentos,
    acesso,
    banco,
    acompanhamento,
    completude,
    deposito,
    entidades,
    remetente,
    rol,
    validacao,
)
from .config import (
    LIMITE_ARQUIVO_BYTES,
    LIMITE_PACOTE_BYTES,
    MINUTOS_DO_CODIGO,
    Config,
    carregar,
)

log = logging.getLogger("protocol.portal")


def _hash_curto(texto: str) -> str:
    """Marcador para o log de auditoria. NUNCA o CPF em claro: um log cheio
    de CPF é um segundo banco de dado pessoal, com retenção mais longa e
    menos cuidado que o primeiro."""
    import hashlib

    return hashlib.sha256(str(texto or "").encode("utf-8")).hexdigest()


def _pendencias_vazias() -> list[dict]:
    """As três chaves, vazias. A tela não deve ter de adivinhar a diferença
    entre "nada aqui" e "não calculado"."""
    return [
        {
            "quem": dono,
            "titulo": pendencia.TITULOS[dono],
            "explicacao": pendencia.EXPLICACOES[dono],
            "itens": [],
        }
        for dono in pendencia.DONOS
    ]

PEDACO = 64 * 1024

#: `contribuicao-3.pdf` ou `sentenca.pdf`. Nada de barra, nada de ponto-ponto:
#: o nome vem do cliente e não pode virar caminho.
_NOME_DE_DOCUMENTO = re.compile(r"^[a-z_]+(-\d{1,2})?\.pdf$")

#: Em MODO ENSAIO o servidor devolve o código de acesso na própria resposta
#: HTTP. Isso é o certo para teste e inaceitável com gente real — e um
#: servidor publicado assim fica a UM cadastro de distância de virar
#: vazamento: basta alguém registrar um sindicato de verdade e subir o rol.
#:
#: Então, em ensaio, só se atende entidade cujo apelido começa com isto. A
#: trava é de código, não de procedimento: procedimento se esquece.
#:
#: REEXPORTADO, não redefinido. Uma segunda cópia desta constante é uma
#: divergência esperando acontecer, e foi uma regra escrita em dois lugares
#: que deixou o agendador atender quem o HTTP recusava.
PREFIXO_DEMO = entidades.PREFIXO_DEMO


def _problema(status: int, mensagem: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"erro": mensagem, **extra})


async def _ler_limitado(arquivo: UploadFile, teto: int) -> bytes:
    """Lê com teto. `await arquivo.read()` sem limite é um upload de 4 GB."""
    pedacos: list[bytes] = []
    total = 0
    while True:
        pedaco = await arquivo.read(PEDACO)
        if not pedaco:
            break
        total += len(pedaco)
        if total > teto:
            raise _problema(
                413, f"o arquivo {arquivo.filename!r} passa do limite permitido"
            )
        pedacos.append(pedaco)
    return b"".join(pedacos)


def _origem(pedido: Request, cfg: Config) -> str:
    """Quem está pedindo, para a contagem por hora.

    O ENDEREÇO DO SOCKET MANDA, e o cabeçalho só entra quando quem fala com
    este servidor é um proxy DECLARADO em `PROTOCOL_PROXIES_CONFIAVEIS`.

    Antes era o contrário: devolvia o primeiro valor de `X-Forwarded-For`
    sempre que o cabeçalho existia. Como é cabeçalho de PEDIDO, quem pede
    escolhia a chave da contagem — girando o valor, cada pedido caía num
    balde novo. Medido: com o limite em 3, oito pedidos com o cabeçalho
    variando deram oito 202. E a contagem por origem é o que `acesso.py`
    declara como a defesa contra varrer CPFs para descobrir quem é filiado.

    O comentário antigo dizia que o primeiro valor é o cliente. É o
    contrário: proxy conforme ACRESCENTA ao fim o endereço de quem lhe
    falou, preservando o que veio antes. Então o que o cliente escreveu
    fica no começo, e o que o nosso proxy observou fica no FIM. Por isso o
    último, e por isso só de um proxy que a gente declarou.

    Ignorar o cabeçalho sempre não serve: atrás de proxy todo mundo viraria
    uma origem só, e o primeiro sindicato com atendimento presencial
    fecharia o portão para a fila inteira.

    Supõe UM salto confiável, que é a implantação descrita. Com dois proxies
    nossos em série, o último valor passa a ser o do proxy de dentro, e aqui
    é o lugar de consertar isso — não no cabeçalho.
    """
    peer = pedido.client.host if pedido.client else ""
    if peer and peer in cfg.proxies_confiaveis:
        encaminhado = pedido.headers.get("x-forwarded-for", "")
        if encaminhado:
            partes = [p.strip() for p in encaminhado.split(",") if p.strip()]
            if partes:
                return partes[-1]
    return peer or "desconhecido"


def criar_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or carregar()
    for aviso in cfg.avisos:
        log.warning("CONFIGURAÇÃO: %s", aviso)

    cfg.raiz.mkdir(parents=True, exist_ok=True)
    cadastro = entidades.Cadastro(cfg.raiz)
    portao = acesso.Portao(
        cfg.raiz,
        cfg.segredo,
        emissoes_por_cpf_hora=cfg.emissoes_por_cpf_hora,
        emissoes_por_origem_hora=cfg.emissoes_por_origem_hora,
    )
    correio: remetente.Remetente = (
        remetente.PorSmtp(
            cfg.smtp_host,
            cfg.smtp_porta,
            cfg.smtp_usuario,
            cfg.smtp_senha,
            cfg.smtp_remetente,
        )
        if cfg.tem_remetente
        else remetente.ParaArquivo(cfg.raiz)
    )

    if cfg.semente_demo:
        # Onde o disco não é persistente, a entidade de demonstração some a
        # cada reinício e a página sobe sem ninguém poder entrar. A semente
        # só roda em MODO ENSAIO e só escreve CPF sintético — ver
        # `servidor/semente.py`.
        from . import semente

        try:
            log.warning("SEMENTE: entidade de demonstração %s recriada",
                        semente.semear(cfg))
        except semente.SementeRecusada as e:
            log.error("SEMENTE recusada: %s", e)

    app = FastAPI(title="Portal de execução", docs_url=None, redoc_url=None)

    # O TRABALHO DE FUNDO SOBE COM O SERVIDOR.
    #
    # Aqui e não num cron de fora por um motivo concreto: o aviso toca CPF,
    # nome e e-mail, e por isso tem de rodar onde a API roda — que tem de ser
    # região brasileira. O coletor poderia viver em qualquer agendador (ele
    # só toca número de processo), mas separar os dois em lugares diferentes
    # dobraria o que há para configurar e esquecer.
    #
    # Em THREAD, nunca no laço de eventos: a coleta leva de 22 a 43 s por
    # processo, medidos, e isso dentro do laço travaria o portal inteiro.
    #
    # E só com banco: sem ele não há arrendamento entre instâncias nem
    # registro de execução — e agendador sem registro é agendador que morre
    # calado.
    if cfg.tem_banco and cfg.agendar:
        agenda.subir(app, cfg)
    app.state.cfg = cfg
    app.state.cadastro = cadastro
    app.state.portao = portao

    if cfg.origens:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cfg.origens),
            allow_methods=["GET", "POST"],
            # `authorization` entra porque as telas de consulta mandam
            # `Authorization: Bearer ...`. Sem ele o PREFLIGHT do navegador
            # reprova e as telas não carregam nada — e isso não aparece em
            # teste de TestClient, que não faz preflight. Achado conduzindo o
            # navegador de verdade em 29/10/2026, com o portal e o servidor em
            # origens diferentes, que é como eles vivem em produção.
            allow_headers=["content-type", "authorization"],
        )

    def _entidade(apelido: str) -> entidades.Entidade:
        try:
            ent = cadastro.resolver(apelido)
        except entidades.EntidadeDesconhecida:
            raise _problema(404, "entidade não encontrada") from None
        except entidades.EntidadeSuspensa:
            raise _problema(
                403, "esta entidade não está recebendo cadastros agora"
            ) from None
        # AS TRÊS TRAVAS VIVEM EM `entidades.atendivel`, e não aqui.
        #
        # Viviam aqui, e por isso valiam só no HTTP: o laço do agendador
        # resolve entidade por `Cadastro.todas()` e não passava por esta
        # função. O MESMO servidor devolvia 403 para um sindicato e, no
        # mesmo processo, lia os dados nominais dele e mandava o e-mail.
        # Uma regra escrita numa porta e não na outra é como este defeito
        # nasce. A decisão é uma; aqui fica só a tradução para HTTP.
        recusa = entidades.atendivel(ent, cfg)
        if recusa is not None:
            log.error("%s recusou a entidade %s (regiao=%r, ensaio=%s, "
                      "banco=%s)", recusa.motivo.upper(), ent.apelido,
                      cfg.regiao, cfg.modo_ensaio, cfg.tem_banco)
            raise _problema(recusa.estado, recusa.explicacao)

        return ent

    # ------------------------------------------------------------- diagnóstico

    @app.get("/saude")
    def saude() -> dict:
        # O ESTADO DO TRABALHO DE FUNDO VAI NA SAÚDE, e é o ponto inteiro
        # deste checkpoint: um agendador que parou tem de aparecer em algum
        # lugar que alguém olhe. `ok: false` quando alguma tarefa está
        # atrasada — monitor que só confere se a porta responde não percebe
        # que os avisos pararam.
        # AGREGADO POR TAREFA, NÃO UMA LINHA POR SINDICATO. Esta rota não
        # exige sessão, e uma linha por entidade entregava a um anônimo a
        # lista de todos os clientes — informação comercial, e o apelido é
        # a chave das rotas públicas. A pergunta que o monitor faz é "o
        # trabalho parou?", e ela se responde sem nomear ninguém.
        por_tarefa: dict[str, dict] = {
            t: {"tarefa": t, "entidades": 0, "atrasadas": 0,
                "ultima_boa": None, "alguma_falhou": False}
            for t in agenda.TAREFAS
        }
        ilegivel = 0
        atrasados = 0
        if cfg.tem_banco:
            for ent in cadastro.todas():
                try:
                    for e in agenda.estado(cfg.banco_url, ent.apelido):
                        linha = por_tarefa.setdefault(
                            e["tarefa"],
                            {"tarefa": e["tarefa"], "entidades": 0,
                             "atrasadas": 0, "ultima_boa": None,
                             "alguma_falhou": False},
                        )
                        linha["entidades"] += 1
                        if e["atrasado"]:
                            linha["atrasadas"] += 1
                            atrasados += 1
                        if e["ultima_falhou"]:
                            linha["alguma_falhou"] = True
                        boa = e["ultima_boa"]
                        # A MAIS ANTIGA MANDA. Se UMA entidade parou, a
                        # tarefa está parada; a mais recente esconderia
                        # exatamente a que precisa aparecer.
                        if boa and (linha["ultima_boa"] is None
                                    or boa < linha["ultima_boa"]):
                            linha["ultima_boa"] = boa
                except Exception:  # noqa: BLE001
                    # NÃO ENGOLIR. Visto no vivo, com a tabela ainda não
                    # criada: a consulta falhava, a lista ficava vazia, e a
                    # saúde respondia `ok: true` — exatamente o silêncio que
                    # este checkpoint existe para impedir. Não saber como
                    # está o trabalho é um estado RUIM, não um estado bom.
                    # O apelido e o tipo do erro vão para o LOG, que é
                    # canal de operador; para fora sai só a contagem.
                    log.exception("estado do agendador falhou para %s",
                                  ent.apelido)
                    ilegivel += 1
        return {
            "ok": not atrasados and not ilegivel,
            "trabalho_de_fundo": list(por_tarefa.values()),
            "atrasados": atrasados,
            "estado_ilegivel": ilegivel,
            "modo_ensaio": cfg.modo_ensaio,
            "envio_de_email": "smtp" if cfg.tem_remetente else "arquivo",
            "entidades": len(cadastro.todas()),
        }

    #: O que a tela mostra quando o servidor é de demonstração. Texto aqui,
    #: e não no portal, porque quem sabe que isto é demonstração é o
    #: SERVIDOR — o portal é o mesmo código nos dois casos, e deixá-lo
    #: adivinhar pelo endereço seria errar no dia em que o endereço mudasse.
    AVISO_DEMONSTRACAO = (
        "Esta é uma demonstração. Não envie documentos de verdade: o "
        "servidor é de teste, os dados são apagados a cada reinício e o "
        "cadastro aceito é fictício."
    )

    @app.get("/api/entidade/{apelido}")
    def ver_entidade(apelido: str) -> dict:
        ent = _entidade(apelido)
        # O nome, para o portal escrever "Sindicato X" no cabeçalho. E, em
        # ensaio, a marca de demonstração: quem chega pelo link não tem como
        # adivinhar que não é para valer, e aqui alguém poderia enviar
        # identidade e procuração de verdade para um servidor de teste.
        corpo = {"apelido": ent.apelido, "nome": ent.nome}
        if cfg.modo_ensaio:
            corpo["demonstracao"] = True
            corpo["aviso_demonstracao"] = AVISO_DEMONSTRACAO
        return corpo

    # ------------------------------------------------------------------ portão

    @app.post("/api/acesso/codigo")
    def pedir_codigo(corpo: dict, pedido: Request) -> JSONResponse:
        ent = _entidade(str(corpo.get("entidade", "")))
        cpf = str(corpo.get("cpf", ""))
        if not validacao.cpf_valido(cpf):
            # Aqui a resposta PODE ser específica: um CPF com dígito
            # verificador errado não é um CPF de ninguém, então dizer isso não
            # revela nada sobre filiação — e poupar a pessoa de esperar um
            # e-mail que nunca vem vale mais.
            raise _problema(400, "CPF inválido")

        marca = portao.marcar_cpf(cpf)[:12]
        try:
            codigo = portao.emitir(ent.apelido, cpf, _origem(pedido, cfg))
        except acesso.ExcessoDeTentativas as e:
            log.info("codigo recusado por contagem ent=%s cpf=%s", ent.apelido, marca)
            raise _problema(429, str(e)) from None

        resposta: dict = {
            "enviado": True,
            "minutos": MINUTOS_DO_CODIGO,
            "aviso": (
                "Se este CPF estiver no cadastro da entidade, o código chega "
                "no e-mail registrado lá."
            ),
        }

        try:
            lista = rol.carregar(ent.pasta(cfg.raiz))
        except rol.RolAusente:
            # Fail-closed e em voz alta: sem rol ninguém entra, e o operador
            # tem que ver isso no log, não descobrir pelo filiado reclamando.
            log.error(
                "ROL AUSENTE em %s: nenhum código será entregue até a "
                "entidade enviar filiados.csv",
                ent.apelido,
            )
            return JSONResponse(resposta, status_code=202)
        except ValueError as e:
            log.error("ROL INVÁLIDO em %s: %s", ent.apelido, e)
            return JSONResponse(resposta, status_code=202)

        # O gerente do sindicato não é necessariamente filiado. Se o código
        # só fosse para quem está em filiados.csv, não haveria como ele
        # entrar no painel — e inventar um login de gestor seria inventar uma
        # senha para guardar.
        #
        # OS DOIS RÓIS SÃO CARREGADOS ANTES DO RAMO, e isso não é estilo.
        # Carregar o de gestores só quando o CPF falta no de filiados fazia um
        # `gestores.csv` malformado — o `;` do Excel em português basta —
        # levantar exceção SÓ para quem não está no rol: 202 para quem está,
        # 500 para quem não está. Oráculo de filiação sindical, sem
        # autenticação, para qualquer CPF. Filiação sindical é dado sensível
        # (LGPD, art. 11), e este módulo abre dizendo que a resposta tem de ser
        # a mesma nos dois casos.
        try:
            dos_gestores = rol.carregar_gestores(ent.pasta(cfg.raiz))
        except (rol.RolAusente, ValueError) as e:
            # Mesmo tratamento do rol de filiados: erra alto no log, e a
            # resposta não muda.
            log.error("GESTORES INVÁLIDO em %s: %s", ent.apelido, e)
            dos_gestores = None

        destino = lista.email_de(cpf) or (
            dos_gestores.email_de(cpf) if dos_gestores else None
        )
        if destino is None:
            log.info("codigo sem destino ent=%s cpf=%s", ent.apelido, marca)
            return JSONResponse(resposta, status_code=202)

        try:
            correio.enviar(destino, codigo, ent.nome, MINUTOS_DO_CODIGO)
        except Exception:
            # FALHA DE ENTREGA NÃO VIRA STATUS, e isto é a correção de um
            # oráculo de filiação.
            #
            # Este ramo só é alcançado quando `destino` existe — isto é, só
            # para quem ESTÁ num dos dois róis; o CPF de fora já voltou 202
            # acima. Então o 502 que havia aqui era, por construção, uma
            # AFIRMAÇÃO de que aquele CPF está no cadastro do sindicato,
            # dada a um anônimo. Filiação sindical é dado sensível (LGPD,
            # art. 11), e é o próprio dado que este produto existe para
            # proteger.
            #
            # E não era estado exótico: em produção o remetente é sempre
            # SMTP, e `send_message` levanta quando o relay recusa o
            # destinatário. Um e-mail velho numa linha de `filiados.csv` —
            # rotina numa base de sindicato — dava um 502 permanente e
            # estável para exatamente aquele CPF.
            #
            # Falha de entrega é problema do operador, e o lugar dela é o
            # log. Sem o texto da exceção em resposta nenhuma: ele costuma
            # trazer o endereço de destino.
            log.exception("falha ao enviar código ent=%s cpf=%s", ent.apelido, marca)

        if cfg.modo_ensaio:
            resposta["codigo_do_ensaio"] = codigo
            resposta["ensaio"] = (
                "MODO ENSAIO: o código vem na resposta. Não use com dados de "
                "pessoas reais."
            )
        return JSONResponse(resposta, status_code=202)

    @app.post("/api/acesso/conferir")
    def conferir_codigo(corpo: dict) -> dict:
        ent = _entidade(str(corpo.get("entidade", "")))
        cpf = str(corpo.get("cpf", ""))
        codigo = str(corpo.get("codigo", "")).strip()
        try:
            token = portao.conferir(ent.apelido, cpf, codigo)
        except acesso.ExcessoDeTentativas as e:
            raise _problema(429, str(e)) from None
        except acesso.CodigoInvalido as e:
            raise _problema(401, str(e)) from None
        return {"token": token, "entidade": ent.apelido, "nome": ent.nome}

    # ---------------------------------------------------------------- cadastro



    # ------------------------------------------------------------- consulta

    def _nome_de_documento_valido(nome: str) -> bool:
        """O nome vindo do cliente NUNCA vira caminho.

        Ou é um dos tipos do contrato — com índice, quando o tipo aceita
        vários, porque três anos de contracheque são três arquivos —, ou o
        pedido morre aqui.
        """
        return bool(_NOME_DE_DOCUMENTO.match(nome)) and (
            nome.split("-")[0].removesuffix(".pdf") in conta.DOCUMENTOS
            or nome.removesuffix(".pdf") in conta.DOCUMENTOS
        )

    def _sessao_de(pedido: Request) -> acesso.Sessao:
        """A sessão do cabeçalho Authorization, ou 401.

        A resposta é a MESMA para token ausente, inválido e expirado: dizer
        qual dos três é dar a quem tenta uma pista sobre o que tentar.
        """
        bruto = pedido.headers.get("authorization") or ""
        token = bruto[7:] if bruto.lower().startswith("bearer ") else bruto
        try:
            return portao.abrir_sessao(token)
        except acesso.SessaoInvalida:
            raise _problema(401, "sessão inválida ou expirada") from None

    def _linhas_do_cpf_da_sessao(
        ent: entidades.Entidade, sessao: acesso.Sessao
    ) -> list[dict]:
        """Os cadastros de quem abriu a sessão.

        O casamento é por MARCADOR HMAC do CPF, não pelo CPF: a sessão nunca
        guardou o CPF em claro, e não há razão para esta rota pedi-lo de
        volta. Quem abriu a sessão já provou quem é, no portão.
        """
        achadas: list[dict] = []
        for registro in deposito.ler_diario(ent.pasta(cfg.raiz)):
            linha = registro.get("linha")
            if not isinstance(linha, dict):
                continue
            # `cpf` e não `id_externo`: o contrato do B identifica pelo
            # próprio CPF. `id_externo` era do manifesto do Produto A, e com
            # ele aqui a consulta do filiado devolvia lista vazia — sem erro.
            cpf = conta.so_digitos(linha.get("cpf") or "")
            if cpf and portao.marcar_cpf(cpf) == sessao.cpf_hash:
                achadas.append(linha)
        return achadas

    def _cpf_da_sessao(ent: entidades.Entidade, sessao) -> str:
        """O CPF de quem abriu a sessão, descoberto pelo MARCADOR.

        A sessão nunca guardou o CPF em claro — de propósito. Para consultar
        o banco por CPF é preciso achar de quem é o marcador, e o único lugar
        onde o par existe é o rol que o sindicato mandou.
        """
        # OS DOIS ROLS. A sessão pode ter sido aberta por quem está em
        # `filiados.csv` OU em `gestores.csv` — o gerente do sindicato não é
        # necessariamente filiado, e quando é, ele tem cadastro como todo
        # mundo. Procurar só no primeiro deixava o gestor sem os próprios
        # dados, sem erro nenhum para explicar.
        for carregar in (rol.carregar, rol.carregar_gestores):
            try:
                lista = carregar(ent.pasta(cfg.raiz))
            except (rol.RolAusente, ValueError):
                continue
            for cpf in lista.por_cpf:
                if portao.marcar_cpf(cpf) == sessao.cpf_hash:
                    return conta.so_digitos(cpf)
        return ""

    @app.get("/api/meus-processos")
    def meus_processos(pedido: Request) -> dict:
        """Os processos de quem está logado, e o que andou neles.

        ESTA ROTA NÃO ACEITA CPF. Nem por parâmetro, nem no corpo: ela filtra
        pelo CPF que abriu a sessão. Aceitar um CPF de fora transformaria a
        consulta na pesquisa de filiação que o portão se recusa a ser — e o
        portão foi desenhado justamente para que pedir código não revele se
        alguém está no rol.

        Também não consulta o DataJud: a consulta leva 22 a 43 s, medidos.
        Quem fala com o tribunal é o coletor, em segundo plano; esta rota lê
        o que ele já trouxe.
        """
        sessao = _sessao_de(pedido)
        ent = _entidade(sessao.entidade)
        linhas = _linhas_do_cpf_da_sessao(ent, sessao)

        numeros: list[str] = []
        for linha in linhas:
            for numero in conta.numeros_de_processo(
                linha.get("numeros_de_processo", "")
            ):
                if numero not in numeros:
                    numeros.append(numero)

        # E OS QUE O SINDICATO MANDOU. A planilha dele costuma ter o número,
        # e até aqui a pessoa precisava achar 20 dígitos numa papelada e
        # digitar no celular para que a gente acompanhasse o processo dela.
        if cfg.tem_banco:
            try:
                for numero in banco.processos_do_cpf(
                    cfg.banco_url, ent.apelido, _cpf_da_sessao(ent, sessao)
                ):
                    if numero not in numeros:
                        numeros.append(numero)
            except Exception:  # noqa: BLE001
                log.exception("PROCESSOS do banco falharam ent=%s", ent.apelido)

        ultimos = acompanhamento.ultimo_por_processo(
            acompanhamento.ler_diario_de_movimentos(
                ent.pasta(cfg.raiz) / "movimentos.jsonl"
            )
        )
        processos = []
        for numero in numeros:
            ultimo = ultimos.get(numero)
            try:
                alias = acompanhamento.alias_do_numero(numero)
            except acompanhamento.TribunalDesconhecido:
                alias = ""
            processos.append({
                "numero": numero,
                "tribunal": alias.replace("api_publica_", "").upper(),
                "ultimo_movimento": (
                    {"data": ultimo.data, "nome": ultimo.nome,
                     "grau": ultimo.grau}
                    if ultimo else None
                ),
            })
        # QUANDO FOI A ÚLTIMA CONFERÊNCIA. Sem isto a tela sabia a data do
        # último MOVIMENTO e não a da última COLETA — e "nada novo" só é
        # verdade em relação à segunda. É a frase que mata o telefonema:
        # quem liga, liga para ouvir "conferimos hoje de manhã e não mudou
        # nada". Sem a data da coleta, a tela não podia dizer isso.
        conferido_em = ""
        if cfg.tem_banco:
            try:
                quando = agenda.ultima_boa(cfg.banco_url, ent.apelido,
                                           "coletar")
                conferido_em = quando.isoformat() if quando else ""
            except Exception:  # noqa: BLE001
                log.exception("última coleta falhou ent=%s", ent.apelido)

        return {
            "entidade": ent.apelido,
            "nome": ent.nome,
            "processos": processos,
            "conferido_em": conferido_em,
            # Dito na resposta, não só na tela: quem consumir esta API por
            # fora tem de receber o limite junto com o dado.
            "limite": (
                "Movimentação registrada pelo tribunal, com cerca de um dia "
                "de atraso. NÃO é intimação e não serve para contar prazo."
            ),
        }

    def _fatos_lidos_do_cpf(ent: entidades.Entidade, cpf: str) -> dict:
        """Os fatos que os documentos da pessoa dizem.

        DO BANCO QUANDO HÁ BANCO. Os achados são extraídos UMA VEZ, na
        chegada do cadastro, e ficam gravados com o trecho de onde saíram.
        Antes isto reabria todos os PDFs da pessoa a cada carregamento de
        tela — e era o que impedia o painel do sindicato de olhar os
        documentos da base inteira.

        Sem banco, relê os arquivos: é o modo de demonstração, e ali a base
        tem uma pessoa.

        DOCUMENTO ILEGÍVEL NÃO VIRA ERRO: vira ausência de fato, e o motor
        devolve FALTA. Quebrar a consulta inteira por causa de um arquivo
        manda a pessoa ligar para o sindicato por algo que ela já resolveu
        enviando.
        """
        achados: list[leitura.Achado] = []
        if cfg.tem_banco:
            try:
                return leitura.fatos_confiaveis(
                    banco.achados_do_cpf(cfg.banco_url, ent.apelido, cpf)
                )
            except Exception:  # noqa: BLE001
                log.exception("ACHADOS do banco falharam; relendo os arquivos")
        pasta = ent.entrega(cfg.raiz) / conta.so_digitos(cpf)
        for arquivo in sorted(pasta.glob("*.pdf")) if pasta.is_dir() else []:
            try:
                achados += documentos.ler_pdf(arquivo.read_bytes())
            except Exception:  # noqa: BLE001
                log.warning("documento ilegível em %s", arquivo.name)
        return leitura.fatos_confiaveis(achados)

    def _entregues_do_cpf(ent: entidades.Entidade, cpf: str) -> tuple[str, ...]:
        """QUE TIPOS de documento a pessoa já entregou — não o que eles
        dizem. É o que faz a pendência mudar de dono: quem mandou a sentença
        está esperando leitura, não providência.

        DO BANCO QUANDO HÁ BANCO, pelo mesmo motivo dos achados: com banco,
        nenhuma leitura de tela toca os PDFs. Olhar o disco aqui também
        amarraria a resposta à presença do arquivo, e arquivo some — por
        backup restaurado pela metade, por migração de armazenamento — sem
        que a pessoa tenha deixado de entregar nada.
        """
        if cfg.tem_banco:
            try:
                return banco.documentos_do_cpf(cfg.banco_url, ent.apelido, cpf)
            except Exception:  # noqa: BLE001
                log.exception("DOCUMENTOS do banco falharam; olhando o disco")
        pasta = ent.entrega(cfg.raiz) / conta.so_digitos(cpf)
        nomes = (
            [a.name for a in pasta.glob("*.pdf")] if pasta.is_dir() else []
        )
        return panorama.tipos_entregues(nomes)

    @app.get("/api/meu-cadastro")
    def meu_cadastro(pedido: Request) -> dict:
        """O que já sabemos sobre quem está entrando.

        A PESSOA RECEBE O LINK NO GRUPO DO SINDICATO E ABRE. Até aqui ela
        encontrava 17 campos em branco — e **10 deles o sindicato já tinha
        mandado**. Cada campo desses é gente que abandona o cadastro no meio,
        e a abandonada é sempre a mesma: a aposentada, no celular.

        Agora ela CONFERE em vez de digitar. E o que ela corrigir não
        sobrescreve o sindicato: vira afirmação dela, e a divergência aparece
        no painel. Quem decide qual versão vale é o sindicato — a ordem de
        chegada não decide isso.

        ESTA ROTA NÃO ACEITA CPF, pela mesma razão das outras, e aqui com mais
        força: o que ela devolve é o cadastro inteiro de uma pessoa.

        QUEM NÃO ESTÁ NA BASE RECEBE VAZIO, não erro. É o filiado novo, que
        entrou depois da última exportação do sindicato: ele existe, e a tela
        dele é a de sempre.
        """
        sessao = _sessao_de(pedido)
        ent = _entidade(sessao.entidade)
        _auditar(ent, "meu-cadastro", quem_hash=sessao.cpf_hash,
                 alvo_hash=sessao.cpf_hash)

        vazio = {
            "entidade": ent.apelido,
            "nome": ent.nome,
            "conhecido": False,
            "campos": {},
            "documentos": [],
            "aviso": (
                "Não encontramos você na base que o seu sindicato enviou. "
                "Isso é normal para quem se filiou há pouco — basta preencher "
                "os seus dados."
            ),
        }

        cpf = _cpf_da_sessao(ent, sessao)
        if not cpf or not cfg.tem_banco:
            return vazio
        try:
            registro = next(
                (r for r in banco.base(cfg.banco_url, ent.apelido)
                 if conta.so_digitos(r["linha"].get("cpf", "")) == cpf),
                None,
            )
        except Exception:  # noqa: BLE001
            log.exception("MEU-CADASTRO falhou ent=%s", ent.apelido)
            return vazio
        if registro is None:
            return vazio

        # SÓ OS CAMPOS DO CONTRATO, e só os preenchidos. Devolver campo vazio
        # faria a tela marcar como "conferido" o que ninguém informou.
        campos = {
            campo: str(registro["linha"].get(campo) or "").strip()
            for campo in conta.CAMPOS
            if str(registro["linha"].get(campo) or "").strip()
        }
        return {
            **vazio,
            "conhecido": True,
            "campos": campos,
            "documentos": sorted(registro["arquivos"]),
            "aviso": (
                "O seu sindicato já enviou parte dos seus dados. Confira, "
                "corrija o que estiver errado e complete o que faltar — a "
                "correção não apaga o que ele enviou: ele confere a diferença."
            ),
        }

    @app.get("/api/minhas-acoes")
    def minhas_acoes(pedido: Request) -> dict:
        """De quais ações o filiado participa, e o que pode ser feito em cada.

        É O QUE O CADASTRO PROMETE no último passo: "a gente lê os seus
        documentos e mostra de quais ações você faz parte e o que pode ser
        feito em cada uma". Até agora o motor calculava e ninguém via.

        ESTA ROTA NÃO ACEITA CPF, pela mesma razão de `/api/meus-processos`:
        aceitar um CPF de fora transformaria a consulta na pesquisa de
        filiação que o portão se recusa a ser.

        E SÓ O CATÁLOGO DAS CATEGORIAS QUE ESTA ENTIDADE CONTRATOU. Entidade
        sem declaração recebe lista VAZIA, nunca o catálogo das outras —
        `entendimentos.carregar_categorias` trata tupla vazia como "nenhuma",
        e é a diferença entre atender um sindicato e entregar a ele o acervo
        de outro.

        TRÊS VAZIOS QUE NÃO SÃO ERRO, e todos os três respondem com `aviso`
        em vez de status 4xx ou 5xx: quem não cadastrou ainda, a entidade sem
        categoria declarada, e o catálogo sem nada homologado. Erro aqui
        manda a pessoa ligar justamente para ouvir o que a tela já poderia
        ter dito.
        """
        sessao = _sessao_de(pedido)
        ent = _entidade(sessao.entidade)
        _auditar(ent, "minhas-acoes", quem_hash=sessao.cpf_hash,
                 alvo_hash=sessao.cpf_hash)
        linhas = _linhas_do_cpf_da_sessao(ent, sessao)

        # Recarrega a cada pedido de propósito: homologar é ato de advogado
        # que acontece no arquivo, e catálogo guardado em memória continuaria
        # recusando depois de alguém assinar.
        catalogo = entendimentos.carregar_categorias(
            entendimentos.PASTA_PADRAO, tuple(ent.categorias)
        )

        comum = {
            "entidade": ent.apelido,
            "nome": ent.nome,
            "categorias": list(catalogo.categorias),
            "catalogo": catalogo.assinatura,
            "filiado": "",
            "acoes": [],
            "oportunidades": [],
            "pendencias": _pendencias_vazias(),
        }

        if not linhas:
            return {**comum, "aviso": (
                "Você ainda não enviou o seu cadastro, então não há o que "
                "analisar. Faça o cadastro e volte aqui — nada é apresentado "
                "em juízo com base nele, e isto não é parecer."
            )}
        if not catalogo.categorias:
            return {**comum, "aviso": (
                "O seu sindicato ainda não tem categoria declarada no "
                "sistema, então não há ação a cruzar com os seus dados. "
                "Isto não é parecer: nada foi analisado."
            )}

        # O último envio vence: é o que a pessoa corrigiu por último, e o
        # anterior está no histórico, não perdido.
        linha = conta.normalizar(linhas[-1])
        # O QUE A PESSOA RESPONDEU NO CADASTRO É LIDO, e não era: a tela
        # devolvia "saber se já existe ação própria" como tarefa dela depois
        # de ela ter respondido exatamente isso três telas antes. Perguntar
        # de novo o que ela acabou de responder é o telefonema que esta tela
        # existe para evitar.
        #
        # `ja_executou_conferido=False` porque a resposta é DELA, não da base
        # de execuções: o motor conta com ela e deixa nota dizendo de onde
        # veio. Quando a base existir, ela entra aqui e a nota desaparece.
        fatos = documentos.fatos_para_o_motor(
            _fatos_lidos_do_cpf(ent, linha["cpf"]),
            linha,
            documentos_entregues=_entregues_do_cpf(ent, linha["cpf"]),
            ja_executou=conta.resposta_booleana(linha["ja_executou"]),
            tem_acao_propria=conta.resposta_booleana(
                linha["tem_acao_propria"]
            ),
        )
        quem = participacao.Filiado(
            cpf=fatos.cpf,
            cargo=fatos.cargo,
            situacao=fatos.situacao,
            filiado_desde=fatos.filiado_desde,
            filiado_ate=fatos.filiado_ate,
            no_rol=fatos.no_rol,
        )
        acoes = participacao.participacoes(quem, catalogo)
        oportunidades = motor.avaliar(fatos, catalogo)
        grupos = pendencia.agrupar(
            [f for p in acoes for f in p.falta]
            + [f for o in oportunidades for f in o.falta]
            + [f for o in oportunidades for f in o.falta_para_valor]
        )

        return {
            **comum,
            "filiado": linha["nome_completo"],
            "acoes": [
                {
                    "id": p.acao,
                    "rotulo": p.rotulo,
                    "estado": p.estado,
                    "inicio": p.inicio,
                    "fim": p.fim,
                    "meses": p.meses,
                    "motivos": list(p.motivos),
                }
                for p in acoes
            ],
            "oportunidades": [
                {
                    "trilha": o.trilha,
                    "referencia": o.referencia,
                    "rotulo": o.rotulo,
                    "categoria": o.categoria,
                    "veredicto": o.veredicto,
                    "periodo_inicio": o.periodo_inicio,
                    "periodo_fim": o.periodo_fim,
                    "meses": o.meses,
                    "motivos": list(o.motivos),
                    "notas": list(o.notas),
                    "fonte": o.fonte,
                    "falta": [
                        {"quem": f.quem, "o_que": f.o_que} for f in o.falta
                    ],
                    # SEPARADO de `falta`: uma responde "posso?", a outra
                    # "quanto?". Juntá-las faria "falta a sua ficha
                    # financeira" parecer impedimento para executar.
                    "falta_para_valor": [
                        {"quem": f.quem, "o_que": f.o_que}
                        for f in o.falta_para_valor
                    ],
                    "valor": (
                        {
                            "apurado": str(o.apuracao.total)
                            if o.apuracao.total is not None else None,
                            "aviso": o.apuracao.aviso,
                            "memoria": [
                                {"o_que": p.o_que, "resultado": p.resultado,
                                 "fonte": p.fonte}
                                for p in o.apuracao.memoria
                            ],
                        }
                        if o.apuracao is not None else None
                    ),
                }
                for o in oportunidades
            ],
            "pendencias": [
                {
                    "quem": dono,
                    "titulo": pendencia.TITULOS[dono],
                    "explicacao": pendencia.EXPLICACOES[dono],
                    "itens": list(grupos[dono]),
                }
                for dono in pendencia.DONOS
            ],
            # DITO NA RESPOSTA, não só na tela: quem consumir esta API por
            # fora tem de receber o limite junto com o dado.
            "aviso": (
                "Isto NÃO é parecer. É o que os seus documentos e o seu "
                "cadastro permitem apurar hoje, e nada é apresentado em "
                "juízo sem um advogado conferir e assinar."
            ),
        }

    def _auditar(ent: entidades.Entidade, o_que: str, *, quem_hash: str,
                 alvo_hash: str = "") -> None:
        """Registra a leitura de dado nominal.

        FALHA DE REGISTRO NÃO DERRUBA A CONSULTA, e esta é uma escolha com
        um custo: um banco fora do ar deixa a leitura sem rastro em vez de
        negar a leitura. A alternativa — recusar — tiraria do ar a consulta
        de milhares de pessoas por causa de uma indisponibilidade de
        infraestrutura, e o registro perdido aparece no log do servidor.
        A trava que importa é outra, e é anterior: entidade REAL não é
        atendida sem banco nenhum.
        """
        if not cfg.tem_banco:
            return
        try:
            banco.registrar_leitura(cfg.banco_url, ent.apelido,
                                    quem_hash=quem_hash, o_que=o_que,
                                    alvo_hash=alvo_hash)
        except Exception:  # noqa: BLE001
            log.exception("AUDITORIA falhou ent=%s o_que=%s",
                          ent.apelido, o_que)

    # -------------------------------------------------------- painel do gestor

    def _gestor_de(apelido: str, pedido: Request) -> entidades.Entidade:
        """A entidade, se quem abriu a sessão é gestor DELA.

        DUAS CONFERÊNCIAS, NESTA ORDEM, E A ORDEM É O QUE IMPORTA: primeiro
        que a sessão é da entidade pedida, depois que quem abriu é gestor
        dela. A ordem inversa diria a um gestor de outra entidade se o CPF
        dele consta como gestor aqui.

        Está num ajudante porque passou a ter dois usos, e as duas
        conferências copiadas à mão divergem — a segunda cópia é sempre a que
        esquece a ordem.
        """
        sessao = _sessao_de(pedido)
        if sessao.entidade != apelido:
            raise _problema(403, "esta sessão não é desta entidade")
        ent = _entidade(apelido)

        try:
            gestores = rol.carregar_gestores(ent.pasta(cfg.raiz))
        except (rol.RolAusente, ValueError) as e:
            # `gestores.csv` ilegível é o mesmo que não haver gestor: ninguém
            # abre o painel. 500 aqui transformaria erro de planilha em erro
            # de servidor, e esconderia a causa de quem pode consertá-la.
            log.error("GESTORES INVÁLIDO em %s: %s", ent.apelido, e)
            raise _problema(
                403,
                "o arquivo de gestores desta entidade não pôde ser lido; "
                "avise quem administra o cadastro",
            ) from None
        if not any(
            portao.marcar_cpf(cpf) == sessao.cpf_hash
            for cpf in gestores.por_cpf
        ):
            raise _problema(403, "esta sessão não é de um gestor desta entidade")
        return ent

    @app.get("/api/entidade/{apelido}/panorama")
    def ver_panorama(apelido: str, pedido: Request) -> dict:
        """O que o sindicato faz primeiro.

        `completude` conta o estado da BASE — quem não se alcança, que campo
        falta —, que é o retrato da primeira semana. Este responde a pergunta
        da terceira: **o que eu resolvo primeiro?** A resposta útil não é uma
        lista de 4.812 pessoas, é uma frase: "homologar a GIFA destrava 1.204
        pessoas". Uma decisão, mil pessoas.

        NÃO LÊ DOCUMENTO, e o diz na resposta. Rodar a leitura de PDF da base
        inteira a cada carregamento de painel é consulta de minutos para
        responder uma tela — e o que decide participação (cargo e período de
        filiação) está no cadastro. Para as pendências basta saber QUAIS
        arquivos chegaram, que o diário já guarda.
        """
        ent = _gestor_de(apelido, pedido)
        _auditar(ent, "panorama",
                 quem_hash=_sessao_de(pedido).cpf_hash)
        catalogo = entendimentos.carregar_categorias(
            entendimentos.PASTA_PADRAO, tuple(ent.categorias)
        )
        # DO BANCO QUANDO HÁ BANCO, do diário quando não há. Não são duas
        # verdades: o banco é projeção do diário, e um teste monta o panorama
        # das duas pontas e exige que sejam idênticos.
        # A BASE INTEIRA quando há banco: a planilha do sindicato mais os
        # cadastros. `cadastros()` continua existindo e continua sendo só o
        # cadastro — é ele que o teste de concordância compara com o diário.
        visao = panorama.montar(
            banco.base(cfg.banco_url, ent.apelido) if cfg.tem_banco
            else deposito.ler_diario(ent.pasta(cfg.raiz)),
            catalogo,
        )
        return {
            "entidade": ent.apelido,
            "nome": ent.nome,
            "manchete": visao.manchete(),
            "pessoas": visao.pessoas,
            "cadastrados": visao.cadastrados,
            "aptos": visao.aptos,
            "categorias": list(visao.categorias),
            "catalogo": visao.catalogo,
            "leu_documentos": visao.leu_documentos,
            "por_acao": [
                {
                    "acao": a.acao,
                    "rotulo": a.rotulo,
                    "participam": a.participam,
                    "indeterminados": a.indeterminados,
                    "nao_participam": a.nao_participam,
                    "meses_somados": a.meses_somados,
                }
                for a in visao.por_acao
            ],
            "gargalos": [
                {
                    "quem": g.quem,
                    "titulo": pendencia.TITULOS[g.quem],
                    "explicacao": pendencia.EXPLICACOES[g.quem],
                    "o_que": g.o_que,
                    "pessoas": g.pessoas,
                    "exemplos": list(g.exemplos),
                }
                for g in visao.gargalos
            ],
            # Dito na resposta, não só na tela: quem consumir esta API por
            # fora recebe o limite junto com o número.
            "limite": (
                "Apurado a partir do CADASTRO e da lista de arquivos "
                "entregues. Nenhum documento foi lido para montar este "
                "panorama, e nada aqui é parecer."
            ),
        }

    @app.get("/api/entidade/{apelido}/completude")
    def ver_completude(apelido: str, pedido: Request) -> dict:
        """O retrato da base, para o gestor da PRÓPRIA entidade.

        Duas conferências, nesta ordem, e a ordem importa: primeiro que a
        sessão é da entidade pedida, depois que quem abriu é gestor dela. A
        ordem inversa diria a um gestor de outra entidade se o CPF dele
        consta como gestor aqui.
        """
        ent = _gestor_de(apelido, pedido)
        pasta = ent.pasta(cfg.raiz)
        caminho_acervo = pasta / "acervo.jsonl"
        pessoas: list[acervo.Pessoa] = []
        if caminho_acervo.is_file():
            linhas = [
                l for l in caminho_acervo.read_text("utf-8").splitlines()
                if l.strip()
            ]
            if linhas:
                # A última ingestão vence: o diário guarda o histórico, o
                # retrato é do acervo vigente.
                ultima = json.loads(linhas[-1])
                for bruto in ultima.get("pessoas") or []:
                    pessoas.append(acervo.Pessoa(
                        cpf=bruto.get("cpf", ""),
                        linha_no_arquivo=bruto.get("linha_no_arquivo", 0),
                        campos=bruto.get("campos") or {},
                        achados=tuple(
                            acervo.Achado(**a)
                            for a in bruto.get("achados") or []
                        ),
                    ))

        retrato = completude.retratar(pessoas, deposito.ler_diario(pasta))

        # A lista NOMINAL. A spec pede "a lista nominal de quem precisa ser
        # procurado", e CPF é pouco melhor que contagem: o gestor não liga
        # para um número, liga para a Carla. O nome está no acervo — guardá-lo
        # e entregar só o CPF seria reter a informação útil.
        nome_de = {
            p.cpf or f"linha-{p.linha_no_arquivo}":
                p.campos.get("nome_completo") or ""
            for p in pessoas
        }
        inalcancaveis = [
            {"chave": chave, "nome": nome_de.get(chave, ""), "motivo": motivo}
            for chave, motivo in retrato.inalcancaveis_por_cpf.items()
        ]

        return {
            "entidade": ent.apelido,
            "nome": ent.nome,
            "manchete": retrato.manchete(),
            "retrato": dataclasses.asdict(retrato),
            "inalcancaveis": inalcancaveis,
            "tem_acervo": caminho_acervo.is_file(),
        }

    @app.post("/api/cadastro")
    async def receber_cadastro(
        pedido: Request,
        token: Annotated[str, Form()],
        linha: Annotated[str, Form()],
        arquivos: Annotated[list[UploadFile], Form()],
    ) -> dict:
        try:
            sessao = portao.abrir_sessao(token)
        except acesso.SessaoInvalida as e:
            raise _problema(401, str(e)) from None

        ent = _entidade(sessao.entidade)

        try:
            bruta = json.loads(linha)
        except json.JSONDecodeError:
            raise _problema(400, "o cadastro não veio em JSON válido") from None

        # O CONTRATO É O DO PRODUTO B (`nucleo.cadastro`), não o do A. O que
        # se pede aqui é contribuição, carreira e filiação — não procuração,
        # identidade e endereço, que são documentos para litigar.
        problemas = conta.conferir(bruta)
        if problemas:
            raise _problema(422, "cadastro incompleto", problemas=problemas)

        limpa = conta.normalizar(bruta)

        # O token diz quem é; o formulário diz de quem é o cadastro. Se não
        # baterem, alguém entrou com o próprio código e está cadastrando
        # outra pessoa — com os documentos dela.
        if not portao.confere_com(sessao, limpa["cpf"]):
            log.warning(
                "CPF do cadastro difere do que abriu a sessão ent=%s",
                ent.apelido,
            )
            raise _problema(
                403, "este cadastro é de um CPF diferente do que fez o acesso"
            )

        recebidos: dict[str, bytes] = {}
        total = 0
        for arquivo in arquivos:
            nome = (arquivo.filename or "").strip()
            if not _nome_de_documento_valido(nome):
                # O nome vindo do cliente NUNCA vira caminho: ou é um dos
                # nomes do contrato, ou o pedido morre aqui.
                raise _problema(422, f"arquivo fora do contrato: {nome!r}")
            if nome in recebidos:
                raise _problema(422, f"arquivo {nome} veio duas vezes")
            corpo = await _ler_limitado(arquivo, LIMITE_ARQUIVO_BYTES)
            total += len(corpo)
            if total > LIMITE_PACOTE_BYTES:
                raise _problema(413, "o pacote de arquivos passa do limite")
            if not corpo:
                raise _problema(422, f"o arquivo {nome} chegou vazio")
            if not validacao.parece_pdf(corpo):
                raise _problema(
                    422,
                    f"o arquivo {nome} não é um PDF; converta antes de enviar",
                )
            serve, caracteres = validacao.texto_extraivel(corpo)
            if not serve:
                raise _problema(
                    422,
                    f"o arquivo {nome} não tem texto selecionável — é uma "
                    f"imagem digitalizada, e sem texto não há o que ler. "
                    f"Gere o PDF a partir do arquivo original, ou digitalize "
                    f"com reconhecimento de texto (OCR).",
                    caracteres=caracteres,
                )
            recebidos[nome] = corpo

        # O que falta NÃO depende do que a pessoa declarou sobre processo:
        # ela pode saber o número e não ter o papel em mãos, e bloquear por
        # isso a deixaria sem resposta — justamente ela, que mais precisa.
        faltas = [
            f"falta o documento obrigatório: {tipo}"
            for tipo in conta.documentos_exigidos(limpa)
            if not any(n.startswith(tipo) for n in recebidos)
        ]
        if faltas:
            raise _problema(422, "pacote incompleto", problemas=faltas)

        anterior = deposito.ja_cadastrado(ent, cfg.raiz, limpa["cpf"])
        recibo = deposito.depositar(ent, cfg.raiz, limpa, recebidos)
        # Um token, um envio.
        portao.gastar_sessao(token)

        # ESPELHA NO BANCO, DEPOIS DO DIÁRIO. A ordem é a mesma do depósito e
        # pelo mesmo motivo: o diário é a autoridade. Se o banco falhar, o
        # envio já está gravado e `banco.reconstruir` o recupera — por isso
        # a falha aqui vira log e não 500: a pessoa não perde o cadastro por
        # causa de um banco fora do ar, e nada se perdeu de fato.
        #
        # E OS ACHADOS SÃO EXTRAÍDOS AQUI, UMA VEZ. Antes, a leitura do PDF
        # acontecia a cada carregamento da tela do filiado, e nunca para o
        # painel do sindicato — ler a base inteira a cada pedido é consulta
        # de minutos para responder uma página.
        if cfg.tem_banco:
            try:
                # SÓ O QUE CHEGOU, não o diário inteiro.
                #
                # Esta linha passava `deposito.ler_diario(...)` — TODOS os
                # registros. `reconstruir` é a função de RECUPERAÇÃO: ela
                # existe para refazer a projeção a partir do diário todo, e
                # estava sendo usada como escrita incremental de um envio.
                # Como o diário é append-only e nunca é podado, o pedido do
                # filiado número N custava O(N), e a campanha inteira O(N²).
                #
                # Medido: 279 comandos SQL num diário de 12 registros, 21 por
                # registro já existente. Na escala que a arquitetura nomeia,
                # 4.812 filiados, são ~101 mil comandos numa transação só —
                # contra um banco pela rede, minutos de transação aberta por
                # cadastro. A ironia é que o comentário logo abaixo já dizia
                # que ler a base inteira a cada pedido é consulta de minutos
                # para responder uma página.
                #
                # A recuperação pelo diário inteiro continua existindo, e
                # tem teste próprio — ela só deixou de rodar aqui.
                banco.reconstruir(cfg.banco_url, ent.apelido,
                                  [recibo.registro])
                for nome, corpo in recebidos.items():
                    banco.guardar_achados(
                        cfg.banco_url, ent.apelido, limpa["cpf"],
                        hashlib.sha256(corpo).hexdigest(),
                        documentos.ler_pdf(corpo),
                    )
            except Exception:  # noqa: BLE001
                log.exception(
                    "ESPELHO falhou para ent=%s protocolo=%s — o diário está "
                    "gravado; refaça com banco.reconstruir",
                    ent.apelido, recibo.protocolo,
                )

        log.info(
            "cadastro gravado ent=%s protocolo=%s arquivos=%d substituiu=%s",
            ent.apelido,
            recibo.protocolo,
            len(recebidos),
            bool(anterior),
        )
        saida = recibo.para_json()
        saida["substituiu_protocolo"] = anterior
        return saida

    return app
