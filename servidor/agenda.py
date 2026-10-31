"""
O trabalho de fundo, e o silêncio que ele pode criar.

Os dois trabalhos — coletar a movimentação e avisar quem pediu — existiam,
funcionavam, e ninguém os chamava. Comando que alguém precisa lembrar de
rodar é comando que não roda: o aviso ficava pronto, correto e mudo.

**MAS O RISCO DE VERDADE NÃO É ESQUECER DE AGENDAR.** É o agendador morrer
calado. O produto continua prometendo aviso na tela de cadastro, a pessoa
continua marcando o opt-in, e ninguém recebe nada — até o primeiro telefonema
perguntando por uma sentença de três meses atrás. Um trabalho que nunca rodou
e um que roda bem todo dia NÃO PODEM APARECER IGUAIS em lugar nenhum.

Por isso aqui não há só um laço com `sleep`:

    GRAVA CADA EXECUÇÃO  quando, como foi, e o detalhe de quando foi mal
    ARRENDA O TRABALHO   duas instâncias do servidor não rodam a mesma coisa
                         duas vezes — e o arrendamento EXPIRA, para que um
                         processo morto no meio não trave tudo para sempre
    DECLARA O ATRASO     `estado()` diz quem está sem rodar bem, e há quanto

A trava é de BANCO e não de memória, porque duas instâncias não compartilham
memória — e é com duas que o problema aparece.

A ORDEM É COLETAR, DEPOIS AVISAR. Avisar antes de coletar avisaria sobre o
que chegou ontem, sempre um dia atrasado. E os dois são separados de
propósito: se o DataJud cair, a coleta falha e quem já tinha novidade
guardada continua sendo avisado.
"""
from __future__ import annotations

import datetime as dt
import logging

from .banco import sessao

log = logging.getLogger("protocol.agenda")

#: Na ordem em que rodam.
TAREFAS = ("coletar", "avisar")

#: A partir de quanto tempo sem uma execução BOA o trabalho conta como
#: atrasado. Os trabalhos são diários: menos que 24h daria alarme falso a
#: cada variação de horário; mais que três dias deixaria um fim de semana
#: inteiro de silêncio passar por normal.
TOLERANCIA_HORAS = 36

#: Por quanto tempo uma instância segura o trabalho. Maior que a execução
#: mais longa que se espera — a coleta leva de 22 a 43 s por processo,
#: medidos —, e curto o bastante para que uma instância morta não bloqueie a
#: rodada do dia seguinte.
ARRENDAMENTO_SEGUNDOS = 3600


def assumir(url: str, entidade: str, tarefa: str,
            segundos: int = ARRENDAMENTO_SEGUNDOS) -> bool:
    """Tenta ficar com o trabalho. `False` quer dizer "outra instância está".

    O `WHERE` do `DO UPDATE` é a trava inteira: ele só deixa assumir quando
    não há arrendamento ou quando o que havia já venceu. Duas instâncias
    chegando juntas disputam a MESMA linha, e o banco serializa — que é
    exatamente o que memória nenhuma faria.
    """
    with sessao(url, entidade) as cur:
        cur.execute(
            "INSERT INTO execucao (entidade, tarefa, arrendado_ate) "
            "VALUES (%s, %s, now() + make_interval(secs => %s)) "
            "ON CONFLICT (entidade, tarefa) DO UPDATE SET "
            "  arrendado_ate = now() + make_interval(secs => %s) "
            "WHERE execucao.arrendado_ate IS NULL "
            "   OR execucao.arrendado_ate < now()",
            (entidade, tarefa, segundos, segundos),
        )
        return cur.rowcount > 0


