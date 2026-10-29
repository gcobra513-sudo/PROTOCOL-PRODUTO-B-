"""
A entidade de demonstração, recriada a cada partida.

POR QUE ISTO EXISTE

No plano gratuito do Render não há disco persistente: tudo o que o servidor
grava some a cada reinício. Sem uma semente, a demonstração sobe vazia e
ninguém consegue nem pedir um código.

DUAS TRAVAS, E AS DUAS SÃO DE CÓDIGO

1. **Só em MODO ENSAIO.** Fora dele a função se recusa a rodar. Semear uma
   entidade automaticamente num servidor de produção seria criar um caminho
   de entrada que ninguém cadastrou;
2. **Só CPF sintético.** O rol sai de `compartilhado/vetores_validacao.json`,
   que são números gerados para teste — nunca de ninguém. Quem não estiver
   nesse rol não entra, e é essa a razão de a demonstração ser segura: um
   filiado de verdade simplesmente não existe aqui.

O apelido começa com `demo-` porque o servidor em ensaio recusa qualquer
outro (ver `PREFIXO_DEMO` em `app.py`).
"""

from __future__ import annotations

import csv
import json
import pathlib

from .config import Config
from .entidades import Cadastro, EntidadeDesconhecida

APELIDO = "demo-sindicato"
NOME = "Sindicato de Demonstração"

RAIZ_REPO = pathlib.Path(__file__).resolve().parent.parent
VETORES = RAIZ_REPO / "compartilhado" / "vetores_validacao.json"

#: Para onde vai o código de acesso na demonstração. Endereço de exemplo
#: reservado por norma, que não entrega a ninguém.
EMAIL_DEMO = "demonstracao@example.org"


class SementeRecusada(RuntimeError):
    """Pedida fora do modo ensaio. Não se semeia produção."""


def _cpfs_sinteticos() -> list[str]:
    dados = json.loads(VETORES.read_text(encoding="utf-8"))
    vistos: list[str] = []
    for bruto in dados["cpf"]["validos"]:
        so_digitos = "".join(c for c in bruto if c.isdigit())
        if so_digitos not in vistos:
            vistos.append(so_digitos)
    return vistos


def semear(cfg: Config) -> str:
    """Cria a entidade de demonstração e o rol. Devolve o apelido."""
    if not cfg.modo_ensaio:
        raise SementeRecusada(
            "semear a entidade de demonstração só vale em MODO ENSAIO. Num "
            "servidor de produção isso criaria um caminho de entrada que "
            "ninguém cadastrou"
        )

    cadastro = Cadastro(cfg.raiz)
    try:
        ent = cadastro.resolver(APELIDO)
    except EntidadeDesconhecida:
        ent = cadastro.criar(APELIDO, NOME)

    pasta = ent.pasta(cfg.raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    with open(pasta / "filiados.csv", "w", newline="", encoding="utf-8") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["cpf", "email"])
        for cpf in _cpfs_sinteticos():
            escritor.writerow([cpf, EMAIL_DEMO])
    return ent.apelido
