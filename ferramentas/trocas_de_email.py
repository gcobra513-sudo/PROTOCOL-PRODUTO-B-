#!/usr/bin/env python3
"""
As trocas de e-mail que a planilha do sindicato pediu, e a decisão sobre elas.

A planilha que o gestor envia põe gente NOVA no acesso na hora. O que ela não
faz é trocar o e-mail de quem já entra, nem pôr no acesso gente nova com um
e-mail que outra pessoa usa: as duas coisas ficam pedidas, e só valem depois
que alguém AQUI confere — por telefone, por e-mail ao endereço antigo, pelo
que o contrato com o sindicato combinar. O motivo está em `servidor/trocas.py`:
se a troca valesse sozinha, uma conta de gestor comprometida viraria todas as
contas.

    python3 ferramentas/trocas_de_email.py --entidade demo-sindicato listar
    python3 ferramentas/trocas_de_email.py --entidade demo-sindicato aprovar 11144477735
    python3 ferramentas/trocas_de_email.py --entidade demo-sindicato recusar 11144477735

    python3 ferramentas/trocas_de_email.py --entidade demo-sindicato confiar reparticao.gov.br

`confiar` é para o domínio da repartição ou da cooperativa: fora dos
provedores comuns, um domínio só recebe três pessoas novas sem conferência,
e as demais esperam. Confiar vale para ESTE sindicato, libera quem esperava
por causa do domínio, e as próximas planilhas não seguram mais ninguém dali.

`aprovar` e `recusar` aceitam vários CPFs. A recusa fica guardada: a mesma
planilha, reenviada, não recria o pedido.

SAI COM CÓDIGO != 0 se algum CPF não tinha troca pedida — e os outros, que
tinham, são decididos assim mesmo; a saída diz qual foi qual.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import entidades, rol, trocas  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entidade", required=True, help="apelido da entidade")
    p.add_argument("--raiz", default="dados",
                   help="raiz dos dados (padrão: dados)")
    p.add_argument("acao",
                   choices=("listar", "aprovar", "recusar", "confiar"))
    p.add_argument("cpfs", nargs="*",
                   help="CPFs a decidir — ou, em `confiar`, os domínios")
    args = p.parse_args()

    raiz = pathlib.Path(args.raiz)
    try:
        ent = entidades.Cadastro(raiz).resolver(args.entidade)
    except LookupError:
        print(f"entidade {args.entidade!r} não existe em {raiz}",
              file=sys.stderr)
        return 2
    pasta = ent.pasta(raiz)

    if args.acao == "listar":
        pendentes = trocas.estado(pasta).pendentes
        if not pendentes:
            print("nenhuma troca de e-mail esperando")
            return 0
        print(f"{len(pendentes)} pedido(s) esperando em {ent.apelido}:\n")
        por_dominio: dict[str, list[str]] = {}
        for cpf, pedido in sorted(pendentes.items()):
            # O e-mail de HOJE, lido do portão agora — não o que valia
            # quando a planilha chegou.
            hoje = trocas.destino_atual(pasta, cpf)
            if hoje:
                print(f"  {cpf}  troca: {hoje}  ->  {pedido['para']}"
                      f"   (pedida em {pedido['quando']})")
                # Quem decide precisa saber se a pessoa JÁ FOI AVISADA no
                # e-mail de hoje: se foi e não reclamou, é um dado; se não
                # foi, aprovar é decidir sem ela saber.
                print(f"               dono avisado no e-mail de hoje: "
                      f"{'sim' if pedido.get('dono_avisado') else 'NÃO'}")
                continue
            # ENTRADA NOVA segurada: o e-mail é de mais alguém. Quem
            # decide precisa ver de quem.
            print(f"  {cpf}  entrada nova com {pedido['para']}"
                  f"   (pedida em {pedido['quando']})")
            if pedido.get("motivo") == trocas.DOMINIO:
                dominio = rol.dominio_registravel(pedido["para"])
                por_dominio.setdefault(dominio, []).append(cpf)
                print(f"               segurada pelo domínio {dominio}")
                continue
            outros = trocas.outros_com(pasta, cpf, pedido["para"])
            print(f"               mesmo e-mail de: "
                  f"{', '.join(outros) or '(ninguém mais, hoje)'}")
        for dominio, cpfs in sorted(por_dominio.items()):
            # O QUE DECIDIR sobre um domínio: se é o da repartição, confiar
            # uma vez libera todos; se ninguém o reconhece, é o sinal.
            print(f"\n  domínio {dominio}: {len(cpfs)} esperando. Se é "
                  f"legítimo para este sindicato:\n"
                  f"    python3 ferramentas/trocas_de_email.py --raiz "
                  f"{raiz} --entidade {ent.apelido} confiar {dominio}")
        return 0

    if args.acao == "confiar":
        if not args.cpfs:
            print("confiar: diga o domínio", file=sys.stderr)
            return 2
        for dominio in args.cpfs:
            try:
                confiado, liberados = trocas.confiar_dominio(pasta, dominio)
            except ValueError as e:
                print(f"{e}: nada foi feito", file=sys.stderr)
                return 2
            print(f"confiado: {confiado}, para {ent.apelido}. "
                  f"{len(liberados)} pessoa(s) que esperavam por ele "
                  f"entraram no acesso.")
        return 0

    if not args.cpfs:
        print(f"{args.acao}: diga o CPF", file=sys.stderr)
        return 2
    faltou = False
    for cpf in args.cpfs:
        try:
            if args.acao == "aprovar":
                feito = trocas.aprovar(pasta, cpf)
                print(f"aprovada: {cpf}  "
                      f"{feito['de'] or '(entrada nova)'}  ->  {feito['para']}")
            else:
                feito = trocas.recusar(pasta, cpf)
                print(f"recusada: {cpf}  (continua como estava; "
                      f"{feito['para']} não será pedido de novo)")
        except trocas.SemPedido as e:
            faltou = True
            print(f"sem troca pedida para {cpf}: nada foi feito ({e})",
                  file=sys.stderr)
    return 1 if faltou else 0


if __name__ == "__main__":
    raise SystemExit(main())