def registrar(url: str, entidade: str, tarefa: str, ok: bool,
              detalhe: str = "") -> None:
    """O resultado da execução, e ele é o produto desta tabela.

    `ultima_boa` só anda quando `ok`. Contar a tentativa como sucesso faria o
    painel dizer "rodou hoje" enquanto ninguém é avisado há semanas — que é
    precisamente o engano que este módulo existe para impedir.
    """
    with sessao(url, entidade) as cur:
        cur.execute(
            "INSERT INTO execucao (entidade, tarefa, ultima_em, ultima_ok, "
            "ultimo_detalhe, ultima_boa, arrendado_ate) "
            "VALUES (%s,%s, now(), %s, %s, CASE WHEN %s THEN now() END, NULL) "
            "ON CONFLICT (entidade, tarefa) DO UPDATE SET "
            "  ultima_em = now(), ultima_ok = EXCLUDED.ultima_ok, "
            "  ultimo_detalhe = EXCLUDED.ultimo_detalhe, "
            "  ultima_boa = CASE WHEN EXCLUDED.ultima_ok "
            "                    THEN now() ELSE execucao.ultima_boa END, "
            "  arrendado_ate = NULL",
            (entidade, tarefa, ok, detalhe[:500], ok),
        )


def ultima_boa(url: str, entidade: str, tarefa: str):
    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT ultima_boa FROM execucao WHERE tarefa = %s", (tarefa,)
        )
        linha = cur.fetchone()
        return linha[0] if linha else None


def estado(url: str, entidade: str) -> list[dict]:
    """O estado de TODAS as tarefas, inclusive as que nunca rodaram.

    Tarefa que nunca rodou aparece, e aparece como ATRASADA. O estado mais
    perigoso é o que parece vazio: uma lista sem a tarefa faria quem lê
    concluir que não há nada a fazer.
    """
    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT tarefa, ultima_boa, ultima_em, ultima_ok FROM execucao"
        )
        por_tarefa = {t: (b, e, k) for t, b, e, k in cur.fetchall()}

    agora = dt.datetime.now(dt.UTC)
    saida = []
    for tarefa in TAREFAS:
        boa, em, ok = por_tarefa.get(tarefa, (None, None, None))
        atrasado = (
            boa is None
            or (agora - boa) > dt.timedelta(hours=TOLERANCIA_HORAS)
        )
        # `ultimo_detalhe` NÃO SAI DAQUI, e a coluna continua existindo.
        # Esta função alimenta `/saude`, que não exige sessão, e o detalhe
        # era o stdout cru do subprocesso: o de `avisar_movimentacao.py`
        # termina listando CPF e e-mail de quem ficou sem aviso, e o do
        # caminho de tempo esgotado carregava a linha de comando inteira,
        # com a URL do banco e a senha. Auditoria independente leu os dois
        # por um GET sem cabeçalho nenhum. "Estado" é se a tarefa rodou e
        # quando; o conteúdo da execução é outra coisa, e tem outro dono.
        saida.append({
            "tarefa": tarefa,
            "ultima_boa": boa.isoformat() if boa else None,
            "ultima_em": em.isoformat() if em else None,
            "ultima_falhou": ok is False,
            "atrasado": atrasado,
        })
    return saida


def detalhe(url: str, entidade: str, tarefa: str) -> str:
    """O detalhe da última execução — CANAL DE OPERADOR, não de monitor.

    Existe separado de `estado` de propósito. `estado` alimenta `/saude`,
    que não exige sessão; este detalhe pode conter o que a execução disse,
    e quem o lê tem de ser alguém com direito a ler. Chamar daqui é a
    decisão explícita de que o chamador é esse alguém.
    """
    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT ultimo_detalhe FROM execucao WHERE tarefa = %s", (tarefa,)
        )
        linha = cur.fetchone()
    return (linha[0] if linha else "") or ""


