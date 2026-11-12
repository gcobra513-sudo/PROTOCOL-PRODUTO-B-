#!/usr/bin/env python3
"""
O motor do veredicto: dada uma pessoa, o que ela pode fazer.

É A CAIXA 3 DO MAPA, e é o produto. Entra o que se sabe da pessoa, sai a
lista do que ela pode executar e do que ela pode ajuizar — com o motivo de
cada "não".

A REGRA QUE ORGANIZA TUDO: **executar exige título; ajuizar não.**

Sentença transitada em nome da pessoa, ou coletiva em que ela é substituída.
Sem título não há o que executar, por melhor que seja a tese. Dizer "você
pode executar" para quem tem só a tese cria expectativa de dinheiro em gente
aposentada, e esse erro não se conserta com atualização de software. O
primeiro teste deste arquivo é exatamente esse, e se ele falhar nenhum outro
importa.

E a segunda regra, que vem da pesquisa de 29/10/2026: o **STJ Tema 1.302**
está AFETADO, COM SUSPENSÃO NACIONAL, e decide justamente se quem está fora
do rol de substituídos pode executar. Enquanto pende, afirmar que pode é
apostar com o processo de outra pessoa. O motor devolve FALTA, nunca PODE.
"""
from __future__ import annotations

import pathlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import entendimentos, motor  # noqa: E402

CATEGORIAS = RAIZ / "config" / "categorias"

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def catalogo(homologar: tuple[str, ...] = ()) -> entendimentos.Catalogo:
    """O catálogo real, com as entradas pedidas marcadas como homologadas.

    Homologar no teste e não no arquivo é de propósito: o arquivo em disco
    tem de continuar com `homologado = "N"` em tudo, porque homologar é ato
    de advogado e não de programador.
    """
    return entendimentos.carregar_categorias(CATEGORIAS).homologando(homologar)


def fatos(**trocas) -> motor.Fatos:
    base = dict(
        cpf="11144477735",
        nome="FULANA DE TAL (CADASTRO DE EXEMPLO)",
        cargo="Auditor-Fiscal da Receita Federal do Brasil",
        situacao="aposentado",
        data_ingresso="1992-04-01",
        data_aposentadoria="2018-06-30",
        filiado_desde="1992-05",
        filiado_ate="",
        tem_titulo=None,
        no_rol=None,
        ja_executou=None,
        tem_acao_propria=None,
    )
    base.update(trocas)
    return motor.Fatos(**base)


# ------------------------------------------------------- a regra que organiza

def teste_sem_titulo_ninguem_executa_nunca():
    """O teste mais importante do repositório.

    Se ele falhar, o sistema está dizendo a uma pessoa aposentada que ela tem
    dinheiro a receber quando ela não tem título nenhum.
    """
    secao("executar exige título")
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    for sem_titulo in (False, None):
        achadas = motor.avaliar(fatos(tem_titulo=sem_titulo), cat)
        executar = [o for o in achadas if o.trilha == motor.EXECUTAR]
        podem = [o for o in executar if o.veredicto == motor.PODE]
        checa(podem == [],
              f"tem_titulo={sem_titulo!r} e o motor disse que PODE EXECUTAR: "
              f"{[o.referencia for o in podem]}")
    print("  ok     sem título, nenhuma oportunidade de executar sai como PODE")


def teste_quem_tem_titulo_e_esta_no_rol_pode_executar():
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    achadas = motor.avaliar(
        fatos(tem_titulo=True, no_rol=True, ja_executou=False), cat)
    executar = [o for o in achadas if o.trilha == motor.EXECUTAR]
    checa(any(o.veredicto == motor.PODE for o in executar),
          f"quem tem título e está no rol devia poder: "
          f"{[(o.referencia, o.veredicto, o.motivos) for o in executar]}")
    print("  ok     título + rol + sem execução prévia = PODE")


