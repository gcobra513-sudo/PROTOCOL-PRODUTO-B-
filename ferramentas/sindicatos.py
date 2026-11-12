#!/usr/bin/env python3
"""
Pôr um sindicato novo para funcionar — e cuidar de quem é gestor.

É a ferramenta de QUEM OPERA O SERVIDOR. Criar um sindicato é o contrato:
quem é cliente, e que carreiras contratou. E nomear gestor é a única
credencial que nasce fora do sindicato — gestor não nomeia gestor, porque a
sessão de gestor vê a base inteira. Por isso nada daqui tem rota no portal.

    python3 ferramentas/sindicatos.py --raiz dados categorias
    python3 ferramentas/sindicatos.py --raiz dados criar sind-df "Sindicato Tal" \\
        --categoria auditor-fiscal-receita-federal \\
        --gestor 000.000.000-00=secretaria@sindicato.exemplo.org
    python3 ferramentas/sindicatos.py --raiz dados listar

    python3 ferramentas/sindicatos.py --raiz dados gestor sind-df listar
    python3 ferramentas/sindicatos.py --raiz dados gestor sind-df nomear CPF EMAIL
    python3 ferramentas/sindicatos.py --raiz dados gestor sind-df tirar CPF

`criar` CONFERE TUDO ANTES DE GRAVAR QUALQUER COISA, e exige ao menos uma
categoria e um gestor: sem categoria o sindicato não recebe resposta
nenhuma, e sem gestor ninguém abre o painel. Daí em diante é com o
sindicato — o gestor entra, envia a planilha, e os filiados passam a
receber código.

O APELIDO DECIDE SE É DEMONSTRAÇÃO. Começando por `demo-`, o servidor
atende em modo ensaio e mostra a faixa de demonstração. Qualquer outro é
sindicato de verdade, e o servidor só o atende fora do ensaio, em região
brasileira e com banco.

O QUE ESTA FERRAMENTA NÃO FAZ: trocar o e-mail de quem já entra (é
`trocas_de_email.py`, com conferência), mudar as categorias de um sindicato
que já existe, e suspender um sindicato. Os dois últimos ainda são edição de
`entidades.json`.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import entendimentos  # noqa: E402
from servidor import entidades, rol, validacao  # noqa: E402


class Recusado(Exception):
    """A mensagem é para quem opera ler, e diz o que consertar."""


def _categorias_do_catalogo(pasta: pathlib.Path) -> list[str]:
    return sorted(a.stem for a in pasta.glob("*.toml"))


def _cpf_mascarado(cpf: str) -> str:
    """O bastante para reconhecer a pessoa na lista, e não é o CPF."""
    d = validacao.so_digitos(cpf)
    return f"***.{d[3:6]}.{d[6:9]}-**" if len(d) == 11 else "(CPF inválido)"


def _gestores_pedidos(brutos: list[str]) -> list[tuple[str, str]]:
    pares: list[tuple[str, str]] = []
    for bruto in brutos:
        cpf, sinal, email = bruto.partition("=")
        if not sinal or not email.strip():
            raise Recusado(
                f"--gestor {bruto!r}: escreva CPF=e-mail, com o sinal de = "
                f"entre os dois"
            )
        digitos = validacao.so_digitos(cpf)
        if not validacao.cpf_valido(digitos):
            raise Recusado(
                f"--gestor: o CPF {_cpf_mascarado(cpf)} não fecha o dígito "
                f"verificador"
            )
        if not rol.email_serve(email.strip()):
            raise Recusado(
                f"--gestor: o e-mail {email.strip()!r} não serve — é para "
                f"ele que o código de acesso vai"
            )
        if digitos in {c for c, _ in pares}:
            raise Recusado(
                f"--gestor: o CPF {_cpf_mascarado(cpf)} aparece duas vezes"
            )
        pares.append((digitos, email.strip()))
    return pares


def _endereco(apelido: str) -> str:
    return f"/?entidade={apelido}&tela=painel"


def criar(raiz: pathlib.Path, catalogo: pathlib.Path, args) -> int:
    cadastro = entidades.Cadastro(raiz)
    apelido = (args.apelido or "").strip().lower()

    # TUDO É CONFERIDO AQUI, antes da primeira gravação. Um sindicato criado
    # pela metade — sem gestor, ou com uma categoria que não existe — é pior
    # que nenhum: ele aparece na lista e não funciona.
    if not entidades.APELIDO.match(args.apelido or ""):
        raise Recusado(
            f"apelido {args.apelido!r} inválido: use minúsculas, dígitos e "
            f"hífen, de 1 a 40 caracteres. Ele vai no link que o sindicato "
            f"distribui"
        )
    if any(e.apelido == apelido for e in cadastro.todas()) \
            or (raiz / apelido).exists():
        raise Recusado(f"{apelido} já existe em {raiz}. Nada foi mexido")
    if not (args.nome or "").strip():
        raise Recusado("diga o nome do sindicato, como ele vai aparecer na tela")
    existentes = _categorias_do_catalogo(catalogo)
    if not args.categoria:
        raise Recusado(
            "diga ao menos uma --categoria: sem ela o sindicato não recebe "
            "resposta nenhuma. As que existem: " + ", ".join(existentes)
        )
    desconhecidas = [c for c in args.categoria if c not in existentes]
    if desconhecidas:
        raise Recusado(
            f"categoria que não existe no catálogo: "
            f"{', '.join(desconhecidas)}. As que existem: "
            f"{', '.join(existentes)}"
        )
    if not args.gestor:
        raise Recusado(
            "diga ao menos um --gestor CPF=e-mail: sem gestor ninguém abre "
            "o painel, e o sindicato não tem como enviar a planilha"
        )
    gestores = _gestores_pedidos(args.gestor)
    # O catálogo inteiro é carregado como o servidor carrega. Se o acervo
    # está torto, é melhor saber agora do que na primeira tela do gestor.
    try:
        achado = entendimentos.carregar_categorias(catalogo,
                                                   tuple(args.categoria))
    except Exception as e:  # noqa: BLE001
        raise Recusado(f"o catálogo não carrega com essas categorias: {e}") \
            from None

    ent = cadastro.criar(apelido, args.nome, categorias=tuple(args.categoria))
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    for cpf, email in gestores:
        rol.nomear_gestor(pasta, cpf, email)

    demonstracao = apelido.startswith(entidades.PREFIXO_DEMO)
    print(f"criado: {ent.apelido} — {ent.nome}")
    print(f"  categorias: {', '.join(ent.categorias)} "
          f"({len(achado.acoes)} ação(ões) coletiva(s), "
          f"{len(achado.entendimentos)} entendimento(s))")
    for cpf, email in gestores:
        print(f"  gestor: {_cpf_mascarado(cpf)}  {email}")
    if not achado.acoes and not achado.entendimentos:
        # Não é recusa: a carreira pode estar contratada antes de o jurídico
        # preencher o catálogo dela. Mas quem cria precisa saber que, hoje,
        # este sindicato abre o painel e não recebe resposta nenhuma.
        print("  ATENÇÃO: as categorias contratadas ainda não têm nenhuma "
              "ação nem entendimento no catálogo. O sindicato organiza a "
              "base, mas não recebe resposta sobre o que cada filiado pode "
              "fazer.")
    if demonstracao:
        print("  É DEMONSTRAÇÃO (o apelido começa com "
              f"{entidades.PREFIXO_DEMO!r}): o servidor atende em modo "
              "ensaio e mostra a faixa de demonstração. Não é para dado de "
              "pessoa de verdade.")
    else:
        print("  É um sindicato de verdade: o servidor só o atende fora do "
              "modo ensaio, em região brasileira e com banco.")
    print(f"  o gestor entra em: <endereço do portal>{_endereco(ent.apelido)}")
    print("  o que falta é com o sindicato: o gestor envia a planilha de "
          "filiados pelo painel.")
    return 0


def listar(raiz: pathlib.Path) -> int:
    todas = entidades.Cadastro(raiz).todas()
    if not todas:
        print(f"nenhum sindicato em {raiz}")
        return 0
    for ent in sorted(todas, key=lambda e: e.apelido):
        pasta = ent.pasta(raiz)
        faltas = []
        if not ent.categorias:
            faltas.append("SEM CATEGORIA (não recebe resposta nenhuma)")
        try:
            gestores = len(rol.carregar_gestores(pasta).por_cpf)
        except ValueError:
            gestores = 0
            faltas.append("GESTORES ILEGÍVEL (ninguém abre o painel)")
        else:
            if not gestores:
                faltas.append("SEM GESTOR (ninguém abre o painel)")
        if not (pasta / rol.ARQUIVO).is_file():
            faltas.append("sem planilha de filiados ainda")
        if not ent.ativa:
            faltas.append("SUSPENSO")
        print(f"{ent.apelido}  {ent.nome}  "
              f"[{', '.join(ent.categorias) or '-'}]  "
              f"gestores: {gestores}"
              + ("  " + "; ".join(faltas) if faltas else ""))
    return 0


def categorias(catalogo: pathlib.Path) -> int:
    for slug in _categorias_do_catalogo(catalogo):
        try:
            c = entendimentos.carregar_categorias(catalogo, (slug,))
            detalhe = (f"{len(c.acoes)} ação(ões) coletiva(s), "
                       f"{len(c.entendimentos)} entendimento(s)")
        except Exception as e:  # noqa: BLE001
            detalhe = f"NÃO CARREGA: {e}"
        print(f"{slug}  — {detalhe}")
    return 0


def gestor(raiz: pathlib.Path, args) -> int:
    try:
        ent = entidades.Cadastro(raiz).resolver(args.apelido)
    except LookupError:
        raise Recusado(f"sindicato {args.apelido!r} não existe em {raiz}") \
            from None
    pasta = ent.pasta(raiz)

    if args.o_que == "listar":
        pares = sorted(rol.carregar_gestores(pasta).por_cpf.items())
        if not pares:
            print(f"{ent.apelido} não tem gestor: ninguém abre o painel")
        for cpf, email in pares:
            print(f"{_cpf_mascarado(cpf)}  {email}")
        return 0

    if args.o_que == "nomear":
        if len(args.dados) != 2:
            raise Recusado("nomear: diga o CPF e o e-mail")
        cpf, email = args.dados
        pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            feito = rol.nomear_gestor(pasta, cpf, email.strip())
        except rol.GestorDivergente as e:
            raise Recusado(f"{_cpf_mascarado(cpf)}: {e}") from None
        except ValueError as e:
            raise Recusado(f"nomear: {e}") from None
        print(f"{_cpf_mascarado(cpf)}  {email.strip()}  — "
              + ("agora é gestor" if feito == "nomeado" else "já era gestor"))
        return 0

    if len(args.dados) != 1:
        raise Recusado("tirar: diga o CPF")
    saiu = rol.destituir_gestor(pasta, args.dados[0])
    if not saiu:
        raise Recusado(f"{_cpf_mascarado(args.dados[0])} não é gestor de "
                       f"{ent.apelido}")
    print(f"{_cpf_mascarado(args.dados[0])} deixou de ser gestor de "
          f"{ent.apelido}. Se for filiado, continua entrando no portal.")
    if not rol.carregar_gestores(pasta).por_cpf:
        print(f"ATENÇÃO: {ent.apelido} ficou sem gestor — ninguém abre o "
              f"painel até outro ser nomeado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raiz", default="dados",
                   help="raiz dos dados (padrão: dados)")
    p.add_argument("--catalogo", default=str(entendimentos.PASTA_PADRAO),
                   help="pasta das categorias (padrão: config/categorias)")
    sub = p.add_subparsers(dest="comando", required=True)

    sub.add_parser("listar", help="os sindicatos, e o que falta em cada um")
    sub.add_parser("categorias", help="as carreiras que dá para contratar")

    c = sub.add_parser("criar", help="cria o sindicato e nomeia os gestores")
    c.add_argument("apelido", help="vai no link: minúsculas, dígitos e hífen")
    c.add_argument("nome", help="como o sindicato aparece na tela")
    c.add_argument("--categoria", action="append", default=[],
                   help="carreira contratada (repita para mais de uma)")
    c.add_argument("--gestor", action="append", default=[],
                   metavar="CPF=EMAIL",
                   help="quem abre o painel (repita para mais de um)")

    g = sub.add_parser("gestor", help="quem abre o painel de um sindicato")
    g.add_argument("apelido")
    g.add_argument("o_que", choices=("listar", "nomear", "tirar"))
    g.add_argument("dados", nargs="*", help="CPF, e em `nomear` o e-mail")

    args = p.parse_args(argv)
    raiz = pathlib.Path(args.raiz)
    catalogo = pathlib.Path(args.catalogo)
    try:
        if args.comando == "listar":
            return listar(raiz)
        if args.comando == "categorias":
            return categorias(catalogo)
        if args.comando == "criar":
            return criar(raiz, catalogo, args)
        return gestor(raiz, args)
    except Recusado as e:
        print(f"RECUSADO: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
