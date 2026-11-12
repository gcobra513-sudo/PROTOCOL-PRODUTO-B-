"""T28, o resto: um apagamento a pedido NO MEIO de uma tarefa agendada.

As três tarefas que o agendador roda sozinho — coletar, avisar, reavaliar —
leem a base no começo e gravam por pessoa depois. A pergunta é a mesma da
outra medição: o que sobra de quem foi apagado nesse intervalo? E, para
`avisar`, uma pior: SAI E-MAIL para quem acabou de pedir para sair?

SEQUÊNCIA FORÇADA: a ferramenta roda neste processo (`main()` da própria
ferramenta, com os argumentos de sempre), e a função que ela chama logo
depois de ler a base é embrulhada para que o apagamento rode antes, inteiro
e pela rota.

    PROTOCOL_DATABASE_URL='postgresql://...' \\
        python3 docs/medicoes/2026-11-12-apagamento-e-as-tarefas-agendadas.py

Sai com 1 se alguma coisa da pessoa sobrou, ou se saiu e-mail para ela.

MEDIDO em 12/11/2026, ANTES da correção: ver o fim deste arquivo.
"""
import contextlib, importlib, io, json, logging, os, pathlib, sys, time
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tests"))
logging.disable(logging.CRITICAL)
import testes_espelho as te
from servidor import acompanhamento, banco

te.preparar()
X = te.C_PLAN                         # CPF sintético, declarado como exemplo
NOME = "SAI NO MEIO (CADASTRO DE EXEMPLO)"
EMAIL = "meio@exemplo.invalid"
PROCESSO = "00103912420064013400"     # o número de exemplo das suítes
SELO = int(time.time())


def sobras(raiz, entidade: str) -> list[str]:
    """Tudo o que ainda diz o CPF, o e-mail ou o nome dela."""
    achou = []
    marcas = {"CPF": X.encode(), "e-mail": EMAIL.encode(),
              "nome": NOME.encode()}
    for caminho in sorted(raiz.rglob("*")):
        if X in caminho.name:
            achou.append(f"caminho {caminho.relative_to(raiz)}")
        elif caminho.is_file():
            corpo = caminho.read_bytes()
            ditas = [r for r, m in marcas.items() if m in corpo]
            if ditas:
                achou.append(f"{' e '.join(ditas)} em "
                             f"{caminho.relative_to(raiz)}")
    with banco.sessao(te.URL, entidade) as cur:
        for tabela in banco._TABELAS_DO_APAGAMENTO:
            cur.execute(f"SELECT count(*) FROM {tabela} WHERE cpf = %s", (X,))
            n = cur.fetchone()[0]
            if n:
                achou.append(f"banco: {n} linha(s) em {tabela}")
    return achou


def cenario(nome: str):
    """Uma entidade só deste caso, com a pessoa na base, cadastrada, com um
    processo e com o aviso pedido."""
    entidade = f"demo-agenda-{nome}-{SELO}"
    cliente, ent, raiz = te._servidor(entidade)
    planilha = ("CPF;Nome Completo;E-mail;Cargo;Processo\r\n"
                f"{X};{NOME};{EMAIL};Auditor Fiscal da Receita Federal;"
                f"{PROCESSO}\r\n").encode("latin-1")
    te._confirmar_planilha(cliente, entidade, planilha)
    r = cliente.post(
        "/api/cadastro",
        data={"token": te._token(cliente, X, entidade),
              "linha": json.dumps(te.linha(X, nome_completo=NOME, email=EMAIL,
                                           quer_aviso="sim"))},
        files=[("arquivos", ("contribuicao-1.pdf", te._pdf(te.CONTRIB),
                             "application/pdf"))])
    assert r.status_code == 200, r.text
    return entidade, cliente, ent, raiz


def rodar(ferramenta: str, argumentos: list[str]) -> tuple[int, str]:
    modulo = importlib.import_module(f"ferramentas.{ferramenta}")
    antigo = sys.argv
    sys.argv = [ferramenta, *argumentos]
    saida = io.StringIO()
    try:
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            codigo = modulo.main()
    finally:
        sys.argv = antigo
    return codigo, saida.getvalue()


def medir(nome: str, ferramenta: str, modulo, funcao: str, extra=(),
          preparar=None, substituta=None):
    entidade, cliente, ent, raiz = cenario(nome)
    if preparar:
        preparar(entidade, ent, raiz)
    gestor = te._token(cliente, te.B, entidade)
    original = getattr(modulo, funcao)
    apagou = []

    def com_apagamento_no_meio(*a, **k):
        if not apagou:
            r = te._apagar(cliente, entidade,
                           {"cpf": X, "motivo": "pedido do titular",
                            "pedido_por": "g"}, gestor)
            apagou.append((r.status_code, r.json().get("vestigios")))
        return (substituta or original)(*a, **k)

    setattr(modulo, funcao, com_apagamento_no_meio)
    try:
        codigo, saida = rodar(ferramenta, [
            "--entidade", entidade, "--raiz", str(raiz),
            "--banco", te.URL, *extra])
    finally:
        setattr(modulo, funcao, original)
    ficou = sobras(raiz, entidade)
    print(f"\n== {nome}")
    print(f"   o apagamento do meio respondeu: {apagou}")
    print(f"   a ferramenta saiu com {codigo}")
    print(f"   sobrou da pessoa: {len(ficou)}")
    for linha in ficou:
        print(f"     - {linha}")
    return ficou, raiz, entidade, saida


