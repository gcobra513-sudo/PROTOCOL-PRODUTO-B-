#!/usr/bin/env python3
"""
Ensaia a implantação: RODA OS COMANDOS DO PRÓPRIO `implantacao/LEIAME.md`.

    sudo python3 implantacao/ensaio/ensaiar.py --maquina-descartavel --banco URL
    sudo python3 implantacao/ensaio/ensaiar.py --maquina-descartavel --desfazer

SÓ EM MÁQUINA DESCARTÁVEL (um contêiner Ubuntu 24.04). Ele cria o usuário
`protocol`, escreve em /srv, /etc, /var e /etc/hosts, e instala pacotes.

POR QUE LÊ O PASSO A PASSO EM VEZ DE REPETI-LO: um ensaio com os comandos
copiados ensaia a cópia. Aqui cada bloco de comando do LEIAME é executado
como está escrito, e os poucos que não cabem num contêiner são TROCADOS ou
PULADOS com o motivo dito na saída. Bloco que o ensaio não conhece faz o
ensaio falhar — `tests/testes_repositorio.py` confere isso sem precisar de
máquina, para o passo a passo não mudar sem o ensaio saber.

O QUE NÃO É ENSAIADO, porque um contêiner não tem:
- o systemd de verdade. O serviço é imitado com `bwrap`+`setpriv`, lendo do
  arquivo `.service` instalado o usuário, a pasta, o ambiente, o comando, o
  que pode ser escrito e a máscara. O resto do endurecimento não é imitado;
- o certificado público (ACME). O Caddy usa a autoridade interna dele;
- o GitHub. O clone vem de uma cópia local deste repositório;
- o servidor de e-mail de verdade. É um SMTP local, com TLS conferido;
- o temporizador. A cópia roda uma vez, com o comando do `.service` dela.

`--banco` é a URL de um banco PostgreSQL VAZIO, alcançável por TCP.
"""
from __future__ import annotations

import argparse
import email
import http.client
import json
import os
import pathlib
import re
import shutil
import signal
import ssl
import subprocess
import sys
import time

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
LEIAME = RAIZ / "implantacao" / "LEIAME.md"
TRABALHO = pathlib.Path("/opt/protocol-ensaio")
DOMINIO = "portal.exemplo.org"
SMTP = "smtp.exemplo.org"
# Cadastro declaradamente fictício: CPFs de teste, nomes que dizem que são.
CPF_GESTORA = "111.444.777-35"
CPF_FILIADA = "529.982.247-25"
SUDOERS = pathlib.Path("/etc/sudoers.d/protocol-ensaio")
AC_DO_CADDY = pathlib.Path(
    "/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt")

