"""
As teses de UM sindicato, com o alcance na base dele — e o aviso das
novidades a quem decide.

`nucleo/teses.py` sabe listar as teses de um catálogo e simular quem cada uma
alcança. Aqui isso é juntado com a base de um sindicato, para as três
superfícies que mostram a mesma coisa: o painel do escritório, o painel da
diretoria e o e-mail da manhã. Uma função só, para os três darem o mesmo
número.

O AVISO É DIÁRIO E NÃO REPETE: cada novidade é avisada uma vez, e o que já
foi avisado fica em `teses_avisadas.json`, na pasta do sindicato. E é
cartão-postal, como os outros: tribunal, tema e contagens — nunca nome.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

from nucleo import entendimentos, teses

from . import banco, deposito, escritorios, fichas, rol, substituidos

AVISADAS = "teses_avisadas.json"


def da_entidade(ent, raiz: pathlib.Path, *, banco_url: str = "",
                ambiente: dict | None = None,
                hoje: str | None = None) -> dict:
    """`{"teses": [...], "novidades": [...]}` deste sindicato. Só contagens.

    O ALCANCE É SIMULAÇÃO: quantos poderiam SE a tese fosse conferida.
    """
    catalogo = entendimentos.do_ambiente(tuple(ent.categorias), ambiente)
    pasta = ent.pasta(raiz)
    if banco_url:
        registros = banco.base(banco_url, ent.apelido)
        lidos = banco.fatos_lidos_da_entidade(banco_url, ent.apelido)
    else:
        registros, lidos = deposito.ler_diario(pasta), None
    lista = teses.do_catalogo(catalogo)
    alcance = teses.impacto(
        catalogo, registros, lidos_por_cpf=lidos,
        rol_por_cpf=substituidos.por_cpf(pasta),
        fichas_por_cpf=fichas.por_cpf(pasta))
    conferida = {t.id: t.conferida for t in lista}
    hoje = hoje or dt.datetime.now(dt.UTC).date().isoformat()
    return {
        "teses": [{
            "id": t.id, "tipo": t.tipo, "rotulo": t.rotulo,
            "tribunal": t.tribunal, "situacao": t.situacao, "data": t.data,
            "questao": t.questao, "tese": t.tese, "fonte": t.fonte,
            "conferida": t.conferida, **alcance[t.id],
        } for t in lista],
        "novidades": [{
            "id": n.id, "evento": n.evento, "data": n.data,
            "rotulo": n.rotulo,
            "frase": teses.frase_da_novidade(
                n, sindicato=ent.nome,
                poderiam=alcance[n.id]["poderiam"],
                dependem=alcance[n.id]["dependem"],
                conferida=conferida[n.id]),
        } for n in teses.novidades(lista, hoje=hoje)],
    }


def pessoas_da_tese(ent, raiz: pathlib.Path, tese_id: str, *,
                    banco_url: str = "",
                    ambiente: dict | None = None) -> list[dict] | None:
    """Quem esta tese alcança na base deste sindicato: `[{cpf, nome, como}]`.
    `None` se a tese não é do catálogo dele. Quem chama decide QUEM pode ver
    QUAIS nomes — aqui sai a lista inteira."""
    catalogo = entendimentos.do_ambiente(tuple(ent.categorias), ambiente)
    if tese_id not in {t.id for t in teses.do_catalogo(catalogo)}:
        return None
    pasta = ent.pasta(raiz)
    if banco_url:
        registros = banco.base(banco_url, ent.apelido)
        lidos = banco.fatos_lidos_da_entidade(banco_url, ent.apelido)
    else:
        registros, lidos = deposito.ler_diario(pasta), None
    return teses.alcancadas(
        catalogo, registros, tese_id, lidos_por_cpf=lidos,
        rol_por_cpf=substituidos.por_cpf(pasta),
        fichas_por_cpf=fichas.por_cpf(pasta))


def _ja_avisadas(pasta: pathlib.Path) -> set[str]:
    try:
        return set(json.loads((pasta / AVISADAS).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return set()


def mensagem(sindicato: str, frases: list[str]) -> tuple[str, str]:
    """(assunto, corpo) do aviso da manhã."""
    quantas = ("1 novidade" if len(frases) == 1
               else f"{len(frases)} novidades")
    corpo = (f"Bom dia. Há {quantas} nos tribunais para o {sindicato}:\n\n"
             + "\n\n".join(f"- {f}" for f in frases)
             + "\n\nOs números são uma simulação: quantas pessoas teriam o "
               "caminho aberto se a tese for conferida por advogado. Nada "
               "muda para o filiado antes disso.\n\nA lista das teses e o "
               "alcance de cada uma estão no portal do sindicato. Este "
               "aviso não traz o nome nem os dados de ninguém.\n")
    return f"{sindicato}: {quantas} nos tribunais", corpo


def avisar_novidades(ent, raiz: pathlib.Path, *, correio, banco_url: str = "",
                     ambiente: dict | None = None,
                     hoje: str | None = None) -> dict:
    """Avisa por e-mail as novidades que ainda não foram avisadas: a quem é
    de cada escritório contratado, e aos gestores do sindicato.

    Devolve `{novas, avisados, falharam}`. Só marca como avisada a novidade
    cujo e-mail saiu para ALGUÉM — a que não saiu é tentada na rodada
    seguinte.
    """
    pasta = ent.pasta(raiz)
    todas = da_entidade(ent, raiz, banco_url=banco_url, ambiente=ambiente,
                        hoje=hoje)["novidades"]
    vistas = _ja_avisadas(pasta)
    novas = [n for n in todas
             if f"{n['id']}|{n['evento']}|{n['data']}" not in vistas]
    resultado = {"novas": len(novas), "avisados": 0, "falharam": 0}
    if not novas:
        return resultado
    destinos = {email for e in escritorios.cadastrados(pasta)
                for email in e.pessoas.values()}
    try:
        destinos |= set(rol.carregar_gestores(pasta).por_cpf.values())
    except (rol.RolAusente, ValueError):
        pass
    assunto, corpo = mensagem(ent.nome, [n["frase"] for n in novas])
    for destino in sorted(d for d in destinos if d):
        try:
            correio.enviar_mensagem(destino, assunto, corpo)
            resultado["avisados"] += 1
        except Exception:  # noqa: BLE001 — a conta volta para quem chama
            resultado["falharam"] += 1
    if resultado["avisados"]:
        vistas |= {f"{n['id']}|{n['evento']}|{n['data']}" for n in novas}
        (pasta / AVISADAS).write_text(
            json.dumps(sorted(vistas), ensure_ascii=False), encoding="utf-8")
    return resultado
