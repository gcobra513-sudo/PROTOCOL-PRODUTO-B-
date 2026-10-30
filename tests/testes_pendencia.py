#!/usr/bin/env python3
"""
QUEM DESTRAVA CADA PENDÊNCIA — a parte informacional do produto.

POR QUE ISTO É O MIOLO DA TELA DO FILIADO, e não enfeite. A lista de faltas
era texto corrido, tudo no mesmo saco:

    falta: homologação por advogado; os comprovantes de contribuição;
           o rol de substituídos; julgamento do STJ Tema 1.302

Uma pessoa que lê isso liga para o sindicato. Não porque não entendeu, mas
porque não dá para saber o que ELA tem de fazer. E o telefonema é o custo que
o produto promete cortar.

Separado por quem destrava, a mesma lista responde sozinha:

    VOCÊ         manda os comprovantes de contribuição      -> ela age
    EM CONFERÊNCIA   o rol, a homologação                   -> não é com ela
    TRIBUNAL     o julgamento do STJ Tema 1.302             -> ninguém pode
                                                               nada, nem nós

A terceira é a que mais poupa ligação: "esperando o STJ" é resposta completa,
e nenhum telefonema a melhora.

UMA DECISÃO QUE NÃO É ÓBVIA: cargo não reconhecido é **EM CONFERÊNCIA**, não
VOCÊ. A pessoa já respondeu o cargo dela; quem não conhece a grafia é a nossa
tabela. Mandá-la "confirmar a carreira" que ela já informou é justamente o
telefonema que estamos tentando evitar.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import entendimentos, motor, pendencia  # noqa: E402
from nucleo import participacao as part  # noqa: E402

CATEGORIAS = RAIZ / "config" / "categorias"
AFRFB = "Auditor-Fiscal da Receita Federal do Brasil"

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def acervo(homologar: tuple[str, ...] = ()) -> entendimentos.Catalogo:
    return entendimentos.carregar_categorias(CATEGORIAS).homologando(homologar)


def fatos(**trocas) -> motor.Fatos:
    base = dict(
        cpf="11144477735",
        nome="FULANA DE TAL (CADASTRO DE EXEMPLO)",
        cargo=AFRFB,
        situacao="aposentado",
        filiado_desde="2004-01",
        filiado_ate="",
        tem_titulo=None,
        no_rol=None,
        ja_executou=None,
        tem_acao_propria=None,
    )
    base.update(trocas)
    return motor.Fatos(**base)


def todas_as_faltas(f: motor.Fatos, cat=None) -> list[pendencia.Falta]:
    cat = cat if cat is not None else acervo()
    return [x for o in motor.avaliar(f, cat) for x in o.falta]


# ------------------------------------------------------- nenhuma falta é órfã

def teste_toda_falta_tem_dono():
    """A trava estrutural. Uma falta sem dono volta para o saco único, e a
    tela volta a gerar telefonema."""
    secao("nenhuma falta é órfã")
    vistas = 0
    for troca in ({}, {"tem_titulo": True, "no_rol": False},
                  {"tem_titulo": False}, {"filiado_desde": ""},
                  {"cargo": "Cargo Que Ninguém Cadastrou"},
                  {"tem_titulo": True, "no_rol": True, "ja_executou": False,
                   "tem_acao_propria": False}):
        for f in todas_as_faltas(fatos(**troca),
                                 acervo(("GIFA-2006", "STJ-T1169",
                                         "STJ-T1302", "STJ-T1410"))):
            vistas += 1
            checa(f.quem in pendencia.DONOS,
                  f"falta sem dono conhecido: {f.quem!r} / {f.o_que!r}")
            checa(bool(f.o_que.strip()), f"falta sem texto: {f!r}")
    checa(vistas > 10, f"só {vistas} faltas exercitadas; o cenário é fraco")
    print(f"  ok     {vistas} faltas, todas com dono")


def teste_participacao_tambem_declara_o_dono():
    """A etapa 3 produz falta própria, e ela entra na mesma tela."""
    gifa = acervo(("GIFA-2006",)).de("GIFA-2006")
    p = part.cruzar(
        part.Filiado(cargo=AFRFB, filiado_desde=""), gifa, acervo(("GIFA-2006",))
    )
    checa(bool(p.falta), "sem data de filiação não apontou falta nenhuma")
    for f in p.falta:
        checa(f.quem in pendencia.DONOS, f"falta sem dono: {f!r}")
    print(f"  ok     participação: {len(p.falta)} falta(s) com dono")


# ------------------------------------------------------ cada dono, um caso

def teste_comprovante_de_contribuicao_depende_do_filiado():
    """O caso que faz a tela valer: a pessoa pode resolver sozinha."""
    secao("cada dono, um caso")
    faltas = todas_as_faltas(fatos(filiado_desde=""), acervo(("GIFA-2006",)))
    dela = [f for f in faltas if f.quem == pendencia.VOCE]
    checa(any("contribui" in f.o_que.lower() for f in dela),
          f"o comprovante de contribuição não ficou com o filiado: "
          f"{[(f.quem, f.o_que) for f in faltas]}")
    print(f"  ok     sem filiação comprovada: {len(dela)} pendência(s) dela")


def teste_homologacao_depende_da_conferencia():
    """Nada nominal sai sem advogado — e isso não é problema do filiado."""
    faltas = todas_as_faltas(fatos())          # nada homologado
    homologacao = [f for f in faltas if "homologa" in f.o_que.lower()]
    checa(bool(homologacao), "o catálogo não homologado não apontou falta")
    for f in homologacao:
        checa(f.quem == pendencia.CONFERENCIA,
              f"homologação ficou com {f.quem}, e não é com o filiado")
    print(f"  ok     homologação: {len(homologacao)} pendência(s) em "
          f"conferência")


def teste_tema_pendente_depende_do_tribunal():
    """A pendência que nenhum telefonema resolve. O STJ Tema 1.302 está
    afetado com suspensão nacional, e é ele que decide se quem está fora do
    rol pode executar."""
    faltas = todas_as_faltas(
        fatos(tem_titulo=True, no_rol=False, ja_executou=False),
        acervo(("GIFA-2006", "STJ-T1302")),
    )
    do_tribunal = [f for f in faltas if f.quem == pendencia.TRIBUNAL]
    checa(bool(do_tribunal),
          f"fora do rol com o Tema 1.302 pendente não gerou pendência de "
          f"tribunal: {[(f.quem, f.o_que) for f in faltas]}")
    checa(any("1.302" in f.o_que or "1302" in f.o_que for f in do_tribunal),
          f"a pendência não cita o tema: {[f.o_que for f in do_tribunal]}")
    print(f"  ok     fora do rol: {len(do_tribunal)} pendência(s) de tribunal")


def teste_cargo_nao_reconhecido_e_conferencia_nao_tarefa_do_filiado():
    """A decisão que não é óbvia. A pessoa já respondeu o cargo; quem não
    conhece a grafia é a nossa tabela. Devolver isso como tarefa dela é o
    telefonema que a tela existe para evitar."""
    faltas = todas_as_faltas(fatos(cargo="Guarda Municipal de Exemplo"),
                             acervo(("GIFA-2006", "STJ-T1410")))
    carreira = [f for f in faltas if "carreira" in f.o_que.lower()]
    checa(bool(carreira), f"cargo desconhecido não gerou pendência de "
                          f"carreira: {[f.o_que for f in faltas]}")
    for f in carreira:
        checa(f.quem == pendencia.CONFERENCIA,
              f"a carreira ficou com {f.quem}: {f.o_que!r}")
    print(f"  ok     carreira não reconhecida: {len(carreira)} em conferência")


def teste_sem_cargo_nenhum_e_tarefa_do_filiado():
    """E a assimetria: quem NÃO informou o cargo pode informar. Aí é dela."""
    faltas = todas_as_faltas(fatos(cargo=""),
                             acervo(("GIFA-2006", "STJ-T1410")))
    dela = [f for f in faltas if f.quem == pendencia.VOCE]
    checa(any("cargo" in f.o_que.lower() for f in dela),
          f"cargo em branco não virou tarefa do filiado: "
          f"{[(f.quem, f.o_que) for f in faltas]}")
    print("  ok     cargo em branco: tarefa do filiado")


# -------------------------------------------------------------- o agrupamento

def teste_agrupar_junta_por_dono_sem_repetir():
    secao("o agrupamento")
    faltas = (
        pendencia.Falta(pendencia.VOCE, "os comprovantes de contribuição"),
        pendencia.Falta(pendencia.CONFERENCIA, "a homologação por advogado"),
        pendencia.Falta(pendencia.VOCE, "os comprovantes de contribuição"),
        pendencia.Falta(pendencia.TRIBUNAL, "o julgamento do STJ, Tema 1.302"),
    )
    grupos = pendencia.agrupar(faltas)
    checa(grupos[pendencia.VOCE] == ("os comprovantes de contribuição",),
          f"repetiu ou perdeu: {grupos[pendencia.VOCE]}")
    checa(len(grupos[pendencia.CONFERENCIA]) == 1, "conferência errada")
    checa(len(grupos[pendencia.TRIBUNAL]) == 1, "tribunal errado")
    print("  ok     agrupa por dono, sem repetir")


def teste_agrupar_devolve_os_tres_donos_sempre():
    """A tela precisa das três chaves para não ter de adivinhar. Um grupo
    vazio é informação: significa "nada aqui"."""
    grupos = pendencia.agrupar(())
    checa(tuple(grupos) == pendencia.DONOS,
          f"as chaves não são os três donos, na ordem: {tuple(grupos)}")
    checa(all(v == () for v in grupos.values()), "grupo vazio não veio vazio")
    print(f"  ok     sempre as três chaves, na ordem {pendencia.DONOS}")


def teste_agrupar_recusa_dono_desconhecido():
    """Fail-closed: um dono inventado iria para nenhum grupo e a pendência
    desapareceria da tela."""
    try:
        pendencia.agrupar((pendencia.Falta("SEI_LA", "alguma coisa"),))
        checa(False, "aceitou dono desconhecido")
    except ValueError as e:
        checa("SEI_LA" in str(e), f"a mensagem não diz qual: {e}")
        print("  ok     dono desconhecido é recusado, não ignorado")


# ---------------------------------------------------- o texto que a pessoa lê

def teste_cada_dono_tem_titulo_para_o_filiado():
    for dono in pendencia.DONOS:
        titulo = pendencia.TITULOS[dono]
        checa(bool(titulo.strip()), f"{dono} sem título")
        checa(titulo[0].isupper(), f"{dono}: título não começa maiúsculo")
    print("  ok     " + " | ".join(pendencia.TITULOS[d]
                                   for d in pendencia.DONOS))


def teste_nenhum_texto_fala_de_escritorio():
    """REGRA ZERO. Quem fala com o filiado é o SINDICATO. Se um escritório
    existe na relação, ele foi contratado pelo sindicato — isso é contrato,
    não arquitetura, e não entra na tela de ninguém."""
    fonte = (RAIZ / "nucleo" / "pendencia.py").read_text("utf-8")
    textos = list(pendencia.TITULOS.values()) + list(
        pendencia.EXPLICACOES.values()
    )
    for t in textos:
        checa("escritório" not in t.lower() and "escritorio" not in t.lower(),
              f"texto do filiado fala de escritório: {t!r}")
    # E o vocabulário do Produto A não atravessa para cá.
    for proibida in ("lote", "peticion", "pje", "quarentena", "manifesto"):
        checa(proibida not in fonte.lower(),
              f"pendencia.py usa vocabulário do Produto A: {proibida!r}")
    print("  ok     nenhum texto do filiado fala de escritório")


def teste_cada_dono_explica_o_que_esperar():
    """O que corta a ligação não é o rótulo, é a frase seguinte: "não é com
    você" e "não há o que fazer senão esperar" são respostas completas."""
    for dono in pendencia.DONOS:
        texto = pendencia.EXPLICACOES[dono]
        checa(len(texto) > 30, f"{dono}: explicação curta demais: {texto!r}")
    checa("espera" in pendencia.EXPLICACOES[pendencia.TRIBUNAL].lower()
          or "aguard" in pendencia.EXPLICACOES[pendencia.TRIBUNAL].lower(),
          "a explicação do tribunal não diz que é esperar")
    print("  ok     as três explicações dizem o que esperar")


