#!/usr/bin/env python3
"""
O VALOR — "quanto" —, e por que ele é o último checkpoint de propósito.

Dizer "você vai receber R$ 48.000" para uma auditora aposentada e estar
errado não é defeito de software: é dinheiro prometido a quem já contou com
ele. Não se conserta com atualização. Por isso este módulo começa pela
recusa, e só calcula quando TODOS os insumos existem e estão homologados.

O QUE NÃO TEMOS HOJE, e nenhum código resolve:

    a base de cálculo    a ficha financeira da pessoa, mês a mês
    o valor da verba     quanto a GIFA mandava pagar, em cada período
    o índice             qual correção, a partir de quando, com qual tese

Sem os três, qualquer número seria inventado. Então `apurar` RECUSA, e a
recusa diz o que falta e de quem é — a mesma divisão da tela do filiado.

O QUE DÁ PARA FAZER HOJE, e é a peça que ninguém tem:

    a PRESCRIÇÃO. Dos 72 meses em que a pessoa participou, quantos ainda são
    cobráveis? É conta de calendário sobre dado que já temos, muda o
    resultado materialmente, e hoje ninguém no produto sabe responder.

DINHEIRO É `Decimal`, NUNCA `float`. `0.1 + 0.2 != 0.3` em binário, e um
centavo de erro por parcela em 2.000 parcelas é uma conta que o outro lado
confere e nós não.
"""
from __future__ import annotations

import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import pendencia, valor  # noqa: E402

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


# ------------------------------------------------------------ a prescrição

def teste_prescricao_corta_o_que_passou_de_cinco_anos():
    """Súmula 85/STJ: na relação de trato sucessivo, prescrevem as PARCELAS
    anteriores ao quinquênio, não o fundo de direito. A ação de 2006
    alcança de 2001 em diante — e o que é de 2000 não entra."""
    secao("a prescrição")
    p = valor.periodo_apuravel("1998-01", "2008-12", interrompida_em="2006-05")
    checa(p.inicio == "2001-05",
          f"o corte do quinquênio saiu em {p.inicio}, esperado 2001-05")
    checa(p.fim == "2008-12", f"o fim mudou sem motivo: {p.fim}")
    checa(p.meses_prescritos == 40,
          f"meses prescritos: {p.meses_prescritos}, esperado 40")
    print(f"  ok     1998-01..2008-12 -> {p.inicio}..{p.fim} "
          f"({p.meses_prescritos} meses prescritos)")


def teste_quem_esta_todo_dentro_do_quinquenio_nao_perde_nada():
    p = valor.periodo_apuravel("2003-01", "2008-12", interrompida_em="2006-05")
    checa(p.meses_prescritos == 0,
          f"cortou {p.meses_prescritos} meses de quem está dentro")
    checa((p.inicio, p.fim) == ("2003-01", "2008-12"), f"{p}")
    print("  ok     dentro do quinquênio, nada se perde")


def teste_tudo_prescrito_nao_vira_valor_nenhum():
    """E não vira erro: é resposta. A pessoa participou e nada é cobrável."""
    p = valor.periodo_apuravel("1990-01", "1995-12", interrompida_em="2006-05")
    checa(p.meses == 0, f"sobrou período de algo todo prescrito: {p}")
    checa(p.meses_prescritos == 72, f"prescritos: {p.meses_prescritos}")
    checa(not p, "o período vazio deu verdadeiro")
    print("  ok     tudo prescrito: zero meses cobráveis, e é resposta")


def teste_sem_a_data_de_interrupcao_nao_se_chuta():
    """A data que interrompe a prescrição NÃO é adivinhável: para a execução
    de coletiva é o ajuizamento DA COLETIVA, não o da execução individual, e
    confundir os dois muda o resultado em anos. Sem ela, recusa."""
    p = valor.periodo_apuravel("2003-01", "2008-12", interrompida_em="")
    checa(p.meses == 0, "calculou sem saber a data que interrompe")
    checa(any("interromp" in f.o_que.lower() or "ajuizamento" in f.o_que.lower()
              for f in p.falta),
          f"a recusa não pede a data: {[f.o_que for f in p.falta]}")
    print("  ok     sem a data de interrupção, recusa")


def teste_o_prazo_e_parametro_nao_constante():
    """O STJ Tema 1.410 trata da prescrição do fundo de direito e está
    pendente. Se o prazo fosse constante no código, mudá-lo seria mexer no
    motor — e é exatamente isso que um tema pendente promete exigir."""
    cinco = valor.periodo_apuravel("1998-01", "2008-12",
                                   interrompida_em="2006-05")
    dez = valor.periodo_apuravel("1998-01", "2008-12",
                                 interrompida_em="2006-05", anos=10)
    checa(cinco.inicio != dez.inicio,
          "mudar o prazo não mudou o corte — o prazo está cravado no código")
    checa(dez.inicio == "1998-01", f"com 10 anos o corte deu {dez.inicio}")
    print(f"  ok     prazo é parâmetro: 5 anos -> {cinco.inicio}, "
          f"10 anos -> {dez.inicio}")