def rodar_uma_vez(url: str, entidade: str, tarefas: dict) -> None:
    """Roda as tarefas desta entidade, uma vez, na ordem.

    **UMA EXCEÇÃO NÃO PODE MATAR O LAÇO.** Se matasse, o produto continuaria
    prometendo aviso na tela de cadastro e ninguém receberia nada — calado, e
    por tempo indeterminado. Cada tarefa é isolada, e a falha vira linha no
    registro em vez de fim do agendador.
    """
    for tarefa in TAREFAS:
        funcao = tarefas.get(tarefa)
        if funcao is None:
            continue
        if not assumir(url, entidade, tarefa):
            log.info("tarefa %s de %s já está com outra instância",
                     tarefa, entidade)
            continue
        try:
            saiu = funcao(entidade) or ""
        except Exception as e:  # noqa: BLE001
            log.exception("tarefa %s de %s falhou", tarefa, entidade)
            # SÓ O TIPO DA EXCEÇÃO, nunca a mensagem. A mensagem de uma
            # exceção arbitrária carrega o que ela quiser: a de
            # `TimeoutExpired` carrega a linha de comando inteira, e assim
            # a URL do banco COM SENHA chegou a esta coluna e saiu por uma
            # rota sem sessão. O texto completo está no log, uma linha
            # acima, que é onde o operador olha.
            registrar(url, entidade, tarefa, ok=False,
                      detalhe=f"falhou: {type(e).__name__}")
            continue
        registrar(url, entidade, tarefa, ok=True, detalhe=str(saiu)[:200])


# =====================================================================
# O LAÇO, E COMO ELE SOBE COM O SERVIDOR
# =====================================================================

#: De quanto em quanto tempo o laço acorda. Ele não "roda a cada 6 horas":
#: ele ACORDA a cada 6 horas e só trabalha se já passou o intervalo — assim
#: reiniciar o servidor não dispara uma rodada extra, e perder uma janela
#: não espera um dia inteiro para se recuperar.
ACORDAR_SEGUNDOS = 6 * 3600
#: Quanto tempo tem de ter passado desde a última execução BOA.
INTERVALO_HORAS = 20


def _vencida(url: str, entidade: str, tarefa: str) -> bool:
    import datetime as _dt

    boa = ultima_boa(url, entidade, tarefa)
    if boa is None:
        return True
    return (_dt.datetime.now(_dt.UTC) - boa) >= _dt.timedelta(
        hours=INTERVALO_HORAS
    )


def tarefas_padrao(cfg):
    """As duas tarefas, ligadas às ferramentas que já existem.

    Chamam os mesmos programas que alguém rodaria à mão: o agendador não é um
    segundo caminho para a mesma coisa. Dois caminhos divergem, e o que roda
    sozinho é o que ninguém olha.
    """
    import os as _os
    import subprocess
    import sys as _sys
    from pathlib import Path as _Path

    raiz_do_repo = _Path(__file__).resolve().parent.parent

    def _rodar(programa: str, extra: list[str]):
        def executar(entidade: str) -> str:
            comando = [
                _sys.executable, str(raiz_do_repo / "ferramentas" / programa),
                "--entidade", entidade, "--raiz", str(cfg.raiz),
            ] + extra
            # A CREDENCIAL VAI PELO AMBIENTE, NÃO PELA LINHA DE COMANDO.
            # Em `argv` ela aparecia em `/proc/<pid>/cmdline` e, pior, no
            # `str()` de `TimeoutExpired`, que carrega a lista inteira de
            # argumentos — e esse texto era gravado e servido sem sessão.
            # As duas ferramentas já leem PROTOCOL_DATABASE_URL por padrão;
            # passar explícito mantém o comportamento mesmo quando a
            # `Config` foi montada em código, e não só lida do ambiente.
            ambiente = dict(_os.environ)
            if cfg.banco_url:
                ambiente["PROTOCOL_DATABASE_URL"] = cfg.banco_url
            r = subprocess.run(comando, capture_output=True, text=True,
                               timeout=ARRENDAMENTO_SEGUNDOS - 60,
                               env=ambiente)
            # O STDOUT DESTAS FERRAMENTAS É RELATÓRIO PARA HUMANO, e por
            # desenho contém CPF e e-mail de quem ficou sem aviso, e
            # números de processo. Ele vai para o LOG, que é canal de
            # operador, e nunca para o `detalhe`, que é coluna lida por
            # quem monitora. O agendador precisa do código de saída.
            if r.stdout and r.stdout.strip():
                log.info("%s em %s: %s", programa, entidade,
                         r.stdout.strip())
            if r.stderr and r.stderr.strip():
                log.warning("%s em %s (stderr): %s", programa, entidade,
                            r.stderr.strip())
            if r.returncode not in (0, 1):
                raise RuntimeError(f"{programa} saiu com {r.returncode}")
            # Código 1 é "rodou, mas algo ficou de fora" — e isso É uma falha
            # para o registro: alguém tem de olhar, e é o registro que avisa.
            # O QUE ficou de fora está no log, não aqui.
            if r.returncode == 1:
                raise RuntimeError(f"{programa} saiu com 1")
            return f"{programa} saiu com 0"
        return executar

    return {
        "coletar": _rodar("coletar_movimentacao.py", []),
        "avisar": _rodar("avisar_movimentacao.py",
                         ["--portal", cfg.portal] if cfg.portal else []),
    }


