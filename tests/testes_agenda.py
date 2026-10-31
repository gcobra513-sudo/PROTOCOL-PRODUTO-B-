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
import subprocess
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
    """Quem for olhar precisa saber o que aconteceu, não só que deu errado.

    MUDOU O CANAL, NÃO A EXIGÊNCIA. Este teste lia o detalhe por
    `agenda.estado`, que é o que alimenta `/saude` — rota sem sessão. O
    detalhe continua tendo de sobreviver, e continua sendo conferido aqui;
    só passa a ser lido por `agenda.detalhe`, que é canal de operador e
    declara isso no nome.
    """
    from servidor import agenda

    agenda.registrar(URL, "demo-a", "coletar", ok=False,
                     detalhe="tribunal TRF1 devolveu 503")
    checa("TRF1" in agenda.detalhe(URL, "demo-a", "coletar"),
          "o detalhe da falha sumiu do canal de operador")
    estado = agenda.estado(URL, "demo-a")
    coletar = [e for e in estado if e["tarefa"] == "coletar"][0]
    checa(coletar["ultima_falhou"] is True, f"{coletar}")
    checa("ultimo_detalhe" not in coletar,
          f"o detalhe voltou para o canal do monitor: {coletar}")
    print("  ok     o detalhe sobrevive, no canal de operador")


def teste_a_falha_nao_grava_a_mensagem_da_excecao():
    """A MENSAGEM DE UMA EXCEÇÃO CARREGA O QUE ELA QUISER.

    `subprocess.TimeoutExpired.__str__` embute a lista inteira de
    argumentos. Como a URL do banco ia em `--banco`, a senha chegava a esta
    coluna e saía por `/saude`, que não exige sessão. Auditoria independente
    leu a credencial completa por um GET anônimo.

    Gravar o tipo basta para quem monitora; o texto inteiro está no log.
    """
    from servidor import agenda

    SENHA = "SENHA-FICTICIA-DE-EXEMPLO"
    CPF = "11144477735"       # CPF de teste; não é de ninguém

    def estoura(entidade):
        raise subprocess.TimeoutExpired(
            ["python3", "--banco",
             f"postgresql://postgres:{SENHA}@exemplo.invalid/x",
             "--cpf", CPF],
            3540,
        )

    agenda.rodar_uma_vez(URL, "demo-a", {"coletar": estoura})
    guardado = agenda.detalhe(URL, "demo-a", "coletar")
    checa(SENHA not in guardado,
          f"a senha do banco foi gravada na coluna: {guardado}")
    checa(CPF not in guardado, f"o CPF foi gravado na coluna: {guardado}")
    checa("TimeoutExpired" in guardado,
          f"perdeu a informação de QUE tipo de falha foi: {guardado}")
    estado = [e for e in agenda.estado(URL, "demo-a")
              if e["tarefa"] == "coletar"][0]
    checa(estado["ultima_falhou"] is True,
          f"perdeu o sinal de que falhou: {estado}")
    print("  ok     a falha grava o tipo, nunca a mensagem")


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


# ------------------------------------- as travas valem em TODO caminho

def _cfg(raiz, *, modo_ensaio: bool, regiao: str, banco: str = ""):
    from servidor import config

    return config.Config(
        raiz=raiz, segredo="segredo-de-teste", modo_ensaio=modo_ensaio,
        origens=(), smtp_host="", smtp_porta=0, smtp_usuario="",
        smtp_senha="", smtp_remetente="",
        regiao=regiao, banco_url=banco if banco else URL,
    )


