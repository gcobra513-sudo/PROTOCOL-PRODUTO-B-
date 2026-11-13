"""
Um servidor SMTP mínimo, de verdade, para teste — e as autoridades de teste.

Mora à parte porque dois lugares o usam: `testes_remetente.py` e o ensaio da
implantação (`implantacao/ensaio/ensaiar.py`). Fala só o que `smtplib`
precisa: EHLO, STARTTLS, AUTH, MAIL, RCPT, DATA, QUIT. Guarda o que viu.
"""
from __future__ import annotations

import pathlib
import socket
import ssl
import subprocess
import threading


def openssl(*args: str) -> None:
    subprocess.run(["openssl", *args], check=True, capture_output=True)


def autoridade(pasta: pathlib.Path, nome: str) -> None:
    openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
             "-keyout", str(pasta / f"{nome}.key"),
             "-out", str(pasta / f"{nome}.crt"),
             "-subj", f"/CN=AC de teste {nome}",
             # O Python de hoje recusa AC sem estas duas extensões.
             "-addext", "basicConstraints=critical,CA:TRUE",
             "-addext", "keyUsage=critical,keyCertSign,cRLSign")


def certificado(pasta: pathlib.Path, ac: str, nome: str, dns: str) -> None:
    openssl("req", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(pasta / f"{nome}.key"),
             "-out", str(pasta / f"{nome}.csr"), "-subj", f"/CN={dns}")
    (pasta / f"{nome}.ext").write_text(f"subjectAltName=DNS:{dns}\n")
    openssl("x509", "-req", "-in", str(pasta / f"{nome}.csr"),
             "-CA", str(pasta / f"{ac}.crt"), "-CAkey", str(pasta / f"{ac}.key"),
             "-CAcreateserial", "-days", "2",
             "-extfile", str(pasta / f"{nome}.ext"),
             "-out", str(pasta / f"{nome}.crt"))


class ServidorSmtp:
    """Um SMTP mínimo com STARTTLS, numa porta livre. Guarda o que viu."""

    def __init__(self, cert: pathlib.Path, chave: pathlib.Path,
                 porta: int = 0) -> None:
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(cert, chave)
        self.escuta = socket.socket()
        self.escuta.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.escuta.bind(("127.0.0.1", porta))
        self.escuta.listen(8)
        self.porta = self.escuta.getsockname()[1]
        self.autenticou = False
        self.mensagens: list[str] = []
        self.fio = threading.Thread(target=self._atender, daemon=True)
        self.fio.start()

    def _atender(self) -> None:
        while True:
            try:
                con, _ = self.escuta.accept()
            except OSError:
                return
            con.settimeout(10)
            try:
                self._conversa(con)
            except (OSError, ssl.SSLError):
                pass
            finally:
                con.close()

    def _conversa(self, con: socket.socket) -> None:
        fh = con.makefile("rwb")

        def diz(texto: str) -> None:
            fh.write(texto.encode() + b"\r\n")
            fh.flush()

        cifrado = False
        diz("220 teste")
        while True:
            linha = fh.readline()
            if not linha:
                return
            verbo = linha.decode("utf-8", "replace").strip().upper()
            if verbo.startswith(("EHLO", "HELO")):
                diz("250-teste")
                if not cifrado:
                    diz("250-STARTTLS")
                diz("250 AUTH PLAIN LOGIN")
            elif verbo.startswith("STARTTLS"):
                diz("220 pode")
                con = self.ctx.wrap_socket(con, server_side=True)
                fh = con.makefile("rwb")
                cifrado = True
            elif verbo.startswith("AUTH"):
                self.autenticou = True
                diz("235 ok")
            elif verbo.startswith(("MAIL", "RCPT", "RSET", "NOOP")):
                diz("250 ok")
            elif verbo.startswith("DATA"):
                diz("354 mande")
                corpo = b""
                while not corpo.endswith(b"\r\n.\r\n"):
                    pedaco = fh.readline()
                    if not pedaco:
                        return
                    corpo += pedaco
                self.mensagens.append(corpo.decode("utf-8", "replace"))
                diz("250 recebida")
            elif verbo.startswith("QUIT"):
                diz("221 tchau")
                return
            else:
                diz("502 não sei")

    def fechar(self) -> None:
        self.escuta.close()
        self.fio.join(timeout=5)