# Cada bloco do LEIAME, reconhecido por um trecho que só ele tem, e o que o
# ensaio faz com ele. "igual" roda como está escrito.
BLOCOS: list[tuple[str, str, str]] = [
    ("apt-get install", "igual", ""),
    ("useradd --system", "igual", ""),
    ("-m 750 /var/lib/protocol", "igual", ""),
    ("-m 751 /srv/protocol", "igual", ""),
    ("-m 755 /srv/protocol/portal", "igual", ""),
    ("-m 750 /etc/protocol", "igual", ""),
    ("ssh-keygen", "igual", ""),
    ("id_ed25519.pub", "igual", ""),
    ("git clone git@github.com", "trocado",
     "não há GitHub aqui: clona de uma cópia local deste repositório"),
    ("python3 -m venv", "igual", ""),
    ("pip install -r /srv/protocol/app", "igual", ""),
    ("protocol.env.exemplo /etc/protocol/protocol.env", "igual", ""),
    ("secrets.token_urlsafe", "igual", ""),
    ("banco.criar_esquema", "igual", ""),
    ("2026-11-03-oportunidade-origem-do-catalogo.sql", "pulado",
     "o banco do ensaio é novo: migração é para banco antigo"),
    ("2026-11-10-documento-origem-e-leitura-humana.sql", "pulado",
     "o banco do ensaio é novo: migração é para banco antigo"),
    ("conferir_forma.sql", "igual", ""),
    ("npx vite build", "igual", ""),
    ("/etc/systemd/system/", "igual", ""),
    ("systemctl enable --now", "trocado",
     "sem systemd: o serviço é imitado a partir do arquivo .service"),
    ("curl -s http://127.0.0.1:8000/saude", "igual", ""),
    ("Caddyfile /etc/caddy/Caddyfile", "igual", ""),
    ("caddy validate", "trocado",
     "valida como está escrito; sem systemd, o Caddy é posto no ar à mão, "
     "com a autoridade interna dele no lugar do certificado público"),
    ("sindicatos.py --raiz /var/lib/protocol categorias", "igual", ""),
    ("sindicatos.py --raiz /var/lib/protocol criar", "trocado",
     "o CPF do exemplo é só marcador: entra um CPF de teste"),
    ("sindicatos.py --raiz /var/lib/protocol listar", "igual", ""),
    ("trocas_de_email.py", "igual", ""),
    ("systemctl list-timers", "trocado",
     "sem systemd: a cópia roda uma vez, com o comando do .service dela"),
    ("git pull", "igual", ""),
    ("systemctl restart protocol", "trocado",
     "sem systemd: o serviço imitado é derrubado e posto de novo"),
]


def blocos_do_leiame() -> list[str]:
    return [b.strip() for b in
            re.findall(r"```bash\n(.*?)```", LEIAME.read_text("utf-8"), re.S)]


def classificar(bloco: str) -> tuple[str, str, str] | None:
    achados = [b for b in BLOCOS if b[0] in bloco]
    return achados[0] if len(achados) == 1 else None


# ------------------------------------------------------------------ miúdos

problemas: list[str] = []
relato: list[tuple[str, str, str]] = []
filhos: list[subprocess.Popen] = []
LOCAIS = f"127.0.0.1,localhost,{DOMINIO},{SMTP}"
# Ambiente limpo, MENOS o caminho de saída para a internet: onde o contêiner
# só alcança os pacotes por um proxy, `pip` e `npm` precisam dele. Os nomes
# do ensaio ficam de fora do proxy — eles são esta máquina.
AMBIENTE = {
    **{k: v for k, v in os.environ.items()
       if "proxy" in k.lower() or k in ("NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE",
                                        "NPM_CONFIG_USERCONFIG")},
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8",
    "HOME": "/root", "NO_PROXY": LOCAIS, "no_proxy": LOCAIS,
}


def diz(texto: str) -> None:
    print(texto, flush=True)


def confere(cond: bool, o_que: str) -> None:
    diz(f"    {'ok   ' if cond else 'FALHA'} {o_que}")
    if not cond:
        problemas.append(o_que)


