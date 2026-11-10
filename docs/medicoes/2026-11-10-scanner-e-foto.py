import csv, json, os, pathlib, sys, tempfile
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tests"))
import testes_espelho as te, testes_documentos as td
from fastapi.testclient import TestClient
cli, ent, raiz = te._servidor()
def tk(c):
    cod = cli.post("/api/acesso/codigo", json={"entidade": "demo-a", "cpf": c}).json()["codigo_do_ensaio"]
    return cli.post("/api/acesso/conferir", json={"entidade": "demo-a", "cpf": c, "codigo": cod}).json()["token"]
def envia(rotulo, arquivos):
    r = cli.post("/api/cadastro", data={"token": tk(te.A), "linha": json.dumps(te.linha(te.A))}, files=arquivos)
    corpo = r.json(); msg = corpo.get("protocolo") or json.dumps(corpo, ensure_ascii=False)[:230]
    print(f"  {rotulo:44} -> {r.status_code}  {msg}")
contrib = ("arquivos", ("contribuicao-1.pdf", te._pdf(te.CONTRIB), "application/pdf"))
envia("contribuição ESCANEADA (PDF só imagem)", [("arquivos", ("contribuicao-1.pdf", td.pdf_so_imagem(), "application/pdf"))])
envia("contribuição ok + SENTENÇA escaneada", [contrib, ("arquivos", ("sentenca.pdf", td.pdf_so_imagem(), "application/pdf"))])
envia("contribuição em FOTO (jpg)", [("arquivos", ("contribuicao-1.jpg", b"\xff\xd8\xff\xe0" + b"0"*2000, "image/jpeg"))])
