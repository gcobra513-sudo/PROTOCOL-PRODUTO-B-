"""O que o SINDICATO entrega: a planilha da base e os documentos que ele tem.

POR QUE ESTE MÓDULO EXISTE. A ingestão morava dentro de duas ferramentas de
linha de comando, e por isso só entrava no produto pelas mãos de quem tem
acesso ao servidor. Quando a planilha e os documentos passaram a entrar
também pela WEB, o caminho errado seria escrever a rota copiando o miolo das
ferramentas: dois caminhos para a mesma coisa divergem, e o que roda sozinho
é o que ninguém olha — a regra que `agenda.tarefas_padrao` já escreve.

Então o miolo desceu para cá, e a ferramenta e a rota chamam as MESMAS
funções. O que cada uma tem de seu é só a casca: uma imprime, a outra
responde em JSON.

AS TRAVAS QUE VIERAM JUNTO, e que a rota herda sem reescrever:

- quem pediu para sair NÃO volta pela planilha (LGPD art. 18, VI), e sem
  conseguir ler os tombstones NADA é gravado — falha fechada;
- o retrato é recalculado DEPOIS de tirar os apagados, porque ele é
  indexado por CPF;
- o documento do sindicato entra com `origem = 'sindicato'`, que é o que
  impede o reenvio de um filiado de apagá-lo, e com `tem_texto` MEDIDO.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import pathlib

from . import acervo, completude, deposito, validacao
from . import documentos_do_sindicato as lote
from .entidades import Entidade

ARQUIVO_DO_ACERVO = "acervo.jsonl"


class IngestaoRecusada(Exception):
    """Não deu para gravar com segurança. Nada foi gravado."""


# ------------------------------------------------------------- a planilha

def sem_apagados(pessoas: list, *, banco_url: str, apelido: str,
                 marcador_de) -> tuple[list, int]:
    """(pessoas que podem entrar, quantas foram tiradas por tombstone).

    QUEM PEDIU PARA SAIR NÃO VOLTA PELA PLANILHA. O apagamento a pedido não
    se sustentaria se a próxima planilha do sindicato recriasse a pessoa — e
    ela VAI estar lá, porque a planilha é o cadastro dele e nós não mexemos
    nela.

    FALHA FECHADA: sem conseguir ler os tombstones não dá para saber quem
    pediu para sair, e gravar assim pode ressuscitar alguém. Levanta
    `IngestaoRecusada`.

    Sem banco não há tombstone para consultar, e a lista volta inteira — é o
    modo de arquivo, sem projeção.
    """
    if not banco_url:
        return list(pessoas), 0
    from . import banco

    try:
        marcados = banco.tombstones(banco_url, apelido)
        if not marcados:
            return list(pessoas), 0
        ficam = [p for p in pessoas if marcador_de(p.cpf) not in marcados]
    except Exception as e:  # noqa: BLE001
        raise IngestaoRecusada(
            f"não deu para conferir quem foi apagado a pedido ({e}). Sem "
            f"esta conferência a ingestão pode recriar quem pediu para sair"
        ) from None
    return ficam, len(pessoas) - len(ficam)


def gravar_planilha(ent: Entidade, raiz: pathlib.Path, pessoas: list, *,
                    origem: str, banco_url: str, quem: str = "") -> dict:
    """Grava a planilha JÁ FILTRADA: o arquivo primeiro, o banco depois.

    `pessoas` tem de ter passado por `sem_apagados`. O retrato é calculado
    AQUI, sobre o que vai ser gravado: a primeira versão gravava o retrato
    calculado antes do filtro, e como ele é indexado por CPF, cada planilha
    reenviada escrevia em disco o CPF de quem tinha pedido para sair.

    `quem` é o marcador de quem enviou, quando veio pela web. Pela linha de
    comando fica vazio: lá quem roda é o operador, e o registro dele é o do
    servidor.
    """
    retrato = completude.retratar(pessoas)
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    registro = {
        "ingerido_em": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "origem": pathlib.PurePath(origem).name,
        "retrato": dataclasses.asdict(retrato),
        "pessoas": [
            {
                "cpf": p.cpf,
                "linha_no_arquivo": p.linha_no_arquivo,
                "campos": p.campos,
                "achados": [
                    {"coluna": a.coluna, "estado": a.estado,
                     "detalhe": a.detalhe}
                    for a in p.achados
                ],
            }
            for p in pessoas
        ],
    }
    if quem:
        registro["enviado_por"] = quem
    deposito.anexar_com_fsync(
        pasta / ARQUIVO_DO_ACERVO,
        json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n",
    )
    projetadas = 0
    if banco_url:
        from . import banco

        projetadas = banco.projetar_acervo(banco_url, ent.apelido, pessoas)
    return {"retrato": retrato, "projetadas": projetadas,
            "arquivo": pasta / ARQUIVO_DO_ACERVO}


# ----------------------------------------------------------- os documentos

def cpfs_da_base(banco_url: str, apelido: str,
                 pasta: pathlib.Path) -> set[str]:
    """Quem a entidade declarou atender. Do banco quando há banco; do rol em
    disco quando não há — e o rol é o mínimo, porque é por ele que alguém
    recebe código de acesso."""
    cpfs: set[str] = set()
    if banco_url:
        from . import banco

        for r in banco.base(banco_url, apelido):
            digitos = validacao.so_digitos(r["linha"].get("cpf", ""))
            if digitos:
                cpfs.add(digitos)
    if not cpfs:
        from . import rol

        try:
            cpfs = {validacao.so_digitos(k)
                    for k in rol.carregar(pasta).por_cpf}
        except Exception:  # noqa: BLE001
            cpfs = set()
    return {c for c in cpfs if c}


def gravar_documentos(ent: Entidade, raiz: pathlib.Path,
                      resultado: lote.Resultado, banco_url: str) -> int:
    """Grava os documentos que CASARAM. Devolve quantos.

    OS BYTES VÃO PARA A ENTREGA, com o nome do contrato: é a pasta que quem
    confere abre, e ela já tem uma convenção. O documento do sindicato entra
    do mesmo jeito que o do filiado — o que os distingue é `origem`, no
    banco.

    O NOME DO ARQUIVO NO DISCO É CALCULADO AQUI, do tipo: o nome que o
    sindicato deu ao arquivo nunca vira caminho.
    """
    entrega = ent.entrega(raiz)
    gravados = 0
    for cpf, docs in resultado.casados.items():
        destino = entrega / cpf
        destino.mkdir(parents=True, exist_ok=True)
        por_tipo: dict[str, int] = {}
        for d in docs:
            indice = por_tipo.get(d.tipo, 0) + 1
            por_tipo[d.tipo] = indice
            nome = (f"{d.tipo}.pdf" if indice == 1 and d.tipo != lote.OUTRO
                    else f"{d.tipo}-{indice}.pdf")
            (destino / nome).write_bytes(d.corpo)
            gravados += 1

        if banco_url:
            from . import banco

            for d in docs:
                soma = hashlib.sha256(d.corpo).hexdigest()
                # `tem_texto` É MEDIDO, documento por documento: o arquivo
                # casa também pelo CPF no NOME, e um de scanner casa assim
                # sem texto nenhum. Esse espera uma pessoa ler.
                _abre, tem_texto, _n = validacao.examinar_pdf(d.corpo)
                with banco.sessao(banco_url, ent.apelido) as cur:
                    cur.execute(
                        # `origem = 'sindicato'`: é o que impede o reenvio
                        # de um filiado de apagar o que o sindicato entregou.
                        "INSERT INTO documento (entidade, cpf, tipo, sha256,"
                        " tem_texto, origem) "
                        "VALUES (%s,%s,%s,%s,%s,'sindicato') "
                        "ON CONFLICT (entidade, cpf, tipo, sha256) "
                        "DO UPDATE SET tem_texto = EXCLUDED.tem_texto,"
                        " origem = 'sindicato'",
                        (ent.apelido, cpf, d.tipo, soma, tem_texto),
                    )
                banco.guardar_achados(banco_url, ent.apelido, cpf, soma,
                                      d.achados)
    return gravados
