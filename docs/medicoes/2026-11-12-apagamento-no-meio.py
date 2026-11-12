"""T28, medido: um apagamento a pedido que chega NO MEIO de uma gravação.

Quatro caminhos gravam dado de pessoa a pedido de alguém. Os quatro conferem alguma coisa ANTES
(a sessão, a base, os tombstones) e gravam DEPOIS. A pergunta é o que sobra
da pessoa quando o apagamento a pedido cai nesse intervalo.

A sequência é FORÇADA, não disputada: a função que grava é embrulhada para
que o apagamento rode, inteiro e pela rota, imediatamente antes dela. É o
pior intercalamento possível, tornado determinístico.

    PROTOCOL_DATABASE_URL='postgresql://...' \\
        python3 docs/medicoes/2026-11-12-apagamento-no-meio.py

Sai com 1 se alguma coisa da pessoa sobrou em algum caminho.

MEDIDO em 12/11/2026, ANTES da correção (com o gancho do cadastro em
`deposito.depositar`):

    planilha     0 sobras   (corrigida em 10/11)
    documentos   3 sobras   entrega/<cpf>, 2 `achado`, 1 `documento`
    cadastro     7 sobras   entrega/<cpf>, manifesto.csv, recebidos.jsonl,
                            3 `achado`, 2 `documento`, 17 `pessoa_afirmacao`,
                            1 `pessoa`

    leitura      1 sobra    leituras.jsonl — o CPF e o que a sentença diz

DEPOIS da correção: 0 nos quatro; o cadastro responde 401 e a leitura, 404.
"""
import json, logging, os, pathlib, sys, time
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tests"))
logging.disable(logging.CRITICAL)
import testes_espelho as te
from servidor import banco, conferencia, ingestao, validacao

te.preparar()
X = te.C_PLAN            # CPF sintético, declarado como exemplo
SELO = int(time.time())


def sobras(ent, raiz, entidade: str, cpf: str) -> list[str]:
    """Tudo o que ainda diz este CPF: caminho, conteúdo de arquivo, banco."""
    achou = []
    for caminho in sorted(raiz.rglob("*")):
        if cpf in caminho.name:
            achou.append(f"caminho {caminho.relative_to(raiz)}")
        elif caminho.is_file() and cpf.encode() in caminho.read_bytes():
            achou.append(f"conteúdo de {caminho.relative_to(raiz)}")
    with banco.sessao(te.URL, entidade) as cur:
        for tabela in banco._TABELAS_DO_APAGAMENTO:
            cur.execute(f"SELECT count(*) FROM {tabela} WHERE cpf = %s", (cpf,))
            n = cur.fetchone()[0]
            if n:
                achou.append(f"banco: {n} linha(s) em {tabela}")
    return achou


def medir(nome: str, modulo, funcao: str, preparar, gravar) -> list[str]:
    entidade = f"demo-meio-{nome}-{SELO}"
    cliente, ent, raiz = te._servidor(entidade)
    gestor = te._token(cliente, te.B, entidade)
    contexto = preparar(cliente, entidade, raiz)
    original = getattr(modulo, funcao)
    apagou = []

    def com_apagamento_no_meio(*a, **k):
        # Uma vez só, e ANTES de quem grava tomar a trava do apagamento
        # (depois da correção, encaixado mais tarde ele esperaria para
        # sempre por quem o chamou — que é a correção funcionando).
        if not apagou:
            r = te._apagar(cliente, entidade,
                           {"cpf": X, "motivo": "pedido do titular",
                            "pedido_por": "g"}, gestor)
            apagou.append((r.status_code, r.json().get("vestigios")))
        return original(*a, **k)

    setattr(modulo, funcao, com_apagamento_no_meio)
    try:
        r = gravar(cliente, entidade, contexto)
    finally:
        setattr(modulo, funcao, original)
    ficou = sobras(ent, raiz, entidade, X)
    print(f"\n== {nome}")
    print(f"   o apagamento do meio respondeu: {apagou}")
    print(f"   a gravação respondeu: {r.status_code}")
    print(f"   sobrou da pessoa: {len(ficou)}")
    for linha in ficou:
        print(f"     - {linha}")
    return ficou


