#!/usr/bin/env python3
"""
Os documentos que o sindicato já tem, para dentro do produto.

    python3 ferramentas/ingerir_documentos.py \
        --pasta /caminho/dos/pdfs --entidade demo-sindicato

    python3 ferramentas/ingerir_documentos.py \
        --zip acervo.zip --entidade demo-sindicato

Sem `--entidade` nada é gravado: dá para passar a pasta e ver de quem é cada
arquivo antes de decidir. É a mesma disciplina de `ingerir_acervo.py`.

O QUE SAI NA TELA É A PILHA DO QUE NÃO CASOU, não a contagem do que casou:
"3.812 de 4.000" esconde 188 sentenças de gente que vai ficar sem resposta.
Cada sobra aparece com o nome do arquivo e o motivo, para alguém abrir.

CÓDIGOS DE SAÍDA, para o agendador:

    0  tudo casou
    1  casou, mas sobrou arquivo — alguém tem de olhar
    2  não deu para começar (entidade inexistente, nada a ler)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import (  # noqa: E402
    documentos_do_sindicato as lote,
    entidades,
)


def _ler_pasta(pasta: pathlib.Path) -> list[tuple[str, bytes]]:
    return [
        (p.name, p.read_bytes())
        for p in sorted(pasta.rglob("*"))
        if p.is_file() and p.suffix.lower() == ".pdf"
        and not p.name.startswith(".")
    ]


def _cpfs_da_base(url: str, apelido: str, pasta: pathlib.Path) -> set[str]:
    """Quem a entidade declarou atender. Do banco quando há banco; do rol em
    disco quando não há — e o rol é o mínimo, porque é por ele que alguém
    recebe código de acesso."""
    cpfs: set[str] = set()
    if url:
        from servidor import banco

        for r in banco.base(url, apelido):
            digitos = "".join(c for c in r["linha"].get("cpf", "")
                              if c.isdigit())
            if digitos:
                cpfs.add(digitos)
    if not cpfs:
        from servidor import rol

        try:
            cpfs = {"".join(c for c in k if c.isdigit())
                    for k in rol.carregar(pasta).por_cpf}
        except Exception:  # noqa: BLE001
            cpfs = set()
    return {c for c in cpfs if c}


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    origem = p.add_mutually_exclusive_group(required=True)
    origem.add_argument("--pasta", help="pasta com os PDFs")
    origem.add_argument("--zip", dest="zip_", help="arquivo .zip com os PDFs")
    p.add_argument("--entidade", default="",
                   help="apelido da entidade. Sem isto, nada é gravado")
    p.add_argument("--raiz", default="dados", help="raiz dos dados")
    p.add_argument("--banco", default=os.environ.get("PROTOCOL_DATABASE_URL", ""))
    p.add_argument("--mostrar", type=int, default=30,
                   help="quantas sobras listar (padrão: 30)")
    args = p.parse_args()

    if args.zip_:
        try:
            arquivos = lote.abrir_zip(pathlib.Path(args.zip_).read_bytes())
        except lote.ZipRecusado as e:
            print(f"O ZIP NÃO PÔDE SER ABERTO: {e}", file=sys.stderr)
            return 2
        except OSError as e:
            print(f"não deu para ler {args.zip_}: {e}", file=sys.stderr)
            return 2
    else:
        pasta_origem = pathlib.Path(args.pasta)
        if not pasta_origem.is_dir():
            print(f"{args.pasta} não é uma pasta", file=sys.stderr)
            return 2
        arquivos = _ler_pasta(pasta_origem)

    if not arquivos:
        print("nenhum PDF encontrado", file=sys.stderr)
        return 2

    raiz = pathlib.Path(args.raiz)
    cpfs: set[str] = set()
    ent = None
    if args.entidade:
        try:
            ent = entidades.Cadastro(raiz).resolver(args.entidade)
        except LookupError:
            print(f"entidade {args.entidade!r} não existe em {raiz}",
                  file=sys.stderr)
            return 2
        cpfs = _cpfs_da_base(args.banco, ent.apelido, ent.pasta(raiz))
        if not cpfs:
            print(
                "a base desta entidade está VAZIA: ingira a planilha de "
                "filiados antes, senão nenhum arquivo casa com ninguém",
                file=sys.stderr,
            )
            return 2
    else:
        # Sem entidade é diagnóstico: aceita qualquer CPF que feche, só para
        # mostrar de quem seria cada arquivo.
        from servidor import validacao

        for nome, corpo in arquivos:
            cpfs |= {c for c in lote._cpf_no_nome(nome)}
            try:
                from servidor import documentos as doc

                cpfs |= set(lote._cpfs_no_texto(doc.ler_pdf(corpo)))
            except Exception:  # noqa: BLE001
                pass
        cpfs = {c for c in cpfs if validacao.cpf_valido(c)}

    r = lote.casar(arquivos, cpfs)
    pessoas = len(r.casados)
    documentos_casados = sum(len(v) for v in r.casados.values())

    print("=" * 66)
    print(f"\n  {len(arquivos)} arquivo(s) lidos")
    print(f"  {documentos_casados} casaram com {pessoas} pessoa(s)")
    print(f"  {len(r.sobraram)} NÃO casaram\n")

    for aviso in r.avisos[: args.mostrar]:
        print(f"  ATENÇÃO  {aviso}")
    if r.avisos:
        print()

    if r.sobraram:
        print(f"  o que NÃO casou (primeiros {args.mostrar}):")
        for s in r.sobraram[: args.mostrar]:
            print(f"    {s.arquivo[:44]:46} {s.motivo}")
        if len(r.sobraram) > args.mostrar:
            print(f"    ... e mais {len(r.sobraram) - args.mostrar}")
        print()

    if ent is None:
        print("  (nada gravado — passe --entidade para ingerir)")
        return 1 if r.sobraram else 0

    # OS BYTES VÃO PARA A ENTREGA, com o nome do contrato: é a pasta que
    # quem confere abre, e ela já tem uma convenção. O documento do sindicato
    # entra do mesmo jeito que o do filiado — depois de dentro, não há dois
    # tipos de documento.
    entrega = ent.entrega(raiz)
    for cpf, docs in r.casados.items():
        destino = entrega / cpf
        destino.mkdir(parents=True, exist_ok=True)
        por_tipo: dict[str, int] = {}
        for d in docs:
            indice = por_tipo.get(d.tipo, 0) + 1
            por_tipo[d.tipo] = indice
            nome = (f"{d.tipo}.pdf" if indice == 1 and d.tipo != lote.OUTRO
                    else f"{d.tipo}-{indice}.pdf")
            (destino / nome).write_bytes(d.corpo)

        if args.banco:
            from servidor import banco

            for d in docs:
                soma = hashlib.sha256(d.corpo).hexdigest()
                with banco.sessao(args.banco, ent.apelido) as cur:
                    cur.execute(
                        "INSERT INTO documento (entidade, cpf, tipo, sha256) "
                        "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (ent.apelido, cpf, d.tipo, soma),
                    )
                banco.guardar_achados(args.banco, ent.apelido, cpf, soma,
                                      d.achados)

    print(f"  gravado em {entrega}")
    if not args.banco:
        print(
            "\n  AVISO: sem --banco, os arquivos ficam no disco e os fatos\n"
            "  lidos deles NÃO são gravados. A tela da pessoa relê o PDF a\n"
            "  cada visita, e o painel do sindicato não os enxerga."
        )
    return 1 if r.sobraram else 0


if __name__ == "__main__":
    raise SystemExit(main())