def teste_a_memoria_diz_a_regra_aplicada():
    """A memória de cálculo é o produto tanto quanto o número. Conta sem
    memória é conta que o outro lado contesta e nós não sabemos defender."""
    p = valor.periodo_apuravel("1998-01", "2008-12", interrompida_em="2006-05")
    texto = " ".join(passo.o_que + passo.resultado + passo.fonte
                     for passo in p.memoria)
    checa(bool(p.memoria), "nenhum passo registrado")
    checa("85" in texto or "quinqu" in texto.lower(),
          f"a memória não cita a regra aplicada: {p.memoria}")
    checa(any(passo.fonte.strip() for passo in p.memoria),
          "nenhum passo cita fonte")
    print(f"  ok     {len(p.memoria)} passos, com fonte")


# --------------------------------------------------- a apuração, e a recusa

def teste_sem_verba_homologada_nao_se_apura():
    """A trava de sempre, agora sobre dinheiro: nada nominal sai sem
    advogado."""
    secao("a apuração")
    a = valor.apurar(
        valor.Periodo("2003-01", "2008-12"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="N"),
        bases={"2003-01": Decimal("1000.00")},
    )
    checa(a.total is None, f"apurou com verba não homologada: {a.total}")
    checa(a.veredicto == valor.FALTA_DADO, f"veredicto: {a.veredicto}")
    checa(any("homolog" in f.o_que.lower() for f in a.falta),
          f"a recusa não cita a homologação: {[f.o_que for f in a.falta]}")
    checa(all(f.quem in pendencia.DONOS for f in a.falta),
          "falta sem dono conhecido")
    print("  ok     verba não homologada: não apura, e diz por quê")


def teste_sem_base_de_calculo_nao_se_apura():
    """O QUE FALTA DE VERDADE HOJE. A ficha financeira da pessoa não está em
    lugar nenhum do produto, e sem ela não há do que tirar percentual."""
    a = valor.apurar(
        valor.Periodo("2003-01", "2003-03"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="S", fonte="exemplo://verba"),
        bases={},
    )
    checa(a.total is None, f"apurou sem base de cálculo: {a.total}")
    checa(any("base" in f.o_que.lower() or "ficha" in f.o_que.lower()
              for f in a.falta),
          f"a recusa não pede a ficha financeira: {[f.o_que for f in a.falta]}")
    print("  ok     sem ficha financeira: não apura, e pede a ficha")


def teste_um_mes_sem_base_impede_a_conta_inteira():
    """NÃO SE COMPLETA MÊS QUE FALTA. Preencher o buraco com a média seria
    inventar — e o número inventado sai com a nossa assinatura, no meio de
    uma conta correta, sem marca nenhuma."""
    a = valor.apurar(
        valor.Periodo("2003-01", "2003-03"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="S", fonte="exemplo://verba"),
        bases={"2003-01": Decimal("1000.00"), "2003-03": Decimal("1000.00")},
    )
    checa(a.total is None,
          f"calculou com um mês faltando, total={a.total}")
    checa(any("2003-02" in f.o_que for f in a.falta),
          f"a recusa não diz QUAL mês falta: {[f.o_que for f in a.falta]}")
    print("  ok     mês sem base impede a conta, e a recusa nomeia o mês")


def teste_com_tudo_no_lugar_a_conta_sai_e_fecha():
    a = valor.apurar(
        valor.Periodo("2003-01", "2003-03"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="S", fonte="exemplo://verba"),
        bases={"2003-01": Decimal("1000.00"),
               "2003-02": Decimal("1000.00"),
               "2003-03": Decimal("2000.00")},
    )
    checa(a.veredicto == valor.APURADO, f"veredicto: {a.veredicto} / {a.falta}")
    checa(a.total == Decimal("400.00"),
          f"total {a.total}, esperado 400.00 (100+100+200)")
    checa(len(a.parcelas) == 3, f"{len(a.parcelas)} parcelas para 3 meses")
    checa(sum((p.valor for p in a.parcelas), Decimal("0")) == a.total,
          "as parcelas não somam o total")
    print(f"  ok     3 meses -> R$ {a.total}")


