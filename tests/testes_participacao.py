#!/usr/bin/env python3
"""
O cruzamento: em quais ações esta pessoa participa.

É A ETAPA QUE LIGA TUDO. A ação coletiva alcança uma CATEGORIA, num PERÍODO.
Os comprovantes de contribuição provam o PERÍODO DE FILIAÇÃO. Cruzar os dois
responde a pergunta que o filiado faz primeiro — *de quais ações eu faço
parte?* — e só depois vem *e o que eu posso fazer nelas?*.

TRÊS COISAS QUE ESTE MÓDULO FAZ DIFERENTE DO ÓBVIO, e cada uma tem teste:

**1. Devolve a INTERSEÇÃO, não só sim ou não.** Quem foi filiada de 2005 a
2006 participa de uma ação que cobre 2003 a 2008 — mas só pelas parcelas
daqueles dois anos. Filiação parcial é participação parcial, e é dessa
interseção que o valor sai depois. Responder só "sim" perderia a informação
que mais importa para a conta.

**2. Cargo que não casa é INDETERMINADO, não "não participa".** "Auditor
Fiscal" e "Auditor-Fiscal da Receita Federal do Brasil" são a mesma pessoa
escrita de dois jeitos. Dizer "você não participa" por diferença de grafia é
tirar direito de alguém por causa de um hífen.

**3. Ação não homologada não decide nada.** O catálogo prepara; quem assina
é advogado.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import entendimentos, participacao  # noqa: E402

#: A pasta inteira, como o produto carrega: as grafias de cargo de TODAS as
#: carreiras conhecidas, e só as ações das categorias contratadas. É o que
#: permite reconhecer o Analista Tributário como OUTRA carreira em vez de
#: pedir para confirmar a dele.
CATEGORIAS = RAIZ / "config" / "categorias"


def acervo() -> entendimentos.Catalogo:
    return entendimentos.carregar_categorias(CATEGORIAS)
HOJE = dt.date(2026, 10, 30)

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def gifa(**trocas) -> entendimentos.AcaoColetiva:
    """A GIFA do catálogo real, homologada, com ajustes pontuais."""
    base = acervo().homologando(("GIFA-2006",)).de("GIFA-2006")
    import dataclasses
    return dataclasses.replace(base, **trocas) if trocas else base


def filiado(**trocas) -> participacao.Filiado:
    base = dict(
        cpf="11144477735",
        cargo="Auditor-Fiscal da Receita Federal do Brasil",
        situacao="aposentado",
        filiado_desde="1992-05",
        filiado_ate="",
        no_rol=None,
    )
    base.update(trocas)
    return participacao.Filiado(**base)


# ------------------------------------------------------------- o período

def teste_filiacao_que_cobre_a_acao_inteira():
    secao("o período")
    p = participacao.cruzar(filiado(), gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.PARTICIPA,
          f"{p.estado}: {p.motivos}")
    checa((p.inicio, p.fim) == ("2003-01", "2008-12"),
          f"a interseção devia ser o período inteiro da ação: "
          f"{p.inicio} a {p.fim}")
    print(f"  ok     filiada desde 1992 participa de 2003-01 a 2008-12")


def teste_filiacao_parcial_e_participacao_parcial():
    """O teste que define o desenho. Quem entrou no meio participa só do que
    viveu — e é essa interseção que o valor vai usar."""
    p = participacao.cruzar(
        filiado(filiado_desde="2005-04", filiado_ate="2006-11"),
        gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.PARTICIPA, f"{p.estado}: {p.motivos}")
    checa((p.inicio, p.fim) == ("2005-04", "2006-11"),
          f"interseção errada: {p.inicio} a {p.fim}")
    print("  ok     filiada de 2005-04 a 2006-11 participa só desse pedaço")


def teste_um_mes_em_comum_ainda_e_participacao():
    p = participacao.cruzar(
        filiado(filiado_desde="2008-12", filiado_ate="2009-06"),
        gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.PARTICIPA, f"{p.estado}: {p.motivos}")
    checa((p.inicio, p.fim) == ("2008-12", "2008-12"), f"{p.inicio} a {p.fim}")
    print("  ok     um mês em comum basta")


def teste_filiacao_que_termina_antes_nao_participa():
    p = participacao.cruzar(
        filiado(filiado_desde="1995-01", filiado_ate="2002-12"),
        gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.NAO_PARTICIPA, f"{p.estado}")
    checa(any("per" in m.lower() for m in p.motivos),
          f"o motivo não fala do período: {p.motivos}")
    print("  ok     saiu antes de a ação começar: não participa")


def teste_filiacao_que_comeca_depois_nao_participa():
    p = participacao.cruzar(filiado(filiado_desde="2015-01"), gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.NAO_PARTICIPA, f"{p.estado}: {p.motivos}")
    print("  ok     entrou depois de a ação acabar: não participa")


def teste_ainda_filiada_conta_ate_hoje():
    """`filiado_ate` vazio é resposta: a pessoa continua filiada. Tratá-lo
    como desconhecido tiraria da conta justamente quem está lá hoje."""
    p = participacao.cruzar(
        filiado(filiado_desde="2007-01", filiado_ate=""), gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.PARTICIPA, f"{p.estado}: {p.motivos}")
    checa((p.inicio, p.fim) == ("2007-01", "2008-12"), f"{p.inicio} a {p.fim}")
    print("  ok     ainda filiada conta até hoje, limitada pelo fim da ação")


def teste_sem_data_de_filiacao_e_indeterminado():
    """Não saber não é não participar."""
    p = participacao.cruzar(filiado(filiado_desde=""), gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.INDETERMINADO, f"{p.estado}")
    checa(p.falta != (), "disse INDETERMINADO sem dizer o que falta")
    print(f"  ok     sem data de filiação: INDETERMINADO, falta {p.falta}")


# ------------------------------------------------------------- a categoria

def teste_cargo_escrito_de_outro_jeito_ainda_casa():
    secao("a categoria")
    for variacao in (
        "Auditor Fiscal da Receita Federal",
        "AUDITOR-FISCAL DA RECEITA FEDERAL DO BRASIL",
        "auditora fiscal da receita federal do brasil",
    ):
        p = participacao.cruzar(filiado(cargo=variacao), gifa(), acervo(), hoje=HOJE)
        checa(p.estado == participacao.PARTICIPA,
              f"{variacao!r} não casou com a categoria: {p.estado} {p.motivos}")
    print("  ok     acento, hífen, caixa e gênero não separam a mesma pessoa")


def teste_cargo_de_outra_categoria_nao_participa():
    p = participacao.cruzar(
        filiado(cargo="Analista Tributário da Receita Federal"),
        gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.NAO_PARTICIPA, f"{p.estado}: {p.motivos}")
    checa(any("categoria" in m.lower() for m in p.motivos),
          f"o motivo não fala de categoria: {p.motivos}")
    print("  ok     outra carreira não participa, e o motivo diz por quê")


def teste_cargo_irreconhecivel_e_indeterminado_nao_recusa():
    """A regra que protege o filiado: cargo que não casa com nada pode ser
    variação de nomenclatura que a gente não conhece. Recusar seria tirar
    direito por causa de grafia."""
    p = participacao.cruzar(
        filiado(cargo="Servidor do Poder Executivo Federal"), gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.INDETERMINADO,
          f"recusou em vez de perguntar: {p.estado} {p.motivos}")
    print("  ok     cargo desconhecido vira pergunta, não recusa")


def teste_sem_cargo_e_indeterminado():
    p = participacao.cruzar(filiado(cargo=""), gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.INDETERMINADO, f"{p.estado}")
    print("  ok     sem cargo, INDETERMINADO")


# ----------------------------------------------------------------- o rol

def teste_acao_que_exige_rol_e_pessoa_fora_dele():
    secao("o rol")
    p = participacao.cruzar(
        filiado(no_rol=False), gifa(exige_rol=True), acervo(), hoje=HOJE)
    checa(p.estado != participacao.PARTICIPA,
          "disse que participa estando fora do rol de uma ação que o exige")
    print(f"  ok     fora do rol de ação que o exige: {p.estado}")


def teste_acao_que_exige_rol_sem_saber_e_indeterminado():
    p = participacao.cruzar(
        filiado(no_rol=None), gifa(exige_rol=True), acervo(), hoje=HOJE)
    checa(p.estado == participacao.INDETERMINADO, f"{p.estado}")
    checa(any("rol" in f.o_que.lower() for f in p.falta),
          f"não disse que falta o rol: {p.falta}")
    print("  ok     ação exige rol e não sabemos: INDETERMINADO")


def teste_acao_sem_rol_nao_pergunta_pelo_rol():
    """A GIFA do catálogo não exige rol. Perguntar à toa manda o sindicato
    atrás de uma lista que ninguém precisa."""
    p = participacao.cruzar(filiado(no_rol=None), gifa(), acervo(), hoje=HOJE)
    checa(p.estado == participacao.PARTICIPA, f"{p.estado}: {p.motivos}")
    checa(not any("rol" in f.o_que.lower() for f in p.falta),
          f"pediu o rol de uma ação que não o exige: {p.falta}")
    print("  ok     ação sem rol não pede rol")


# ------------------------------------------------------------ homologação

def teste_acao_nao_homologada_nao_decide_nada():
    secao("homologação")
    crua = acervo().de("GIFA-2006")   # homologado = N
    p = participacao.cruzar(filiado(), crua, acervo(), hoje=HOJE)
    checa(p.estado == participacao.INDETERMINADO, f"{p.estado}")
    checa(any("homolog" in f.o_que.lower() for f in p.falta),
          f"não disse que falta homologação: {p.falta}")
    print("  ok     ação não homologada não afirma participação")


# ---------------------------------------------------------- o catálogo todo

def teste_participacoes_percorre_o_catalogo():
    secao("o catálogo inteiro")
    cat = acervo().homologando(("GIFA-2006",))
    todas = participacao.participacoes(filiado(), cat, hoje=HOJE)
    checa(len(todas) == len(cat.acoes),
          f"avaliou {len(todas)} de {len(cat.acoes)} ações")
    checa(all(p.acao for p in todas), "participação sem referência à ação")
    checa(all(p.rotulo for p in todas), "participação sem rótulo legível")
    print(f"  ok     {len(todas)} ação(ões) avaliada(s), todas com rótulo")


def teste_quem_participa_vem_primeiro():
    """Ordem de leitura: o que a pessoa tem vem antes do que ela não tem."""
    cat = acervo().homologando(("GIFA-2006",))
    todas = participacao.participacoes(filiado(), cat, hoje=HOJE)
    estados = [p.estado for p in todas]
    checa(estados == sorted(estados, key=participacao.ORDEM.get),
          f"ordem errada: {estados}")
    print("  ok     participa primeiro, depois indeterminado, depois não")


TESTES.extend([
    teste_filiacao_que_cobre_a_acao_inteira,
    teste_filiacao_parcial_e_participacao_parcial,
    teste_um_mes_em_comum_ainda_e_participacao,
    teste_filiacao_que_termina_antes_nao_participa,
    teste_filiacao_que_comeca_depois_nao_participa,
    teste_ainda_filiada_conta_ate_hoje,
    teste_sem_data_de_filiacao_e_indeterminado,
    teste_cargo_escrito_de_outro_jeito_ainda_casa,
    teste_cargo_de_outra_categoria_nao_participa,
    teste_cargo_irreconhecivel_e_indeterminado_nao_recusa,
    teste_sem_cargo_e_indeterminado,
    teste_acao_que_exige_rol_e_pessoa_fora_dele,
    teste_acao_que_exige_rol_sem_saber_e_indeterminado,
    teste_acao_sem_rol_nao_pergunta_pelo_rol,
    teste_acao_nao_homologada_nao_decide_nada,
    teste_participacoes_percorre_o_catalogo,
    teste_quem_participa_vem_primeiro,
])


def main() -> int:
    print("=" * 70)
    print("PARTICIPAÇÃO — em quais ações esta pessoa participa")
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
