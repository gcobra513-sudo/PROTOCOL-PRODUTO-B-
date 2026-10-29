"""
O coletor de movimentação — o carrapato.

UMA REGRA DE DESENHO QUE RESOLVE DE GRAÇA UM PROBLEMA DE JURISDIÇÃO: este
módulo toca **só número de processo e movimento**. Sem CPF, sem nome, sem
entidade. Por isso o processo que roda a coleta pode viver em qualquer lugar
— agendador gratuito, máquina de terceiro — sem exportar dado pessoal
nenhum. É a mesma regra do coletor que o DJEN exigiria: empurra, nunca puxa.

O QUE O DATAJUD DÁ E NÃO DÁ, medido em 29/10/2026 e registrado em
`docs/achados_datajud.md`:

  - **65 tribunais**, e o alias sai do próprio número CNJ. Acompanhar não é
    privilégio do TRF1;
  - **o STF não está lá.** `api_publica_stf` devolve index_not_found, e a
    lista oficial não o cita. O STJ está;
  - **22 a 43 s por consulta**, e o custo é por CHAMADA, não por processo —
    daí o agrupamento em lote;
  - **defasagem de ~1 dia**, e só nome e data de movimento. Não é intimação.

POR QUE A TABELA DE ALIASES É EXPLÍCITA, e não `f"api_publica_trf{tr}"`: a
fórmula acerta a Justiça Federal e erra todo o resto. `J=8, TR=07` é o TJDFT,
não "tj07"; `J=8, TR=26` é o TJSP. Fórmula aqui produziria requisição a
índice inexistente com cara de código elegante.
"""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass
from typing import Callable, Iterable


from nucleo import processo_cnj  # noqa: E402

#: Código de tribunal da Justiça Estadual (e da Eleitoral regional) por UF,
#: na ordem alfabética de sigla que a Res. CNJ 65/2008 adota. Conferido
#: contra números conhecidos: TJSP é `8.26`, TJRJ `8.19`, TJDFT `8.07`,
#: TJMG `8.13`.
_UF_POR_CODIGO = {
    "01": "ac", "02": "al", "03": "ap", "04": "am", "05": "ba", "06": "ce",
    "07": "dft", "08": "es", "09": "go", "10": "ma", "11": "mt", "12": "ms",
    "13": "mg", "14": "pa", "15": "pb", "16": "pr", "17": "pe", "18": "pi",
    "19": "rj", "20": "rn", "21": "rs", "22": "ro", "23": "rr", "24": "sc",
    "25": "se", "26": "sp", "27": "to",
}


def _tabela() -> dict[tuple[str, str], str]:
    """(segmento, tribunal) -> alias do DataJud. As 65 entradas medidas."""
    aliases: dict[tuple[str, str], str] = {}

    # J=3 — STJ. O STF seria J=1 e NÃO existe no DataJud.
    aliases[("3", "00")] = "api_publica_stj"

    # J=4 — Justiça Federal, TRF1 a TRF6.
    for n in range(1, 7):
        aliases[("4", f"{n:02d}")] = f"api_publica_trf{n}"

    # J=5 — Justiça do Trabalho: TST em TR=00, TRT1 a TRT24 nos demais.
    aliases[("5", "00")] = "api_publica_tst"
    for n in range(1, 25):
        aliases[("5", f"{n:02d}")] = f"api_publica_trt{n}"

    # J=6 — Justiça Eleitoral: TSE em TR=00. Os TREs têm um único alias
    # genérico `api_publica_tre` na lista oficial, não um por UF.
    aliases[("6", "00")] = "api_publica_tse"
    for codigo in _UF_POR_CODIGO:
        aliases[("6", codigo)] = "api_publica_tre"

    # J=7 — Justiça Militar da União: STM.
    aliases[("7", "00")] = "api_publica_stm"

    # J=8 — Justiça Estadual, um alias por tribunal.
    for codigo, uf in _UF_POR_CODIGO.items():
        aliases[("8", codigo)] = f"api_publica_tj{uf}"

    # J=9 — Justiça Militar Estadual: só MG, RS e SP têm TJM.
    for codigo in ("13", "21", "26"):
        aliases[("9", codigo)] = f"api_publica_tjm{_UF_POR_CODIGO[codigo]}"

    return aliases


