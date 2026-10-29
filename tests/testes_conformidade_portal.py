"""Conformidade entre o validador do portal (TypeScript) e o nosso (Python).

Os dois leem `compartilhado/vetores_validacao.json`. Este arquivo testa o lado
Python; `portal/src/lib/validacao.test.ts` testa o lado TypeScript, contra os
mesmos vetores.

POR QUE OS DOIS LADOS

A especificação do portal deixava uma escolha: portar o algoritmo do dígito
verificador para TypeScript — validação instantânea, mas o algoritmo passa a
existir em dois lugares e pode divergir — ou expor como API, uma fonte da
verdade só, mas dependendo de rede a cada dígito digitado.

Portamos E travamos. A pessoa digitando o CPF tem resposta imediata, sem
rede; e se as duas implementações discordarem, um teste reprova de cada lado.
Divergência silenciosa deixa de ser possível.

Também confere uma coisa que vetor nenhum pega sozinho: que o CPF usado como
exemplo nos vetores não é o CPF de ninguém de verdade — são os CPFs
sintéticos que a documentação usa.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo.processo_cnj import (  # noqa: E402
    calcular_verificador,
    conferir,
    decompor,
    so_digitos,
    valido,
)

VETORES = RAIZ / "compartilhado" / "vetores_validacao.json"
TS = RAIZ / "portal" / "src" / "lib" / "validacao.ts"

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def _cpf_valido(valor: str) -> bool:
    """Mesma regra do portal, para conferir os vetores dos dois lados."""
    d = so_digitos(valor)
    if len(d) != 11 or len(set(d)) == 1:
        return False

    def dv(base: str, peso: int) -> int:
        soma = sum(int(c) * (peso - i) for i, c in enumerate(base))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto

    return int(d[9]) == dv(d[:9], 10) and int(d[10]) == dv(d[:10], 11)


def t_vetores_existem_e_sao_coerentes():
    checa(VETORES.is_file(), f"vetores compartilhados ausentes: {VETORES}")
    if not VETORES.is_file():
        return
    d = json.loads(VETORES.read_text(encoding="utf-8"))
    checa(len(d["cpf"]["validos"]) >= 3, "poucos CPFs válidos nos vetores")
    checa(len(d["cpf"]["invalidos"]) >= 5, "poucos CPFs inválidos nos vetores")
    checa(len(d["processo_cnj"]["validos"]) >= 2, "poucos processos válidos")
    checa(len(d["processo_cnj"]["fora_do_trf1"]) >= 2,
          "poucos processos de fora do TRF1")


def t_cpf_bate_com_os_vetores():
    d = json.loads(VETORES.read_text(encoding="utf-8"))
    for valor in d["cpf"]["validos"]:
        checa(_cpf_valido(valor), f"o Python recusou o CPF válido {valor!r}")
    for caso in d["cpf"]["invalidos"]:
        checa(not _cpf_valido(caso["valor"]),
              f"o Python aceitou o CPF inválido {caso['valor']!r} "
              f"({caso['motivo']})")


def t_processo_bate_com_os_vetores():
    d = json.loads(VETORES.read_text(encoding="utf-8"))
    for caso in d["processo_cnj"]["validos"]:
        checa(valido(caso["valor"]),
              f"o Python recusou o processo válido {caso['valor']!r}")
    for caso in d["processo_cnj"]["invalidos"]:
        checa(not valido(caso["valor"]),
              f"o Python aceitou o processo inválido {caso['valor']!r} "
              f"({caso['motivo']})")
    for caso in d["processo_cnj"]["fora_do_trf1"]:
        checa(valido(caso["valor"]),
              f"{caso['valor']!r} deveria ser número íntegro "
              f"({caso['justica']})")
        checa(bool(conferir(caso["valor"], exigir_trf1=True)),
              f"{caso['valor']!r} deveria avisar que não é do TRF1 "
              f"({caso['justica']})")


def t_vetores_foram_gerados_nao_escritos_a_mao():
    """Vetor inventado é teste que mente.

    A primeira versão deste arquivo tinha um número de processo escrito à mão:
    eu troquei o tribunal e mantive o dígito verificador. Mas o dígito depende
    do número INTEIRO, então o vetor era inválido e o teste "passaria" por
    motivo errado. Este teste recalcula cada dígito.
    """
    d = json.loads(VETORES.read_text(encoding="utf-8"))
    todos = (d["processo_cnj"]["validos"] + d["processo_cnj"]["fora_do_trf1"])
    for caso in todos:
        p = decompor(caso["valor"])
        esperado = calcular_verificador(p.sequencial, p.ano, p.segmento,
                                        p.tribunal, p.origem)
        checa(p.verificador == esperado,
              f"o vetor {caso['valor']!r} tem dígito {p.verificador}, "
              f"mas o certo é {esperado} — vetor escrito à mão?")


def t_typescript_usa_bigint():
    """20 dígitos estouram o inteiro seguro do JavaScript.

    Com `Number` em vez de `BigInt`, o cálculo do dígito sai errado em parte
    dos casos — e errado de um jeito que passa em teste superficial, porque
    muitos números continuam batendo. Este teste lê o fonte.
    """
    checa(TS.is_file(), f"validador do portal ausente: {TS}")
    if not TS.is_file():
        return
    fonte = TS.read_text(encoding="utf-8")
    checa("BigInt(" in fonte and "97n" in fonte,
          "o validador do portal deveria usar BigInt para o MOD 97-10: "
          "20 dígitos passam de Number.MAX_SAFE_INTEGER")
    checa("compartilhado/vetores_validacao.json" in
          (RAIZ / "portal" / "src" / "lib" / "validacao.test.ts").read_text("utf-8"),
          "o teste do portal deveria ler os vetores compartilhados")


def t_cpfs_de_exemplo_nao_sao_de_ninguem():
    """Os CPFs dos vetores têm de ser sintéticos.

    Vetor de teste vai para o repositório e para a tela de demonstração. CPF
    de pessoa real num arquivo versionado é vazamento, e não há motivo: os
    CPFs sintéticos de documentação servem igual.
    """
    conhecidos = {"11144477735", "52998224725"}
    d = json.loads(VETORES.read_text(encoding="utf-8"))
    for valor in d["cpf"]["validos"]:
        checa(so_digitos(valor) in conhecidos,
              f"o CPF {valor!r} não está na lista de CPFs sintéticos "
              f"conhecidos. Se for de alguém de verdade, tire daqui")


TESTES = [
    ("vetores existem e são coerentes", t_vetores_existem_e_sao_coerentes),
    ("CPF bate com os vetores", t_cpf_bate_com_os_vetores),
    ("processo bate com os vetores", t_processo_bate_com_os_vetores),
    ("vetores foram gerados, não escritos à mão",
     t_vetores_foram_gerados_nao_escritos_a_mao),
    ("o TypeScript usa BigInt", t_typescript_usa_bigint),
    ("CPFs de exemplo são sintéticos", t_cpfs_de_exemplo_nao_sao_de_ninguem),
]


def main() -> int:
    print("=" * 70)
    print("CONFORMIDADE Python <-> TypeScript (validação do portal)")
    print("=" * 70)
    for nome, fn in TESTES:
        antes = len(falhas)
        try:
            fn()
        except Exception as exc:   # noqa: BLE001
            falhas.append(f"{nome}: levantou {type(exc).__name__}: {exc}")
        print(f"  {'FALHA' if len(falhas) > antes else 'ok   '}  {nome}")
    print("-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} testes passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