# ------------------------------------- o que a saída real mostrou de errado

def teste_a_mesma_falta_nao_aparece_duas_vezes():
    """Medido na resposta de verdade: "a homologação da GIFA por advogado"
    saía DUAS vezes na mesma oportunidade — `participacao` aponta e
    `_homologacao` aponta de novo. As duas conferências são de propósito
    (cinto e suspensório), mas a pessoa não tem de ler duas vezes."""
    secao("o que a saída real mostrou de errado")
    for o in motor.avaliar(fatos(), acervo()):
        textos = [f.o_que for f in o.falta]
        checa(len(textos) == len(set(textos)),
              f"{o.referencia}: falta repetida -> {textos}")
        checa(len(o.motivos) == len(set(o.motivos)),
              f"{o.referencia}: motivo repetido -> {o.motivos}")
    print("  ok     nenhuma falta nem motivo repetido")


def teste_quem_declarou_nao_e_perguntado_de_novo():
    """O CADASTRO PERGUNTA E NINGUÉM LIA. A pessoa responde "não tenho ação
    própria" no cadastro, e a tela devolvia "saber se já existe ação própria"
    como tarefa dela. Perguntar de novo o que ela acabou de responder é
    exatamente o telefonema que a tela existe para evitar."""
    faltas = todas_as_faltas(fatos(tem_acao_propria=False),
                             acervo(("STJ-T1410",)))
    dela = [f.o_que for f in faltas if f.quem == pendencia.VOCE]
    checa(not any("ação própria" in t for t in dela),
          f"perguntou de novo o que a pessoa já respondeu: {dela}")
    print("  ok     quem respondeu não é perguntado de novo")