ALIASES: dict[tuple[str, str], str] = _tabela()

#: Segmentos que existem na numeração CNJ mas NÃO no DataJud, com o motivo.
#: Dizer "tribunal desconhecido" para um número do STF seria esconder que o
#: problema é institucional, não de digitação.
AUSENTES = {
    "1": "o STF não está no DataJud — a competência do CNJ (CF, art. 103-B, "
         "§4º) alcança os órgãos do Judiciário mas não o Supremo",
    "2": "o CNJ não julga processo",
}

#: Processos por chamada. O custo é por CHAMADA (15–30 s, medido, qualquer
#: que seja o tamanho), então lote grande é a diferença entre viável e
#: inviável: 15 mil processos em série passariam de 100 horas.
POR_LOTE = 100


class TribunalDesconhecido(LookupError):
    """O número não aponta para nenhum tribunal que o DataJud sirva."""


class ErroDeConsulta(RuntimeError):
    """A consulta falhou. NÃO é o mesmo que 'não há movimento novo'."""


@dataclass(frozen=True)
class Movimento:
    numero: str
    grau: str
    data: str
    nome: str

    @property
    def chave(self) -> str:
        """O que identifica um movimento.

        O GRAU entra porque o DataJud devolve G1 e G2 como registros
        separados do mesmo `numeroProcesso`: sem ele, cada coleta
        "descobriria" de novo todos os movimentos do outro grau.
        """
        return f"{self.numero}|{self.grau}|{self.data}|{self.nome}"


def alias_do_numero(numero: str) -> str:
    """O alias do DataJud para este número. Falha fechado.

    A trava é ANTES da requisição, não depois do 404: o número fica na base e
    seria tentado a cada coleta, para sempre.
    """
    digitos = processo_cnj.so_digitos(numero)
    if len(digitos) != 20:
        raise TribunalDesconhecido(
            f"{numero!r} não tem 20 dígitos — não dá para saber o tribunal"
        )
    partes = processo_cnj.decompor(digitos)
    if partes is None:
        raise TribunalDesconhecido(f"{numero!r} não se decompõe")
    chave = (partes.segmento, partes.tribunal)
    if chave in ALIASES:
        return ALIASES[chave]
    if partes.segmento in AUSENTES:
        raise TribunalDesconhecido(
            f"{numero!r}: {AUSENTES[partes.segmento]}"
        )
    raise TribunalDesconhecido(
        f"{numero!r}: segmento {partes.segmento!r} e tribunal "
        f"{partes.tribunal!r} não correspondem a nenhum dos 65 tribunais "
        f"servidos pelo DataJud"
    )


def movimentos_da_fonte(fonte: dict) -> list[Movimento]:
    """Os movimentos de um `_source` do DataJud.

    Movimento sem data ou sem nome é DESCARTADO: com data vazia a chave
    colidiria com outro movimento sem data, e os dois se esconderiam.
    """
    numero = processo_cnj.so_digitos(str(fonte.get("numeroProcesso", "")))
    grau = str(fonte.get("grau") or "?")
    saida: list[Movimento] = []
    for bruto in fonte.get("movimentos") or []:
        data = str(bruto.get("dataHora") or "").strip()
        nome = str(bruto.get("nome") or "").strip()
        if not data or not nome:
            continue
        saida.append(Movimento(numero=numero, grau=grau, data=data, nome=nome))
    return saida


