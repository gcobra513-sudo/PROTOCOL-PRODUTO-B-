"""
Em quais ações esta pessoa participa.

A ETAPA QUE LIGA TUDO. A ação coletiva alcança uma CATEGORIA, num PERÍODO.
Os comprovantes de contribuição provam o PERÍODO DE FILIAÇÃO. Cruzar os dois
responde a pergunta que o filiado faz primeiro — *de quais ações eu faço
parte?* — e só depois vem *e o que eu posso fazer nelas?*.

TRÊS DECISÕES DE DESENHO, e nenhuma é óbvia:

**Devolve a INTERSEÇÃO, não só sim ou não.** Quem foi filiada de 2005 a 2006
participa de uma ação que cobre 2003 a 2008 — mas só pelas parcelas daqueles
dois anos. Filiação parcial é participação parcial, e é dessa interseção que
o valor sai depois. Responder só "sim" perderia a informação que mais
importa para a conta.

**Cargo que não casa é INDETERMINADO, não "não participa".** "Auditor Fiscal"
e "Auditor-Fiscal da Receita Federal do Brasil" são a mesma pessoa escrita de
dois jeitos. Dizer "você não participa" por diferença de grafia é tirar
direito de alguém por causa de um hífen. Só se recusa quando o cargo casa
com uma categoria DIFERENTE e conhecida.

**`filiado_ate` vazio conta até hoje.** É resposta, não omissão: a pessoa
continua filiada. Tratá-lo como desconhecido tiraria da conta justamente
quem está lá hoje.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass

from . import entendimentos as ent

PARTICIPA = "PARTICIPA"
NAO_PARTICIPA = "NAO_PARTICIPA"
INDETERMINADO = "INDETERMINADO"

#: Ordem de leitura: o que a pessoa tem vem antes do que ela não tem.
ORDEM = {PARTICIPA: 0, INDETERMINADO: 1, NAO_PARTICIPA: 2}

#: Categorias conhecidas e como elas aparecem escritas por aí. Serve para
#: dois fins opostos e igualmente importantes: casar a mesma carreira escrita
#: de jeitos diferentes, e RECONHECER uma carreira diferente — porque só aí
#: dá para dizer "não participa" com segurança.
#:
#: Crescer esta tabela é o trabalho normal de quem opera o produto. Enquanto
#: um cargo não estiver aqui, ele é INDETERMINADO, nunca recusado.
CATEGORIAS: dict[str, tuple[str, ...]] = {
    "auditor-fiscal da receita federal do brasil": (
        "auditor fiscal da receita federal do brasil",
        "auditor fiscal da receita federal",
        "auditora fiscal da receita federal do brasil",
        "auditora fiscal da receita federal",
        "auditor fiscal da receita federal do brasil afrfb",
        "afrfb",
        "auditor fiscal do tesouro nacional",
        "fiscal de tributos federais",
    ),
    "analista tributario da receita federal do brasil": (
        "analista tributario da receita federal",
        "analista tributario da receita federal do brasil",
        "tecnico da receita federal",
        "atrfb",
    ),
}


@dataclass(frozen=True)
class Filiado:
    """O que se precisa saber da pessoa para dizer de quais ações ela faz
    parte. Nada além disto — cadastro completo é outra coisa."""

    cpf: str = ""
    cargo: str = ""
    situacao: str = ""
    #: AAAA-MM. Vem dos comprovantes de contribuição.
    filiado_desde: str = ""
    #: AAAA-MM, ou VAZIO para "ainda filiada".
    filiado_ate: str = ""
    #: Consta do rol de substituídos? `None` é "não se sabe".
    no_rol: bool | None = None


@dataclass(frozen=True)
class Participacao:
    acao: str
    rotulo: str
    estado: str
    #: A interseção entre a filiação e o período da ação, em AAAA-MM. Vazia
    #: quando não participa ou quando não dá para saber.
    inicio: str = ""
    fim: str = ""
    motivos: tuple[str, ...] = ()
    falta: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.estado == PARTICIPA

    @property
    def meses(self) -> int:
        """Quantos meses de participação. É a base do cálculo, depois."""
        if not (self.inicio and self.fim):
            return 0
        ai, mi = (int(x) for x in self.inicio.split("-"))
        af, mf = (int(x) for x in self.fim.split("-"))
        return (af - ai) * 12 + (mf - mi) + 1


def _plano(texto: str) -> str:
    """Minúsculo, sem acento, sem pontuação, espaços colapsados."""
    sem = "".join(
        c for c in unicodedata.normalize("NFD", str(texto or ""))
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^\w\s]", " ", sem).lower().split())


def _categoria_de(cargo: str) -> str | None:
    """A categoria canônica deste cargo, ou None se não for reconhecido.

    None NÃO significa "outra categoria": significa que não sabemos. A
    diferença é o que impede o sistema de recusar alguém por causa de uma
    grafia que a tabela ainda não conhece.
    """
    plano = _plano(cargo)
    if not plano:
        return None
    for canonica, variacoes in CATEGORIAS.items():
        if plano == canonica or plano in (_plano(v) for v in variacoes):
            return canonica
    return None


def _competencia(valor: str) -> tuple[int, int] | None:
    m = re.match(r"^(\d{4})-(0[1-9]|1[0-2])$", str(valor or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _texto(c: tuple[int, int]) -> str:
    return f"{c[0]:04d}-{c[1]:02d}"


def cruzar(
    filiado: Filiado,
    acao: ent.AcaoColetiva,
    hoje: dt.date | None = None,
) -> Participacao:
    """Esta pessoa participa desta ação? E, se participa, de que pedaço dela?"""
    hoje = hoje or dt.date.today()
    motivos: list[str] = []
    falta: list[str] = []
    rotulo = acao.rotulo

    if not acao.esta_homologado:
        falta.append("homologação da ação por advogado")
        motivos.append(
            f"{rotulo}: a ação ainda não foi homologada — o catálogo prepara, "
            f"quem assina é gente"
        )
        return Participacao(acao.id, rotulo, INDETERMINADO, falta=tuple(falta),
                            motivos=tuple(motivos))

    # ---- a categoria ----
    da_acao = _categoria_de(acao.categoria) or _plano(acao.categoria)
    da_pessoa = _categoria_de(filiado.cargo)
    if da_pessoa is None:
        falta.append("confirmar a carreira desta pessoa")
        motivos.append(
            f"o cargo {filiado.cargo!r} não foi reconhecido. Pode ser a mesma "
            f"carreira escrita de outro jeito — e recusar por causa disso "
            f"seria tirar direito por grafia"
            if filiado.cargo.strip() else
            "a pessoa não informou o cargo, e é ele que define a categoria"
        )
    elif da_pessoa != da_acao:
        return Participacao(
            acao.id, rotulo, NAO_PARTICIPA,
            motivos=(
                f"esta ação alcança a categoria {acao.categoria!r}, e o cargo "
                f"informado é de outra carreira ({filiado.cargo})",
            ),
        )

    # ---- o período ----
    inicio_acao = _competencia(acao.periodo_inicio)
    fim_acao = _competencia(acao.periodo_fim)
    if not (inicio_acao and fim_acao):
        falta.append(f"o período coberto por {rotulo}")
        motivos.append(f"{rotulo}: a ação não declara o período que cobre")
        return Participacao(acao.id, rotulo, INDETERMINADO,
                            motivos=tuple(motivos), falta=tuple(falta))

    desde = _competencia(filiado.filiado_desde)
    if desde is None:
        falta.append("os comprovantes de contribuição, que provam desde "
                     "quando a pessoa é filiada")
        motivos.append(
            "não se sabe desde quando esta pessoa é filiada, e é isso que "
            "decide de quais ações ela faz parte"
        )
        return Participacao(acao.id, rotulo, INDETERMINADO,
                            motivos=tuple(motivos), falta=tuple(falta))

    # Vazio é resposta: ainda filiada, logo conta até hoje.
    ate = _competencia(filiado.filiado_ate) or (hoje.year, hoje.month)

    comum_inicio = max(desde, inicio_acao)
    comum_fim = min(ate, fim_acao)
    if comum_inicio > comum_fim:
        quando = ("saiu antes de a ação começar"
                  if ate < inicio_acao else
                  "entrou depois de a ação acabar")
        return Participacao(
            acao.id, rotulo, NAO_PARTICIPA,
            motivos=(
                f"a filiação ({_texto(desde)} a {_texto(ate)}) não tem mês em "
                f"comum com o período da ação ({acao.periodo_inicio} a "
                f"{acao.periodo_fim}): {quando}",
            ),
        )

    # ---- o rol, e só quando a ação o exige ----
    if acao.exige_rol:
        if filiado.no_rol is False:
            return Participacao(
                acao.id, rotulo, NAO_PARTICIPA,
                inicio=_texto(comum_inicio), fim=_texto(comum_fim),
                motivos=(
                    "esta ação tem rol de substituídos e esta pessoa não "
                    "consta dele",
                ),
            )
        if filiado.no_rol is None:
            falta.append(f"o rol de substituídos de {rotulo}")
            motivos.append(
                f"{rotulo} tem rol de substituídos, e não se sabe se esta "
                f"pessoa consta dele"
            )

    estado = INDETERMINADO if falta else PARTICIPA
    if estado == PARTICIPA:
        motivos.append(
            f"filiada de {_texto(desde)} a {_texto(ate)}, e a ação cobre "
            f"{acao.periodo_inicio} a {acao.periodo_fim}"
        )
    return Participacao(
        acao.id, rotulo, estado,
        inicio=_texto(comum_inicio), fim=_texto(comum_fim),
        motivos=tuple(motivos), falta=tuple(falta),
    )


def participacoes(
    filiado: Filiado,
    catalogo: ent.Catalogo,
    hoje: dt.date | None = None,
) -> list[Participacao]:
    """Todas as ações do catálogo, avaliadas para esta pessoa.

    Devolve TODAS, inclusive as que ela não participa: quem opera precisa
    saber por que alguém ficou de fora tanto quanto precisa saber quem
    entrou. Lista só com as positivas esconde o trabalho de corrigir
    cadastro, que é metade do produto.
    """
    achadas = [cruzar(filiado, a, hoje=hoje) for a in catalogo.acoes]
    return sorted(achadas, key=lambda p: (ORDEM[p.estado], p.acao))
