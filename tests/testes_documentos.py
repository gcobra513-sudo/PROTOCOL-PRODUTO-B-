#!/usr/bin/env python3
"""
O caminho inteiro: PDF -> texto -> achados -> fatos -> veredicto.

POR QUE ESTA SUÍTE EXISTE SEPARADA DA `testes_leitura`

Aquela prova que o texto vira fato. Esta prova que o PDF VIRA TEXTO e que o
fato chega ao motor — e é no meio desse caminho que as coisas se perdem na
vida real: PDF que é só imagem, página que o extrator devolve em branco,
acento que vira caractere de controle.

O teste final é o que importa: uma sentença e uma certidão entram como PDF,
e sai "esta pessoa PODE executar" sem ninguém digitar nada.

NENHUM DADO PESSOAL REAL. Os PDFs são gerados aqui, com nome declaradamente
fictício e CPF sintético.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import entendimentos, leitura, motor  # noqa: E402
from servidor import documentos  # noqa: E402

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def pdf_com(linhas: list[str]) -> bytes:
    """Um PDF com camada de texto, gerado aqui."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for linha in linhas:
        c.drawString(60, y, linha)
        y -= 16
        if y < 60:
            c.showPage()
            y = 800
    c.save()
    return buffer.getvalue()


def pdf_so_imagem() -> bytes:
    """Um PDF sem camada de texto — o que sai de um scanner."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.rect(100, 100, 300, 300, fill=1)
    c.save()
    return buffer.getvalue()


SENTENCA = [
    "PODER JUDICIARIO - JUSTICA FEDERAL DE PRIMEIRO GRAU",
    "Secao Judiciaria do Distrito Federal",
    "5a Vara Federal Civel",
    "",
    "PROCESSO: 0010391-24.2006.4.01.3400",
    "AUTOR: UNAFISCO SINDICAL",
    "REU: UNIAO FEDERAL",
    "",
    "SENTENCA",
    "",
    "Trata-se de acao ordinaria proposta pelo sindicato autor, na",
    "qualidade de substituto processual, objetivando o pagamento das",
    "diferencas da GIFA, no periodo de 01/2003 a 12/2008.",
    "",
    "Ante o exposto, JULGO PROCEDENTE o pedido para condenar a Uniao",
    "ao pagamento das diferencas devidas.",
    "",
    "Brasilia, 14 de marco de 2011.",
]

CERTIDAO = [
    "CERTIDAO DE TRANSITO EM JULGADO",
    "",
    "CERTIFICO que a sentenca proferida nos autos do processo numero",
    "0010391-24.2006.4.01.3400 transitou em julgado em 22/08/2019,",
    "nada havendo nos autos que a modifique.",
]


# ------------------------------------------------------------- extração

def teste_extrai_texto_de_pdf_com_camada_de_texto():
    secao("PDF para texto")
    texto, paginas = documentos.extrair_texto(pdf_com(SENTENCA))
    checa(paginas == 1, f"contou {paginas} páginas")
    checa("0010391-24.2006.4.01.3400" in texto,
          f"o número do processo não sobreviveu à extração: {texto[:120]!r}")
    checa("JULGO PROCEDENTE" in texto.upper(),
          "o dispositivo não sobreviveu à extração")
    print(f"  ok     {len(texto)} caracteres extraídos de 1 página")


def teste_pdf_so_imagem_nao_vira_texto_inventado():
    """Scanner produz isto o tempo todo. O portal já avisa a pessoa; aqui a
    questão é não deixar passar como se tivesse sido lido."""
    texto, paginas = documentos.extrair_texto(pdf_so_imagem())
    checa(len(texto.strip()) < documentos.MINIMO_DE_CARACTERES,
          f"PDF só-imagem devolveu {len(texto)} caracteres de texto")
    checa(not documentos.tem_texto(pdf_so_imagem()),
          "disse que o PDF só-imagem tem camada de texto")
    print("  ok     PDF sem camada de texto é reconhecido como tal")


def teste_arquivo_que_nao_e_pdf_falha_fechado():
    texto, paginas = documentos.extrair_texto(b"isto nao e um PDF")
    checa(texto == "" and paginas == 0,
          f"inventou conteúdo para um não-PDF: {texto!r}")
    print("  ok     não-PDF devolve vazio, não exceção nem invenção")


# --------------------------------------------------------------- leitura

def teste_le_os_fatos_da_sentenca_em_pdf():
    secao("PDF para fatos")
    achados = documentos.ler_pdf(pdf_com(SENTENCA))
    tipos = {a.tipo for a in achados}
    for esperado in ("numero_processo", "dispositivo", "periodo"):
        checa(esperado in tipos, f"não achou {esperado}: {sorted(tipos)}")
    numero = next(a for a in achados if a.tipo == "numero_processo")
    checa(numero.valor == "00103912420064013400", numero.valor)
    checa(numero.confianca == leitura.CERTO, numero.confianca)
    print(f"  ok     {len(achados)} achado(s) na sentença: {sorted(tipos)}")


def teste_le_o_transito_da_certidao_em_pdf():
    achados = documentos.ler_pdf(pdf_com(CERTIDAO))
    transito = [a for a in achados if a.tipo == "transito_em_julgado"]
    checa(len(transito) == 1, f"trânsito: {transito}")
    if transito:
        checa(transito[0].valor == "2019-08-22", transito[0].valor)
    print("  ok     trânsito em julgado lido do PDF")


def teste_os_dois_documentos_juntos_concordam():
    """Sentença e certidão trazem o MESMO número. Se o módulo relatasse
    divergência aqui, o escritório conferiria à toa a vida inteira."""
    achados = (documentos.ler_pdf(pdf_com(SENTENCA))
               + documentos.ler_pdf(pdf_com(CERTIDAO)))
    checa(leitura.divergencias(achados) == {},
          f"inventou divergência entre documentos que concordam: "
          f"{leitura.divergencias(achados)}")
    print("  ok     documentos que concordam não geram divergência")


# ----------------------------------------------------- o caminho completo

def teste_do_pdf_ao_veredicto_sem_ninguem_digitar():
    """O TESTE QUE IMPORTA.

    Dois PDFs entram. Sai "esta pessoa PODE executar". Ninguém digitou o
    número do processo, a data do trânsito nem o dispositivo — e é esse o
    produto que o filiado compra sem saber que compra.
    """
    secao("do PDF ao veredicto")
    achados = (documentos.ler_pdf(pdf_com(SENTENCA))
               + documentos.ler_pdf(pdf_com(CERTIDAO)))
    fatos_lidos = leitura.fatos_confiaveis(achados)

    checa(fatos_lidos.get("transito_em_julgado") == "2019-08-22",
          f"o trânsito não chegou aos fatos: {fatos_lidos}")
    checa(fatos_lidos.get("dispositivo") == "procedente",
          f"o dispositivo não chegou aos fatos: {fatos_lidos}")

    # O que os documentos NÃO dizem continua vindo de fora: o rol de
    # substituídos está na ação coletiva, não no PDF da pessoa.
    fatos = documentos.fatos_para_o_motor(
        fatos_lidos,
        # A filiação NÃO está na sentença: vem dos comprovantes de
        # contribuição, pelo cadastro. Sem ela o motor recusa dizer PODE, e
        # é o comportamento certo.
        cadastro={"cpf": "11144477735", "nome": "FULANA DE TAL (EXEMPLO)",
                  "cargo": "Auditor-Fiscal da Receita Federal do Brasil",
                  "filiado_desde": "1992-05", "filiado_ate": ""},
        no_rol=True,
        ja_executou=False,
    )
    checa(fatos.tem_titulo is True,
          "sentença procedente + trânsito em julgado deviam dar tem_titulo=True")

    catalogo = entendimentos.carregar(
        RAIZ / "config" / "entendimentos.toml"
    ).homologando(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    podem = [o for o in motor.avaliar(fatos, catalogo)
             if o.trilha == motor.EXECUTAR and o.veredicto == motor.PODE]
    checa(podem != [],
          f"o caminho completo não chegou a PODE: "
          f"{[(o.referencia, o.veredicto, o.motivos) for o in motor.avaliar(fatos, catalogo)]}")
    print("  ok     dois PDFs entram, 'PODE executar' sai, zero digitação")


def teste_sentenca_improcedente_nao_vira_titulo():
    """O inverso do teste anterior, e é o que impede a promessa falsa: uma
    sentença improcedente transitada NÃO é título a executar."""
    ruim = [l.replace("JULGO PROCEDENTE", "JULGO IMPROCEDENTE") for l in SENTENCA]
    achados = documentos.ler_pdf(pdf_com(ruim)) + documentos.ler_pdf(pdf_com(CERTIDAO))
    fatos = documentos.fatos_para_o_motor(
        leitura.fatos_confiaveis(achados),
        cadastro={"cpf": "11144477735",
                  "cargo": "Auditor-Fiscal da Receita Federal do Brasil",
                  "filiado_desde": "1992-05"},
        no_rol=True, ja_executou=False,
    )
    checa(fatos.tem_titulo is False,
          f"sentença IMPROCEDENTE virou título: tem_titulo={fatos.tem_titulo}")

    catalogo = entendimentos.carregar(
        RAIZ / "config" / "entendimentos.toml"
    ).homologando(("STJ-T1169", "STJ-T1302", "GIFA-2006"))
    executar = [o for o in motor.avaliar(fatos, catalogo)
                if o.trilha == motor.EXECUTAR]
    checa(all(o.veredicto != motor.PODE for o in executar),
          "disse PODE executar com sentença improcedente")
    print("  ok     improcedente não vira título, e não vira PODE")


def teste_sem_transito_nao_ha_titulo_ainda():
    """Procedente mas sem trânsito: ainda cabe recurso, e executar seria
    executar o que não é definitivo."""
    achados = documentos.ler_pdf(pdf_com(SENTENCA))      # só a sentença
    fatos = documentos.fatos_para_o_motor(
        leitura.fatos_confiaveis(achados),
        cadastro={"cpf": "11144477735",
                  "cargo": "Auditor-Fiscal da Receita Federal do Brasil",
                  "filiado_desde": "1992-05"},
        no_rol=True, ja_executou=False,
    )
    checa(fatos.tem_titulo is None,
          f"sem certidão de trânsito, tem_titulo devia ser desconhecido "
          f"(None), veio {fatos.tem_titulo!r}")
    print("  ok     sem trânsito, a resposta é 'não sei', não 'sim'")


TESTES.extend([
    teste_extrai_texto_de_pdf_com_camada_de_texto,
    teste_pdf_so_imagem_nao_vira_texto_inventado,
    teste_arquivo_que_nao_e_pdf_falha_fechado,
    teste_le_os_fatos_da_sentenca_em_pdf,
    teste_le_o_transito_da_certidao_em_pdf,
    teste_os_dois_documentos_juntos_concordam,
    teste_do_pdf_ao_veredicto_sem_ninguem_digitar,
    teste_sentenca_improcedente_nao_vira_titulo,
    teste_sem_transito_nao_ha_titulo_ainda,
])


def main() -> int:
    print("=" * 70)
    print("DOCUMENTOS — do PDF ao veredicto")
    print("=" * 70)
    for teste in TESTES:
        antes = len(falhas)
        try:
            teste()
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{teste.__name__}: levantou "
                          f"{type(exc).__name__}: {exc}")
            print(f"  FALHA  {teste.__name__}")
        else:
            if len(falhas) > antes:
                print(f"  FALHA  {teste.__name__}")
    print("-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
