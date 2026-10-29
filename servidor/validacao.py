"""
A conferência do lado do servidor.

POR QUE EXISTE, SE O PORTAL JÁ CONFERE: o portal confere para a pessoa não
errar; o servidor confere porque o navegador não é fonte de verdade. Qualquer
pessoa monta um POST à mão. Se a única validação fosse a do navegador, a
entrega que o escritório abre seria o que o cliente quisesse mandar.

As duas conferências são de propósito independentes — e a de cá é a que vale.

Três decisões que parecem rigor inútil e não são:

1. **Coluna desconhecida é erro, não é descartada.** Se o portal mandar
   `data_aposentadoira`, descartar em silêncio perde o campo e ninguém
   descobre. Recusar o pedido faz o erro aparecer no primeiro teste.
2. **Todo campo de texto tem teto.** Um `nome_completo` de 4 MB não é cadastro,
   é abuso — e ainda enche o log e a planilha.
3. **`ciencia_e_iniciativa` tem que ser exatamente "sim".** É a declaração de
   que a iniciativa é da pessoa. Aceitar "x" ali seria registrar declaração que
   ninguém fez.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

from nucleo import processo_cnj

RAIZ_REPO = pathlib.Path(__file__).resolve().parent.parent
CONTRATO = json.loads(
    (RAIZ_REPO / "compartilhado" / "contrato_entrega.json").read_text("utf-8")
)
COLUNAS: tuple[str, ...] = tuple(CONTRATO["colunas_manifesto"])
VALORES: dict[str, list[str]] = CONTRATO["valores"]
ARQUIVOS: dict[str, str] = CONTRATO["arquivos"]
OBRIGATORIOS: tuple[str, ...] = tuple(CONTRATO["obrigatorios"])
SE_TEM_PROCESSO: tuple[str, ...] = tuple(CONTRATO["se_tem_processo"])
DESEJAVEIS: tuple[str, ...] = tuple(CONTRATO["desejaveis"])

#: Campos que o PORTAL manda e o manifesto do Produto A não leva. Existem
#: porque o Produto B pergunta coisas que o A não usa — quais processos
#: acompanhar, e se a pessoa quer ser avisada. Ficam fora de
#: `colunas_manifesto` de propósito: o manifesto é do A, e misturar os dois
#: faria o A reprovar coluna que não entende.
ACOMPANHAMENTO: dict = CONTRATO["acompanhamento"]
CAMPOS_PORTAL: tuple[str, ...] = tuple(CONTRATO["campos_do_portal"])
#: O que uma linha de cadastro pode trazer. Chave fora disto é erro, não
#: descarte em silêncio.
ACEITAS: tuple[str, ...] = COLUNAS + CAMPOS_PORTAL
NOMES_DE_ARQUIVO: frozenset[str] = frozenset(ARQUIVOS.values())

# Teto por campo. Generoso para nome composto e endereço longo, apertado para
# o que não tem razão de ser grande.
TETOS = {
    "observacao_processo": 2000,
    "logradouro": 200,
    "complemento": 120,
    "nome_completo": 180,
    "email": 254,
    "unidade": 180,
    "cargo": 120,
    # 20 números FORMATADOS (25 caracteres: 0000000-00.0000.0.00.0000) mais
    # os separadores. Contar 20 dígitos por número capava o campo perto de 16
    # — e o portal exibe o número formatado, então era o caso comum. Pior: a
    # truncagem partia um número ao meio e produzia um segundo erro,
    # "deve ter 20 dígitos (tem 4)", que culpava quem digitou.
    #
    # O teto continua existindo porque o campo é livre e vem de fora: 200
    # números numa linha é erro ou abuso, e nos dois casos a coleta seguinte
    # faria 200 consultas de 30 s por causa de uma linha de planilha.
    "acompanhar": ACOMPANHAMENTO["maximo"] * 26,
}
TETO_PADRAO = 80

EXIGIDOS = (
    "cpf",
    "nome_completo",
    "email",
    "telefone",
    "cep",
    "logradouro",
    "numero",
    "bairro",
    "municipio",
    "uf",
    "cargo",
    "situacao",
    # Obrigatória: é dela que sai a prioridade de tramitação. Sem ela, num
    # lote de aposentados, ninguém pede "Idoso(a)" — e isso é tempo de vida
    # de quem está na fila.
    "data_nascimento",
    "data_ingresso",
    "tem_processo",
)

EMAIL = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")
UF = re.compile(r"^[A-Z]{2}$")
UFS = frozenset(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR "
    "SC SP SE TO".split()
)
CEP = re.compile(r"^\d{5}-?\d{3}$")


def so_digitos(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def cpf_valido(cpf: str) -> bool:
    d = so_digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for corte in (9, 10):
        soma = sum(int(d[i]) * (corte + 1 - i) for i in range(corte))
        resto = (soma * 10) % 11
        if int(d[corte]) != (0 if resto == 10 else resto):
            return False
    return True


def _data_iso(valor: str) -> bool:
    try:
        dt.date.fromisoformat(valor)
    except ValueError:
        return False
    return True


def numeros_de_acompanhamento(bruto: str) -> list[str]:
    """Os números de `acompanhar`, em dígitos, sem repetição e na ordem de
    chegada. A primeira menção vence: é a que a pessoa digitou primeiro.
    """
    vistos: list[str] = []
    for pedaco in str(bruto or "").split(ACOMPANHAMENTO["separador"]):
        if not pedaco.strip():
            continue
        digitos = so_digitos(pedaco)
        # Pedaço sem dígito nenhum vira "" e, vindo do diário, chegaria ao
        # coletor como erro espúrio — ruído no canal cujo valor inteiro é
        # ser sinal.
        if digitos and digitos not in vistos:
            vistos.append(digitos)
    return vistos


def _problemas_do_acompanhamento(bruto: str) -> list[str]:
    """Sem `exigir_trf1`: são 65 tribunais no DataJud, e acompanhar processo
    de outro tribunal é legítimo. Quem exige TRF1 é `numero_processo`, que é
    o processo da sentença de origem e decide o juízo da execução.
    """
    numeros = numeros_de_acompanhamento(bruto)
    if len(numeros) > ACOMPANHAMENTO["maximo"]:
        return [
            f"acompanhar tem {len(numeros)} números e o máximo é "
            f"{ACOMPANHAMENTO['maximo']}"
        ]
    problemas: list[str] = []
    for numero in numeros:
        problemas += [
            f"acompanhar: {p}"
            for p in processo_cnj.conferir(numero, exigir_trf1=False)
        ]
    return problemas


def conferir_linha(linha: object) -> list[str]:
    """Problemas na linha do manifesto. Lista vazia = pode gravar."""
    if not isinstance(linha, dict):
        return ["o cadastro não veio como um objeto"]

    problemas: list[str] = []

    desconhecidas = sorted(set(linha) - set(ACEITAS))
    if desconhecidas:
        problemas.append(
            "coluna(s) que o contrato não tem: " + ", ".join(desconhecidas)
        )

    valores: dict[str, str] = {}
    for coluna in ACEITAS:
        bruto = linha.get(coluna, "")
        if bruto is None:
            bruto = ""
        if not isinstance(bruto, str):
            problemas.append(f"{coluna} precisa ser texto")
            bruto = ""
        valor = bruto.strip()
        teto = TETOS.get(coluna, TETO_PADRAO)
        if len(valor) > teto:
            problemas.append(f"{coluna} passa de {teto} caracteres")
            valor = valor[:teto]
        valores[coluna] = valor

    for coluna in EXIGIDOS:
        if not valores[coluna]:
            problemas.append(f"{coluna} está vazio")

    if valores["cpf"] and not cpf_valido(valores["cpf"]):
        problemas.append("CPF inválido")

    # id_externo é o que nomeia a pasta. Ele tem que ser o CPF, e não uma
    # escolha do cliente — senão o cliente escolhe em que pasta grava.
    if valores["cpf"] and valores["id_externo"] != so_digitos(valores["cpf"]):
        problemas.append("id_externo tem que ser os 11 dígitos do CPF")

    if valores["email"] and not EMAIL.match(valores["email"]):
        problemas.append("e-mail inválido")
    if valores["cep"] and not CEP.match(valores["cep"]):
        problemas.append("CEP inválido")
    if valores["uf"] and valores["uf"].upper() not in UFS:
        problemas.append("UF inválida")

    if valores["situacao"] and valores["situacao"] not in VALORES["situacao"]:
        problemas.append(
            "situacao tem que ser " + " / ".join(VALORES["situacao"])
        )
    if (
        valores["situacao"] in ("aposentado", "pensionista")
        and not valores["data_aposentadoria"]
    ):
        problemas.append("data_aposentadoria falta para quem não está na ativa")

    for coluna in ("data_nascimento", "data_ingresso", "data_aposentadoria"):
        if valores[coluna] and not _data_iso(valores[coluna]):
            problemas.append(f"{coluna} não está no formato AAAA-MM-DD")

    # A data de nascimento decide a prioridade, então erro nela não pode
    # virar "sem prioridade" em silêncio. Futuro e ano impossível reprovam.
    nascimento = valores["data_nascimento"]
    if nascimento and _data_iso(nascimento):
        try:
            data = dt.date.fromisoformat(nascimento)
        except ValueError:
            data = None
        if data is not None:
            if data > dt.date.today():
                problemas.append("data_nascimento está no futuro")
            elif data.year < 1900:
                problemas.append(
                    "data_nascimento é anterior a 1900; provavelmente erro "
                    "de digitação no ano"
                )

    tem = valores["tem_processo"]
    if tem and tem not in VALORES["tem_processo"]:
        problemas.append(
            "tem_processo tem que ser " + " / ".join(VALORES["tem_processo"])
        )
    if tem == "sim":
        problemas += [
            f"número do processo: {p}"
            for p in processo_cnj.conferir(
                valores["numero_processo"], exigir_trf1=True
            )
        ]
    elif valores["numero_processo"]:
        # Não é frescura: a planilha vai ser lida por gente, e um número ao
        # lado de "não tenho sentença" é contradição que alguém vai seguir.
        problemas.append(
            "numero_processo preenchido mas tem_processo não é 'sim'"
        )

    # Só confere os números se o campo NÃO estourou o teto: depois da
    # truncagem o último número está partido, e relatar "tem 4 dígitos" em
    # cima de "passa do teto" aponta para a causa errada.
    if len(str(linha.get("acompanhar", "") or "").strip()) <= TETOS["acompanhar"]:
        problemas += _problemas_do_acompanhamento(valores["acompanhar"])

    if valores["quer_aviso"] not in VALORES["quer_aviso"]:
        problemas.append(
            "quer_aviso tem que ser " + " / ".join(
                repr(v) for v in VALORES["quer_aviso"]
            )
        )

    for coluna in ("ja_tem_execucao", "ja_recebeu_acordo", "outro_advogado"):
        if valores[coluna] not in VALORES["resposta"]:
            problemas.append(
                f"{coluna} tem que ser " + " / ".join(VALORES["resposta"])
            )

    if valores["ciencia_e_iniciativa"] != "sim":
        problemas.append("a declaração final não foi marcada")

    return problemas


def normalizar_linha(linha: dict) -> dict[str, str]:
    """A linha como vai para o diário: as colunas do contrato mais os campos
    do portal, aparadas. O manifesto do Produto A é escrito com
    `extrasaction="ignore"` sobre `COLUNAS`, então os campos do portal viajam
    no diário sem aparecer na planilha que o escritório abre."""
    saida: dict[str, str] = {}
    for coluna in ACEITAS:
        valor = str(linha.get(coluna, "") or "").strip()
        saida[coluna] = valor[: TETOS.get(coluna, TETO_PADRAO)]
    saida["uf"] = saida["uf"].upper()
    saida["id_externo"] = so_digitos(saida["cpf"])
    if saida["tem_processo"] == "sim" and saida["numero_processo"]:
        saida["numero_processo"] = processo_cnj.normalizar(
            saida["numero_processo"]
        )
    else:
        saida["numero_processo"] = ""
    saida["acompanhar"] = ACOMPANHAMENTO["separador"].join(
        numeros_de_acompanhamento(saida["acompanhar"])
    )
    return saida


def arquivos_exigidos(tem_processo: str) -> tuple[str, ...]:
    """Quais arquivos o pacote precisa ter, dada a resposta sobre o processo.

    Sentença e certidão de trânsito só de quem declarou 'sim'. Exigir de quem
    não sabe o número é travar o cadastro num documento que a pessoa não tem
    como apresentar — e é a mesma regra do portal, lida do mesmo contrato.
    """
    if tem_processo == "sim":
        return OBRIGATORIOS + SE_TEM_PROCESSO
    return OBRIGATORIOS


def conferir_pacote(
    nomes: list[str], tem_processo: str
) -> list[str]:
    """Problemas no conjunto de arquivos recebido."""
    problemas: list[str] = []
    vistos = set()
    for nome in nomes:
        if nome not in NOMES_DE_ARQUIVO:
            problemas.append(f"arquivo com nome fora do contrato: {nome!r}")
        elif nome in vistos:
            problemas.append(f"arquivo {nome} veio duas vezes")
        vistos.add(nome)
    for exigido in arquivos_exigidos(tem_processo):
        if exigido not in vistos:
            problemas.append(f"falta o arquivo {exigido}")
    return problemas


def parece_pdf(corpo: bytes) -> bool:
    """Um PDF começa com %PDF-. Confiar na extensão é confiar no cliente."""
    return corpo[:5] == b"%PDF-"


# O mesmo número que `portal/src/lib/leitura.ts` usa. Abaixo disso o PDF tem
# alguma marca de texto mas não o conteúdo do documento — tipicamente uma
# digitalização com um rodapé de scanner por cima da imagem.
MINIMO_DE_CARACTERES = 120


def texto_extraivel(corpo: bytes) -> tuple[bool, int]:
    """(serve, quantos caracteres). Um PDF só-imagem devolve (False, 0).

    POR QUE NO SERVIDOR TAMBÉM, se o portal já confere: porque
    `ferramentas/conferir_entrega.py` REPROVA documento sem camada de texto,
    e a reprovação acontece no escritório, dias depois, longe da pessoa que
    tem o documento na mão. Se o servidor aceita o que o motor recusa, o
    portal entrega recibo para um cadastro que já nasceu reprovado.

    O portal confere para a pessoa não errar; aqui conferimos porque o
    navegador não é fonte de verdade — e um POST montado à mão não passa pelo
    portal nenhum.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        # Sem pypdf não inventamos aprovação: devolvemos "não sei" como
        # serve=True e 0 caracteres, e quem chama decide. Veja o uso em
        # `app.py`: lá isso vira aviso, não recusa, porque recusar todo mundo
        # por falta de biblioteca no servidor é pior que deixar o motor pegar.
        return True, 0
    import io as _io

    try:
        leitor = PdfReader(_io.BytesIO(corpo))
        texto = "".join(pagina.extract_text() or "" for pagina in leitor.pages)
    except Exception:
        return False, 0
    return len(texto.strip()) >= MINIMO_DE_CARACTERES, len(texto.strip())
