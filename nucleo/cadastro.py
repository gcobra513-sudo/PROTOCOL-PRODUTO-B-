"""
A conta do filiado: o que o Produto B pede, e o que ele recusa pedir.

O PORTAL QUE EXISTIA PEDIA PROCURAÇÃO, IDENTIDADE E COMPROVANTE DE
RESIDÊNCIA. São documentos para LITIGAR — hipótese do Produto A, que monta
petição. O Produto B responde uma pergunta, e para responder precisa de
outra coisa.

    comprovantes de CONTRIBUIÇÃO   provam o PERÍODO DE FILIAÇÃO, e é o
                                   cruzamento desse período contra o da ação
                                   coletiva que responde "em quais ações
                                   esta pessoa participa"
    cargo e situação               definem a CATEGORIA alcançada
    sentença e certidão            só se a pessoa tiver — decidem se ela
                                   EXECUTA (tem título) ou AJUÍZA (não tem)

Exigir procuração de quem só quer saber se tem direito derruba a conclusão
do cadastro e não melhora resposta nenhuma.

A FORMA VEM DO CONTRATO, não daqui. O portal e o servidor leem o mesmo
`compartilhado/contrato_cadastro.json`, porque duas listas de campos mantidas
à mão divergem — e a divergência só aparece na primeira conta de verdade.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from . import processo_cnj

RAIZ = Path(__file__).resolve().parent.parent
CONTRATO: dict = json.loads(
    (RAIZ / "compartilhado" / "contrato_cadastro.json").read_text("utf-8")
)

VERSAO: int = CONTRATO["_versao"]
CAMPOS: tuple[str, ...] = tuple(CONTRATO["campos"])
OBRIGATORIOS: tuple[str, ...] = tuple(CONTRATO["obrigatorios"])
DOCUMENTOS: dict[str, dict] = CONTRATO["documentos"]
VALORES: dict[str, list[str]] = CONTRATO["valores"]
TETOS: dict[str, int] = CONTRATO["tetos"]
TETO_PADRAO: int = CONTRATO["teto_padrao"]

EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")
#: AAAA-MM. Mês fora de 01..12 não casa, de propósito: "1992-13" é erro de
#: digitação, e aceitá-lo faria o cruzamento comparar contra um mês que não
#: existe.
COMPETENCIA = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def so_digitos(v: str) -> str:
    return "".join(c for c in str(v) if c.isdigit())


def cpf_valido(cpf: str) -> bool:
    d = [int(c) for c in so_digitos(cpf)]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for corte in (9, 10):
        soma = sum(d[i] * (corte + 1 - i) for i in range(corte))
        if (soma * 10) % 11 % 10 != d[corte]:
            return False
    return True


def numeros_de_processo(bruto: str) -> list[str]:
    """Os números informados, em dígitos, sem repetição e na ordem de chegada."""
    vistos: list[str] = []
    for pedaco in str(bruto or "").split(";"):
        digitos = so_digitos(pedaco)
        if digitos and digitos not in vistos:
            vistos.append(digitos)
    return vistos


def documentos_exigidos(linha: dict) -> tuple[str, ...]:
    """Quais documentos esta conta precisa ter.

    NÃO DEPENDE DO QUE A PESSOA DECLAROU SOBRE PROCESSO. No Produto A,
    dizer "tenho processo" passava a exigir sentença e certidão. Aqui não: a
    pessoa pode saber o número e não ter os papéis em mãos, e bloquear o
    cadastro por isso a deixaria sem resposta nenhuma — justamente ela, que é
    quem mais precisa.
    """
    return tuple(n for n, d in DOCUMENTOS.items() if d["obrigatorio"])


def _competencia_valida(valor: str, hoje: dt.date) -> str:
    """"" se serve; a mensagem do problema se não serve."""
    m = COMPETENCIA.match(valor)
    if not m:
        return "deve estar no formato AAAA-MM (por exemplo, 1992-05)"
    ano, mes = int(m.group(1)), int(m.group(2))
    if (ano, mes) > (hoje.year, hoje.month):
        return "está no futuro"
    if ano < 1930:
        return "é anterior a 1930; provavelmente erro de digitação"
    return ""


def conferir(linha: object, hoje: dt.date | None = None) -> list[str]:
    """Problemas da conta. Lista vazia = pode gravar."""
    hoje = hoje or dt.date.today()
    if not isinstance(linha, dict):
        return ["o cadastro não veio como um objeto"]

    problemas: list[str] = []

    # Campo fora do contrato é ERRO, não descarte. Descarte em silêncio é
    # como um campo renomeado some sem ninguém ver.
    desconhecidos = sorted(set(linha) - set(CAMPOS))
    if desconhecidos:
        problemas.append(
            "campo(s) que o contrato não tem: " + ", ".join(desconhecidos)
        )

    valores: dict[str, str] = {}
    for campo in CAMPOS:
        bruto = linha.get(campo, "")
        if bruto is None:
            bruto = ""
        if not isinstance(bruto, str):
            problemas.append(f"{campo} precisa ser texto")
            bruto = ""
        valor = bruto.strip()
        teto = TETOS.get(campo, TETO_PADRAO)
        if len(valor) > teto:
            problemas.append(f"{campo} passa de {teto} caracteres")
            valor = valor[:teto]
        valores[campo] = valor

    for campo in OBRIGATORIOS:
        if not valores[campo]:
            problemas.append(f"{campo} está vazio")

    if valores["cpf"] and not cpf_valido(valores["cpf"]):
        problemas.append("CPF inválido")
    if valores["email"] and not EMAIL.match(valores["email"]):
        problemas.append("e-mail inválido")

    if valores["situacao"] and valores["situacao"] not in VALORES["situacao"]:
        problemas.append(
            "situacao tem que ser " + " / ".join(VALORES["situacao"])
        )

    for campo in ("tem_processo", "ja_executou", "tem_acao_propria"):
        if valores[campo] and valores[campo] not in VALORES["resposta"]:
            problemas.append(
                f"{campo} tem que ser " + " / ".join(VALORES["resposta"])
            )

    # ---- o período de filiação, que é o miolo do produto ----
    if valores["filiado_desde"]:
        erro = _competencia_valida(valores["filiado_desde"], hoje)
        if erro:
            problemas.append(f"filiado_desde {erro}")
    # VAZIO É RESPOSTA: significa "ainda filiada". Tratá-lo como omissão
    # reprovaria justamente quem está filiada hoje.
    if valores["filiado_ate"]:
        erro = _competencia_valida(valores["filiado_ate"], hoje)
        if erro:
            problemas.append(f"filiado_ate {erro}")
        elif (valores["filiado_desde"]
              and not _competencia_valida(valores["filiado_desde"], hoje)
              and valores["filiado_ate"] < valores["filiado_desde"]):
            problemas.append(
                f"a filiação termina ({valores['filiado_ate']}) antes de "
                f"começar ({valores['filiado_desde']})"
            )

    for campo in ("data_nascimento", "data_ingresso", "data_aposentadoria"):
        if valores[campo] and not DATA_ISO.match(valores[campo]):
            problemas.append(f"{campo} deve estar no formato AAAA-MM-DD")

    # ---- os números de processo, de qualquer tribunal ----
    # Acompanhar não é protocolar: a sentença de alguém pode ser de tribunal
    # estadual, e recusá-la seria pôr a nossa suposição acima do fato dela.
    for numero in numeros_de_processo(valores["numeros_de_processo"]):
        problemas += [
            f"número de processo: {p}"
            for p in processo_cnj.conferir(numero, exigir_trf1=False)
        ]

    return problemas


def normalizar(linha: dict) -> dict[str, str]:
    """A conta como vai para o banco: só os campos do contrato, aparados."""
    saida: dict[str, str] = {}
    for campo in CAMPOS:
        valor = str(linha.get(campo, "") or "").strip()
        saida[campo] = valor[: TETOS.get(campo, TETO_PADRAO)]
    saida["cpf"] = so_digitos(saida["cpf"])
    saida["email"] = saida["email"].lower()
    saida["numeros_de_processo"] = ";".join(
        processo_cnj.normalizar(n)
        for n in numeros_de_processo(saida["numeros_de_processo"])
    )
    return saida
