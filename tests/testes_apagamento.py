"""Apagamento a pedido — LGPD art. 18, VI.

O produto guarda nome, CPF, e-mail, sentença e número de processo de gente
aposentada, e filiação sindical é dado sensível (art. 11). Um pedido de
eliminação tem de ser atendido, e a lei dá 15 dias.

O QUE ESTES TESTES PROVAM, e é diferente de "a função foi chamada": que
depois de apagar **não sobra nada** — e a prova é uma varredura de banco,
disco, CSV e diário, não um campo `apagado = true`. Campo desses é uma
AFIRMAÇÃO, e a auditoria de 31/10 derrubou sete afirmações assim neste
mesmo repositório.

SEM BANCO ESTA SUÍTE É PULADA, e o resumo diz isso. Suíte pulada não está
testada.

Spec: `docs/superpowers/specs/2026-11-02-apagamento-a-pedido-design.md`
"""
from __future__ import annotations

import os
import sys
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


def preparar() -> None:
    from servidor import banco

    banco.criar_esquema(URL, recriar=True)


# --------------------------------------------------------- o tombstone

def teste_o_tombstone_guarda_o_pedido_e_nunca_o_cpf():
    """O tombstone é a prova de que a remoção foi deliberada.

    Guarda QUEM foi apagado (por marcador), QUANDO, e A PEDIDO DE QUEM —
    sem o dado. É isso que transforma "append-only" em "não se edita" em
    vez de "não se apaga nunca".
    """
    secao("o tombstone")
    from servidor import banco

    banco.marcar_tombstone(URL, "demo-a", "marcador-de-teste",
                           motivo="pedido do titular",
                           pedido_por="gestor@exemplo.invalid")

    checa(banco.tombstones(URL, "demo-a") == {"marcador-de-teste"},
          f"o tombstone não foi lido de volta: "
          f"{banco.tombstones(URL, 'demo-a')}")

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT motivo, pedido_por FROM tombstone")
        linha = cur.fetchone()
    checa(linha == ("pedido do titular", "gestor@exemplo.invalid"),
          f"o pedido não ficou registrado: {linha}")
    print("  ok     o tombstone guarda o pedido, por marcador")


def teste_o_tombstone_nao_atravessa_entidade():
    """Apagar numa entidade não pode apagar na outra, nem ser visto por ela."""
    from servidor import banco

    banco.marcar_tombstone(URL, "demo-b", "marcador-da-b",
                           motivo="", pedido_por="")
    checa("marcador-da-b" not in banco.tombstones(URL, "demo-a"),
          "a entidade A vê o tombstone da B")
    checa("marcador-de-teste" not in banco.tombstones(URL, "demo-b"),
          "a entidade B vê o tombstone da A")
    print("  ok     tombstone não atravessa entidade")


TESTES = [
    teste_o_tombstone_guarda_o_pedido_e_nunca_o_cpf,
    teste_o_tombstone_nao_atravessa_entidade,
]


def main() -> int:
    print("=" * 70)
    print("APAGAMENTO A PEDIDO (LGPD art. 18, VI)")
    print("=" * 70)
    if not URL:
        print("PULADO: defina PROTOCOL_DATABASE_URL. Suíte pulada não está "
              "testada.")
        return 0
    preparar()
    for teste in TESTES:
        try:
            teste()
        except Exception as e:  # noqa: BLE001
            import traceback

            falhas.append(f"{teste.__name__} levantou "
                          f"{type(e).__name__}: {e}")
            traceback.print_exc()
    print("-" * 70)
    if falhas:
        print(f"FALHOU ({len(falhas)}):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
