#!/usr/bin/env python3
"""
A ingestão do acervo do sindicato: a planilha como ela vem.

POR QUE ESTA SUÍTE EXISTE, E CONTRA O QUE

Contra a tentação de recusar a planilha. O sindicato não tem um cadastro
limpo — tem exportação de folha, lista de secretaria, sistema antigo e
planilha que alguém juntou à mão. Se a ingestão exigir arquivo bonito, não
ingere nada, e a primeira entrega do produto não acontece.

E contra o oposto: engolir e descartar em silêncio. Linha ruim é o PRODUTO —
é ela que o gerente precisa ver. "Não consigo falar com 1.930 dos meus 4.812
filiados" é a informação que ele não tem hoje, e ela só existe se a linha sem
e-mail aparecer em vez de sumir.

As duas armadilhas são de encoding e de repetição, e as duas já morderam este
projeto: `rol.py` aprendeu o BOM na mão (cabeçalho vinha "﻿cpf", não
casava com "cpf", e o rol inteiro ficava vazio), e `elegibilidade.py` aprendeu
que planilha de entidade repete pessoa.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import acervo  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures"
SUJO = FIXTURES / "acervo_sujo.csv"
LATIN1 = FIXTURES / "acervo_latin1.csv"
SEM_CPF = FIXTURES / "acervo_sem_cpf.csv"
CPF_DUPLO = FIXTURES / "acervo_cpf_duplo.csv"

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


# ------------------------------------------------------------------ encoding

def teste_le_planilha_de_excel_brasileiro():
    """BOM e separador ';'. Encoding errado não dá erro: deixa o acervo vazio
    ou o cabeçalho ilegível, e aí alguém conclui que o sindicato não tem
    dados. Foi o que `rol.py` aprendeu na mão."""
    secao("encoding e separador")
    pessoas, problemas = acervo.ler(SUJO)
    checa(problemas == [], f"recusou planilha legítima: {problemas}")
    checa(len(pessoas) == 6, f"leu {len(pessoas)} pessoas, esperava 6")
    print("  ok     BOM e separador ';' — 6 linhas lidas")


def teste_le_exportacao_em_latin1():
    """Sistema antigo exporta em latin-1, e o acento é o que estoura."""
    pessoas, problemas = acervo.ler(LATIN1)
    checa(problemas == [], f"recusou latin-1: {problemas}")
    checa(len(pessoas) == 2, f"leu {len(pessoas)}, esperava 2")
    nomes = " ".join(p.campos.get("nome_completo", "") for p in pessoas)
    checa("JOSÉ" in nomes and "CONCEIÇÃO" in nomes,
          f"os acentos não sobreviveram: {nomes!r}")
    print("  ok     latin-1 com acento, lido sem perder letra")


def teste_arquivo_sem_coluna_de_cpf_reprova_alto():
    """Sem CPF não há como identificar ninguém. Falhar fechado, e em voz alta:
    aceitar e devolver zero pessoa pareceria 'o sindicato não tem base'."""
    pessoas, problemas = acervo.ler(SEM_CPF)
    checa(problemas != [], "aceitou arquivo sem coluna de CPF")
    checa(pessoas == [], f"devolveu pessoas de um arquivo sem CPF: {pessoas}")
    checa(any("cpf" in p.lower() for p in problemas),
          f"o problema não diz que falta a coluna de CPF: {problemas}")
    print("  ok     sem coluna de CPF, reprova e diz por quê")


# -------------------------------------------------------------- cabeçalhos

def teste_reconhece_cabecalho_com_outro_nome():
    """'CPF/CNPJ', 'E-MAIL', 'Nome Completo', 'matricula_siape'. A secretaria
    do sindicato não usa os nomes do nosso contrato, e não tem por que usar."""
    secao("cabeçalhos")
    pessoas, _ = acervo.ler(SUJO)
    primeira = pessoas[0]
    for coluna, esperado in (
        ("nome_completo", "MARIA DE EXEMPLO (CADASTRO FICTICIO)"),
        ("email", "maria@exemplo.org"),
        ("matricula", "1001"),
        ("cargo", "Auditor-Fiscal"),
        ("data_nascimento", "1960-05-02"),
    ):
        checa(primeira.campos.get(coluna) == esperado,
              f"{coluna} mapeou para {primeira.campos.get(coluna)!r}, "
              f"esperava {esperado!r}")
    print("  ok     sinônimos de coluna mapeados para o contrato")


def teste_coluna_desconhecida_e_preservada_nao_e_erro():
    """'Observacoes' não está no contrato. Descartar seria perder informação
    que o sindicato achou importante guardar; reprovar seria recusar a
    planilha por ela ter uma coluna a mais."""
    pessoas, problemas = acervo.ler(SUJO)
    checa(problemas == [], f"coluna a mais virou erro: {problemas}")
    joao = next(p for p in pessoas if p.cpf == "52998224725")
    checa("filiado desde 1998" in " ".join(joao.campos.values()),
          f"a coluna desconhecida foi descartada: {joao.campos}")
    print("  ok     coluna fora do contrato é preservada, não é erro")


# ------------------------------------------------------------------- achados

def teste_cpf_que_nao_fecha_entra_como_invalido_e_nao_desaparece():
    secao("achados por pessoa")
    pessoas, _ = acervo.ler(SUJO)
    ruins = [p for p in pessoas
             if any(a.coluna == "cpf" and a.estado == acervo.INVALIDO
                    for a in p.achados)]
    checa(len(ruins) == 1, f"CPF inválido sumiu ou duplicou: {len(ruins)}")
    checa(ruins and "PEDRO" in ruins[0].campos.get("nome_completo", ""),
          "não é a linha que eu sujei de propósito")
    print("  ok     CPF que não fecha entra como INVALIDO, não é descartado")


def teste_cpf_repetido_marca_as_duas_linhas():
    """Exportação concatenada, pessoa recadastrada, duas filiações.

    AS DUAS linhas são marcadas, não só a segunda — e isso é deliberado. A
    ordem de uma exportação não é informação sobre nada, então escolher "a
    primeira vale" seria sortear qual versão da verdade entra na base. É a
    mesma postura de `elegibilidade.achado_de_repeticao`, que faz TODAS as
    linhas divergentes pararem, inclusive a primeira.
    """
    pessoas, _ = acervo.ler(SUJO)
    divergentes = [p for p in pessoas
                   if any(a.estado == acervo.DIVERGENTE for a in p.achados)]
    checa(len(divergentes) == 2,
          f"esperava as DUAS linhas da Maria marcadas, marcou {len(divergentes)}")
    checa(all(p.cpf == "11144477735" for p in divergentes),
          f"marcou a pessoa errada: {[p.cpf for p in divergentes]}")
    detalhe = " ".join(a.detalhe for p in divergentes for a in p.achados
                       if a.estado == acervo.DIVERGENTE)
    checa("cargo" in detalhe,
          f"o achado não diz QUAL campo divergiu: {detalhe!r}")
    print("  ok     CPF repetido com dado diferente marca as duas linhas")


def teste_repeticao_identica_nao_e_divergencia():
    """Duas linhas iguais são uma informação só. Marcar como divergente
    mandaria o gerente decidir entre duas coisas idênticas."""
    pessoas, _ = acervo.ler(LATIN1)
    checa(not any(a.estado == acervo.DIVERGENTE
                  for p in pessoas for a in p.achados),
          "inventou divergência onde não há repetição")
    print("  ok     sem repetição, sem divergência")


def teste_sem_email_valido_a_pessoa_e_inalcancavel():
    """A manchete do painel sai daqui. `alcancavel` é CPF que fecha E e-mail
    que serve — porque o código de acesso vai para o e-mail do rol, e sem ele
    a pessoa não entra no portal nem recebe aviso."""
    secao("alcançabilidade")
    pessoas, _ = acervo.ler(SUJO)
    inalcancaveis = [p for p in pessoas if not p.alcancavel]
    checa(len(inalcancaveis) == 3,
          f"esperava 3 inalcançáveis, achou {len(inalcancaveis)}: "
          f"{[p.campos.get('nome_completo') for p in inalcancaveis]}")
    nomes = " ".join(p.campos.get("nome_completo", "") for p in inalcancaveis)
    for quem in ("ANA", "PEDRO", "CARLA"):
        checa(quem in nomes, f"{quem} devia estar inalcançável: {nomes}")
    print("  ok     e-mail sem ponto, e-mail vazio e CPF torto: 3 inalcançáveis")


def teste_campo_vazio_vira_achado_de_falta():
    pessoas, _ = acervo.ler(SUJO)
    ana = next(p for p in pessoas if p.cpf == "52601815906")
    checa(any(a.coluna == "data_nascimento" and a.estado == acervo.FALTA
              for a in ana.achados),
          f"data_nascimento vazia não gerou achado: {ana.achados}")
    print("  ok     campo exigido e vazio vira achado de FALTA")


def teste_duas_colunas_para_o_mesmo_campo_nao_se_sobrescrevem():
    """C2 — ACHADO NA REVISÃO, reproduzido.

    Exportação concatenada traz `CPF` e `CPF/CNPJ`; as duas mapeiam para
    `cpf`, e a última vencia em silêncio. Com a segunda vazia, o CPF da pessoa
    era DESTRUÍDO: ela virava "inalcançável por falta de CPF", ganhava a chave
    `linha-N` e nunca mais casava com o cadastro dela no portal.

    É exatamente a perda silenciosa que o cabeçalho deste módulo jura não
    fazer. O valor preenchido tem de vencer o vazio, e a colisão tem de
    aparecer.
    """
    secao("colisão de cabeçalho (C2)")
    pessoas, problemas = acervo.ler(CPF_DUPLO)
    checa(len(pessoas) == 1, f"leu {len(pessoas)} pessoas")
    if not pessoas:
        return
    pessoa = pessoas[0]
    checa(pessoa.cpf == "11144477735",
          f"o CPF foi destruído pela coluna vazia: {pessoa.cpf!r}")
    checa(pessoa.alcancavel,
          f"a pessoa virou inalcançável por um defeito de cabeçalho: "
          f"{pessoa.achados}")
    checa(any("CPF/CNPJ" in p or "cpf" in p.lower() for p in problemas),
          f"a colisão de cabeçalho não foi relatada: {problemas}")
    print("  ok     valor preenchido vence o vazio, e a colisão é relatada")


def teste_coluna_ausente_nao_e_o_mesmo_que_coluna_vazia():
    """I4 — a base para o painel distinguir as duas coisas."""
    pessoas, _ = acervo.ler(SUJO)
    colunas = set().union(*(p.campos.keys() for p in pessoas))
    checa("telefone" not in colunas,
          "telefone não está na planilha e não deveria aparecer em campos")
    checa("data_nascimento" in colunas,
          "data_nascimento está na planilha e deveria aparecer em campos")
    print("  ok     `campos` traz só o que a planilha trouxe")



TESTES.extend([
    teste_le_planilha_de_excel_brasileiro,
    teste_le_exportacao_em_latin1,
    teste_arquivo_sem_coluna_de_cpf_reprova_alto,
    teste_reconhece_cabecalho_com_outro_nome,
    teste_coluna_desconhecida_e_preservada_nao_e_erro,
    teste_cpf_que_nao_fecha_entra_como_invalido_e_nao_desaparece,
    teste_cpf_repetido_marca_as_duas_linhas,
    teste_repeticao_identica_nao_e_divergencia,
    teste_sem_email_valido_a_pessoa_e_inalcancavel,
    teste_campo_vazio_vira_achado_de_falta,
    teste_duas_colunas_para_o_mesmo_campo_nao_se_sobrescrevem,
    teste_coluna_ausente_nao_e_o_mesmo_que_coluna_vazia,
])


def main() -> int:
    print("=" * 70)
    print("ACERVO DO SINDICATO — a planilha como ela vem")
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
