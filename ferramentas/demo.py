#!/usr/bin/env python3
"""
A demonstração do portal, no seu computador, com um comando.

    python3 ferramentas/demo.py        (no Windows: python ferramentas/demo.py)

Sobe o servidor e o portal num endereço só (http://127.0.0.1:8080), com um
sindicato de demonstração já preenchido, e imprime com que CPF entrar. Fica
no ar até você apertar Ctrl+C; aí desliga tudo e apaga o que criou.

TUDO É FICTÍCIO, e declaradamente: os nomes trazem "(FICTÍCIO)" escrito, os
CPFs são montados a partir de um contador, os e-mails ficam num domínio que
não existe, e nenhuma mensagem sai — o servidor roda em modo ensaio, em que
o código de acesso aparece na tela. NÃO ponha dado de gente de verdade aqui.

O BANCO. Sem `--banco`, a demonstração cria um PostgreSQL só dela, numa
pasta temporária, e o apaga no fim — basta o PostgreSQL estar instalado.
Com `--banco URL`, usa o banco que você indicar, que tem de estar VAZIO: a
demonstração não apaga banco de ninguém, nem para se ajeitar.

O que precisa estar instalado: Python 3.11+, Node.js 18+ e PostgreSQL 14+, e

    pip install -r servidor/requirements.txt httpx reportlab
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

APELIDO = "demo-sindicato"      # o prefixo `demo-` é o que o modo ensaio atende
NOME = "Sindicato de Demonstração"
DOMINIO = "exemplo.invalid"     # `.invalid` não existe, por norma (RFC 2606)
PROCESSO = "0010391-24.2006.4.01.3400"
GESTOR = 9001                   # índice do CPF sintético do gestor


class NaoDa(Exception):
    """Falta algo na máquina. A mensagem é para quem chamou ler e resolver."""


# ---------------------------------------------------------------- o que falta


def conferir_a_maquina() -> None:
    faltam = [m for m in ("fastapi", "uvicorn", "psycopg", "multipart",
                          "pypdf", "openpyxl", "httpx", "reportlab")
              if importlib.util.find_spec(m) is None]
    if faltam:
        raise NaoDa(
            "faltam pacotes do Python: " + ", ".join(faltam) + ".\n"
            "  pip install -r servidor/requirements.txt httpx reportlab")
    for programa in ("node", "npx", "npm"):
        if not shutil.which(programa):
            raise NaoDa(f"`{programa}` não está instalado. Instale o Node.js "
                        "(versão 18 ou mais nova): https://nodejs.org")


def porta_livre(host: str, porta: int) -> None:
    with socket.socket() as s:
        s.settimeout(1)
        if s.connect_ex((host if host != "0.0.0.0" else "127.0.0.1",
                         porta)) == 0:
            raise NaoDa(f"a porta {porta} já está em uso. Feche o que está "
                        "nela ou escolha outra com --porta.")


# -------------------------------------------------------------------- o banco


def _programa_do_postgres(nome: str) -> str | None:
    achado = shutil.which(nome)
    if achado:
        return achado
    # O instalador do PostgreSQL costuma NÃO pôr `initdb` no caminho.
    for padrao in ("/usr/lib/postgresql/*/bin", "/opt/homebrew/opt/postgresql*/bin",
                   "/usr/local/opt/postgresql*/bin", "/Library/PostgreSQL/*/bin",
                   "/Applications/Postgres.app/Contents/Versions/*/bin",
                   "C:/Program Files/PostgreSQL/*/bin"):
        for pasta in sorted(glob.glob(padrao), reverse=True):
            for sufixo in ("", ".exe"):
                caminho = pathlib.Path(pasta) / (nome + sufixo)
                if caminho.exists():
                    return str(caminho)
    return None


class BancoProprio:
    """Um PostgreSQL só da demonstração, numa pasta que some no fim.

    SÓ EM 127.0.0.1, numa porta livre, e sem senha: quem alcança é só
    programa desta máquina, pelo tempo da demonstração, e o que há dentro é
    cadastro fictício. Não serve de modelo para banco nenhum de verdade.
    """

    def __init__(self, pasta: pathlib.Path) -> None:
        self.dados = pasta / "postgres"
        self.pg_ctl = _programa_do_postgres("pg_ctl")
        initdb = _programa_do_postgres("initdb")
        if not initdb or not self.pg_ctl:
            raise NaoDa(
                "não achei o PostgreSQL nesta máquina (procurei `initdb`).\n"
                "  Instale o PostgreSQL (https://www.postgresql.org/download/)"
                " ou indique um banco VAZIO com --banco URL.")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            raise NaoDa(
                "o PostgreSQL se recusa a rodar como administrador (root).\n"
                "  Rode como usuário comum, ou indique um banco VAZIO com "
                "--banco URL.")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.porta = s.getsockname()[1]
        r = subprocess.run(
            [initdb, "-D", str(self.dados), "-U", "postgres", "-A", "trust",
             "-E", "UTF8", "--locale=C"], capture_output=True, text=True)
        if r.returncode != 0:
            raise NaoDa("o PostgreSQL não conseguiu criar o banco da "
                        f"demonstração:\n{r.stdout}\n{r.stderr}")
        opcoes = f"-p {self.porta} -c listen_addresses=127.0.0.1"
        if os.name != "nt":
            # Sem soquete em arquivo: só a porta em 127.0.0.1. NO WINDOWS
            # NÃO: lá o padrão já é nenhum, e as aspas simples não são aspas
            # — o servidor recebia `''` como nome de pasta e não subia
            # (visto na primeira vez que a demonstração rodou em Windows).
            opcoes += " -c unix_socket_directories=''"
        r = subprocess.run(
            [self.pg_ctl, "-D", str(self.dados), "-w", "-o", opcoes,
             "-l", str(pasta / "postgres.log"), "start"],
            capture_output=True, text=True)
        if r.returncode != 0:
            # O REGISTRO VAI NA MENSAGEM: a pasta é temporária e some logo
            # em seguida, então "examine o arquivo de log" mandaria a
            # pessoa atrás de um arquivo que já não existe.
            try:
                registro = (pasta / "postgres.log").read_text(
                    encoding="utf-8", errors="replace")[-1500:]
            except OSError:
                registro = "(sem registro)"
            raise NaoDa("o PostgreSQL da demonstração não subiu:\n"
                        f"{r.stdout}\n{r.stderr}\n"
                        f"--- o que o PostgreSQL registrou ---\n{registro}")
        self.url = f"postgresql://postgres@127.0.0.1:{self.porta}/postgres"

    def parar(self) -> None:
        subprocess.run([self.pg_ctl, "-D", str(self.dados), "-m", "fast",
                        "-w", "stop"], capture_output=True, text=True)


def exigir_banco_vazio(url: str) -> None:
    """O banco de `--banco` é de quem chamou. Com QUALQUER tabela nele, para.

    Não há opção de "limpar antes": o jeito de errar aqui é apontar para o
    banco errado, e apagar o banco errado não tem volta."""
    import psycopg

    try:
        with psycopg.connect(url, connect_timeout=10) as con:
            n = con.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN "
                "('pg_catalog', 'information_schema')").fetchone()[0]
    except psycopg.Error as exc:
        raise NaoDa(f"não consegui abrir o banco de --banco: "
                    f"{type(exc).__name__}") from None
    if n:
        raise NaoDa(
            f"o banco de --banco não está vazio ({n} tabela(s)). A "
            "demonstração só usa banco vazio e não apaga nada: crie um "
            "banco novo para ela, ou rode sem --banco.")


# ------------------------------------------------------------------- o portal


def compilar_portal(destino: pathlib.Path) -> None:
    portal = REPO / "portal"
    if not (portal / "node_modules").is_dir():
        print("  instalando as dependências do portal (só na primeira vez; "
              "leva um ou dois minutos)...", flush=True)
        r = subprocess.run([shutil.which("npm") or "npm", "ci"], cwd=portal,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise NaoDa("`npm ci` falhou na pasta portal/:\n"
                        + (r.stderr or r.stdout)[-1500:])
    # "/" como endereço da API: portal e API saem do MESMO endereço, e por
    # isso a demonstração é uma porta só para abrir.
    # O CAMINHO INTEIRO do `npx`, e não só o nome: no Windows ele é
    # `npx.cmd`, e chamar pelo nome puro não o encontra.
    r = subprocess.run(
        [shutil.which("npx") or "npx", "vite", "build", "--outDir",
         str(destino), "--emptyOutDir"],
        cwd=portal, env={**os.environ, "VITE_API": "/"},
        capture_output=True, text=True)
    if r.returncode != 0:
        raise NaoDa("a compilação do portal falhou:\n"
                    + (r.stdout + r.stderr)[-1500:])


# ------------------------------------------------------------------ a semente


def _suite(url: str):
    """Os documentos fictícios e o CPF sintético são os da suíte: uma fonte
    só, para a demonstração não ganhar um PDF "de exemplo" que os testes
    nunca viram. A suíte lê o endereço do banco ao ser importada, e por isso
    ele vai para o ambiente antes."""
    os.environ["PROTOCOL_DATABASE_URL"] = url
    sys.path.insert(0, str(REPO / "tests"))
    import testes_espelho

    return testes_espelho


def semear(api: str, url: str, raiz: pathlib.Path) -> list[tuple[str, str]]:
    """Enche o sindicato de demonstração PELA PORTA DA FRENTE: o gestor
    manda a planilha, os filiados mandam documento — as mesmas rotas de
    quem usa. Demonstração semeada por dentro mostraria um estado a que o
    produto talvez nem consiga chegar."""
    import httpx

    te = _suite(url)

    from nucleo import aviso
    from servidor import agenda, banco

    gestor = te._cpf_sintetico(GESTOR)
    pessoas = [(te._cpf_sintetico(9100 + i),
                f"FILIADO DE EXEMPLO {i + 1:02d} (FICTÍCIO)",
                f"filiado{i + 1:02d}@{DOMINIO}") for i in range(42)]
    c = httpx.Client(base_url=api, timeout=120, trust_env=False)

    def token(cpf: str) -> str:
        codigo = c.post("/api/acesso/codigo", json={
            "entidade": APELIDO, "cpf": cpf}).json()["codigo_do_ensaio"]
        return c.post("/api/acesso/conferir", json={
            "entidade": APELIDO, "cpf": cpf, "codigo": codigo}).json()["token"]

    # A PLANILHA TEM DEFEITO DE PROPÓSITO — cinco sem e-mail, dois com CPF
    # que não fecha —, porque é isso que a base de um sindicato tem, e é o
    # que a tela do gestor existe para mostrar.
    linhas = ["CPF;Nome Completo;E-mail;Cargo;Filiado desde;Processo"]
    for i, (cpf, nome, email) in enumerate(pessoas):
        if i in (5, 17, 23, 31, 38):
            email = ""
        if i in (11, 29):
            cpf = cpf[:-1] + str((int(cpf[-1]) + 1) % 10)
        processo = PROCESSO if i in (0, 4, 21) else ""
        linhas.append(f"{cpf};{nome};{email};Auditor Fiscal da Receita "
                      f"Federal;2004-03;{processo}")
    planilha = ("\r\n".join(linhas) + "\r\n").encode("latin-1")
    confirmar = ""
    for _ in range(2):          # a primeira mostra o que vai mudar; a segunda confirma
        r = c.post(f"/api/entidade/{APELIDO}/planilha",
                   data={"confirmar": confirmar},
                   files={"arquivo": ("base-do-sindicato.csv", planilha,
                                      "text/csv")},
                   headers={"Authorization": f"Bearer {token(gestor)}"})
        r.raise_for_status()
        confirmar = r.json()["sha256"]

    def cadastrar(i: int, arquivos: dict, **respostas: str) -> None:
        cpf, nome, email = pessoas[i]
        r = c.post("/api/cadastro", data={
            "token": token(cpf),
            "linha": json.dumps(te.linha(cpf, nome_completo=nome,
                                         email=email, **respostas))},
            files=[("arquivos", (n, b, "application/pdf"))
                   for n, b in arquivos.items()])
        r.raise_for_status()

    contrib = {"contribuicao-1.pdf": te._pdf(te.CONTRIB)}
    titulo = {**contrib, "sentenca.pdf": te._pdf(te.SENTENCA),
              "certidao_transito.pdf": te._pdf(te.CERTIDAO)}
    for i in (0, 1, 2, 3, 6, 7, 8, 9, 12, 13):
        cadastrar(i, contrib)
    for i in (4, 10, 14, 15, 16):
        cadastrar(i, titulo, ja_executou="nao", tem_acao_propria="nao")
    for i in (18, 19, 20):      # documento que é só imagem: fica para conferir
        cadastrar(i, {**contrib, "sentenca.pdf": te._so_imagem()})
    cadastrar(21, contrib, quer_aviso="sim")

    # Um andamento já registrado, para a área de processos ter o que contar
    # sem a demonstração falar com tribunal nenhum.
    numero = "".join(ch for ch in PROCESSO if ch.isdigit())
    banco.guardar_movimentos(url, APELIDO, [aviso.Movimento(
        numero=numero, grau="G1", data="2026-11-10",
        nome="Conclusos para decisão")])
    (raiz / APELIDO / "movimentos.jsonl").write_text(json.dumps({
        "coletado_em": "2026-11-11T09:00:00+00:00", "consultados": 1,
        "falhas": [], "movimentos": [{
            "numero": numero, "grau": "G1", "data": "2026-11-10",
            "nome": "Conclusos para decisão"}]}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    agenda.registrar(url, APELIDO, "coletar", ok=True, detalhe="demonstração")

    return [("Gestor do sindicato", gestor),
            ("Filiado com processo", pessoas[4][0]),
            ("Filiado que pediu aviso", pessoas[21][0]),
            ("Filiado que ainda não entrou", pessoas[30][0])]


def _cpf(c: str) -> str:
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


# ------------------------------------------------------------------ principal


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--porta", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1",
                    help="onde escutar. O padrão só atende este computador, "
                         "de propósito.")
    ap.add_argument("--banco", default="",
                    help="URL de um PostgreSQL VAZIO. Sem isto, a "
                         "demonstração cria e apaga o dela.")
    ap.add_argument("--pasta", default="",
                    help="onde guardar os arquivos da demonstração. Sem "
                         "isto, uma pasta temporária, apagada no fim.")
    a = ap.parse_args(argv)

    # O encerramento pelo sistema tem de passar pela MESMA limpeza do
    # Ctrl+C: servidor ou banco deixado para trás segura a porta da próxima.
    def _encerrar(*_: object) -> None:
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, _encerrar)

    pasta = pathlib.Path(a.pasta).resolve() if a.pasta else pathlib.Path(
        tempfile.mkdtemp(prefix="protocol-demo-"))
    pasta.mkdir(parents=True, exist_ok=True)
    estado: dict = {"servidor": None, "proprio": None}
    try:
        return _rodar(a, pasta, estado)
    except NaoDa as exc:
        print(f"\nNão deu para subir a demonstração: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nDemonstração encerrada.", flush=True)
        return 0
    finally:
        _limpar(estado["servidor"], estado["proprio"], pasta,
                apagar=not a.pasta)


def _rodar(a: argparse.Namespace, pasta: pathlib.Path, estado: dict) -> int:
    print("Preparando a demonstração (cerca de um minuto)...", flush=True)
    conferir_a_maquina()
    porta_livre(a.host, a.porta)
    if a.banco:
        exigir_banco_vazio(a.banco)
        url = a.banco
    else:
        estado["proprio"] = BancoProprio(pasta)
        url = estado["proprio"].url

    from ferramentas import ensaio_portal
    from servidor import banco, entidades, trocas

    banco.criar_esquema(url)
    raiz = pasta / "dados"
    shutil.rmtree(raiz, ignore_errors=True)
    raiz.mkdir()
    ent = entidades.Cadastro(raiz).criar(
        APELIDO, NOME, categorias=("auditor-fiscal-receita-federal",))
    pasta_ent = ent.pasta(raiz)
    pasta_ent.mkdir(parents=True, exist_ok=True)
    gestor = _suite(url)._cpf_sintetico(GESTOR)
    (pasta_ent / "gestores.csv").write_text(
        f"cpf,email\n{gestor},gestor@{DOMINIO}\n", encoding="utf-8")
    (pasta_ent / trocas.ARQUIVO_DE_DOMINIOS).write_text(
        DOMINIO + "\n", encoding="utf-8")

    print("  compilando o portal...", flush=True)
    portal = pasta / "portal"
    compilar_portal(portal)

    # MODO ENSAIO, sempre: o código de acesso aparece na tela e nenhum
    # e-mail sai. E sem o trabalho de fundo, que falaria com tribunal.
    ambiente = {
        **os.environ,
        "PROTOCOL_MODO_ENSAIO": "1",
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_AGENDAR": "0",
        "PROTOCOL_DATABASE_URL": url,
        "PROTOCOL_PORTAL_ESTATICO": str(portal),
        # Folga: numa demonstração uma pessoa só pede muitos códigos.
        "PROTOCOL_EMISSOES_POR_CPF_HORA": "200",
        "PROTOCOL_EMISSOES_POR_ORIGEM_HORA": "5000",
    }
    registro = open(pasta / "servidor.log", "w", encoding="utf-8")
    estado["servidor"] = subprocess.Popen(
        [sys.executable, "-m", "servidor", "--host", a.host,
         "--porta", str(a.porta)],
        cwd=REPO, env=ambiente, stdout=registro, stderr=subprocess.STDOUT)
    api = f"http://127.0.0.1:{a.porta}"
    if not ensaio_portal._esperar(f"{api}/saude"):
        raise NaoDa("o servidor não subiu. O motivo está em "
                    f"{pasta / 'servidor.log'}")

    print("  preenchendo o sindicato de demonstração...", flush=True)
    acessos = semear(api, url, raiz)

    print()
    print("=" * 62)
    print(f"NO AR — abra no navegador:  {api}/?entidade={APELIDO}")
    print("=" * 62)
    print("Para entrar, digite um destes CPFs. O código de acesso aparece")
    print("na própria tela (é demonstração: nenhum e-mail é enviado).")
    print()
    for quem, cpf in acessos:
        print(f"  {quem:30} {_cpf(cpf)}")
    print()
    print("Tudo aqui é fictício. Não envie documento de gente de verdade.")
    print("Para encerrar: Ctrl+C.", flush=True)
    estado["servidor"].wait()
    raise NaoDa("o servidor parou sozinho. O motivo está em "
                f"{pasta / 'servidor.log'}")


def _limpar(servidor, proprio, pasta: pathlib.Path, *, apagar: bool) -> None:
    if servidor is not None and servidor.poll() is None:
        servidor.terminate()
        try:
            servidor.wait(timeout=15)
        except subprocess.TimeoutExpired:
            servidor.kill()
    if proprio is not None:
        proprio.parar()
    if apagar:
        shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
