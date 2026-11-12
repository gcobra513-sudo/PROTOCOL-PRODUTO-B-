#!/usr/bin/env python3
"""
O rol de substituídos: a porta por onde ele entra.

O motor sempre soube perguntar "esta pessoa consta do rol?" — e ninguém
nunca respondeu. `grep -rn "no_rol="` em `nucleo/`, `servidor/` e
`ferramentas/` não achava um lugar que gravasse o fato (auditoria de
10/11/2026, item 1). Era por isso que o produto não chegava a `PODE` por
caminho nenhum.

O QUE ESTES TESTES FIXAM, e nenhuma das quatro coisas é detalhe:

1. **O rol é de UMA ação.** Enviado para a GIFA, responde pela GIFA.
2. **Ausência só é resposta quando a lista é declarada COMPLETA.** Quem não
   aparece numa lista parcial não está "fora do rol": não se sabe.
3. **Só fica guardado quem é da base.** O rol traz gente que este sindicato
   não declarou atender; o CPF dessas pessoas é contado e descartado.
4. **Quem entrou na base DEPOIS do envio não tem resposta.** Dizer "fora do
   rol" de quem nunca foi comparado com o rol seria inventar.
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import substituidos  # noqa: E402

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


A, B, C, D, E = (cpf(n) for n in (100, 101, 102, 103, 104))


def planilha(*cpfs: str, cabecalho: str = "CPF;Nome") -> bytes:
    linhas = [cabecalho] + [f"{c};PESSOA DE EXEMPLO (FICTÍCIA)" for c in cpfs]
    return ("\n".join(linhas) + "\n").encode("utf-8")


def pdf_com(linhas: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for linha in linhas:
        c.drawString(60, y, linha)
        y -= 16
    c.save()
    return buffer.getvalue()


def pontuado(c: str) -> str:
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


def pasta_nova() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp(prefix="rol-"))


def enviar(pasta, acao, cpfs, base, *, completo, arquivo="rol.csv"):
    lido = substituidos.ler_arquivo(planilha(*cpfs), arquivo)
    plano = substituidos.planejar(lido, set(base), acao=acao,
                                  completo=completo)
    substituidos.gravar(pasta, plano, quem="marcador-de-teste",
                        arquivo=arquivo, sha256="0" * 64)
    return plano


# ------------------------------------------------------------ ler o arquivo

def teste_planilha_com_coluna_de_cpf():
    secao("ler o arquivo")
    corpo = planilha(pontuado(A), B, B, "12345678900", "", cabecalho="cpf;nome")
    lido = substituidos.ler_arquivo(corpo, "rol.csv")
    checa(lido.cpfs == frozenset({A, B}), f"CPFs lidos: {sorted(lido.cpfs)}")
    checa(lido.invalidas == 2,
          f"1 CPF que não fecha e 1 linha sem CPF = 2, veio {lido.invalidas}")
    print("  ok     planilha: pontuado e cru, repetido conta uma vez, "
          "o que não fecha é contado à parte")


def teste_planilha_sem_coluna_de_cpf_e_recusada():
    """Rol só com nome e matrícula existe. Casar por nome é adivinhar — com
    o direito de alguém —, e por isso a recusa diz o que falta."""
    corpo = "Nome;Matrícula\nPESSOA DE EXEMPLO;1234567\n".encode()
    try:
        substituidos.ler_arquivo(corpo, "rol.csv")
    except substituidos.RolIlegivel as e:
        checa("CPF" in str(e), f"a recusa não fala em CPF: {e}")
    else:
        checa(False, "aceitou um rol sem coluna de CPF")
    print("  ok     sem coluna de CPF: recusado, e diz por quê")


def teste_pdf_com_texto():
    corpo = pdf_com(["ROL DE SUBSTITUIDOS - documento de exemplo",
                     f"1. PESSOA DE EXEMPLO UM   CPF {pontuado(A)}",
                     f"2. PESSOA DE EXEMPLO DOIS CPF {pontuado(B)}",
                     "3. PESSOA DE EXEMPLO TRES CPF 123.456.789-00",
                     "Processo 0010391-24.2006.4.01.3400"] + ["linha"] * 12)
    lido = substituidos.ler_arquivo(corpo, "rol.pdf")
    checa(lido.cpfs == frozenset({A, B}), f"CPFs lidos: {sorted(lido.cpfs)}")
    checa(lido.invalidas == 1, f"o CPF que não fecha: {lido.invalidas}")
    print("  ok     PDF com texto: só CPF escrito por extenso e que fecha")


def teste_pdf_sem_texto_e_recusado():
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.rect(100, 100, 300, 300, fill=1)
    c.save()
    try:
        substituidos.ler_arquivo(buffer.getvalue(), "rol.pdf")
    except substituidos.RolIlegivel as e:
        checa("planilha" in str(e).lower(), f"não aponta a saída: {e}")
    else:
        checa(False, "aceitou um rol em imagem como se tivesse lido")
    print("  ok     PDF de scanner: recusado, não vira rol vazio")


def teste_arquivo_sem_nenhum_cpf_valido_e_recusado():
    """Um rol vazio e DECLARADO COMPLETO poria a base inteira fora do rol."""
    try:
        substituidos.ler_arquivo(planilha("123", "456"), "rol.csv")
    except substituidos.RolIlegivel:
        pass
    else:
        checa(False, "aceitou um rol sem nenhum CPF válido")
    print("  ok     nenhum CPF válido: recusado")


# ----------------------------------------------------------------- o plano

def teste_lista_completa_responde_por_quem_nao_esta_nela():
    secao("o plano")
    lido = substituidos.ler_arquivo(planilha(A, B, E), "rol.csv")
    plano = substituidos.planejar(lido, {A, B, C, D}, acao="GIFA-2006",
                                  completo=True)
    checa(set(plano.constam) == {A, B}, f"constam: {plano.constam}")
    checa(set(plano.nao_constam) == {C, D}, f"não constam: {plano.nao_constam}")
    checa(plano.sem_resposta == 0, f"sem resposta: {plano.sem_resposta}")
    checa(plano.fora_da_base == 1, f"fora da base: {plano.fora_da_base}")
    print("  ok     completa: quem é da base e não está na lista NÃO consta")


def teste_lista_parcial_nao_responde_por_quem_nao_esta_nela():
    """A dúvida nunca vira resposta. Sem a declaração de que a lista é o rol
    inteiro, quem não aparece nela continua sem resposta — e "fora do rol" é
    resposta, com consequência."""
    lido = substituidos.ler_arquivo(planilha(A, B), "rol.csv")
    plano = substituidos.planejar(lido, {A, B, C, D}, acao="GIFA-2006",
                                  completo=False)
    checa(set(plano.constam) == {A, B}, f"constam: {plano.constam}")
    checa(plano.nao_constam == (), f"parcial e afirmou: {plano.nao_constam}")
    checa(plano.sem_resposta == 2, f"sem resposta: {plano.sem_resposta}")
    print("  ok     parcial: quem não está na lista fica SEM resposta")


def teste_lista_completa_com_linha_ilegivel_nao_poe_ninguem_fora():
    """CPF que começa com zero, guardado no Excel como NÚMERO, perde o zero
    e chega com dez dígitos — cerca de um em cada dez. Essa linha não é
    reconhecida, e a pessoa dela, que ESTÁ no rol, apareceria como fora dele.

    Então "completa" só vale quando a lista inteira foi lida. Com uma linha
    ilegível que seja, qualquer ausente pode ser ela: ninguém é dado como
    fora, e o plano diz por quê.
    """
    sem_o_zero = A.lstrip("0")
    checa(len(sem_o_zero) < 11, "o CPF de teste devia começar com zero")
    lido = substituidos.ler_arquivo(planilha(sem_o_zero, B), "rol.csv")
    checa(lido.invalidas == 1 and lido.cpfs == frozenset({B}), f"{lido}")
    plano = substituidos.planejar(lido, {A, B, C}, acao="GIFA-2006",
                                  completo=True)
    checa(plano.nao_constam == (),
          f"A está no rol (sem o zero) e foi dada como FORA: {plano.nao_constam}")
    checa(plano.sem_resposta == 2 and plano.completo is False
          and plano.declarado_completo is True, f"{plano}")
    # Sem linha ilegível, a mesma declaração vale.
    limpo = substituidos.planejar(
        substituidos.ler_arquivo(planilha(B), "rol.csv"), {A, B, C},
        acao="GIFA-2006", completo=True)
    checa(limpo.completo is True and set(limpo.nao_constam) == {A, C},
          f"{limpo}")
    print("  ok     completa com linha ilegível: ninguém é dado como fora")


# --------------------------------------------------------- gravar e responder

def teste_a_resposta_e_por_pessoa_e_por_acao():
    secao("gravar e responder")
    pasta = pasta_nova()
    enviar(pasta, "GIFA-2006", [A, B], {A, B, C}, completo=True)
    enviar(pasta, "OUTRA-2010", [C], {A, B, C}, completo=False)
    por = substituidos.por_cpf(pasta)
    checa(dict(por[A]) == {"GIFA-2006": True}, f"A: {por.get(A)}")
    checa(dict(por[C]) == {"GIFA-2006": False, "OUTRA-2010": True},
          f"C: {por.get(C)}")
    checa(substituidos.de_cpf(pasta, pontuado(B)) == (("GIFA-2006", True),),
          f"de_cpf com CPF pontuado: {substituidos.de_cpf(pasta, pontuado(B))}")
    checa(substituidos.de_cpf(pasta, D) == (), "quem não foi comparado tem resposta")
    print("  ok     cada pessoa: a resposta de cada ação em que foi comparada")


def teste_quem_entrou_na_base_depois_nao_tem_resposta():
    """D não estava na base quando o rol COMPLETO foi enviado. Ele nunca foi
    comparado com o rol: dizer "fora" seria inventar, e o motor devolveria
    NAO_PODE para alguém que pode estar na lista."""
    pasta = pasta_nova()
    enviar(pasta, "GIFA-2006", [A], {A, B}, completo=True)
    checa(substituidos.de_cpf(pasta, D) == (),
          f"respondeu por quem não estava na base: "
          f"{substituidos.de_cpf(pasta, D)}")
    resumo = substituidos.resumo(pasta, {A, B, D})["GIFA-2006"]
    checa((resumo["constam"], resumo["nao_constam"], resumo["sem_resposta"])
          == (1, 1, 1), f"resumo: {resumo}")
    print("  ok     entrou depois do envio: sem resposta, e o resumo conta")


def teste_cpf_de_fora_da_base_nao_fica_guardado():
    """O rol de uma coletiva traz gente que saiu do sindicato, que morreu,
    que nunca foi desta base. Guardar o CPF delas seria guardar dado de quem
    a entidade não declarou atender."""
    pasta = pasta_nova()
    enviar(pasta, "GIFA-2006", [A, E], {A, B}, completo=True)
    bruto = (pasta / substituidos.ARQUIVO).read_text(encoding="utf-8")
    checa(E not in bruto, "o CPF de quem não é da base ficou no arquivo")
    checa(A in bruto and B in bruto, "quem é da base não foi guardado")
    registro = json.loads(bruto.splitlines()[-1])
    checa(registro["fora_da_base"] == 1, f"a contagem: {registro}")
    print("  ok     fora da base: contado, não guardado")


def teste_o_envio_novo_substitui_o_da_mesma_acao():
    pasta = pasta_nova()
    enviar(pasta, "GIFA-2006", [A], {A, B}, completo=True)
    enviar(pasta, "OUTRA-2010", [A], {A, B}, completo=True)
    enviar(pasta, "GIFA-2006", [B], {A, B}, completo=False)
    por = substituidos.por_cpf(pasta)
    checa(dict(por[B]) == {"GIFA-2006": True, "OUTRA-2010": False},
          f"B: {por.get(B)}")
    checa(dict(por[A]) == {"OUTRA-2010": True},
          f"A ficou com a resposta do envio ANTERIOR da GIFA: {por.get(A)}")
    print("  ok     reenvio: vale o último daquela ação, e só dela")


def teste_retirar_desfaz_o_envio():
    """Arquivo errado, ou enviado para a ação errada: tem de dar para
    desfazer sem enviar outro por cima."""
    pasta = pasta_nova()
    enviar(pasta, "GIFA-2006", [A], {A, B}, completo=True)
    checa(substituidos.retirar(pasta, "GIFA-2006", quem="m") is True,
          "não retirou")
    checa(substituidos.por_cpf(pasta) == {}, f"{substituidos.por_cpf(pasta)}")
    checa(substituidos.retirar(pasta, "GIFA-2006", quem="m") is False,
          "retirou duas vezes")
    checa("GIFA-2006" not in substituidos.resumo(pasta, {A, B}),
          "o resumo ainda mostra o rol retirado")
    print("  ok     retirar: a resposta some, e não se retira duas vezes")


def teste_linha_ilegivel_nao_derruba_a_leitura():
    pasta = pasta_nova()
    enviar(pasta, "GIFA-2006", [A], {A, B}, completo=True)
    with (pasta / substituidos.ARQUIVO).open("a", encoding="utf-8") as f:
        f.write("{isto não é json\n")
    checa(dict(substituidos.por_cpf(pasta)[A]) == {"GIFA-2006": True},
          "uma linha quebrada apagou as respostas")
    print("  ok     linha ilegível é pulada")


# ------------------------------------------------------------ o apagamento

def teste_quem_pede_para_sair_sai_do_rol_guardado():
    """O arquivo guarda o CPF dela e uma afirmação sobre ela. Sai de TODAS as
    linhas, inclusive das de envios já substituídos — e os outros ficam."""
    secao("o apagamento")
    pasta = pasta_nova()
    enviar(pasta, "GIFA-2006", [A, B], {A, B, C}, completo=True)
    enviar(pasta, "GIFA-2006", [B], {A, B, C}, completo=True)
    with (pasta / substituidos.ARQUIVO).open("a", encoding="utf-8") as f:
        f.write("{isto não é json\n")
    saiu = substituidos.remover_pessoa(pasta, pontuado(A))
    bruto = (pasta / substituidos.ARQUIVO).read_text(encoding="utf-8")
    checa(saiu == 2, f"A estava em 2 linhas, saiu de {saiu}")
    checa(A not in bruto, "o CPF de quem pediu para sair continua no arquivo")
    checa("{isto não é json" in bruto, "a linha ilegível foi descartada")
    por = substituidos.por_cpf(pasta)
    checa(A not in por, f"A ainda tem resposta: {por.get(A)}")
    checa(dict(por[B]) == {"GIFA-2006": True}
          and dict(por[C]) == {"GIFA-2006": False},
          f"os outros mudaram: {por}")
    checa(substituidos.remover_pessoa(pasta, A) == 0, "removeu duas vezes")
    print("  ok     sai de todas as linhas; os outros ficam como estavam")


TESTES.extend([
    teste_planilha_com_coluna_de_cpf,
    teste_planilha_sem_coluna_de_cpf_e_recusada,
    teste_pdf_com_texto,
    teste_pdf_sem_texto_e_recusado,
    teste_arquivo_sem_nenhum_cpf_valido_e_recusado,
    teste_lista_completa_responde_por_quem_nao_esta_nela,
    teste_lista_parcial_nao_responde_por_quem_nao_esta_nela,
    teste_lista_completa_com_linha_ilegivel_nao_poe_ninguem_fora,
    teste_a_resposta_e_por_pessoa_e_por_acao,
    teste_quem_entrou_na_base_depois_nao_tem_resposta,
    teste_cpf_de_fora_da_base_nao_fica_guardado,
    teste_o_envio_novo_substitui_o_da_mesma_acao,
    teste_retirar_desfaz_o_envio,
    teste_linha_ilegivel_nao_derruba_a_leitura,
    teste_quem_pede_para_sair_sai_do_rol_guardado,
])


def main() -> int:
    print("=" * 70)
    print("ROL DE SUBSTITUÍDOS — a porta por onde ele entra")
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
