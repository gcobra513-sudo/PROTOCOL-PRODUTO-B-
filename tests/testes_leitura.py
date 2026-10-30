#!/usr/bin/env python3
"""
A caixa 2: ler o que os documentos dizem.

O SALTO QUE FALTAVA. O portal já extrai o TEXTO do PDF; ninguém nunca tirou
FATOS desse texto. Hoje o filiado digita o número do processo à mão, e tudo o
que está na sentença — trânsito em julgado, órgão julgador, dispositivo,
período — continua trancado num PDF que só um humano lê.

A REGRA QUE GOVERNA ESTE MÓDULO: **nunca afirmar o que não dá para
justificar.**

Cada achado carrega o TRECHO de onde saiu. Um humano confere a extração sem
abrir o PDF, lendo uma linha. Extração sem trecho é palpite com cara de dado,
e num produto que diz a uma pessoa se ela tem direito a dinheiro isso é
inaceitável.

E três níveis de confiança, porque eles decidem coisas diferentes:

    CERTO     tem conferência própria — dígito verificador que fecha, frase
              inequívoca. Pode alimentar o motor sozinho
    PROVAVEL  o padrão casou, mas a frase admite outra leitura. Vai para
              conferência humana, NÃO para o motor
    SUSPEITO  casou a forma e falhou a conferência — número cujo dígito não
              fecha. É DEFEITO, e aparece como tal

Uma data solta num documento NÃO é trânsito em julgado. Só vira achado se a
frase disser que é. Esta é a diferença entre ler e adivinhar.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import leitura  # noqa: E402

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def de_tipo(achados, tipo):
    return [a for a in achados if a.tipo == tipo]


# Uma sentença sintética, no formato que o TRF1 produz. Nome e CPF
# declaradamente fictícios.
SENTENCA = """
PODER JUDICIÁRIO
JUSTIÇA FEDERAL DE PRIMEIRO GRAU
Seção Judiciária do Distrito Federal
5ª Vara Federal Cível da SJDF

PROCESSO: 0010391-24.2006.4.01.3400
CLASSE: AÇÃO ORDINÁRIA
AUTOR: UNAFISCO SINDICAL - SINDICATO NACIONAL DOS AUDITORES-FISCAIS
RÉU: UNIÃO FEDERAL

SENTENÇA

Trata-se de ação ordinária proposta pelo sindicato autor, na qualidade de
substituto processual de seus filiados, objetivando o pagamento das
diferenças da Gratificação de Incremento da Fiscalização e Arrecadação
(GIFA), no período de 01/2003 a 12/2008.

[...]

Ante o exposto, JULGO PROCEDENTE o pedido para condenar a União ao pagamento
das diferenças devidas, observada a prescrição quinquenal.

Brasília, 14 de março de 2011.

JOÃO DA SILVA SAURO (NOME FICTÍCIO)
Juiz Federal
"""

CERTIDAO = """
PODER JUDICIÁRIO
SEÇÃO JUDICIÁRIA DO DISTRITO FEDERAL

CERTIDÃO DE TRÂNSITO EM JULGADO

CERTIFICO que a sentença proferida nos autos do processo nº
0010391-24.2006.4.01.3400 transitou em julgado em 22/08/2019, nada havendo
nos autos que a modifique.

O referido é verdade e dou fé.
Brasília, 05/09/2019.
"""

# Um documento com data mas SEM frase de trânsito. Não pode virar achado de
# trânsito em julgado — é o teste que separa ler de adivinhar.
PETICAO = """
EXCELENTÍSSIMO SENHOR JUIZ FEDERAL

FULANA DE TAL (CADASTRO DE EXEMPLO), CPF 111.444.777-35, vem requerer a
juntada do documento em anexo.

