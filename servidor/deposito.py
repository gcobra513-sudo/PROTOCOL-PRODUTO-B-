"""
A gravação da entrega. É a parte do servidor que não pode errar.

O FORMATO É O MESMO QUE `ferramentas/conferir_entrega.py` JÁ ABRE:

    dados/<entidade>/
      recebidos.jsonl              diário append-only — a verdade
      entrega/
        manifesto.csv              derivado do diário, uma linha por CPF
        52601815906/               pasta com os 11 dígitos do CPF
          procuracao.pdf …
      historico/52601815906/<ts>/  o que um reenvio substituiu

DUAS DECISÕES QUE VALEM A EXPLICAÇÃO:

**O manifesto é derivado, não acumulado.** O diário recebe uma linha por envio
e nunca é reescrito; o manifesto é refeito a partir dele, com o último envio de
cada CPF. Assim um reenvio corrige o cadastro sem deixar duas linhas do mesmo
filiado na planilha que o escritório abre — e sem perder o que foi enviado
antes, que fica no diário e no histórico. É o mesmo desenho do diário de
protocolo que já existe no projeto, pelo mesmo motivo.

**A ordem é diário → arquivos → manifesto, e isso é de propósito.** Uma queda
no meio tem que deixar um estado que grita, não um que engana:

- cair depois do diário e antes dos arquivos deixa linha sem pasta, e o
  verificador reprova dizendo qual arquivo falta. Alto e claro;
- cair antes de refazer o manifesto se resolve sozinho no envio seguinte, e
  `reconstruir_manifesto()` resolve na hora;
- a ordem inversa — arquivos primeiro — deixaria pasta sem linha no manifesto.
  O verificador percorre o manifesto, então essa pasta ficaria **invisível**:
  documentos de uma pessoa no disco e ninguém sabendo que ela se cadastrou.

Entre um erro que aparece e um que não aparece, a gente escolhe o que aparece.
"""

from __future__ import annotations

import contextlib
import csv
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
import pathlib
import secrets
import shutil
from dataclasses import dataclass

from . import validacao
from .entidades import Entidade

DIARIO = "recebidos.jsonl"
MANIFESTO = "manifesto.csv"
TRAVA = ".trava"
PARCIAL = ".parcial"
HISTORICO = "historico"

MODO_PASTA = 0o700
MODO_ARQUIVO = 0o600


@dataclass(frozen=True)
class Recibo:
    protocolo: str
    recebido_em: str
    cpf: str
    entidade: str
    arquivos: dict[str, str]
    substituiu: str

    def para_json(self) -> dict:
        return {
            "protocolo": self.protocolo,
            "recebido_em": self.recebido_em,
            "entidade": self.entidade,
            "arquivos": self.arquivos,
            "substituiu": self.substituiu,
        }


def novo_protocolo(agora: dt.datetime | None = None) -> str:
    agora = agora or dt.datetime.now(dt.UTC)
    return f"PRT-{agora:%Y%m%d}-{secrets.token_hex(4).upper()}"


