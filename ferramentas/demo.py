#!/usr/bin/env python3
"""
A demonstração do portal, no seu computador, com um comando.

    python3 ferramentas/demo.py

Sobe o servidor e o portal num endereço só (http://127.0.0.1:8080), com um
sindicato de demonstração já preenchido, e imprime com que CPF entrar. Fica
no ar até você apertar Ctrl+C; aí desliga tudo e apaga o que criou.

TUDO É FICTÍCIO, e declaradamente: os nomes trazem "DE EXEMPLO (FICTÍCIO)" escrito, os
CPFs são montados a partir de um contador, os e-mails ficam num domínio que
não existe, e nenhuma mensagem sai — o servidor roda em modo ensaio, em que
o código de acesso aparece na tela. NÃO ponha dado de gente de verdade aqui.

O BANCO. Sem `--banco`, a demonstração cria um PostgreSQL só dela, numa
pasta temporária, e o apaga no fim — basta o PostgreSQL estar instalado.
Com `--banco URL`, usa o banco que você indicar, que tem de estar VAZIO: a
demonstração não apaga banco de ninguém, nem para se ajeitar.

Roda em Linux e macOS. No Windows, dentro do WSL (ver o README.md).

O que precisa estar instalado: Python 3.11+, Node.js 18+ e PostgreSQL 14+, e

    pip install --require-hashes -r requirements.lock
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import pathlib
import secrets
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
# NÚMERO QUE NÃO EXISTE: sequencial zero, que nenhum tribunal distribui. A
# demonstração registra um andamento inventado nele, e inventar andamento
# num processo de verdade seria afirmar coisa falsa sobre um caso real.
PROCESSO = "0000000-35.2000.4.01.0000"
#: O catálogo fictício da demonstração (`implantacao/demo/categorias/`).
CATALOGO = REPO / "implantacao" / "demo" / "categorias"
CATEGORIA = "servidor-de-exemplo"
CARGO = "Servidor de Exemplo"
ACAO = "EXEMPLO-FICTICIA"
#: SÓ O PRIMEIRO NOME É DE GENTE. O sobrenome de todos é "DE EXEMPLO", e a
#: marca "(FICTÍCIA)" vai escrita: nome plausível, com CPF que fecha o
#: dígito, numa página pública, passaria por pessoa real. Mulher e homem se
#: alternam — a marca concorda pelo índice.
NOMES = (
    "MARIA", "JOSE", "ANA", "ANTONIO", "HELENA", "FRANCISCO", "LUCIA",
    "CARLOS", "TEREZA", "PAULO", "VERA", "PEDRO", "ROSA", "LUIZ", "MARTA",
    "MARCOS", "SONIA", "RAIMUNDO", "REGINA", "SEBASTIAO", "CELIA", "MANOEL",
    "NEUSA", "JORGE", "IRENE", "ROBERTO", "ALICE", "SERGIO", "DALVA",
    "GERALDO", "EDNA", "FERNANDO", "ZELIA", "EDSON", "NAIR", "JOAQUIM",
    "ELZA", "BENEDITO", "IVONE", "WALTER", "OLGA", "NELSON",
)
#: O segundo sindicato de demonstração, que contratou o mesmo escritório A.
APELIDO_B = "demo-sindicato-b"
NOME_B = "Sindicato de Demonstração B"
NOMES_B = ("RUI", "LIA", "IVO", "EVA", "ARI", "ISA", "NEI", "ZITA")
GESTOR = 9001                   # índice do CPF sintético do gestor
ADVOGADO = 9051                 # idem, de quem entra pelo escritório A


class NaoDa(Exception):
    """Falta algo na máquina. A mensagem é para quem chamou ler e resolver."""


# ---------------------------------------------------------------- o que falta


def conferir_a_maquina(*, precisa_de_node: bool = True) -> None:
    # O SERVIDOR É DE LINUX, que é onde ele vai morar: as travas de arquivo
    # do rol e do apagamento usam `fcntl`, que o Windows não tem. Dito aqui,
    # antes de tudo — da primeira vez a demonstração criou o banco inteiro e
    # só então quebrou, com um rastro de erro que não dizia o que fazer.
    if os.name == "nt":
        raise NaoDa(
            "o servidor não roda direto no Windows (ele é feito para Linux, "
            "onde vai ser hospedado).\n"
            "  Rode dentro do WSL, o Linux que o próprio Windows instala: "
            "veja \"No Windows\" no README.md.")
    faltam = [m for m in ("fastapi", "uvicorn", "psycopg", "multipart",
                          "pypdf", "openpyxl", "httpx", "reportlab")
              if importlib.util.find_spec(m) is None]
    if faltam:
        raise NaoDa(
            "faltam pacotes do Python: " + ", ".join(faltam) + ".\n"
            "  pip install --require-hashes -r requirements.lock")
    # Com o portal já compilado (a imagem da demonstração hospedada), o
    # Node não entra na máquina que serve — menos coisa instalada lá.
    for programa in ("node", "npx", "npm") if precisa_de_node else ():
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

    SÓ EM 127.0.0.1, numa porta livre, e COM SENHA sorteada na hora. Era
    sem senha, pelo raciocínio de que só programa desta máquina alcança — e
    numa máquina compartilhada "programa desta máquina" inclui os outros
    usuários, que entrariam como administrador do banco de quem roda a
    demonstração (auditoria de 16/11/2026).
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
        print("  criando o banco da demonstração...", flush=True)
        senha = secrets.token_urlsafe(24)
        arquivo_da_senha = pasta / "senha-do-banco"
        arquivo_da_senha.touch(mode=0o600)
        arquivo_da_senha.write_text(senha + "\n", encoding="utf-8")
        try:
            r = subprocess.run(
                [initdb, "-D", str(self.dados), "-U", "postgres",
                 "-A", "scram-sha-256", f"--pwfile={arquivo_da_senha}",
                 "-E", "UTF8", "--locale=C"], capture_output=True, text=True,
                stdin=subprocess.DEVNULL)
        finally:
            arquivo_da_senha.unlink(missing_ok=True)
        if r.returncode != 0:
            raise NaoDa("o PostgreSQL não conseguiu criar o banco da "
                        f"demonstração:\n{r.stdout}\n{r.stderr}")
        # Memória pequena de propósito: a demonstração hospedada roda numa
        # máquina de 512 MB, junto com o servidor, e são 42 cadastros.
        opcoes = (f"-p {self.porta} -c listen_addresses=127.0.0.1 "
                  "-c shared_buffers=24MB -c max_connections=20")
        if os.name != "nt":
            # Sem soquete em arquivo: só a porta em 127.0.0.1. NO WINDOWS
            # NÃO: lá o padrão já é nenhum, e as aspas simples não são aspas
            # — o servidor recebia `''` como nome de pasta e não subia
            # (visto na primeira vez que a demonstração rodou em Windows).
            opcoes += " -c unix_socket_directories=''"
        # A SAÍDA VAI PARA ARQUIVO, NÃO PARA UM CANO. O servidor que o
        # `pg_ctl` deixa rodando herda a saída de quem o chamou; com um cano,
        # quem espera o fim da saída espera para sempre, porque o servidor
        # nunca a fecha. Visto no Windows: o banco subia e a demonstração
        # ficava parada em "Preparando".
        with open(pasta / "pg_ctl.log", "w", encoding="utf-8") as saida:
            try:
                codigo = subprocess.run(
                    [self.pg_ctl, "-D", str(self.dados), "-w", "-o", opcoes,
                     "-l", str(pasta / "postgres.log"), "start"],
                    stdout=saida, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL).returncode
            except BaseException:
                # Interrompido no meio da partida: o servidor pode já estar
                # de pé, e ninguém mais teria como desligá-lo.
                self.parar()
                raise
        r = subprocess.CompletedProcess(
            [], codigo, (pasta / "pg_ctl.log").read_text(
                encoding="utf-8", errors="replace"), "")
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
        self.url = (f"postgresql://postgres:{senha}@127.0.0.1:"
                    f"{self.porta}/postgres")

    def parar(self) -> None:
        subprocess.run([self.pg_ctl, "-D", str(self.dados), "-m", "fast",
                        "-w", "stop"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)


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
                f"{nome} DE EXEMPLO (FICTÍCI{'A' if i % 2 == 0 else 'O'})",
                f"filiado{i + 1:02d}@{DOMINIO}")
               for i, nome in enumerate(NOMES)]
    c = httpx.Client(base_url=api, timeout=120, trust_env=False)

    def token(cpf: str, apelido: str = APELIDO) -> str:
        codigo = c.post("/api/acesso/codigo", json={
            "entidade": apelido, "cpf": cpf}).json()["codigo_do_ensaio"]
        return c.post("/api/acesso/conferir", json={
            "entidade": apelido, "cpf": cpf, "codigo": codigo}).json()["token"]

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
        linhas.append(f"{cpf};{nome};{email};{CARGO};2004-03;{processo}")
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
                                         email=email, cargo=CARGO,
                                         **respostas))},
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

    # O ROL DE SUBSTITUÍDOS DA AÇÃO FICTÍCIA, enviado pelo gestor como um
    # sindicato enviaria. É ele que separa os três resultados: dos cinco que
    # têm título, quatro constam e PODEM; um ficou de fora e não pode. Os
    # doze últimos da planilha também ficaram de fora. O resto consta e
    # ainda depende de alguma coisa.
    no_rol = [pessoas[i][0] for i in range(30) if i != 16]
    rol = ("CPF\r\n" + "\r\n".join(no_rol) + "\r\n").encode("utf-8")
    confirmar = ""
    for _ in range(2):
        r = c.post(f"/api/entidade/{APELIDO}/rol-de-substituidos",
                   data={"acao": ACAO, "completo": "sim",
                         "confirmar": confirmar},
                   files={"arquivo": ("rol-de-substituidos.csv", rol,
                                      "text/csv")},
                   headers={"Authorization": f"Bearer {token(gestor)}"})
        r.raise_for_status()
        confirmar = r.json()["sha256"]

    # A FICHA FINANCEIRA, também pelo gestor e pela porta da frente: a base
    # de cálculo dos quatro que podem, de 03/2004 a 12/2008. Com a verba
    # fictícia do catálogo (10%), a conta deles sai — e os outros continuam
    # mostrando o que falta para ela. Valores redondos de propósito: 58
    # meses de 10% sobre 5.000,00 se conferem de cabeça (29.000,00).
    meses = [f"{m:02d}/{a}" for a in range(2004, 2009) for m in range(1, 13)
             if (a, m) >= (2004, 3)]
    ficha = "CPF;Competência;Base\r\n" + "".join(
        f"{pessoas[i][0]};{mes};{base}\r\n"
        for i, base in ((4, "5.000,00"), (10, "6.200,00"),
                        (14, "4.800,00"), (15, "5.500,00"))
        for mes in meses)
    confirmar = ""
    for _ in range(2):
        r = c.post(f"/api/entidade/{APELIDO}/ficha-financeira",
                   data={"confirmar": confirmar},
                   files={"arquivo": ("ficha-financeira.csv",
                                      ficha.encode("utf-8"), "text/csv")},
                   headers={"Authorization": f"Bearer {token(gestor)}"})
        r.raise_for_status()
        confirmar = r.json()["sha256"]

    # OS ESCRITÓRIOS que o sindicato de demonstração "contratou", e a
    # triagem — feita pelo gestor, pela porta da frente. Dois escritórios
    # fictícios: o A cuida da ação de exemplo e recebe os casos; o B existe
    # para a tela mostrar que um não vê o que é do outro.
    advogado = te._cpf_sintetico(ADVOGADO)
    (raiz / APELIDO / "escritorios.json").write_text(json.dumps({
        "escritorios": [
            {"id": "exemplo-a", "nome": "Escritório de Exemplo A (fictício)",
             "contato": f"atendimento@escritorio-a.{DOMINIO}",
             "acoes": [ACAO],
             "pessoas": [{"cpf": advogado,
                          "email": f"equipe@escritorio-a.{DOMINIO}"}]},
            {"id": "exemplo-b", "nome": "Escritório de Exemplo B (fictício)",
             "contato": f"atendimento@escritorio-b.{DOMINIO}", "acoes": [],
             "pessoas": [{"cpf": te._cpf_sintetico(ADVOGADO + 1),
                          "email": f"equipe@escritorio-b.{DOMINIO}"}]},
        ]}, ensure_ascii=False), encoding="utf-8")
    # TRÊS CASOS PARADOS, e é a ÚNICA coisa desta semente que não entra
    # pela porta da frente. Não há como: a porta grava "encaminhado agora",
    # e um caso só fica parado depois de sete dias. Então estes três são
    # gravados pelo MESMO módulo que a rota usa, com a data de dez dias
    # atrás — e o lembrete é o do agendador, rodado como ele rodaria no
    # oitavo dia. O que a tela mostra deles (o alerta em vermelho, "há 10
    # dias", o lembrete no histórico) é o que o portal mostraria de verdade.
    import datetime as dt

    from servidor import escritorios, remetente

    agora = dt.datetime.now(dt.UTC).replace(microsecond=0)
    pasta_do_sindicato = raiz / APELIDO
    parados = {pessoas[i][0] for i in (1, 2, 3)}
    escritorios.encaminhar(
        pasta_do_sindicato, parados, acao=ACAO, escritorio="exemplo-a",
        base_de=lambda: parados, quem="demonstracao",
        quando=(agora - dt.timedelta(days=10)).isoformat())
    escritorios.lembrar_parados(
        pasta_do_sindicato, sindicato=NOME,
        correio=remetente.ParaArquivo(raiz),
        agora=(agora - dt.timedelta(days=2)).isoformat())

    r = c.post(f"/api/entidade/{APELIDO}/encaminhamentos",
               json={"acao": ACAO, "escritorio": "exemplo-a"},
               headers={"Authorization": f"Bearer {token(gestor)}"})
    r.raise_for_status()
    # DOIS FILIADOS SE CADASTRAM DEPOIS DA TRIAGEM: são eles que o painel
    # mostra como "ainda não encaminhados", para quem apresenta ter um
    # botão de encaminhar para apertar.
    for i in (22, 24):
        cadastrar(i, contrib)

    # E O ESCRITÓRIO JÁ TRABALHOU EM ALGUNS, para as três telas terem o que
    # mostrar: o filiado de exemplo com a documentação completa, um com
    # documento faltando, um só recebido. O resto espera — e é a fila.
    do_escritorio = {"Authorization": f"Bearer {token(advogado)}"}
    for i, situacao, faltam in ((4, "COMPLETO", []), (10, "RECEBIDO", []),
                                (0, "PENDENTE", ["procuracao", "identidade"])):
        r = c.post(f"/api/entidade/{APELIDO}/escritorio/casos",
                   json={"cpf": pessoas[i][0], "acao": ACAO,
                         "situacao": situacao, "faltam": faltam},
                   headers=do_escritorio)
        r.raise_for_status()

    # O SEGUNDO SINDICATO, que contratou O MESMO escritório. Existe para a
    # visão única: com um login, o escritório A vê os casos dos dois — e é
    # o que um escritório que atende vários sindicatos precisa ver. Pela
    # porta da frente, como o primeiro: planilha, cadastro, triagem.
    gestor_b = te._cpf_sintetico(GESTOR + 1)
    da_b = [(te._cpf_sintetico(9300 + i), f"{nome} DE EXEMPLO (FICTÍCI"
             f"{'O' if i % 2 == 0 else 'A'})", f"filiado{i + 1:02d}@b.{DOMINIO}")
            for i, nome in enumerate(NOMES_B)]
    planilha_b = ("\r\n".join(
        ["CPF;Nome Completo;E-mail;Cargo;Filiado desde;Processo"]
        + [f"{cpf};{nome};{email};{CARGO};2005-01;"
           for cpf, nome, email in da_b]) + "\r\n").encode("latin-1")
    confirmar = ""
    for _ in range(2):
        r = c.post(f"/api/entidade/{APELIDO_B}/planilha",
                   data={"confirmar": confirmar},
                   files={"arquivo": ("base.csv", planilha_b, "text/csv")},
                   headers={"Authorization":
                            f"Bearer {token(gestor_b, APELIDO_B)}"})
        r.raise_for_status()
        confirmar = r.json()["sha256"]
    for i, (cpf, nome, email) in enumerate(da_b[:5]):
        r = c.post("/api/cadastro", data={
            "token": token(cpf, APELIDO_B),
            "linha": json.dumps(te.linha(cpf, nome_completo=nome, email=email,
                                         cargo=CARGO))},
            files=[("arquivos", (n, b, "application/pdf"))
                   for n, b in (titulo if i < 2 else contrib).items()])
        r.raise_for_status()
    # O MESMO CPF E O MESMO E-MAIL do escritório A: é isso que faz o
    # servidor juntar os dois sindicatos na visão dele.
    (raiz / APELIDO_B / "escritorios.json").write_text(json.dumps({
        "escritorios": [
            {"id": "exemplo-a", "nome": "Escritório de Exemplo A (fictício)",
             "contato": f"atendimento@escritorio-a.{DOMINIO}",
             "acoes": [ACAO],
             "pessoas": [{"cpf": advogado,
                          "email": f"equipe@escritorio-a.{DOMINIO}"}]},
        ]}, ensure_ascii=False), encoding="utf-8")
    r = c.post(f"/api/entidade/{APELIDO_B}/encaminhamentos",
               json={"acao": ACAO, "escritorio": "exemplo-a"},
               headers={"Authorization":
                        f"Bearer {token(gestor_b, APELIDO_B)}"})
    r.raise_for_status()
    r = c.post(f"/api/entidade/{APELIDO_B}/escritorio/casos",
               json={"cpf": da_b[0][0], "acao": ACAO, "situacao": "RECEBIDO",
                     "faltam": []}, headers=do_escritorio)
    r.raise_for_status()

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

    acessos = [("Gestor do sindicato", gestor),
               ("Filiado com processo", pessoas[4][0]),
               ("Filiado que pediu aviso", pessoas[21][0]),
               ("Filiado que ainda não entrou", pessoas[30][0]),
               ("Escritório contratado", advogado)]
    # NA TELA TAMBÉM: quem abre o link não vê este terminal. O servidor só
    # publica este arquivo em modo ensaio.
    (raiz / APELIDO / "acessos_da_demonstracao.json").write_text(json.dumps([
        {"quem": quem, "cpf": cpf,
         "area": ("painel" if cpf == gestor
                  else "escritorio" if cpf == advogado else "cadastro")}
        for quem, cpf in acessos], ensure_ascii=False), encoding="utf-8")
    return acessos


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
    ap.add_argument("--portal-pronto", default="",
                    help="pasta de um portal JÁ compilado (com a API em "
                         "\"/\"). Sem isto, compila agora, e precisa do Node.")
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
    conferir_a_maquina(precisa_de_node=not a.portal_pronto)
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
        APELIDO, NOME, categorias=(CATEGORIA,))
    pasta_ent = ent.pasta(raiz)
    pasta_ent.mkdir(parents=True, exist_ok=True)
    gestor = _suite(url)._cpf_sintetico(GESTOR)
    (pasta_ent / "gestores.csv").write_text(
        f"cpf,email\n{gestor},gestor@{DOMINIO}\n", encoding="utf-8")
    (pasta_ent / trocas.ARQUIVO_DE_DOMINIOS).write_text(
        DOMINIO + "\n", encoding="utf-8")
    # O segundo sindicato (`semear` diz para que serve).
    pasta_b = entidades.Cadastro(raiz).criar(
        APELIDO_B, NOME_B, categorias=(CATEGORIA,)).pasta(raiz)
    pasta_b.mkdir(parents=True, exist_ok=True)
    (pasta_b / "gestores.csv").write_text(
        f"cpf,email\n{_suite(url)._cpf_sintetico(GESTOR + 1)},"
        f"gestor@b.{DOMINIO}\n", encoding="utf-8")
    (pasta_b / trocas.ARQUIVO_DE_DOMINIOS).write_text(
        DOMINIO + "\n", encoding="utf-8")

    if a.portal_pronto:
        portal = pathlib.Path(a.portal_pronto).resolve()
        if not (portal / "index.html").is_file():
            raise NaoDa(f"--portal-pronto não tem um portal compilado: "
                        f"{portal}")
    else:
        print("  compilando o portal...", flush=True)
        portal = pasta / "portal"
        compilar_portal(portal)

    # MODO ENSAIO, sempre: o código de acesso aparece na tela e nenhum
    # e-mail sai. E sem o trabalho de fundo, que falaria com tribunal.
    ambiente = {
        # SEM AS `PROTOCOL_*` DE QUEM CHAMOU. Com `PROTOCOL_SMTP_HOST` no
        # ambiente — a máquina de quem opera um servidor de verdade — a
        # demonstração mandaria e-mail de verdade, para endereços que
        # qualquer visitante põe numa planilha (auditoria de 16/11/2026).
        **{k: v for k, v in os.environ.items()
           if not k.startswith("PROTOCOL_")},
        "PROTOCOL_MODO_ENSAIO": "1",
        # O CATÁLOGO FICTÍCIO: uma carreira e uma ação inventadas, para a
        # demonstração ter quem pode. O servidor só o aceita em modo ensaio.
        "PROTOCOL_CATEGORIAS_DA_DEMONSTRACAO": str(CATALOGO),
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_AGENDAR": "0",
        "PROTOCOL_DATABASE_URL": url,
        "PROTOCOL_PORTAL_ESTATICO": str(portal),
        # Folga: numa demonstração uma pessoa só pede muitos códigos.
        # Teto de envio baixo: a hospedagem gratuita tem 512 MB, com o banco
        # junto, e um pacote de 60 MB lido na memória derruba a máquina.
        "PROTOCOL_TETO_DO_PACOTE_MB": "8",
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
