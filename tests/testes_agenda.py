#!/usr/bin/env python3
"""
O AGENDADOR — e o problema que ele cria ao existir.

Os dois trabalhos existiam e funcionavam, e ninguém os chamava. Comando que
alguém precisa lembrar de rodar é comando que não roda: o aviso ficava
pronto, correto e mudo.

MAS O RISCO DE VERDADE NÃO É ESQUECER DE AGENDAR — é o agendador MORRER
CALADO. O produto continua prometendo aviso na tela de cadastro, a pessoa
continua marcando o opt-in, e ninguém recebe nada. Ninguém percebe até o
primeiro telefonema perguntando por uma sentença de três meses atrás.

Por isso este módulo não é só um laço com `sleep`. Ele:

    GRAVA CADA EXECUÇÃO     início, fim, estado e detalhe
    USA ARRENDAMENTO        duas instâncias do servidor não rodam a mesma
                            coisa duas vezes, e o arrendamento EXPIRA, então
                            um processo que morreu no meio não trava o
                            trabalho para sempre
    DIZ QUANDO FALHOU       e por quanto tempo está sem rodar bem

A trava do arrendamento é de banco, não de memória: duas instâncias não
compartilham memória, e é justamente com duas que o problema aparece.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

URL = os.environ.get("PROTOCOL_DATABASE_URL", "").strip()

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def preparar():
    from servidor import banco

    banco.criar_esquema(URL, recriar=True)


def limpar():
    """Entre testes. O arrendamento dura 60 s de propósito em alguns casos,
    e sem limpar o teste seguinte herdaria a trava do anterior — falhando
    por um motivo que não é o dele."""
    from servidor import banco

    for entidade in ("demo-a", "demo-b"):
        with banco.sessao(URL, entidade) as cur:
            cur.execute("DELETE FROM execucao")


# ----------------------------------------------------------- o arrendamento

def teste_duas_instancias_so_uma_roda():
    """O caso que só aparece com duas: o servidor sobe em duas instâncias e
    cada uma tem o seu relógio. Sem trava, a pessoa recebe dois e-mails."""
    secao("o arrendamento")
    from servidor import agenda

    primeira = agenda.assumir(URL, "demo-a", "avisar", segundos=60)
    segunda = agenda.assumir(URL, "demo-a", "avisar", segundos=60)
    checa(primeira is True, "a primeira instância não conseguiu assumir")
    checa(segunda is False, "as duas instâncias assumiram o mesmo trabalho")
    print("  ok     uma assume, a outra não")


def teste_o_arrendamento_expira():
    """Um processo que morre no meio não pode travar o trabalho para sempre.
    Reiniciar o servidor não deve exigir mexer no banco à mão."""
    from servidor import agenda

    checa(agenda.assumir(URL, "demo-a", "coletar", segundos=1) is True,
          "não assumiu")
    checa(agenda.assumir(URL, "demo-a", "coletar", segundos=1) is False,
          "assumiu duas vezes dentro do prazo")
    time.sleep(1.2)
    checa(agenda.assumir(URL, "demo-a", "coletar", segundos=60) is True,
          "o arrendamento não expirou, e um processo morto travaria tudo")
    print("  ok     arrendamento expira sozinho")


def teste_entidades_nao_disputam_o_mesmo_arrendamento():
    from servidor import agenda

    checa(agenda.assumir(URL, "demo-a", "avisar", segundos=60) is True, "A")
    checa(agenda.assumir(URL, "demo-b", "avisar", segundos=60) is True,
          "a entidade B ficou esperando a trava da entidade A")
    print("  ok     cada entidade tem o seu")


# -------------------------------------------------------- o registro da corrida

def teste_a_execucao_boa_fica_registrada():
    secao("o registro")
    from servidor import agenda

    agenda.assumir(URL, "demo-a", "avisar", segundos=60)
    agenda.registrar(URL, "demo-a", "avisar", ok=True, detalhe="3 e-mails")
    ultima = agenda.ultima_boa(URL, "demo-a", "avisar")
    checa(ultima is not None, "a execução boa não ficou registrada")
    print(f"  ok     última boa: {ultima}")


def teste_a_execucao_que_falhou_nao_vira_ultima_boa():
    """É a confusão que esconde o problema: contar a tentativa como sucesso
    faria o painel dizer "rodou hoje" enquanto ninguém é avisado há semanas."""
    from servidor import agenda

    agenda.registrar(URL, "demo-a", "coletar", ok=True, detalhe="ok")
    boa = agenda.ultima_boa(URL, "demo-a", "coletar")
    agenda.registrar(URL, "demo-a", "coletar", ok=False,
                     detalhe="DataJud fora do ar")
    depois = agenda.ultima_boa(URL, "demo-a", "coletar")
    checa(boa == depois,
          "uma execução que FALHOU virou a última execução boa")
    print("  ok     falha não conta como sucesso")


def teste_o_detalhe_da_falha_sobrevive():
    """Quem for olhar precisa saber o que aconteceu, não só que deu errado."""
    from servidor import agenda

    agenda.registrar(URL, "demo-a", "coletar", ok=False,
                     detalhe="tribunal TRF1 devolveu 503")
    estado = agenda.estado(URL, "demo-a")
    coletar = [e for e in estado if e["tarefa"] == "coletar"][0]
    checa("TRF1" in (coletar["ultimo_detalhe"] or ""),
          f"o detalhe sumiu: {coletar}")
    checa(coletar["ultima_falhou"] is True, f"{coletar}")
    print("  ok     o detalhe da falha sobrevive")


# ------------------------------------------------- o silêncio é o inimigo

def teste_quem_nunca_rodou_aparece_como_atrasado():
    """O estado mais perigoso é o que parece vazio. Um trabalho que NUNCA
    rodou e um que roda bem todo dia não podem aparecer iguais."""
    secao("o silêncio é o inimigo")
    from servidor import agenda

    estado = agenda.estado(URL, "demo-b")
    por_tarefa = {e["tarefa"]: e for e in estado}
    for tarefa in agenda.TAREFAS:
        checa(tarefa in por_tarefa,
              f"{tarefa} não aparece no estado de quem nunca rodou")
        checa(por_tarefa[tarefa]["atrasado"] is True,
              f"{tarefa} nunca rodou e não está marcado como atrasado")
        checa(por_tarefa[tarefa]["ultima_boa"] is None, f"{tarefa}")
    print(f"  ok     {len(agenda.TAREFAS)} tarefas, todas atrasadas e visíveis")


def teste_quem_rodou_agora_nao_esta_atrasado():
    from servidor import agenda

    for tarefa in agenda.TAREFAS:
        agenda.registrar(URL, "demo-b", tarefa, ok=True, detalhe="ok")
    estado = agenda.estado(URL, "demo-b")
    checa(all(not e["atrasado"] for e in estado),
          f"marcou como atrasado quem acabou de rodar: {estado}")
    print("  ok     quem rodou agora não está atrasado")


def teste_o_atraso_tem_limite_declarado_nao_chutado():
    """O limite não pode ser adivinhado por quem lê a tela: o trabalho roda
    uma vez por dia, e o alarme tem de tocar antes de alguém reclamar."""
    from servidor import agenda

    checa(agenda.TOLERANCIA_HORAS >= 24,
          f"tolerância de {agenda.TOLERANCIA_HORAS}h dispararia alarme "
          f"falso num trabalho diário")
    checa(agenda.TOLERANCIA_HORAS <= 72,
          f"tolerância de {agenda.TOLERANCIA_HORAS}h deixaria três dias de "
          f"silêncio passarem por normais")
    print(f"  ok     tolerância declarada: {agenda.TOLERANCIA_HORAS}h")


# -------------------------------------------------- o laço não pode morrer

def teste_tarefa_que_estoura_nao_derruba_o_agendador():
    """Se uma exceção matasse o laço, o produto continuaria prometendo aviso
    na tela de cadastro e ninguém receberia nada — calado."""
    secao("o laço não morre")
    from servidor import agenda

    chamadas = []

    def explode(entidade):
        chamadas.append("explode")
        raise RuntimeError("falha de propósito")

    def funciona(entidade):
        chamadas.append("funciona")
        return "2 e-mails"

    agenda.rodar_uma_vez(URL, "demo-a",
                         {"coletar": explode, "avisar": funciona})
    checa(chamadas == ["explode", "funciona"],
          f"a exceção impediu a tarefa seguinte: {chamadas}")
    estado = {e["tarefa"]: e for e in agenda.estado(URL, "demo-a")}
    checa(estado["coletar"]["ultima_falhou"] is True,
          "a tarefa que estourou não ficou registrada como falha")
    checa(estado["avisar"]["ultima_falhou"] is False,
          "a tarefa boa foi marcada como falha")
    print("  ok     uma tarefa estoura, a outra roda, e as duas ficam no log")


def teste_a_ordem_e_coletar_depois_avisar():
    """Avisar antes de coletar avisaria sobre o que chegou ontem, sempre um
    dia atrasado."""
    from servidor import agenda

    checa(list(agenda.TAREFAS) == ["coletar", "avisar"],
          f"a ordem está trocada: {agenda.TAREFAS}")
    print("  ok     coleta primeiro, aviso depois")


TESTES = [
    teste_duas_instancias_so_uma_roda,
    teste_o_arrendamento_expira,
    teste_entidades_nao_disputam_o_mesmo_arrendamento,
    teste_a_execucao_boa_fica_registrada,
    teste_a_execucao_que_falhou_nao_vira_ultima_boa,
    teste_o_detalhe_da_falha_sobrevive,
    teste_quem_nunca_rodou_aparece_como_atrasado,
    teste_quem_rodou_agora_nao_esta_atrasado,
    teste_o_atraso_tem_limite_declarado_nao_chutado,
    teste_tarefa_que_estoura_nao_derruba_o_agendador,
    teste_a_ordem_e_coletar_depois_avisar,
]


def main() -> int:
    print("=" * 62)
    print("O AGENDADOR, E O SILÊNCIO QUE ELE PODE CRIAR")
    print("=" * 62)
    if not URL:
        print("\nPULADO: sem PROTOCOL_DATABASE_URL.")
        print("Suíte pulada NÃO está testada.")
        return 0
    # O teste do laço provoca uma exceção DE PROPÓSITO, e o módulo a
    # registra com traceback — em produção é o certo; aqui, só parece falha.
    logging.getLogger("protocol.agenda").setLevel(logging.CRITICAL)
    preparar()
    for t in TESTES:
        try:
            limpar()
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
