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



# ============================================ o que decide participação (etapa 1)
#
# A AUDITORIA QUE ABRIU ESTE BLOCO: o leitor da planilha trazia cargo,
# situação, lotação e datas da carreira — e **não trazia o período de
# filiação nem os processos**. Justamente os dois que o produto usa para
# responder o que ele promete responder.
#
# O efeito prático era pior do que parece: a pessoa aposentada tinha de
# digitar, no celular, desde quando contribui e o número de 20 dígitos do
# próprio processo — informação que o sindicato já tinha na planilha que nos
# mandou.


def _planilha(tmp, cabecalho: str, *linhas: str):
    caminho = tmp / "acervo.csv"
    caminho.write_text(
        cabecalho + "\n" + "\n".join(linhas) + "\n", encoding="utf-8"
    )
    return acervo.ler(caminho)


def teste_le_o_periodo_de_filiacao_da_planilha():
    """É o campo que cruza com o período da ação. Sem ele na planilha, o
    sindicato manda 4.812 pessoas e o motor não responde por nenhuma."""
    secao("o período de filiação")
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    pessoas, problemas = _planilha(
        tmp,
        "cpf;nome;email;filiado desde;desfiliado em",
        "111.444.777-35;FULANA (EXEMPLO);f@exemplo.org;15/03/2004;",
        "529.982.247-25;BELTRANO (EXEMPLO);b@exemplo.org;01/2001;12/2009",
    )
    checa(problemas == [], f"recusou planilha legítima: {problemas}")
    campos = {p.cpf: p.campos for p in pessoas}
    checa(campos["11144477735"].get("filiado_desde") == "2004-03",
          f"filiado_desde não normalizado: "
          f"{campos['11144477735'].get('filiado_desde')!r}")
    checa(campos["11144477735"].get("filiado_ate") == "",
          "inventou data de saída para quem continua filiado")
    checa(campos["52998224725"].get("filiado_desde") == "2001-01",
          f"{campos['52998224725'].get('filiado_desde')!r}")
    checa(campos["52998224725"].get("filiado_ate") == "2009-12",
          f"{campos['52998224725'].get('filiado_ate')!r}")
    print("  ok     filiação lida e normalizada para AAAA-MM")


def teste_reconhece_os_nomes_que_a_planilha_usa_para_filiacao():
    """Nenhum sindicato escreve "filiado_desde". Cada sistema tem o seu nome,
    e um cabeçalho não reconhecido faz a coluna virar texto solto que o motor
    nunca olha."""
    import tempfile
    for cabecalho in ("data de filiacao", "filiado em", "associado desde",
                      "dt_filiacao", "inicio da contribuicao"):
        tmp = Path(tempfile.mkdtemp())
        pessoas, _ = _planilha(
            tmp, f"cpf;email;{cabecalho}",
            "111.444.777-35;f@exemplo.org;03/2004",
        )
        achado = pessoas[0].campos.get("filiado_desde", "")
        checa(achado == "2004-03",
              f"o cabeçalho {cabecalho!r} não virou filiado_desde: {achado!r}")
    print("  ok     cinco grafias de cabeçalho reconhecidas")


def teste_data_que_nao_da_para_ler_vira_achado_nao_silencio():
    """DESCARTAR EM SILÊNCIO É O PIOR CAMINHO. A pessoa perderia a
    participação dela por causa de uma célula que o Excel formatou torto, e
    ninguém saberia por quê."""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    pessoas, _ = _planilha(
        tmp, "cpf;email;filiado desde",
        "111.444.777-35;f@exemplo.org;sei la quando",
    )
    p = pessoas[0]
    checa(p.campos.get("filiado_desde") == "",
          f"aceitou lixo como data: {p.campos.get('filiado_desde')!r}")
    invalidos = [a for a in p.achados
                 if a.coluna == "filiado_desde" and a.estado == acervo.INVALIDO]
    checa(bool(invalidos),
          f"a data ilegível sumiu sem achado: {p.achados}")
    checa("sei la quando" in invalidos[0].detalhe,
          f"o achado não mostra o que veio: {invalidos[0].detalhe!r}")
    print("  ok     data ilegível vira achado, com o valor original")


