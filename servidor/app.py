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

import csv
import dataclasses
import hashlib
import io
import json
import logging
import pathlib
import re
from typing import Annotated

from fastapi import (
    Body, FastAPI, File, Form, HTTPException, Request, UploadFile,
)
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

# `conta` e não `cadastro`: `entidades.Cadastro` já ocupa esse nome aqui,
# e a colisão deixava o módulo do contrato invisível em silêncio.
from nucleo import atendimento
from nucleo import cadastro as conta
from nucleo import entendimentos, leitura, motor, panorama
from nucleo import dito, participacao, pendencia

from . import documentos_do_sindicato as lote
from . import (
    acervo,
    agenda,
    apagamento,
    conferencia,
    documentos,
    acesso,
    banco,
    acompanhamento,
    completude,
    deposito,
    entidades,
    ingestao,
    remetente,
    rol,
    substituidos,
    trocas,
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

#: De quanto em quanto tempo `/saude` manda conferir a conexão com o servidor
#: de e-mail. Cinco minutos: curto o bastante para o monitor saber no mesmo
#: quarto de hora, longo o bastante para que a rota, que é anônima, não
#: sirva para fazer o portal martelar o provedor.
CONFERIR_ENVIO_A_CADA = 300


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


class TetoDeCorpo:
    """Recusa requisição acima do teto ANTES de o corpo ser lido.

    POR QUE NA APLICAÇÃO, E NÃO NO PROXY.

    Numa requisição `multipart`, o FastAPI precisa ler o corpo INTEIRO para
    montar os parâmetros do handler, e o Starlette, ao ler, derrama cada
    arquivo: até 1 MiB em memória, acima disso num arquivo em `/tmp`. Só
    depois disso o corpo da rota roda — e é lá que o token é conferido e que
    os tetos de `LIMITE_ARQUIVO_BYTES` e `LIMITE_PACOTE_BYTES` são
    aplicados. A ordem estava errada: quem não tem token nenhum fazia o
    servidor escrever em disco antes de levar 401.

    A auditoria classificou isso como dependente da implantação, e com
    razão: com um proxy reverso na frente — o nginx recusa acima de 1 MB por
    padrão — a requisição nem chega. Mas `servidor/__main__.py` sobe o
    uvicorn direto, e uma defesa que mora fora do repositório é a mesma
    hipótese não medida que produziu os outros achados desta auditoria. Aqui
    o teto vale em qualquer implantação, inclusive no dia em que alguém
    trocar o proxy sem avisar.

    DOIS CAMINHOS, e os dois MEDIDOS contra um uvicorn de verdade em
    loopback, com 200 MiB tentados contra um teto de 60 MiB:

    - Com `Content-Length` — o que todo navegador manda, e o que o nosso
      portal manda: **413, e o cliente enviou 0 byte de corpo**. A recusa
      sai do cabeçalho, antes de qualquer leitura.
    - Sem `Content-Length`, corpo em pedaços: só dá para contar enquanto
      chega. Medido, a conexão foi cortada depois de **2,7 MiB** dos 200 MiB
      tentados — o controle de fluxo do uvicorn para de puxar quando
      deixamos de alimentar o corpo. Em nenhum dos dois caminhos ficou
      arquivo temporário em disco.

    A primeira versão deste docstring afirmava que a conexão cai no segundo
    caminho, sem que eu tivesse medido. Era o mesmo tipo de hipótese não
    verificada que produziu os sete achados desta auditoria, e só por sorte
    estava na direção certa. Os números acima vieram da medição.
    """

    def __init__(self, app, teto: int) -> None:
        self.app = app
        self.teto = teto

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        declarado = self._declarado(scope)
        if declarado is not None and declarado > self.teto:
            await self._recusar(send)
            return

        lidos = 0

        async def contando():
            nonlocal lidos
            evento = await receive()
            if evento.get("type") == "http.request":
                lidos += len(evento.get("body", b"") or b"")
                if lidos > self.teto:
                    # Corta o fornecimento. O corpo da rota vê o pedido
                    # morrer e nada chega a disco além do que já passou,
                    # que é no máximo um pedaço.
                    return {"type": "http.disconnect"}
            return evento

        await self.app(scope, contando, send)

    def _declarado(self, scope) -> int | None:
        for nome, valor in scope.get("headers") or ():
            if nome == b"content-length":
                try:
                    return int(valor)
                except ValueError:
                    # Cabeçalho ilegível não vale como declaração; o
                    # contador adiante resolve. Não dá para confiar nele
                    # para liberar, só para recusar.
                    return None
        return None

    async def _recusar(self, send) -> None:
        corpo = json.dumps({
            "detail": {
                "erro": f"o pedido passa do limite de "
                        f"{self.teto // (1024 * 1024)} MB por envio"
            }
        }).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(corpo)).encode("ascii")),
            ],
        })
        await send({"type": "http.response.body", "body": corpo})


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
    # VIGIADO: todo envio deste processo passa por aqui, e o resultado fica
    # onde `/saude` lê. Ver `remetente.Vigiado`.
    correio = remetente.Vigiado(
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

    # O ESQUEMA DA API SÓ EM ENSAIO.
    #
    # `docs_url` e `redoc_url` já estavam desligados, mas `openapi_url` fica
    # em `/openapi.json` por padrão — e ele publica, a um anônimo, a lista de
    # rotas, a forma de cada corpo e de cada resposta, e os nomes internos.
    # Não é vulnerabilidade por si: é o mapa que torna todo o resto mais
    # fácil, inclusive achar rota que ninguém divulgou.
    #
    # Em ensaio continua ligado porque lá não há dado de pessoa e quem
    # desenvolve precisa dele. Desligar nos dois seria pagar conveniência
    # por nada.
    app = FastAPI(
        title="Portal de execução",
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if cfg.modo_ensaio else None,
    )

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

    # O TETO DE CORPO VAI POR FORA DE TUDO, e por isso é o ÚLTIMO a ser
    # acrescentado.
    #
    # `Starlette.add_middleware` faz `insert(0, ...)`: quem entra depois fica
    # mais por fora e roda primeiro — conferido no fonte, não suposto. Este
    # tem de decidir antes de qualquer outra camada tocar o corpo.
    app.add_middleware(TetoDeCorpo, teto=LIMITE_PACOTE_BYTES)

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
        # O ENVIO DE E-MAIL PARADO É SAÚDE RUIM. Sem código ninguém entra,
        # e a tela de quem pede não pode dizer que falhou (seria dizer a um
        # anônimo que o CPF está no rol) — então é AQUI que aparece. A
        # conferência é disparada por esta rota, em fundo e no máximo a cada
        # `CONFERIR_ENVIO_A_CADA` segundos, para pegar o provedor que parou
        # mesmo sem ninguém pedindo código.
        correio.conferir_em_fundo(CONFERIR_ENVIO_A_CADA)
        envio = correio.estado()
        return {
            "ok": not atrasados and not ilegivel and envio != "falhando",
            "trabalho_de_fundo": list(por_tarefa.values()),
            "atrasados": atrasados,
            "estado_ilegivel": ilegivel,
            "modo_ensaio": cfg.modo_ensaio,
            "envio_de_email": "smtp" if cfg.tem_remetente else "arquivo",
            "envio": envio,
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
            acessos = _acessos_da_demonstracao(ent)
            if acessos:
                corpo["acessos_da_demonstracao"] = acessos
        return corpo

    def _acessos_da_demonstracao(ent) -> list[dict]:
        """Com que CPF FICTÍCIO entrar, para a tela dizer.

        Visto na primeira demonstração hospedada: a tela pedia um CPF e
        quem abria o link não tinha como saber qual — eles estavam no
        terminal de quem subiu a demo.

        SÓ É CHAMADA EM ENSAIO, e quem a chama é que garante isso: esta
        rota não exige sessão, e fora do ensaio isto seria publicar CPF. O
        arquivo é escrito por `ferramentas/demo.py`; o servidor não inventa
        acesso nenhum. Qualquer coisa fora da forma esperada: nada sai.
        """
        try:
            bruto = json.loads((ent.pasta(cfg.raiz)
                                / "acessos_da_demonstracao.json")
                               .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(bruto, list):
            return []
        limpos = []
        for item in bruto[:12]:
            if not isinstance(item, dict):
                return []
            quem, cpf, area = (str(item.get(k, "")) for k in
                               ("quem", "cpf", "area"))
            if not (cpf.isdigit() and len(cpf) == 11 and 0 < len(quem) <= 60
                    and area in ("cadastro", "painel")):
                return []
            limpos.append({"quem": quem, "cpf": cpf, "area": area})
        return limpos

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
            # Fail-closed e em voz alta: sem rol nenhum FILIADO entra, e o
            # operador tem que ver isso no log, não descobrir pelo filiado
            # reclamando.
            #
            # O GESTOR ENTRA, e isso mudou de propósito. Antes este ramo
            # devolvia 202 para todos, e o sindicato novo não tinha como
            # enviar a planilha que CRIA o rol sem que nós puséssemos um
            # arquivo vazio antes. O que a regra protege é o portão não
            # abrir para qualquer CPF — e um rol vazio continua não abrindo
            # para ninguém além de quem está em `gestores.csv`, que também
            # vem da entidade.
            log.error(
                "ROL AUSENTE em %s: nenhum filiado recebe código até a "
                "entidade enviar a lista",
                ent.apelido,
            )
            lista = rol.Rol(caminho=ent.pasta(cfg.raiz) / rol.ARQUIVO,
                            por_cpf={}, recusados=())
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
        # QUEM PEDIU PARA SAIR NÃO RECEBE CREDENCIAL NOSSA, e a forma como
        # isso é feito importa.
        #
        # Três comportamentos eram possíveis e só um não tem defeito:
        # não consultar o tombstone manda o código para quem pediu para
        # sair, que é a substância da violação; RECUSAR no portão cria um
        # ORÁCULO, porque um anônimo passaria a descobrir quais CPFs foram
        # apagados a pedido; e consultar sem mandar deixa a resposta
        # idêntica à de qualquer CPF desconhecido.
        #
        # É o terceiro. A pessoa continua podendo PEDIR — a rota não a
        # recusa —, só não há a quem entregar. E a simetria desta resposta é
        # a mesma que impede o portão de virar consulta de filiação.
        if destino is not None and cfg.tem_banco:
            try:
                if portao.marcar_cpf(cpf) in banco.tombstones(
                        cfg.banco_url, ent.apelido):
                    destino = None
            except Exception:  # noqa: BLE001
                # SEM CONSEGUIR CONFERIR, NÃO ENTREGA — e isto NÃO fecha o
                # portão.
                #
                # A escolha anterior aqui era deixar passar, pelo raciocínio
                # de que recusar pararia o portal para todos os filiados por
                # causa de um banco fora do ar. O raciocínio estava errado
                # porque supunha só duas saídas, passar ou recusar. Há uma
                # terceira: tratar a falha DAQUELE pedido como "sem
                # destino" — mesmo 202, mesmo corpo, nada para para quem
                # pede, nenhum oráculo novo — e simplesmente não entregar
                # credencial a quem pode ter pedido para sair.
                #
                # O custo é real e é o lado certo de errar: enquanto o banco
                # estiver fora, ninguém recebe código, e a falha fica no log.
                # A dúvida nunca vira permissão.
                log.exception("não deu para conferir apagamento ent=%s "
                              "cpf=%s — não entregamos o código",
                              ent.apelido, marca)
                destino = None

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

    @app.post("/api/acesso/sair")
    def sair(pedido: Request) -> dict:
        """Encerra a sessão NO SERVIDOR. É o botão "Sair" do portal, que
        existe por causa do computador da sede: uma pessoa depois da outra,
        no mesmo navegador.

        A RESPOSTA É SEMPRE A MESMA — token válido, vencido, inventado ou
        ausente. Uma rota que respondesse diferente serviria para testar
        token.
        """
        bruto = pedido.headers.get("authorization") or ""
        token = bruto[7:] if bruto.lower().startswith("bearer ") else bruto
        portao.encerrar_sessao(token)
        return {"saiu": True}

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
            # FILTRA NO BANCO, não em Python. Esta linha era
            # `next(... for r in banco.base(...))`: lia a base nominal
            # INTEIRA da entidade e descartava tudo menos uma linha. O
            # pedido de uma pessoa pelos dados dela transportava a base
            # completa do sindicato para a memória do processo, a cada
            # carregamento de tela — medido, 21 MB de pico para 4.000
            # pessoas, para responder uma linha. As rotas irmãs já filtravam
            # no banco; esta era a única que não.
            registro = banco.registro_do_cpf(cfg.banco_url, ent.apelido, cpf)
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
        #
        # O MESMO CONSTRUTOR DO PAINEL E DO VEREDICTO GUARDADO. Eram dois, e
        # a diferença entre eles fazia o sindicato ver uma resposta e o
        # filiado outra sobre a mesma pessoa.
        fatos = panorama.fatos_do_cadastro(
            linha,
            _entregues_do_cpf(ent, linha["cpf"]),
            _fatos_lidos_do_cpf(ent, linha["cpf"]),
            rol=substituidos.de_cpf(ent.pasta(cfg.raiz), linha["cpf"]),
        )
        quem = participacao.Filiado(
            cpf=fatos.cpf,
            cargo=fatos.cargo,
            situacao=fatos.situacao,
            filiado_desde=fatos.filiado_desde,
            filiado_ate=fatos.filiado_ate,
            no_rol=fatos.no_rol,
            rol_das_acoes=fatos.rol_das_acoes,
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
                    # A FRASE DO FILIADO, não a do veredicto guardado: aqui
                    # quem lê é a própria pessoa, e "esta pessoa consta do
                    # rol" lê como dossiê sobre outra (`nucleo/dito.py`).
                    "motivos": [dito.para_voce(m) for m in p.motivos],
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
                    "motivos": [dito.para_voce(m) for m in o.motivos],
                    "notas": [dito.para_voce(n) for n in o.notas],
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
        registros = (
            banco.base(cfg.banco_url, ent.apelido) if cfg.tem_banco
            else deposito.ler_diario(ent.pasta(cfg.raiz))
        )
        # OS DOCUMENTOS JÁ LIDOS ENTRAM. Os achados são gravados na chegada
        # do cadastro justamente para o painel poder olhar a base inteira —
        # e o painel continuou sem olhar, cobrando do sindicato "a leitura
        # da sentença já entregue" de sentença já lida. Sem banco não há
        # achado gravado: o panorama sai sem documento, e DIZ isso.
        lidos = (
            banco.fatos_lidos_da_entidade(cfg.banco_url, ent.apelido)
            if cfg.tem_banco else None
        )
        visao = panorama.montar(
            registros, catalogo, lidos_por_cpf=lidos,
            rol_por_cpf=substituidos.por_cpf(ent.pasta(cfg.raiz)))
        return {
            "entidade": ent.apelido,
            "nome": ent.nome,
            "mudancas": _o_que_mudou(ent, catalogo, registros),
            "aguardando_leitura": _aguardando_leitura(ent),
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
                    # Quem lê o painel é o GESTOR: o título do filiado
                    # ("O que depende de você") diria que a tarefa é dele.
                    "titulo": pendencia.TITULOS_DO_SINDICATO[g.quem],
                    "explicacao": pendencia.EXPLICACOES_DO_SINDICATO[g.quem],
                    "o_que": g.o_que,
                    "pessoas": g.pessoas,
                    "exemplos": list(g.exemplos),
                    # Onde, no painel, o gestor resolve isto — ou vazio.
                    "onde": g.onde,
                }
                for g in visao.gargalos
            ],
            # Dito na resposta, não só na tela: quem consumir esta API por
            # fora recebe o limite junto com o número.
            # DOIS TEXTOS, porque são dois estados e afirmar o errado nos
            # dois sentidos é defeito: dizer "nenhum documento foi lido" de
            # um panorama que leu esconde do sindicato que a resposta já
            # considera as sentenças; dizer que leu sem ter lido faria o
            # contrário.
            "limite": (
                "Apurado a partir do CADASTRO e do que os documentos "
                "entregues disseram quando foram lidos, na chegada. A leitura "
                "é automática e só usa o que deu para afirmar com certeza — "
                "nada aqui é parecer."
                if visao.leu_documentos else
                "Apurado a partir do CADASTRO e da lista de arquivos "
                "entregues. Nenhum documento foi lido para montar este "
                "panorama, e nada aqui é parecer."
            ),
        }

    #: Quantos nomes acompanham cada grupo de mudança. Mais que isto vira
    #: parede de texto no painel; menos não dá para o gestor reconhecer de
    #: quem se trata.
    NOMES_POR_MUDANCA = 10

    def _o_que_mudou(ent: entidades.Entidade, catalogo, base) -> dict:
        """O que mudou de veredicto no catálogo de AGORA, agrupado e com nome.

        SEM BANCO, DIZ QUE NÃO SABE. Devolver `total: 0` afirmaria que nada
        mudou — e é exatamente esse o relatório tranquilizador que faz
        ninguém perceber. A dúvida não vira resposta.

        O NOME VEM DA BASE QUE JÁ ESTÁ EM MÃOS, não de uma consulta nova:
        quem monta o panorama já leu a base inteira. E nome, não CPF:
        "3 pessoas mudaram de FALTA para PODE" não é acionável, porque o
        gestor liga para gente — e o CPF em claro numa resposta de API é um
        segundo lugar com dado pessoal.
        """
        vazio = {"catalogo": catalogo.assinatura, "total": 0,
                 "sem_banco": not cfg.tem_banco, "grupos": []}
        if not cfg.tem_banco or not catalogo.assinatura:
            return vazio
        try:
            mudou = banco.mudancas(cfg.banco_url, ent.apelido,
                                   assinatura=catalogo.assinatura)
        except Exception:  # noqa: BLE001
            log.exception("não deu para apurar as mudanças ent=%s",
                          ent.apelido)
            # Falha de apuração também não vira zero: `sem_banco` é a forma
            # de dizer "não dá para saber", e é o que a tela mostra.
            return {**vazio, "sem_banco": True}

        nomes = {}
        for envio in base:
            linha = envio.get("linha") or {}
            digitos = conta.so_digitos(linha.get("cpf") or "")
            if digitos:
                nomes[digitos] = str(linha.get("nome_completo") or "")

        grupos: dict[tuple[str, str, str, str], list[str]] = {}
        for m in mudou:
            chave = (m["referencia"], m["trilha"], m["de"], m["para"])
            grupos.setdefault(chave, []).append(
                nomes.get(m["cpf"]) or "(sem nome na base)")
        return {
            "catalogo": catalogo.assinatura,
            "total": len(mudou),
            "sem_banco": False,
            "grupos": [
                {
                    "referencia": referencia,
                    "trilha": trilha,
                    "de": de,
                    "para": para,
                    "pessoas": len(quem),
                    "exemplos": sorted(quem)[:NOMES_POR_MUDANCA],
                }
                for (referencia, trilha, de, para), quem
                in sorted(grupos.items())
            ],
        }

    def _aguardando_leitura(ent: entidades.Entidade) -> dict:
        """Quantos documentos esperam que uma PESSOA leia, e de quanta gente.

        Aceitar o documento escaneado e não mostrar a fila criaria uma fila
        invisível: o filiado acha que entregou, o sindicato não sabe que há
        o que ler. CONTAGEM, não lista — quem são aparece nas pendências.

        SEM BANCO, DIZ QUE NÃO SABE, pela mesma razão das mudanças: zero
        afirmaria que não há nada esperando.
        """
        vazio = {"documentos": 0, "pessoas": 0, "ilegiveis": 0,
                 "sem_banco": not cfg.tem_banco}
        if not cfg.tem_banco:
            return vazio
        try:
            documentos_, pessoas = banco.aguardando_leitura(cfg.banco_url,
                                                            ent.apelido)
            ilegiveis = banco.nem_pessoa_leu(cfg.banco_url, ent.apelido)
        except Exception:  # noqa: BLE001
            log.exception("não deu para contar a fila de leitura ent=%s",
                          ent.apelido)
            return {**vazio, "sem_banco": True}
        return {"documentos": documentos_, "pessoas": pessoas,
                "ilegiveis": ilegiveis, "sem_banco": False}

    def _apagados_na_planilha(ent: entidades.Entidade, pessoas) -> int:
        """Quantos CPFs da planilha do sindicato têm tombstone.

        Zero quando não há banco: sem ele não há tombstone para consultar, e
        inventar um número seria pior que não ter.
        """
        if not cfg.tem_banco:
            return 0
        try:
            marcados = banco.tombstones(cfg.banco_url, ent.apelido)
        except Exception:  # noqa: BLE001
            log.exception("não deu para contar os apagados ent=%s",
                          ent.apelido)
            return 0
        if not marcados:
            return 0
        return sum(1 for cpf in {p.cpf for p in pessoas if p.cpf}
                   if portao.marcar_cpf(cpf) in marcados)

    @app.post("/api/entidade/{apelido}/apagar")
    def apagar_filiado(apelido: str, corpo: dict, pedido: Request) -> dict:
        """Apaga um filiado a pedido (LGPD art. 18, VI).

        QUEM ACIONA É O SINDICATO. Ele tem a relação com o filiado e foi ele
        que nos confiou o dado; sob a LGPD ele tende a ser o CONTROLADOR e
        nós o operador, e é o controlador que responde ao titular.

        NÃO DEVOLVE 404 PARA CPF DE FORA DA BASE, e isto é deliberado: um
        404 aqui diria a quem tem sessão de gestor se um CPF está na base
        desta entidade — oráculo, e sobre dado sensível. A resposta é a
        mesma, e o que varia é só a contagem do que saiu.

        `vestigios` NÃO VAZIO NÃO É ERRO: é a resposta honesta de que sobrou
        coisa. Dizer 200 e esconder o resto seria afirmar um apagamento que
        não aconteceu.
        """
        ent = _gestor_de(apelido, pedido)
        sessao = _sessao_de(pedido)
        cpf = conta.so_digitos(str(corpo.get("cpf", "")))
        if not validacao.cpf_valido(cpf):
            raise _problema(400, "CPF inválido")
        # ANTES DE QUALQUER EFEITO. `apagamento.apagar` também trava, como
        # retaguarda, mas lá a falha já viraria 500 — e 500 não diz ao
        # gestor que ele só precisa encurtar o texto.
        for rotulo in ("motivo", "pedido_por"):
            texto = str(corpo.get(rotulo, ""))
            if len(texto) > apagamento.TETO_DO_TEXTO:
                raise _problema(
                    400,
                    f"{rotulo} tem {len(texto)} caracteres e o limite é "
                    f"{apagamento.TETO_DO_TEXTO}. Recusamos em vez de "
                    f"cortar: o registro de um apagamento precisa guardar "
                    f"exatamente o que você escreveu.",
                )
        if not cfg.tem_banco:
            raise _problema(
                503,
                "este servidor está sem banco de dados, e o apagamento "
                "precisa registrar o tombstone para ser retomável e para "
                "impedir que a próxima planilha recrie a pessoa",
            )

        marcador = portao.marcar_cpf(cpf)
        # AQUI NÃO SERVE `_auditar`, E A DIFERENÇA É O QUE ESTÁ EM JOGO.
        #
        # `_auditar` engole exceção, e essa decisão foi tomada para LEITURA:
        # lá, registro perdido deixa a consulta sem rastro, mas nenhum dado
        # se perde e a pessoa continua atendida. Aqui o ato é destrutivo e
        # irreversível — o mesmo engolir significaria pessoa apagada sem
        # nenhum registro de qual gestor mandou, que é precisamente o que o
        # item 9 da spec existe para impedir.
        #
        # Então falha fechado: registra PRIMEIRO, e se o registro não entra,
        # nada é apagado. O custo é um apagamento adiado enquanto o banco
        # estiver fora; o custo do contrário é um apagamento sem autor.
        try:
            banco.registrar_leitura(cfg.banco_url, ent.apelido,
                                    quem_hash=sessao.cpf_hash,
                                    o_que="apagar", alvo_hash=marcador)
        except Exception:  # noqa: BLE001
            log.exception("AUDITORIA DO APAGAMENTO falhou ent=%s",
                          ent.apelido)
            raise _problema(
                503,
                "não conseguimos registrar quem pediu este apagamento, e "
                "sem esse registro não apagamos nada. Nada foi alterado: "
                "tente de novo.",
            ) from None
        try:
            saida = apagamento.apagar(
                cfg.banco_url, ent, cfg.raiz, cpf,
                motivo=str(corpo.get("motivo", "")),
                pedido_por=str(corpo.get("pedido_por", "")),
                portao=portao,
            )
        except Exception:  # noqa: BLE001
            log.exception("APAGAR falhou ent=%s cpf=%s", ent.apelido,
                          _hash_curto(cpf))
            raise _problema(
                500,
                "não conseguimos concluir o apagamento. Nada foi apagado "
                "sem registro: confira com a ferramenta de linha de comando "
                "e repita",
            ) from None
        log.info("apagado a pedido ent=%s cpf=%s vestigios=%d",
                 ent.apelido, _hash_curto(cpf), len(saida["vestigios"]))
        return saida

    # ------------------------------------ a porta de entrada do sindicato

    #: Teto da planilha. A de 100 mil filiados não chega a um décimo disto;
    #: o que passa daqui é exportação que levou a folha inteira do Excel.
    LIMITE_DA_PLANILHA = 20 * 1024 * 1024
    #: Quantas sobras voltam na resposta. O total vai junto.
    SOBRAS_NA_RESPOSTA = 50

    def _exigir_banco_para_ingerir() -> None:
        if not cfg.tem_banco:
            raise _problema(
                503,
                "este servidor está sem banco de dados. A base do sindicato "
                "mora nele, e é nele que se confere quem pediu para sair",
            )

    def _conferir_confirmacao(confirmar: str, soma: str) -> bool:
        """`True` se é para GRAVAR. Levanta 409 se o arquivo é outro.

        A CONFIRMAÇÃO VALE PARA O ARQUIVO CONFERIDO. A prévia devolve a
        impressão digital do que foi lido, e é ela que volta na segunda
        etapa: se o que chega agora é outro arquivo, o gestor confirmaria
        uma base que não viu.
        """
        if not confirmar:
            return False
        if confirmar != soma:
            raise _problema(
                409,
                "o arquivo enviado agora não é o que foi conferido. Nada "
                "foi gravado: confira este arquivo antes de confirmar.",
            )
        return True

    def _processar_planilha(ent: entidades.Entidade, quem: str, nome: str,
                            corpo: bytes, confirmar: str) -> dict:
        soma = hashlib.sha256(corpo).hexdigest()
        pessoas, problemas = acervo.ler_bytes(corpo, nome)
        if problemas:
            # A mesma regra da ferramenta: problema DE ARQUIVO recusa, com o
            # motivo. Problema de linha não recusa nada — vira achado.
            raise _problema(422, "a planilha não pôde ser usada",
                            problemas=problemas)
        try:
            ficam, apagadas = ingestao.sem_apagados(
                pessoas, banco_url=cfg.banco_url, apelido=ent.apelido,
                marcador_de=portao.marcar_cpf)
        except ingestao.IngestaoRecusada as e:
            log.error("PLANILHA recusada ent=%s: %s", ent.apelido, e)
            raise _problema(
                503,
                "não conseguimos conferir quem pediu apagamento, e sem isso "
                "a planilha poderia recriar quem pediu para sair. Nada foi "
                "gravado: tente de novo.",
            ) from None

        try:
            plano = ingestao.plano_do_portao(ent.pasta(cfg.raiz), ficam)
        except ingestao.IngestaoRecusada as e:
            log.error("PLANILHA recusada ent=%s: %s", ent.apelido, e)
            raise _problema(
                409,
                "o cadastro de acesso desta entidade não pôde ser lido, e "
                "sem ele não dá para saber quem já entra no portal. Nada "
                "foi gravado: avise quem administra o cadastro.",
            ) from None

        retrato = completude.retratar(ficam)
        resposta = {
            "sha256": soma,
            "arquivo": nome,
            "manchete": retrato.manchete(),
            "linhas": retrato.linhas,
            "pessoas": retrato.total,
            "alcancaveis": retrato.alcancaveis,
            "inalcancaveis": retrato.inalcancaveis,
            "divergentes": retrato.divergentes,
            "colunas_ausentes": list(retrato.colunas_ausentes),
            # QUANTOS, nunca quem: a pessoa pediu para sair. O número existe
            # para o sindicato corrigir a FONTE — enquanto ela estiver na
            # planilha dele, toda ingestão vai pulá-la de novo.
            "apagados_a_pedido": apagadas,
            # O QUE MUDA EM QUEM CONSEGUE ENTRAR. Só contagens: quem é novo
            # entra, e troca de e-mail de quem já entra NÃO vale por aqui —
            # fica pedida, esperando quem opera o servidor.
            "acesso": plano.para_json(),
            "gravado": False,
        }
        if not _conferir_confirmacao(confirmar, soma):
            return resposta
        try:
            feito = ingestao.gravar_planilha(
                ent, cfg.raiz, ficam, origem=nome, banco_url=cfg.banco_url,
                marcador_de=portao.marcar_cpf, quem=quem)
        except ingestao.IngestaoRecusada as e:
            log.error("PLANILHA recusada ent=%s: %s", ent.apelido, e)
            raise _problema(
                409,
                "o cadastro de acesso desta entidade mudou enquanto a "
                "planilha era conferida. Nada foi gravado: envie de novo.",
            ) from None
        feito_no_portao = feito["portao"]
        log.info("planilha ingerida ent=%s pessoas=%d novos_no_acesso=%d",
                 ent.apelido, retrato.total, len(feito_no_portao.novos))
        if feito_no_portao.trocas or feito_no_portao.seguradas:
            log.warning(
                "TROCA DE E-MAIL pedida ent=%s quantas=%d entradas=%d — "
                "conferir com ferramentas/trocas_de_email.py",
                ent.apelido, len(feito_no_portao.trocas),
                len(feito_no_portao.seguradas))
        if feito["pedidos_novos"]:
            _avisar_os_donos(ent)
            _avisar_quem_opera(ent, feito["pedidos_novos"])
        return {**resposta, "acesso": feito_no_portao.para_json(),
                # Quem pediu para sair ENTRE a conferência e a gravação
                # também não entrou, e a conta tem de dizer isso.
                "apagados_a_pedido": apagadas + feito["apagadas"],
                "pessoas": feito["retrato"].total,
                "gravado": True, "projetadas": feito["projetadas"]}

    def _avisar_os_donos(ent: entidades.Entidade) -> None:
        """Quem hoje recebe o código fica sabendo que pediram a troca.

        É a única pessoa que SABE se pediu. NUNCA DERRUBA A PLANILHA, pelo
        mesmo motivo do aviso a quem opera — e o que falhar aqui o lembrete
        diário tenta de novo, porque só o que saiu fica registrado.
        """
        try:
            sairam, falharam = trocas.avisar_donos(
                ent.pasta(cfg.raiz), nome=ent.nome, correio=correio)
        except Exception:  # noqa: BLE001
            log.exception("AVISO ao dono do e-mail falhou ent=%s",
                          ent.apelido)
            return
        if falharam:
            # QUANTOS, sem endereço: a exceção do correio costuma trazê-lo.
            log.error("AVISO ao dono do e-mail: %d não saíram ent=%s — o "
                      "lembrete diário tenta de novo", falharam, ent.apelido)
        if sairam:
            log.info("aviso ao dono do e-mail ent=%s enviados=%d",
                     ent.apelido, sairam)

    def _avisar_quem_opera(ent: entidades.Entidade, novos: int) -> None:
        """O pedido que a planilha deixou chega a quem decide.

        A linha de log acima era o ÚNICO jeito de alguém ficar sabendo, e
        log é lugar que se olha depois que algo quebrou.

        NUNCA DERRUBA A PLANILHA. O aviso é para nós; o sindicato não tem
        de reenviar a base porque o nosso correio caiu. O pedido já está
        gravado, e a tarefa `pedidos` do agendador lembra todo dia enquanto
        ele esperar.
        """
        if not cfg.email_de_quem_opera:
            log.warning("PEDIDO sem a quem avisar ent=%s — defina "
                        "PROTOCOL_EMAIL_DE_QUEM_OPERA", ent.apelido)
            return
        try:
            trocas.avisar_quem_opera(
                ent.pasta(cfg.raiz), apelido=ent.apelido, nome=ent.nome,
                raiz=cfg.raiz, correio=correio,
                destino=cfg.email_de_quem_opera, novos=novos)
        except Exception:  # noqa: BLE001
            log.exception("AVISO a quem opera falhou ent=%s — o pedido "
                          "está gravado; o lembrete diário repete",
                          ent.apelido)

    def _nome_de_envio(arquivo: UploadFile) -> str:
        """O nome que o gestor deu, SÓ COMO RÓTULO. Nunca vira caminho: é
        cortado no último separador e no tamanho."""
        return pathlib.PurePath(
            (arquivo.filename or "arquivo").replace("\\", "/")).name[:120]

    @app.post("/api/entidade/{apelido}/planilha")
    async def enviar_planilha(
        apelido: str,
        pedido: Request,
        # Com padrão, para a SESSÃO ser conferida antes do formato: sem ele
        # o FastAPI recusa o pedido sem arquivo antes de esta função rodar.
        arquivo: UploadFile | None = File(None),
        confirmar: str = Form(""),
    ) -> dict:
        """O sindicato manda a lista de filiados — CSV ou .xlsx.

        EM DUAS ETAPAS, E A PRIMEIRA NÃO GRAVA NADA. Sem `confirmar`, volta
        o que o arquivo traz: quantas pessoas, quantas o sindicato não
        alcança, quantas pediram para sair. Com `confirmar` igual à
        impressão digital devolvida, grava.

        O miolo é `servidor/ingestao.py`, o MESMO da ferramenta de linha de
        comando: as travas dela — quem pediu para sair não volta, falha
        fechada sem os tombstones — valem aqui sem terem sido reescritas.

        A PLANILHA CONFIRMADA TAMBÉM LIGA O ACESSO: quem é novo passa a
        receber código. O que ela NÃO faz é trocar o e-mail de quem já
        entra — com isso, esta sessão valeria todas as contas do sindicato.
        A troca fica pedida (`servidor/trocas.py`), e esta rota só conta.
        """
        ent = _gestor_de(apelido, pedido)
        sessao = _sessao_de(pedido)
        _exigir_banco_para_ingerir()
        if arquivo is None:
            raise _problema(422, "envie o arquivo da planilha")
        corpo = await _ler_limitado(arquivo, LIMITE_DA_PLANILHA)
        if not corpo:
            raise _problema(422, "a planilha chegou vazia")
        _auditar(ent, "enviar_planilha", quem_hash=sessao.cpf_hash)
        # Ler dez mil linhas e projetá-las no banco leva segundos. Fora do
        # laço de eventos, para o portal do filiado não parar enquanto isso.
        return await run_in_threadpool(
            _processar_planilha, ent, sessao.cpf_hash,
            _nome_de_envio(arquivo), corpo, confirmar)

    def _processar_documentos(ent: entidades.Entidade,
                              arquivos: list[tuple[str, bytes]],
                              confirmar: str) -> dict:
        cpfs = ingestao.cpfs_da_base(cfg.banco_url, ent.apelido,
                                     ent.pasta(cfg.raiz))
        if not cpfs:
            # Sem base, nenhum arquivo casa com ninguém. Aceitar e devolver
            # "0 casaram" faria o gestor achar que os arquivos estão errados.
            raise _problema(
                409,
                "a base desta entidade está vazia. Envie primeiro a "
                "planilha de filiados: é por ela que cada documento "
                "encontra o dono.",
            )
        r = lote.casar(arquivos, cpfs)
        soma = hashlib.sha256("\n".join(sorted(
            hashlib.sha256(corpo).hexdigest() for _, corpo in arquivos
        )).encode()).hexdigest()
        resposta = {
            "sha256": soma,
            "arquivos": len(arquivos),
            "casaram": sum(len(v) for v in r.casados.values()),
            "pessoas": len(r.casados),
            # A PILHA DO QUE NÃO CASOU, com o motivo de cada um. "3.812 de
            # 4.000" esconde 188 sentenças de gente que ficaria sem resposta.
            "sobraram": [{"arquivo": x.arquivo, "motivo": x.motivo}
                         for x in r.sobraram[:SOBRAS_NA_RESPOSTA]],
            "sobraram_total": len(r.sobraram),
            "avisos": list(r.avisos[:SOBRAS_NA_RESPOSTA]),
            "gravado": False,
        }
        if not _conferir_confirmacao(confirmar, soma):
            return resposta
        try:
            feito = ingestao.gravar_documentos(
                ent, cfg.raiz, r, cfg.banco_url,
                marcador_de=portao.marcar_cpf)
        except ingestao.IngestaoRecusada as e:
            log.error("DOCUMENTOS recusados ent=%s: %s", ent.apelido, e)
            raise _problema(
                503,
                "não conseguimos conferir quem pediu apagamento, e sem isso "
                "os documentos poderiam recriar quem pediu para sair. Nada "
                "foi gravado: tente de novo.",
            ) from None
        log.info("documentos do sindicato ent=%s gravados=%d sobraram=%d",
                 ent.apelido, feito["gravados"], len(r.sobraram))
        # O QUE FOI GRAVADO, não o que a prévia casou: quem pediu para sair
        # entre uma coisa e outra não entra, nem na conta.
        return {**resposta, "casaram": feito["gravados"],
                "pessoas": feito["pessoas"], "gravado": True}

    @app.post("/api/entidade/{apelido}/documentos-do-sindicato")
    async def enviar_documentos_do_sindicato(
        apelido: str,
        pedido: Request,
        arquivos: list[UploadFile] = File(default=[]),
        confirmar: str = Form(""),
    ) -> dict:
        """As sentenças e certidões que o SINDICATO já guarda — PDFs, ou um
        .zip deles.

        Cada arquivo casa com alguém da base pelo CPF, no nome do arquivo ou
        no texto. Em duas etapas, como a planilha: a primeira mostra o que
        casou e o que SOBROU, com o motivo; a segunda grava.

        O NOME QUE O SINDICATO DEU AO ARQUIVO NUNCA VIRA CAMINHO: no disco
        ele ganha o nome do tipo (`ingestao.gravar_documentos`). E o .zip é
        aberto por `lote.abrir_zip`, que conta os bytes enquanto lê — a
        trava contra zip que declara um tamanho e entrega outro.
        """
        ent = _gestor_de(apelido, pedido)
        sessao = _sessao_de(pedido)
        _exigir_banco_para_ingerir()
        if not arquivos:
            raise _problema(422, "envie os documentos, ou um .zip com eles")

        recebidos: list[tuple[str, bytes]] = []
        total = 0
        for arquivo in arquivos:
            nome = _nome_de_envio(arquivo)
            corpo = await _ler_limitado(arquivo, LIMITE_ARQUIVO_BYTES)
            total += len(corpo)
            if total > LIMITE_PACOTE_BYTES:
                raise _problema(
                    413,
                    "o envio passa do limite. Mande os documentos em "
                    "partes menores.",
                )
            if nome.lower().endswith(".zip"):
                try:
                    recebidos += lote.abrir_zip(corpo)
                except lote.ZipRecusado as e:
                    raise _problema(
                        422, f"o arquivo {nome} não pôde ser aberto: {e}"
                    ) from None
            else:
                recebidos.append((nome, corpo))
        if not recebidos:
            raise _problema(422, "não havia nenhum PDF no envio")
        _auditar(ent, "enviar_documentos", quem_hash=sessao.cpf_hash)
        return await run_in_threadpool(
            _processar_documentos, ent, recebidos, confirmar)

    # --------------------------------------------- o rol de substituídos

    def _acao_do_catalogo(ent: entidades.Entidade, acao: str):
        """A ação coletiva, se é do catálogo que ESTA entidade contratou.

        O rol de uma ação de outra carreira não é assunto deste sindicato,
        e um id qualquer gravado aqui ficaria respondendo por ação nenhuma.
        """
        catalogo = entendimentos.carregar_categorias(
            entendimentos.PASTA_PADRAO, tuple(ent.categorias)
        )
        for a in catalogo.acoes:
            if a.id == acao:
                return a
        raise _problema(
            422,
            "esta ação não está entre as ações coletivas do seu sindicato "
            "no sistema",
        )

    def _base_sem_apagados(ent: entidades.Entidade) -> set[str]:
        """Quem a entidade atende HOJE, sem quem pediu para sair.

        O segundo filtro é redundante de propósito: quem foi apagado já
        saiu da base. Mas um tombstone ilegível tem de RECUSAR, e não
        deixar passar — é a regra de toda porta que grava dado de pessoa.
        """
        import types

        pasta = ent.pasta(cfg.raiz)
        cpfs = ingestao.cpfs_da_base(cfg.banco_url, ent.apelido, pasta)
        ficam, _ = ingestao.sem_apagados(
            [types.SimpleNamespace(cpf=c) for c in sorted(cpfs)],
            banco_url=cfg.banco_url, apelido=ent.apelido,
            marcador_de=portao.marcar_cpf)
        return {p.cpf for p in ficam}

    def _processar_rol(ent: entidades.Entidade, quem: str, nome: str,
                       corpo: bytes, acao, completo: bool,
                       confirmar: str) -> dict:
        try:
            lido = substituidos.ler_arquivo(corpo, nome)
        except substituidos.RolIlegivel as e:
            raise _problema(422, str(e)) from None
        # A IMPRESSÃO DIGITAL COBRE A AÇÃO E A DECLARAÇÃO, não só o arquivo:
        # "lista completa" é o que põe gente FORA do rol, e confirmar com
        # ela trocada seria gravar o que o gestor não viu.
        soma = hashlib.sha256(
            hashlib.sha256(corpo).hexdigest().encode()
            + f"|{acao.id}|{'completo' if completo else 'parcial'}".encode()
        ).hexdigest()

        def resposta(plano: substituidos.Plano, gravado: bool) -> dict:
            return {
                "acao": acao.id,
                "rotulo": acao.rotulo,
                "sha256": soma,
                "completo": plano.completo,
                # O que o gestor declarou. Difere de `completo` quando há
                # linha ilegível, e aí a declaração não valeu.
                "declarado_completo": plano.declarado_completo,
                # SÓ CONTAGENS. Os CPFs de quem consta ficam no arquivo da
                # entidade; a tela não precisa deles para decidir.
                "constam": len(plano.constam),
                "nao_constam": len(plano.nao_constam),
                "sem_resposta": plano.sem_resposta,
                "fora_da_base": plano.fora_da_base,
                "invalidas": plano.invalidas,
                "gravado": gravado,
            }

        try:
            if not _conferir_confirmacao(confirmar, soma):
                return resposta(substituidos.planejar(
                    lido, _base_sem_apagados(ent), acao=acao.id,
                    completo=completo), False)
            # O PLANO QUE VALE É O DA HORA DE GRAVAR, cruzado com a base
            # com o apagamento parado — não o da prévia.
            plano = substituidos.enviar(
                ent.pasta(cfg.raiz), lido, acao=acao.id, completo=completo,
                base_de=lambda: _base_sem_apagados(ent), quem=quem,
                arquivo=nome, sha256=hashlib.sha256(corpo).hexdigest())
        except ingestao.IngestaoRecusada as e:
            log.error("ROL recusado ent=%s: %s", ent.apelido, e)
            raise _problema(
                503,
                "não conseguimos conferir quem pediu apagamento, e sem isso "
                "o rol poderia guardar de novo quem pediu para sair. Nada "
                "foi gravado: tente de novo.",
            ) from None
        log.info("rol de substituídos ent=%s acao=%s constam=%d "
                 "nao_constam=%d completo=%s", ent.apelido, acao.id,
                 len(plano.constam), len(plano.nao_constam), plano.completo)
        return resposta(plano, True)

    @app.post("/api/entidade/{apelido}/rol-de-substituidos")
    async def enviar_rol_de_substituidos(
        apelido: str,
        pedido: Request,
        arquivo: UploadFile | None = File(None),
        acao: str = Form(""),
        completo: str = Form(""),
        confirmar: str = Form(""),
    ) -> dict:
        """O sindicato envia o rol de substituídos de UMA ação coletiva.

        Era o que faltava para o produto responder: o motor pergunta se a
        pessoa consta do rol, e nenhum caminho gravava a resposta.

        EM DUAS ETAPAS, como a planilha: sem `confirmar`, conta e não grava.
        `completo` é a declaração de que a lista é o rol INTEIRO — só com
        ela quem não aparece passa a constar como fora. As regras estão em
        `servidor/substituidos.py`.

        NÃO EXIGE BANCO: a autoridade é o arquivo da entidade, e a base sai
        do banco quando há e do cadastro de acesso quando não há.
        """
        ent = _gestor_de(apelido, pedido)
        sessao = _sessao_de(pedido)
        alvo = _acao_do_catalogo(ent, acao.strip())
        if arquivo is None:
            raise _problema(422, "envie o arquivo do rol")
        corpo = await _ler_limitado(arquivo, LIMITE_DA_PLANILHA)
        if not corpo:
            raise _problema(422, "o arquivo do rol chegou vazio")
        _auditar(ent, "enviar_rol_de_substituidos",
                 quem_hash=sessao.cpf_hash)
        return await run_in_threadpool(
            _processar_rol, ent, sessao.cpf_hash, _nome_de_envio(arquivo),
            corpo, alvo, bool(completo.strip()), confirmar)

    @app.get("/api/entidade/{apelido}/rol-de-substituidos")
    def ver_rol_de_substituidos(apelido: str, pedido: Request) -> dict:
        """As ações coletivas do sindicato, e o rol de cada uma — em
        contagens. Nenhum CPF sai daqui."""
        ent = _gestor_de(apelido, pedido)
        _auditar(ent, "ver_rol_de_substituidos",
                 quem_hash=_sessao_de(pedido).cpf_hash)
        catalogo = entendimentos.carregar_categorias(
            entendimentos.PASTA_PADRAO, tuple(ent.categorias)
        )
        pasta = ent.pasta(cfg.raiz)
        resumo = substituidos.resumo(
            pasta, ingestao.cpfs_da_base(cfg.banco_url, ent.apelido, pasta))
        return {
            "entidade": ent.apelido,
            "acoes": [
                {"acao": a.id, "rotulo": a.rotulo,
                 "rol": resumo.get(a.id)}
                for a in catalogo.acoes
            ],
        }

    @app.post("/api/entidade/{apelido}/rol-de-substituidos/retirar")
    def retirar_rol_de_substituidos(apelido: str, corpo: dict,
                                    pedido: Request) -> dict:
        """Desfaz o rol de uma ação: arquivo errado, ou ação errada."""
        ent = _gestor_de(apelido, pedido)
        sessao = _sessao_de(pedido)
        alvo = _acao_do_catalogo(ent, str(corpo.get("acao") or "").strip())
        _auditar(ent, "retirar_rol_de_substituidos",
                 quem_hash=sessao.cpf_hash)
        retirado = substituidos.retirar(ent.pasta(cfg.raiz), alvo.id,
                                        quem=sessao.cpf_hash)
        if retirado:
            log.info("rol de substituídos RETIRADO ent=%s acao=%s",
                     ent.apelido, alvo.id)
        return {"acao": alvo.id, "retirado": retirado}

    # --------------------------------------------- nome por nome

    def _base_avaliada(ent: entidades.Entidade) -> list:
        """Cada pessoa da base, avaliada — pelo MESMO laço do panorama."""
        catalogo = entendimentos.carregar_categorias(
            entendimentos.PASTA_PADRAO, tuple(ent.categorias)
        )
        if cfg.tem_banco:
            registros = banco.base(cfg.banco_url, ent.apelido)
            lidos = banco.fatos_lidos_da_entidade(cfg.banco_url, ent.apelido)
        else:
            registros = deposito.ler_diario(ent.pasta(cfg.raiz))
            lidos = None
        return panorama.por_pessoa(
            registros, catalogo, lidos,
            substituidos.por_cpf(ent.pasta(cfg.raiz)))

    def _cpf_mascarado(cpf: str) -> str:
        """`***.444.777-**`: dá para o gestor distinguir dois homônimos, e
        não é o CPF. O inteiro só sai na exportação, que é pedida de
        propósito e registrada."""
        d = conta.so_digitos(cpf)
        return f"***.{d[3:6]}.{d[6:9]}-**" if len(d) == 11 else ""

    @app.get("/api/entidade/{apelido}/pessoas")
    def ver_pessoas(apelido: str, pedido: Request) -> dict:
        """A base, NOME POR NOME: o que cada pessoa pode fazer, o que falta
        e de quem depende.

        A frase do produto é "nós dizemos, nome por nome", e o sindicato
        recebia totais e até oito nomes de exemplo por pendência. Esta é a
        quarta superfície que responde sobre uma pessoa — e sai do mesmo
        laço do panorama, para não poder dizer outra coisa.
        """
        ent = _gestor_de(apelido, pedido)
        _auditar(ent, "pessoas", quem_hash=_sessao_de(pedido).cpf_hash)
        return {
            "entidade": ent.apelido,
            "pessoas": [
                {
                    "nome": a.nome,
                    "cpf": _cpf_mascarado(a.cpf),
                    "cadastrou": a.cadastrou,
                    "pode": a.pode,
                    "depende_de": list(a.depende_de),
                    "acoes": [
                        {"id": p.acao, "estado": p.estado}
                        for p in a.participacoes
                    ],
                    "oportunidades": [
                        {
                            "trilha": o.trilha,
                            "referencia": o.referencia,
                            "rotulo": o.rotulo,
                            "veredicto": o.veredicto,
                            "falta": [{"quem": f.quem, "o_que": f.o_que}
                                      for f in o.falta],
                        }
                        for o in a.oportunidades
                    ],
                }
                for a in _base_avaliada(ent)
            ],
        }

    @app.get("/api/entidade/{apelido}/pessoas.csv")
    def exportar_pessoas(apelido: str, pedido: Request) -> Response:
        """A mesma lista, como planilha que o sindicato leva embora.

        COM O CPF INTEIRO, porque é por ele que o sindicato casa esta lista
        com os registros dele — uma exportação sem CPF não serve para o que
        se exporta. Por isso é a maior saída de dado do produto, e:

        - o registro de QUEM exportou é SÍNCRONO. `_auditar` engole falha,
          decisão tomada para a consulta de uma tela; aqui, sem registro,
          não sai arquivo — é esse registro que torna um vazamento
          investigável;
        - vem como anexo, sem cache.

        O DIALETO É O DO EXCEL EM PORTUGUÊS: `;` como separador e a marca de
        UTF-8 no começo. Com vírgula tudo cai numa coluna só; sem a marca,
        os acentos saem trocados. (Comportamento conhecido do Excel, não
        medido aqui — não há Excel nesta máquina.)

        CÉLULA QUE COMEÇA COM `=` É FÓRMULA, e o nome vem do filiado: tudo
        passa por `deposito._sem_formula`, a mesma trava do manifesto.
        """
        ent = _gestor_de(apelido, pedido)
        sessao = _sessao_de(pedido)
        if cfg.tem_banco:
            try:
                banco.registrar_leitura(cfg.banco_url, ent.apelido,
                                        quem_hash=sessao.cpf_hash,
                                        o_que="exportar")
            except Exception:  # noqa: BLE001
                log.exception("AUDITORIA DA EXPORTAÇÃO falhou ent=%s",
                              ent.apelido)
                raise _problema(
                    503,
                    "não conseguimos registrar quem pediu esta exportação, "
                    "e sem esse registro não exportamos. Tente de novo.",
                ) from None

        def faltas(a, dono: str) -> str:
            return " | ".join(sorted(
                o_que for quem, o_que in a.pendencias if quem == dono))

        buffer = io.StringIO(newline="")
        escritor = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        escritor.writerow([
            "cpf", "nome", "cadastrou_no_portal", "pode",
            # Os três donos com o nome que a casa já usa em
            # `pendencia.ROTULO_CURTO`: a mesma pendência com outro nome na
            # planilha faria o gestor achar que são coisas diferentes.
            "depende_do_filiado", "depende_do_sindicato",
            "depende_do_tribunal", "acoes_de_que_participa",
        ])
        for a in _base_avaliada(ent):
            escritor.writerow([deposito._sem_formula(str(c)) for c in (
                a.cpf,
                a.nome,
                "sim" if a.cadastrou else "não",
                " | ".join(f"{o.trilha}: {o.referencia}"
                           for o in a.oportunidades
                           if o.veredicto == motor.PODE),
                faltas(a, pendencia.VOCE),
                faltas(a, pendencia.CONFERENCIA),
                faltas(a, pendencia.TRIBUNAL),
                " | ".join(p.acao for p in a.participacoes
                           if p.estado == participacao.PARTICIPA),
            )])
        log.info("exportação ent=%s", ent.apelido)
        return Response(
            content=("\ufeff" + buffer.getvalue()).encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition":
                    f'attachment; filename="base-{ent.apelido}.csv"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------- a conferência humana

    #: `<sha256 do arquivo>.<16 do marcador do CPF>`. O sha256 sozinho não
    #: identifica: duas pessoas podem mandar o MESMO arquivo — a sentença de
    #: uma coletiva é igual para todos. E o CPF em claro não vai em URL.
    _ID_DE_DOCUMENTO = re.compile(r"^([0-9a-f]{64})\.([0-9a-f]{16})$")

    def _rotulo_do_tipo(tipo: str) -> str:
        return str((conta.DOCUMENTOS.get(tipo) or {}).get("rotulo") or tipo)

    def _id_do_documento(linha: dict) -> str:
        return f"{linha['sha256']}.{portao.marcar_cpf(linha['cpf'])[:16]}"

    def _para_a_tela(linha: dict) -> dict:
        """NOME, nunca CPF. O gestor precisa saber de quem é o documento, e
        o CPF em claro numa resposta de API é mais um lugar com ele."""
        return {
            "id": _id_do_documento(linha),
            "nome": linha["nome"] or "(sem nome na base)",
            "tipo": linha["tipo"],
            "rotulo": _rotulo_do_tipo(linha["tipo"]),
            "recebido_em": linha["recebido_em"].isoformat(timespec="seconds"),
        }

    def _documento_da_fila(ent: entidades.Entidade, doc_id: str) -> dict:
        """A linha do documento, ou 404.

        PROCURADO NA FILA DESTA ENTIDADE, e não aberto por caminho: o que o
        gestor pode abrir é exatamente o que espera a leitura dele (ou o que
        ele marcou como ilegível, para poder rever). Documento que a máquina
        leu não passa por aqui — não há motivo para o gestor baixá-lo, e o
        que não tem motivo não tem rota.
        """
        casou = _ID_DE_DOCUMENTO.match(doc_id or "")
        if not casou:
            raise _problema(404, "documento não encontrado")
        for situacao in ("", conferencia.ILEGIVEL):
            for linha in banco.fila_de_leitura(cfg.banco_url, ent.apelido,
                                               situacao):
                if _id_do_documento(linha) == doc_id:
                    return linha
        raise _problema(404, "documento não encontrado")

    def _exigir_banco_para_conferir() -> None:
        if not cfg.tem_banco:
            raise _problema(
                503,
                "este servidor está sem banco de dados, e a fila de leitura "
                "mora nele",
            )

    @app.get("/api/entidade/{apelido}/conferencia")
    def ver_fila_de_leitura(apelido: str, pedido: Request) -> dict:
        """O que espera a leitura de uma PESSOA, para o gestor da entidade.

        Scanner e foto entram no cadastro e a máquina não os lê. Quem lê é o
        sindicato, por aqui — decisão de 10/11/2026.
        """
        ent = _gestor_de(apelido, pedido)
        _exigir_banco_para_conferir()
        _auditar(ent, "conferencia", quem_hash=_sessao_de(pedido).cpf_hash)
        return {
            "pendentes": [
                _para_a_tela(l) for l in
                banco.fila_de_leitura(cfg.banco_url, ent.apelido)
            ],
            # A QUEM PEDIR DE NOVO: o que alguém abriu e não conseguiu ler.
            "ilegiveis": [
                _para_a_tela(l) for l in
                banco.fila_de_leitura(cfg.banco_url, ent.apelido,
                                      conferencia.ILEGIVEL)
            ],
            "dispositivos": list(conferencia.DISPOSITIVOS),
        }

    @app.get("/api/entidade/{apelido}/conferencia/{doc_id}/arquivo")
    def abrir_documento_da_fila(apelido: str, doc_id: str,
                                pedido: Request) -> Response:
        """O PDF, para o gestor LER. É a leitura mais sensível do produto: é
        aqui que o documento de um filiado sai do servidor.

        Por isso: só gestor da própria entidade; só documento que está na
        fila dela; registrado em `leitura` com o marcador de quem abriu e de
        quem é; e `no-store`, para o navegador do gestor não guardar cópia.
        """
        ent = _gestor_de(apelido, pedido)
        _exigir_banco_para_conferir()
        linha = _documento_da_fila(ent, doc_id)
        _auditar(ent, "ver_documento",
                 quem_hash=_sessao_de(pedido).cpf_hash,
                 alvo_hash=portao.marcar_cpf(linha["cpf"]))
        pasta = ent.entrega(cfg.raiz) / conta.so_digitos(linha["cpf"])
        for arquivo in sorted(pasta.glob("*.pdf")) if pasta.is_dir() else []:
            corpo = arquivo.read_bytes()
            if hashlib.sha256(corpo).hexdigest() == linha["sha256"]:
                return Response(
                    content=corpo,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": 'inline; filename="documento.pdf"',
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                    },
                )
        raise _problema(
            404,
            "o arquivo deste documento não está mais na entrega — a pessoa "
            "pode ter enviado outro no lugar",
        )

    @app.post("/api/entidade/{apelido}/conferencia/{doc_id}")
    def registrar_leitura_humana(
        apelido: str, doc_id: str, pedido: Request,
        # COM PADRÃO, de propósito: sem ele o FastAPI recusa o pedido sem
        # corpo com 422 ANTES de esta função rodar — e quem não tem sessão
        # recebia um erro de formato em vez de 401. Primeiro quem é, depois
        # o que mandou.
        corpo: dict = Body(default_factory=dict),
    ) -> dict:
        """O gestor registra o que LEU — ou que não deu para ler.

        O QUE ELE REGISTRA VIRA FATO, e fato alimenta o motor. Então só
        entram valores que existem (`conferencia.validar`), e a ordem é a de
        sempre: o arquivo de leituras primeiro, com fsync, e o banco depois.
        Se o banco falhar, a leitura está gravada e a projeção se refaz.
        """
        ent = _gestor_de(apelido, pedido)
        _exigir_banco_para_conferir()
        sessao = _sessao_de(pedido)
        linha = _documento_da_fila(ent, doc_id)
        resultado = str(corpo.get("resultado", ""))
        observacao = str(corpo.get("observacao", "") or "")
        fatos, problemas = conferencia.validar(
            linha["tipo"], resultado, corpo.get("fatos") or {}, observacao)
        if problemas:
            raise _problema(422, "leitura não registrada",
                            problemas=problemas)

        # COM O APAGAMENTO PARADO, E O DOCUMENTO CONFERIDO DE NOVO. O gestor
        # abriu a fila, leu o PDF e digitou — minutos. Medido em 12/11/2026:
        # se a pessoa fosse apagada a pedido nesse intervalo, a leitura era
        # gravada assim mesmo, com o CPF dela e o que a sentença dela diz,
        # em `leituras.jsonl`. O documento apagado SAI da fila; então
        # procurá-lo de novo, dentro da trava, é a conferência — e devolve
        # o mesmo 404 de um documento que nunca existiu.
        with deposito.travada(ent.pasta(cfg.raiz),
                              deposito.TRAVA_DO_APAGAMENTO):
            linha = _documento_da_fila(ent, doc_id)
            registro = conferencia.registrar(
                ent.pasta(cfg.raiz), entidade=ent.apelido, cpf=linha["cpf"],
                documento=linha["sha256"], tipo=linha["tipo"],
                resultado=resultado, fatos=fatos, observacao=observacao,
                quem=sessao.cpf_hash,
            )
            _auditar(ent, "registrar_leitura", quem_hash=sessao.cpf_hash,
                     alvo_hash=portao.marcar_cpf(linha["cpf"]))
            try:
                banco.projetar_leituras(cfg.banco_url, ent.apelido, [registro])
            except Exception:  # noqa: BLE001
                log.exception(
                    "PROJEÇÃO da leitura falhou ent=%s — a leitura está em %s; "
                    "refaça com banco.projetar_leituras",
                    ent.apelido, conferencia.ARQUIVO,
                )
                raise _problema(
                    503,
                    "a leitura foi registrada, mas ainda não aparece no painel. "
                    "Não registre de novo: avise quem opera o servidor.",
                ) from None
        log.info("leitura humana ent=%s tipo=%s resultado=%s",
                 ent.apelido, linha["tipo"], resultado)
        return {"resultado": resultado, "tipo": linha["tipo"],
                "fatos": fatos}

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
            # QUANTOS DA PLANILHA DELE FORAM APAGADOS A PEDIDO.
            #
            # CONTAGEM, e nunca lista nominal: a pessoa pediu para sair, e
            # devolver o nome dela numa tela seria exatamente o oposto. O
            # número existe para o sindicato corrigir a FONTE — enquanto o
            # CPF estiver na planilha dele, toda ingestão vai pulá-lo de
            # novo, e sem este aviso ele reenviaria para sempre sem saber.
            "apagados_a_pedido": _apagados_na_planilha(ent, pessoas),
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
            sessao = portao.abrir_sessao(token, para_enviar=True)
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
        #: Os arquivos que ABREM mas não têm texto que a máquina leia.
        aguardando: list[str] = []
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
            abre, tem_texto, _caracteres = validacao.examinar_pdf(corpo)
            if not abre:
                # Este ninguém lê — nem a máquina, nem uma pessoa. Guardá-lo
                # como "aguardando leitura" criaria uma fila que não anda,
                # com a pessoa achando que entregou.
                raise _problema(
                    422,
                    f"não conseguimos abrir o arquivo {nome}. Ele pode estar "
                    f"corrompido ou protegido por senha. Envie o arquivo "
                    f"original, sem senha.",
                )
            if not tem_texto:
                # ACEITA E MARCA. Scanner e foto são o caso comum de quem tem
                # papel físico, e recusar aqui derrubava o cadastro inteiro —
                # inclusive por um anexo opcional. A máquina não lê; uma
                # pessoa lê. Ver `validacao.examinar_pdf`.
                aguardando.append(nome)
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

        # COM O APAGAMENTO PARADO, E A SESSÃO CONFERIDA DE NOVO.
        #
        # A sessão foi conferida lá em cima, e desde então os arquivos
        # subiram — segundos, num pacote grande. Medido em 12/11/2026: um
        # apagamento a pedido que caísse nesse intervalo era desfeito aqui,
        # e no pior lugar: o DIÁRIO, que é a autoridade. Sobravam 7
        # vestígios, e `banco.reconstruir` traria a pessoa de volta para
        # sempre.
        #
        # O apagamento REVOGA a sessão. Então conferi-la de novo, dentro da
        # trava que ele segura, basta — e não depende do banco estar no ar,
        # que é o que este caminho nunca pôde exigir (o cadastro tem de
        # entrar com o banco fora). A trava vai até o fim do ESPELHO: solta
        # antes dele, o apagamento caberia entre o diário e o banco.
        with deposito.travada(ent.pasta(cfg.raiz),
                              deposito.TRAVA_DO_APAGAMENTO):
            try:
                portao.abrir_sessao(token, para_enviar=True)
            except acesso.SessaoInvalida as e:
                raise _problema(401, str(e)) from None

            anterior = deposito.ja_cadastrado(ent, cfg.raiz, limpa["cpf"])
            recibo = deposito.depositar(ent, cfg.raiz, limpa, recebidos,
                                        aguardando_leitura=tuple(aguardando))
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
                                      [recibo.registro],
                                      consentimento_novo=True)
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

    @app.post("/api/atendimento")
    def atender(pedido: Request,
                corpo: dict = Body(default_factory=dict)) -> dict:
        """As perguntas de sempre do filiado, respondidas na hora.

        NÃO ACEITA CPF, como as outras rotas dele: responde sobre quem abriu
        a sessão. E NÃO APURA NADA — pergunta às MESMAS funções que as telas
        usam, e `nucleo.atendimento` só escreve em frases. Um segundo jeito
        de apurar seria uma segunda resposta para a mesma pessoa.

        A PERGUNTA NÃO É GUARDADA NEM LOGADA. É texto livre: a pessoa pode
        escrever ali o que quiser, de si e dos outros. O log leva só o
        assunto reconhecido.

        NÃO HÁ MODELO DE LINGUAGEM AQUI, e não é falta de tempo: dado de
        filiado não vai para modelo de linguagem.
        """
        sessao = _sessao_de(pedido)
        assunto = atendimento.entender(str(corpo.get("pergunta") or "")[:500])
        dados: dict = {}
        if assunto in (atendimento.PROCESSOS, atendimento.NOVIDADES):
            dados["processos"] = meus_processos(pedido)
        if assunto in (atendimento.PROCESSOS, atendimento.DOCUMENTOS,
                       atendimento.FALTA, atendimento.DIREITOS):
            dados["acoes"] = minhas_acoes(pedido)
        if assunto in (atendimento.DOCUMENTOS, atendimento.DADOS):
            dados["cadastro"] = meu_cadastro(pedido)
        log.info("atendimento ent=%s assunto=%s", sessao.entidade, assunto)
        return {
            "assunto": assunto,
            "resposta": atendimento.responder(assunto, **dados),
            "sugestoes": list(atendimento.SUGESTOES),
        }

    # AS PÁGINAS, POR ÚLTIMO — depois de TODAS as rotas. Montado antes, o
    # portal estático ficaria na frente de `/saude` e de `/api/...`.
    if cfg.portal_estatico:
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=cfg.portal_estatico, html=True),
                  name="portal")

    return app
