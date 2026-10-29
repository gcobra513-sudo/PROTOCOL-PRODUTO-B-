#!/usr/bin/env python3
"""
O retrato da base: os números que o gerente do sindicato vê.

POR QUE ESTA SUÍTE É A MAIS IMPORTANTE DAS TRÊS PRIMEIRAS

Porque aqui mora o número que vai para o cliente. "Você não consegue falar
com 1.930 dos seus 4.812 filiados" é a primeira frase do produto, e um erro
de contagem nela não é bug de software — é uma afirmação falsa dita a um
diretor de sindicato, com a nossa assinatura.

A ingestão já aprendeu duas lições de contagem na mão, e elas são as duas
primeiras coisas testadas aqui:

  - **conta PESSOA, não linha.** Planilha repete pessoa. Quem aparece duas
    vezes, uma sem e-mail e outra com, é alcançável — e contar linha inflaria
    a manchete com gente que o sindicato alcança perfeitamente;
  - **divergência não é inalcançabilidade.** Quem aparece duas vezes com
    cargos diferentes continua tendo e-mail que funciona.

E uma terceira, que vem do diário: **reenvio não é pessoa nova.** O diário
recebe uma linha por envio e nunca é reescrito; o retrato olha o ÚLTIMO envio
de cada CPF, pelo mesmo desenho de `deposito.reconstruir_manifesto`.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import acervo, completude  # noqa: E402

SUJO = RAIZ / "tests" / "fixtures" / "acervo_sujo.csv"

#: Os CPFs da fixture, para os testes não dependerem de ler o arquivo de novo.
MARIA = "11144477735"      # aparece DUAS vezes, com cargo diferente
JOAO = "52998224725"       # alcançável, completo
ANA = "52601815906"        # e-mail sem ponto -> inalcançável
PEDRO = "11144477700"      # CPF não fecha -> inalcançável
CARLA = "24843803480"      # sem e-mail -> inalcançável

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def pessoas() -> list[acervo.Pessoa]:
    lidas, problemas = acervo.ler(SUJO)
    assert problemas == [], problemas
    return lidas


def registro(cpf: str, **trocas) -> dict:
    """Uma linha do diário de cadastro, como `deposito.depositar` a grava."""
    linha = {
        "id_externo": cpf,
        "cpf": cpf,
        "tem_processo": "sim",
        "numero_processo": "00012347020194013400",
        "acompanhar": "",
        "quer_aviso": "",
    }
    linha.update(trocas)
    return {
        "protocolo": f"P-{cpf}",
        "recebido_em": trocas.pop("recebido_em", "2026-10-29T12:00:00+00:00"),
        "entidade": "demo-teste",
        "linha": linha,
        "arquivos": {"procuracao.pdf": "a" * 64},
    }


# ------------------------------------------------------------------ manchete

def teste_a_manchete_e_quantos_o_sindicato_nao_alcanca():
    secao("a manchete")
    r = completude.retratar(pessoas(), diario=[])
    checa(r.total == 5,
          f"total deveria contar PESSOA (5), não linha (6); veio {r.total}")
    checa(r.inalcancaveis == 3, f"inalcançáveis: {r.inalcancaveis}")
    checa(r.alcancaveis == 2, f"alcançáveis: {r.alcancaveis}")
    checa(r.alcancaveis + r.inalcancaveis == r.total,
          "as partes não somam o total — alguém está sendo contado duas vezes")
    print(f"  ok     {r.inalcancaveis} de {r.total} inalcançáveis, e as partes somam")


def teste_quem_aparece_duas_vezes_conta_uma():
    r = completude.retratar(pessoas(), diario=[])
    checa(r.linhas == 6 and r.total == 5,
          f"6 linhas deveriam virar 5 pessoas; veio {r.linhas}/{r.total}")
    print("  ok     6 linhas, 5 pessoas")


def teste_divergencia_nao_torna_ninguem_inalcancavel():
    """A Maria aparece duas vezes com cargos diferentes e tem e-mail que
    funciona. Se ela entrasse na manchete, a manchete estaria mentindo."""
    r = completude.retratar(pessoas(), diario=[])
    checa(r.divergentes >= 1, "não contou a divergência")
    checa(MARIA not in r.inalcancaveis_por_cpf,
          "a divergência de cargo tornou a Maria inalcançável")
    print("  ok     divergência é contada, e não entra na manchete")


# -------------------------------------------------------------------- diário

def teste_quem_cadastrou_no_portal_conta_como_cadastrado():
    secao("cruzamento com o diário")
    r = completude.retratar(pessoas(), diario=[registro(MARIA)])
    checa(r.cadastrados == 1, f"cadastrados={r.cadastrados}")
    checa(r.sem_cadastro == r.total - 1, f"sem_cadastro={r.sem_cadastro}")
    print("  ok     cadastro no portal aparece no retrato")


def teste_reenvio_nao_conta_a_pessoa_duas_vezes():
    """O diário tem uma linha por ENVIO. Reenvio é a mesma pessoa corrigindo
    o cadastro, e contá-lo duas vezes faria o painel inventar filiado."""
    diario = [registro(MARIA), registro(MARIA, recebido_em="2026-10-29T13:00:00+00:00")]
    checa(completude.retratar(pessoas(), diario).cadastrados == 1,
          "reenvio inflou a contagem de cadastrados")
    print("  ok     reenvio não inventa filiado")


def teste_quem_cadastrou_e_nao_esta_no_acervo_aparece():
    """Filiado novo que entrou pelo portal antes de o sindicato reexportar a
    planilha. Ignorá-lo faria o painel esconder quem se cadastrou — e esse é
    exatamente quem o sindicato quer ver."""
    r = completude.retratar(pessoas(), diario=[registro("39053344705")])
    checa(r.fora_do_acervo == 1,
          f"cadastro de quem não está no acervo desapareceu: {r.fora_do_acervo}")
    print("  ok     cadastro sem linha no acervo é contado, não sumido")


def teste_o_que_a_pessoa_respondeu_sobre_processo():
    diario = [
        registro(MARIA, tem_processo="sim"),
        registro(JOAO, tem_processo="nao_sei", numero_processo=""),
        registro(ANA, tem_processo="nao", numero_processo=""),
    ]
    r = completude.retratar(pessoas(), diario)
    checa((r.com_processo, r.nao_sabe_o_processo, r.sem_processo) == (1, 1, 1),
          f"contagem por resposta errada: {r.com_processo}/"
          f"{r.nao_sabe_o_processo}/{r.sem_processo}")
    print("  ok     sim / não sei / não tenho, contados separados")


def teste_acompanhamento_e_opt_in_sao_contados():
    diario = [
        registro(MARIA, acompanhar="00012347020194013400;00076540520198070001",
                 quer_aviso="sim"),
        registro(JOAO, acompanhar="00012347020194013400"),
    ]
    r = completude.retratar(pessoas(), diario)
    checa(r.acompanhando == 2, f"acompanhando={r.acompanhando}")
    checa(r.processos_acompanhados == 2,
          f"processos distintos acompanhados={r.processos_acompanhados}")
    checa(r.querem_aviso == 1, f"querem_aviso={r.querem_aviso}")
    print("  ok     2 pessoas, 2 processos distintos, 1 opt-in")


# ------------------------------------------------------------- o que falta

def teste_campo_faltante_e_contado_por_nome():
    secao("o que falta")
    r = completude.retratar(pessoas(), diario=[])
    checa(r.falta_por_campo.get("data_nascimento", 0) >= 1,
          f"não contou data_nascimento faltante: {r.falta_por_campo}")
    checa(r.falta_por_campo.get("email", 0) >= 1,
          f"não contou email faltante: {r.falta_por_campo}")
    print(f"  ok     falta por campo: {dict(list(r.falta_por_campo.items())[:3])}")


def teste_cadastro_no_portal_supre_o_que_falta_no_acervo():
    """A Carla não tem e-mail no acervo. Se ela se cadastrar pelo portal com
    e-mail, continuar contando-a como "falta e-mail" seria mandar o sindicato
    atrás de informação que já chegou."""
    r = completude.retratar(
        pessoas(),
        diario=[registro(CARLA, email="carla@exemplo.org")],
    )
    checa(CARLA not in r.falta_nominal.get("email", []),
          "o cadastro no portal não supriu o e-mail que faltava no acervo")
    print("  ok     o que o portal trouxe deixa de constar como falta")


def teste_falta_nominal_diz_quem_e():
    """Contagem agregada não serve para agir: o gerente precisa da lista."""
    r = completude.retratar(pessoas(), diario=[])
    checa(CARLA in r.falta_nominal.get("email", []),
          f"a Carla não aparece na lista de quem falta e-mail: "
          f"{r.falta_nominal.get('email')}")
    print("  ok     a falta é nominal, não só contagem")


# ---------------------------------------------- achados da revisão (I1 a I4)

def teste_total_conta_so_o_acervo_e_a_manchete_diz_a_verdade():
    """I1 — ACHADO NA REVISÃO, reproduzido.

    `total` somava acervo E cadastrados, mas o rótulo diz "filiados no
    acervo" e a manchete diz "Você tem N filiados no acervo". Com acervo
    vazio e dois cadastros, a tela mostrava AO MESMO TEMPO "Você tem 2
    filiados no acervo" e "Você ainda não enviou a sua base" — duas
    afirmações contraditórias na mesma tela, no módulo que tem menos licença
    para errar.
    """
    secao("a manchete diz a verdade (I1)")
    r = completude.retratar([], diario=[registro(MARIA), registro(JOAO)])
    checa(r.total == 0,
          f"total conta quem não está no acervo: {r.total}")
    checa(r.fora_do_acervo == 2, f"fora_do_acervo={r.fora_do_acervo}")
    checa("acervo está vazio" in r.manchete().lower()
          or "vazio" in r.manchete().lower(),
          f"a manchete afirma ter filiados no acervo: {r.manchete()!r}")
    print(f"  ok     acervo vazio + 2 cadastros -> {r.manchete()!r}")


def teste_partes_somam_o_total_sempre():
    for diario in ([], [registro(MARIA)], [registro("39053344705")]):
        r = completude.retratar(pessoas(), diario)
        checa(r.alcancaveis + r.inalcancaveis == r.total,
              f"as partes não somam: {r.alcancaveis}+{r.inalcancaveis} != "
              f"{r.total}")
    print("  ok     alcançáveis + inalcançáveis = total, em todos os casos")


def teste_cpf_placeholder_nao_funde_pessoas():
    """I2 — ACHADO NA REVISÃO, reproduzido.

    `000.000.000-00` é endêmico em exportação de sindicato. A chave caía para
    o número da linha só quando o CPF estava VAZIO, então três pessoas com o
    mesmo placeholder viravam uma — e as outras duas sumiam do denominador E
    da lista nominal de quem ligar, que é exatamente quem mais precisa ser
    procurado.
    """
    falsos = [
        acervo.Pessoa(cpf="00000000000", linha_no_arquivo=n,
                      campos={"nome_completo": f"PESSOA {n} (EXEMPLO)",
                              "cpf": "000.000.000-00", "email": ""},
                      achados=(acervo.Achado("cpf", acervo.INVALIDO, "não fecha"),))
        for n in (2, 3, 4)
    ]
    r = completude.retratar(falsos, diario=[])
    checa(r.total == 3,
          f"três pessoas com CPF placeholder viraram {r.total}")
    checa(len(r.inalcancaveis_por_cpf) == 3,
          f"só {len(r.inalcancaveis_por_cpf)} apareceram na lista nominal")
    print("  ok     CPF inválido não funde pessoas distintas")


def teste_email_divergente_e_marcado_nao_resolvido():
    """I3 — ACHADO NA REVISÃO.

    Regra global da spec: "Divergência entre acervo e cadastro não se resolve
    sozinha — marca e mostra, nunca escolhe." O cadastro do portal estava
    sobrescrevendo o e-mail do acervo em silêncio, bem na visão que o
    sindicato usa para homologar.
    """
    r = completude.retratar(
        pessoas(),
        diario=[registro(JOAO, email="outro@exemplo.org")],
    )
    divergentes = r.divergencias.get(JOAO, [])
    checa(any(d["campo"] == "email" for d in divergentes),
          f"a divergência de e-mail não foi marcada: {r.divergencias}")
    if divergentes:
        d = next(x for x in divergentes if x["campo"] == "email")
        checa(d["acervo"] == "joao@exemplo.org"
              and d["cadastro"] == "outro@exemplo.org",
              f"a divergência não traz os dois valores: {d}")
    print("  ok     e-mail divergente é marcado com os dois valores")


def teste_nao_cobra_coluna_que_a_planilha_nunca_teve():
    """I4 — ACHADO NA REVISÃO, reproduzido.

    `falta_por_campo` contava coluna AUSENTE do arquivo como se estivesse
    vazia. Na fixture, que não tem endereço nem telefone, o topo da lista
    "O que falta" era nove linhas dizendo "= todo mundo". E `tem_processo` é
    resposta do PORTAL, nunca atributo do cadastro do sindicato: dizer
    "tem_processo: 4812" afirma que 4812 registros do diretor estão
    defeituosos quando nenhum está.
    """
    r = completude.retratar(pessoas(), diario=[])
    checa("telefone" not in r.falta_por_campo,
          f"cobrou coluna que a planilha não tem: {sorted(r.falta_por_campo)}")
    checa("tem_processo" not in r.falta_por_campo,
          "cobrou tem_processo, que é resposta do portal")
    checa("email" in r.falta_por_campo and "data_nascimento" in r.falta_por_campo,
          f"deixou de cobrar coluna presente e vazia: {r.falta_por_campo}")
    checa("telefone" in r.colunas_ausentes,
          f"não relatou a coluna ausente: {r.colunas_ausentes}")
    print(f"  ok     cobra {sorted(r.falta_por_campo)}; ausentes: "
          f"{sorted(r.colunas_ausentes)[:3]}...")



TESTES.extend([
    teste_a_manchete_e_quantos_o_sindicato_nao_alcanca,
    teste_quem_aparece_duas_vezes_conta_uma,
    teste_divergencia_nao_torna_ninguem_inalcancavel,
    teste_quem_cadastrou_no_portal_conta_como_cadastrado,
    teste_reenvio_nao_conta_a_pessoa_duas_vezes,
    teste_quem_cadastrou_e_nao_esta_no_acervo_aparece,
    teste_o_que_a_pessoa_respondeu_sobre_processo,
    teste_acompanhamento_e_opt_in_sao_contados,
    teste_campo_faltante_e_contado_por_nome,
    teste_cadastro_no_portal_supre_o_que_falta_no_acervo,
    teste_falta_nominal_diz_quem_e,
    teste_total_conta_so_o_acervo_e_a_manchete_diz_a_verdade,
    teste_partes_somam_o_total_sempre,
    teste_cpf_placeholder_nao_funde_pessoas,
    teste_email_divergente_e_marcado_nao_resolvido,
    teste_nao_cobra_coluna_que_a_planilha_nunca_teve,
])


def main() -> int:
    print("=" * 70)
    print("COMPLETUDE — o retrato da base que o gerente vê")
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
