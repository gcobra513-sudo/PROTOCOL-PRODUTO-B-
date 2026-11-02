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


def apagar(url: str, ent: Entidade, raiz: pathlib.Path, cpf: str, *,
           motivo: str, pedido_por: str, marcar_cpf) -> dict:
    """Apaga esta pessoa de tudo, e CONFERE no fim.

    A ORDEM É O DESENHO, e cada passo está onde está por um motivo:

    1. **O TOMBSTONE, commitado sozinho.** É ele que torna a operação
       retomável e que ativa o bloqueio de reingestão imediatamente. Na
       mesma transação das exclusões, uma falha o desfaria junto — a pessoa
       teria pedido para sair, o processo teria caído, e não haveria
       registro de que alguém pediu nada. Se ele não grava, NADA começa.

    2. **O DIÁRIO, antes do banco.** O diário é a AUTORIDADE; o banco é
       projeção dele. Apagando o banco primeiro, uma falha antes da redação
       deixa o diário intacto — e a próxima `banco.reconstruir`, que é a
       operação de RECUPERAÇÃO, ressuscita a pessoa. O apagamento seria
       desfeito pela função que existe para consertar as coisas.

    3. Os arquivos em disco, os róis e o acervo.

    4. **O banco.**

    5. **`vestigios`**, e é por isso que esta função devolve o que devolve.
       Não existe campo "apagado": quem chama confere a lista. Vazia
       significa terminou; não vazia significa reexecutar, e o operador tem
       a ferramenta.

    `marcar_cpf` é INJETADO para este módulo não importar o portão: o
    apagamento não tem nada a ver com autenticação, e acoplar os dois faria
    um depender do segredo do outro.
    """
    digitos = validacao.so_digitos(cpf)
    if len(digitos) != 11:
        raise ValueError("apagar exige CPF de 11 dígitos")

    # 1. O TOMBSTONE PRIMEIRO. Se isto levantar, propaga e nada mais roda.
    banco.marcar_tombstone(url, ent.apelido, marcar_cpf(digitos),
                           motivo, pedido_por)

    # 2. O diário, que é a autoridade.
    redigidos = deposito.redigir_no_diario(ent, raiz, digitos)

    # 3. Os arquivos, os róis e o acervo.
    import shutil

    arquivos = 0
    pasta = ent.pasta(raiz)
    for alvo in (ent.entrega(raiz) / digitos,
                 pasta / deposito.HISTORICO / digitos):
        if alvo.is_dir():
            arquivos += sum(1 for _ in alvo.rglob("*") if _.is_file())
            shutil.rmtree(alvo)

    saiu_do_rol = rol.remover(pasta, digitos)
    saiu_do_acervo = _remover_do_acervo(pasta, digitos)

    # 4. O banco.
    do_banco = banco.apagar_pessoa(url, ent.apelido, digitos)

    # 5. A CONFERÊNCIA. Medir, não declarar.
    return {
        "marcador": _marcador(digitos),
        "banco": do_banco,
        "diario": redigidos,
        "arquivos": arquivos,
        "rol": saiu_do_rol,
        "acervo": saiu_do_acervo,
        "vestigios": vestigios(url, ent, raiz, digitos),
    }


def _remover_do_acervo(pasta: pathlib.Path, cpf: str) -> int:
    from . import acervo as mod_acervo

    return mod_acervo.remover_pessoa(pasta / "acervo.jsonl", cpf)