def uma_rodada(cfg, tarefas) -> None:
    """Uma passada por todas as entidades do cadastro.

    FORA DO LAÇO de propósito, para poder ser exercitada por teste. Era um
    fecho dentro de `subir`, e foi exatamente onde o defeito morou sem ser
    visto: nenhum teste conseguia chegar aqui.

    APLICA AS MESMAS TRAVAS DO HTTP. Elas moravam em `app._entidade`, que só
    é chamada por rota, e este caminho resolvia entidade por
    `Cadastro.todas()`. O mesmo servidor recusava um sindicato por HTTP e
    aqui lia os dados nominais dele e mandava o e-mail.
    """
    from . import entidades as mod_entidades

    cadastro = mod_entidades.Cadastro(cfg.raiz)
    for ent in cadastro.todas():
        if not ent.ativa:
            continue
        recusa = mod_entidades.atendivel(ent, cfg)
        if recusa is not None:
            log.error("agendador recusou %s: %s", ent.apelido, recusa.motivo)
            # REGISTRA, NÃO PULA CALADO. Entidade que desaparece do painel
            # é o silêncio que este módulo existe para impedir: quem olhar
            # tem de ver que há um sindicato no arquivo que este servidor
            # não pode atender. Registrada como falha, ela aparece como
            # atrasada — que é a verdade.
            if cfg.tem_banco:
                for nome in TAREFAS:
                    try:
                        registrar(cfg.banco_url, ent.apelido, nome, ok=False,
                                  detalhe=f"recusada: {recusa.motivo}")
                    except Exception:  # noqa: BLE001
                        log.exception("não deu para registrar a recusa de %s",
                                      ent.apelido)
            continue
        pendentes = {
            nome: f for nome, f in tarefas.items()
            if _vencida(cfg.banco_url, ent.apelido, nome)
        }
        if pendentes:
            rodar_uma_vez(cfg.banco_url, ent.apelido, pendentes)


def subir(app, cfg) -> None:
    """Põe o laço para rodar junto com o servidor.

    EM THREAD, nunca no laço de eventos: a coleta leva de 22 a 43 s por
    processo, medidos, e isso dentro do laço travaria o portal inteiro
    enquanto durasse.

    `daemon=True` para que a thread não segure o desligamento: um servidor
    que não encerra porque um trabalho de fundo está dormindo é um servidor
    que alguém mata à força, e aí o arrendamento fica preso até expirar.
    """
    import threading

    parar = threading.Event()

    def laco() -> None:
        # Espera um pouco antes da primeira rodada: subir servidor e
        # começar a falar com tribunal no mesmo segundo faz o primeiro
        # pedido de um filiado esperar por nada.
        parar.wait(30)
        tarefas = tarefas_padrao(cfg)
        while not parar.is_set():
            try:
                uma_rodada(cfg, tarefas)
            except Exception:  # noqa: BLE001
                # O LAÇO NÃO MORRE. Se morresse, o produto continuaria
                # prometendo aviso e ninguém receberia nada — calado.
                log.exception("rodada do agendador falhou inteira")
            parar.wait(ACORDAR_SEGUNDOS)

    thread = threading.Thread(target=laco, name="protocol-agenda", daemon=True)

    @app.on_event("startup")
    def _comecar() -> None:  # pragma: no cover - ciclo de vida do servidor
        thread.start()
        log.info("agendador no ar: acorda a cada %ds", ACORDAR_SEGUNDOS)

    @app.on_event("shutdown")
    def _parar() -> None:  # pragma: no cover
        parar.set()
