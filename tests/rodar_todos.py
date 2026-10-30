#!/usr/bin/env python3
"""Roda todas as suítes do Produto B numa chamada.

Existe para que "está tudo verde?" seja uma pergunta de dez segundos, e não
um exercício de memória sobre quais suítes existem.

    python3 tests/rodar_todos.py

Com banco, para o isolamento entre entidades ser exercitado de verdade:

    PROTOCOL_DATABASE_URL='postgresql://...' python3 tests/rodar_todos.py
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
    "tests/testes_categorias.py",
    "tests/testes_leitura.py",
    "tests/testes_documentos.py",
    "tests/testes_acervo.py",
    "tests/testes_completude.py",
    "tests/testes_acompanhamento.py",
    "tests/testes_servidor_portal.py",
    "tests/testes_banco.py",
    "tests/testes_conformidade_portal.py",
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
