"""Apagamento a pedido — LGPD art. 18, VI.

QUEM ACIONA É O SINDICATO, pelo painel. Ele tem a relação com o filiado e
foi ele que nos confiou o dado; sob a LGPD ele tende a ser o CONTROLADOR e
nós o operador, e é o controlador que responde ao titular. É também a regra
da casa: quem fala com o filiado é o sindicato.

ESTE MÓDULO NÃO DECLARA, ELE MEDE. Não existe campo `apagado = true` no
esquema, e a ausência é deliberada: um campo desses é uma AFIRMAÇÃO, e a
auditoria de 31/10 derrubou sete afirmações assim neste mesmo repositório —
em cada caso havia um comentário dizendo que algo era verdade e nenhuma
medição por trás. `vestigios()` varre; `apagar()` a chama no fim e devolve o
que sobrou.

A ORDEM É O DESENHO, e está em `apagar()`.

Spec: `docs/superpowers/specs/2026-11-02-apagamento-a-pedido-design.md`
"""
from __future__ import annotations

import json
import pathlib

from . import banco, deposito, rol, validacao
from .entidades import Entidade


def _marcador(cpf: str) -> str:
    """Um pedaço de marcador para NOMEAR o vestígio sem publicar o CPF.

    Quem lê um vestígio precisa saber de quem ele é para conferir, e o CPF
    em claro numa lista de diagnóstico é um segundo lugar com dado pessoal.
    """
    import hashlib

    return hashlib.sha256(validacao.so_digitos(cpf).encode()).hexdigest()[:12]


def vestigios(url: str, ent: Entidade, raiz: pathlib.Path,
              cpf: str) -> list[str]:
    """O que AINDA existe desta pessoa, em qualquer lugar.

    Vazio é a única prova aceitável de que o apagamento terminou. `apagar()`
    chama isto no fim e, se não vier vazio, NÃO diz que apagou.

    Serve três coisas: a conferência dentro de `apagar`, a asserção do teste,
    e a ferramenta de retomada do operador.

    OLHA NO `historico/` de propósito. É o lugar que se esquece, e é onde
    mora o PDF de sentença de um reenvio anterior — apagar `entrega/` e
    parar ali deixaria o documento em disco com o apagamento declarado
    concluído.
    """
    digitos = validacao.so_digitos(cpf)
    marca = _marcador(digitos)
    achados: list[str] = []
    if len(digitos) != 11:
        return achados

    if url:
        with banco.sessao(url, ent.apelido) as cur:
            for tabela in banco._TABELAS_DO_APAGAMENTO:
                cur.execute(
                    f"SELECT count(*) FROM {tabela} WHERE cpf = %s",
                    (digitos,),
                )
                quantas = cur.fetchone()[0]
                if quantas:
                    achados.append(
                        f"banco: {quantas} linha(s) em {tabela} ({marca})"
                    )

    pasta = ent.pasta(raiz)

    for registro in deposito.ler_diario(pasta):
        linha = registro.get("linha")
        if (isinstance(linha, dict)
                and validacao.so_digitos(linha.get("cpf") or "") == digitos):
            achados.append(
                f"diário: envio {registro.get('protocolo', '?')} com "
                f"conteúdo ({marca})"
            )

    entregue = ent.entrega(raiz) / digitos
    if entregue.is_dir():
        quantos = len(list(entregue.iterdir()))
        achados.append(f"entrega: {quantos} arquivo(s) em disco ({marca})")

    guardado = pasta / deposito.HISTORICO / digitos
    if guardado.is_dir():
        quantos = sum(1 for _ in guardado.rglob("*") if _.is_file())
        achados.append(f"historico: {quantos} arquivo(s) de reenvio ({marca})")

    if rol.carregar(pasta).email_de(digitos) if _rol_legivel(pasta) else False:
        achados.append(f"rol: linha em {rol.ARQUIVO} ({marca})")
    if _gestores_legivel(pasta) and rol.carregar_gestores(
            pasta).email_de(digitos):
        achados.append(f"rol: linha em {rol.ARQUIVO_GESTORES} ({marca})")

    # `acervo.ler` NÃO serve aqui: ela lê a PLANILHA do sindicato (CSV ou
    # xlsx). O `acervo.jsonl` é outro formato — uma linha por INGESTÃO, com
    # uma lista `pessoas` dentro. Confundir os dois fez este teste falhar.
    quantas = 0
    jsonl = pasta / "acervo.jsonl"
    if jsonl.is_file():
        for bruto in jsonl.read_text(encoding="utf-8").splitlines():
            if not bruto.strip():
                continue
            try:
                registro = json.loads(bruto)
            except json.JSONDecodeError:
                continue
            for pessoa in registro.get("pessoas") or ():
                if validacao.so_digitos(
                        (pessoa or {}).get("cpf", "")) == digitos:
                    quantas += 1
    if quantas:
        achados.append(f"acervo: {quantas} linha(s) de planilha ({marca})")

    return achados


def _rol_legivel(pasta: pathlib.Path) -> bool:
    """Rol ausente ou inválido não é vestígio — é ausência de dado.

    Deixar a exceção subir faria a CONFERÊNCIA do apagamento falhar por um
    arquivo malformado do sindicato, e aí ninguém consegue nem saber se
    sobrou alguma coisa.
    """
    try:
        rol.carregar(pasta)
        return True
    except Exception:  # noqa: BLE001
        return False


def _gestores_legivel(pasta: pathlib.Path) -> bool:
    try:
        rol.carregar_gestores(pasta)
        return True
    except Exception:  # noqa: BLE001
        return False