def ler_diario_de_movimentos(
    caminho: pathlib.Path,
) -> list[Movimento]:
    """Os movimentos já coletados, do diário append-only.

    Tolerante a linha corrompida: uma queda no meio da gravação não pode
    impedir a leitura do que já estava lá. O diário é a verdade, e verdade
    parcial é melhor que exceção.
    """
    import json

    if not caminho.is_file():
        return []
    saida: list[Movimento] = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        for m in registro.get("movimentos") or []:
            try:
                saida.append(Movimento(
                    numero=m["numero"], grau=m["grau"],
                    data=m["data"], nome=m["nome"],
                ))
            except (KeyError, TypeError):
                continue
    return saida


def ultimo_por_processo(
    movimentos: Iterable[Movimento],
) -> dict[str, Movimento]:
    """O movimento mais recente de cada número, qualquer que seja o grau.

    É o que a tela do filiado mostra: ele quer saber o que andou, não em que
    instância andou.
    """
    ultimo: dict[str, Movimento] = {}
    for m in movimentos:
        atual = ultimo.get(m.numero)
        if atual is None or m.data > atual.data:
            ultimo[m.numero] = m
    return ultimo


def novidades(
    antes: Iterable[Movimento], agora: Iterable[Movimento]
) -> list[Movimento]:
    """O que apareceu desde a última coleta.

    Só o que ENTROU. Movimento que saiu da lista — o tribunal reclassifica —
    não é novidade: tratar ausência como evento criaria aviso do nada.
    """
    vistos = {m.chave for m in antes}
    return [m for m in agora if m.chave not in vistos]


def _por_alias(numeros: Iterable[str]) -> tuple[dict[str, list[str]], list[str]]:
    grupos: dict[str, list[str]] = {}
    erros: list[str] = []
    vistos: set[str] = set()
    for numero in numeros:
        digitos = processo_cnj.so_digitos(numero)
        # Número repetido na entrada é o caso óbvio: dois filiados na MESMA
        # ação coletiva. Sem isto ele era consultado e expandido duas vezes, e
        # a pessoa recebia dois avisos do mesmo andamento.
        if not digitos or digitos in vistos:
            continue
        vistos.add(digitos)
        try:
            alias = alias_do_numero(digitos)
        except TribunalDesconhecido as e:
            erros.append(str(e))
            continue
        grupos.setdefault(alias, []).append(digitos)
    return grupos, erros


def coletar(
    numeros: Iterable[str],
    consultar: Callable[..., dict] | None = None,
    chave: str = "",
) -> tuple[list[Movimento], list[str]]:
    """Consulta a movimentação dos números dados. Devolve (movimentos, falhas).

    `consultar` é injetável para que a suíte não toque a rede — um teste que
    dependesse do DataJud levaria 22 a 43 s por caso e ficaria vermelho
    exatamente quando o CNJ estivesse fora do ar.

    FALHA NÃO É AUSÊNCIA DE MOVIMENTO. Um tribunal fora do ar devolve falha
    nominal e não derruba os outros; o que ele NÃO faz é deixar o processo
    parecer "nada novo". A promessa do produto é avisar, e falso silêncio é o
    pior defeito possível aqui.
    """
    if consultar is None:
        from ferramentas import conferir_datajud

        consultar = conferir_datajud.consultar_lote
        chave = chave or conferir_datajud.CHAVE_PUBLICA

    grupos, erros = _por_alias(numeros)
    movimentos: list[Movimento] = []
    for alias, lote in sorted(grupos.items()):
        for inicio in range(0, len(lote), POR_LOTE):
            fatia = lote[inicio:inicio + POR_LOTE]
            try:
                achados = consultar(fatia, chave, alias)
            except Exception as e:  # noqa: BLE001
                # Larga a mão SÓ desta fatia. E o erro diz o alias e os
                # números, para que quem lê o relatório saiba o que ficou sem
                # conferir — "falhou" sem dizer o quê é quase silêncio.
                erros.append(
                    f"{alias}: {type(e).__name__}: {e} "
                    f"(processos {', '.join(fatia)})"
                )
                continue
            for numero in fatia:
                for fonte in achados.get(numero) or []:
                    movimentos.extend(movimentos_da_fonte(fonte))
    return movimentos, erros