def teste_data_no_futuro_e_recusada():
    """Filiação em 2041 é erro de digitação ou ano de dois dígitos lido
    errado. Aceitar poria a pessoa fora de toda ação."""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    pessoas, _ = _planilha(
        tmp, "cpf;email;filiado desde",
        "111.444.777-35;f@exemplo.org;15/03/2099",
    )
    checa(pessoas[0].campos.get("filiado_desde") == "",
          "aceitou filiação no futuro")
    checa(any(a.coluna == "filiado_desde" for a in pessoas[0].achados),
          "a data futura sumiu sem achado")
    print("  ok     data no futuro é recusada, com achado")


def teste_le_os_processos_da_planilha():
    """O sindicato costuma ter o número. Hoje a pessoa aposentada tem de
    achar 20 dígitos numa papelada e digitar no celular."""
    secao("os processos")
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    pessoas, problemas = _planilha(
        tmp, "cpf;email;numero do processo",
        "111.444.777-35;f@exemplo.org;0010391-24.2006.4.01.3400",
        "529.982.247-25;b@exemplo.org;"
        "0010391-24.2006.4.01.3400 / 0007654-05.2019.8.07.0001",
    )
    checa(problemas == [], f"{problemas}")
    campos = {p.cpf: p.campos for p in pessoas}
    checa(campos["11144477735"].get("numeros_de_processo")
          == "00103912420064013400",
          f"{campos['11144477735'].get('numeros_de_processo')!r}")
    # Dois numa célula é o caso normal: separador pode ser barra, vírgula,
    # ponto e vírgula ou quebra de linha, e a planilha não avisa qual.
    checa(campos["52998224725"].get("numeros_de_processo")
          == "00103912420064013400;00076540520198070001",
          f"{campos['52998224725'].get('numeros_de_processo')!r}")
    print("  ok     processos lidos, inclusive vários numa célula")


def teste_numero_de_processo_que_nao_fecha_vira_achado():
    """Dígito verificador que não bate é erro de digitação. Acompanhar um
    número errado é gastar consulta e devolver silêncio à pessoa."""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    pessoas, _ = _planilha(
        tmp, "cpf;email;processo",
        "111.444.777-35;f@exemplo.org;0010391-99.2006.4.01.3400",
    )
    p = pessoas[0]
    checa(p.campos.get("numeros_de_processo") == "",
          f"aceitou número que não fecha: "
          f"{p.campos.get('numeros_de_processo')!r}")
    checa(any(a.coluna == "numeros_de_processo" for a in p.achados),
          f"o número errado sumiu sem achado: {p.achados}")
    print("  ok     número que não fecha vira achado, não acompanhamento")


def teste_planilha_sem_filiacao_continua_sendo_lida():
    """FAIL-OPEN NA INGESTÃO. Exigir a coluna faria a primeira entrega não
    acontecer — e o produto já sabe dizer que falta: a pendência aparece
    nominal, com dono."""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    pessoas, problemas = _planilha(
        tmp, "cpf;nome;email",
        "111.444.777-35;FULANA (EXEMPLO);f@exemplo.org",
    )
    checa(problemas == [], f"recusou planilha sem filiação: {problemas}")
    checa(len(pessoas) == 1, "perdeu a linha")
    checa(pessoas[0].alcancavel, "marcou como inalcançável sem motivo")
    print("  ok     planilha sem filiação entra, e a falta aparece depois")


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
    teste_le_o_periodo_de_filiacao_da_planilha,
    teste_reconhece_os_nomes_que_a_planilha_usa_para_filiacao,
    teste_data_que_nao_da_para_ler_vira_achado_nao_silencio,
    teste_data_no_futuro_e_recusada,
    teste_le_os_processos_da_planilha,
    teste_numero_de_processo_que_nao_fecha_vira_achado,
    teste_planilha_sem_filiacao_continua_sendo_lida,
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
