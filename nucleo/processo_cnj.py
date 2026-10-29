"""Validação do número único de processo (Res. CNJ 65/2008).

Existe porque **o número do processo de origem é o dado mais crítico da
entrada**. Com títulos individuais, é ele que amarra o filiado ao seu título:
é o que o DataJud consulta para descobrir o juízo que decidiu e o rito
herdado. Número errado = título não levantado = caso parado.

E é um campo que as pessoas digitam errado com frequência, porque é longo e
tem pontuação. A boa notícia é que ele **tem dígito verificador**, então erro
de digitação é detectável na origem — no momento em que a pessoa preenche o
formulário, e não três semanas depois.

Formato: NNNNNNN-DD.AAAA.J.TR.OOOO  (20 dígitos)

    NNNNNNN  sequencial por unidade de origem e por ano
    DD       dígito verificador
    AAAA     ano do ajuizamento
    J        segmento do Judiciário (4 = Justiça Federal)
    TR       tribunal (01 = TRF1)
    OOOO     unidade de origem

O verificador é ISO 7064 MOD 97-10: concatena-se
NNNNNNN+AAAA+J+TR+OOOO+"00", toma-se o resto da divisão por 97, e o dígito
é 98 menos esse resto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SEGMENTO_JUSTICA_FEDERAL = "4"
TRIBUNAL_TRF1 = "01"

# Unidades de origem da Justiça Federal da 1ª Região, por UF, pelos dois
# primeiros dígitos de OOOO. Serve para pegar número de outro tribunal que
# por acaso passou no dígito verificador.
_PREFIXOS_TRF1 = {
    "30": "AC", "31": "AP", "32": "AM", "33": "BA", "34": "DF",
    "35": "GO", "36": "MA", "37": "MT", "39": "PA", "40": "PI",
    "41": "RO", "42": "RR", "43": "TO",
}


@dataclass(frozen=True)
class NumeroProcesso:
    sequencial: str
    verificador: str
    ano: str
    segmento: str
    tribunal: str
    origem: str

    @property
    def digitos(self) -> str:
        return (
            self.sequencial + self.verificador + self.ano
            + self.segmento + self.tribunal + self.origem
        )

    @property
    def formatado(self) -> str:
        return (
            f"{self.sequencial}-{self.verificador}.{self.ano}."
            f"{self.segmento}.{self.tribunal}.{self.origem}"
        )

    @property
    def e_justica_federal(self) -> bool:
        return self.segmento == SEGMENTO_JUSTICA_FEDERAL

    @property
    def e_trf1(self) -> bool:
        return self.e_justica_federal and self.tribunal == TRIBUNAL_TRF1

    @property
    def uf_provavel(self) -> str:
        """UF pela unidade de origem. Vazio se não reconhecer."""
        return _PREFIXOS_TRF1.get(self.origem[:2], "") if self.e_trf1 else ""


def so_digitos(v: str) -> str:
    return re.sub(r"\D", "", str(v or ""))


def calcular_verificador(
    sequencial: str, ano: str, segmento: str, tribunal: str, origem: str
) -> str:
    """ISO 7064 MOD 97-10, na ordem que a Res. CNJ 65/2008 define."""
    base = f"{sequencial}{ano}{segmento}{tribunal}{origem}00"
    return f"{98 - (int(base) % 97):02d}"


def decompor(valor: str) -> NumeroProcesso:
    """Quebra o número em partes. Levanta ValueError se não tiver 20 dígitos."""
    d = so_digitos(valor)
    if len(d) != 20:
        raise ValueError(
            f"número de processo deve ter 20 dígitos, veio com {len(d)}: {valor!r}"
        )
    return NumeroProcesso(
        sequencial=d[0:7],
        verificador=d[7:9],
        ano=d[9:13],
        segmento=d[13],
        tribunal=d[14:16],
        origem=d[16:20],
    )


def conferir(valor: str, *, exigir_trf1: bool = False) -> list[str]:
    """Devolve a lista de problemas. Lista vazia = número íntegro.

    Não levanta: devolve motivos nominais, para o formulário mostrar à pessoa
    e para a triagem registrar na quarentena.
    """
    d = so_digitos(valor)
    if not d:
        return ["número de processo vazio"]
    if len(d) != 20:
        return [
            f"deve ter 20 dígitos (tem {len(d)}). Formato: "
            f"NNNNNNN-DD.AAAA.J.TR.OOOO"
        ]

    p = decompor(d)
    problemas: list[str] = []

    esperado = calcular_verificador(p.sequencial, p.ano, p.segmento, p.tribunal, p.origem)
    if p.verificador != esperado:
        problemas.append(
            f"dígito verificador inválido: veio {p.verificador}, esperado "
            f"{esperado} — provavelmente erro de digitação"
        )

    ano = int(p.ano)
    if not (1990 <= ano <= 2100):
        problemas.append(f"ano implausível: {p.ano}")

    if exigir_trf1:
        if not p.e_justica_federal:
            problemas.append(
                f"não é Justiça Federal (segmento {p.segmento}; "
                f"esperado {SEGMENTO_JUSTICA_FEDERAL})"
            )
        elif not p.e_trf1:
            problemas.append(
                f"é Justiça Federal mas não TRF1 (tribunal {p.tribunal}; "
                f"esperado {TRIBUNAL_TRF1})"
            )
        elif not p.uf_provavel:
            # Não é erro fatal: pode ser unidade nova. Mas vale sinalizar.
            problemas.append(
                f"unidade de origem {p.origem} não reconhecida entre as do TRF1"
            )
    return problemas


def valido(valor: str, *, exigir_trf1: bool = False) -> bool:
    return not conferir(valor, exigir_trf1=exigir_trf1)


def normalizar(valor: str) -> str:
    """Devolve só os 20 dígitos, como o DataJud espera na consulta."""
    d = so_digitos(valor)
    if len(d) != 20:
        raise ValueError(f"não normalizável: {valor!r} tem {len(d)} dígitos")
    return d