Brasília, 22/08/2019.
"""


# --------------------------------------------------- número CNJ e dígito

def teste_acha_o_numero_do_processo_e_confere_o_digito():
    secao("número do processo")
    achados = leitura.ler(SENTENCA)
    numeros = de_tipo(achados, "numero_processo")
    checa(len(numeros) == 1, f"achou {len(numeros)} números, esperava 1")
    if numeros:
        checa(numeros[0].valor == "00103912420064013400",
              f"normalizou errado: {numeros[0].valor!r}")
        checa(numeros[0].confianca == leitura.CERTO,
              f"número com dígito que fecha devia ser CERTO: "
              f"{numeros[0].confianca}")
        checa("0010391" in numeros[0].trecho,
              f"o trecho não mostra o número: {numeros[0].trecho!r}")
    print("  ok     número CNJ achado, normalizado e conferido")


def teste_numero_com_digito_errado_e_SUSPEITO_nao_some():
    """Descartar seria esconder um defeito de digitação do cartório."""
    texto = "PROCESSO: 0010391-99.2006.4.01.3400"
    achados = de_tipo(leitura.ler(texto), "numero_processo")
    checa(len(achados) == 1, "o número com dígito errado sumiu")
    if achados:
        checa(achados[0].confianca == leitura.SUSPEITO,
              f"devia ser SUSPEITO, veio {achados[0].confianca}")
    print("  ok     dígito que não fecha vira SUSPEITO, não desaparece")


def teste_nao_inventa_numero_onde_nao_ha():
    checa(de_tipo(leitura.ler("Nada aqui. 12345. 2006."), "numero_processo") == [],
          "inventou número de processo")
    print("  ok     texto sem número não produz número")


# ------------------------------------------------------ trânsito em julgado

def teste_transito_so_existe_se_a_frase_disser_que_existe():
    """O teste que separa LER de ADIVINHAR.

    A petição tem uma data — a mesma data do trânsito, de propósito — e
    nenhuma frase de trânsito. Se o módulo emitir trânsito ali, ele está
    chutando, e um chute aqui vira "sua pretensão prescreveu".
    """
    secao("trânsito em julgado")
    da_certidao = de_tipo(leitura.ler(CERTIDAO), "transito_em_julgado")
    da_peticao = de_tipo(leitura.ler(PETICAO), "transito_em_julgado")

    checa(len(da_certidao) == 1,
          f"não achou o trânsito na certidão: {da_certidao}")
    if da_certidao:
        checa(da_certidao[0].valor == "2019-08-22",
              f"data errada: {da_certidao[0].valor!r}")
        checa(da_certidao[0].confianca == leitura.CERTO,
              f"frase inequívoca devia ser CERTO: {da_certidao[0].confianca}")
    checa(da_peticao == [],
          f"inventou trânsito em julgado a partir de uma data solta: "
          f"{da_peticao}")
    print("  ok     data solta não vira trânsito; a frase é que decide")


def teste_data_por_extenso_tambem_e_lida():
    """Sentença velha escreve a data por extenso, e descartá-la seria perder
    o documento mais importante do acervo."""
    texto = "transitou em julgado em 22 de agosto de 2019, nada havendo"
    achados = de_tipo(leitura.ler(texto), "transito_em_julgado")
    checa(len(achados) == 1, f"não leu a data por extenso: {achados}")
    if achados:
        checa(achados[0].valor == "2019-08-22",
              f"data por extenso virou {achados[0].valor!r}")
    print("  ok     data por extenso lida")


def teste_data_impossivel_nao_vira_achado():
    checa(de_tipo(leitura.ler("transitou em julgado em 31/02/2019"),
                  "transito_em_julgado") == [],
          "aceitou 31 de fevereiro")
    print("  ok     data que não existe no calendário é recusada")


# ------------------------------------------------------------- dispositivo

def teste_le_o_dispositivo_da_sentenca():
    secao("dispositivo e órgão")
    achados = de_tipo(leitura.ler(SENTENCA), "dispositivo")
    checa(len(achados) == 1, f"dispositivo: {achados}")
    if achados:
        checa(achados[0].valor == "procedente",
              f"leu o dispositivo como {achados[0].valor!r}")
    print("  ok     JULGO PROCEDENTE lido como procedente")


def teste_parcialmente_procedente_nao_vira_procedente():
    """A diferença muda o que se pode cobrar. Ler 'parcialmente procedente'
    como 'procedente' é afirmar direito que a sentença não deu."""
    achados = de_tipo(leitura.ler("JULGO PARCIALMENTE PROCEDENTE o pedido"),
                      "dispositivo")
    checa(achados and achados[0].valor == "parcialmente_procedente",
          f"confundiu parcial com total: {[a.valor for a in achados]}")
    print("  ok     parcialmente procedente é outra coisa")


def teste_improcedente_e_extinto_sao_lidos():
    for texto, esperado in (
        ("JULGO IMPROCEDENTE o pedido", "improcedente"),
        ("JULGO EXTINTO o processo sem resolução do mérito", "extinto"),
    ):
        achados = de_tipo(leitura.ler(texto), "dispositivo")
        checa(achados and achados[0].valor == esperado,
              f"{texto!r} -> {[a.valor for a in achados]}, esperava {esperado}")
    print("  ok     improcedente e extinto lidos")


def teste_acha_o_orgao_julgador():
    achados = de_tipo(leitura.ler(SENTENCA), "orgao_julgador")
    checa(achados != [], "não achou a vara")
    if achados:
        # O nome INTEIRO. "5ª Vara Fe" é pior que nada: parece dado e está
        # cortado no meio da palavra, e vai assim para a tela do gestor.
        checa(achados[0].valor == "5ª Vara Federal Cível",
              f"órgão lido como {achados[0].valor!r}, esperava "
              f"'5ª Vara Federal Cível'")
    print(f"  ok     órgão julgador: {achados[0].valor if achados else '-'}")


# ------------------------------------------------------------------ período

def teste_le_o_periodo_apurado():
    secao("período e valores")
    achados = de_tipo(leitura.ler(SENTENCA), "periodo")
    checa(achados != [], "não achou o período")
    if achados:
        checa(achados[0].valor == "2003-01/2008-12",
              f"período lido como {achados[0].valor!r}")
    print("  ok     período 01/2003 a 12/2008 lido")


def teste_le_valores_em_reais():
    achados = de_tipo(leitura.ler("o valor de R$ 12.345,67 a ser pago"), "valor")
    checa(achados and achados[0].valor == "12345.67",
          f"valor lido como {[a.valor for a in achados]}")
    print("  ok     R$ 12.345,67 lido como 12345.67")


# -------------------------------------------------------------------- CPF

def teste_acha_cpf_e_confere_o_digito():
    secao("CPF")
    achados = de_tipo(leitura.ler(PETICAO), "cpf")
    checa(len(achados) == 1, f"CPF: {achados}")
    if achados:
        checa(achados[0].valor == "11144477735", f"{achados[0].valor!r}")
        checa(achados[0].confianca == leitura.CERTO, achados[0].confianca)
    print("  ok     CPF achado e conferido")


def teste_cpf_com_digito_errado_e_SUSPEITO():
    achados = de_tipo(leitura.ler("CPF 111.444.777-00"), "cpf")
    checa(achados and achados[0].confianca == leitura.SUSPEITO,
          f"{[a.confianca for a in achados]}")
    print("  ok     CPF que não fecha vira SUSPEITO")


# ------------------------------------------------------------- procedência

def teste_todo_achado_traz_o_trecho_e_o_metodo():
    """Extração sem trecho é palpite com cara de dado. O trecho é o que
    permite a um humano conferir sem abrir o PDF."""
    secao("procedência")
    for a in leitura.ler(SENTENCA) + leitura.ler(CERTIDAO):
        checa(bool(a.trecho.strip()), f"{a.tipo}: achado sem trecho")
        checa(bool(a.metodo), f"{a.tipo}: achado sem método")
        checa(a.confianca in leitura.CONFIANCAS,
              f"{a.tipo}: confiança desconhecida {a.confianca!r}")
        checa(a.posicao >= 0, f"{a.tipo}: posição inválida")
    print("  ok     todo achado tem trecho, método, confiança e posição")


def teste_so_o_CERTO_alimenta_o_motor():
    """A regra que liga esta caixa à caixa 3: PROVAVEL e SUSPEITO não viram
    fato automaticamente. Vão para conferência."""
    achados = leitura.ler(SENTENCA) + leitura.ler(CERTIDAO)
    automaticos = leitura.fatos_confiaveis(achados)
    for tipo, valor in automaticos.items():
        origem = [a for a in achados if a.tipo == tipo and a.valor == valor]
        checa(all(a.confianca == leitura.CERTO for a in origem),
              f"{tipo}: fato automático veio de achado não-CERTO")
    checa("numero_processo" in automaticos,
          f"o número do processo devia entrar automaticamente: {automaticos}")
    print(f"  ok     {len(automaticos)} fato(s) automático(s), todos CERTO")


def teste_dois_documentos_que_discordam_nao_se_fundem_em_silencio():
    """Dois PDFs com números de processo diferentes. Escolher um seria
    sortear qual versão vale."""
    a = leitura.ler("PROCESSO: 0010391-24.2006.4.01.3400")
    b = leitura.ler("PROCESSO: 0001234-70.2019.4.01.3400")
    fatos = leitura.fatos_confiaveis(a + b)
    checa("numero_processo" not in fatos,
          f"escolheu sozinho entre dois números divergentes: {fatos}")
    divergencias = leitura.divergencias(a + b)
    checa("numero_processo" in divergencias,
          f"não relatou a divergência: {divergencias}")
    print("  ok     documentos que discordam viram divergência, não escolha")


TESTES.extend([
    teste_acha_o_numero_do_processo_e_confere_o_digito,
    teste_numero_com_digito_errado_e_SUSPEITO_nao_some,
    teste_nao_inventa_numero_onde_nao_ha,
    teste_transito_so_existe_se_a_frase_disser_que_existe,
    teste_data_por_extenso_tambem_e_lida,
    teste_data_impossivel_nao_vira_achado,
    teste_le_o_dispositivo_da_sentenca,
    teste_parcialmente_procedente_nao_vira_procedente,
    teste_improcedente_e_extinto_sao_lidos,
    teste_acha_o_orgao_julgador,
    teste_le_o_periodo_apurado,
    teste_le_valores_em_reais,
    teste_acha_cpf_e_confere_o_digito,
    teste_cpf_com_digito_errado_e_SUSPEITO,
    teste_todo_achado_traz_o_trecho_e_o_metodo,
    teste_so_o_CERTO_alimenta_o_motor,
    teste_dois_documentos_que_discordam_nao_se_fundem_em_silencio,
])


def main() -> int:
    print("=" * 70)
    print("LEITURA DE DOCUMENTOS — texto vira fato, com procedência")
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
