#!/usr/bin/env python3
"""
O e-mail só sai para o servidor de e-mail CERTO.

O que passa por essa conexão é o código de acesso de um filiado e a senha da
conta de envio. Ao ensaiar a implantação (13/11/2026), o servidor entregou os
dois a um servidor de e-mail cujo certificado vinha de uma autoridade que a
máquina não conhecia — sem erro, sem aviso. O motivo: `smtplib`, sem um
contexto dado por quem chama, cifra a conexão mas NÃO confere quem está do
outro lado. Cifrar sem conferir protege de quem só escuta, e não de quem se
põe no meio.

O QUE ESTES TESTES FIXAM, contra um servidor SMTP de verdade (local):

1. Certificado de autoridade desconhecida: não entrega, e a senha não sai.
2. Certificado bom, mas de OUTRO nome: não entrega.
3. Certificado bom do nome certo: entrega — a trava não fechou a porta.
4. O caminho da porta 465 confere do mesmo jeito.

E, do mesmo ensaio: quando o envio falhava, a pessoa lia "código enviado" e
só o log sabia. `Vigiado` guarda o resultado de cada envio para `/saude` ler.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import smtplib
import ssl
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import remetente  # noqa: E402
from tests.smtp_de_teste import (  # noqa: E402
    ServidorSmtp, autoridade, certificado)

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


class _ConfiandoEm:
    """Faz a máquina confiar numa AC de teste, do jeito que o OpenSSL lê —
    sem dar ao código de produção um parâmetro que só o teste usaria."""

    def __init__(self, ac: pathlib.Path) -> None:
        self.ac = ac

    def __enter__(self) -> None:
        self.antes = os.environ.get("SSL_CERT_FILE")
        os.environ["SSL_CERT_FILE"] = str(self.ac)

    def __exit__(self, *_: object) -> None:
        if self.antes is None:
            os.environ.pop("SSL_CERT_FILE", None)
        else:
            os.environ["SSL_CERT_FILE"] = self.antes


def _tentar(host: str, porta: int) -> Exception | None:
    correio = remetente.PorSmtp(host, porta, "usuario", "senha-que-nao-pode-vazar",
                                "portal@exemplo.invalid")
    try:
        correio.enviar("fulana@exemplo.invalid", "123456", "Sindicato Tal", 15)
    except Exception as exc:  # noqa: BLE001
        return exc
    return None


def _pasta() -> pathlib.Path:
    pasta = pathlib.Path(tempfile.mkdtemp(prefix="remetente-"))
    autoridade(pasta, "conhecida")
    autoridade(pasta, "desconhecida")
    certificado(pasta, "conhecida", "certo", "localhost")
    certificado(pasta, "conhecida", "outro-nome", "smtp.outro.invalid")
    certificado(pasta, "desconhecida", "de-fora", "localhost")
    return pasta


def t_nao_entrega_a_certificado_de_autoridade_desconhecida():
    pasta = _pasta()
    srv = ServidorSmtp(pasta / "de-fora.crt", pasta / "de-fora.key")
    try:
        with _ConfiandoEm(pasta / "conhecida.crt"):
            erro = _tentar("localhost", srv.porta)
    finally:
        srv.fechar()
        shutil.rmtree(pasta)
    checa(isinstance(erro, ssl.SSLCertVerificationError),
          f"esperava recusa por certificado, veio {erro!r}")
    checa(not srv.mensagens,
          "o código de acesso foi ENTREGUE a um servidor de autoridade "
          "desconhecida")
    checa(not srv.autenticou,
          "a senha do envio foi mandada a um servidor de autoridade "
          "desconhecida")


def t_nao_entrega_a_certificado_de_outro_nome():
    pasta = _pasta()
    srv = ServidorSmtp(pasta / "outro-nome.crt", pasta / "outro-nome.key")
    try:
        with _ConfiandoEm(pasta / "conhecida.crt"):
            erro = _tentar("localhost", srv.porta)
    finally:
        srv.fechar()
        shutil.rmtree(pasta)
    checa(isinstance(erro, ssl.SSLCertVerificationError),
          f"esperava recusa pelo nome do certificado, veio {erro!r}")
    checa(not srv.mensagens and not srv.autenticou,
          "entregou a um servidor cujo certificado é de OUTRO nome")


def t_entrega_a_certificado_certo():
    """A trava não pode fechar a porta: com o certificado certo, chega."""
    pasta = _pasta()
    srv = ServidorSmtp(pasta / "certo.crt", pasta / "certo.key")
    try:
        with _ConfiandoEm(pasta / "conhecida.crt"):
            erro = _tentar("localhost", srv.porta)
    finally:
        srv.fechar()
        shutil.rmtree(pasta)
    checa(erro is None, f"não entregou a um servidor certo: {erro!r}")
    checa(len(srv.mensagens) == 1 and "123456" in srv.mensagens[0],
          f"a mensagem não chegou inteira: {srv.mensagens}")
    checa(srv.autenticou, "não se identificou ao servidor certo")


def t_a_porta_465_confere_do_mesmo_jeito():
    """465 é outro caminho no código (TLS do primeiro byte). Abrir a porta
    465 num teste pede privilégio; então aqui se olha O CONTEXTO que o
    caminho entrega à conexão — é ele que decide se confere."""
    visto: dict = {}

    class Espia(smtplib.SMTP_SSL):
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            visto["contexto"] = kwargs.get("context")
            raise ConnectionRefusedError("espia: não conecta")

    original = smtplib.SMTP_SSL
    smtplib.SMTP_SSL = Espia  # type: ignore[misc]
    try:
        _tentar("localhost", 465)
    finally:
        smtplib.SMTP_SSL = original  # type: ignore[misc]
    ctx = visto.get("contexto")
    checa(isinstance(ctx, ssl.SSLContext)
          and ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname,
          "na porta 465 a conexão sai sem conferir o certificado")


# ------------------------------------------------- a frase que a pessoa lê


def t_a_mensagem_do_codigo_fala_do_portal_do_sindicato():
    """O texto dizia "cadastro de execução de sentença": é a hipótese do
    Produto A (só executar). Aqui a pessoa entra num portal do SINDICATO, e
    quem recebe este e-mail pode ser filiado ou gestor."""
    texto = remetente.corpo("123456", "Sindicato Tal", 15)
    baixo = texto.lower()
    checa("123456" in texto and "Sindicato Tal" in texto and "15" in texto,
          f"falta o código, o sindicato ou o prazo: {texto!r}")
    for proibida in ("execução", "sentença", "escritório", "lote",
                     "peticionamento", "protocolo"):
        checa(proibida not in baixo,
              f"a mensagem do código diz {proibida!r}: {texto!r}")
    checa("portal" in baixo, f"não diz para que serve o código: {texto!r}")


# ------------------------------------------- o envio parado tem de aparecer


class _Quebrado:
    """Um correio que falha do jeito que se manda."""

    def __init__(self) -> None:
        self.erro: Exception | None = None
        self.enviadas = 0

    def _vai(self) -> None:
        if self.erro is not None:
            raise self.erro
        self.enviadas += 1

    def enviar(self, *a: object) -> None:
        self._vai()

    def enviar_mensagem(self, *a: object) -> None:
        self._vai()

    def conferir(self) -> None:
        self._vai()


def t_o_envio_que_falha_fica_marcado_ate_um_envio_dar_certo():
    """Visto no ensaio: o envio falhava, a pessoa lia "código enviado", e só
    o log sabia. A falha tem de ficar num estado que `/saude` possa ler."""
    dentro = _Quebrado()
    vigia = remetente.Vigiado(dentro)
    checa(vigia.estado() == "conferindo",
          f"antes de qualquer tentativa disse {vigia.estado()!r}")
    vigia.conferir()
    checa(vigia.estado() == "ok", f"conexão boa e disse {vigia.estado()!r}")

    dentro.erro = ConnectionRefusedError("fora do ar")
    try:
        vigia.enviar("a@exemplo.invalid", "1", "S", 15)
        checa(False, "a falha do envio foi ENGOLIDA pelo vigia")
    except ConnectionRefusedError:
        pass
    checa(vigia.estado() == "falhando",
          f"o envio falhou e o estado é {vigia.estado()!r}")

    # A CONEXÃO VOLTAR NÃO LIMPA UMA ENTREGA QUE FALHOU: há provedor que
    # aceita a conta e recusa a mensagem (remetente não verificado), e aí a
    # conferência daria "ok" para sempre com os códigos sem sair.
    dentro.erro = None
    vigia.conferir()
    checa(vigia.estado() == "falhando",
          "a conferência da conexão apagou uma falha de ENTREGA")
    vigia.enviar_mensagem("a@exemplo.invalid", "assunto", "corpo")
    checa(vigia.estado() == "ok",
          f"um envio deu certo e o estado é {vigia.estado()!r}")

    dentro.erro = ssl.SSLCertVerificationError("certificado")
    try:
        vigia.conferir()
    except Exception:  # noqa: BLE001
        checa(False, "conferir() levantou: quem chama é um fio de fundo")
    checa(vigia.estado() == "falhando",
          "a conexão não fecha e o estado não diz")


def t_endereco_recusado_nao_e_envio_parado():
    """Um e-mail velho numa linha do rol é rotina, e é problema DAQUELE
    endereço. Se pintasse a saúde de vermelho, o alarme tocaria todo dia e
    ninguém mais olharia para ele."""
    dentro = _Quebrado()
    vigia = remetente.Vigiado(dentro)
    vigia.conferir()
    dentro.erro = smtplib.SMTPRecipientsRefused(
        {"velho@exemplo.invalid": (550, b"nao existe")})
    try:
        vigia.enviar("velho@exemplo.invalid", "1", "S", 15)
    except smtplib.SMTPRecipientsRefused:
        pass
    checa(vigia.estado() == "ok",
          f"um endereço recusado virou envio parado: {vigia.estado()!r}")


def t_conferir_abre_a_conexao_sem_mandar_mensagem():
    """A conferência é para saber ANTES do primeiro filiado. Ela se
    identifica (é onde a senha errada aparece) e não manda nada."""
    pasta = _pasta()
    bom = ServidorSmtp(pasta / "certo.crt", pasta / "certo.key")
    ruim = ServidorSmtp(pasta / "de-fora.crt", pasta / "de-fora.key")
    try:
        with _ConfiandoEm(pasta / "conhecida.crt"):
            remetente.PorSmtp("localhost", bom.porta, "usuario", "senha",
                              "portal@exemplo.invalid").conferir()
            vigia = remetente.Vigiado(remetente.PorSmtp(
                "localhost", ruim.porta, "usuario", "senha",
                "portal@exemplo.invalid"))
            vigia.conferir()
    finally:
        bom.fechar()
        ruim.fechar()
        shutil.rmtree(pasta)
    checa(bom.autenticou and not bom.mensagens,
          f"a conferência não se identificou, ou mandou mensagem: "
          f"{bom.autenticou}, {bom.mensagens}")
    checa(not ruim.autenticou,
          "a conferência mandou a senha a um servidor de certificado ruim")
    checa(vigia.estado() == "falhando",
          f"certificado ruim e o estado é {vigia.estado()!r}")


def t_conferir_em_fundo_nao_empilha():
    """`/saude` não exige sessão. Se cada chamada abrisse uma conexão com o
    servidor de e-mail, um anônimo faria o portal martelar o provedor."""
    dentro = _Quebrado()
    vigia = remetente.Vigiado(dentro)
    for _ in range(50):
        fio = vigia.conferir_em_fundo(intervalo=300)
        if fio is not None:
            fio.join(timeout=5)
    checa(dentro.enviadas == 1,
          f"50 pedidos de conferência viraram {dentro.enviadas} conexões")
    fio = vigia.conferir_em_fundo(intervalo=0)
    if fio is not None:
        fio.join(timeout=5)
    checa(dentro.enviadas == 2, "vencido o intervalo, não conferiu de novo")


TESTES = [
    t_nao_entrega_a_certificado_de_autoridade_desconhecida,
    t_nao_entrega_a_certificado_de_outro_nome,
    t_entrega_a_certificado_certo,
    t_a_porta_465_confere_do_mesmo_jeito,
    t_a_mensagem_do_codigo_fala_do_portal_do_sindicato,
    t_o_envio_que_falha_fica_marcado_ate_um_envio_dar_certo,
    t_endereco_recusado_nao_e_envio_parado,
    t_conferir_abre_a_conexao_sem_mandar_mensagem,
    t_conferir_em_fundo_nao_empilha,
]


def main() -> int:
    print("=" * 70)
    print("REMETENTE — o e-mail só sai para o servidor de e-mail certo")
    print("=" * 70)
    for teste in TESTES:
        antes = len(falhas)
        try:
            teste()
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{teste.__name__}: levantou "
                          f"{type(exc).__name__}: {exc}")
            print(f"  FALHA  {teste.__name__}")
        else:
            if len(falhas) > antes:
                print(f"  FALHA  {teste.__name__}")
    print("-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
