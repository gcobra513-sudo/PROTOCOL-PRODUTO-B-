#!/usr/bin/env python3
"""
As frases que o motor diz — a do sindicato e a do filiado, lado a lado.

    python3 ferramentas/frases.py            # imprime
    python3 ferramentas/frases.py --gravar   # atualiza docs/frases_do_filiado.md

Cada resposta do motor é escrita duas vezes na origem (`nucleo/dito.py`):
uma para o veredicto guardado, lida por advogado e gestor, e outra para a
tela do próprio filiado. Esta ferramenta LÊ O CÓDIGO e lista os pares, para
quem revisa texto conferir todos num lugar só, sem abrir o código.

É LEITURA DO CÓDIGO, e não uma lista mantida à mão: uma lista à mão ficaria
velha na primeira frase nova. O que aparece entre chaves — `{rotulo}`,
`{inicio}` — é o pedaço que muda de pessoa para pessoa.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs" / "frases_do_filiado.md"
#: Onde nascem frases com dois leitores.
PASTAS = ("nucleo", "servidor")


def _texto(no: ast.AST) -> str:
    """O texto de um argumento, do jeito que se lê: literais juntos, e o que
    é calculado entre chaves."""
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return no.value
    if isinstance(no, ast.JoinedStr):
        partes = []
        for p in no.values:
            if isinstance(p, ast.Constant):
                partes.append(str(p.value))
            else:
                partes.append("{" + ast.unparse(p.value) + "}")
        return "".join(partes)
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        return _texto(no.left) + _texto(no.right)
    return "{" + ast.unparse(no) + "}"


def frases() -> list[dict]:
    achadas = []
    for pasta in PASTAS:
        for arquivo in sorted((RAIZ / pasta).glob("*.py")):
            if arquivo.name == "dito.py":
                continue        # as definições, não os usos
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if not isinstance(no, ast.Call):
                    continue
                nome = (no.func.attr if isinstance(no.func, ast.Attribute)
                        else getattr(no.func, "id", ""))
                if nome == "dito" and len(no.args) == 2:
                    sindicato, voce = (_texto(a) for a in no.args)
                elif nome == "ambos" and len(no.args) == 1:
                    sindicato = voce = _texto(no.args[0])
                else:
                    continue
                achadas.append({
                    "onde": f"{arquivo.relative_to(RAIZ)}:{no.lineno}",
                    "sindicato": " ".join(sindicato.split()),
                    "voce": " ".join(voce.split()),
                })
    return sorted(achadas, key=lambda f: (f["onde"].split(":")[0],
                                          int(f["onde"].split(":")[1])))


def documento() -> str:
    lista = frases()
    linhas = [
        "# As frases do motor, para revisão",
        "",
        "Gerado por `python3 ferramentas/frases.py --gravar` — não edite à "
        "mão: para mudar uma frase, mude no código (o arquivo está em cada "
        "item) e gere de novo.",
        "",
        f"São **{len(lista)}** frases. Cada uma tem dois leitores: o "
        "**sindicato** (é o que fica no veredicto guardado) e o **filiado** "
        "(é o que ele lê na tela dele). O que está entre chaves muda de "
        "pessoa para pessoa.",
        "",
    ]
    for i, f in enumerate(lista, 1):
        # SÓ O ARQUIVO no título, sem o número da linha: com ele, qualquer
        # edição acima de uma frase deixaria este documento "desatualizado"
        # sem que frase nenhuma tivesse mudado.
        linhas += [f"## {i}. `{f['onde'].split(':')[0]}`", ""]
        if f["sindicato"] == f["voce"]:
            linhas += [f"- **Para os dois:** {f['voce']}", ""]
        else:
            linhas += [f"- **Sindicato lê:** {f['sindicato']}",
                       f"- **Filiado lê:** {f['voce']}", ""]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gravar", action="store_true",
                    help=f"escreve em {DESTINO.relative_to(RAIZ)}")
    a = ap.parse_args(argv)
    texto = documento()
    if a.gravar:
        DESTINO.write_text(texto, encoding="utf-8")
        print(f"{len(frases())} frases em {DESTINO.relative_to(RAIZ)}")
    else:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
