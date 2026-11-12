"""As trocas de e-mail que a planilha PEDE e que não valem sozinhas.

POR QUE EXISTE. O portão só é portão porque o e-mail não é escolhido por
quem entra (`rol.py`). Quando a planilha do gestor passou a alimentar o
portão, apareceu o caminho por onde essa regra quebraria: se a planilha
trocasse o e-mail de quem JÁ entra, uma sessão de gestor — uma só,
comprometida — virava todas as contas do sindicato. Troca o e-mail, pede o
código, entra no lugar da pessoa.

Então a planilha faz duas coisas diferentes com o mesmo campo:

- para quem é NOVO no portão, o e-mail vale na hora (`rol.acrescentar`);
- para quem JÁ tem destino, o e-mail diferente vira um PEDIDO aqui, e o
  portão continua mandando o código para o endereço de antes;
- para quem é novo e veio com um e-mail que OUTRA pessoa usa, a ENTRADA
  vira pedido também (`de` vazio): um endereço não recebe o código de
  várias pessoas sem alguém conferir.

QUEM DECIDE é quem opera o servidor, por `ferramentas/trocas_de_email.py`,
depois de conferir por fora. NÃO HÁ ROTA para aprovar, e não é esquecimento:
uma rota de aprovar seria mais uma sessão capaz de trocar e-mail, e a trava
voltaria a depender de uma credencial só.

A AUTORIDADE É UM ARQUIVO APPEND-ONLY, `trocas_de_email.jsonl`, e o estado é
a dobra dele. Guarda também a RECUSA, e isso tem uso: a planilha do sindicato
vai continuar trazendo o e-mail recusado, e sem memória cada envio recriaria
o pedido.

É DADO PESSOAL — CPF e dois e-mails. O apagamento a pedido tira a pessoa
daqui (`remover_pessoa`) e a varredura de vestígios nomeia este arquivo.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
from dataclasses import dataclass, field

from . import deposito, rol, validacao

ARQUIVO = "trocas_de_email.jsonl"

PEDIDA, APROVADA, RECUSADA, RETIRADA = (
    "pedida", "aprovada", "recusada", "retirada")


@dataclass
class Estado:
    #: cpf -> {"de", "para", "quando", "enviado_por"}
    pendentes: dict[str, dict] = field(default_factory=dict)
    #: (cpf, e-mail recusado em minúsculas)
    recusadas: set[tuple[str, str]] = field(default_factory=set)

    def foi_recusada(self, cpf: str, para: str) -> bool:
        return (cpf, para.strip().casefold()) in self.recusadas


def _agora() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def _anexar(pasta: pathlib.Path, registro: dict) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    deposito.anexar_com_fsync(
        pasta / ARQUIVO,
        json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n",
    )


def estado(pasta_entidade: pathlib.Path) -> Estado:
    """O que está pedido e o que já foi recusado, dobrando o arquivo.

    Linha que não dá para interpretar é PULADA, não fatal: um arquivo de
    pedidos ilegível não pode impedir o sindicato de enviar a base. O custo
    de pular é um pedido que some da fila — e o portão, que é o que importa,
    não muda por causa disso.
    """
    e = Estado()
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        return e
    for bruta in caminho.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(bruta)
        except json.JSONDecodeError:
            continue
        if not isinstance(r, dict):
            continue
        cpf = validacao.so_digitos(str(r.get("cpf", "")))
        evento = r.get("evento")
        if evento == PEDIDA:
            e.pendentes[cpf] = {k: r.get(k, "") for k in
                                ("de", "para", "quando", "enviado_por")}
        elif evento in (APROVADA, RETIRADA):
            e.pendentes.pop(cpf, None)
        elif evento == RECUSADA:
            e.pendentes.pop(cpf, None)
            e.recusadas.add((cpf, str(r.get("para", "")).strip().casefold()))
    return e


def pedir(pasta_entidade: pathlib.Path, *, cpf: str, de: str, para: str,
          quem: str = "") -> None:
    _anexar(pasta_entidade, {
        "evento": PEDIDA, "quando": _agora(),
        "cpf": validacao.so_digitos(cpf), "de": de, "para": para,
        "enviado_por": quem,
    })


def retirar(pasta_entidade: pathlib.Path, cpf: str) -> None:
    """A planilha voltou a concordar com o portão: não há mais o que decidir."""
    _anexar(pasta_entidade, {"evento": RETIRADA, "quando": _agora(),
                             "cpf": validacao.so_digitos(cpf)})


class SemPedido(LookupError):
    """Ninguém pediu troca para este CPF."""


def aprovar(pasta_entidade: pathlib.Path, cpf: str) -> dict:
    """Faz o pedido valer. Devolve `{"de", "para"}` — `de` vazio quando era
    uma ENTRADA segurada, e não uma troca.

    O ROL PRIMEIRO, o registro depois: se a escrita do rol falhar, o pedido
    continua pendente e a ferramenta pode ser rodada de novo. Na ordem
    inversa haveria um pedido "aprovado" que nunca valeu, e ninguém olhando.

    `de` é o que o portão tem AGORA, não o que tinha quando o pedido foi
    feito — é o que quem aprova precisa ver. Quem não tem destino hoje
    ENTRA com o e-mail pedido: é a entrada segurada por e-mail repetido, e
    quem opera acabou de dizer que o e-mail é mesmo dela.
    """
    digitos = validacao.so_digitos(cpf)
    pedido = estado(pasta_entidade).pendentes.get(digitos)
    if pedido is None:
        raise SemPedido(digitos)
    de = destino_atual(pasta_entidade, digitos) or ""
    if de:
        feito = rol.trocar_email(pasta_entidade, digitos, pedido["para"])
    else:
        feito = rol.acrescentar(pasta_entidade, [(digitos, pedido["para"])])
    if not feito:
        raise SemPedido("o rol não mudou; o pedido continua esperando")
    _anexar(pasta_entidade, {"evento": APROVADA, "quando": _agora(),
                             "cpf": digitos, "para": pedido["para"]})
    return {"de": de, "para": pedido["para"]}


def outros_com(pasta_entidade: pathlib.Path, cpf: str, email: str) -> list[str]:
    """Os OUTROS CPFs que usam este e-mail: no portão, ou esperando entrar.

    É o que quem opera precisa ver para decidir uma entrada segurada: de
    quem mais é o endereço.
    """
    digitos = validacao.so_digitos(cpf)
    alvo = email.strip().casefold()
    achou: set[str] = set()
    try:
        listas = [rol.carregar(pasta_entidade).por_cpf]
    except rol.RolAusente:
        listas = []
    listas.append(rol.carregar_gestores(pasta_entidade).por_cpf)
    for lista in listas:
        achou |= {c for c, e in lista.items() if e.strip().casefold() == alvo}
    achou |= {c for c, p in estado(pasta_entidade).pendentes.items()
              if not p.get("de")
              and str(p.get("para", "")).strip().casefold() == alvo}
    return sorted(achou - {digitos})


def recusar(pasta_entidade: pathlib.Path, cpf: str) -> dict:
    digitos = validacao.so_digitos(cpf)
    pedido = estado(pasta_entidade).pendentes.get(digitos)
    if pedido is None:
        raise SemPedido(digitos)
    _anexar(pasta_entidade, {"evento": RECUSADA, "quando": _agora(),
                             "cpf": digitos, "para": pedido["para"]})
    return {"para": pedido["para"]}


def destino_atual(pasta_entidade: pathlib.Path, cpf: str) -> str | None:
    """Para onde o portão manda o código deste CPF hoje — os DOIS róis, na
    ordem em que o portão os consulta."""
    digitos = validacao.so_digitos(cpf)
    try:
        achado = rol.carregar(pasta_entidade).email_de(digitos)
    except rol.RolAusente:
        achado = None
    return achado or rol.carregar_gestores(pasta_entidade).email_de(digitos)


def remover_pessoa(pasta_entidade: pathlib.Path, cpf: str) -> int:
    """Tira os pedidos desta pessoa. Para o apagamento a pedido.

    "Append-only" quer dizer "não se edita", não "não se apaga nunca". A
    linha de quem NÃO pediu para sair fica byte a byte.
    """
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        return 0
    digitos = validacao.so_digitos(cpf)
    guardadas: list[str] = []
    sairam = 0
    for bruta in caminho.read_text(encoding="utf-8").splitlines():
        try:
            registro = json.loads(bruta)
        except json.JSONDecodeError:
            guardadas.append(bruta)
            continue
        if isinstance(registro, dict) and validacao.so_digitos(
                str(registro.get("cpf", ""))) == digitos:
            sairam += 1
            continue
        guardadas.append(bruta)
    if not sairam:
        return 0
    tmp = caminho.with_suffix(caminho.suffix + ".parcial")
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                 deposito.MODO_ARQUIVO)
    try:
        os.write(fd, ("".join(l + "\n" for l in guardadas)).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(caminho)
    return sairam