def teste_dinheiro_e_decimal_nunca_float():
    """`0.1 + 0.2 != 0.3` em binário. Um centavo por parcela, em 2.000
    parcelas, é uma conta que o outro lado confere e nós não."""
    a = valor.apurar(
        valor.Periodo("2003-01", "2003-03"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="S", fonte="exemplo://verba"),
        bases={m: Decimal("0.10") for m in ("2003-01", "2003-02", "2003-03")},
    )
    checa(isinstance(a.total, Decimal),
          f"o total não é Decimal: {type(a.total).__name__}")
    for p in a.parcelas:
        checa(isinstance(p.valor, Decimal) and isinstance(p.base, Decimal),
              f"parcela em {type(p.valor).__name__}")
    # 0.10 * 0.10 = 0.01, três vezes = 0.03 exato. Em float daria 0.030000000000000002.
    checa(a.total == Decimal("0.03"), f"total {a.total!r}, esperado 0.03")
    print(f"  ok     total exato: {a.total!r}")


def teste_base_negativa_e_recusada():
    """Ficha financeira com valor negativo é erro de exportação, não desconto.
    Aceitar reduziria a conta de alguém em silêncio."""
    a = valor.apurar(
        valor.Periodo("2003-01", "2003-01"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="S", fonte="exemplo://verba"),
        bases={"2003-01": Decimal("-1000.00")},
    )
    checa(a.total is None, f"aceitou base negativa: {a.total}")
    checa(any("negativ" in f.o_que.lower() for f in a.falta),
          f"a recusa não explica: {[f.o_que for f in a.falta]}")
    print("  ok     base negativa é recusada")


def teste_a_memoria_da_apuracao_tem_uma_linha_por_decisao():
    a = valor.apurar(
        valor.Periodo("2003-01", "2003-02"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="S", fonte="exemplo://verba"),
        bases={"2003-01": Decimal("1000.00"), "2003-02": Decimal("1000.00")},
    )
    checa(len(a.memoria) >= 2, f"memória curta demais: {a.memoria}")
    for passo in a.memoria:
        checa(bool(passo.o_que.strip()) and bool(passo.resultado.strip()),
              f"passo incompleto: {passo}")
    print(f"  ok     {len(a.memoria)} passos na memória")


# ------------------------------------------------- o que a conta NÃO afirma

def teste_a_apuracao_nunca_se_chama_de_valor_a_receber():
    """Falta correção monetária, juros, compensação do que já foi pago e
    retenção de IR. O número apurado é BRUTO e PARCIAL, e chamá-lo de
    "o que você vai receber" é a promessa que este checkpoint existe para
    não fazer."""
    secao("o que a conta não afirma")
    a = valor.apurar(
        valor.Periodo("2003-01", "2003-01"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="S", fonte="exemplo://verba"),
        bases={"2003-01": Decimal("1000.00")},
    )
    aviso = a.aviso.lower()
    checa("não é" in aviso or "nao e" in aviso,
          f"o aviso não nega nada: {a.aviso!r}")
    for prometido in ("você vai receber", "voce vai receber",
                      "tem direito a receber", "garantido"):
        checa(prometido not in aviso, f"o aviso promete: {prometido!r}")
    for esperado in ("correção", "juros"):
        checa(esperado in aviso,
              f"o aviso não diz que falta {esperado}: {a.aviso!r}")
    checa("escritóri" not in aviso, f"REGRA ZERO: {a.aviso!r}")
    print(f"  ok     {a.aviso[:88]}...")


def teste_apuracao_sem_total_tambem_traz_aviso():
    a = valor.apurar(
        valor.Periodo("2003-01", "2003-01"),
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="N"),
        bases={},
    )
    checa(bool(a.aviso.strip()), "a recusa saiu sem aviso")
    print("  ok     a recusa também vem com aviso")


def teste_a_prescricao_entra_na_apuracao_antes_da_conta():
    """A ordem importa: cortar depois de somar daria um total que inclui
    parcela prescrita, e alguém leria o número errado no caminho."""
    p = valor.periodo_apuravel("1998-01", "2003-03", interrompida_em="2003-01")
    checa(p.inicio == "1998-01",
          f"corte de 5 anos sobre 2003-01 devia alcançar 1998-01: {p.inicio}")
    a = valor.apurar(
        p,
        verba=valor.Verba(id="GIFA", percentual=Decimal("0.10"),
                          homologado="S", fonte="exemplo://verba"),
        bases={},
    )
    checa(any("1998-01" in f.o_que or "base" in f.o_que.lower()
              for f in a.falta),
          f"a apuração não usou o período já cortado: {a.falta}")
    print("  ok     a prescrição corta antes de a conta começar")


