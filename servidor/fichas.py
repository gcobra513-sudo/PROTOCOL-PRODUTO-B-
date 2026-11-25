"""
A ficha financeira de cada filiado — a base de cálculo, mês a mês.

`nucleo/valor.py` sabe fazer a conta desde que existe, e desde que existe
recusa: não havia do que tirar percentual. Quem tem a ficha é o SINDICATO
(ou o órgão, por intermédio dele), e este módulo é a entrada.

É DADO DE REMUNERAÇÃO, e por isso as regras são as mais duras da casa:

1. **Só fica guardado quem é da base.** Ficha de quem a entidade não
   declarou atender é contada e descartada, como no rol de substituídos.

2. **Linha que não se entende é CONTADA, nunca adivinhada.** CPF que não
   fecha, mês que não existe, valor que não é número ou é negativo: a linha
   não entra, e o gestor fica sabendo quantas foram.

3. **Divergência não se resolve sozinha.** O mesmo mês com dois valores
   diferentes para a mesma pessoa tira a FICHA INTEIRA dela do envio. Ficar
   com o primeiro, o último ou o maior seria escolher a base de cálculo de
   alguém — e o erro sairia no meio de uma conta correta.

4. **Envio novo substitui a ficha da pessoa INTEIRA.** Juntar com a
   anterior deixaria um mês velho, de um arquivo que o gestor já corrigiu,
   dentro da conta nova.

5. **Mês que não veio não é zero.** A conta só sai com todos os meses do
   período, e a recusa diz quais faltam (`valor.apurar`).

O VALOR É DECLARADO, NÃO CONFERIDO: entra pelo arquivo que um gestor enviou.
Por isso o que sai dele é "apuração preliminar e bruta", e nada vai a juízo
sem advogado.

O ARQUIVO (`fichas_financeiras.jsonl`) é a autoridade: uma linha por envio.
Para cada pessoa vale a ficha do ÚLTIMO envio em que ela aparece.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import pathlib
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from . import acervo, deposito, validacao

ARQUIVO = "fichas_financeiras.jsonl"

CENTAVO = Decimal("0.01")

#: Como a planilha chama cada coluna, já normalizado.
COLUNAS = {
    "cpf": ("cpf",),
    "competencia": ("competencia", "mes", "periodo", "referencia",
                    "mes_ano", "mes_referencia"),
    "base": ("base", "base_de_calculo", "valor", "remuneracao",
             "vencimento", "vencimento_basico"),
}


class FichaIlegivel(ValueError):
    """O arquivo não serve como ficha financeira, e a mensagem diz por quê."""


@dataclass(frozen=True)
class Lido:
    #: cpf -> {competência AAAA-MM: base, em texto com dois decimais}
    fichas: dict[str, dict[str, str]]
    invalidas: int = 0
    #: Pessoas tiradas do envio por terem o mesmo mês com dois valores.
    divergentes: int = 0


@dataclass(frozen=True)
class Plano:
    fichas: dict[str, dict[str, str]]
    pessoas: int
    competencias: int
    fora_da_base: int
    invalidas: int
    divergentes: int


def _competencia(bruto: str) -> str:
    """`2004-03`, `03/2004` ou `2004/03` -> `2004-03`. Vazio se não for mês."""
    texto = (bruto or "").strip()
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})", texto)
    if m:
        ano, mes = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(r"(\d{1,2})[-/.](\d{4})", texto)
        if not m:
            return ""
        mes, ano = int(m.group(1)), int(m.group(2))
    if not (1 <= mes <= 12 and 1900 <= ano <= 2100):
        return ""
    return f"{ano:04d}-{mes:02d}"


def _valor(bruto: str) -> str:
    """`5.000,00`, `R$ 5000,5`, `5000.50` -> `5000.50`. Vazio se não der.

    COM VÍRGULA, o ponto é milhar (o jeito brasileiro). SEM vírgula, o ponto
    é decimal — é como o Excel exporta número. Um valor como `5.000`, sem
    vírgula, é ambíguo e NÃO entra: cinco ou cinco mil não se adivinha.
    """
    texto = (bruto or "").replace("R$", "").replace(" ", "").strip()
    if not texto:
        return ""
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        return ""
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return ""
    if not numero.is_finite() or numero < 0:
        return ""
    return str(numero.quantize(CENTAVO))


def _linhas(corpo: bytes, nome: str) -> tuple[list[str], list[dict]]:
    if corpo[:2] == b"PK" or nome.lower().endswith((".xlsx", ".xlsm")):
        try:
            return acervo._linhas_de_xlsx(corpo)
        except acervo.AcervoIlegivel as e:
            raise FichaIlegivel(f"{nome}: {e}") from None
    try:
        texto = acervo._decodificar(corpo)
    except acervo.AcervoIlegivel as e:
        raise FichaIlegivel(str(e)) from None
    primeira = texto.splitlines()[0] if texto.strip() else ""
    if not primeira:
        raise FichaIlegivel(f"{nome} está vazio")
    leitor = csv.DictReader(io.StringIO(texto),
                            delimiter=acervo._separador(primeira))
    return list(leitor.fieldnames or []), list(leitor)


def ler_arquivo(corpo: bytes, nome: str) -> Lido:
    """A planilha (CSV ou .xlsx): uma linha por pessoa e por mês, com as
    colunas CPF, Competência e Base."""
    if not corpo:
        raise FichaIlegivel(f"{nome} está vazio")
    cabecalho, registros = _linhas(corpo, nome)
    coluna: dict[str, str] = {}
    for bruto in cabecalho:
        chave = acervo.normalizar_cabecalho(bruto)
        for campo, nomes in COLUNAS.items():
            if chave in nomes and campo not in coluna:
                coluna[campo] = bruto
    faltam = [c for c in COLUNAS if c not in coluna]
    if faltam:
        raise FichaIlegivel(
            f"{nome} não tem as colunas de que a ficha financeira precisa. "
            f"São três: CPF, Competência (o mês, como 03/2004) e Base (o "
            f"valor sobre o qual a verba incide). Faltou: "
            f"{', '.join(faltam)}."
        )

    fichas: dict[str, dict[str, str]] = {}
    com_divergencia: set[str] = set()
    invalidas = 0
    for linha in registros:
        cpf = validacao.so_digitos(str(linha.get(coluna["cpf"]) or ""))
        mes = _competencia(str(linha.get(coluna["competencia"]) or ""))
        base = _valor(str(linha.get(coluna["base"]) or ""))
        if not (validacao.cpf_valido(cpf) and mes and base):
            invalidas += 1
            continue
        anterior = fichas.setdefault(cpf, {}).get(mes)
        if anterior is not None and anterior != base:
            com_divergencia.add(cpf)
        fichas[cpf][mes] = base
    for cpf in com_divergencia:
        del fichas[cpf]
    if not fichas:
        raise FichaIlegivel(
            f"{nome} não trouxe nenhuma linha que dê para usar. Cada linha "
            f"precisa de um CPF válido, do mês (como 03/2004) e do valor "
            f"(como 5.000,00)."
        )
    return Lido(fichas=fichas, invalidas=invalidas,
                divergentes=len(com_divergencia))


def planejar(lido: Lido, base: set[str]) -> Plano:
    """Cruza com a base. Não grava nada."""
    base = {validacao.so_digitos(c) for c in base if c}
    ficam = {c: dict(sorted(f.items()))
             for c, f in sorted(lido.fichas.items()) if c in base}
    return Plano(
        fichas=ficam,
        pessoas=len(ficam),
        competencias=sum(len(f) for f in ficam.values()),
        fora_da_base=len(set(lido.fichas) - base),
        invalidas=lido.invalidas,
        divergentes=lido.divergentes,
    )


def _agora() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def enviar(pasta_entidade: pathlib.Path, lido: Lido, *, base_de, quem: str,
           arquivo: str, sha256: str) -> Plano:
    """Cruza com a base DE AGORA e grava, com o apagamento parado — a mesma
    corrida que `substituidos.enviar` fecha: quem pediu para sair entre a
    prévia e a confirmação não pode voltar ao arquivo."""
    with deposito.travada(pasta_entidade, deposito.TRAVA_DO_APAGAMENTO):
        plano = planejar(lido, base_de())
        if plano.fichas:
            deposito.anexar_com_fsync(
                pasta_entidade / ARQUIVO,
                json.dumps({
                    "quando": _agora(), "quem": quem, "arquivo": arquivo,
                    "sha256": sha256, "fichas": plano.fichas,
                    "fora_da_base": plano.fora_da_base,
                    "invalidas": plano.invalidas,
                    "divergentes": plano.divergentes,
                }, ensure_ascii=False, sort_keys=True) + "\n",
            )
    return plano


def _linhas_guardadas(pasta_entidade: pathlib.Path) -> list[str]:
    caminho = pasta_entidade / ARQUIVO
    if not caminho.is_file():
        return []
    return caminho.read_text(encoding="utf-8").splitlines()


def _vigentes(pasta_entidade: pathlib.Path) -> tuple[dict[str, dict], dict]:
    """(cpf -> ficha que vale, o último envio). Linha ilegível é pulada."""
    valem: dict[str, dict] = {}
    ultimo: dict = {}
    for bruta in _linhas_guardadas(pasta_entidade):
        try:
            registro = json.loads(bruta)
        except json.JSONDecodeError:
            continue
        if not isinstance(registro, dict):
            continue
        guardadas = registro.get("fichas")
        if not isinstance(guardadas, dict):
            continue
        ultimo = registro
        for cpf, ficha in guardadas.items():
            if isinstance(ficha, dict):
                valem[str(cpf)] = ficha
    return valem, ultimo


def por_cpf(pasta_entidade: pathlib.Path
            ) -> dict[str, tuple[tuple[str, str], ...]]:
    """cpf -> ((competência, base), ...), na forma que `motor.Fatos` recebe."""
    valem, _ = _vigentes(pasta_entidade)
    return {cpf: tuple(sorted((str(m), str(b)) for m, b in ficha.items()))
            for cpf, ficha in valem.items()}


def de_cpf(pasta_entidade: pathlib.Path, cpf: str
           ) -> tuple[tuple[str, str], ...]:
    return por_cpf(pasta_entidade).get(validacao.so_digitos(cpf), ())


def resumo(pasta_entidade: pathlib.Path, base: set[str]) -> dict:
    """O que o painel mostra. Só contagens — valor nenhum."""
    base = {validacao.so_digitos(c) for c in base if c}
    valem, ultimo = _vigentes(pasta_entidade)
    com = set(valem) & base
    return {
        "pessoas": len(com),
        "sem_ficha": len(base - com),
        "enviado_em": str(ultimo.get("quando", "")),
        "arquivo": str(ultimo.get("arquivo", "")),
    }


def remover_pessoa(pasta_entidade: pathlib.Path, cpf: str) -> int:
    """Tira esta pessoa de TODAS as linhas — inclusive das de envios já
    substituídos, que não valem mais e continuam guardando a remuneração
    dela. A linha que não der para interpretar fica byte a byte."""
    caminho = pasta_entidade / ARQUIVO
    digitos = validacao.so_digitos(cpf)
    if not caminho.is_file() or not digitos:
        return 0
    guardadas: list[str] = []
    mexidas = 0
    for bruta in _linhas_guardadas(pasta_entidade):
        try:
            registro = json.loads(bruta)
        except json.JSONDecodeError:
            guardadas.append(bruta)
            continue
        dela = registro.get("fichas") if isinstance(registro, dict) else None
        if not isinstance(dela, dict) or digitos not in dela:
            guardadas.append(bruta)
            continue
        del dela[digitos]
        mexidas += 1
        guardadas.append(json.dumps(registro, ensure_ascii=False,
                                    sort_keys=True))
    if not mexidas:
        return 0
    tmp = caminho.with_suffix(caminho.suffix + ".parcial")
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
                 deposito.MODO_ARQUIVO)
    try:
        os.write(fd, "".join(l + "\n" for l in guardadas).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    tmp.replace(caminho)
    return mexidas
