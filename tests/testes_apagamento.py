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



# ------------------------------------------- semeadura (dados fictícios)

def _cpf(n: int) -> str:
    """CPF sintético com dígito que fecha. A base é o índice, não ninguém."""
    base = [int(c) for c in f"{n:09d}"]
    for peso0 in (10, 11):
        soma = sum(d * (peso0 - i) for i, d in enumerate(base))
        base.append((soma * 10 % 11) % 10)
    return "".join(map(str, base))


A = _cpf(3001)
B = _cpf(3002)
C = _cpf(3003)
D = _cpf(3004)


def _pessoa_do_acervo(cpf: str, linha: int = 2):
    from servidor import acervo

    return acervo.Pessoa(cpf=cpf, linha_no_arquivo=linha, campos={
        "nome_completo": f"PESSOA {cpf} (CADASTRO FICTÍCIO)",
        "email": f"exemplo-{cpf}@exemplo.invalid",
        "unidade": "UNIDADE DE EXEMPLO",
    })


def _registro_do_diario(cpf: str, protocolo: str) -> dict:
    return {
        "protocolo": protocolo,
        "recebido_em": "2026-11-02T00:00:00+00:00",
        "entidade": "demo-a",
        "linha": {
            "cpf": cpf,
            "nome_completo": f"PESSOA {cpf} (CADASTRO FICTÍCIO)",
            "email": f"exemplo-{cpf}@exemplo.invalid",
            "cargo": "Auditor Fiscal da Receita Federal",
            "situacao": "aposentado",
            "filiado_desde": "2004-03",
        },
        "arquivos": {"contribuicao": "a" * 64},
    }


# ----------------------------------------------- as exclusões no banco

def teste_apagar_pessoa_limpa_o_que_e_dela():
    secao("as exclusões no banco")
    from servidor import banco

    # A MESMA ingestão de acervo traz as duas pessoas, de propósito: é o
    # caso em que apagar demais estragaria o dado de terceiro.
    banco.projetar_acervo(URL, "demo-a",
                          [_pessoa_do_acervo(A, 2), _pessoa_do_acervo(B, 3)])
    # O retorno é ignorado: a T7 muda a assinatura, e o que este teste
    # prova não é o valor devolvido (ver ruling no livro de registro).
    banco.reconstruir(URL, "demo-a", [_registro_do_diario(A, "PRT-A")])

    saiu = banco.apagar_pessoa(URL, "demo-a", A)

    checa(saiu.get("pessoa_afirmacao", 0) > 0 and saiu.get("pessoa") == 1,
          f"não apagou as linhas da pessoa: {saiu}")
    checa(banco.registro_do_cpf(URL, "demo-a", A) is None,
          "a pessoa continua na base depois de apagada")
    checa("leitura" not in saiu and "processo" not in saiu
          and "movimento" not in saiu,
          f"tocou tabela que a spec manda não tocar: {saiu}")
    print("  ok     as linhas da pessoa saíram")


def teste_apagar_nao_estraga_o_dado_de_terceiro():
    """APAGAR DEMAIS É IRREVERSÍVEL, e aqui está o caminho para isso.

    `projetar_acervo` grava UM `recebimento` por INGESTÃO, compartilhado
    por todas as pessoas da planilha. Apagar esse recebimento junto com uma
    pessoa anularia o `recebimento_id` de todas as outras — e a coluna é
    `ON DELETE SET NULL`, então o estrago é silencioso.

    A outra pessoa da mesma ingestão tem de continuar inteira, e com a
    procedência dela intacta.
    """
    from servidor import banco

    # AUTOSSUFICIENTE DE PROPÓSITO. A primeira versão deste teste só lia, e
    # por isso passava ANTES de `apagar_pessoa` existir — nada apagava, e a
    # outra pessoa sobrevivia à toa. Teste que passa sem o código é um
    # achado sobre o teste.
    banco.projetar_acervo(URL, "demo-a",
                          [_pessoa_do_acervo(C, 4), _pessoa_do_acervo(D, 5)])
    banco.apagar_pessoa(URL, "demo-a", C)

    outra = banco.registro_do_cpf(URL, "demo-a", D)
    checa(outra is not None,
          "apagou a pessoa errada: a outra da mesma ingestão desapareceu")
    checa(outra and outra["linha"].get("nome_completo"),
          f"a outra pessoa ficou sem nome: {outra}")

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM pessoa_afirmacao "
                    "WHERE cpf = %s AND recebimento_id IS NULL", (D,))
        orfas = cur.fetchone()[0]
    checa(orfas == 0,
          f"{orfas} afirmações da outra pessoa perderam a procedência")
    print("  ok     a outra pessoa da mesma ingestão ficou intacta")


def teste_apagar_nao_atravessa_entidade():
    from servidor import banco

    banco.projetar_acervo(URL, "demo-b", [_pessoa_do_acervo(A, 2)])
    banco.apagar_pessoa(URL, "demo-a", A)
    checa(banco.registro_do_cpf(URL, "demo-b", A) is not None,
          "apagar na entidade A apagou a mesma pessoa na B")
    print("  ok     apagar não atravessa entidade")


TESTES = [
    teste_o_tombstone_guarda_o_pedido_e_nunca_o_cpf,
    teste_o_tombstone_nao_atravessa_entidade,
    teste_apagar_pessoa_limpa_o_que_e_dela,
    teste_apagar_nao_estraga_o_dado_de_terceiro,
    teste_apagar_nao_atravessa_entidade,
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
