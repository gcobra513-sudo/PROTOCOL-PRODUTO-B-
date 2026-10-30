"""
Ler o que os documentos dizem. A caixa 2 do mapa.

O SALTO QUE FALTAVA. O portal já extrai o TEXTO do PDF; ninguém tirava FATOS
dele. O filiado digitava o número do processo à mão, e trânsito em julgado,
órgão julgador, dispositivo e período continuavam trancados num PDF que só um
humano lê.

A REGRA QUE GOVERNA TUDO AQUI: **nunca afirmar o que não dá para
justificar.**

Cada achado carrega o TRECHO de onde saiu. Um humano confere a extração sem
abrir o PDF, lendo uma linha. Extração sem trecho é palpite com cara de dado,
e num produto que diz a alguém se tem direito a dinheiro isso é inaceitável.

E três níveis de confiança, porque decidem coisas diferentes:

    CERTO     tem conferência própria — dígito verificador que fecha, frase
              inequívoca. Pode alimentar o motor sozinho
    PROVAVEL  o padrão casou, mas a frase admite outra leitura. Vai para
              conferência humana, NÃO para o motor
    SUSPEITO  casou a forma e falhou a conferência. É DEFEITO, e aparece
              como tal em vez de sumir

POR QUE DETERMINÍSTICO, E NÃO UM MODELO DE LINGUAGEM: porque o resultado tem
de ser o mesmo amanhã, explicável para um juiz, e produzível sem mandar a
sentença de um filiado para um terceiro — que seria transferência
internacional de dado sensível. Um modelo pode entrar DEPOIS, como sugestão a
confirmar, nunca como fonte de fato.

A diferença entre ler e adivinhar está num teste: uma data solta num
documento NÃO é trânsito em julgado. Só vira achado se a frase disser que é.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass

from . import processo_cnj

CERTO = "CERTO"
PROVAVEL = "PROVAVEL"
SUSPEITO = "SUSPEITO"
CONFIANCAS = (CERTO, PROVAVEL, SUSPEITO)

#: Quantos caracteres de contexto acompanham cada achado. O suficiente para
#: um humano reconhecer a frase sem abrir o documento.
CONTEXTO = 90

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}


@dataclass(frozen=True)
class Achado:
    """Um fato extraído, com de onde saiu."""

    tipo: str
    valor: str
    confianca: str
    trecho: str
    posicao: int
    metodo: str

    @property
    def automatico(self) -> bool:
        """Pode alimentar o motor sem conferência humana?"""
        return self.confianca == CERTO


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _trecho(texto: str, inicio: int, fim: int) -> str:
    a = max(0, inicio - CONTEXTO // 2)
    b = min(len(texto), fim + CONTEXTO // 2)
    return " ".join(texto[a:b].split())


def _data(dia: int, mes: int, ano: int) -> str:
    """ISO, ou "" se a data não existir no calendário.

    31 de fevereiro casa o padrão e não é data. Deixar passar faria uma
    prescrição ser contada de um dia que nunca houve.
    """
    try:
        return dt.date(ano, mes, dia).isoformat()
    except ValueError:
        return ""


# --------------------------------------------------------------- leitores

_NUMERO = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")


def _ler_numero_processo(texto: str) -> list[Achado]:
    achados = []
    for m in _NUMERO.finditer(texto):
        bruto = m.group(0)
        digitos = processo_cnj.so_digitos(bruto)
        fecha = not processo_cnj.conferir(bruto)
        achados.append(Achado(
            tipo="numero_processo",
            valor=digitos,
            # O dígito verificador É a conferência. Com ele fechando, não há
            # como este ser um número de outra coisa.
            confianca=CERTO if fecha else SUSPEITO,
            trecho=_trecho(texto, m.start(), m.end()),
            posicao=m.start(),
            metodo="padrao_cnj+digito",
        ))
    return achados


_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")


def _ler_cpf(texto: str) -> list[Achado]:
    from .processo_cnj import so_digitos

    def fecha(cpf: str) -> bool:
        d = [int(c) for c in cpf]
        if len(set(d)) == 1:
            return False
        for corte in (9, 10):
            soma = sum(d[i] * (corte + 1 - i) for i in range(corte))
            resto = (soma * 10) % 11 % 10
            if resto != d[corte]:
                return False
        return True

    achados = []
    for m in _CPF.finditer(texto):
        digitos = so_digitos(m.group(0))
        achados.append(Achado(
            tipo="cpf",
            valor=digitos,
            confianca=CERTO if fecha(digitos) else SUSPEITO,
            trecho=_trecho(texto, m.start(), m.end()),
            posicao=m.start(),
            metodo="padrao_cpf+digito",
        ))
    return achados


#: A FRASE é que faz o trânsito, não a data. Uma data solta num documento não
#: é trânsito em julgado — e tratá-la como se fosse faria uma prescrição ser
#: contada de um marco inventado.
_TRANSITO = re.compile(
    r"(transit\w+\s+em\s+julgado\s+em|"
    r"transito\s+em\s+julgado\s*:?\s*em|"
    r"certifico[^.]{0,80}?transit\w+\s+em\s+julgado\s+em)"
    r"\s*(?P<data>\d{1,2}[/.]\d{1,2}[/.]\d{4}"
    r"|\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
    re.I,
)


def _ler_transito(texto: str) -> list[Achado]:
    plano = _sem_acento(texto)
    achados = []
    for m in _TRANSITO.finditer(plano):
        bruto = m.group("data")
        if "/" in bruto or "." in bruto:
            dia, mes, ano = (int(p) for p in re.split(r"[/.]", bruto))
        else:
            partes = bruto.lower().split()
            dia, nome, ano = int(partes[0]), partes[2], int(partes[4])
            mes = MESES.get(nome, 0)
        iso = _data(dia, mes, ano) if mes else ""
        if not iso:
            # Data que o calendário não tem. Não é achado de baixa confiança
            # — é não-achado, e inventar um marco aqui vira "sua pretensão
            # prescreveu".
            continue
        achados.append(Achado(
            tipo="transito_em_julgado",
            valor=iso,
            confianca=CERTO,
            trecho=_trecho(texto, m.start(), m.end()),
            posicao=m.start(),
            metodo="frase_de_transito+data",
        ))
    return achados


#: Parcialmente procedente vem ANTES de procedente: a ordem é a regra, porque
#: "parcialmente procedente" contém "procedente", e ler a parcial como total
#: é afirmar direito que a sentença não deu.
_DISPOSITIVOS = (
    ("parcialmente_procedente",
     re.compile(r"julg\w*\s+(?:\w+\s+){0,3}?parcialmente\s+procedente", re.I)),
    ("improcedente", re.compile(r"julg\w*\s+(?:\w+\s+){0,3}?improcedente", re.I)),
    ("extinto", re.compile(r"julg\w*\s+(?:\w+\s+){0,3}?extint\w+", re.I)),
    ("procedente", re.compile(r"julg\w*\s+(?:\w+\s+){0,3}?procedente", re.I)),
)


def _ler_dispositivo(texto: str) -> list[Achado]:
    plano = _sem_acento(texto)
    for valor, padrao in _DISPOSITIVOS:
        m = padrao.search(plano)
        if m:
            return [Achado(
                tipo="dispositivo",
                valor=valor,
                confianca=CERTO,
                trecho=_trecho(texto, m.start(), m.end()),
                posicao=m.start(),
                metodo="verbo_julgar",
            )]
    return []


# O lookahead exige ESPAÇO antes de "da/de/do". Sem isso o padrão parava
# dentro de "Federal" — o "de" de "deral" casava — e o órgão saía como
# "5ª Vara Fe". Pior que não achar: parece dado e vai cortado para a tela.
_ORGAO = re.compile(
    r"\b(\d{1,2})\s*[ªa]\s+(vara[\w\s\-]{0,40}?)"
    r"(?=\s+(?:da|de|do|dos|das)\s|\s*\n|\s*$)",
    re.I,
)


def _ler_orgao(texto: str) -> list[Achado]:
    m = _ORGAO.search(texto)
    if not m:
        return []
    return [Achado(
        tipo="orgao_julgador",
        valor=" ".join(f"{m.group(1)}ª {m.group(2)}".split()),
        # PROVAVEL e não CERTO: a vara aparece no cabeçalho e também pode
        # aparecer citada no corpo, referindo-se a OUTRO juízo. Conferência
        # humana resolve; adivinhação não.
        confianca=PROVAVEL,
        trecho=_trecho(texto, m.start(), m.end()),
        posicao=m.start(),
        metodo="padrao_vara",
    )]


_PERIODO = re.compile(
    r"(?:no\s+)?per[ií]odo\s+de\s+(\d{1,2})/(\d{4})\s+a\s+(\d{1,2})/(\d{4})",
    re.I,
)


def _ler_periodo(texto: str) -> list[Achado]:
    achados = []
    for m in _PERIODO.finditer(texto):
        mes_i, ano_i, mes_f, ano_f = (int(g) for g in m.groups())
        if not (1 <= mes_i <= 12 and 1 <= mes_f <= 12):
            continue
        achados.append(Achado(
            tipo="periodo",
            valor=f"{ano_i:04d}-{mes_i:02d}/{ano_f:04d}-{mes_f:02d}",
            confianca=CERTO,
            trecho=_trecho(texto, m.start(), m.end()),
            posicao=m.start(),
            metodo="periodo_de_a",
        ))
    return achados


_VALOR = re.compile(r"R\$\s*([\d.]+,\d{2})")


def _ler_valor(texto: str) -> list[Achado]:
    achados = []
    for m in _VALOR.finditer(texto):
        bruto = m.group(1).replace(".", "").replace(",", ".")
        achados.append(Achado(
            tipo="valor",
            valor=bruto,
            # PROVAVEL sempre: um documento tem muitos valores — causa,
            # honorários, custas, multa — e saber QUAL é qual é leitura, não
            # extração. Virar número no painel sem conferência seria prometer.
            confianca=PROVAVEL,
            trecho=_trecho(texto, m.start(), m.end()),
            posicao=m.start(),
            metodo="padrao_reais",
        ))
    return achados


LEITORES = (
    _ler_numero_processo,
    _ler_cpf,
    _ler_transito,
    _ler_dispositivo,
    _ler_orgao,
    _ler_periodo,
    _ler_valor,
)


def ler(texto: str) -> list[Achado]:
    """Todos os achados de um texto, em ordem de aparição."""
    achados: list[Achado] = []
    for leitor in LEITORES:
        achados.extend(leitor(texto or ""))
    return sorted(achados, key=lambda a: (a.posicao, a.tipo))


# ------------------------------------------------- do achado para o fato

def divergencias(achados: list[Achado]) -> dict[str, list[str]]:
    """Tipos em que os documentos discordam entre si.

    Dois PDFs com números de processo diferentes é informação, não ruído.
    Escolher um seria sortear qual versão vale — a mesma postura que o resto
    do sistema tem para divergência entre o acervo e o cadastro.
    """
    por_tipo: dict[str, set[str]] = {}
    for a in achados:
        if a.confianca == CERTO:
            por_tipo.setdefault(a.tipo, set()).add(a.valor)
    return {t: sorted(v) for t, v in por_tipo.items() if len(v) > 1}


def fatos_confiaveis(achados: list[Achado]) -> dict[str, str]:
    """Os fatos que podem alimentar o motor sem passar por um humano.

    Só os CERTO, e só quando não houver divergência. `PROVAVEL` e `SUSPEITO`
    ficam de fora de propósito: vão para a fila de conferência, que é onde
    um humano decide em segundos o que o programa não pode decidir nunca.
    """
    discordantes = set(divergencias(achados))
    fatos: dict[str, str] = {}
    for a in achados:
        if a.confianca == CERTO and a.tipo not in discordantes:
            fatos.setdefault(a.tipo, a.valor)
    return fatos


def para_conferir(achados: list[Achado]) -> list[Achado]:
    """O que um humano precisa olhar: o provável, o suspeito e o divergente."""
    discordantes = set(divergencias(achados))
    return [
        a for a in achados
        if a.confianca != CERTO or a.tipo in discordantes
    ]
