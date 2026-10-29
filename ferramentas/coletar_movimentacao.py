#!/usr/bin/env python3
"""
Coleta a movimentação dos processos que os filiados pediram para acompanhar.

É o que roda sozinho, todo dia. O que ele toca: número de processo e
movimento. O que ele NÃO toca: CPF, nome, entidade, documento — e por isso
pode viver em qualquer agendador sem exportar dado pessoal.

    python3 ferramentas/coletar_movimentacao.py --entidade demo-sindicato
    python3 ferramentas/coletar_movimentacao.py --processos numeros.txt --seco

CÓDIGOS DE SAÍDA, e eles existem para o agendador:

    0  coletou tudo
    1  coletou, mas algum tribunal falhou — alguém tem de olhar
    2  não deu para começar (entidade inexistente, nada a coletar)

Falha de tribunal sai com código != 0 de propósito. A promessa do produto é
"a gente te avisa"; um timeout que passasse por sucesso faria o filiado ficar
sem saber de uma sentença porque a nossa rede piscou — e ninguém perceberia.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import acompanhamento, deposito, entidades, validacao  # noqa: E402

ARQUIVO = "movimentos.jsonl"


def numeros_do_diario(registros: list[dict]) -> list[str]:
    """Os números a acompanhar, do último envio de cada CPF.

    Último envio porque reenvio é correção: se a pessoa tirou um processo da
    lista, a gente para de acompanhar.
    """
    por_cpf: dict[str, str] = {}
    for registro in registros:
        linha = registro.get("linha")
        if not isinstance(linha, dict):
            continue
        cpf = validacao.so_digitos(linha.get("id_externo") or "")
        if cpf:
            por_cpf[cpf] = linha.get("acompanhar", "")
    numeros: list[str] = []
    for bruto in por_cpf.values():
        for numero in validacao.numeros_de_acompanhamento(bruto):
            if numero not in numeros:
                numeros.append(numero)
    return numeros


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    fonte = p.add_mutually_exclusive_group(required=True)
    fonte.add_argument("--entidade", help="coleta o que os filiados pediram")
    fonte.add_argument("--processos",
                       help="arquivo com um número por linha (para medir)")
    p.add_argument("--raiz", default="dados")
    p.add_argument("--seco", action="store_true",
                   help="não grava nada; só mostra o que viria")
    args = p.parse_args()

    raiz = pathlib.Path(args.raiz)
    destino: pathlib.Path | None = None

    if args.processos:
        numeros = [
            validacao.so_digitos(l)
            for l in pathlib.Path(args.processos).read_text("utf-8").splitlines()
            if l.strip()
        ]
    else:
        try:
            ent = entidades.Cadastro(raiz).resolver(args.entidade)
        except LookupError:
            print(f"entidade {args.entidade!r} não existe em {raiz}",
                  file=sys.stderr)
            return 2
        pasta = ent.pasta(raiz)
        numeros = numeros_do_diario(deposito.ler_diario(pasta))
        destino = pasta / ARQUIVO

    if not numeros:
        print("nada a acompanhar — nenhum filiado informou processo",
              file=sys.stderr)
        return 2

    vistos = (acompanhamento.ler_diario_de_movimentos(destino)
              if destino else [])
    print(f"acompanhando {len(numeros)} processo(s); "
          f"{len(vistos)} movimento(s) já vistos")

    agora, erros = acompanhamento.coletar(numeros)
    novos = acompanhamento.novidades(vistos, agora)

    print(f"\n  consultados ........... {len(numeros)}")
    print(f"  movimentos lidos ...... {len(agora)}")
    print(f"  NOVIDADES ............. {len(novos)}")
    print(f"  tribunais com falha ... {len(erros)}")

    # Processo que não devolveu nada NÃO é falha: a defasagem é de ~1 dia, e
    # protocolado ontem pode não estar indexado. Mas aparece, porque "zero
    # movimento para sempre" é sinal de número errado na base.
    com_registro = {m.numero for m in agora}
    sem_registro = [n for n in numeros if n not in com_registro]
    if sem_registro:
        print(f"  sem registro no DataJud {len(sem_registro)} "
              f"(defasagem de ~1 dia é normal)")

    for m in novos[:30]:
        print(f"    {m.data[:10]}  {m.numero}  {m.grau}  {m.nome}")
    if len(novos) > 30:
        print(f"    ... e outras {len(novos) - 30}")

    for erro in erros:
        print(f"  FALHA: {erro}", file=sys.stderr)

    if destino and not args.seco and agora:
        deposito.anexar_com_fsync(
            destino,
            json.dumps(
                {
                    "coletado_em": dt.datetime.now(dt.UTC).isoformat(
                        timespec="seconds"),
                    "consultados": len(numeros),
                    "falhas": erros,
                    "movimentos": [
                        {"numero": m.numero, "grau": m.grau,
                         "data": m.data, "nome": m.nome}
                        for m in agora
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
            ) + "\n",
        )
        print(f"\n  gravado em {destino}")

    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
