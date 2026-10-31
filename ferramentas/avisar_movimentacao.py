#!/usr/bin/env python3
"""
Avisa quem pediu para ser avisado. É o que roda sozinho, depois da coleta.

    python3 ferramentas/avisar_movimentacao.py --entidade demo-sindicato

    # ver o que SERIA enviado, sem enviar nada:
    python3 ferramentas/avisar_movimentacao.py --entidade demo-sindicato --seco

O cadastro pergunta "quero receber aviso por e-mail quando houver
movimentação nos meus processos", guarda a resposta — e nada nunca lia esse
campo. Opt-in coletado e ignorado é pior que não ter: a pessoa marcou achando
que seria avisada, e continuou ligando para o sindicato.

A ORDEM IMPORTA, e é esta: coletar primeiro, avisar depois. O coletor
(`coletar_movimentacao.py`) fala com o tribunal; este aqui só lê o que ele
trouxe e manda e-mail. Juntar os dois faria uma falha de rede do DataJud
derrubar o aviso de quem já tinha novidade guardada.

CÓDIGOS DE SAÍDA, para o agendador:

    0  avisou tudo o que havia (inclusive quando não havia nada)
    1  alguém ficou sem aviso — e-mail que não serve, ou envio que falhou
    2  não deu para começar (sem banco, entidade inexistente)
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import aviso as mod  # noqa: E402
from servidor import acompanhamento, banco, entidades, remetente  # noqa: E402


def _movimentos_do_diario(pasta: pathlib.Path) -> list[mod.Movimento]:
    """O que a coleta trouxe. O diário é a autoridade, como no resto."""
    return [
        mod.Movimento(numero=m.numero, grau=m.grau, data=m.data, nome=m.nome)
        for m in acompanhamento.ler_diario_de_movimentos(
            pasta / "movimentos.jsonl"
        )
    ]


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--entidade", required=True)
    p.add_argument("--raiz", default="dados")
    p.add_argument("--banco", default=os.environ.get("PROTOCOL_DATABASE_URL", ""))
    p.add_argument("--portal", default=os.environ.get("PROTOCOL_PORTAL", ""),
                   help="endereço do portal, para o e-mail dizer onde ver o "
                        "resto. Vazio, nenhum link é inventado")
    p.add_argument("--seco", action="store_true",
                   help="mostra o que seria enviado e NÃO envia")
    args = p.parse_args()

    if not args.banco:
        print(
            "sem banco (--banco ou PROTOCOL_DATABASE_URL) não há como saber "
            "o que já foi avisado, e sem isso o aviso ou repete todo dia ou "
            "não sai nunca",
            file=sys.stderr,
        )
        return 2

    raiz = pathlib.Path(args.raiz)
    try:
        ent = entidades.Cadastro(raiz).resolver(args.entidade)
    except LookupError:
        print(f"entidade {args.entidade!r} não existe em {raiz}",
              file=sys.stderr)
        return 2

    movimentos = _movimentos_do_diario(ent.pasta(raiz))
    pessoas = banco.destinatarios(args.banco, ent.apelido)
    conhecidos = banco.processos_coletados(args.banco, ent.apelido)

    # Um conjunto de chaves por pessoa: duas pessoas no mesmo processo têm
    # estados diferentes, e quem se cadastrou ontem não pode herdar o "já
    # avisado" de quem está há meses.
    por_pessoa = {
        d.cpf: banco.chaves_ja_avisadas(args.banco, ent.apelido, d.cpf)
        for d in pessoas
    }

    enviados = 0
    suprimidos = 0
    falharam: list[str] = []
    sem_destino: list[str] = []
    for d in pessoas:
        r = mod.preparar(
            [d], movimentos,
            ja_avisados=por_pessoa.get(d.cpf, set()),
            processos_conhecidos=conhecidos,
            endereco=args.portal,
        )
        sem_destino += r.sem_destino
        # A SUPRESSÃO DA ESTREIA É GRAVADA PRIMEIRO, e independe de envio:
        # ela não gera e-mail nenhum. Sem isto, o histórico volta amanhã.
        if not args.seco and r.estreia.get(d.cpf):
            banco.marcar_avisado(args.banco, ent.apelido, d.cpf,
                                 r.estreia[d.cpf], motivo="estreia")
            suprimidos += len(r.estreia[d.cpf])
        for m in r.avisos:
            if args.seco:
                print(f"--- PARA {m.destino} ({m.cpf})")
                print(m.corpo)
                enviados += 1
                continue
            correio = (
                remetente.PorSmtp(
                    os.environ.get("PROTOCOL_SMTP_HOST", ""),
                    int(os.environ.get("PROTOCOL_SMTP_PORTA", "587")),
                    os.environ.get("PROTOCOL_SMTP_USUARIO", ""),
                    os.environ.get("PROTOCOL_SMTP_SENHA", ""),
                    os.environ.get("PROTOCOL_SMTP_REMETENTE", ""),
                )
                if os.environ.get("PROTOCOL_SMTP_HOST")
                else remetente.ParaArquivo(raiz)
            )
            try:
                correio.enviar_mensagem(m.destino, m.assunto, m.corpo)
            except Exception as e:  # noqa: BLE001
                # NÃO MARCA. Falha de envio tem de ser tentada de novo
                # amanhã: entre nunca saber e saber duas vezes, saber duas.
                falharam.append(f"{m.cpf}: {e}")
                continue
            banco.marcar_avisado(args.banco, ent.apelido, m.cpf, m.chaves)
            enviados += 1

    # A MOVIMENTAÇÃO VAI PARA O BANCO DEPOIS DE DECIDIR, nunca antes: gravá-la
    # primeiro faria todo processo parecer "já conhecido" e ninguém seria
    # avisado na própria rodada em que a novidade chegou.
    if not args.seco:
        banco.guardar_movimentos(args.banco, ent.apelido, movimentos)

    print(f"\n  {len(pessoas)} pessoa(s) pediram aviso")
    print(f"  {enviados} e-mail(s) {'seriam enviados' if args.seco else 'enviados'}")
    if suprimidos:
        print(f"  {suprimidos} movimento(s) de ESTREIA, memorizados sem aviso")
    if sem_destino:
        print(f"  {len(sem_destino)} ficaram SEM aviso:")
        for s in sem_destino[:20]:
            print(f"    {s}")
    if falharam:
        print(f"  {len(falharam)} envios FALHARAM (serão tentados de novo):")
        for f in falharam[:20]:
            print(f"    {f}")
    return 1 if (sem_destino or falharam) else 0


if __name__ == "__main__":
    raise SystemExit(main())