# --- avisar: o processo já é conhecido, e há um movimento novo -------------
def _prep_avisar(entidade, ent, raiz):
    from nucleo import aviso as mod

    banco.guardar_movimentos(te.URL, entidade, [mod.Movimento(
        numero=PROCESSO, grau="G1", data="2026-10-01", nome="Distribuição")])
    (ent.pasta(raiz) / "movimentos.jsonl").write_text(json.dumps({
        "coletado_em": "2026-11-11T00:00:00+00:00", "consultados": 1,
        "falhas": [], "movimentos": [
            {"numero": PROCESSO, "grau": "G1", "data": "2026-11-10",
             "nome": "Juntada de petição"}]}) + "\n", encoding="utf-8")


total = 0
ficou, raiz, entidade, saida = medir(
    "avisar", "avisar_movimentacao", banco, "chaves_ja_avisadas",
    preparar=_prep_avisar)
log = raiz / "mensagens_enviadas.log"
emails = (log.read_text(encoding="utf-8").count(f"\t{EMAIL}\t")
          if log.is_file() else 0)
print(f"   E-MAILS ENVIADOS A ELA DEPOIS DO APAGAMENTO: {emails}")
total += len(ficou) + emails

# --- reavaliar -------------------------------------------------------------
ficou, *_ = medir("reavaliar", "reavaliar_oportunidades", banco,
                  "fatos_lidos_da_entidade")
total += len(ficou)

# --- coletar: a consulta ao tribunal é substituída por uma resposta fixa ---
def _tribunal_de_mentira(numeros, *a, **k):
    numeros = list(numeros)
    return ([acompanhamento.Movimento(numero=n, grau="G1", data="2026-11-11",
                                      nome="Conclusos para decisão")
             for n in numeros], [])


ficou, raiz, entidade, saida = medir(
    "coletar", "coletar_movimentacao", acompanhamento, "coletar",
    substituta=_tribunal_de_mentira)
diario = raiz / entidade / "movimentos.jsonl"
gravou = diario.is_file() and PROCESSO in diario.read_text(encoding="utf-8")
print(f"   o processo dela foi GRAVADO depois do apagamento: "
      f"{'sim' if gravou else 'não'}")
total += len(ficou)

# --- coletar, SEM CORRIDA: apagada antes; a coleta roda dois dias depois ----
entidade, cliente, ent, raiz = cenario("controle")
r = te._apagar(cliente, entidade, {"cpf": X, "motivo": "pedido do titular",
                                   "pedido_por": "g"},
               te._token(cliente, te.B, entidade))
consultados: list[str] = []


def _tribunal_que_anota(numeros, *a, **k):
    numeros = list(numeros)
    consultados.extend(numeros)
    return _tribunal_de_mentira(numeros)


verdadeiro = acompanhamento.coletar
acompanhamento.coletar = _tribunal_que_anota
try:
    for _dia in (1, 2):
        rodar("coletar_movimentacao", ["--entidade", entidade, "--raiz",
                                       str(raiz), "--banco", te.URL])
finally:
    acompanhamento.coletar = verdadeiro
print("\n== coletar, sem corrida (apagada ANTES; duas coletas depois)")
print(f"   o apagamento respondeu: {(r.status_code, r.json().get('vestigios'))}")
print(f"   consultas ao tribunal pelo processo dela: "
      f"{consultados.count(PROCESSO)}")
total += consultados.count(PROCESSO)

# --- o que FICA do processo dela, por decisão registrada -------------------
# Não entra no total: `processo` e `movimento` são sobre o processo, e o
# apagamento os mantém de propósito (`banco._TABELAS_DO_APAGAMENTO`). Fica
# medido aqui porque é a pergunta que sobra para o jurídico: numa ação
# PRÓPRIA, o número identifica a pessoa.
with banco.sessao(te.URL, entidade) as cur:
    guardado = {}
    for tabela in ("processo", "movimento", "vinculo"):
        cur.execute(f"SELECT count(*) FROM {tabela} WHERE numero = %s",
                    (PROCESSO,))
        guardado[tabela] = cur.fetchone()[0]
print(f"   o NÚMERO do processo dela continua guardado em: {guardado}")

print(f"\nTOTAL de sobras, e-mails e consultas indevidas: {total}")
raise SystemExit(1 if total else 0)


# MEDIDO em 12/11/2026, ANTES da correção:
#
#   avisar      1 E-MAIL enviado a quem tinha acabado de pedir para sair;
#               e-mail e nome em mensagens_enviadas.log; 1 `aviso_enviado`
#   reavaliar   2 linhas em `oportunidade`
#   coletar     nada do CPF, do nome ou do e-mail dela — mas o processo dela
#               consultado e gravado depois do apagamento
#   coletar,    SEM CORRIDA: o processo dela consultado no tribunal nas duas
#   sem corrida coletas seguintes (2 de 2). A lista saía da tabela
#               `processo`, que o apagamento não limpa.
#
# DEPOIS: 0 em tudo. `avisar` e `reavaliar` conferem a pessoa de novo, uma a
# uma, com o apagamento parado; `coletar` relê a lista na hora de gravar; e a
# lista do que acompanhar passou a sair de `vinculo`.
