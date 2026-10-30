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

**Cargo que não casa é INDETERMINADO, não "não participa".** A mesma
carreira aparece escrita de vários jeitos, e dizer "você não participa" por
diferença de grafia é tirar direito de alguém por causa de um hífen. Só se
recusa quando o cargo casa com uma categoria DIFERENTE e conhecida.

**A tabela de grafias NÃO mora aqui.** Mora no `cargos` de cada arquivo de
`config/categorias/`, e chega por `catalogo.categoria_do_cargo`. Enquanto ela
morava neste módulo, acrescentar uma categoria era mexer no código — e é
assim que a tabela para de crescer. Por isso `cruzar` exige o catálogo: sem
ele não há como saber quais carreiras existem, e adivinhar seria recusar
gente por grafia.

**`filiado_ate` vazio conta até hoje.** É resposta, não omissão: a pessoa
continua filiada. Tratá-lo como desconhecido tiraria da conta justamente
quem está lá hoje.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from . import entendimentos as ent
from . import pendencia

PARTICIPA = "PARTICIPA"
NAO_PARTICIPA = "NAO_PARTICIPA"
INDETERMINADO = "INDETERMINADO"

#: Ordem de leitura: o que a pessoa tem vem antes do que ela não tem.
ORDEM = {PARTICIPA: 0, INDETERMINADO: 1, NAO_PARTICIPA: 2}

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
    #: O que falta, e DE QUEM é cada coisa. O dono é declarado aqui, na
    #: origem, e não deduzido do texto depois: deduzir por palavra na frase
    #: erra calado quando alguém reescreve a frase, e errar aqui é mandar uma
    #: pessoa providenciar o que ela não tem como providenciar.
    falta: tuple[pendencia.Falta, ...] = ()

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


def _competencia(valor: str) -> tuple[int, int] | None:
    m = re.match(r"^(\d{4})-(0[1-9]|1[0-2])$", str(valor or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _texto(c: tuple[int, int]) -> str:
    return f"{c[0]:04d}-{c[1]:02d}"


def cruzar(
    filiado: Filiado,
    acao: ent.AcaoColetiva,
    catalogo: ent.Catalogo,
    hoje: dt.date | None = None,
) -> Participacao:
    """Esta pessoa participa desta ação? E, se participa, de que pedaço dela?

    O CATÁLOGO É OBRIGATÓRIO, e não tem padrão. É dele que vêm as grafias de
    cargo: sem ele, nenhum cargo seria reconhecido e todo mundo viraria
    INDETERMINADO — fail-closed na forma mais inútil possível, a de não
    responder nada a ninguém.
    """
    hoje = hoje or dt.date.today()
    motivos: list[str] = []
    falta: list[str] = []
    rotulo = acao.rotulo

    if not acao.esta_homologado:
        falta.append(pendencia.Falta(
            pendencia.CONFERENCIA, f"a homologação de {rotulo} por advogado"))
        # MESMO TEXTO de `motor._homologacao`, de propósito: as duas
        # conferências são cinto e suspensório, e com textos diferentes a
        # pessoa lia a mesma pendência duas vezes, com duas redações.
        motivos.append(
            f"{rotulo}: ainda não homologado — o motor prepara, quem assina "
            f"é gente"
        )
        return Participacao(acao.id, rotulo, INDETERMINADO, falta=tuple(falta),
                            motivos=tuple(motivos))

    # ---- a categoria ----
    # A ação já carrega a categoria canônica do arquivo que a contém, então
    # a comparação é direta. Normalizar de novo aqui esconderia um arquivo
    # mal declarado, e a autópsia do catálogo é que tem de pegá-lo.
    da_acao = acao.categoria
    da_pessoa = catalogo.categoria_do_cargo(filiado.cargo)
    if da_pessoa is None:
        # DOIS DONOS DIFERENTES, e a diferença importa. Cargo em branco a
        # pessoa pode preencher. Cargo preenchido que a nossa tabela não
        # conhece NÃO é tarefa dela: ela já respondeu, e mandá-la "confirmar a
        # carreira" que informou é justamente o telefonema que a tela existe
        # para evitar.
        falta.append(
            pendencia.Falta(pendencia.CONFERENCIA,
                            "a conferência da carreira informada")
            if filiado.cargo.strip() else
            pendencia.Falta(pendencia.VOCE,
                            "o cargo, que é o que define a categoria")
        )
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
        falta.append(pendencia.Falta(
            pendencia.CONFERENCIA, f"o período coberto por {rotulo}"))
        motivos.append(f"{rotulo}: a ação não declara o período que cobre")
        return Participacao(acao.id, rotulo, INDETERMINADO,
                            motivos=tuple(motivos), falta=tuple(falta))

    desde = _competencia(filiado.filiado_desde)
    if desde is None:
        falta.append(pendencia.Falta(
            pendencia.VOCE, "os comprovantes de contribuição ao sindicato"))
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
            falta.append(pendencia.Falta(
                pendencia.CONFERENCIA, f"o rol de substituídos de {rotulo}"))
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
    achadas = [cruzar(filiado, a, catalogo, hoje=hoje) for a in catalogo.acoes]
    return sorted(achadas, key=lambda p: (ORDEM[p.estado], p.acao))
