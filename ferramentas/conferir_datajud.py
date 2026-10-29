#!/usr/bin/env python3
"""
Conferidor de auditoria — lê o DataJud e NÃO confia no robô de protocolo.

Para cada processo, confirma contra a base pública do CNJ o que o tribunal
efetivamente registrou, e compara com o que o lote prometeu:

  - o processo existe e foi distribuído?            (movimento "Distribuição")
  - caiu no órgão julgador esperado?
  - a classe e o assunto são os esperados?
  - foi REDISTRIBUÍDO?    -> sinal objetivo de competência errada
  - foi extinto sem mérito / indeferido?            -> erro sistemático

Emite veredicto nominal por caso e, no fim, o DISJUNTOR ESTATÍSTICO: se a
taxa de redistribuição ou de extinção passar do limiar, o lote deve parar.

Por que o DataJud e não o PJe: automatizar consulta ao PJe é, pela Res. CNJ
185/2013 art. 29 §3º, caminho reservado ao MNI, e uso desproporcional pode
bloquear o usuário. O DataJud é base pública própria do CNJ, com chave
publicada, e consultá-lo não é consultar o PJe.

LIMITE IMPORTANTE: o DataJud NÃO traz partes (nome/CPF). Logo este conferidor
NÃO substitui o pós-voo que baixa o PDF registrado e confere autor. Ele
complementa.

Uso:
    python3 ferramentas/conferir_datajud.py --processos numeros.txt
    DATAJUD_APIKEY='...' python3 ...   # só se o CNJ trocar a chave pública
    python3 ferramentas/conferir_datajud.py --manifesto saida/LOTE/manifesto.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api-publica.datajud.cnj.jus.br"
ALIAS_PADRAO = "api_publica_trf1"

#: A chave da API pública do DataJud. NÃO é segredo: o CNJ a publica em
#: https://datajud-wiki.cnj.jus.br/api-publica/acesso/ justamente para que
#: qualquer pessoa consulte sem cadastro. Guardá-la fora do repositório, como
#: se fosse credencial, só fazia o conferidor não rodar até alguém lembrar de
#: exportar a variável — e o CNJ avisa que pode trocá-la a qualquer momento,
#: então o caminho certo é ter um padrão que funciona hoje e deixar a variável
#: de ambiente sobrepô-lo no dia em que mudar.
#:
#: Lida da wiki do CNJ e conferida por requisição em 29/10/2026: HTTP 200 nos
#: aliases api_publica_trf1, api_publica_stj e api_publica_trt10.
CHAVE_PUBLICA = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

# Classificação por NOME do movimento. Deliberadamente por texto e não por
# código: a tabela do CNJ muda, e um código errado aqui produziria silêncio.
PADRAO_DISTRIBUICAO = re.compile(r"^distribui", re.I)
PADRAO_REDISTRIBUICAO = re.compile(r"redistribui", re.I)
PADRAO_RUIM = re.compile(
    r"extin|improced|indefer|arquivamento definitivo|não-provimento|nao-provimento",
    re.I,
)


class ErroDataJud(RuntimeError):
    pass


#: Documentos pedidos POR PROCESSO. O mesmo número existe em mais de um grau
#: — G1, G2, JE, e ainda o tribunal superior —, e pedir 2 por processo fazia
#: um lote de 100 parar em 200 documentos. O excedente some SEM ERRO, e o
#: coletor leria a ausência como "sem registro no DataJud, defasagem de ~1 dia
#: é normal". Falso silêncio.
TAMANHO_DA_RESPOSTA = 6


def conferir_resposta(dados: dict) -> None:
    """Levanta `ErroDataJud` quando a resposta veio INCOMPLETA.

    O Elasticsearch devolve HTTP 200 com `timed_out: true` e/ou
    `_shards.failed > 0` em falha parcial — e `docs/achados_datajud.md` §4
    mediu exatamente esse regime, com o tjdft estourando 60 s. Sem esta
    conferência, falha parcial volta como menos movimentos e zero erros: a
    pessoa fica sem saber de uma sentença porque um shard piscou, e ninguém
    percebe.
    """
    if "error" in dados:
        raise ErroDataJud(json.dumps(dados["error"])[:200])
    if dados.get("timed_out"):
        raise ErroDataJud(
            "a consulta expirou no servidor do CNJ (timed_out) — resultado "
            "parcial, e parcial não pode passar por completo"
        )
    shards = dados.get("_shards") or {}
    if shards.get("failed"):
        raise ErroDataJud(
            f"{shards['failed']} de {shards.get('total', '?')} shards "
            f"falharam — a resposta está incompleta"
        )


def consultar(numero: str, chave: str, alias: str = ALIAS_PADRAO, timeout: int = 120) -> dict | None:
    """Devolve o _source do processo, ou None se não houver registro."""
    corpo = json.dumps(
        {"size": 1, "query": {"match": {"numeroProcesso": numero}}}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/{alias}/_search",
        data=corpo,
        headers={
            "Authorization": f"APIKey {chave}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ErroDataJud(f"HTTP {e.code} ao consultar {numero}") from e
    conferir_resposta(dados)
    hits = dados.get("hits", {}).get("hits", [])
    return hits[0]["_source"] if hits else None


def consultar_lote(
    numeros: list[str], chave: str, alias: str = ALIAS_PADRAO, timeout: int = 180
) -> dict[str, list[dict]]:
    """Consulta vários processos numa única chamada.

    Medido em 23/10/2026: uma consulta leva 15-30 s, qualquer que seja o número
    de processos pedidos. Em série, 15 mil processos passariam de 100 horas; em
    lotes de ~100, caem para ~1 hora. É a diferença entre viável e inviável.

    Devolve {numero: [fontes]} — uma LISTA porque o mesmo número existe em mais
    de um grau (G1 e a apelação em G2, por exemplo), e tratar isso como um
    registro só esconderia metade da história.
    """
    corpo = json.dumps(
        {
            "size": max(TAMANHO_DA_RESPOSTA * len(numeros), 10),
            "query": {"terms": {"numeroProcesso": numeros}},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/{alias}/_search",
        data=corpo,
        headers={
            "Authorization": f"APIKey {chave}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ErroDataJud(f"HTTP {e.code} na consulta em lote") from e
    conferir_resposta(dados)

    saida: dict[str, list[dict]] = {n: [] for n in numeros}
    for h in dados.get("hits", {}).get("hits", []):
        fonte = h["_source"]
        num = str(fonte.get("numeroProcesso", ""))
        saida.setdefault(num, []).append(fonte)
    return saida


def escolher_grau_originario(fontes: list[dict]) -> dict | None:
    """Entre os graus devolvidos, o que interessa auditar é o de origem (G1/JE).

    A apelação em G2 não diz se a distribuição em 1o grau foi correta; se
    conferissemos o G2, o orgao julgador seria sempre um gabinete do tribunal
    e toda comparacao de competencia daria divergente.
    """
    if not fontes:
        return None
    for preferido in ("G1", "JE"):
        for f in fontes:
            if f.get("grau") == preferido:
                return f
    return fontes[0]


def conferir(
    numero: str,
    fonte: dict | None,
    esperado: dict | None = None,
) -> dict:
    """Compara o registrado com o esperado e devolve veredicto nominal."""
    esperado = esperado or {}
    if fonte is None:
        return {
            "numero": numero,
            "veredicto": "NAO_ENCONTRADO",
            "motivos": ["sem registro no DataJud (pode ser defasagem de ~1 dia)"],
        }

    movimentos = fonte.get("movimentos") or []
    nomes = [str(m.get("nome", "")) for m in movimentos]

    motivos: list[str] = []
    distribuido = any(PADRAO_DISTRIBUICAO.search(n) for n in nomes)
    redistribuido = any(PADRAO_REDISTRIBUICAO.search(n) for n in nomes)
    ruins = sorted({n for n in nomes if PADRAO_RUIM.search(n)})

    if not distribuido:
        motivos.append("sem movimento de distribuição")
    if redistribuido:
        motivos.append("REDISTRIBUIDO — competência provavelmente errada")
    for n in ruins:
        motivos.append(f"movimento adverso: {n}")

    orgao = (fonte.get("orgaoJulgador") or {}).get("nome")
    if esperado.get("orgaoJulgador") and orgao != esperado["orgaoJulgador"]:
        motivos.append(
            f"órgão julgador divergente: registrado {orgao!r}, "
            f"esperado {esperado['orgaoJulgador']!r}"
        )

    classe_cod = str((fonte.get("classe") or {}).get("codigo", ""))
    if esperado.get("classe") and classe_cod != str(esperado["classe"]):
        motivos.append(
            f"classe divergente: registrada {classe_cod}, esperada {esperado['classe']}"
        )

    cods_assunto = {str(a.get("codigo")) for a in (fonte.get("assuntos") or [])}
    if esperado.get("assunto") and str(esperado["assunto"]) not in cods_assunto:
        motivos.append(
            f"assunto esperado {esperado['assunto']} ausente (registrados: "
            f"{sorted(cods_assunto)})"
        )

    if any(m.startswith("REDISTRIBUIDO") or "divergente" in m for m in motivos):
        veredicto = "DIVERGENTE"
    elif motivos:
        veredicto = "ATENCAO"
    else:
        veredicto = "OK"

    return {
        "numero": numero,
        "veredicto": veredicto,
        "motivos": motivos,
        "grau": fonte.get("grau"),
        "orgaoJulgador": orgao,
        "classe": (fonte.get("classe") or {}).get("nome"),
        "assuntos": [a.get("nome") for a in (fonte.get("assuntos") or [])],
        "dataAjuizamento": fonte.get("dataAjuizamento"),
        "qtd_movimentos": len(movimentos),
    }


def disjuntor(resultados: list[dict], limiar_redistribuicao: float, limiar_adverso: float) -> dict:
    """O disjuntor que falta hoje: estatístico, sobre o lote, não por caso."""
    encontrados = [r for r in resultados if r["veredicto"] != "NAO_ENCONTRADO"]
    n = len(encontrados) or 1
    redis = sum(
        1 for r in encontrados if any("REDISTRIBUIDO" in m for m in r["motivos"])
    )
    adversos = sum(
        1 for r in encontrados if any("movimento adverso" in m for m in r["motivos"])
    )
    divergentes = sum(1 for r in encontrados if r["veredicto"] == "DIVERGENTE")

    parar: list[str] = []
    if redis / n > limiar_redistribuicao:
        parar.append(
            f"taxa de redistribuição {redis}/{n} = {redis/n:.1%} "
            f"> limiar {limiar_redistribuicao:.1%}"
        )
    if adversos / n > limiar_adverso:
        parar.append(
            f"taxa de movimentos adversos {adversos}/{n} = {adversos/n:.1%} "
            f"> limiar {limiar_adverso:.1%}"
        )
    return {
        "conferidos": len(encontrados),
        "nao_encontrados": len(resultados) - len(encontrados),
        "redistribuidos": redis,
        "com_movimento_adverso": adversos,
        "divergentes": divergentes,
        "PARAR_LOTE": bool(parar),
        "razoes": parar,
    }


def _numeros_do_manifesto(caminho: pathlib.Path) -> list[tuple[str, dict]]:
    saida = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        reg = json.loads(linha)
        num = reg.get("numero_processo") or reg.get("numeroProcesso")
        if not num:
            continue
        esperado = {
            k: reg.get(k)
            for k in ("orgaoJulgador", "classe", "assunto")
            if reg.get(k)
        }
        saida.append((re.sub(r"\D", "", str(num)), esperado))
    return saida


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--processos", help="arquivo com um número de processo por linha")
    g.add_argument("--manifesto", help="manifesto.jsonl do lote")
    p.add_argument("--alias", default=ALIAS_PADRAO)
    p.add_argument("--pausa", type=float, default=1.0)
    p.add_argument(
        "--tamanho-lote",
        type=int,
        default=100,
        help="processos por consulta (uma consulta custa 15-30 s "
        "independentemente do tamanho)",
    )
    p.add_argument("--limiar-redistribuicao", type=float, default=0.02)
    p.add_argument("--limiar-adverso", type=float, default=0.05)
    p.add_argument("--saida", default=None, help="grava o relatório em JSON")
    args = p.parse_args()

    chave = os.environ.get("DATAJUD_APIKEY", "").strip() or CHAVE_PUBLICA

    if args.manifesto:
        alvos = _numeros_do_manifesto(pathlib.Path(args.manifesto))
    else:
        alvos = [
            (re.sub(r"\D", "", l), {})
            for l in pathlib.Path(args.processos).read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]

    if not alvos:
        print("nada a conferir", file=sys.stderr)
        return 1

    esperados = dict(alvos)
    numeros = [n for n, _ in alvos]
    resultados = []
    i = 0
    for inicio in range(0, len(numeros), args.tamanho_lote):
        fatia = numeros[inicio : inicio + args.tamanho_lote]
        try:
            achados = consultar_lote(fatia, chave, args.alias)
        except ErroDataJud as e:
            achados = {}
            erro = str(e)
        else:
            erro = None
        for numero in fatia:
            i += 1
            if erro is not None:
                r = {"numero": numero, "veredicto": "ERRO_CONSULTA", "motivos": [erro]}
            else:
                fonte = escolher_grau_originario(achados.get(numero, []))
                r = conferir(numero, fonte, esperados.get(numero) or {})
            resultados.append(r)
            marca = {"OK": "  ok ", "ATENCAO": "  ~~ ", "DIVERGENTE": "  !! "}.get(
                r["veredicto"], "  ?? "
            )
            print(
                f"{marca}[{i}/{len(alvos)}] {numero} {r['veredicto']}"
                + (f" :: {'; '.join(r['motivos'])}" if r["motivos"] else ""),
                flush=True,
            )
        time.sleep(args.pausa)

    resumo = disjuntor(resultados, args.limiar_redistribuicao, args.limiar_adverso)
    print("\n" + "=" * 62)
    print("RESUMO DA AUDITORIA")
    for k, v in resumo.items():
        print(f"  {k:.<28} {v}")
    if resumo["PARAR_LOTE"]:
        print("\n  *** DISJUNTOR ACIONADO — o lote deve parar. ***")

    if args.saida:
        pathlib.Path(args.saida).write_text(
            json.dumps(
                {"resumo": resumo, "casos": resultados}, ensure_ascii=False, indent=1
            ),
            encoding="utf-8",
        )
        print(f"\n  relatório -> {args.saida}")

    return 3 if resumo["PARAR_LOTE"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
