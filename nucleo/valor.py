"""
Quanto — e, quase sempre, a recusa de dizer quanto.

É O ÚLTIMO CHECKPOINT DE PROPÓSITO. Dizer "você vai receber R$ 48.000" para
uma auditora aposentada e estar errado não é defeito de software: é dinheiro
prometido a quem já contou com ele, e não se conserta com atualização.

O QUE NÃO EXISTE NO PRODUTO HOJE, e nenhum código resolve:

    a base de cálculo    a ficha financeira da pessoa, mês a mês
    o valor da verba     quanto a verba mandava pagar, em cada período
    o índice             qual correção, a partir de quando, com qual tese

Sem os três, qualquer número seria inventado. Por isso `apurar` começa pela
recusa, e a recusa diz o que falta e DE QUEM É — a mesma divisão da tela do
filiado, porque é a mesma pergunta: o que eu faço para destravar isto?

O QUE DÁ PARA FAZER HOJE, e é a peça que ninguém tem: a PRESCRIÇÃO.
`periodo_apuravel` responde "dos 72 meses em que você participou, quantos
ainda são cobráveis?" — conta de calendário sobre dado que já temos, que
muda o resultado materialmente.

DINHEIRO É `Decimal`, NUNCA `float`. `0.1 + 0.2 != 0.3` em binário, e um
centavo de erro por parcela, em duas mil parcelas, é uma conta que o outro
lado confere e nós não.

E TUDO SAI COM MEMÓRIA. A memória de cálculo é o produto tanto quanto o
número: conta sem memória é conta que o outro lado contesta e que nós não
sabemos defender.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from . import pendencia

APURADO = "APURADO"
FALTA_DADO = "FALTA_DADO"

#: Prazo do Decreto 20.910/1932 contra a Fazenda Pública. PARÂMETRO, não
#: constante no código: o STJ Tema 1.410 trata da prescrição do fundo de
#: direito nas relações de trato sucessivo e está pendente — se ele mudar o
#: prazo, muda-se o argumento, não o motor.
ANOS_PADRAO = 5

#: Centavos. `ROUND_HALF_UP` e não o padrão do Python (`ROUND_HALF_EVEN`):
#: arredondamento bancário é defensável em estatística e surpreendente numa
#: planilha que alguém confere à mão.
CENTAVO = Decimal("0.01")

COMPETENCIA = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class Passo:
    """Uma linha da memória de cálculo."""

    o_que: str
    resultado: str
    fonte: str = ""


def _mes(valor: str) -> tuple[int, int] | None:
    achado = COMPETENCIA.match(str(valor or "").strip())
    return (int(achado.group(1)), int(achado.group(2))) if achado else None


def _texto(c: tuple[int, int]) -> str:
    return f"{c[0]:04d}-{c[1]:02d}"


def _meses_entre(inicio: tuple[int, int], fim: tuple[int, int]) -> int:
    return (fim[0] - inicio[0]) * 12 + (fim[1] - inicio[1]) + 1


def _andar(c: tuple[int, int], passos: int) -> tuple[int, int]:
    total = c[0] * 12 + (c[1] - 1) + passos
    return (total // 12, total % 12 + 1)


@dataclass(frozen=True)
class Periodo:
    """Um intervalo de competências, e o que sobrou dele."""

    inicio: str = ""
    fim: str = ""
    #: Quantos meses o corte da prescrição tirou. É informação para o
    #: filiado: ele participou de um período maior do que o cobrável.
    meses_prescritos: int = 0
    memoria: tuple[Passo, ...] = ()
    falta: tuple[pendencia.Falta, ...] = ()

    @property
    def meses(self) -> int:
        i, f = _mes(self.inicio), _mes(self.fim)
        return _meses_entre(i, f) if i and f and i <= f else 0

    def __bool__(self) -> bool:
        return self.meses > 0

    def competencias(self) -> list[str]:
        i, f = _mes(self.inicio), _mes(self.fim)
        if not (i and f and i <= f):
            return []
        return [_texto(_andar(i, n)) for n in range(_meses_entre(i, f))]


def periodo_apuravel(
    inicio: str,
    fim: str,
    interrompida_em: str,
    anos: int = ANOS_PADRAO,
) -> Periodo:
    """O pedaço do período que ainda é cobrável.

    SÚMULA 85/STJ: na relação de trato sucessivo contra a Fazenda, prescrevem
    as PARCELAS anteriores ao quinquênio, não o fundo de direito. O corte é
    sobre as parcelas, e por isso ele move o início e deixa o fim onde está.

    `interrompida_em` NÃO TEM PADRÃO, e é a decisão mais importante desta
    função. Para a execução de sentença coletiva, a data que interrompe é a
    do ajuizamento DA COLETIVA, não a da execução individual — e confundir as
    duas muda o resultado em anos. Quem sabe qual é não é o software.

    `anos` é parâmetro porque o STJ Tema 1.410 está pendente sobre
    exatamente isto. Prazo cravado no código seria uma mudança de motor
    esperando para acontecer.
    """
    i, f = _mes(inicio), _mes(fim)
    if not (i and f):
        return Periodo(
            falta=(pendencia.Falta(
                pendencia.CONFERENCIA,
                "o período de participação, em competências AAAA-MM",
            ),),
            memoria=(Passo("período recebido", f"{inicio!r} a {fim!r}",
                           "não é competência válida"),),
        )

    corte = _mes(interrompida_em)
    if not corte:
        return Periodo(
            falta=(pendencia.Falta(
                pendencia.CONFERENCIA,
                "a data que interrompeu a prescrição — na execução de "
                "coletiva, o ajuizamento DA AÇÃO COLETIVA",
            ),),
            memoria=(Passo(
                "prescrição",
                "não calculada",
                "sem a data de interrupção não há de onde contar o prazo, e "
                "supor a data erraria o resultado em anos",
            ),),
        )

    limite = _andar(corte, -anos * 12)
    memoria = [
        Passo("período de participação",
              f"{_texto(i)} a {_texto(f)} ({_meses_entre(i, f)} meses)",
              "cruzamento da filiação com o período da ação"),
        Passo(f"corte do prazo de {anos} ano(s)",
              f"nada antes de {_texto(limite)}",
              f"Decreto 20.910/1932 e Súmula 85/STJ: na relação de trato "
              f"sucessivo prescrevem as parcelas anteriores ao quinquênio, "
              f"contado de {_texto(corte)}"),
    ]

    novo_inicio = max(i, limite)
    if novo_inicio > f:
        return Periodo(
            meses_prescritos=_meses_entre(i, f),
            memoria=tuple(memoria + [Passo(
                "resultado", "nenhuma parcela cobrável",
                "todo o período participado é anterior ao prazo")]),
        )

    prescritos = _meses_entre(i, _andar(novo_inicio, -1)) if novo_inicio > i else 0
    memoria.append(Passo(
        "período cobrável",
        f"{_texto(novo_inicio)} a {_texto(f)} "
        f"({_meses_entre(novo_inicio, f)} meses; {prescritos} prescritos)",
        "",
    ))
    # O tema pendente anda junto do resultado: quem ler o número tem de
    # saber que a regra que o produziu pode mudar.
    memoria.append(Passo(
        "a regra pode mudar",
        "STJ Tema 1.410, pendente",
        "trata da prescrição do fundo de direito nas relações de trato "
        "sucessivo em que a Fazenda é devedora",
    ))
    return Periodo(
        inicio=_texto(novo_inicio), fim=_texto(f),
        meses_prescritos=prescritos, memoria=tuple(memoria),
    )


@dataclass(frozen=True)
class Verba:
    """O que a decisão manda pagar, e sobre o quê.

    `homologado` pela mesma razão de todo o resto: nada nominal sai sem
    advogado, e dinheiro menos ainda.
    """

    id: str
    percentual: Decimal = Decimal("0")
    incide_sobre: str = "a base de cálculo declarada na ficha financeira"
    fonte: str = ""
    homologado: str = "N"

    @property
    def esta_homologada(self) -> bool:
        return self.homologado.strip().upper() == "S"


@dataclass(frozen=True)
class Parcela:
    competencia: str
    base: Decimal
    percentual: Decimal
    valor: Decimal


#: O que esta conta NÃO é. Fica junto do número, não no rodapé.
AVISO = (
    "Esta é uma APURAÇÃO PRELIMINAR E BRUTA. Não é o valor a receber: ainda "
    "faltam a correção monetária, os juros, a compensação do que já foi pago "
    "e a retenção de imposto. Nenhum número sai daqui sem um advogado "
    "conferir e assinar."
)


@dataclass(frozen=True)
class Apuracao:
    veredicto: str = FALTA_DADO
    total: Decimal | None = None
    parcelas: tuple[Parcela, ...] = ()
    memoria: tuple[Passo, ...] = ()
    falta: tuple[pendencia.Falta, ...] = ()
    aviso: str = AVISO

    def __bool__(self) -> bool:
        return self.veredicto == APURADO


def apurar(periodo: Periodo, verba: Verba, bases: dict) -> Apuracao:
    """A conta, quando todos os insumos existem. A recusa, quando não.

    **NÃO COMPLETA MÊS QUE FALTA.** Preencher o buraco com a média seria
    inventar — e o número inventado sairia com a nossa assinatura, no meio de
    uma conta correta, sem marca nenhuma. Falta um mês, não há total.

    A PRESCRIÇÃO JÁ VEIO CORTADA no `periodo`: somar primeiro e cortar depois
    produziria, no caminho, um total que inclui parcela prescrita — e alguém
    leria esse número.
    """
    memoria: list[Passo] = list(periodo.memoria)
    falta: list[pendencia.Falta] = list(periodo.falta)

    if not verba.esta_homologada:
        falta.append(pendencia.Falta(
            pendencia.CONFERENCIA,
            f"a homologação da verba {verba.id} por advogado",
        ))
        memoria.append(Passo(
            "verba", f"{verba.id}: não homologada",
            "o catálogo prepara; quem assina é gente",
        ))

    competencias = periodo.competencias()
    if not competencias and not falta:
        falta.append(pendencia.Falta(
            pendencia.CONFERENCIA,
            "um período cobrável — nenhuma parcela sobrou após a prescrição",
        ))

    sem_base = [c for c in competencias if bases.get(c) is None]
    if sem_base:
        mostrar = ", ".join(sem_base[:6]) + (
            f" e mais {len(sem_base) - 6}" if len(sem_base) > 6 else ""
        )
        falta.append(pendencia.Falta(
            pendencia.CONFERENCIA,
            f"a base de cálculo (ficha financeira) de: {mostrar}",
        ))
        memoria.append(Passo(
            "base de cálculo",
            f"faltam {len(sem_base)} de {len(competencias)} competências",
            "mês sem base não se completa com média: o número inventado "
            "sairia no meio de uma conta correta, sem marca nenhuma",
        ))

    negativas = [c for c in competencias
                 if bases.get(c) is not None and Decimal(bases[c]) < 0]
    if negativas:
        falta.append(pendencia.Falta(
            pendencia.CONFERENCIA,
            f"conferir a ficha financeira: base NEGATIVA em "
            f"{', '.join(negativas[:6])}",
        ))
        memoria.append(Passo(
            "base negativa", ", ".join(negativas[:6]),
            "é erro de exportação, não desconto — aceitar reduziria a conta "
            "de alguém em silêncio",
        ))

    if falta:
        return Apuracao(veredicto=FALTA_DADO, memoria=tuple(memoria),
                        falta=tuple(falta))

    parcelas = []
    total = Decimal("0")
    for c in competencias:
        base = Decimal(bases[c])
        bruto = (base * verba.percentual).quantize(CENTAVO, ROUND_HALF_UP)
        parcelas.append(Parcela(competencia=c, base=base,
                                percentual=verba.percentual, valor=bruto))
        total += bruto

    memoria.append(Passo(
        "verba aplicada",
        f"{verba.percentual} sobre {verba.incide_sobre}",
        verba.fonte,
    ))
    memoria.append(Passo(
        "soma das parcelas",
        f"{len(parcelas)} competências, total bruto {total}",
        "sem correção monetária, sem juros, sem compensação, sem imposto",
    ))
    return Apuracao(veredicto=APURADO, total=total,
                    parcelas=tuple(parcelas), memoria=tuple(memoria))