def roda(comando: str, *, pode_falhar: bool = False) -> str:
    r = subprocess.run(["bash", "-c", comando], env=AMBIENTE,
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0 and not pode_falhar:
        raise SystemExit(f"\nPAROU: o comando falhou ({r.returncode}):\n  "
                         f"{comando}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout


def no_fundo(args: list[str], registro: str) -> subprocess.Popen:
    p = subprocess.Popen(args, env=AMBIENTE, stdin=subprocess.DEVNULL,
                         stdout=open(TRABALHO / registro, "ab"),
                         stderr=subprocess.STDOUT, start_new_session=True)
    filhos.append(p)
    return p


def derruba(p: subprocess.Popen) -> None:
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass
    # Quem morre na hora é o invólucro; o servidor ainda atende enquanto
    # encerra. Sem esperar o grupo sumir, o próximo a subir acha a porta
    # ocupada — e a checagem de "subiu" é respondida pelo que está saindo.
    for _ in range(100):
        try:
            os.killpg(p.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    os.killpg(p.pid, signal.SIGKILL)


def campo(unidade: str, nome: str) -> str:
    m = re.search(rf"(?m)^{nome}=(.*)$", unidade)
    if not m:
        raise SystemExit(f"o .service não tem {nome}=")
    return m.group(1).strip()


def servico_imitado() -> subprocess.Popen:
    """O que o systemd faria com /etc/systemd/system/protocol.service."""
    u = pathlib.Path("/etc/systemd/system/protocol.service").read_text("utf-8")
    args = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
            "--tmpfs", "/tmp", "--tmpfs", "/home", "--tmpfs", "/root",
            "--bind", campo(u, "ReadWritePaths"), campo(u, "ReadWritePaths"),
            "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
            "--setenv", "LANG", "C.UTF-8",
            # Só do ensaio: a autoridade do SMTP de teste. Numa máquina de
            # verdade o certificado do provedor fecha com as do sistema.
            "--setenv", "SSL_CERT_FILE", str(TRABALHO / "ac-conhecida.pem")]
    for linha in pathlib.Path(campo(u, "EnvironmentFile")).read_text(
            "utf-8").splitlines():
        if linha and not linha.startswith("#"):
            nome, _, valor = linha.partition("=")
            args += ["--setenv", nome, valor]
    args += ["--chdir", campo(u, "WorkingDirectory"), "setpriv",
             "--reuid", campo(u, "User"), "--regid", campo(u, "Group"),
             "--clear-groups", "--no-new-privs", "--", "sh", "-c",
             f"umask {campo(u, 'UMask')}; exec {campo(u, 'ExecStart')}"]
    p = no_fundo(args, "servidor.log")
    for _ in range(40):
        if "ok" in roda("curl -s -m 2 http://127.0.0.1:8000/saude",
                        pode_falhar=True):
            return p
        time.sleep(0.5)
    raise SystemExit("PAROU: o servidor não respondeu em 127.0.0.1:8000 — "
                     f"veja {TRABALHO}/servidor.log")


def preencher_ambiente(banco: str, segredo: str, porta_smtp: int) -> None:
    caminho = pathlib.Path("/etc/protocol/protocol.env")
    texto = caminho.read_text("utf-8")
    valores = {
        "PROTOCOL_SEGREDO": segredo,
        "PROTOCOL_DATABASE_URL": banco,
        "PROTOCOL_SMTP_HOST": SMTP,
        "PROTOCOL_SMTP_PORTA": str(porta_smtp),
        "PROTOCOL_SMTP_USUARIO": "usuario-de-ensaio",
        "PROTOCOL_SMTP_SENHA": "senha-de-ensaio",
        "PROTOCOL_SMTP_REMETENTE": f"portal@{DOMINIO}",
        "PROTOCOL_EMAIL_DE_QUEM_OPERA": "operacao@exemplo.invalid",
    }
    for nome, valor in valores.items():
        texto, n = re.subn(rf"(?m)^{nome}=.*$",
                           lambda _m, n=nome, v=valor: f"{n}={v}", texto)
        if n != 1:
            raise SystemExit(f"o exemplo de ambiente não tem {nome}=")
    caminho.write_text(texto, "utf-8")


def pedir(metodo: str, caminho: str, *, corpo: dict | None = None,
          token: str = "", origem: str = "127.0.0.1",
          cabecalhos: dict | None = None) -> tuple[int, dict, bytes]:
    """Um pedido ao portal PELA PORTA DA FRENTE: HTTPS, pelo Caddy, com o
    certificado conferido contra a autoridade dele."""
    ctx = ssl.create_default_context(cafile=str(AC_DO_CADDY))
    con = http.client.HTTPSConnection(DOMINIO, 443, context=ctx, timeout=60,
                                      source_address=(origem, 0))
    cab = dict(cabecalhos or {})
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cab["Content-Type"] = "application/json"
    if token:
        cab["Authorization"] = f"Bearer {token}"
    con.request(metodo, caminho, body=dados, headers=cab)
    r = con.getresponse()
    bruto = r.read()
    con.close()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, bruto


def codigo_no_correio(correio, destino: str) -> str:
    for _ in range(40):
        for bruta in reversed(correio.mensagens):
            msg = email.message_from_string(bruta)
            if destino in (msg["To"] or ""):
                texto = msg.get_payload(decode=True).decode("utf-8")
                return re.search(r"\b(\d{6})\b", texto).group(1)
        time.sleep(0.25)
    return ""


def entrar(correio, cpf: str, destino: str) -> str:
    antes = len(correio.mensagens)
    s, _, _ = pedir("POST", "/api/acesso/codigo",
                    corpo={"entidade": "sind-df", "cpf": cpf})
    if s != 202:
        return ""
    for _ in range(40):
        if len(correio.mensagens) > antes:
            break
        time.sleep(0.25)
    codigo = codigo_no_correio(correio, destino)
    s, _, b = pedir("POST", "/api/acesso/conferir",
                    corpo={"entidade": "sind-df", "cpf": cpf, "codigo": codigo})
    return json.loads(b).get("token", "") if s == 200 else ""


def cpf_de_teste(i: int) -> str:
    base = f"0009{i:05d}"
    for peso in (10, 11):
        soma = sum(int(d) * (peso - k) for k, d in enumerate(base))
        base += str((soma * 10) % 11 % 10)
    return base


# ------------------------------------------------------------------ o ensaio

def desfazer() -> None:
    roda("pkill -u protocol; pkill -u caddy; true",
         pode_falhar=True)
    time.sleep(1)
    roda("userdel protocol 2>/dev/null; rm -rf /srv/protocol /etc/protocol "
         "/var/lib/protocol /var/backups/protocol /opt/protocol-ensaio "
         "/etc/systemd/system/protocol.service "
         "/etc/systemd/system/protocol-copia.service "
         "/etc/systemd/system/protocol-copia.timer; "
         f"rm -f {SUDOERS}; "
         f"sed -i '/{DOMINIO}/d' /etc/hosts; true", pode_falhar=True)
    diz("desfeito.")


def ensaiar(banco: str) -> int:
    sys.path.insert(0, str(RAIZ))
    from tests.smtp_de_teste import ServidorSmtp, autoridade, certificado

    if pathlib.Path("/etc/protocol").exists():
        raise SystemExit("já existe /etc/protocol: esta máquina tem uma "
                         "implantação. Rode com --desfazer antes, se ela é "
                         "mesmo descartável.")
    blocos = blocos_do_leiame()
    desconhecidos = [b for b in blocos if classificar(b) is None]
    if desconhecidos:
        raise SystemExit("o passo a passo tem bloco que o ensaio não "
                         "conhece (ou reconhece duas vezes):\n  "
                         + "\n  ".join(b[:90] for b in desconhecidos))

    # --- o que é só do ensaio
    roda("apt-get update -q && apt-get install -y -q bubblewrap "
         "openssh-client openssl sudo curl util-linux")
    TRABALHO.mkdir(mode=0o755)
    # Numa Ubuntu recém-criada só existem os programas do `apt`. Um contêiner
    # de trabalho costuma ter outro Node em /usr/local, e o `sudo` o acharia
    # primeiro — o ensaio compilaria o portal com um Node que a máquina de
    # verdade não tem.
    SUDOERS.write_text(
        'Defaults secure_path="/usr/sbin:/usr/bin:/sbin:/bin"\n', "utf-8")
    SUDOERS.chmod(0o440)
    roda(f"git clone -q --bare {RAIZ} {TRABALHO}/origem.git")
    autoridade(TRABALHO, "conhecida")
    autoridade(TRABALHO, "desconhecida")
    certificado(TRABALHO, "conhecida", "smtp-certo", SMTP)
    certificado(TRABALHO, "desconhecida", "smtp-de-fora", SMTP)
    shutil.copy(TRABALHO / "conhecida.crt", TRABALHO / "ac-conhecida.pem")
    os.chmod(TRABALHO / "ac-conhecida.pem", 0o644)
    roda(f"grep -q {DOMINIO} /etc/hosts || "
         f"echo '127.0.0.1 {DOMINIO} {SMTP}' >> /etc/hosts")
    correio = ServidorSmtp(TRABALHO / "smtp-certo.crt",
                           TRABALHO / "smtp-certo.key")
    de_fora = ServidorSmtp(TRABALHO / "smtp-de-fora.crt",
                           TRABALHO / "smtp-de-fora.key")
    banco += ("&" if "?" in banco else "?") + (
        "application_name=protocol-ensaio&connect_timeout=10")

    servidor = caddy = None
    segredo = ""
    for bloco in blocos:
        marca, como, motivo = classificar(bloco)
        relato.append((bloco.splitlines()[0][:70], como, motivo))
        diz(f"\n[{como}] {bloco.splitlines()[0][:100]}")
        if motivo:
            diz(f"    {motivo}")
        if como == "pulado":
            continue
        if como == "igual":
            saida = roda(bloco)
            if marca == "secrets.token_urlsafe":
                segredo = saida.strip()
            elif marca == "protocol.env.exemplo /etc/protocol/protocol.env":
                pass
            elif marca == "banco.criar_esquema":
                diz("    esquema criado")
            elif marca == "conferir_forma.sql":
                confere(bool(saida.strip()), "a forma do banco foi lida: "
                        + saida.strip()[:60])
            elif marca == "npx vite build":
                confere(roda("sudo -u protocol node --version").startswith(
                    "v18."), "compilado com o Node 18 do Ubuntu 24.04")
                confere(roda("sudo -u caddy head -c 15 "
                             "/srv/protocol/portal/index.html",
                             pode_falhar=True).startswith("<!"),
                        "o usuário do Caddy lê o portal compilado")
            elif marca == "/etc/systemd/system/":
                v = subprocess.run(
                    ["systemd-analyze", "verify",
                     "/etc/systemd/system/protocol.service",
                     "/etc/systemd/system/protocol-copia.service",
                     "/etc/systemd/system/protocol-copia.timer"],
                    capture_output=True, text=True, env=AMBIENTE)
                confere(v.returncode == 0, "systemd-analyze aceita as três "
                        "unidades " + v.stderr.strip()[:200])
            elif marca.startswith("curl -s http://127.0.0.1:8000/saude"):
                saude = json.loads(saida)
                confere(saude.get("modo_ensaio") is False
                        and saude.get("envio_de_email") == "smtp",
                        "/saude: fora do modo ensaio, envio por SMTP")
            elif marca == "git pull":
                diz("    " + saida.strip().splitlines()[0][:80])
            if marca == "secrets.token_urlsafe":
                # É aqui que a pessoa edita o arquivo de ambiente (passo 5).
                preencher_ambiente(banco, segredo, correio.porta)
                diz("    ambiente preenchido (banco com `&` na URL)")
            continue

        # --- trocados
        if marca == "git clone git@github.com":
            roda(f"chown -R protocol:protocol {TRABALHO}/origem.git")
            roda(f"sudo -u protocol git clone -q {TRABALHO}/origem.git "
                 "/srv/protocol/app")
        elif marca == "systemctl enable --now":
            servidor = servico_imitado()
            diz("    servidor no ar, como o .service manda")
        elif marca == "caddy validate":
            roda("caddy validate --config /etc/caddy/Caddyfile")
            diz("    o Caddyfile do repositório valida como está")
            roda(r"sed -i 's/^\tencode gzip/\ttls internal\n\tencode gzip/' "
                 "/etc/caddy/Caddyfile")
            caddy = no_fundo(
                ["setpriv", "--reuid", "caddy", "--regid", "caddy",
                 "--init-groups", "--inh-caps", "+net_bind_service",
                 "--ambient-caps", "+net_bind_service", "env",
                 "HOME=/var/lib/caddy", "caddy", "run", "--config",
                 "/etc/caddy/Caddyfile"], "caddy.log")
            for _ in range(40):
                if AC_DO_CADDY.exists() and "ok" in roda(
                        f"curl -s -m 2 --cacert {AC_DO_CADDY} "
                        f"https://{DOMINIO}/saude", pode_falhar=True):
                    break
                time.sleep(0.5)
            pela_frente(correio)
        elif marca.endswith("criar"):
            roda(bloco.replace("000.000.000-00", CPF_GESTORA))
        elif marca == "systemctl list-timers":
            a_copia()
        elif marca == "systemctl restart protocol":
            derruba(servidor)
            servidor = servico_imitado()
            s, _, _ = pedir("GET", "/saude")
            confere(s == 200, "depois de reiniciar, o portal responde")

    # --- o que o passo a passo promete, medido pela porta da frente
    diz("\n== do gestor ao primeiro filiado com código, por HTTPS")
    o_primeiro_filiado(correio)
    diz("\n== o limite de pedidos de código, atrás do Caddy")
    o_limite()
    # Olhado ANTES do próximo trecho: a recusa que ele provoca deixa rastro
    # no registro, de propósito.
    registro = (TRABALHO / "servidor.log").read_text("utf-8", "replace")
    confere("Traceback" not in registro and "Read-only" not in registro,
            "o servidor não tentou escrever fora da raiz de dados, nem "
            "deixou rastro de erro")

    diz("\n== servidor de e-mail com certificado que não fecha")
    servidor = o_email_errado(servidor, correio, de_fora)

    for p in filhos:
        derruba(p)
    diz("\n" + "=" * 70)
    for linha, como, motivo in relato:
        if como != "igual":
            diz(f"{como.upper()}: {linha}\n    {motivo}")
    iguais = sum(1 for r in relato if r[1] == "igual")
    diz(f"{iguais} de {len(relato)} blocos do passo a passo rodaram como "
        "estão escritos.")
    if problemas:
        diz(f"{len(problemas)} FALHA(S):")
        for p in problemas:
            diz(f"  - {p}")
        return 1
    diz("o ensaio passou.")
    return 0


def pela_frente(correio) -> None:
    s, cab, corpo = pedir("GET", "/saude")
    confere(s == 200 and json.loads(corpo).get("ok") is True,
            "https: /saude chega ao servidor")
    s, cab, corpo = pedir("GET", "/")
    confere(s == 200 and b"<!doctype html" in corpo[:200].lower()
            and b"/assets/index-" in corpo,
            "https: a página do portal abre")
    s, _, _ = pedir("GET", "/qualquer/caminho")
    confere(s == 200, "https: endereço de tela cai no portal, não em 404")
    nome = next(p.name for p in
                pathlib.Path("/srv/protocol/portal/assets").glob("index-*.js"))
    s, c2, js = pedir("GET", f"/assets/{nome}")
    confere(s == 200 and "javascript" in c2.get("content-type", ""),
            "https: o programa do portal é entregue")
    confere(f"https://{DOMINIO}".encode() in js,
            "o portal compilado chama a API no endereço público")
    confere(cab.get("strict-transport-security", "").startswith("max-age")
            and cab.get("x-frame-options") == "DENY"
            and cab.get("x-content-type-options") == "nosniff"
            and cab.get("referrer-policy") == "no-referrer",
            "os quatro cabeçalhos de proteção saem")
    r = roda(f"curl -s -m 5 -o /dev/null -w '%{{http_code}} %{{redirect_url}}'"
             f" http://{DOMINIO}/")
    confere(r.startswith("308 https://"), "http redireciona para https")
    grande = roda(f"head -c 85000000 /dev/zero | curl -s -m 60 --cacert "
                  f"{AC_DO_CADDY} -o /dev/null -w '%{{http_code}}' -X POST "
                  f"--data-binary @- https://{DOMINIO}/api/acesso/sair")
    confere(grande == "413", "pedido de 85 MB é recusado na porta (413)")
    for fechado in ("/etc/protocol/protocol.env", "/var/lib/protocol",
                    "/var/backups/protocol"):
        r = subprocess.run(["sudo", "-u", "caddy", "ls", fechado],
                           capture_output=True, env=AMBIENTE)
        confere(r.returncode != 0, f"o usuário do Caddy NÃO lê {fechado}")


def o_primeiro_filiado(correio) -> None:
    gestora = entrar(correio, CPF_GESTORA, "gestor@sindicato.exemplo.org")
    confere(bool(gestora), "a gestora recebe o código por e-mail e entra")
    planilha = TRABALHO / "planilha.csv"
    planilha.write_text(
        "CPF,Nome Completo,E-mail,Cargo\n"
        f"{CPF_FILIADA},FULANA DE TAL (CADASTRO DE EXEMPLO),"
        "fulana@exemplo.invalid,Auditor Fiscal da Receita Federal\n", "utf-8")
    envia = (f"curl -s -m 60 --cacert {AC_DO_CADDY} -H 'Authorization: Bearer "
             f"{gestora}' -F arquivo=@{planilha} ")
    url = f"https://{DOMINIO}/api/entidade/sind-df/planilha"
    previa = json.loads(roda(envia + url))
    confere(previa.get("pessoas") == 1 and previa.get("gravado") is False,
            "a planilha é lida e mostrada antes de gravar")
    gravada = json.loads(roda(envia + f"-F confirmar={previa.get('sha256')} "
                              + url))
    confere(gravada.get("gravado") is True, "a planilha confirmada é gravada")
    filiada = entrar(correio, CPF_FILIADA, "fulana@exemplo.invalid")
    confere(bool(filiada), "A FILIADA RECEBE O CÓDIGO POR E-MAIL E ENTRA")
    s, _, b = pedir("GET", "/api/minhas-acoes", token=filiada)
    confere(s == 200 and "pendencias" in json.loads(b),
            "a filiada vê a resposta dela")
    s, _, b = pedir("GET", "/api/entidade/sind-df/panorama", token=gestora)
    confere(s == 200 and "1 pessoa" in json.loads(b).get("manchete", ""),
            "o painel da gestora conta a filiada")
    s, _, _ = pedir("GET", "/api/entidade/sind-df/panorama", token=filiada)
    confere(s in (401, 403), "a filiada não abre o painel do sindicato")


def o_limite() -> None:
    limite = 20
    vistos = []
    for i in range(limite + 3):
        s, _, _ = pedir("POST", "/api/acesso/codigo", origem="127.0.0.2",
                        corpo={"entidade": "sind-df", "cpf": cpf_de_teste(i)},
                        cabecalhos={"X-Forwarded-For": f"10.9.8.{i}"})
        vistos.append(s)
    confere(vistos == [202] * limite + [429] * 3,
            f"de um mesmo endereço, forjando o cabeçalho a cada pedido: "
            f"{limite} passam e os seguintes são recusados ({vistos[-4:]})")
    s, _, _ = pedir("POST", "/api/acesso/codigo", origem="127.0.0.3",
                    corpo={"entidade": "sind-df", "cpf": cpf_de_teste(99)})
    confere(s == 202, "outro endereço não paga pelo primeiro")


def o_email_errado(servidor, correio, de_fora):
    """Aponta o envio para um servidor cujo certificado vem de autoridade
    que a máquina não conhece. O código NÃO pode chegar lá."""
    env = pathlib.Path("/etc/protocol/protocol.env")
    texto = env.read_text("utf-8")
    env.write_text(texto.replace(f"PROTOCOL_SMTP_PORTA={correio.porta}",
                                 f"PROTOCOL_SMTP_PORTA={de_fora.porta}"),
                   "utf-8")
    derruba(servidor)
    servidor = servico_imitado()
    pedir("POST", "/api/acesso/codigo", origem="127.0.0.4",
          corpo={"entidade": "sind-df", "cpf": CPF_FILIADA})
    time.sleep(3)
    confere(not de_fora.mensagens and not de_fora.autenticou,
            "nem o código nem a senha do envio chegam ao servidor errado")
    registro = (TRABALHO / "servidor.log").read_text("utf-8", "replace")
    confere("CERTIFICATE_VERIFY_FAILED" in registro
            or "certificate verify failed" in registro,
            "e o registro do servidor diz por quê")
    # A PESSOA LEU "código enviado". Quem tem de saber é quem opera, e o
    # lugar é a saúde — que é o que um monitor de fora consegue ler.
    saude = json.loads(pedir("GET", "/saude")[2])
    confere(saude.get("ok") is False and saude.get("envio") == "falhando",
            "/saude denuncia o envio parado "
            f"(ok={saude.get('ok')}, envio={saude.get('envio')})")
    env.write_text(texto, "utf-8")
    derruba(servidor)
    servidor = servico_imitado()
    # De volta ao servidor certo, SEM ninguém pedir código: é a conferência
    # da conexão, disparada pela própria saúde, que tem de dizer "ok".
    envio = ""
    for _ in range(20):
        envio = json.loads(pedir("GET", "/saude")[2]).get("envio", "")
        if envio != "conferindo":
            break
        time.sleep(0.5)
    confere(envio == "ok",
            f"com o servidor de e-mail certo, /saude diz envio ok ({envio})")
    return servidor


def a_copia() -> None:
    u = pathlib.Path(
        "/etc/systemd/system/protocol-copia.service").read_text("utf-8")
    roda(f"sudo -u {campo(u, 'User')} {campo(u, 'ExecStart')}")
    copias = sorted(pathlib.Path("/var/backups/protocol").glob("*.tar.gz"))
    confere(len(copias) == 1 and copias[0].stat().st_mode & 0o077 == 0,
            "a cópia existe e é fechada aos outros")
    destino = TRABALHO / "restaura"
    destino.mkdir()
    roda(f"tar -C {destino} -xzf {copias[0]}")
    # O banco de sessões muda a cada pedido; o que tem de voltar igual é o
    # que é autoridade: os arquivos de cada sindicato.
    r = subprocess.run(["diff", "-r", "-x", "acesso.sqlite3*",
                        str(destino / "protocol"), "/var/lib/protocol"],
                       capture_output=True, text=True)
    confere(r.returncode == 0, "a cópia restaurada é igual à raiz de dados "
            + r.stdout[:200])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--maquina-descartavel", action="store_true")
    ap.add_argument("--banco", default="")
    ap.add_argument("--desfazer", action="store_true")
    a = ap.parse_args(argv)
    if not a.maquina_descartavel:
        ap.error("este ensaio cria usuário e escreve em /srv, /etc e /var. "
                 "Só roda com --maquina-descartavel.")
    if os.geteuid() != 0:
        ap.error("precisa de root")
    if pathlib.Path("/proc/1/comm").read_text().strip() == "systemd":
        ap.error("esta máquina tem systemd de verdade — não é o contêiner "
                 "que este ensaio espera. Numa máquina de verdade, siga o "
                 "passo a passo.")
    if a.desfazer:
        desfazer()
        return 0
    if not a.banco.startswith("postgresql://"):
        ap.error("--banco tem de ser a URL de um banco PostgreSQL vazio")
    try:
        return ensaiar(a.banco)
    finally:
        for p in filhos:
            derruba(p)


if __name__ == "__main__":
    raise SystemExit(main())
