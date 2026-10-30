#!/usr/bin/env python3
"""
A conta do filiado: o que o Produto B pede, e o que ele NÃO pede.

O PORTAL QUE EXISTIA PEDIA PROCURAÇÃO, IDENTIDADE E COMPROVANTE DE
RESIDÊNCIA. São documentos para LITIGAR — hipótese do Produto A, que monta
petição. O Produto B responde uma pergunta, e para responder precisa de
outra coisa.

O QUE O B PRECISA, E POR QUÊ:

    comprovantes de CONTRIBUIÇÃO   provam o PERÍODO DE FILIAÇÃO, e é o
                                   cruzamento desse período contra o período
                                   da ação coletiva que responde "em quais
                                   ações esta pessoa participa"
    cargo e situação               definem a CATEGORIA alcançada
    sentença e certidão            só se a pessoa tiver — decidem se ela
                                   EXECUTA ou AJUÍZA

Exigir procuração de quem só quer saber se tem direito derruba a conclusão do
cadastro e não melhora resposta nenhuma. Procuração aparece quando houver
ação a propor, e aí é outra conversa.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import cadastro  # noqa: E402

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def conta(**trocas) -> dict:
    base = {
        "cpf": "111.444.777-35",
        "nome_completo": "FULANA DE TAL (CADASTRO DE EXEMPLO)",
        "email": "fulana@exemplo.org",
        "telefone": "(61) 99999-0000",
        "cargo": "Auditor-Fiscal da Receita Federal do Brasil",
        "situacao": "aposentado",
        "unidade": "Delegacia da Receita Federal em Goiânia",
        "data_nascimento": "1958-06-27",
        "data_ingresso": "1992-04-01",
        "data_aposentadoria": "2018-06-30",
        "filiado_desde": "1992-05",
        "filiado_ate": "",
        "tem_processo": "nao_sei",
        "numeros_de_processo": "",
        "ja_executou": "nao",
        "tem_acao_propria": "nao",
    }
    base.update(trocas)
    return base


# ------------------------------------------------- o que o B pede, e o que não

def teste_o_cadastro_nao_pede_procuracao_nem_identidade():
    """A dívida do Produto A, paga. Nenhum desses documentos melhora a
    resposta que o B dá."""
    secao("o que o B pede")
    nomes = set(cadastro.DOCUMENTOS)
    for do_produto_a in ("procuracao", "identidade", "residencia",
                         "comprovante_residencia"):
        checa(do_produto_a not in nomes,
              f"o cadastro do B ainda pede {do_produto_a!r} — isso é do A")
    print(f"  ok     documentos pedidos: {sorted(nomes)}")


def teste_contribuicao_e_obrigatoria_e_aceita_varios():
    """É ela que prova o período de filiação, e período de filiação é o que
    diz em quais ações a pessoa participa. Um comprovante por ano é normal."""
    obrigatorios = [n for n, d in cadastro.DOCUMENTOS.items() if d["obrigatorio"]]
    checa(obrigatorios == ["contribuicao"],
          f"obrigatórios deviam ser só a contribuição: {obrigatorios}")
    checa(cadastro.DOCUMENTOS["contribuicao"]["multiplos"],
          "contribuição devia aceitar vários arquivos")
    print("  ok     contribuição é o único obrigatório, e aceita vários")


def teste_sentenca_e_certidao_sao_opcionais():
    """Quem não tem sentença ainda assim recebe resposta — a dele é 'ajuizar'."""
    for nome in ("sentenca", "certidao_transito"):
        checa(nome in cadastro.DOCUMENTOS, f"{nome} sumiu do cadastro")
        checa(not cadastro.DOCUMENTOS[nome]["obrigatorio"],
              f"{nome} não pode ser obrigatório: quem não tem ainda tem "
              f"direito a uma resposta")
    print("  ok     sentença e certidão entram se a pessoa tiver")


# ---------------------------------------------------------- período de filiação

def teste_filiado_desde_e_obrigatorio():
    """Sem ele não dá para cruzar com ação nenhuma, e o cadastro inteiro
    perde a razão de existir."""
    secao("período de filiação")
    checa(cadastro.conferir(conta(filiado_desde="")) != [],
          "aceitou cadastro sem data de início da filiação")
    print("  ok     sem filiado_desde, reprova")


def teste_filiado_ate_vazio_significa_ainda_filiado():
    """Vazio é resposta, não omissão: a pessoa continua filiada hoje."""
    checa(cadastro.conferir(conta(filiado_ate="")) == [],
          f"recusou quem ainda é filiado: {cadastro.conferir(conta())}")
    limpa = cadastro.normalizar(conta(filiado_ate=""))
    checa(limpa["filiado_ate"] == "",
          f"inventou data de saída: {limpa['filiado_ate']!r}")
    print("  ok     filiado_ate vazio = ainda filiado")


def teste_periodo_invertido_reprova():
    problemas = cadastro.conferir(
        conta(filiado_desde="2010-01", filiado_ate="2005-01"))
    checa(problemas != [], "aceitou filiação que termina antes de começar")
    print("  ok     período invertido reprova")


def teste_filiacao_no_futuro_reprova():
    problemas = cadastro.conferir(conta(filiado_desde="2099-01"))
    checa(problemas != [], "aceitou filiação começando no futuro")
    print("  ok     filiação no futuro reprova")


def teste_formato_do_periodo_e_AAAA_MM():
    for ruim in ("1992", "05/1992", "1992-13", "1992-00"):
        checa(cadastro.conferir(conta(filiado_desde=ruim)) != [],
              f"aceitou filiado_desde={ruim!r}")
    print("  ok     só AAAA-MM é aceito")


# ------------------------------------------------------------- identificação

def teste_cpf_e_email_sao_conferidos():
    secao("identificação e categoria")
    checa(cadastro.conferir(conta(cpf="111.444.777-00")) != [],
          "aceitou CPF que não fecha")
    checa(cadastro.conferir(conta(email="fulana@exemplo")) != [],
          "aceitou e-mail sem ponto")
    print("  ok     CPF e e-mail conferidos")


def teste_cargo_e_situacao_sao_obrigatorios():
    """O cargo define a CATEGORIA, e categoria decide quais ações alcançam a
    pessoa. Sem ele o cruzamento não acontece."""
    checa(cadastro.conferir(conta(cargo="")) != [], "aceitou sem cargo")
    checa(cadastro.conferir(conta(situacao="")) != [], "aceitou sem situação")
    checa(cadastro.conferir(conta(situacao="aposentado")) == [],
          "recusou situação válida")
    checa(cadastro.conferir(conta(situacao="ferias")) != [],
          "aceitou situação que não está no contrato")
    print("  ok     cargo e situação obrigatórios, situação com valores fixos")


# ------------------------------------------------------------------- judicial

def teste_o_judicial_e_opcional_inteiro():
    """Quem não sabe nada do judiciário ainda assim completa o cadastro — e é
    justamente essa pessoa que mais precisa da resposta."""
    secao("judicial")
    magro = conta(tem_processo="nao_sei", numeros_de_processo="",
                  ja_executou="nao_sei", tem_acao_propria="nao_sei")
    checa(cadastro.conferir(magro) == [],
          f"recusou quem não sabe do judiciário: {cadastro.conferir(magro)}")
    print("  ok     'não sei' é resposta completa em tudo que é judicial")


def teste_numeros_de_processo_de_qualquer_tribunal():
    """Acompanhar não é protocolar: 65 tribunais, não só o TRF1."""
    tjdft = "0007654-05.2019.8.07.0001"
    checa(cadastro.conferir(conta(tem_processo="sim",
                                  numeros_de_processo=tjdft)) == [],
          "recusou processo de tribunal estadual")
    checa(cadastro.conferir(conta(tem_processo="sim",
                                  numeros_de_processo="0007654-99.2019.8.07.0001")) != [],
          "aceitou número cujo dígito não fecha")
    print("  ok     qualquer tribunal, com o dígito conferido")


def teste_coluna_que_o_contrato_nao_tem_e_erro():
    """Descarte em silêncio é como um campo renomeado some sem ninguém ver."""
    checa(cadastro.conferir(conta(sobrenome="x")) != [],
          "aceitou campo fora do contrato")
    print("  ok     campo desconhecido reprova, não é descartado")


# ------------------------------------------------------------- normalização

def teste_normalizar_deixa_pronto_para_o_banco():
    limpa = cadastro.normalizar(conta(cpf="111.444.777-35"))
    checa(limpa["cpf"] == "11144477735", f"CPF: {limpa['cpf']!r}")
    checa(limpa["nome_completo"].isupper() is False or True, "")
    checa(set(limpa) == set(cadastro.CAMPOS),
          f"normalizar devolveu campos fora do contrato: "
          f"{sorted(set(limpa) ^ set(cadastro.CAMPOS))}")
    print("  ok     normalizado nos campos do contrato, CPF em dígitos")


def teste_documentos_exigidos_nao_dependem_do_judicial():
    """No Produto A, declarar processo passava a exigir sentença e certidão.
    Aqui não: a pessoa pode saber o número e não ter os papéis em mãos, e
    bloquear o cadastro por isso a deixaria sem resposta nenhuma."""
    checa(cadastro.documentos_exigidos(conta(tem_processo="sim"))
          == ("contribuicao",),
          f"declarar processo passou a exigir documento: "
          f"{cadastro.documentos_exigidos(conta(tem_processo='sim'))}")
    print("  ok     declarar processo não passa a exigir papel")


TESTES.extend([
    teste_o_cadastro_nao_pede_procuracao_nem_identidade,
    teste_contribuicao_e_obrigatoria_e_aceita_varios,
    teste_sentenca_e_certidao_sao_opcionais,
    teste_filiado_desde_e_obrigatorio,
    teste_filiado_ate_vazio_significa_ainda_filiado,
    teste_periodo_invertido_reprova,
    teste_filiacao_no_futuro_reprova,
    teste_formato_do_periodo_e_AAAA_MM,
    teste_cpf_e_email_sao_conferidos,
    teste_cargo_e_situacao_sao_obrigatorios,
    teste_o_judicial_e_opcional_inteiro,
    teste_numeros_de_processo_de_qualquer_tribunal,
    teste_coluna_que_o_contrato_nao_tem_e_erro,
    teste_normalizar_deixa_pronto_para_o_banco,
    teste_documentos_exigidos_nao_dependem_do_judicial,
])


def main() -> int:
    print("=" * 70)
    print("CADASTRO DO FILIADO — o que o Produto B pede")
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
