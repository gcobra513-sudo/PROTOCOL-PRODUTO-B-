"""
A conferência do lado do servidor.

POR QUE EXISTE, SE O PORTAL JÁ CONFERE: o portal confere para a pessoa não
errar; o servidor confere porque o navegador não é fonte de verdade. Qualquer
pessoa monta um POST à mão. Se a única validação fosse a do navegador, a
entrega que o sindicato abre seria o que quem monta o POST quisesse mandar.

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

from nucleo import cadastro as _conta
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


#: UMA SÓ, a de `nucleo/cadastro.py`. Ver lá por quê.
so_digitos = _conta.so_digitos


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






def arquivos_exigidos(tem_processo: str) -> tuple[str, ...]:
    """Quais arquivos o pacote precisa ter, dada a resposta sobre o processo.

    Sentença e certidão de trânsito só de quem declarou 'sim'. Exigir de quem
    não sabe o número é travar o cadastro num documento que a pessoa não tem
    como apresentar — e é a mesma regra do portal, lida do mesmo contrato.
    """
    if tem_processo == "sim":
        return OBRIGATORIOS + SE_TEM_PROCESSO
    return OBRIGATORIOS




def parece_pdf(corpo: bytes) -> bool:
    """Um PDF começa com %PDF-. Confiar na extensão é confiar no cliente."""
    return corpo[:5] == b"%PDF-"


# O mesmo número que `portal/src/lib/leitura.ts` usa. Abaixo disso o PDF tem
# alguma marca de texto mas não o conteúdo do documento — tipicamente uma
# digitalização com um rodapé de scanner por cima da imagem.
MINIMO_DE_CARACTERES = 120


def examinar_pdf(corpo: bytes) -> tuple[bool, bool, int]:
    """(abre, tem_texto, quantos caracteres). SÃO DUAS PERGUNTAS, e eram uma.

        abre       um leitor de PDF consegue abrir e há página. Se não, NINGUÉM
                   lê — nem máquina, nem gente: corrompido, ou com senha
        tem_texto  há camada de texto que a máquina consiga ler

    A versão anterior (`texto_extraivel`) devolvia um booleano só, e quem
    chamava recusava o cadastro inteiro quando ele era falso. A justificativa
    escrita aqui era do PRODUTO A: citava `ferramentas/conferir_entrega.py`,
    que "REPROVA documento sem camada de texto" — ferramenta que nem existe
    neste repositório. No A, sem texto não há petição a montar. No B, um
    documento que a máquina não lê pode esperar que uma PESSOA leia, e a base
    deste produto é de aposentados com papel físico: scanner e foto são o
    caso comum, não a exceção.

    Então: não abre -> recusa, com o motivo. Abre sem texto -> ACEITA, e quem
    chama marca "aguardando leitura". Decidido em 10/11/2026, depois de a
    auditoria de produto medir o 422.

    Aqui se confere porque o navegador não é fonte de verdade: um POST
    montado à mão não passa pelo portal nenhum.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        # Sem pypdf não inventamos resposta: "abre, e tem texto" com 0
        # caracteres, e quem chama decide. Recusar todo mundo — ou marcar
        # tudo como ilegível — por falta de biblioteca no servidor seria pior.
        return True, True, 0
    import io as _io

    try:
        leitor = PdfReader(_io.BytesIO(corpo))
        if leitor.is_encrypted:
            return False, False, 0
        paginas = list(leitor.pages)
    except Exception:
        return False, False, 0
    if not paginas:
        return False, False, 0
    try:
        texto = "".join(pagina.extract_text() or "" for pagina in paginas)
    except Exception:
        # Abre, tem página, e o texto não sai: é o caso de uma pessoa ler.
        return True, False, 0
    caracteres = len(texto.strip())
    return True, caracteres >= MINIMO_DE_CARACTERES, caracteres


def texto_extraivel(corpo: bytes) -> tuple[bool, int]:
    """(tem texto, quantos caracteres). Mantida para quem só quer saber isso;
    a decisão de aceitar ou recusar é de `examinar_pdf`."""
    _, tem_texto, caracteres = examinar_pdf(corpo)
    return tem_texto, caracteres
