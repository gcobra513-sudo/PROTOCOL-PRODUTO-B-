#!/usr/bin/env python3
"""
Gera as travas das dependências: a versão exata de cada pacote — inclusive
os que vêm por tabela — e a impressão digital de cada arquivo.

    python3 ferramentas/travar_dependencias.py

POR QUE EXISTE. `requirements.txt` diz "fastapi de 0.115 até antes da 1": o
que de fato se instala depende do dia em que se instala. Com a trava, a
máquina de produção instala exatamente o que a suíte testou, e um pacote
adulterado no caminho não instala (`pip install --require-hashes`).

DUAS TRAVAS, da mesma resolução:

    servidor/requirements.lock   o que a implantação instala
    requirements.lock            isso, mais o que só a suíte e a demonstração
                                 usam (httpx, reportlab)

VALE PARA QUALQUER PYTHON DE 3.11 EM DIANTE E QUALQUER SISTEMA (`--universal`):
a máquina de produção é Ubuntu com o Python dela, a imagem da demonstração
é outra versão, e uma trava que só servisse a uma das duas seria duas travas
para manter.

QUANDO RODAR: ao mudar um `requirements.txt`, ou para subir versões de
propósito. Depois, RODE A SUÍTE INTEIRA antes de publicar — subir versão é
decisão, não efeito colateral. `tests/testes_repositorio.py` acusa trava
que não é dos pedidos atuais.

Precisa do `uv` (https://docs.astral.sh/uv/): `pip install uv`.
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DO_SERVIDOR = RAIZ / "servidor" / "requirements.txt"
DE_TUDO = RAIZ / "requirements.txt"
#: A versão mais antiga de Python para a qual a trava tem de servir.
PYTHON_MINIMO = "3.11"


def marca() -> str:
    """A impressão dos PEDIDOS: é o que liga a trava ao que ela trava."""
    return hashlib.sha256(
        DO_SERVIDOR.read_bytes() + DE_TUDO.read_bytes()).hexdigest()


def _resolver(entrada: pathlib.Path, restricao: pathlib.Path | None) -> str:
    comando = [
        "uv", "pip", "compile", str(entrada.relative_to(RAIZ)),
        "--universal", "--generate-hashes", "--no-header", "--no-annotate",
        "--python-version", PYTHON_MINIMO, "--quiet",
    ]
    if restricao is not None:
        # A trava de tudo NÃO pode escolher versão diferente da do servidor:
        # a suíte tem de rodar o que a produção roda.
        comando += ["--constraint", str(restricao.relative_to(RAIZ))]
    r = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"o uv não resolveu {entrada.name}:\n{r.stderr}")
    return r.stdout


def _cabecalho(entrada: pathlib.Path) -> str:
    return (
        "# GERADO por `python3 ferramentas/travar_dependencias.py` — não "
        "edite à mão.\n"
        f"# Trava de {entrada.relative_to(RAIZ)}: versão exata e impressão "
        "digital de cada pacote,\n"
        f"# para Python {PYTHON_MINIMO}+ em qualquer sistema. Instale com:\n"
        "#     pip install --require-hashes -r <este arquivo>\n"
        f"# pedidos: sha256={marca()}\n\n"
    )


def main() -> int:
    if not shutil.which("uv"):
        print("falta o `uv`: pip install uv", file=sys.stderr)
        return 2
    trava_do_servidor = DO_SERVIDOR.with_suffix(".lock")
    trava_de_tudo = DE_TUDO.with_suffix(".lock")
    trava_do_servidor.write_text(
        _cabecalho(DO_SERVIDOR) + _resolver(DO_SERVIDOR, None),
        encoding="utf-8")
    trava_de_tudo.write_text(
        _cabecalho(DE_TUDO) + _resolver(DE_TUDO, trava_do_servidor),
        encoding="utf-8")
    for trava in (trava_do_servidor, trava_de_tudo):
        pacotes = sum(1 for l in trava.read_text("utf-8").splitlines()
                      if "==" in l and not l.startswith(("#", " ")))
        print(f"{trava.relative_to(RAIZ)}: {pacotes} pacotes")
    print("Agora rode a suíte inteira antes de publicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
