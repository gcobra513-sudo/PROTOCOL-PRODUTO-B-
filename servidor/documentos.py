"""
Do PDF ao fato. A ponte entre o documento que a pessoa manda e o motor.

TRÊS PASSOS, E CADA UM PODE FALHAR DE UM JEITO DIFERENTE:

    PDF  ──extrair_texto──>  texto  ──nucleo.leitura──>  achados
                                                            │
                                            fatos_para_o_motor
                                                            ↓
                                                      motor.Fatos

O primeiro passo falha com PDF só-imagem — o que sai de scanner, e é comum
em acervo de sindicato. O portal já avisa a pessoa na hora; aqui a regra é
não deixar passar como se tivesse sido lido. Texto vazio é texto vazio, não
"documento sem nada relevante".

A REGRA QUE DECIDE O RESTO: **título não é dispositivo, e não é trânsito. É
os dois juntos.**

Uma sentença procedente sem trânsito ainda admite recurso; executá-la seria
executar o que não é definitivo. Uma sentença improcedente transitada é
definitiva e não dá nada a cobrar. Por isso `tem_titulo` só é `True` com
procedente (total ou parcial) E trânsito, é `False` com improcedente ou
extinto, e é `None` — não se sabe — em todo o resto.

`None` é resposta legítima e é a mais comum no começo. Transformá-la em
`True` por otimismo é o que faria o sistema prometer dinheiro a quem não tem
título.
"""
from __future__ import annotations

import io

from nucleo import leitura, motor

#: Abaixo disto, o PDF não tem camada de texto que sirva. O mesmo número que
#: `validacao.texto_extraivel` usa, e pelo mesmo motivo: um PDF de scanner
#: devolve meia dúzia de caracteres de metadado e nada mais.
MINIMO_DE_CARACTERES = 120

#: Dispositivos que produzem título executivo, quando há trânsito.
#: "parcialmente procedente" entra: o que foi deferido é executável, e o
#: limite do que se pode cobrar é problema do cálculo, não da existência do
#: título.
DISPOSITIVOS_COM_TITULO = ("procedente", "parcialmente_procedente")
DISPOSITIVOS_SEM_TITULO = ("improcedente", "extinto")


def extrair_texto(corpo: bytes) -> tuple[str, int]:
    """(texto, número de páginas). Falha fechado: (" ", 0) vira ("", 0).

    Não levanta. Um PDF corrompido no meio de uma ingestão de cinco mil
    documentos não pode derrubar a ingestão — ele tem de virar um documento
    sem texto, visível no relatório, e os outros seguem.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", 0
    # O pypdf imprime "EOF marker not found" no log ao receber lixo. A
    # saída da suíte tem de ser limpa: aviso que aparece sempre vira ruído
    # que ninguém lê, e aí o aviso que importa passa despercebido.
    import logging

    _antes = logging.getLogger("pypdf").level
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        leitor = PdfReader(io.BytesIO(corpo))
        paginas = len(leitor.pages)
        texto = "\n".join(p.extract_text() or "" for p in leitor.pages)
    except Exception:  # noqa: BLE001
        return "", 0
    finally:
        logging.getLogger("pypdf").setLevel(_antes)
    return texto, paginas


def tem_texto(corpo: bytes) -> bool:
    texto, _ = extrair_texto(corpo)
    return len(texto.strip()) >= MINIMO_DE_CARACTERES


def ler_pdf(corpo: bytes) -> list[leitura.Achado]:
    """Os achados de um PDF. Lista vazia se não houver texto."""
    texto, _ = extrair_texto(corpo)
    if len(texto.strip()) < MINIMO_DE_CARACTERES:
        return []
    return leitura.ler(texto)


def tem_titulo(fatos_lidos: dict[str, str]) -> bool | None:
    """Há título executivo? True / False / None, e o None importa.

    Título é DISPOSITIVO FAVORÁVEL **mais** TRÂNSITO EM JULGADO. Um sem o
    outro não é título:

      - procedente sem trânsito  -> ainda cabe recurso. None
      - improcedente             -> definitivo e nada a cobrar. False
      - trânsito sem dispositivo -> não se sabe do quê. None
    """
    dispositivo = fatos_lidos.get("dispositivo")
    transito = fatos_lidos.get("transito_em_julgado")

    if dispositivo in DISPOSITIVOS_SEM_TITULO:
        # Improcedente é resposta, e não depende do trânsito para sê-lo.
        return False
    if dispositivo in DISPOSITIVOS_COM_TITULO and transito:
        return True
    return None


def fatos_para_o_motor(
    fatos_lidos: dict[str, str],
    cadastro: dict[str, str] | None = None,
    *,
    no_rol: bool | None = None,
    ja_executou: bool | None = None,
    tem_acao_propria: bool | None = None,
) -> motor.Fatos:
    """Junta o que os documentos disseram com o que não está neles.

    O que os PDFs da pessoa NÃO podem dizer, e por isso entra por fora:

      `no_rol`           está na ação coletiva, não no documento dela;
      `ja_executou`      está na base de execuções do escritório;
      `tem_acao_propria` idem.

    Passar `None` nesses é o estado honesto antes de o escritório fornecer as
    bases — e o motor devolve FALTA, que é o certo.
    """
    cadastro = cadastro or {}
    return motor.Fatos(
        cpf=cadastro.get("cpf", ""),
        nome=cadastro.get("nome", ""),
        cargo=cadastro.get("cargo", ""),
        situacao=cadastro.get("situacao", ""),
        data_ingresso=cadastro.get("data_ingresso", ""),
        data_aposentadoria=cadastro.get("data_aposentadoria", ""),
        tem_titulo=tem_titulo(fatos_lidos),
        no_rol=no_rol,
        ja_executou=ja_executou,
        tem_acao_propria=tem_acao_propria,
    )
