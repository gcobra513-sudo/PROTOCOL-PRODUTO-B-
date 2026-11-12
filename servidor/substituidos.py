"""
O rol de substituídos de cada ação coletiva — a porta que faltava.

O motor pergunta, desde o primeiro dia, se a pessoa consta do rol da ação. E
desde o primeiro dia ninguém respondia: nenhum caminho do produto gravava o
fato, e por isso nada chegava a `PODE` (auditoria de 10/11/2026, item 1).
Quem tem o rol é o SINDICATO, que foi quem ajuizou a ação. Este módulo é a
entrada dele.

NÃO CONFUNDIR COM `rol.py`, que é o rol de quem ENTRA no portal. Aqui é a
lista que acompanha a petição inicial de uma coletiva.

QUATRO REGRAS, e cada uma existe porque o contrário dela afirma o que não
se sabe:

1. **O rol é de UMA ação.** Cada envio diz de qual, e só responde por ela.

2. **Ausência só é resposta quando o sindicato declara que a lista é o rol
   INTEIRO.** "Fora do rol" tem consequência — o motor barra, ou manda
   esperar o STJ. Quem não aparece numa lista parcial não está fora: não se
   sabe, e a resposta continua sendo `FALTA`.

3. **Só fica guardado quem é da base.** O rol de uma coletiva traz quem saiu
   do sindicato, quem morreu, quem nunca foi desta entidade. O CPF dessas
   pessoas é contado e descartado: guardá-lo seria guardar dado de quem a
   entidade não declarou atender — a mesma recusa de
   `documentos_do_sindicato`.

4. **Quem entra na base DEPOIS do envio fica sem resposta**, até o rol ser
   enviado de novo. É o custo da regra 3, e é o lado certo de errar: a
   pessoa nunca foi comparada com a lista.

A RESPOSTA É DECLARADA, NÃO CONFERIDA. Entra pelo arquivo que um gestor
enviou, e ninguém a comparou com os autos. O motor diz isso em nota
(`nucleo/motor.py`), e nada sai como `PODE` sem a ação estar homologada por
advogado.

O ARQUIVO (`rol_de_substituidos.jsonl`) é a autoridade, uma linha por ato:
`enviado` ou `retirado`. Vale o último ato de cada ação.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
from dataclasses import dataclass

from nucleo import leitura

from . import acervo, deposito, documentos, validacao

ARQUIVO = "rol_de_substituidos.jsonl"

ENVIADO = "enviado"
RETIRADO = "retirado"


class RolIlegivel(ValueError):
    """O arquivo não serve como rol. A mensagem é para o gestor ler."""


@dataclass(frozen=True)
class Lido:
    """O que o arquivo trouxe, antes de cruzar com a base."""

    #: CPFs que fecham o dígito, sem repetir.
    cpfs: frozenset[str]
    #: Linhas (ou ocorrências, no PDF) sem CPF que feche. Contadas e
    #: mostradas: são pessoas do rol que este envio NÃO vai reconhecer.
    invalidas: int


@dataclass(frozen=True)
class Plano:
    """O que este envio muda — e é isto que o gestor vê antes de confirmar."""

    acao: str
    #: A lista VALE como completa: foi declarada assim E foi lida inteira.
    completo: bool
    #: O que o gestor declarou. Difere de `completo` quando há linha
    #: ilegível — e a tela precisa dizer por que a declaração não valeu.
    declarado_completo: bool
    #: Da base E da lista.
    constam: tuple[str, ...]
    #: Da base, fora de uma lista declarada completa. Vazio se parcial.
    nao_constam: tuple[str, ...]
    #: Da base, fora de uma lista parcial: continuam sem resposta.
    sem_resposta: int
    #: Da lista, fora da base: contados, não guardados.
    fora_da_base: int
    invalidas: int


def _e_pdf(corpo: bytes, nome: str) -> bool:
    return corpo[:5] == b"%PDF-" or nome.lower().endswith(".pdf")


def ler_arquivo(corpo: bytes, nome: str) -> Lido:
    """Os CPFs que o arquivo traz. Planilha (CSV, .xlsx) ou PDF com texto.

    A PLANILHA PRECISA DE COLUNA DE CPF. Rol só com nome e matrícula existe,
    e não entra: casar por nome é adivinhar, com o direito de alguém.

    NO PDF só vale CPF escrito por extenso (`000.000.000-00`) e que feche o
    dígito. Onze algarismos soltos podem ser outra coisa.
    """
    if _e_pdf(corpo, nome):
        texto, _ = documentos.extrair_texto(corpo)
        if len(texto.strip()) < documentos.MINIMO_DE_CARACTERES:
            raise RolIlegivel(
                f"{nome} não tem texto que a máquina leia: é imagem de "
                f"scanner ou foto. Envie o rol em planilha (Excel ou CSV), "
                f"com uma coluna de CPF."
            )
        achados = [a for a in leitura.ler(texto) if a.tipo == "cpf"]
        bons = frozenset(a.valor for a in achados
                         if a.confianca == leitura.CERTO)
        ruins = sum(1 for a in achados if a.confianca != leitura.CERTO)
    else:
        pessoas, problemas = acervo.ler_bytes(corpo, nome)
        if not pessoas:
            raise RolIlegivel(
                problemas[0] if problemas
                else f"{nome} não trouxe nenhuma linha"
            )
        bons = frozenset(p.cpf for p in pessoas
                         if validacao.cpf_valido(p.cpf))
        ruins = sum(1 for p in pessoas if not validacao.cpf_valido(p.cpf))
    if not bons:
        # Um rol vazio, declarado completo, poria a base inteira fora dele.
        raise RolIlegivel(
            f"{nome} não trouxe nenhum CPF válido. No PDF o CPF precisa "
            f"estar escrito como 000.000.000-00; na planilha, numa coluna "
            f"chamada CPF."
        )
    return Lido(cpfs=bons, invalidas=ruins)


def planejar(lido: Lido, base: set[str], *, acao: str,
             completo: bool) -> Plano:
    """Cruza a lista com a base. Não grava nada.

    "COMPLETA" SÓ VALE SE A LISTA FOI LIDA INTEIRA. CPF que começa com zero,
    guardado no Excel como número, perde o zero e chega com dez dígitos —
    cerca de um em cada dez. A linha não é reconhecida, e a pessoa dela, que
    está no rol, seria dada como fora dele. Com uma linha ilegível que seja,
    qualquer ausente pode ser ela: ninguém é dado como fora.
    """
    base = {validacao.so_digitos(c) for c in base if c}
    constam = sorted(base & lido.cpfs)
    resto = sorted(base - lido.cpfs)
    declarado = bool(completo)
    completo = declarado and lido.invalidas == 0
    return Plano(
        acao=acao,
        completo=completo,
        declarado_completo=declarado,
        constam=tuple(constam),
        nao_constam=tuple(resto) if completo else (),
        sem_resposta=0 if completo else len(resto),
        fora_da_base=len(lido.cpfs - base),
        invalidas=lido.invalidas,
    )


def _agora() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def gravar(pasta_entidade: pathlib.Path, plano: Plano, *, quem: str,
           arquivo: str, sha256: str) -> dict:
    """Acrescenta o envio, com fsync. Quem chama segura a trava do
    apagamento: o plano foi cruzado com uma base, e ela não pode mudar entre
    o cruzamento e esta linha."""
    registro = {
        "ato": ENVIADO,
        "quando": _agora(),
        "acao": plano.acao,
        "completo": plano.completo,
        "declarado_completo": plano.declarado_completo,
        "constam": list(plano.constam),
        "nao_constam": list(plano.nao_constam),
        "fora_da_base": plano.fora_da_base,
        "invalidas": plano.invalidas,
        "arquivo": arquivo,
        "sha256": sha256,
        "quem": quem,
    }
    deposito.anexar_com_fsync(
        pasta_entidade / ARQUIVO,
        json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return registro



def enviar(pasta_entidade: pathlib.Path, lido: Lido, *, acao: str,
           completo: bool, base_de, quem: str, arquivo: str,
           sha256: str) -> Plano:
    """Cruza com a base DE AGORA e grava, com o apagamento parado.

    `base_de()` é chamada DENTRO da trava, e é isso que fecha a corrida: a
    prévia cruzou o rol com a base de um instante antes, e quem pediu para
    sair nesse intervalo voltaria ao arquivo — com o CPF e uma afirmação
    sobre ela. O plano que vale é o desta hora, e é ele que volta.
    """
    with deposito.travada(pasta_entidade, deposito.TRAVA_DO_APAGAMENTO):
        plano = planejar(lido, base_de(), acao=acao, completo=completo)
        gravar(pasta_entidade, plano, quem=quem, arquivo=arquivo,
               sha256=sha256)
    return plano


def retirar(pasta_entidade: pathlib.Path, acao: str, *, quem: str) -> bool:
    """Desfaz o rol desta ação. `False` se não havia rol a retirar."""
    with deposito.travada(pasta_entidade, deposito.TRAVA_DO_APAGAMENTO):
        if acao not in vigentes(pasta_entidade):
            return False
        deposito.anexar_com_fsync(
            pasta_entidade / ARQUIVO,
            json.dumps({"ato": RETIRADO, "quando": _agora(), "acao": acao,
                        "quem": quem}, ensure_ascii=False,
                       sort_keys=True) + "\n",
        )
    return True


def _linhas(pasta_entidade: pathlib.Path) -> list[str]:
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        return []
    return caminho.read_text(encoding="utf-8").splitlines()


def vigentes(pasta_entidade: pathlib.Path) -> dict[str, dict]:
    """ação -> o envio que vale hoje. Linha ilegível é pulada."""
    valem: dict[str, dict] = {}
    for bruta in _linhas(pasta_entidade):
        try:
            registro = json.loads(bruta)
        except json.JSONDecodeError:
            continue
        if not isinstance(registro, dict) or not registro.get("acao"):
            continue
        if registro.get("ato") == ENVIADO:
            valem[str(registro["acao"])] = registro
        elif registro.get("ato") == RETIRADO:
            valem.pop(str(registro["acao"]), None)
    return valem


def por_cpf(pasta_entidade: pathlib.Path
            ) -> dict[str, tuple[tuple[str, bool], ...]]:
    """cpf -> ((ação, consta?), ...), na forma que `motor.Fatos` recebe.

    Quem não aparece aqui NÃO TEM RESPOSTA para ação nenhuma — e isso é
    diferente de "não consta".
    """
    saida: dict[str, dict[str, bool]] = {}
    for acao, registro in sorted(vigentes(pasta_entidade).items()):
        for cpf in registro.get("constam") or ():
            saida.setdefault(str(cpf), {})[acao] = True
        for cpf in registro.get("nao_constam") or ():
            saida.setdefault(str(cpf), {}).setdefault(acao, False)
    return {cpf: tuple(sorted(respostas.items()))
            for cpf, respostas in saida.items()}


def de_cpf(pasta_entidade: pathlib.Path, cpf: str
           ) -> tuple[tuple[str, bool], ...]:
    return por_cpf(pasta_entidade).get(validacao.so_digitos(cpf), ())


def resumo(pasta_entidade: pathlib.Path, base: set[str]) -> dict[str, dict]:
    """ação -> o que o painel mostra do rol dela. Só contagens.

    `sem_resposta` é contado contra a base DE HOJE: é quem entrou depois do
    envio, mais quem ficou de fora de uma lista parcial. É o número que diz
    ao gestor que vale enviar o rol de novo.
    """
    base = {validacao.so_digitos(c) for c in base if c}
    saida: dict[str, dict] = {}
    for acao, registro in vigentes(pasta_entidade).items():
        constam = set(registro.get("constam") or ()) & base
        nao = set(registro.get("nao_constam") or ()) & base
        saida[acao] = {
            "enviado_em": str(registro.get("quando", "")),
            "arquivo": str(registro.get("arquivo", "")),
            "completo": bool(registro.get("completo")),
            "declarado_completo": bool(registro.get("declarado_completo")),
            "constam": len(constam),
            "nao_constam": len(nao),
            "sem_resposta": len(base - constam - nao),
            "fora_da_base": int(registro.get("fora_da_base") or 0),
            "invalidas": int(registro.get("invalidas") or 0),
        }
    return saida


def remover_pessoa(pasta_entidade: pathlib.Path, cpf: str) -> int:
    """Tira esta pessoa de TODAS as linhas. Para o apagamento a pedido.

    Inclusive das linhas de envios já substituídos: elas não respondem mais
    nada, mas continuam guardando o CPF dela e uma afirmação sobre ela. Os
    outros ficam como estavam, e a linha que não der para interpretar fica
    byte a byte.
    """
    caminho = pasta_entidade / ARQUIVO
    digitos = validacao.so_digitos(cpf)
    if not caminho.is_file() or not digitos:
        return 0
    guardadas: list[str] = []
    mexidas = 0
    for bruta in _linhas(pasta_entidade):
        try:
            registro = json.loads(bruta)
        except json.JSONDecodeError:
            guardadas.append(bruta)
            continue
        if not isinstance(registro, dict):
            guardadas.append(bruta)
            continue
        achou = False
        for lista in ("constam", "nao_constam"):
            antes = registro.get(lista)
            if isinstance(antes, list) and digitos in antes:
                registro[lista] = [c for c in antes if c != digitos]
                achou = True
        if not achou:
            guardadas.append(bruta)
            continue
        mexidas += 1
        guardadas.append(json.dumps(registro, ensure_ascii=False,
                                    sort_keys=True))
    if not mexidas:
        return 0
    tmp = caminho.with_suffix(caminho.suffix + ".parcial")
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                 deposito.MODO_ARQUIVO)
    try:
        os.write(fd, "".join(l + "\n" for l in guardadas).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(caminho)
    return mexidas