def teste_quem_ja_executou_nao_executa_de_novo():
    """Executar duas vezes cria dois processos para a mesma dívida, e o erro
    só aparece semanas depois."""
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    achadas = motor.avaliar(
        fatos(tem_titulo=True, no_rol=True, ja_executou=True), cat)
    executar = [o for o in achadas if o.trilha == motor.EXECUTAR]
    checa(all(o.veredicto != motor.PODE for o in executar),
          "quem já executou apareceu como PODE")
    checa(any("já" in " ".join(o.motivos).lower() for o in executar),
          f"o motivo não menciona a execução anterior: "
          f"{[o.motivos for o in executar]}")
    print("  ok     execução prévia barra, com motivo nominal")


# ------------------------------------------------- o Tema 1.302, que está vivo

def teste_fora_do_rol_com_tema_pendente_e_falta_nao_permissao():
    """A regra que veio da pesquisa.

    O STJ Tema 1.302 está afetado e com suspensão nacional. Quem está fora do
    rol não pode ser informado de que "pode executar" — a dúvida é do STJ, e
    está pendente.
    """
    secao("STJ Tema 1.302, afetado com suspensão")
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    achadas = motor.avaliar(
        fatos(tem_titulo=True, no_rol=False, ja_executou=False), cat)
    executar = [o for o in achadas if o.trilha == motor.EXECUTAR]
    checa(all(o.veredicto != motor.PODE for o in executar),
          "disse PODE para quem está fora do rol com o tema pendente")
    texto = " ".join(m for o in executar for m in o.motivos)
    checa("1302" in texto or "1.302" in texto,
          f"o motivo não cita o tema que causa a dúvida: {texto!r}")
    checa("suspens" in texto.lower(),
          f"o motivo não menciona a suspensão: {texto!r}")
    print("  ok     fora do rol + tema pendente = FALTA, citando o tema")


def teste_entendimento_nao_homologado_nao_produz_veredicto():
    """`homologado = "N"` é a trava: o motor prepara, quem assina é gente."""
    cat = entendimentos.carregar_categorias(CATEGORIAS)      # nada homologado
    achadas = motor.avaliar(fatos(tem_titulo=True, no_rol=True), cat)
    checa(all(o.veredicto != motor.PODE for o in achadas),
          f"entendimento não homologado produziu permissão: "
          f"{[(o.referencia, o.veredicto) for o in achadas]}")
    checa(any("homolog" in " ".join(o.motivos).lower() for o in achadas),
          "não disse que falta homologação")
    print("  ok     catálogo não homologado não autoriza nada")


# --------------------------------------------------------- a trilha AJUIZAR

def teste_sem_titulo_mas_enquadrado_pode_ajuizar():
    """A outra trilha, e é a de população maior: quem nunca entrou com nada."""
    secao("ajuizar não exige título")
    cat = catalogo(("STJ-T1299",))
    achadas = motor.avaliar(
        fatos(tem_titulo=False, tem_acao_propria=False), cat)
    ajuizar = [o for o in achadas if o.trilha == motor.AJUIZAR]
    checa(ajuizar != [], "nenhuma oportunidade de ajuizar foi avaliada")
    print(f"  ok     {len(ajuizar)} oportunidade(s) de ajuizar avaliadas")


def teste_quem_ja_tem_acao_propria_nao_ajuiza_de_novo():
    cat = catalogo(("STJ-T1299",))
    achadas = motor.avaliar(
        fatos(tem_titulo=False, tem_acao_propria=True), cat)
    ajuizar = [o for o in achadas if o.trilha == motor.AJUIZAR]
    checa(all(o.veredicto != motor.PODE for o in ajuizar),
          "quem já tem ação própria apareceu como PODE ajuizar")
    print("  ok     ação própria barra o ajuizamento")


