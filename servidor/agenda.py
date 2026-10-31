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
            "SELECT tarefa, ultima_boa, ultima_em, ultima_ok, ultimo_detalhe "
            "FROM execucao"
        )
        por_tarefa = {t: (b, e, k, d) for t, b, e, k, d in cur.fetchall()}

    agora = dt.datetime.now(dt.UTC)
    saida = []
    for tarefa in TAREFAS:
        boa, em, ok, detalhe = por_tarefa.get(tarefa, (None, None, None, ""))
        atrasado = (
            boa is None
            or (agora - boa) > dt.timedelta(hours=TOLERANCIA_HORAS)
        )
        saida.append({
            "tarefa": tarefa,
            "ultima_boa": boa.isoformat() if boa else None,
            "ultima_em": em.isoformat() if em else None,
            "ultima_falhou": ok is False,
            "ultimo_detalhe": detalhe or "",
            "atrasado": atrasado,
        })
    return saida


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
            detalhe = funcao(entidade) or ""
        except Exception as e:  # noqa: BLE001
            log.exception("tarefa %s de %s falhou", tarefa, entidade)
            registrar(url, entidade, tarefa, ok=False,
                      detalhe=f"{type(e).__name__}: {e}")
            continue
        registrar(url, entidade, tarefa, ok=True, detalhe=str(detalhe))


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
            r = subprocess.run(comando, capture_output=True, text=True,
                               timeout=ARRENDAMENTO_SEGUNDOS - 60)
            saida = (r.stdout or "").strip().replace("\n", " ")[-400:]
            if r.returncode not in (0, 1):
                raise RuntimeError(
                    f"{programa} saiu com {r.returncode}: "
                    f"{(r.stderr or saida)[-300:]}"
                )
            # Código 1 é "rodou, mas algo ficou de fora" — e isso É uma falha
            # para o registro: alguém tem de olhar, e é o registro que avisa.
            if r.returncode == 1:
                raise RuntimeError(f"{programa}: {saida}")
            return saida
        return executar

    return {
        "coletar": _rodar("coletar_movimentacao.py",
                          ["--banco", cfg.banco_url]),
        "avisar": _rodar("avisar_movimentacao.py",
                         ["--banco", cfg.banco_url] +
                         (["--portal", cfg.portal] if cfg.portal else [])),
    }


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

    from . import entidades as mod_entidades

    parar = threading.Event()

    def laco() -> None:
        # Espera um pouco antes da primeira rodada: subir servidor e
        # começar a falar com tribunal no mesmo segundo faz o primeiro
        # pedido de um filiado esperar por nada.
        parar.wait(30)
        tarefas = tarefas_padrao(cfg)
        while not parar.is_set():
            try:
                cadastro = mod_entidades.Cadastro(cfg.raiz)
                for ent in cadastro.todas():
                    if not ent.ativa:
                        continue
                    pendentes = {
                        nome: f for nome, f in tarefas.items()
                        if _vencida(cfg.banco_url, ent.apelido, nome)
                    }
                    if pendentes:
                        rodar_uma_vez(cfg.banco_url, ent.apelido, pendentes)
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