def teste_poder_executar_nao_depende_de_saber_quanto():
    """A LIÇÃO QUE CUSTOU UM TESTE VERMELHO, e ela é do produto.

    Quando a apuração entrou no motor, as faltas dela foram parar na mesma
    lista do veredicto — e ninguém mais conseguia chegar a PODE, porque a
    ficha financeira de ninguém existe. Estava errado: **poder executar é
    sobre título e legitimidade; o valor se apura depois, no próprio
    processo.** Misturar as duas faria ninguém executar nada até a ficha de
    cada pessoa estar em mãos, o que é errado em juízo e inútil como produto.
    """
    secao("as duas perguntas")
    from nucleo import entendimentos, motor

    catalogo = entendimentos.carregar_categorias(
        entendimentos.PASTA_PADRAO, ("auditor-fiscal-receita-federal",)
    ).homologando(("GIFA-2006",))
    fatos = motor.Fatos(
        cpf="11144477735", cargo="Auditor-Fiscal da Receita Federal do Brasil",
        situacao="aposentado", filiado_desde="2004-03",
        tem_titulo=True, no_rol=True, ja_executou=False,
        ja_executou_conferido=True, tem_acao_propria=False,
    )
    executar = [o for o in motor.avaliar(fatos, catalogo)
                if o.trilha == motor.EXECUTAR]
    checa(bool(executar), "nenhuma oportunidade de executar")
    for o in executar:
        checa(o.veredicto == motor.PODE,
              f"{o.referencia}: o valor bloqueou o veredicto -> "
              f"{o.veredicto} / {[f.o_que for f in o.falta]}")
        checa(bool(o.falta_para_valor),
              f"{o.referencia}: pode executar e não disse o que falta para "
              f"saber quanto")
        checa(o.apuracao is not None and o.apuracao.total is None,
              f"{o.referencia}: apurou um total sem ficha financeira")
        das_duas = {f.o_que for f in o.falta} & {
            f.o_que for f in o.falta_para_valor
        }
        checa(not das_duas,
              f"a mesma falta nas duas listas, e elas respondem perguntas "
              f"diferentes: {das_duas}")
    print(f"  ok     PODE executar, e {len(executar[0].falta_para_valor)} "
          f"falta(s) para saber quanto")


def teste_o_que_falta_para_o_valor_nomeia_as_duas_pecas():
    """As duas peças que não existem em lugar nenhum do produto: a data de
    ajuizamento da coletiva e a ficha financeira. Nomeá-las é o que
    transforma 'não dá para calcular' em tarefa."""
    from nucleo import entendimentos, motor

    catalogo = entendimentos.carregar_categorias(
        entendimentos.PASTA_PADRAO, ("auditor-fiscal-receita-federal",)
    ).homologando(("GIFA-2006",))
    fatos = motor.Fatos(
        cpf="11144477735", cargo="Auditor-Fiscal da Receita Federal do Brasil",
        filiado_desde="2004-03", tem_titulo=True, no_rol=True,
        ja_executou=False, tem_acao_propria=False,
    )
    textos = " | ".join(
        f.o_que for o in motor.avaliar(fatos, catalogo)
        for f in o.falta_para_valor
    ).lower()
    checa("ajuizamento" in textos or "interromp" in textos,
          f"não pede a data de ajuizamento da coletiva: {textos}")
    for f in (f for o in motor.avaliar(fatos, catalogo)
              for f in o.falta_para_valor):
        checa(f.quem in pendencia.DONOS, f"falta sem dono: {f}")
    print(f"  ok     {textos[:92]}...")


TESTES = [
    teste_prescricao_corta_o_que_passou_de_cinco_anos,
    teste_quem_esta_todo_dentro_do_quinquenio_nao_perde_nada,
    teste_tudo_prescrito_nao_vira_valor_nenhum,
    teste_sem_a_data_de_interrupcao_nao_se_chuta,
    teste_o_prazo_e_parametro_nao_constante,
    teste_a_memoria_diz_a_regra_aplicada,
    teste_sem_verba_homologada_nao_se_apura,
    teste_sem_base_de_calculo_nao_se_apura,
    teste_um_mes_sem_base_impede_a_conta_inteira,
    teste_com_tudo_no_lugar_a_conta_sai_e_fecha,
    teste_dinheiro_e_decimal_nunca_float,
    teste_base_negativa_e_recusada,
    teste_a_memoria_da_apuracao_tem_uma_linha_por_decisao,
    teste_a_apuracao_nunca_se_chama_de_valor_a_receber,
    teste_apuracao_sem_total_tambem_traz_aviso,
    teste_a_prescricao_entra_na_apuracao_antes_da_conta,
    teste_poder_executar_nao_depende_de_saber_quanto,
    teste_o_que_falta_para_o_valor_nomeia_as_duas_pecas,
]


def main() -> int:
    print("=" * 62)
    print("O VALOR — e o que ele se recusa a afirmar")
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
