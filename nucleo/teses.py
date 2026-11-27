"""
As teses acompanhadas: o que são, quem cada uma alcança, e o que mudou.

O catálogo (`entendimentos.py`) já guardava os temas dos tribunais e as
ações coletivas de cada carreira, e o motor já cruzava cada pessoa com eles.
O que não existia era a pergunta ao contrário: dado um TEMA, quantas pessoas
desta base ele alcança? É a pergunta de quem vai propor a ação — e é o que
permite dizer "o tribunal julgou, e N filiados são alcançados".

TRÊS CUIDADOS, e cada um é uma forma diferente de não prometer:

1. **O número é uma SIMULAÇÃO.** `poderiam` é quantos teriam o caminho
   aberto SE a tese fosse conferida por advogado. A simulação roda sobre uma
   cópia do catálogo e NÃO muda o veredicto de ninguém: para o filiado, a
   resposta continua sendo a de hoje até alguém conferir.

2. **Tema sem tese não alcança ninguém.** Um tema só afetado — o tribunal
   disse que vai julgar — dá `poderiam = 0` mesmo simulado, porque é o motor
   que responde, e ele não apoia ação em tese que não existe.

3. **Novidade tem data.** Só é notícia o que o catálogo registra como
   julgado ou afetado nos últimos `DIAS_DE_NOVIDADE`. A data vem do catálogo,
   que cita a fonte; este módulo não consulta tribunal nenhum.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from . import entendimentos as ent
from . import motor, panorama

#: Por quantos dias um julgamento continua sendo novidade.
DIAS_DE_NOVIDADE = 30


@dataclass(frozen=True)
class Tese:
    id: str
    #: "tema" (entendimento de tribunal) ou "acao" (ação coletiva).
    tipo: str
    rotulo: str
    tribunal: str
    categoria: str
    situacao: str
    #: A data do último evento que o catálogo registra — julgamento, ou, na
    #: falta dele, a afetação. Vazia quando o catálogo não traz.
    data: str
    questao: str
    tese: str
    fonte: str
    #: Um advogado já conferiu (`homologado = "S"` no catálogo)?
    conferida: bool


@dataclass(frozen=True)
class Novidade:
    id: str
    #: "julgado" ou "afetado".
    evento: str
    data: str
    rotulo: str
    tribunal: str


def do_catalogo(catalogo: ent.Catalogo) -> list[Tese]:
    """Tudo o que se acompanha para as carreiras deste catálogo."""
    lista: list[Tese] = []
    for e in catalogo.entendimentos:
        lista.append(Tese(
            id=e.id, tipo="tema", rotulo=e.rotulo, tribunal=e.tribunal,
            categoria=e.categoria, situacao=e.situacao,
            data=e.julgado_em or e.afetado_em, questao=e.questao.strip(),
            tese=e.tese.strip(), fonte=e.fonte, conferida=e.esta_homologado,
        ))
    for a in catalogo.acoes:
        lista.append(Tese(
            id=a.id, tipo="acao", rotulo=a.rotulo, tribunal="",
            categoria=a.categoria, situacao=a.situacao, data="",
            questao="", tese="", fonte=a.fonte, conferida=a.esta_homologado,
        ))
    return lista


def impacto(catalogo: ent.Catalogo, registros, *, lidos_por_cpf=None,
            rol_por_cpf=None, fichas_por_cpf=None) -> dict[str, dict]:
    """id da tese -> {poderiam, dependem, fora}, SE cada uma fosse conferida.

    É O MESMO LAÇO DO PAINEL (`panorama.por_pessoa`), sobre uma CÓPIA do
    catálogo com tudo homologado. Um segundo jeito de avaliar daria um
    segundo número para a mesma pessoa. A cópia morre aqui: o catálogo de
    verdade, e o veredicto que cada um vê, não mudam.
    """
    ids = [t.id for t in do_catalogo(catalogo)]
    conta = {i: {"poderiam": 0, "dependem": 0, "fora": 0} for i in ids}
    simulado = catalogo.homologando(tuple(ids))
    chave = {motor.PODE: "poderiam", motor.FALTA: "dependem",
             motor.NAO_PODE: "fora"}
    for pessoa in panorama.por_pessoa(registros, simulado, lidos_por_cpf,
                                      rol_por_cpf, fichas_por_cpf):
        for o in pessoa.oportunidades:
            if o.referencia in conta:
                conta[o.referencia][chave[o.veredicto]] += 1
    return conta


def novidades(lista: list[Tese], *, hoje: str,
              dias: int = DIAS_DE_NOVIDADE) -> list[Novidade]:
    """O que os tribunais julgaram ou afetaram nos últimos `dias`, da mais
    recente para a mais antiga. Data no futuro não é notícia: é erro de
    catálogo, e anunciá-la seria anunciar um julgamento que não houve."""
    agora = dt.date.fromisoformat(hoje[:10])
    achadas: list[Novidade] = []
    for t in lista:
        if t.tipo != "tema" or t.situacao not in ("julgado", "afetado"):
            continue
        try:
            quando = dt.date.fromisoformat(t.data[:10])
        except ValueError:
            continue
        if dt.timedelta(0) <= agora - quando <= dt.timedelta(days=dias):
            achadas.append(Novidade(id=t.id, evento=t.situacao, data=t.data,
                                    rotulo=t.rotulo, tribunal=t.tribunal))
    return sorted(achadas, key=lambda n: n.data, reverse=True)


def _dia(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if len(iso) >= 10 else ""


def _pessoas(n: int) -> str:
    return "1 pessoa" if n == 1 else f"{n} pessoas"


def frase_da_novidade(n: Novidade, *, sindicato: str, poderiam: int,
                      dependem: int, conferida: bool = False) -> str:
    """A novidade, dita a quem vai propor a ação.

    O TEMA SÓ AFETADO NÃO PROMETE NADA: o tribunal disse que vai julgar, e a
    frase diz quantas pessoas isso pode alcançar — sem "poderiam".
    """
    tema = n.rotulo.split(", ", 1)[-1]
    if n.evento == "afetado":
        return (f"O {n.tribunal} vai julgar o {tema} (afetado em "
                f"{_dia(n.data)}). No {sindicato}, {_pessoas(dependem)} "
                f"{'é' if dependem == 1 else 'são'} da carreira que ele "
                f"alcança. Ainda não há tese em que apoiar ação.")
    frase = (f"O {n.tribunal} julgou o {tema} em {_dia(n.data)}. No "
             f"{sindicato}, {_pessoas(poderiam)} "
             f"{'poderia' if poderiam == 1 else 'poderiam'} entrar com a "
             f"ação e outras {dependem} dependem de alguma conferência.")
    return frase + (" A tese já foi conferida por advogado." if conferida
                    else " A tese ainda não foi conferida por advogado.")
