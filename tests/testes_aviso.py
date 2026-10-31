#!/usr/bin/env python3
"""
O AVISO DE MOVIMENTAÇÃO — a promessa que o formulário fazia e ninguém cumpria.

O cadastro pergunta "quero receber aviso por e-mail quando houver
movimentação nos meus processos", guarda a resposta, o painel até conta
quantos marcaram — e **nada nunca lia esse campo**. Opt-in coletado e
ignorado é pior que não ter: a pessoa marcou achando que seria avisada, e
continuou ligando para o sindicato.

AS QUATRO REGRAS QUE ESTE MÓDULO NÃO PODE QUEBRAR:

**Só quem pediu.** Opt-in ignorado para o outro lado — escrever para quem não
marcou — não é descuido, é mala direta com dado sensível.

**A PRIMEIRA COLETA NÃO AVISA.** É a armadilha que estraga a estreia: no dia
em que o sindicato entra, a coleta traz o histórico inteiro de cada processo
— a GIFA tem 600 movimentos — e todo mundo receberia um e-mail com anos de
andamento. Processo visto pela primeira vez entra como conhecido, calado.

**Um e-mail por pessoa, não por movimento.** Três andamentos no mesmo dia são
três linhas numa mensagem, não três mensagens.

**O e-mail é o do SINDICATO.** Mesmo motivo do código de acesso: se fosse o
digitado, bastaria alguém cadastrar o CPF de outra pessoa com o próprio
e-mail para passar a receber a movimentação do processo dela.

E o que o texto nunca diz: que é intimação, ou que serve para contar prazo.
A movimentação do DataJud tem cerca de um dia de atraso e não substitui
publicação — dizer o contrário faria alguém perder prazo confiando na gente.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import aviso  # noqa: E402

falhas: list[str] = []

A, B = "11144477735", "52998224725"
P1 = "00103912420064013400"
P2 = "00076540520198070001"


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def pessoa(cpf: str, *, quer: bool = True, email: str = "",
           processos=(P1,)) -> aviso.Destinatario:
    return aviso.Destinatario(
        cpf=cpf,
        nome=f"FULANO {cpf[-2:]} (CADASTRO DE EXEMPLO)",
        email_do_sindicato=email or f"{cpf[-2:]}@exemplo.org",
        quer_aviso=quer,
        processos=tuple(processos),
    )


def mov(numero: str, data: str, nome: str, grau: str = "G1") -> aviso.Movimento:
    return aviso.Movimento(numero=numero, grau=grau, data=data, nome=nome)


# ------------------------------------------------------------ quem recebe

def teste_so_quem_pediu_recebe():
    secao("quem recebe")
    r = aviso.preparar(
        [pessoa(A, quer=True), pessoa(B, quer=False)],
        [mov(P1, "2026-10-30", "Juntada de petição")],
        ja_avisados=set(),
        processos_conhecidos={P1},
    )
    destinos = {a.cpf for a in r.avisos}
    checa(destinos == {A}, f"escreveu para quem não pediu: {destinos}")
    print("  ok     só quem marcou o opt-in")


def teste_vai_para_o_email_do_sindicato():
    """Se fosse o digitado, bastaria cadastrar o CPF de outra pessoa com o
    próprio e-mail para passar a receber a movimentação do processo dela."""
    r = aviso.preparar(
        [pessoa(A, email="oficial@sindicato.exemplo.org")],
        [mov(P1, "2026-10-30", "Juntada de petição")],
        ja_avisados=set(), processos_conhecidos={P1},
    )
    checa(r.avisos[0].destino == "oficial@sindicato.exemplo.org",
          f"destino: {r.avisos[0].destino}")
    print("  ok     destino é o e-mail do sindicato")


def teste_sem_email_valido_ninguem_recebe_e_isso_e_reportado():
    """Não é erro silencioso: o sindicato precisa saber quem ficou sem
    aviso, porque é ele que corrige a base."""
    r = aviso.preparar(
        [pessoa(A, email="nao-e-email")],
        [mov(P1, "2026-10-30", "Juntada")],
        ja_avisados=set(), processos_conhecidos={P1},
    )
    checa(r.avisos == [], "mandou para e-mail que não serve")
    checa(any(A in s for s in r.sem_destino),
          f"não reportou quem ficou sem aviso: {r.sem_destino}")
    print("  ok     e-mail que não serve vira relatório, não silêncio")


def teste_quem_nao_tem_processo_nao_recebe():
    r = aviso.preparar(
        [pessoa(A, processos=())],
        [mov(P1, "2026-10-30", "Juntada")],
        ja_avisados=set(), processos_conhecidos={P1},
    )
    checa(r.avisos == [], f"avisou sobre processo que não é dela: {r.avisos}")
    print("  ok     sem processo, sem aviso")


def teste_cada_um_recebe_so_o_do_processo_dele():
    r = aviso.preparar(
        [pessoa(A, processos=(P1,)), pessoa(B, processos=(P2,))],
        [mov(P1, "2026-10-30", "Juntada no primeiro"),
         mov(P2, "2026-10-30", "Juntada no segundo")],
        ja_avisados=set(), processos_conhecidos={P1, P2},
    )
    por_cpf = {a.cpf: a for a in r.avisos}
    checa("primeiro" in por_cpf[A].corpo and "segundo" not in por_cpf[A].corpo,
          f"vazou o processo do outro: {por_cpf[A].corpo!r}")
    print("  ok     cada um recebe só o que é dele")


def teste_dois_filiados_no_mesmo_processo_recebem_os_dois():
    """É o caso NORMAL numa coletiva: o mesmo processo alcança milhares."""
    r = aviso.preparar(
        [pessoa(A, processos=(P1,)), pessoa(B, processos=(P1,))],
        [mov(P1, "2026-10-30", "Juntada de petição")],
        ja_avisados=set(), processos_conhecidos={P1},
    )
    checa({a.cpf for a in r.avisos} == {A, B},
          f"só um dos dois foi avisado: {[a.cpf for a in r.avisos]}")
    print("  ok     coletiva avisa todos os substituídos")


# ---------------------------------------------------- o que conta como novo

def teste_a_primeira_coleta_nao_avisa():
    """A ARMADILHA QUE ESTRAGA A ESTREIA. No dia em que o sindicato entra, a
    coleta traz o histórico inteiro — a GIFA tem 600 movimentos — e todo
    mundo receberia um e-mail com anos de andamento."""
    secao("o que conta como novo")
    historico = [mov(P1, f"2006-{m:02d}-01", f"Andamento {m}")
                 for m in range(1, 13)]
    r = aviso.preparar([pessoa(A)], historico,
                       ja_avisados=set(), processos_conhecidos=set())
    checa(r.avisos == [],
          f"avisou o histórico inteiro na primeira coleta: {r.avisos}")
    # E grava tudo como conhecido, para que o PRÓXIMO movimento seja novo.
    checa(len(r.novas_chaves) == 12,
          f"não guardou o histórico como conhecido: {len(r.novas_chaves)}")
    print(f"  ok     12 movimentos na estreia, 0 e-mails, 12 memorizados")


def teste_a_estreia_e_suprimida_para_sempre_nao_adiada_um_dia():
    """O DEFEITO QUE APARECEU SÓ NO VIVO. Marcar o processo como "conhecido"
    e parar aí não protege: na rodada seguinte o histórico continua
    não-avisado, e a pessoa recebe os 600 movimentos que a estreia evitara.
    A estreia tem de dizer QUAIS chaves ficam suprimidas, por pessoa."""
    historico = [mov(P1, f"2006-{m:02d}-01", f"Antigo {m}")
                 for m in range(1, 7)]
    r1 = aviso.preparar([pessoa(A)], historico,
                        ja_avisados=set(), processos_conhecidos=set())
    checa(r1.avisos == [], "avisou na estreia")
    checa(r1.estreia.get(A) and len(r1.estreia[A]) == 6,
          f"não disse o que suprimir por pessoa: {r1.estreia}")

    # A rodada seguinte, com o processo já conhecido e a supressão gravada.
    r2 = aviso.preparar([pessoa(A)], historico,
                        ja_avisados=r1.estreia[A],
                        processos_conhecidos={P1})
    checa(r2.avisos == [],
          f"a estreia virou e-mail um dia depois: {r2.avisos}")
    print("  ok     estreia suprimida para sempre, não adiada")


def teste_a_estreia_de_um_so_a_dele():
    """Quem não acompanha aquele processo não recebe supressão dele — e
    também não deve receber a chave na conta dela."""
    historico = [mov(P1, "2006-01-01", "Antigo")]
    r = aviso.preparar([pessoa(A, processos=(P1,)), pessoa(B, processos=(P2,))],
                       historico, ja_avisados=set(), processos_conhecidos=set())
    checa(A in r.estreia and B not in r.estreia,
          f"supressão foi para quem não acompanha o processo: {r.estreia}")
    print("  ok     supressão só de quem acompanha o processo")


def teste_depois_da_primeira_so_o_novo_avisa():
    historico = [mov(P1, "2006-01-01", "Antigo")]
    novo = mov(P1, "2026-10-30", "Sentença publicada")
    ja = {aviso.chave(m) for m in historico}
    r = aviso.preparar([pessoa(A)], historico + [novo],
                       ja_avisados=ja, processos_conhecidos={P1})
    checa(len(r.avisos) == 1, f"{r.avisos}")
    checa("Sentença publicada" in r.avisos[0].corpo, r.avisos[0].corpo)
    checa("Antigo" not in r.avisos[0].corpo,
          f"repetiu movimento já avisado: {r.avisos[0].corpo!r}")
    print("  ok     só o movimento novo entra")


def teste_rodar_duas_vezes_nao_avisa_duas_vezes():
    """O trabalho roda todo dia. Avisar de novo o mesmo andamento faria a
    pessoa desligar o aviso — e aí ela volta a ligar."""
    movimentos = [mov(P1, "2026-10-30", "Juntada")]
    r1 = aviso.preparar([pessoa(A)], movimentos,
                        ja_avisados=set(), processos_conhecidos={P1})
    r2 = aviso.preparar([pessoa(A)], movimentos,
                        ja_avisados=r1.novas_chaves,
                        processos_conhecidos={P1})
    checa(len(r1.avisos) == 1 and r2.avisos == [],
          f"a segunda rodada avisou de novo: {r2.avisos}")
    print("  ok     rodar de novo não repete")


def teste_tres_movimentos_viram_um_email_so():
    r = aviso.preparar(
        [pessoa(A)],
        [mov(P1, "2026-10-28", "Primeiro"),
         mov(P1, "2026-10-29", "Segundo"),
         mov(P1, "2026-10-30", "Terceiro")],
        ja_avisados={aviso.chave(mov(P1, "2000-01-01", "velho"))},
        processos_conhecidos={P1},
    )
    checa(len(r.avisos) == 1, f"mandou {len(r.avisos)} e-mails para 1 pessoa")
    corpo = r.avisos[0].corpo
    for esperado in ("Primeiro", "Segundo", "Terceiro"):
        checa(esperado in corpo, f"{esperado} não entrou: {corpo!r}")
    print("  ok     três andamentos, um e-mail")


def teste_os_movimentos_saem_do_mais_novo_para_o_mais_velho():
    """Quem abre o e-mail quer saber o que aconteceu por último."""
    r = aviso.preparar(
        [pessoa(A)],
        [mov(P1, "2026-10-28", "Mais velho"),
         mov(P1, "2026-10-30", "Mais novo")],
        ja_avisados={aviso.chave(mov(P1, "2000-01-01", "x"))},
        processos_conhecidos={P1},
    )
    corpo = r.avisos[0].corpo
    checa(corpo.index("Mais novo") < corpo.index("Mais velho"),
          f"ordem invertida: {corpo!r}")
    print("  ok     o mais recente primeiro")


# --------------------------------------------------- o que o texto não diz

def teste_o_texto_nunca_diz_intimacao_nem_prazo():
    """A movimentação tem cerca de um dia de atraso e não substitui
    publicação. Dizer o contrário faria alguém perder prazo confiando na
    gente — e esse erro não se conserta."""
    secao("o que o texto não diz")
    r = aviso.preparar(
        [pessoa(A)], [mov(P1, "2026-10-30", "Juntada")],
        ja_avisados=set(), processos_conhecidos={P1},
    )
    corpo = r.avisos[0].corpo.lower()
    # O proibido é AFIRMAR que é intimação, não a palavra: o texto certo
    # usa a palavra justamente para negá-la. Proibir o termo faria o teste
    # reprovar a frase que protege a pessoa.
    for proibido in ("é uma intimação", "e uma intimacao",
                     "esta intimação", "serve como intimação",
                     "prazo começa", "prazo comeca",
                     "você tem até", "voce tem ate"):
        checa(proibido not in corpo, f"o texto afirma {proibido!r}: {corpo!r}")
    checa("não é intimação" in corpo or "nao e intimacao" in corpo,
          f"o texto não nega ser intimação: {corpo!r}")
    checa("não substitui" in corpo or "nao substitui" in corpo,
          f"o texto não diz que não substitui publicação: {corpo!r}")
    checa("prazo" in corpo,
          "o texto não fala de prazo nenhum — é justamente aí que alguém "
          "se engana")
    print("  ok     não é intimação, e o texto diz isso")


def teste_o_texto_nao_fala_de_escritorio():
    r = aviso.preparar(
        [pessoa(A)], [mov(P1, "2026-10-30", "Juntada")],
        ja_avisados=set(), processos_conhecidos={P1},
    )
    for texto in (r.avisos[0].corpo, r.avisos[0].assunto):
        checa("escritóri" not in texto.lower(),
              f"REGRA ZERO: {texto!r}")
    print("  ok     quem fala com o filiado é o sindicato")


def teste_o_assunto_nao_vaza_o_conteudo():
    """O assunto aparece na notificação do celular, na tela de bloqueio, e
    numa caixa de e-mail que outra pessoa pode estar olhando. "Penhora de
    bens" ali é vazamento sem precisar abrir nada."""
    r = aviso.preparar(
        [pessoa(A)], [mov(P1, "2026-10-30", "Penhora de bens determinada")],
        ja_avisados=set(), processos_conhecidos={P1},
    )
    assunto = r.avisos[0].assunto
    checa("Penhora" not in assunto, f"o assunto vaza o andamento: {assunto!r}")
    checa(len(assunto) < 90, f"assunto longo demais: {assunto!r}")
    checa(bool(assunto.strip()), "assunto vazio")
    print(f"  ok     {assunto!r}")