# --- 1. a planilha (corrigida em 10/11; fica aqui como controle) ----------
def _prep_planilha(cliente, entidade, raiz):
    corpo = te._planilha([(X, "SAI NO MEIO (CADASTRO DE EXEMPLO)",
                           "meio@exemplo.invalid")])
    return corpo, te._enviar_planilha(cliente, entidade, corpo).json()["sha256"]


def _grava_planilha(cliente, entidade, ctx):
    return te._enviar_planilha(cliente, entidade, ctx[0], confirmar=ctx[1])


# --- 2. os documentos do sindicato ---------------------------------------
def _prep_documentos(cliente, entidade, raiz):
    te._confirmar_planilha(cliente, entidade, te._planilha(
        [(X, "SAI NO MEIO (CADASTRO DE EXEMPLO)", "meio@exemplo.invalid")]))
    arquivos = {f"{X}-sentenca.pdf": te._pdf(te.SENTENCA)}
    return arquivos, te._enviar_documentos(cliente, entidade,
                                           arquivos).json()["sha256"]


def _grava_documentos(cliente, entidade, ctx):
    return te._enviar_documentos(cliente, entidade, ctx[0], confirmar=ctx[1])


# --- 3. o cadastro do próprio filiado ------------------------------------
def _prep_cadastro(cliente, entidade, raiz):
    te._confirmar_planilha(cliente, entidade, te._planilha(
        [(X, "SAI NO MEIO (CADASTRO DE EXEMPLO)", "meio@exemplo.invalid")]))
    return te._token(cliente, X, entidade)


def _grava_cadastro(cliente, entidade, token):
    return cliente.post(
        "/api/cadastro",
        data={"token": token, "linha": json.dumps(te.linha(X))},
        files=[("arquivos", ("contribuicao-1.pdf", te._pdf(te.CONTRIB),
                             "application/pdf")),
               ("arquivos", ("sentenca.pdf", te._pdf(te.SENTENCA),
                             "application/pdf"))],
    )


# --- 4. a leitura que o gestor registra pelo painel -----------------------
def _prep_leitura(cliente, entidade, raiz):
    te._confirmar_planilha(cliente, entidade, te._planilha(
        [(X, "SAI NO MEIO (CADASTRO DE EXEMPLO)", "meio@exemplo.invalid")]))
    r = te._enviar(cliente, X, entidade, {
        "contribuicao-1.pdf": te._pdf(te.CONTRIB),
        "sentenca.pdf": te._so_imagem()})
    assert r.status_code == 200, r.text
    fila = te._fila(cliente, entidade)
    return next(d["id"] for d in fila["pendentes"] if d["tipo"] == "sentenca")


def _grava_leitura(cliente, entidade, doc_id):
    return te._registrar(cliente, entidade, doc_id, {
        "resultado": "lido", "fatos": {"dispositivo": "procedente"}})


total = 0
total += len(medir("planilha", ingestao, "gravar_planilha",
                   _prep_planilha, _grava_planilha))
total += len(medir("documentos", ingestao, "gravar_documentos",
                   _prep_documentos, _grava_documentos))
# O gancho do cadastro é a leitura do primeiro arquivo: o meio do envio,
# depois de a sessão ter sido conferida e antes de qualquer gravação.
total += len(medir("cadastro", validacao, "examinar_pdf",
                   _prep_cadastro, _grava_cadastro))
total += len(medir("leitura", conferencia, "validar",
                   _prep_leitura, _grava_leitura))
print(f"\nTOTAL de sobras: {total}")
raise SystemExit(1 if total else 0)
