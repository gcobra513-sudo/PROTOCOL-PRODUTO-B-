"""
A entrega do código de acesso.

Duas implementações, e a escolha é do ambiente:

- `PorSmtp` manda e-mail de verdade. É o que roda em produção;
- `ParaArquivo` escreve o código num arquivo da pasta de dados. É para
  desenvolver sem servidor de e-mail.

O que NÃO existe aqui é uma terceira implementação que devolve o código na
resposta HTTP. Essa está em `app.py`, vale só com `PROTOCOL_MODO_ENSAIO=1`, e
diz na resposta que está em ensaio. A diferença importa: um atalho de
desenvolvimento que parece produção é como um teste verde que mente.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import smtplib
from email.message import EmailMessage
from typing import Protocol

ASSUNTO = "Seu código de acesso"


def corpo(codigo: str, entidade: str, minutos: int) -> str:
    return (
        f"Seu código de acesso é {codigo}.\n\n"
        f"Ele vale por {minutos} minutos e serve para abrir o cadastro de "
        f"execução de sentença disponibilizado por {entidade}.\n\n"
        "Se não foi você que pediu este código, ignore esta mensagem: sem o "
        "código ninguém abre o cadastro.\n\n"
        "Não responda a esta mensagem.\n"
    )


class Remetente(Protocol):
    def enviar(
        self, destino: str, codigo: str, entidade: str, minutos: int
    ) -> None: ...


class ParaArquivo:
    """Escreve em `<raiz>/codigos_enviados.log`. Desenvolvimento apenas."""

    def __init__(self, raiz: pathlib.Path) -> None:
        self.caminho = raiz / "codigos_enviados.log"

    def enviar(
        self, destino: str, codigo: str, entidade: str, minutos: int
    ) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        agora = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        with open(self.caminho, "a", encoding="utf-8") as fh:
            fh.write(f"{agora}\t{entidade}\t{destino}\t{codigo}\n")


class PorSmtp:
    def __init__(
        self,
        host: str,
        porta: int,
        usuario: str,
        senha: str,
        remetente: str,
    ) -> None:
        self.host = host
        self.porta = porta
        self.usuario = usuario
        self.senha = senha
        self.remetente = remetente

    def enviar(
        self, destino: str, codigo: str, entidade: str, minutos: int
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = ASSUNTO
        msg["From"] = self.remetente
        msg["To"] = destino
        msg.set_content(corpo(codigo, entidade, minutos))
        # 465 é SMTPS do primeiro byte; 587 começa em claro e sobe para TLS.
        # Mandar STARTTLS no 465 falha, e não mandar no 587 passa a senha em
        # claro — por isso a porta decide, e não uma opção a mais.
        if self.porta == 465:
            with smtplib.SMTP_SSL(self.host, self.porta, timeout=20) as s:
                if self.usuario:
                    s.login(self.usuario, self.senha)
                s.send_message(msg)
            return
        with smtplib.SMTP(self.host, self.porta, timeout=20) as s:
            s.starttls()
            if self.usuario:
                s.login(self.usuario, self.senha)
            s.send_message(msg)
