#!/usr/bin/env python3
"""Roda todas as suítes do Produto B numa chamada.

Existe para que "está tudo verde?" seja uma pergunta de dez segundos, e não
um exercício de memória sobre quais suítes existem.

    python3 tests/rodar_todos.py

Com banco, para o isolamento entre entidades ser exercitado de verdade:

    PROTOCOL_DATABASE_URL='postgresql://...' python3 tests/rodar_todos.py

NO FIM RODA O ENSAIO DE NAVEGADOR, que custa cerca de 12 segundos e é a
única verificação que dirige React num Chromium contra o servidor. Ele está
aqui e não num documento porque verificação que ninguém roda é o mesmo que
verificação que não existe — e este repositório já teve uma assim, descrita
em detalhe no `servidor/LEIAME.md` e inexistente em disco.

    PROTOCOL_SEM_ENSAIO=1 python3 tests/rodar_todos.py   # e o pulo aparece
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SUITES = [
    "tests/testes_motor.py",
    "tests/testes_cadastro.py",
    "tests/testes_participacao.py",
    "tests/testes_pendencia.py",
    "tests/testes_panorama.py",
    "tests/testes_valor.py",
    "tests/testes_categorias.py",
    "tests/testes_leitura.py",
    "tests/testes_documentos.py",
    "tests/testes_acervo.py",
    "tests/testes_documentos_do_sindicato.py",
    "tests/testes_substituidos.py",
    "tests/testes_completude.py",
    "tests/testes_acompanhamento.py",
    "tests/testes_aviso.py",
    "tests/testes_servidor_portal.py",
    "tests/testes_banco.py",
    "tests/testes_agenda.py",
    "tests/testes_espelho.py",
    "tests/testes_conformidade_portal.py",
    "tests/testes_repositorio.py",
    "tests/testes_apagamento.py",
    "tests/testes_oportunidade.py",
]

# Dependências opcionais: faltar uma delas é "pulado", não "falha". Mas o
# pulo tem de ser VISÍVEL — suíte silenciosamente não executada é o que faz
# alguém achar que está testado quando não está.
OPCIONAIS = {
    "fastapi": "pip install fastapi uvicorn httpx python-multipart",
    "httpx": "pip install httpx",
    "psycopg": "pip install 'psycopg[binary]'",
}
FERRAMENTAS = {"npx": "instale o Node.js"}


def _falta(suite: str) -> str:
    """O que falta para esta suíte rodar, ou "" se nada falta."""
    fonte = (RAIZ / suite).read_text(encoding="utf-8")
    for modulo, como in OPCIONAIS.items():
        if modulo in fonte and importlib.util.find_spec(modulo) is None:
            return f"requer {modulo} ({como})"
    for binario, como in FERRAMENTAS.items():
        if binario in fonte and shutil.which(binario) is None:
            return f"requer {binario} ({como})"
    return ""


def _ensaio_de_navegador(falhas: list[str]) -> list[str]:
    """O ensaio ponta a ponta, e os três motivos de ele ser PULADO em voz alta.

    Sem `node`/`npx` não há Playwright; sem `reportlab` não há PDF com camada
    de texto para anexar; e `PROTOCOL_SEM_ENSAIO=1` existe para o laço curto
    de quem está mexendo numa suíte só. Nos três casos o pulo é IMPRESSO:
    o ensaio é a única verificação que pega o navegador mandando um nome de
    campo que o servidor não espera, e pular isso em silêncio seria recriar
    exatamente a dívida que ele veio pagar.
    """
    nome = "ensaio_de_navegador"
    if os.environ.get("PROTOCOL_SEM_ENSAIO") == "1":
        print(f"  --   {nome:26} PROTOCOL_SEM_ENSAIO=1")
        return [nome]
    r = subprocess.run(
        [sys.executable, "ferramentas/ensaio_portal.py"], cwd=RAIZ,
        capture_output=True, text=True, timeout=1800,
    )
    linhas = [l for l in r.stdout.strip().splitlines() if l.strip()]
    resumo = (linhas or [""])[-1][:60]
    if r.returncode == 0:
        print(f"  ok   {nome:26} {resumo}")
        return []
    if r.returncode == 2:
        # Falta de pré-requisito, não defeito: a própria ferramenta diz o quê.
        print(f"  --   {nome:26} {(r.stderr.strip().splitlines() or [''])[0][:50]}")
        return [nome]
    print(f"  XX   {nome:26} {resumo}")
    for linha in linhas[-14:]:
        print(f"       {linha}")
    falhas.append("ferramentas/ensaio_portal.py")
    return []


def main() -> int:
    print("=" * 62)
    print("PRODUTO B — todas as suítes")
    print("=" * 62)
    falhas: list[str] = []
    pulados: list[str] = []

    for suite in SUITES:
        nome = Path(suite).stem
        motivo = _falta(suite)
        if motivo:
            print(f"  --   {nome:26} {motivo}")
            pulados.append(nome)
            continue
        r = subprocess.run(
            [sys.executable, suite], cwd=RAIZ,
            capture_output=True, text=True, timeout=1800,
        )
        resumo = (r.stdout.strip().splitlines() or [""])[-1][:60]
        if r.returncode == 0:
            print(f"  ok   {nome:26} {resumo}")
        else:
            print(f"  XX   {nome:26} {resumo}")
            falhas.append(suite)

    pulados += _ensaio_de_navegador(falhas)

    print("-" * 62)
    if falhas:
        print(f"{len(falhas)} FALHA(S):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    if pulados:
        print(f"Tudo verde — com {len(pulados)} suíte(s) PULADA(S):")
        for p in pulados:
            print(f"  - {p}")
        print("\nSuíte pulada NÃO está testada. Instale a dependência antes")
        print("de afirmar que o conjunto está verificado.")
    else:
        print("Tudo verde.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
