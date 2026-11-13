#!/usr/bin/env python3
"""
A demonstração sobe com UM comando, e só com cadastro fictício.

`ferramentas/demo.py` existe para alguém ver o produto funcionando no
próprio computador. Antes dela a demonstração era um roteiro solto numa pasta
temporária, que só rodava na máquina de quem o escreveu.

O QUE ESTES TESTES FIXAM, rodando o comando de verdade:

1. Sobe, serve o portal, e os acessos que ele IMPRIME entram.
2. Toda pessoa da base é declaradamente fictícia — nome rotulado e e-mail
   num domínio que não existe. Demonstração é o lugar onde um nome plausível
   passaria por pessoa real.
3. Num banco que JÁ TEM tabela, recusa e não toca: o `--banco` é de quem
   chamou, e apagar o banco errado não tem volta.
4. Encerrado, não deixa o servidor para trás.

SEM `PROTOCOL_DATABASE_URL`, ou sem `npx`, esta suíte é PULADA em voz alta.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
URL = os.environ.get("PROTOCOL_DATABASE_URL", "").strip()
BANCO = "protocol_demo_teste"

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)
        print(f"  FALHA  {msg}")


def _url_de(banco: str) -> str:
    """A mesma conexão dos testes, em outro banco do mesmo servidor."""
    return re.sub(r"/[^/?]*(\?|$)", f"/{banco}\\1", URL, count=1)


def _banco_vazio() -> str:
    import psycopg

    with psycopg.connect(_url_de("postgres"), autocommit=True) as con:
        con.execute(f"DROP DATABASE IF EXISTS {BANCO}")
        con.execute(f"CREATE DATABASE {BANCO}")
    return _url_de(BANCO)


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pedir(url: str, corpo: dict | None = None, token: str = ""):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cab = {"Content-Type": "application/json"} if dados else {}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, data=dados, headers=cab),
                timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _no_ar(porta: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def teste_a_demo_sobe_fictícia_e_desce_limpa():
    banco = _banco_vazio()
    porta = _porta_livre()
    pasta = Path(tempfile.mkdtemp(prefix="demo-teste-"))
    proc = subprocess.Popen(
        [sys.executable, "ferramentas/demo.py", "--banco", banco,
         "--porta", str(porta), "--pasta", str(pasta)],
        cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env={k: v for k, v in os.environ.items()
             if k != "PROTOCOL_DATABASE_URL"},
    )
    saida = ""
    try:
        limite = time.time() + 240
        for linha in proc.stdout:  # type: ignore[union-attr]
            saida += linha
            if "Ctrl+C" in linha or time.time() > limite:
                break
        checa("NO AR" in saida, f"a demo não subiu:\n{saida[-1500:]}")
        if "NO AR" not in saida:
            return
        base = f"http://127.0.0.1:{porta}"
        checa(f"127.0.0.1:{porta}" in saida,
              "não disse em que endereço abrir")

        s, corpo = _pedir(base + "/")
        checa(s == 200 and b"<!doctype html" in corpo.lower(),
              f"o portal não abre: {s}")

        # OS ACESSOS IMPRESSOS ENTRAM. Acesso que está no texto e não abre é
        # a pior demonstração possível.
        cpfs = re.findall(r"\d{3}\.\d{3}\.\d{3}-\d{2}", saida)
        checa(len(cpfs) >= 4, f"esperava 4 acessos impressos, vi {cpfs}")
        m = re.search(r"entidade=([a-z0-9-]+)", saida)
        apelido = m.group(1) if m else "demo-sindicato"
        for cpf in cpfs[:4]:
            s, corpo = _pedir(base + "/api/acesso/codigo",
                              {"entidade": apelido, "cpf": cpf})
            codigo = json.loads(corpo).get("codigo_do_ensaio", "")
            s, corpo = _pedir(base + "/api/acesso/conferir",
                              {"entidade": apelido, "cpf": cpf,
                               "codigo": codigo})
            checa(s == 200 and "token" in json.loads(corpo),
                  f"o acesso impresso {cpf} não entra: {s}")

        # E OS MESMOS ACESSOS ESTÃO NA TELA: quem abre o link não vê o
        # terminal de quem subiu a demonstração.
        s, corpo = _pedir(base + f"/api/entidade/{apelido}")
        na_tela = [x["cpf"] for x in
                   json.loads(corpo).get("acessos_da_demonstracao", [])]
        checa(sorted(na_tela)
              == sorted(re.sub(r"\D", "", c) for c in cpfs[:4]),
              f"os acessos da tela não são os impressos: {na_tela}")

        # SÓ CADASTRO DECLARADAMENTE FICTÍCIO.
        rol = list(csv.DictReader(
            open(pasta / "dados" / apelido / "filiados.csv",
                 encoding="utf-8")))
        checa(len(rol) >= 30, f"a base da demo tem só {len(rol)} pessoas")
        for linha in rol:
            checa(linha["email"] == ""
                  or linha["email"].endswith("@exemplo.invalid"),
                  f"e-mail que pode existir: {linha['email']!r}")
        # O nome não fica no rol do portão: fica no banco.
        import psycopg

        with psycopg.connect(banco) as con:
            nomes = [n for (n,) in con.execute("SELECT nome FROM pessoa")]
        checa(len(nomes) >= 30, f"só {len(nomes)} pessoas no banco da demo")
        for nome in nomes:
            checa("FICTÍCIO" in nome,
                  f"nome sem rótulo de fictício: {nome!r}")

        # BANCO QUE JÁ TEM TABELA: recusa, e não toca. (Agora ele tem.)
        r = subprocess.run(
            [sys.executable, "ferramentas/demo.py", "--banco", banco,
             "--porta", str(_porta_livre())],
            cwd=RAIZ, capture_output=True, text=True, timeout=120)
        checa(r.returncode != 0 and "vazio" in (r.stdout + r.stderr),
              f"aceitou um banco que não está vazio: {r.returncode} "
              f"{(r.stdout + r.stderr)[-300:]}")
        s, _ = _pedir(base + "/saude")
        checa(s == 200, "a segunda chamada derrubou ou estragou a primeira")
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            checa(False, "a demo não encerrou com Ctrl+C")
        time.sleep(0.5)
        checa(not _no_ar(porta),
              "a demo encerrou e o servidor continuou no ar")
        shutil.rmtree(pasta, ignore_errors=True)


def main() -> int:
    print("=" * 70)
    print("DEMO — um comando, só cadastro fictício")
    print("=" * 70)
    if not URL:
        print("\nPULADO: sem PROTOCOL_DATABASE_URL.")
        return 0
    if not shutil.which("npx"):
        print("\nPULADO: sem npx (instale o Node.js).")
        return 0
    try:
        teste_a_demo_sobe_fictícia_e_desce_limpa()
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        falhas.append(f"levantou {type(exc).__name__}: {exc}")
    print("-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s)")
        return 1
    print("1 grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
