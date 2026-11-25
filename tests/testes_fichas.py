#!/usr/bin/env python3
"""
A ficha financeira — a base de cálculo, mês a mês, que o sindicato envia.

É o insumo que faltava para a conta existir: `nucleo/valor.py` sabe aplicar
o percentual da verba, e não havia do que tirar percentual.

O QUE ESTES TESTES FIXAM:

1. A planilha é lida com o que um sindicato manda: CPF pontuado, mês como
   `03/2004` ou `2004-03`, valor como `5.000,00`.
2. Linha que não dá para entender é CONTADA, nunca adivinhada.
3. O mesmo mês com dois valores para a mesma pessoa é divergência, e
   divergência não se resolve sozinha: a ficha dela não entra.
4. Só fica guardado quem é da base.
5. Envio novo de uma pessoa SUBSTITUI a ficha dela inteira — juntar deixaria
   um mês velho no meio de uma conta nova.
6. Quem pede para sair sai de todas as linhas.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import fichas  # noqa: E402

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def cpf(base: int) -> str:
    """Um CPF que fecha, da faixa `000.009.xxx` — declaradamente de teste."""
    nove = f"000009{base:03d}"
    d = [int(c) for c in nove]
    for corte in (9, 10):
        soma = sum(d[i] * (corte + 1 - i) for i in range(corte))
        d.append((soma * 10) % 11 % 10)
    return "".join(str(x) for x in d)


A, B, C = (cpf(n) for n in (100, 101, 102))


def pontuado(c: str) -> str:
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


def planilha(*linhas: tuple, cabecalho: str = "CPF;Competência;Base") -> bytes:
    corpo = [cabecalho] + [";".join(str(x) for x in l) for l in linhas]
    return ("\n".join(corpo) + "\n").encode("utf-8")


def pasta_nova() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp(prefix="ficha-"))


def enviar(pasta, corpo: bytes, base, arquivo="ficha.csv"):
    lido = fichas.ler_arquivo(corpo, arquivo)
    return fichas.enviar(pasta, lido, base_de=lambda: set(base),
                         quem="marcador-de-teste", arquivo=arquivo,
                         sha256="0" * 64)


def teste_le_o_que_um_sindicato_manda():
    secao("ler a planilha")
    lido = fichas.ler_arquivo(planilha(
        (pontuado(A), "03/2004", "5.000,00"),
        (A, "2004-04", "5000.5"),
        (A, "05/2004", "R$ 1.234,56"),
    ), "ficha.csv")
    checa(lido.fichas == {A: {"2004-03": "5000.00", "2004-04": "5000.50",
                              "2004-05": "1234.56"}},
          f"leu errado: {lido.fichas}")
    checa(lido.invalidas == 0, f"contou linha boa como ruim: {lido.invalidas}")
    print("  ok     CPF pontuado, mês nos dois formatos, valor com vírgula")


def teste_linha_que_nao_se_entende_e_contada_nao_adivinhada():
    lido = fichas.ler_arquivo(planilha(
        (A, "2004-03", "5000,00"),
        ("12345678900", "2004-03", "5000,00"),      # CPF não fecha
        (A, "13/2004", "5000,00"),                   # mês que não existe
        (A, "2004-04", "cinco mil"),                 # não é número
        (A, "2004-05", "-10,00"),                    # negativo
        (A, "2004-06", ""),                          # vazio
    ), "ficha.csv")
    checa(lido.fichas == {A: {"2004-03": "5000.00"}},
          f"guardou linha ruim: {lido.fichas}")
    checa(lido.invalidas == 5, f"esperava 5 linhas recusadas: {lido.invalidas}")
    print("  ok     5 linhas ruins contadas, nenhuma adivinhada")


def teste_valor_ambiguo_nao_e_adivinhado():
    """`5.000`, sem vírgula: cinco, ou cinco mil? Com vírgula o ponto é
    milhar; sem ela, um número nesse formato não se adivinha — a diferença
    é de mil vezes, na base de cálculo de alguém."""
    lido = fichas.ler_arquivo(planilha(
        (A, "2004-03", "5.000"), (A, "2004-04", "12.345.678"),
        (A, "2004-05", "5000.50"), (A, "2004-06", "5.000,00"),
    ), "ficha.csv")
    checa(lido.fichas == {A: {"2004-05": "5000.50", "2004-06": "5000.00"}},
          f"adivinhou um valor ambíguo: {lido.fichas}")
    checa(lido.invalidas == 2, f"invalidas={lido.invalidas}")
    print("  ok     5.000 sem vírgula não entra; 5000.50 e 5.000,00 entram")


def teste_arquivo_sem_as_colunas_e_recusado():
    for corpo, o_que in (
        (planilha((A, "x"), cabecalho="CPF;Nome"), "sem competência e base"),
        (planilha(("2004-03", "1"), cabecalho="Competência;Base"), "sem CPF"),
        (planilha(("12345678900", "2004-03", "1")), "sem nenhuma linha boa"),
        (b"", "vazio"),
    ):
        try:
            fichas.ler_arquivo(corpo, "ficha.csv")
            checa(False, f"aceitou arquivo {o_que}")
        except fichas.FichaIlegivel:
            pass
    print("  ok     sem coluna, sem linha boa ou vazio: recusado com motivo")


def teste_o_mesmo_mes_com_dois_valores_nao_se_escolhe():
    """DIVERGÊNCIA NÃO SE RESOLVE SOZINHA. Ficar com o primeiro, o último ou
    o maior seria escolher a base de cálculo de alguém."""
    secao("divergência")
    lido = fichas.ler_arquivo(planilha(
        (A, "2004-03", "5000,00"), (A, "2004-03", "5200,00"),
        (B, "2004-03", "4000,00"), (B, "2004-03", "4.000,00"),  # igual: ok
    ), "ficha.csv")
    checa(A not in lido.fichas, f"escolheu um valor para A: {lido.fichas.get(A)}")
    checa(lido.divergentes == 1, f"divergentes={lido.divergentes}")
    checa(lido.fichas.get(B) == {"2004-03": "4000.00"},
          f"a repetição igual de B não é divergência: {lido.fichas.get(B)}")
    print("  ok     mês com dois valores: a pessoa fica fora, e é contada")


def teste_so_fica_guardado_quem_e_da_base():
    secao("guardar")
    pasta = pasta_nova()
    plano = enviar(pasta, planilha((A, "2004-03", "5000,00"),
                                   (C, "2004-03", "3000,00")), {A, B})
    checa(plano.pessoas == 1 and plano.fora_da_base == 1,
          f"pessoas={plano.pessoas} fora={plano.fora_da_base}")
    bruto = (pasta / fichas.ARQUIVO).read_text(encoding="utf-8")
    checa(C not in bruto, "guardou a ficha de quem não é da base")
    checa(fichas.por_cpf(pasta) == {A: (("2004-03", "5000.00"),)},
          f"{fichas.por_cpf(pasta)}")
    checa(fichas.de_cpf(pasta, pontuado(A)) == (("2004-03", "5000.00"),)
          and fichas.de_cpf(pasta, B) == (),
          "de_cpf não devolve a ficha da pessoa, ou inventa a de quem não tem")
    print("  ok     quem é de fora é contado e descartado")


def teste_o_envio_novo_substitui_a_ficha_da_pessoa_inteira():
    pasta = pasta_nova()
    enviar(pasta, planilha((A, "2004-03", "5000,00"), (A, "2004-04", "5000,00"),
                           (B, "2004-03", "4000,00")), {A, B})
    enviar(pasta, planilha((A, "2004-04", "5100,00")), {A, B})
    por = fichas.por_cpf(pasta)
    checa(por[A] == (("2004-04", "5100.00"),),
          f"juntou a ficha velha com a nova: {por[A]}")
    checa(por[B] == (("2004-03", "4000.00"),),
          f"o envio de A mexeu na ficha de B: {por[B]}")
    r = fichas.resumo(pasta, {A, B, C})
    checa(r["pessoas"] == 2 and r["sem_ficha"] == 1,
          f"resumo errado: {r}")
    print("  ok     a ficha nova de A substitui a velha; a de B fica")


def teste_quem_pede_para_sair_sai_da_ficha_guardada():
    secao("o apagamento")
    pasta = pasta_nova()
    enviar(pasta, planilha((A, "2004-03", "5000,00"),
                           (B, "2004-03", "4000,00")), {A, B})
    enviar(pasta, planilha((A, "2004-04", "5100,00")), {A, B})
    with (pasta / fichas.ARQUIVO).open("a", encoding="utf-8") as f:
        f.write("{isto não é json\n")
    saiu = fichas.remover_pessoa(pasta, pontuado(A))
    bruto = (pasta / fichas.ARQUIVO).read_text(encoding="utf-8")
    checa(saiu == 2, f"A estava em 2 linhas, saiu de {saiu}")
    checa(A not in bruto, "o CPF de quem pediu para sair continua no arquivo")
    checa("{isto não é json" in bruto, "a linha ilegível foi descartada")
    checa(fichas.por_cpf(pasta) == {B: (("2004-03", "4000.00"),)},
          f"os outros mudaram: {fichas.por_cpf(pasta)}")
    checa(fichas.remover_pessoa(pasta, A) == 0, "removeu duas vezes")
    print("  ok     sai de todas as linhas; os outros ficam como estavam")


TESTES.extend([
    teste_le_o_que_um_sindicato_manda,
    teste_linha_que_nao_se_entende_e_contada_nao_adivinhada,
    teste_valor_ambiguo_nao_e_adivinhado,
    teste_arquivo_sem_as_colunas_e_recusado,
    teste_o_mesmo_mes_com_dois_valores_nao_se_escolhe,
    teste_so_fica_guardado_quem_e_da_base,
    teste_o_envio_novo_substitui_a_ficha_da_pessoa_inteira,
    teste_quem_pede_para_sair_sai_da_ficha_guardada,
])


def main() -> int:
    print("=" * 70)
    print("FICHA FINANCEIRA — a base de cálculo que o sindicato envia")
    print("=" * 70)
    for teste in TESTES:
        try:
            teste()
        except Exception as exc:  # noqa: BLE001
            falhas.append(f"{teste.__name__}: levantou "
                          f"{type(exc).__name__}: {exc}")
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