def teste_as_duas_trilhas_nao_se_misturam():
    """Uma oportunidade de ajuizar nunca vira permissão de executar."""
    cat = catalogo(("STJ-T1169", "STJ-T1299", "STJ-T1302", "GIFA-2006"))
    achadas = motor.avaliar(fatos(tem_titulo=False, tem_acao_propria=False), cat)
    for o in achadas:
        checa(o.trilha in (motor.EXECUTAR, motor.AJUIZAR),
              f"trilha desconhecida: {o.trilha!r}")
        if o.trilha == motor.EXECUTAR:
            checa(o.veredicto != motor.PODE,
                  f"{o.referencia}: sem título, executar não pode ser PODE")
    print("  ok     as trilhas são separadas por construção")


# ------------------------------------------------------------- o que falta

def teste_a_duvida_e_nominal_e_diz_o_que_falta():
    """FALTA sem dizer o que falta é inútil: quem lê não sabe o que fazer."""
    secao("a dúvida é acionável")
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    achadas = motor.avaliar(fatos(tem_titulo=True), cat)   # no_rol=None
    faltando = [o for o in achadas if o.veredicto == motor.FALTA]
    checa(faltando != [], "nada ficou como FALTA, com no_rol desconhecido")
    checa(all(o.falta for o in faltando),
          f"FALTA sem dizer o que falta: "
          f"{[(o.referencia, o.falta) for o in faltando]}")
    print(f"  ok     {len(faltando)} pendência(s), todas dizendo o que falta")


def teste_nada_e_devolvido_sem_referencia_e_rotulo():
    """O que vai para a tela tem de ser legível por gente."""
    cat = catalogo(("STJ-T1169", "STJ-T1299", "STJ-T1302", "GIFA-2006"))
    for o in motor.avaliar(fatos(tem_titulo=True, no_rol=True), cat):
        checa(bool(o.referencia), "oportunidade sem referência")
        checa(bool(o.rotulo), f"{o.referencia}: sem rótulo legível")
        checa(bool(o.fonte), f"{o.referencia}: sem fonte")
    print("  ok     toda oportunidade tem referência, rótulo e fonte")


# ------------------------------------- a ação coletiva como entidade (etapa 2)

def teste_acao_coletiva_declara_quem_ela_cobre():
    """Uma ação coletiva não é só um número. Ela cobre UMA CATEGORIA, num
    PERÍODO — e é disso que sai "em quais ações esta pessoa participa".

    Sem o período declarado não há como responder a pergunta, e a ação não
    pode ser homologada: homologar sem período é afirmar que sabemos quem
    ela alcança quando não sabemos.
    """
    secao("a ação coletiva")
    cat = entendimentos.carregar_categorias(CATEGORIAS)
    gifa = cat.de("GIFA-2006")
    checa(gifa.categoria.strip() != "",
          "a ação não declara qual categoria ela cobre")
    checa(gifa.periodo_inicio and gifa.periodo_fim,
          f"a ação não declara o período coberto: "
          f"{gifa.periodo_inicio!r} a {gifa.periodo_fim!r}")
    checa(gifa.periodo_inicio < gifa.periodo_fim,
          f"período invertido: {gifa.periodo_inicio} a {gifa.periodo_fim}")
    print(f"  ok     {gifa.id}: {gifa.categoria[:28]}... "
          f"{gifa.periodo_inicio} a {gifa.periodo_fim}")


def teste_acao_sem_periodo_nao_homologa():
    """A autópsia. Uma ação homologada sem período diria a quem participa
    com base em nada."""
    import tempfile

    torta = pathlib.Path(tempfile.mkdtemp()) / "c.toml"
    torta.write_text(
        '[catalogo]\nversao = 1\ncategoria = "x"\n\n'
        '[[acoes_coletivas]]\nid = "SEM-PERIODO"\n'
        'descricao = "Ação sem período"\nhomologado = "S"\n',
        encoding="utf-8",
    )
    try:
        entendimentos.carregar(torta)
        checa(False, "aceitou ação homologada sem período coberto")
    except entendimentos.ErroDeCatalogo as e:
        checa("período" in str(e) or "periodo" in str(e),
              f"a mensagem não diz que falta o período: {e}")
    print("  ok     ação homologada sem período é recusada")