def teste_o_laco_recusa_a_entidade_que_o_http_recusa():
    """AS TRAVAS NÃO PODEM VALER SÓ NO HTTP.

    As três travas de código — ensaio, região e auditoria — viviam dentro de
    `app._entidade`, e `_entidade` só é chamada por rota HTTP. O laço deste
    módulo resolvia entidade por `Cadastro.todas()` e não passava por
    nenhuma delas. Auditoria independente observou o MESMO servidor devolver
    403 para um sindicato e, no mesmo processo, ler os dados nominais dele e
    MANDAR O E-MAIL com movimentação processual.

    `MAPA.md` diz, sobre o servidor que roda fora do Brasil: "não é
    promessa, é impedimento". Era impedimento no HTTP; no caminho que manda
    e-mail, não era.

    E a demonstração continua rodando nos dois casos, que é o ponto: a
    correção não pode ser desligar o laço.
    """
    secao("as travas valem em todo caminho")
    import tempfile

    from servidor import agenda, entidades

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        cad = entidades.Cadastro(raiz)
        cad.criar("demo-a", "Demonstração")
        cad.criar("sindicato-ficticio", "Sindicato Fictício de Exemplo")

        from servidor import banco

        for rotulo, cfg in (
            ("ensaio", _cfg(raiz, modo_ensaio=True, regiao="sa-east-1")),
            ("região", _cfg(raiz, modo_ensaio=False, regiao="us-east-1")),
        ):
            # ZERA O ESTADO ENTRE OS DOIS CASOS. Sem isto o segundo caso
            # encontrava `demo-a` como já rodada no primeiro, portanto não
            # vencida, e a demonstração "não rodava" por um motivo que não
            # era o do teste.
            for quem in ("demo-a", "sindicato-ficticio"):
                with banco.sessao(URL, quem) as cur:
                    cur.execute("DELETE FROM execucao")
            rodou: list[str] = []

            def anota(ent, _r=rodou):
                _r.append(ent)
                return "ok"

            agenda.uma_rodada(cfg, {"coletar": anota, "avisar": anota})
            checa("sindicato-ficticio" not in rodou,
                  f"[{rotulo}] o laço processou entidade que o HTTP recusa: "
                  f"{rodou}")
            checa("demo-a" in rodou,
                  f"[{rotulo}] a correção derrubou a demonstração junto: "
                  f"{rodou}")

        # E A RECUSA APARECE. Pular calado faria a entidade desaparecer do
        # painel, e é o silêncio que este módulo existe para impedir.
        estado = agenda.estado(URL, "sindicato-ficticio")
        checa(all(e["atrasado"] for e in estado),
              f"a entidade recusada não aparece como atrasada: {estado}")
        guardado = agenda.detalhe(URL, "sindicato-ficticio", "avisar")
        checa("recus" in guardado.lower(),
              f"o registro não diz que foi recusada: {guardado!r}")
    print("  ok     o laço aplica as mesmas travas do HTTP")


def teste_a_trava_e_uma_so_decisao_para_os_dois_caminhos():
    """Uma trava copiada em dois lugares divergente é questão de tempo.

    Foi exatamente assim que este defeito nasceu: a regra estava escrita
    numa porta e não na outra. A decisão passa a ser UMA função, e os dois
    caminhos a chamam.
    """
    from servidor import entidades

    checa(hasattr(entidades, "atendivel"),
          "não existe uma decisão única sobre atender a entidade")

    with __import__("tempfile").TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        cad = entidades.Cadastro(raiz)
        demo = cad.criar("demo-a", "Demonstração")
        real = cad.criar("sindicato-ficticio", "Sindicato Fictício")

        em_ensaio = _cfg(raiz, modo_ensaio=True, regiao="sa-east-1")
        checa(entidades.atendivel(demo, em_ensaio) is None,
              "a demonstração foi recusada em ensaio")
        recusa = entidades.atendivel(real, em_ensaio)
        checa(recusa is not None and recusa.estado == 403,
              f"ensaio devia recusar entidade real com 403: {recusa}")

        fora = _cfg(raiz, modo_ensaio=False, regiao="us-east-1")
        recusa = entidades.atendivel(real, fora)
        checa(recusa is not None and recusa.estado == 503,
              f"região estrangeira devia recusar com 503: {recusa}")

        sem_banco = _cfg(raiz, modo_ensaio=False, regiao="sa-east-1",
                         banco="-")
        sem_banco = __import__("dataclasses").replace(sem_banco, banco_url="")
        recusa = entidades.atendivel(real, sem_banco)
        checa(recusa is not None and recusa.estado == 503,
              f"sem banco devia recusar com 503: {recusa}")

        bom = _cfg(raiz, modo_ensaio=False, regiao="sa-east-1")
        checa(entidades.atendivel(real, bom) is None,
              "recusou entidade real num servidor que cumpre as três travas")
    print("  ok     uma decisão, dois caminhos")


TESTES = [
    teste_duas_instancias_so_uma_roda,
    teste_o_arrendamento_expira,
    teste_entidades_nao_disputam_o_mesmo_arrendamento,
    teste_a_execucao_boa_fica_registrada,
    teste_a_execucao_que_falhou_nao_vira_ultima_boa,
    teste_o_detalhe_da_falha_sobrevive,
    teste_a_falha_nao_grava_a_mensagem_da_excecao,
    teste_quem_nunca_rodou_aparece_como_atrasado,
    teste_quem_rodou_agora_nao_esta_atrasado,
    teste_o_atraso_tem_limite_declarado_nao_chutado,
    teste_tarefa_que_estoura_nao_derruba_o_agendador,
    teste_a_ordem_e_coletar_depois_avisar,
    teste_o_laco_recusa_a_entidade_que_o_http_recusa,
    teste_a_trava_e_uma_so_decisao_para_os_dois_caminhos,
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