@contextlib.contextmanager
def _travada(pasta: pathlib.Path):
    """Uma gravação por entidade de cada vez.

    Sem isto, dois envios simultâneos reescrevem o manifesto ao mesmo tempo e
    um dos dois desaparece da planilha — com os arquivos no disco, o que é o
    pior dos dois mundos.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / TRAVA
    fd = os.open(caminho, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def anexar_com_fsync(caminho: pathlib.Path, linha: str) -> None:
    """Escreve e força o disco. Diário que não sobrevive à queda não é diário."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(caminho, os.O_CREAT | os.O_APPEND | os.O_WRONLY, MODO_ARQUIVO)
    try:
        os.write(fd, linha.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def ler_diario(pasta_entidade: pathlib.Path) -> list[dict]:
    caminho = pasta_entidade / DIARIO
    if not caminho.is_file():
        return []
    registros = []
    for numero, linha in enumerate(
        caminho.read_text("utf-8").splitlines(), start=1
    ):
        linha = linha.strip()
        if not linha:
            continue
        try:
            registros.append(json.loads(linha))
        except json.JSONDecodeError:
            # Uma linha truncada por queda no meio da escrita não invalida as
            # outras. Avisamos pelo retorno em vez de derrubar a leitura.
            registros.append({"_ilegivel": numero})
    return registros


def _csv_do_diario(registros: list[dict]) -> str:
    """O manifesto: último envio de cada CPF, na ordem das colunas do contrato."""
    por_cpf: dict[str, dict[str, str]] = {}
    for reg in registros:
        linha = reg.get("linha")
        if not isinstance(linha, dict):
            continue
        cpf = linha.get("id_externo") or ""
        if cpf:
            por_cpf[cpf] = linha
    buffer = io.StringIO(newline="")
    # \r\n porque esta planilha é aberta por gente, no Excel em português.
    escritor = csv.DictWriter(
        buffer,
        fieldnames=list(validacao.COLUNAS),
        extrasaction="ignore",
        lineterminator="\r\n",
    )
    escritor.writeheader()
    for cpf in sorted(por_cpf):
        escritor.writerow({c: por_cpf[cpf].get(c, "") for c in validacao.COLUNAS})
    return buffer.getvalue()


def reconstruir_manifesto(
    entidade: Entidade, raiz: pathlib.Path
) -> pathlib.Path:
    """Refaz `manifesto.csv` a partir do diário. Idempotente, e é o reparo."""
    pasta = entidade.pasta(raiz)
    entrega = entidade.entrega(raiz)
    entrega.mkdir(parents=True, exist_ok=True)
    os.chmod(entrega, MODO_PASTA)
    destino = entrega / MANIFESTO
    tmp = entrega / (MANIFESTO + ".parcial")
    tmp.write_text(_csv_do_diario(ler_diario(pasta)), encoding="utf-8")
    os.chmod(tmp, MODO_ARQUIVO)
    tmp.replace(destino)
    return destino


def depositar(
    entidade: Entidade,
    raiz: pathlib.Path,
    linha: dict[str, str],
    arquivos: dict[str, bytes],
) -> Recibo:
    """Grava um cadastro. A linha e os arquivos já passaram por `validacao`."""
    cpf = validacao.so_digitos(linha["cpf"])
    if len(cpf) != 11:
        # Não é conferência duplicada por acidente: é o CPF que nomeia a pasta.
        # Se ele chegasse vazio aqui, a pasta seria `entrega/`, e o cadastro de
        # uma pessoa viraria o diretório de todos.
        raise ValueError("depositar exige CPF de 11 dígitos")

    pasta = entidade.pasta(raiz)
    entrega = entidade.entrega(raiz)
    protocolo = novo_protocolo()
    agora = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")

    somas = {
        nome: hashlib.sha256(corpo).hexdigest()
        for nome, corpo in sorted(arquivos.items())
    }

    with _travada(pasta):
        # 1. o diário primeiro. Ver o cabeçalho do módulo para o porquê.
        anexar_com_fsync(
            pasta / DIARIO,
            json.dumps(
                {
                    "protocolo": protocolo,
                    "recebido_em": agora,
                    "entidade": entidade.apelido,
                    "linha": linha,
                    "arquivos": somas,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
        )

        # 2. os arquivos, montados de lado e trocados de uma vez.
        montagem = pasta / PARCIAL / protocolo
        if montagem.exists():
            shutil.rmtree(montagem)
        montagem.mkdir(parents=True)
        os.chmod(montagem, MODO_PASTA)
        for nome, corpo in arquivos.items():
            # `nome` só pode ser um dos nomes do contrato: `validacao`
            # recusa qualquer outro antes de chegar aqui.
            alvo = montagem / nome
            alvo.write_bytes(corpo)
            os.chmod(alvo, MODO_ARQUIVO)

        entrega.mkdir(parents=True, exist_ok=True)
        os.chmod(entrega, MODO_PASTA)
        destino = entrega / cpf

        substituiu = ""
        if destino.exists():
            # Reenvio. O anterior vai para o histórico — ninguém perde
            # documento por ter corrigido o próprio cadastro.
            marca = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S")
            guarda = pasta / HISTORICO / cpf / marca
            guarda.parent.mkdir(parents=True, exist_ok=True)
            destino.replace(guarda)
            substituiu = str(guarda.relative_to(pasta))

        montagem.replace(destino)
        with contextlib.suppress(OSError):
            (pasta / PARCIAL).rmdir()

        # 3. o manifesto, refeito do diário.
        reconstruir_manifesto(entidade, raiz)

    return Recibo(
        protocolo=protocolo,
        recebido_em=agora,
        cpf=cpf,
        entidade=entidade.apelido,
        arquivos=somas,
        substituiu=substituiu,
    )


def ja_cadastrado(
    entidade: Entidade, raiz: pathlib.Path, cpf: str
) -> str:
    """O protocolo do último envio deste CPF, ou "" se não houver."""
    digitos = validacao.so_digitos(cpf)
    ultimo = ""
    for reg in ler_diario(entidade.pasta(raiz)):
        linha = reg.get("linha")
        if isinstance(linha, dict) and linha.get("id_externo") == digitos:
            ultimo = str(reg.get("protocolo", ""))
    return ultimo