def teste_acao_diz_se_exige_rol():
    """Exigir rol muda tudo: com rol, quem não está nele depende do Tema
    1.302, que está pendente. Sem rol, a coisa julgada alcança a categoria."""
    gifa = entendimentos.carregar_categorias(CATEGORIAS).de("GIFA-2006")
    checa(isinstance(gifa.exige_rol, bool),
          f"exige_rol devia ser booleano, é {type(gifa.exige_rol).__name__}")
    print(f"  ok     exige_rol declarado: {gifa.exige_rol}")



# ----------------------------------- participação antes do veredicto (etapa 3)

def teste_quem_nao_participa_da_acao_nao_pode_executar_mesmo_com_titulo():
    """A etapa 3 ligada ao motor, e a ordem importa.

    Antes, o motor perguntava "tem título?" para toda ação do catálogo, de
    todo mundo. Agora pergunta primeiro se a pessoa FAZ PARTE daquela ação —
    e quem não faz não executa, por mais título que tenha. Um Analista
    Tributário com sentença na mão não executa uma ação de Auditores-Fiscais.
    """
    secao("participação antes do veredicto")
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    f = fatos(tem_titulo=True, no_rol=True, ja_executou=False,
              cargo="Analista Tributário da Receita Federal",
              filiado_desde="1995-01")
    executar = [o for o in motor.avaliar(f, cat) if o.trilha == motor.EXECUTAR]
    checa(all(o.veredicto != motor.PODE for o in executar),
          "deixou executar ação de outra categoria")
    texto = " ".join(m for o in executar for m in o.motivos).lower()
    checa("categoria" in texto or "carreira" in texto,
          f"o motivo não explica que é de outra categoria: {texto[:200]}")
    print("  ok     outra categoria não executa, nem com título")


def teste_quem_saiu_antes_da_acao_nao_executa():
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    f = fatos(tem_titulo=True, no_rol=True, ja_executou=False,
              filiado_desde="1995-01", filiado_ate="2002-12")
    executar = [o for o in motor.avaliar(f, cat) if o.trilha == motor.EXECUTAR]
    checa(all(o.veredicto != motor.PODE for o in executar),
          "deixou executar ação cujo período não alcança a filiação")
    print("  ok     filiação fora do período da ação não executa")


def teste_sem_saber_a_filiacao_a_resposta_e_falta():
    """Não saber não é não ter direito."""
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    f = fatos(tem_titulo=True, no_rol=True, ja_executou=False,
              filiado_desde="")
    executar = [o for o in motor.avaliar(f, cat) if o.trilha == motor.EXECUTAR]
    checa(all(o.veredicto == motor.FALTA for o in executar),
          f"{[(o.referencia, o.veredicto) for o in executar]}")
    checa(any("contribui" in f.o_que.lower() for o in executar for f in o.falta),
          f"não pediu os comprovantes de contribuição: "
          f"{[o.falta for o in executar]}")
    print("  ok     sem filiação conhecida: FALTA, pedindo a contribuição")


def teste_a_oportunidade_diz_de_que_periodo_ela_e():
    """A interseção chega ao veredicto. É dela que o valor sai depois, e sem
    ela o escritório teria de refazer a conta a partir do zero."""
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    f = fatos(tem_titulo=True, no_rol=True, ja_executou=False,
              filiado_desde="2005-04", filiado_ate="2006-11")
    pode = [o for o in motor.avaliar(f, cat)
            if o.trilha == motor.EXECUTAR and o.veredicto == motor.PODE]
    checa(pode != [], "não chegou a PODE com filiação parcial")
    if pode:
        checa((pode[0].periodo_inicio, pode[0].periodo_fim)
              == ("2005-04", "2006-11"),
              f"período da oportunidade: {pode[0].periodo_inicio} a "
              f"{pode[0].periodo_fim}")
        checa(pode[0].meses == 20, f"meses: {pode[0].meses}")
    print("  ok     a oportunidade carrega o período e os 20 meses")



# ------------------------------------------ o rol é DE UMA AÇÃO, não de todas