def teste_o_texto_diz_como_ver_o_resto():
    """Avisar sem dizer onde olhar é gerar a ligação que se queria evitar."""
    r = aviso.preparar(
        [pessoa(A)], [mov(P1, "2026-10-30", "Juntada")],
        ja_avisados=set(), processos_conhecidos={P1},
        endereco="https://portal.exemplo.org/?entidade=demo-a",
    )
    checa("portal.exemplo.org" in r.avisos[0].corpo,
          f"não diz onde ver: {r.avisos[0].corpo!r}")
    print("  ok     o e-mail diz onde ver o resto")


def teste_sem_endereco_o_texto_nao_inventa_link():
    r = aviso.preparar(
        [pessoa(A)], [mov(P1, "2026-10-30", "Juntada")],
        ja_avisados=set(), processos_conhecidos={P1},
    )
    checa("http" not in r.avisos[0].corpo,
          f"inventou um endereço: {r.avisos[0].corpo!r}")
    print("  ok     sem endereço configurado, nenhum link inventado")


TESTES = [
    teste_so_quem_pediu_recebe,
    teste_vai_para_o_email_do_sindicato,
    teste_sem_email_valido_ninguem_recebe_e_isso_e_reportado,
    teste_quem_nao_tem_processo_nao_recebe,
    teste_cada_um_recebe_so_o_do_processo_dele,
    teste_dois_filiados_no_mesmo_processo_recebem_os_dois,
    teste_a_primeira_coleta_nao_avisa,
    teste_a_estreia_e_suprimida_para_sempre_nao_adiada_um_dia,
    teste_a_estreia_de_um_so_a_dele,
    teste_depois_da_primeira_so_o_novo_avisa,
    teste_rodar_duas_vezes_nao_avisa_duas_vezes,
    teste_tres_movimentos_viram_um_email_so,
    teste_os_movimentos_saem_do_mais_novo_para_o_mais_velho,
    teste_o_texto_nunca_diz_intimacao_nem_prazo,
    teste_o_texto_nao_fala_de_escritorio,
    teste_o_assunto_nao_vaza_o_conteudo,
    teste_o_texto_diz_como_ver_o_resto,
    teste_sem_endereco_o_texto_nao_inventa_link,
]


def main() -> int:
    print("=" * 62)
    print("O AVISO DE MOVIMENTAÇÃO")
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
