"""
O encaminhamento do filiado ao escritório que o sindicato contratou.

Sindicatos terceirizam o jurídico. Quem recebe o documento e propõe a ação
é um escritório contratado, e ao sindicato cabe a TRIAGEM: dizer para qual
escritório vai aquela pessoa, com aquela demanda. Hoje isso corre por e-mail
e WhatsApp, e três coisas se perdem: o sindicato não sabe o que o escritório
recebeu; o escritório recebe documento solto, sem saber de quem é a triagem;
e o filiado não sabe com quem o caso dele está — liga para a sede.

ESTE MÓDULO É A PONTE, e é do Produto B: o que acontece DENTRO do
escritório depois que o documento chega (montar a peça, propor a ação) não
é assunto daqui.

AS REGRAS, e o contrário de cada uma engana alguém:

1. **O escritório é da ENTIDADE.** O cadastro (`escritorios.json`) mora na
   pasta dela. Um escritório que atende dois sindicatos é cadastrado nos
   dois, e em cada um vê só o que aquele sindicato lhe encaminhou.

2. **Cadastro que não se leu é "nenhum escritório".** Arquivo ausente,
   torto, ou com a mesma pessoa em dois escritórios: ninguém entra por ele.

3. **O escritório vê SÓ quem foi encaminhado a ele.** Reencaminhado a
   outro, o caso muda de mãos e recomeça — o primeiro deixa de ver.

4. **Todo encaminhamento é por uma AÇÃO.** "Mandei o fulano para o
   escritório" sem dizer por quê é o e-mail solto de hoje.

5. **A situação é de lista fechada, e a falta diz QUAL documento.** Texto
   livre sobre uma pessoa não circula entre escritório, sindicato e filiado:
   é onde iriam parar diagnóstico, opinião e dado de terceiro.

6. **Só fica guardado quem é da base**, como no rol e na ficha.

O ARQUIVO (`encaminhamentos.jsonl`) é a autoridade, uma linha por ato. Para
cada (pessoa, ação) vale o último encaminhamento, e sobre ele a última
situação marcada pelo escritório dono.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
from dataclasses import dataclass

from . import deposito, validacao

CADASTRO = "escritorios.json"
ARQUIVO = "encaminhamentos.jsonl"

ENCAMINHADO = "ENCAMINHADO"   # o sindicato encaminhou; o escritório não abriu
RECEBIDO = "RECEBIDO"         # o escritório recebeu e está conferindo
PENDENTE = "PENDENTE"         # falta documento, e a linha diz qual
COMPLETO = "COMPLETO"         # documentação completa
#: As que o ESCRITÓRIO marca. `ENCAMINHADO` é do sindicato: o escritório não
#: "desrecebe" um caso — se veio errado, quem desfaz é quem encaminhou.
DO_ESCRITORIO = (RECEBIDO, PENDENTE, COMPLETO)

#: O que pode faltar. Os mesmos tipos de documento que o portal já conhece.
DOCUMENTOS = tuple(sorted(
    nome.removesuffix(".pdf") for nome in (
        *validacao.OBRIGATORIOS, *validacao.SE_TEM_PROCESSO,
        *validacao.DESEJAVEIS, "contribuicao.pdf")
))

#: Como cada documento é dito a uma pessoa.
ROTULOS = {
    "procuracao": "procuração",
    "identidade": "documento de identidade",
    "comprovante_residencia": "comprovante de residência",
    "sentenca": "sentença",
    "certidao_transito": "certidão de trânsito em julgado",
    "fichas_financeiras": "fichas financeiras",
    "contribuicao": "comprovante de contribuição",
}

#: Encaminhado e não recebido há mais que isto é caso PARADO.
DIAS_PARADO = 7

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


class Recusado(ValueError):
    """O pedido não pode ser atendido, e a mensagem diz por quê."""


@dataclass(frozen=True)
class Escritorio:
    id: str
    nome: str
    contato: str
    acoes: tuple[str, ...]
    #: cpf -> e-mail de quem é do escritório e entra no portal.
    pessoas: dict[str, str]


@dataclass(frozen=True)
class Caso:
    cpf: str
    acao: str
    escritorio: str
    situacao: str
    faltam: tuple[str, ...]
    encaminhado_em: str
    atualizado_em: str


@dataclass(frozen=True)
class Plano:
    encaminhados: int
    ja_estavam: int
    fora_da_base: int


# ---------------------------------------------------------------- o cadastro

def cadastrados(pasta_entidade: pathlib.Path) -> tuple[Escritorio, ...]:
    """Os escritórios desta entidade. Vazio se o cadastro não puder ser lido
    INTEIRO: meio cadastro deixaria entrar quem estava na metade boa, e
    ninguém saberia que a outra metade ficou de fora."""
    try:
        bruto = json.loads(
            (pasta_entidade / CADASTRO).read_text(encoding="utf-8"))
        itens = bruto["escritorios"]
        if not isinstance(itens, list):
            return ()
        saida: list[Escritorio] = []
        vistos: set[str] = set()
        de_alguem: set[str] = set()
        for item in itens:
            ident = str(item["id"])
            nome = str(item["nome"]).strip()
            if not _ID.match(ident) or not nome or ident in vistos:
                return ()
            vistos.add(ident)
            pessoas: dict[str, str] = {}
            for p in item.get("pessoas") or []:
                cpf = validacao.so_digitos(str(p["cpf"]))
                email = str(p["email"]).strip()
                # A MESMA PESSOA EM DOIS ESCRITÓRIOS: ela veria os casos de
                # qual? Não se escolhe — o cadastro inteiro é recusado.
                if (not validacao.cpf_valido(cpf) or "@" not in email
                        or cpf in de_alguem):
                    return ()
                de_alguem.add(cpf)
                pessoas[cpf] = email
            saida.append(Escritorio(
                id=ident, nome=nome,
                contato=str(item.get("contato") or "").strip(),
                acoes=tuple(str(a) for a in item.get("acoes") or []),
                pessoas=pessoas,
            ))
        return tuple(saida)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ()


def de_quem(pasta_entidade: pathlib.Path, cpf: str) -> Escritorio | None:
    digitos = validacao.so_digitos(cpf)
    for e in cadastrados(pasta_entidade):
        if digitos in e.pessoas:
            return e
    return None


def email_de(pasta_entidade: pathlib.Path, cpf: str) -> str | None:
    dono = de_quem(pasta_entidade, cpf)
    return dono.pessoas[validacao.so_digitos(cpf)] if dono else None


def cpfs_das_pessoas(pasta_entidade: pathlib.Path) -> dict[str, str]:
    """cpf -> id do escritório, de todo mundo que entra por um escritório."""
    return {cpf: e.id for e in cadastrados(pasta_entidade) for cpf in e.pessoas}


def por_id(pasta_entidade: pathlib.Path, ident: str) -> Escritorio | None:
    for e in cadastrados(pasta_entidade):
        if e.id == ident:
            return e
    return None


def responsavel_por(pasta_entidade: pathlib.Path,
                    acao: str) -> Escritorio | None:
    """O escritório que cuida desta ação, segundo o cadastro. É a triagem
    que o sindicato já decidiu: a tela oferece, o gestor confirma."""
    for e in cadastrados(pasta_entidade):
        if acao in e.acoes:
            return e
    return None


# ------------------------------------------------------------------ os atos

def _agora() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def _linhas(pasta_entidade: pathlib.Path) -> list[str]:
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        return []
    return caminho.read_text(encoding="utf-8").splitlines()


def _estado(pasta_entidade: pathlib.Path) -> dict[tuple[str, str], Caso]:
    """(cpf, ação) -> o caso como está hoje. Linha ilegível é pulada."""
    casos: dict[tuple[str, str], Caso] = {}
    for bruta in _linhas(pasta_entidade):
        try:
            r = json.loads(bruta)
            ato, cpf, acao = r["ato"], str(r["cpf"]), str(r["acao"])
            quando = str(r.get("quando", ""))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        chave = (cpf, acao)
        if ato == "encaminhado":
            casos[chave] = Caso(cpf, acao, str(r.get("escritorio", "")),
                                ENCAMINHADO, (), quando, quando)
        elif ato == "desfeito":
            casos.pop(chave, None)
        elif ato == "situacao":
            atual = casos.get(chave)
            # Situação marcada por quem NÃO é mais o dono não vale: o caso
            # foi reencaminhado, e a marca era do encaminhamento anterior.
            if (atual and atual.escritorio == r.get("escritorio")
                    and r.get("situacao") in DO_ESCRITORIO):
                casos[chave] = Caso(
                    cpf, acao, atual.escritorio, r["situacao"],
                    tuple(sorted(f for f in r.get("faltam") or ()
                                 if f in DOCUMENTOS)),
                    atual.encaminhado_em, quando)
    return casos


def _anexar(pasta_entidade: pathlib.Path, registro: dict) -> None:
    deposito.anexar_com_fsync(
        pasta_entidade / ARQUIVO,
        json.dumps(registro, ensure_ascii=False, sort_keys=True) + "\n",
    )


def encaminhar(pasta_entidade: pathlib.Path, cpfs: set[str], *, acao: str,
               escritorio: str, base_de, quem: str,
               quando: str | None = None) -> Plano:
    """O sindicato encaminha estas pessoas, por esta ação, a este escritório.

    `base_de()` é chamada DENTRO da trava do apagamento, como no rol: quem
    pediu para sair entre a tela e a confirmação não volta ao arquivo.

    QUEM JÁ ESTÁ COM ESTE ESCRITÓRIO, POR ESTA AÇÃO, FICA COMO ESTÁ. Gravar
    de novo apagaria o que o escritório já marcou — e o gestor que clica
    duas vezes no botão não quis recomeçar o trabalho de ninguém.
    """
    acao = (acao or "").strip()
    if not acao:
        raise Recusado("diga por qual ação a pessoa está sendo encaminhada")
    if por_id(pasta_entidade, escritorio) is None:
        raise Recusado("este escritório não está no cadastro do sindicato")
    pedidos = {validacao.so_digitos(c) for c in cpfs if c}
    with deposito.travada(pasta_entidade, deposito.TRAVA_DO_APAGAMENTO):
        base = {validacao.so_digitos(c) for c in base_de() if c}
        estado = _estado(pasta_entidade)
        novos, ja = 0, 0
        for cpf in sorted(pedidos & base):
            atual = estado.get((cpf, acao))
            if atual and atual.escritorio == escritorio:
                ja += 1
                continue
            _anexar(pasta_entidade, {
                "ato": "encaminhado", "quando": quando or _agora(),
                "cpf": cpf, "acao": acao, "escritorio": escritorio,
                "quem": quem,
            })
            novos += 1
    return Plano(encaminhados=novos, ja_estavam=ja,
                 fora_da_base=len(pedidos - base))


def desfazer(pasta_entidade: pathlib.Path, cpf: str, acao: str, *,
             quem: str) -> bool:
    """O sindicato desfaz um encaminhamento. `False` se não havia."""
    digitos = validacao.so_digitos(cpf)
    with deposito.travada(pasta_entidade, deposito.TRAVA_DO_APAGAMENTO):
        if (digitos, acao) not in _estado(pasta_entidade):
            return False
        _anexar(pasta_entidade, {"ato": "desfeito", "quando": _agora(),
                                 "cpf": digitos, "acao": acao, "quem": quem})
    return True


def situar(pasta_entidade: pathlib.Path, cpf: str, acao: str, *,
           escritorio: str, situacao: str, quem: str,
           faltam=()) -> Caso:
    """O ESCRITÓRIO diz em que pé está o caso que recebeu."""
    digitos = validacao.so_digitos(cpf)
    if situacao not in DO_ESCRITORIO:
        raise Recusado("situação que não existe")
    faltam = tuple(sorted(set(faltam or ())))
    if any(f not in DOCUMENTOS for f in faltam):
        raise Recusado(
            "o documento que falta precisa ser um dos tipos da lista")
    if situacao == PENDENTE and not faltam:
        raise Recusado("diga qual documento falta")
    if situacao != PENDENTE:
        faltam = ()
    with deposito.travada(pasta_entidade, deposito.TRAVA_DO_APAGAMENTO):
        atual = _estado(pasta_entidade).get((digitos, acao))
        # A MESMA RESPOSTA para "não existe" e "é de outro escritório": a
        # diferença diria a um escritório quem está com o concorrente.
        if atual is None or atual.escritorio != escritorio:
            raise Recusado("este caso não foi encaminhado a este escritório")
        _anexar(pasta_entidade, {
            "ato": "situacao", "quando": _agora(), "cpf": digitos,
            "acao": acao, "escritorio": escritorio, "situacao": situacao,
            "faltam": list(faltam), "quem": quem,
        })
    return _estado(pasta_entidade)[(digitos, acao)]


# ------------------------------------------------------------------ leituras

def casos_de(pasta_entidade: pathlib.Path, escritorio: str) -> tuple[Caso, ...]:
    """Os casos que estão HOJE com este escritório. Só os dele."""
    return tuple(sorted(
        (c for c in _estado(pasta_entidade).values()
         if c.escritorio == escritorio),
        key=lambda c: (c.encaminhado_em, c.cpf, c.acao)))


def tem_caso(pasta_entidade: pathlib.Path, escritorio: str, cpf: str) -> bool:
    """Este escritório tem, hoje, algum caso desta pessoa? É a pergunta que
    decide se ele pode abrir um documento dela."""
    digitos = validacao.so_digitos(cpf)
    return any(c.cpf == digitos for c in casos_de(pasta_entidade, escritorio))


def de_cpf(pasta_entidade: pathlib.Path, cpf: str) -> tuple[Caso, ...]:
    """Os casos DESTA pessoa — para a tela dela."""
    digitos = validacao.so_digitos(cpf)
    return tuple(sorted(
        (c for c in _estado(pasta_entidade).values() if c.cpf == digitos),
        key=lambda c: c.acao))


def todos(pasta_entidade: pathlib.Path) -> tuple[Caso, ...]:
    return tuple(_estado(pasta_entidade).values())


def resumo(pasta_entidade: pathlib.Path, *, agora: str | None = None
           ) -> list[dict]:
    """Por escritório, o que o sindicato precisa ver. Só contagens.

    `parados` é o número que importa: encaminhados que o escritório ainda
    não recebeu, há mais de `DIAS_PARADO` dias. É onde o filiado está
    ligando para a sede.
    """
    momento = dt.datetime.fromisoformat(agora or _agora())
    casos = _estado(pasta_entidade).values()
    saida = []
    for e in cadastrados(pasta_entidade):
        dele = [c for c in casos if c.escritorio == e.id]

        def n(situacao: str) -> int:
            return sum(1 for c in dele if c.situacao == situacao)

        parados = 0
        for c in dele:
            if c.situacao != ENCAMINHADO:
                continue
            try:
                idade = momento - dt.datetime.fromisoformat(c.encaminhado_em)
            except ValueError:
                continue
            if idade > dt.timedelta(days=DIAS_PARADO):
                parados += 1
        saida.append({
            "id": e.id, "nome": e.nome, "contato": e.contato,
            "acoes": list(e.acoes), "casos": len(dele),
            "encaminhados": n(ENCAMINHADO), "recebidos": n(RECEBIDO),
            "pendentes": n(PENDENTE), "completos": n(COMPLETO),
            "parados": parados,
        })
    return saida


def remover_pessoa(pasta_entidade: pathlib.Path, cpf: str) -> int:
    """Tira TODAS as linhas desta pessoa. Para o apagamento a pedido. A
    linha que não der para interpretar fica byte a byte."""
    caminho = pasta_entidade / ARQUIVO
    digitos = validacao.so_digitos(cpf)
    if not caminho.is_file() or not digitos:
        return 0
    ficam: list[str] = []
    saem = 0
    for bruta in _linhas(pasta_entidade):
        try:
            dela = str(json.loads(bruta).get("cpf")) == digitos
        except (json.JSONDecodeError, AttributeError):
            dela = False
        if dela:
            saem += 1
        else:
            ficam.append(bruta)
    if not saem:
        return 0
    tmp = caminho.with_suffix(caminho.suffix + ".parcial")
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                 deposito.MODO_ARQUIVO)
    try:
        os.write(fd, "".join(l + "\n" for l in ficam).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(caminho)
    return saem