def teste_execucao_anterior_declarada_vira_nota_nao_silencio():
    """A ASSIMETRIA QUE PROTEGE. "Não executei" dito pela própria pessoa não
    é a base de execuções: se estiver errado, executar de novo cria dois
    processos para a mesma dívida. Então a resposta dela conta — e vai junto
    uma nota dizendo que foi declarada, não conferida. Aceitar calado seria
    transformar autodeclaração em fato."""
    executar = [o for o in motor.avaliar(
        fatos(tem_titulo=True, no_rol=True, ja_executou=False),
        acervo(("GIFA-2006",)),
    ) if o.trilha == motor.EXECUTAR]
    checa(bool(executar), "nenhuma oportunidade de executar")
    for o in executar:
        checa(any("declarad" in n.lower() for n in o.notas),
              f"{o.referencia}: aceitou a autodeclaração sem nota: {o.notas}")
    # E quando vem de base conferida, a nota não aparece.
    conferido = [o for o in motor.avaliar(
        fatos(tem_titulo=True, no_rol=True, ja_executou=False,
              ja_executou_conferido=True),
        acervo(("GIFA-2006",)),
    ) if o.trilha == motor.EXECUTAR]
    for o in conferido:
        checa(not any("declarad" in n.lower() for n in o.notas),
              f"{o.referencia}: pôs nota de autodeclaração em dado "
              f"conferido: {o.notas}")
    print("  ok     autodeclaração sobre execução vira nota")


