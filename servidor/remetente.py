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
import logging
import pathlib
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from typing import Protocol

log = logging.getLogger("protocol.remetente")

ASSUNTO = "Seu código de acesso"


def corpo(codigo: str, entidade: str, minutos: int) -> str:
    # "PORTAL", E NÃO "CADASTRO DE EXECUÇÃO DE SENTENÇA". A frase antiga era
    # a hipótese do Produto A (só executar) escrita num e-mail do B: aqui o
    # código abre o portal do sindicato, para o filiado e para o gestor, e
    # o que cada um pode fazer lá dentro não é este e-mail que diz.
    return (
        f"Seu código de acesso ao portal ({entidade}) é {codigo}.\n\n"
        f"Ele vale por {minutos} minutos.\n\n"
        "Se não foi você que pediu este código, ignore esta mensagem: sem o "
        "código ninguém entra em seu nome.\n\n"
        "Não responda a esta mensagem.\n"
    )


class Remetente(Protocol):
    def enviar(
        self, destino: str, codigo: str, entidade: str, minutos: int
    ) -> None: ...

    def enviar_mensagem(
        self, destino: str, assunto: str, corpo: str
    ) -> None:
        """Uma mensagem qualquer, não o código.

        Existe porque o aviso de movimentação não é um código de acesso: ele
        tem assunto e corpo próprios, e espremê-lo no formato do código
        obrigaria a inventar um "código" que não existe.
        """
        ...


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

    def enviar_mensagem(
        self, destino: str, assunto: str, corpo: str
    ) -> None:
        caminho = self.caminho.parent / "mensagens_enviadas.log"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        agora = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        with open(caminho, "a", encoding="utf-8") as fh:
            fh.write(f"=== {agora}\t{destino}\t{assunto}\n{corpo}\n")

    def conferir(self) -> None:
        """Nada a conferir: não há servidor de e-mail do outro lado."""


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
        self._entregar(msg)

    def enviar_mensagem(
        self, destino: str, assunto: str, corpo: str
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = assunto
        msg["From"] = self.remetente
        msg["To"] = destino
        msg.set_content(corpo)
        self._entregar(msg)

    def conferir(self) -> None:
        """Abre a conexão, identifica-se e fecha — sem mandar mensagem.

        É o que permite saber que o envio não funciona ANTES de o primeiro
        filiado pedir um código: certificado que não fecha, senha errada e
        servidor fora do ar aparecem todos aqui.
        """
        with self._conexao() as s:
            s.noop()

    def _entregar(self, msg: EmailMessage) -> None:
        with self._conexao() as s:
            s.send_message(msg)

    def _conexao(self) -> smtplib.SMTP:
        # O CONTEXTO É DADO AQUI, E NÃO É DETALHE. Sem ele, `smtplib` cifra a
        # conexão mas não confere o certificado nem o nome de quem responde
        # (visto ao ensaiar a implantação: o código de acesso e a senha do
        # envio foram entregues a um servidor de autoridade desconhecida, sem
        # erro). O contexto padrão confere os dois contra as autoridades da
        # máquina. Servidor com certificado que não fecha: o envio FALHA —
        # não há opção para seguir assim mesmo, de propósito.
        contexto = ssl.create_default_context()
        # 465 é SMTPS do primeiro byte; 587 começa em claro e sobe para TLS.
        # Mandar STARTTLS no 465 falha, e não mandar no 587 passa a senha em
        # claro — por isso a porta decide, e não uma opção a mais.
        if self.porta == 465:
            s: smtplib.SMTP = smtplib.SMTP_SSL(
                self.host, self.porta, timeout=20, context=contexto
            )
        else:
            s = smtplib.SMTP(self.host, self.porta, timeout=20)
        try:
            if self.porta != 465:
                s.starttls(context=contexto)
            if self.usuario:
                s.login(self.usuario, self.senha)
        except BaseException:
            s.close()
            raise
        return s


class Vigiado:
    """Um remetente que LEMBRA se o envio está funcionando.

    Visto ao ensaiar a implantação: o servidor de e-mail recusava, a pessoa
    lia "código enviado" e nada chegava. A resposta a quem pede não pode
    mudar (um erro ali diria a um anônimo que aquele CPF está no rol), então
    a falha só existia no log — que ninguém lê até o telefone tocar. Aqui
    ela vira um estado, e `/saude` publica o estado.

    DOIS FATOS SEPARADOS, e nenhum apaga o outro:

    - a CONEXÃO: abrir, conferir o certificado, identificar-se. Dá para
      testar sem mandar nada, e por isso se sabe antes do primeiro filiado;
    - a ENTREGA: o último envio de verdade. Há provedor que aceita a conta
      e recusa a mensagem (remetente não verificado, conta em quarentena de
      envio), e aí a conexão está ótima e nenhum código sai. Uma entrega
      que falhou só se limpa com uma entrega que deu certo.

    EM MEMÓRIA, de propósito: é o estado DESTE processo falando com o
    provedor, e o serviço é um processo só. Reiniciou, confere de novo.

    O QUE SAI DAQUI É UMA PALAVRA. Nem contagem, nem horário: `/saude` não
    exige sessão, e um contador que anda a cada envio diria a quem pede um
    código para um CPF alheio se o envio aconteceu — isto é, se o CPF está
    no rol.
    """

    def __init__(self, dentro: Remetente) -> None:
        self._dentro = dentro
        self._trava = threading.Lock()
        self._conexao: bool | None = None
        self._entrega: bool | None = None
        self._conferida_em: float | None = None
        self._conferindo = False

    def estado(self) -> str:
        with self._trava:
            if self._conexao is False or self._entrega is False:
                return "falhando"
            if self._conexao is None and self._entrega is None:
                return "conferindo"
            return "ok"

    def enviar(
        self, destino: str, codigo: str, entidade: str, minutos: int
    ) -> None:
        self._vigiar(
            lambda: self._dentro.enviar(destino, codigo, entidade, minutos))

    def enviar_mensagem(
        self, destino: str, assunto: str, corpo: str
    ) -> None:
        self._vigiar(
            lambda: self._dentro.enviar_mensagem(destino, assunto, corpo))

    def _vigiar(self, mandar) -> None:  # noqa: ANN001
        try:
            mandar()
        except smtplib.SMTPRecipientsRefused:
            # O servidor recusou AQUELE endereço — e-mail velho numa linha
            # do rol, rotina em base de sindicato. Não é o envio parado; se
            # contasse, o alarme tocaria todo dia e deixaria de ser olhado.
            raise
        except Exception as exc:
            self._anotar(entrega=False, erro=exc)
            raise
        self._anotar(entrega=True)

    def conferir(self) -> None:
        """Confere a conexão e GUARDA o resultado. Não levanta: quem chama é
        um fio de fundo, e o resultado é o estado."""
        try:
            self._dentro.conferir()
        except Exception as exc:  # noqa: BLE001
            self._anotar(conexao=False, erro=exc)
        else:
            self._anotar(conexao=True)

    def conferir_em_fundo(self, intervalo: float) -> threading.Thread | None:
        """Confere em outro fio, se a última conferência tem mais de
        `intervalo` segundos e não há uma em curso.

        EM FUNDO porque a conexão pode levar o tempo limite inteiro, e quem
        pergunta a saúde é um monitor com pressa. COM INTERVALO porque quem
        dispara é `/saude`, que não exige sessão: sem ele, um anônimo faria
        o portal martelar o provedor de e-mail.
        """
        agora = time.monotonic()
        with self._trava:
            if self._conferindo:
                return None
            if (self._conferida_em is not None
                    and agora - self._conferida_em < intervalo):
                return None
            self._conferindo = True

        def roda() -> None:
            try:
                self.conferir()
            finally:
                with self._trava:
                    self._conferida_em = time.monotonic()
                    self._conferindo = False

        fio = threading.Thread(target=roda, name="protocol-envio", daemon=True)
        fio.start()
        return fio

    def _anotar(self, *, conexao: bool | None = None,
                entrega: bool | None = None,
                erro: Exception | None = None) -> None:
        with self._trava:
            estava_bem = not (self._conexao is False or self._entrega is False)
            if conexao is not None:
                self._conexao = conexao
            if entrega is not None:
                self._entrega = entrega
                if entrega:
                    # Uma mensagem saiu: a conexão está provada também.
                    self._conexao = True
            esta_bem = not (self._conexao is False or self._entrega is False)
        # UMA LINHA NA VIRADA, e não uma por tentativa: é a linha que quem
        # opera procura no log. Só o TIPO do erro — o texto costuma trazer o
        # endereço de destino.
        if estava_bem and not esta_bem:
            log.error("ENVIO DE E-MAIL FALHANDO (%s): %s",
                      "conexão" if conexao is False else "entrega",
                      type(erro).__name__)
        elif esta_bem and not estava_bem:
            log.info("envio de e-mail voltou a funcionar")


def pelo_ambiente(raiz: pathlib.Path) -> Remetente:
    """O remetente de uma FERRAMENTA, lido do ambiente.

    As ferramentas não chamam `config.carregar()` — ela exige o segredo do
    portão, que elas não usam. Com `PROTOCOL_SMTP_HOST`, é SMTP; sem, é o
    arquivo de desenvolvimento, na raiz de dados.
    """
    import os

    if os.environ.get("PROTOCOL_SMTP_HOST"):
        return PorSmtp(
            os.environ.get("PROTOCOL_SMTP_HOST", ""),
            int(os.environ.get("PROTOCOL_SMTP_PORTA", "587")),
            os.environ.get("PROTOCOL_SMTP_USUARIO", ""),
            os.environ.get("PROTOCOL_SMTP_SENHA", ""),
            os.environ.get("PROTOCOL_SMTP_REMETENTE", ""),
        )
    return ParaArquivo(raiz)