def _duas_acoes():
    """O catálogo real mais uma segunda coletiva, cópia da GIFA com outro id.

    O catálogo em disco tem UMA ação, e é por isso que o defeito não
    aparecia: com uma só, "o rol" e "o rol desta ação" são a mesma coisa.
    """
    import dataclasses
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    outra = dataclasses.replace(cat.de("GIFA-2006"), id="OUTRA-2010",
                                descricao="Outra coletiva (de teste)")
    return dataclasses.replace(cat, acoes=(*cat.acoes, outra))


def teste_o_rol_de_uma_acao_nao_vale_para_outra():
    """Constar do rol da GIFA não diz NADA sobre o rol de outra coletiva.

    Com um fato só para todas as ações, o rol enviado para uma destravava a
    execução de todas as outras do catálogo — permissão tirada de um
    documento que não fala daquela ação.
    """
    secao("o rol é de uma ação")
    cat = _duas_acoes()
    achadas = motor.avaliar(
        fatos(tem_titulo=True, ja_executou=False,
              rol_das_acoes=(("GIFA-2006", True),)), cat)
    por = {o.referencia: o for o in achadas if o.trilha == motor.EXECUTAR}
    checa(por["GIFA-2006"].veredicto == motor.PODE,
          f"no rol da GIFA e não pôde: {por['GIFA-2006'].motivos}")
    checa(por["OUTRA-2010"].veredicto == motor.FALTA,
          f"o rol da GIFA decidiu a outra ação: {por['OUTRA-2010'].veredicto}")
    checa(any("rol" in f.o_que for f in por["OUTRA-2010"].falta),
          f"a outra ação não pede o rol DELA: {por['OUTRA-2010'].falta}")
    print("  ok     no rol de uma, a outra continua pedindo o rol dela")


def teste_fora_do_rol_de_uma_acao_nao_barra_a_outra():
    cat = _duas_acoes()
    achadas = motor.avaliar(
        fatos(tem_titulo=True, ja_executou=False,
              rol_das_acoes=(("GIFA-2006", False), ("OUTRA-2010", True))), cat)
    por = {o.referencia: o for o in achadas if o.trilha == motor.EXECUTAR}
    checa(por["OUTRA-2010"].veredicto == motor.PODE,
          f"fora do rol da GIFA barrou a outra: {por['OUTRA-2010'].motivos}")
    checa(por["GIFA-2006"].veredicto != motor.PODE,
          "fora do rol da GIFA e o motor disse PODE")
    print("  ok     fora do rol de uma não barra a outra")


def teste_a_resposta_da_acao_vence_a_resposta_geral():
    """`no_rol` é a resposta sem ação — a que os testes antigos usam. Quando
    há resposta PARA A AÇÃO, é ela que vale: a geral não sabe de qual ação
    está falando."""
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    achadas = motor.avaliar(
        fatos(tem_titulo=True, ja_executou=False, no_rol=True,
              rol_das_acoes=(("GIFA-2006", False),)), cat)
    gifa = next(o for o in achadas if o.referencia == "GIFA-2006")
    checa(gifa.veredicto != motor.PODE,
          "a resposta geral venceu a resposta da própria ação")
    print("  ok     a resposta da ação vence a geral")


