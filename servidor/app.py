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
"""

from __future__ import annotations

import dataclasses
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

from . import (
    acervo,
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
PREFIXO_DEMO = "demo-"


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


def _origem(pedido: Request) -> str:
    """Quem está pedindo, para a contagem por hora.

    Atrás de proxy o IP do socket é o do proxy, e aí a contagem por origem
    vale para o mundo inteiro junto. Por isso olhamos o cabeçalho que o proxy
    põe — e só o primeiro valor, que é o cliente; os seguintes são os proxies.
    """
    encaminhado = pedido.headers.get("x-forwarded-for", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return pedido.client.host if pedido.client else "desconhecido"


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
        if cfg.modo_ensaio and not ent.apelido.startswith(PREFIXO_DEMO):
            log.error(
                "ENSAIO recusou a entidade %s: em ensaio o código de acesso "
                "volta na resposta HTTP, e isso não pode valer para gente "
                "real", ent.apelido,
            )
            raise _problema(
                403,
                f"este servidor está em MODO ENSAIO, e em ensaio o código de "
                f"acesso volta na própria resposta — o que não pode valer "
                f"para pessoas de verdade. Só entidades de demonstração "
                f"(apelido começando com {PREFIXO_DEMO!r}) são atendidas. "
                f"Para atender {ent.apelido!r}, suba o servidor sem "
                f"PROTOCOL_MODO_ENSAIO e configure o envio de e-mail",
            )
        # A TRAVA DE REGIÃO, depois da de ensaio porque em ensaio a
        # região é irrelevante: aquele servidor devolve o código na
        # resposta HTTP e recusa entidade real de qualquer jeito, e a
        # mensagem dele explica a situação de verdade.
        #
        # É de código pelo mesmo motivo que a outra: procedimento se
        # esquece. "Migrar para São Paulo antes do
        # primeiro sindicato" é uma promessa; isto é uma impossibilidade.
        #
        # A demonstração passa em qualquer região porque lá não há dado
        # pessoal — fechar a demonstração não protegeria ninguém e tiraria do
        # ar a única coisa que já está pronta.
        if (
            not ent.apelido.startswith(PREFIXO_DEMO)
            and not banco.regiao_e_brasileira(cfg.regiao)
        ):
            log.error(
                "REGIAO recusou a entidade %s: PROTOCOL_REGIAO=%r nao e "
                "brasileira, e entidade real trata dado pessoal",
                ent.apelido, cfg.regiao,
            )
            raise _problema(
                503,
                f"este servidor roda na região "
                f"{cfg.regiao or '(não declarada)'}, e entidade real só é "
                f"atendida em região brasileira. Dado de filiado em nuvem "
                f"estrangeira é transferência internacional, que desde "
                f"23/08/2025 exige as cláusulas-padrão da ANPD (Res. CD/ANPD "
                f"19/2024). Declare PROTOCOL_REGIAO como uma região "
                f"brasileira ({', '.join(sorted(banco.REGIOES_BRASILEIRAS))}), "
                f"ou atenda só entidades de demonstração",
            )

        return ent

    # ------------------------------------------------------------- diagnóstico

    @app.get("/saude")
    def saude() -> dict:
        return {
            "ok": True,
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
            codigo = portao.emitir(ent.apelido, cpf, _origem(pedido))
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
            # Sem o texto da exceção na resposta: ele costuma trazer o
            # endereço de destino.
            log.exception("falha ao enviar código ent=%s cpf=%s", ent.apelido, marca)
            raise _problema(
                502, "não conseguimos enviar o código agora; tente de novo"
            ) from None

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
        return {
            "entidade": ent.apelido,
            "nome": ent.nome,
            "processos": processos,
            # Dito na resposta, não só na tela: quem consumir esta API por
            # fora tem de receber o limite junto com o dado.
            "limite": (
                "Movimentação registrada pelo tribunal, com cerca de um dia "
                "de atraso. NÃO é intimação e não serve para contar prazo."
            ),
        }

    # -------------------------------------------------------- painel do gestor

    @app.get("/api/entidade/{apelido}/completude")
    def ver_completude(apelido: str, pedido: Request) -> dict:
        """O retrato da base, para o gestor da PRÓPRIA entidade.

        Duas conferências, nesta ordem, e a ordem importa: primeiro que a
        sessão é da entidade pedida, depois que quem abriu é gestor dela. A
        ordem inversa diria a um gestor de outra entidade se o CPF dele
        consta como gestor aqui.
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
