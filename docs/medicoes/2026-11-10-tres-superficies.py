"""EXPERIMENTO DE AUDITORIA: a mesma pessoa, perguntada nas três superfícies.

Catálogo HOMOLOGADO numa CÓPIA (o real não é tocado), pessoa com sentença
procedente + certidão de trânsito. A pergunta: o filiado, o painel do
sindicato e o veredicto GUARDADO dizem a mesma coisa?
"""
import csv, json, os, pathlib, re, shutil, subprocess, sys, tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tests"))
URL = os.environ["PROTOCOL_DATABASE_URL"]

import testes_espelho as te                       # _pdf, linha, textos de exemplo
from nucleo import entendimentos
from servidor import banco, entidades
from servidor.app import criar_app
from servidor.config import carregar
from fastapi.testclient import TestClient

banco.criar_esquema(URL, recriar=True)

# --- catálogo homologado, em cópia, com a versão SUBIDA (como um advogado faria)
cat = pathlib.Path(tempfile.mkdtemp(prefix="aud-cat-"))
for f in sorted((REPO / "config/categorias").glob("*.toml")):
    t = f.read_text(encoding="utf-8")
    # SÓ A AÇÃO COLETIVA: homologar as teses em massa é recusado pela carga
    # ("homologado sem a tese transcrita"), e EXECUTAR só precisa da ação.
    alvo = 'Não confirmado em fonte primária.\n"""\nhomologado      = "N"'
    if alvo in t:
        t = t.replace(alvo, alvo[:-2] + 'S"')
    t = re.sub(r"^versao = (\d+)", lambda m: f"versao = {int(m.group(1))+1}", t, flags=re.M)
    (cat / f.name).write_text(t, encoding="utf-8")
entendimentos.PASTA_PADRAO = cat

raiz = pathlib.Path(tempfile.mkdtemp(prefix="aud-raiz-"))
APELIDO = "demo-auditoria"
entidades.Cadastro(raiz).criar(APELIDO, "Sindicato de Demonstração",
                               categorias=("auditor-fiscal-receita-federal",))
pasta = raiz / APELIDO; pasta.mkdir(parents=True, exist_ok=True)
A, G = te.A, te.B
for nome, cpfs in (("filiados.csv", [A, G]), ("gestores.csv", [G])):
    with open(pasta / nome, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["cpf", "email"])
        for c in cpfs: w.writerow([c, f"x{c[-3:]}@exemplo.invalid"])

cli = TestClient(criar_app(carregar({
    "PROTOCOL_MODO_ENSAIO": "1", "PROTOCOL_RAIZ": str(raiz),
    "PROTOCOL_DATABASE_URL": URL, "PROTOCOL_AGENDAR": "0",
    "PROTOCOL_EMISSOES_POR_CPF_HORA": "50", "PROTOCOL_EMISSOES_POR_ORIGEM_HORA": "500"})))

def token(cpf):
    cod = cli.post("/api/acesso/codigo", json={"entidade": APELIDO, "cpf": cpf}).json()["codigo_do_ensaio"]
    return cli.post("/api/acesso/conferir", json={"entidade": APELIDO, "cpf": cpf, "codigo": cod}).json()["token"]

CERTIDAO = ["PODER JUDICIARIO - JUSTICA FEDERAL", "CERTIDAO", "",
            "Certifico que a sentenca proferida nos autos do processo n.",
            "0010391-24.2006.4.01.3400 transitou em julgado em 22/08/2019, nada havendo",
            "a prover.", "", "Documento de exemplo, para demonstracao do sistema."]

tk = token(A)
r = cli.post("/api/cadastro",
    data={"token": tk, "linha": json.dumps(te.linha(A, ja_executou="nao", tem_acao_propria="nao"))},
    files=[("arquivos", ("contribuicao-1.pdf", te._pdf(te.CONTRIB), "application/pdf")),
           ("arquivos", ("sentenca.pdf", te._pdf(te.SENTENCA), "application/pdf")),
           ("arquivos", ("certidao_transito.pdf", te._pdf(CERTIDAO), "application/pdf"))])
print("cadastro:", r.status_code, r.text[:160] if r.status_code != 200 else r.json().get("protocolo"))

# ---------- SUPERFÍCIE 1: o que o FILIADO vê
ma = cli.get("/api/minhas-acoes", headers={"Authorization": f"Bearer {token(A)}"}).json()
print("\n[1] FILIADO  /api/minhas-acoes")
print("      chaves:", sorted(ma))
print(json.dumps(ma, ensure_ascii=False, indent=1)[:2600])

# ---------- SUPERFÍCIE 2: o que o SINDICATO vê
pan = cli.get(f"/api/entidade/{APELIDO}/panorama", headers={"Authorization": f"Bearer {token(G)}"}).json()
print("\n[2] SINDICATO  /panorama")
print(f"      pessoas={pan.get('pessoas')}  aptos={pan.get('aptos')}  leu_documentos={pan.get('leu_documentos')}")
for g in pan.get("gargalos", [])[:6]:
    print(f"      gargalo [{g['quem']}] {g['o_que'][:70]}  ({g['pessoas']})")

# ---------- SUPERFÍCIE 3: o veredicto GUARDADO (a ferramenta de verdade)
r = subprocess.run([sys.executable, str(REPO / "ferramentas/reavaliar_oportunidades.py"),
                    "--entidade", APELIDO, "--raiz", str(raiz), "--banco", URL, "--catalogos", str(cat)],
                   capture_output=True, text=True, env={**os.environ})
print("\n[3] GUARDADO  reavaliar_oportunidades.py  (saída", r.returncode, ")")
for g in banco.oportunidades_de(URL, APELIDO, A):
    print(f"      {g['trilha']:9} {g['referencia']:34} {g['veredicto']}")
print("\n--- motivos do EXECUTAR guardado:")
for g in banco.oportunidades_de(URL, APELIDO, A):
    if g["trilha"] == "executar":
        for f in g["falta"]: print("      falta:", f)