def teste_o_rol_enviado_pelo_sindicato_vai_com_nota():
    """Quem assina precisa saber DE ONDE veio o "consta do rol": de um
    arquivo que o sindicato enviou, e não dos autos. Sem a nota, a
    declaração do sindicato entra no lugar da conferência — e ninguém vê
    que entrou. É a mesma regra do "não executei" declarado pela pessoa."""
    cat = catalogo(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    for consta in (True, False):
        achadas = motor.avaliar(
            fatos(tem_titulo=True, ja_executou=False,
                  rol_das_acoes=(("GIFA-2006", consta),)), cat)
        gifa = next(o for o in achadas if o.referencia == "GIFA-2006")
        checa(any("enviado pelo sindicato" in n.lower() and "autos" in n
                  for n in gifa.notas),
              f"consta={consta}: sem nota dizendo de onde veio o rol: "
              f"{gifa.notas}")
    # E quem não tem resposta por ação NÃO ganha a nota: ela afirmaria um
    # envio que não houve.
    achadas = motor.avaliar(
        fatos(tem_titulo=True, ja_executou=False, no_rol=True), cat)
    gifa = next(o for o in achadas if o.referencia == "GIFA-2006")
    checa(not any("enviado pelo sindicato" in n.lower() for n in gifa.notas),
          f"nota de envio sem envio: {gifa.notas}")
    print("  ok     rol enviado pelo sindicato: a nota diz que não é dos autos")



def teste_a_falta_do_rol_diz_de_qual_acao_e_onde_se_resolve():
    """"O rol de substituídos da ação coletiva" — de QUAL? Com duas ações no
    catálogo o gestor não sabe qual lista procurar. E a pendência passa a
    dizer ONDE se resolve: o painel leva ao cartão do rol sem adivinhar pela
    palavra na frase, que é o que erra calado quando alguém reescreve."""
    from nucleo import pendencia

    cat = _duas_acoes()
    achadas = motor.avaliar(fatos(tem_titulo=True, ja_executou=False), cat)
    por = {o.referencia: o for o in achadas if o.trilha == motor.EXECUTAR}
    for acao in ("GIFA-2006", "OUTRA-2010"):
        do_rol = [f for f in por[acao].falta if f.onde == pendencia.NO_ROL]
        checa(len(do_rol) == 1, f"{acao}: {por[acao].falta}")
        checa(do_rol and cat.de(acao).rotulo in do_rol[0].o_que,
              f"{acao}: a falta não diz de qual ação é o rol: {do_rol}")
    checa(len({f.o_que for a in por.values() for f in a.falta
               if f.onde == pendencia.NO_ROL}) == 2,
          "as duas ações pedem o rol com a MESMA frase")
    outras = [f for o in achadas for f in o.falta if f.onde != pendencia.NO_ROL]
    checa(all(f.onde == "" for f in outras),
          f"pendência que não é do rol aponta para algum lugar: {outras}")
    print("  ok     a falta do rol nomeia a ação e diz onde se resolve")


TESTES.extend([
    teste_sem_titulo_ninguem_executa_nunca,
    teste_quem_tem_titulo_e_esta_no_rol_pode_executar,
    teste_quem_ja_executou_nao_executa_de_novo,
    teste_fora_do_rol_com_tema_pendente_e_falta_nao_permissao,
    teste_entendimento_nao_homologado_nao_produz_veredicto,
    teste_sem_titulo_mas_enquadrado_pode_ajuizar,
    teste_quem_ja_tem_acao_propria_nao_ajuiza_de_novo,
    teste_as_duas_trilhas_nao_se_misturam,
    teste_a_duvida_e_nominal_e_diz_o_que_falta,
    teste_nada_e_devolvido_sem_referencia_e_rotulo,
    teste_acao_coletiva_declara_quem_ela_cobre,
    teste_acao_sem_periodo_nao_homologa,
    teste_acao_diz_se_exige_rol,
    teste_quem_nao_participa_da_acao_nao_pode_executar_mesmo_com_titulo,
    teste_quem_saiu_antes_da_acao_nao_executa,
    teste_sem_saber_a_filiacao_a_resposta_e_falta,
    teste_a_oportunidade_diz_de_que_periodo_ela_e,
    teste_o_rol_de_uma_acao_nao_vale_para_outra,
    teste_fora_do_rol_de_uma_acao_nao_barra_a_outra,
    teste_a_resposta_da_acao_vence_a_resposta_geral,
    teste_o_rol_enviado_pelo_sindicato_vai_com_nota,
    teste_a_falta_do_rol_diz_de_qual_acao_e_onde_se_resolve,
])


def main() -> int:
    print("=" * 70)
    print("MOTOR DO VEREDICTO — o que esta pessoa pode fazer")
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