def teste_resposta_do_cadastro_vira_booleano():
    """`sim` / `nao` / `nao_sei` do contrato -> True / False / None. O
    `nao_sei` TEM de virar None e não False: são respostas diferentes, e
    tratá-las igual faz o sistema afirmar sobre quem não respondeu."""
    from nucleo import cadastro as conta
    checa(conta.resposta_booleana("sim") is True, "sim não virou True")
    checa(conta.resposta_booleana("nao") is False, "nao não virou False")
    checa(conta.resposta_booleana("nao_sei") is None, "nao_sei não virou None")
    checa(conta.resposta_booleana("") is None, "vazio não virou None")
    checa(conta.resposta_booleana("qualquer") is None, "lixo não virou None")
    print("  ok     sim/nao/nao_sei -> True/False/None")


TESTES = [
    teste_toda_falta_tem_dono,
    teste_participacao_tambem_declara_o_dono,
    teste_comprovante_de_contribuicao_depende_do_filiado,
    teste_homologacao_depende_da_conferencia,
    teste_tema_pendente_depende_do_tribunal,
    teste_cargo_nao_reconhecido_e_conferencia_nao_tarefa_do_filiado,
    teste_sem_cargo_nenhum_e_tarefa_do_filiado,
    teste_a_mesma_falta_nao_aparece_duas_vezes,
    teste_quem_declarou_nao_e_perguntado_de_novo,
    teste_execucao_anterior_declarada_vira_nota_nao_silencio,
    teste_resposta_do_cadastro_vira_booleano,
    teste_agrupar_junta_por_dono_sem_repetir,
    teste_agrupar_devolve_os_tres_donos_sempre,
    teste_agrupar_recusa_dono_desconhecido,
    teste_cada_dono_tem_titulo_para_o_filiado,
    teste_nenhum_texto_fala_de_escritorio,
    teste_cada_dono_explica_o_que_esperar,
]


def main() -> int:
    print("=" * 62)
    print("QUEM DESTRAVA CADA PENDÊNCIA")
    print("=" * 62)
    for t in TESTES:
        try:
            t()
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{t.__name__} levantou {type(e).__name__}: {e}")
    print()
    if falhas:
        print(f"FALHOU ({len(falhas)}):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
