#!/usr/bin/env python3
"""
O encaminhamento do filiado ao escritório que o sindicato contratou.

Sindicatos terceirizam o jurídico: quem recebe o documento e propõe a ação é
um escritório contratado, e o que o sindicato faz é a TRIAGEM — dizer para
qual escritório vai aquela pessoa, com aquela demanda. Hoje isso corre por
e-mail e WhatsApp: o sindicato não sabe o que o escritório recebeu, e o
filiado não sabe com quem o caso dele está.

O QUE ESTES TESTES FIXAM:

1. O cadastro de escritórios é da entidade, e arquivo torto é "nenhum
   escritório" — ninguém entra por um cadastro que não se conseguiu ler.
2. Só se encaminha quem é da base, a um escritório que existe, por uma ação.
3. O escritório vê SÓ quem foi encaminhado a ele. Reencaminhado a outro,
   o primeiro deixa de ver.
4. Só o escritório dono do caso muda a situação; "falta documento" diz QUAL,
   de uma lista fechada — texto livre sobre uma pessoa não circula.
5. O sindicato vê, por escritório, quantos estão em cada situação e quantos
   estão PARADOS: encaminhados e não recebidos há mais de sete dias.
6. Quem pede para sair sai de todas as linhas.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import escritorios as esc  # noqa: E402

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def cpf(base: int) -> str:
    nove = f"000009{base:03d}"
    d = [int(c) for c in nove]
    for corte in (9, 10):
        soma = sum(d[i] * (corte + 1 - i) for i in range(corte))
        d.append((soma * 10) % 11 % 10)
    return "".join(str(x) for x in d)


A, B, C = (cpf(n) for n in (100, 101, 102))
ADV_1, ADV_2 = cpf(801), cpf(802)

CADASTRO = {"escritorios": [
    {"id": "exemplo-a", "nome": "Escritório de Exemplo A (fictício)",
     "contato": "contato@exemplo-a.invalid", "acoes": ["ACAO-1"],
     "pessoas": [{"cpf": ADV_1, "email": "um@exemplo-a.invalid"}]},
    {"id": "exemplo-b", "nome": "Escritório de Exemplo B (fictício)",
     "contato": "", "acoes": ["ACAO-2"],
     "pessoas": [{"cpf": ADV_2, "email": "dois@exemplo-b.invalid"}]},
]}


def pasta_nova(cadastro=CADASTRO) -> pathlib.Path:
    pasta = pathlib.Path(tempfile.mkdtemp(prefix="esc-"))
    if cadastro is not None:
        (pasta / esc.CADASTRO).write_text(
            json.dumps(cadastro, ensure_ascii=False), encoding="utf-8")
    return pasta


def encaminhar(pasta, cpfs, acao="ACAO-1", escritorio="exemplo-a",
               base=(A, B, C), quando=None):
    return esc.encaminhar(pasta, set(cpfs), acao=acao, escritorio=escritorio,
                          base_de=lambda: set(base), quem="gestor-de-teste",
                          quando=quando)


def _recusa(fazer) -> str:
    try:
        fazer()
    except esc.Recusado as e:
        return str(e) or "recusou"
    return ""


# ---------------------------------------------------------------- o cadastro

def teste_o_cadastro_diz_quem_e_de_qual_escritorio():
    secao("o cadastro de escritórios")
    pasta = pasta_nova()
    lista = esc.cadastrados(pasta)
    checa([e.id for e in lista] == ["exemplo-a", "exemplo-b"], f"{lista}")
    checa(esc.email_de(pasta, ADV_1) == "um@exemplo-a.invalid",
          "o e-mail de quem é do escritório não saiu do cadastro")
    checa(esc.email_de(pasta, A) is None, "inventou e-mail para um filiado")
    checa(esc.de_quem(pasta, ADV_2).id == "exemplo-b"
          and esc.de_quem(pasta, A) is None,
          "não sabe de qual escritório a pessoa é")
    checa(esc.responsavel_por(pasta, "ACAO-2").id == "exemplo-b"
          and esc.responsavel_por(pasta, "OUTRA") is None,
          "não sabe qual escritório cuida de cada ação")
    print("  ok     quem é de qual escritório, e qual cuida de cada ação")


def teste_cadastro_torto_e_nenhum_escritorio():
    """FALHA FECHADA: por um cadastro que não se leu, ninguém entra."""
    for torto in (None, "isto não é json", {"escritorios": "x"},
                  {"escritorios": [{"id": "../x", "nome": "N", "pessoas": []}]},
                  {"escritorios": [{"id": "ok", "nome": "", "pessoas": []}]}):
        pasta = pasta_nova(None)
        if torto is not None:
            (pasta / esc.CADASTRO).write_text(
                torto if isinstance(torto, str) else json.dumps(torto),
                encoding="utf-8")
        checa(esc.cadastrados(pasta) == (), f"aceitou cadastro torto: {torto}")
        checa(esc.email_de(pasta, ADV_1) is None, "abriu a porta sem cadastro")
    # A MESMA PESSOA EM DOIS ESCRITÓRIOS não se resolve sozinha: ela veria
    # os casos de qual? O cadastro inteiro é recusado.
    dois = json.loads(json.dumps(CADASTRO))
    dois["escritorios"][1]["pessoas"].append({"cpf": ADV_1, "email": "x@y.invalid"})
    checa(esc.cadastrados(pasta_nova(dois)) == (),
          "aceitou a mesma pessoa em dois escritórios")
    print("  ok     arquivo ausente, ilegível ou ambíguo: nenhum escritório")


# ------------------------------------------------------------- encaminhar

def teste_so_se_encaminha_quem_e_da_base_a_escritorio_que_existe():
    secao("a triagem")
    pasta = pasta_nova()
    plano = encaminhar(pasta, [A, B, cpf(555)])
    checa((plano.encaminhados, plano.fora_da_base) == (2, 1), f"{plano}")
    bruto = (pasta / esc.ARQUIVO).read_text(encoding="utf-8")
    checa(cpf(555) not in bruto, "guardou quem não é da base")
    checa("escritório" in _recusa(
        lambda: encaminhar(pasta, [A], escritorio="nao-existe")).lower(),
        "encaminhou a um escritório que não existe")
    checa(_recusa(lambda: encaminhar(pasta, [A], acao="")) != "",
          "encaminhou sem dizer por qual ação")
    print("  ok     só a base, só a escritório cadastrado, sempre por uma ação")


def teste_encaminhar_de_novo_nao_duplica_nem_apaga_a_situacao():
    pasta = pasta_nova()
    encaminhar(pasta, [A])
    esc.situar(pasta, A, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.RECEBIDO, quem="adv")
    plano = encaminhar(pasta, [A, B])
    checa((plano.encaminhados, plano.ja_estavam) == (1, 1), f"{plano}")
    caso = {c.cpf: c for c in esc.casos_de(pasta, "exemplo-a")}
    checa(caso[A].situacao == esc.RECEBIDO,
          "reencaminhar ao MESMO escritório apagou o que ele já tinha marcado")
    print("  ok     quem já estava com o escritório continua como estava")


def teste_o_escritorio_ve_so_o_que_e_dele():
    secao("o que cada escritório vê")
    pasta = pasta_nova()
    encaminhar(pasta, [A, B])
    encaminhar(pasta, [C], acao="ACAO-2", escritorio="exemplo-b")
    checa(sorted(c.cpf for c in esc.casos_de(pasta, "exemplo-a")) == [A, B]
          and [c.cpf for c in esc.casos_de(pasta, "exemplo-b")] == [C],
          "um escritório vê caso do outro")
    # REENCAMINHADO: A sai de um e vai para o outro, começando do zero.
    esc.situar(pasta, A, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.COMPLETO, quem="adv")
    encaminhar(pasta, [A], escritorio="exemplo-b")
    checa(A not in [c.cpf for c in esc.casos_de(pasta, "exemplo-a")],
          "o escritório antigo continua vendo quem foi reencaminhado")
    novo = [c for c in esc.casos_de(pasta, "exemplo-b") if c.cpf == A]
    checa(len(novo) == 1 and novo[0].situacao == esc.ENCAMINHADO,
          f"no escritório novo o caso devia começar do zero: {novo}")
    checa(esc.tem_caso(pasta, "exemplo-b", A)
          and not esc.tem_caso(pasta, "exemplo-a", A),
          "tem_caso não acompanha o reencaminhamento")
    print("  ok     cada um vê os seus; reencaminhado muda de mãos")


# ------------------------------------------------------------- a situação

def teste_so_o_escritorio_dono_muda_a_situacao():
    secao("a situação do caso")
    pasta = pasta_nova()
    encaminhar(pasta, [A])
    checa(_recusa(lambda: esc.situar(
        pasta, A, "ACAO-1", escritorio="exemplo-b", situacao=esc.RECEBIDO,
        quem="adv")) != "", "o escritório B marcou um caso do A")
    checa(_recusa(lambda: esc.situar(
        pasta, B, "ACAO-1", escritorio="exemplo-a", situacao=esc.RECEBIDO,
        quem="adv")) != "", "marcou situação de quem não foi encaminhado")
    checa(_recusa(lambda: esc.situar(
        pasta, A, "ACAO-1", escritorio="exemplo-a", situacao="RESOLVIDO",
        quem="adv")) != "", "aceitou uma situação fora da lista")
    checa(_recusa(lambda: esc.situar(
        pasta, A, "ACAO-1", escritorio="exemplo-a",
        situacao=esc.ENCAMINHADO, quem="adv")) != "",
        "o escritório 'desrecebeu' um caso")
    print("  ok     só o dono, só de quem foi encaminhado, só da lista")


def teste_falta_documento_diz_qual_e_de_lista_fechada():
    pasta = pasta_nova()
    encaminhar(pasta, [A])
    marcar = lambda **k: esc.situar(  # noqa: E731
        pasta, A, "ACAO-1", escritorio="exemplo-a", quem="adv", **k)
    checa(_recusa(lambda: marcar(situacao=esc.PENDENTE)) != "",
          "aceitou 'falta documento' sem dizer qual")
    checa(_recusa(lambda: marcar(situacao=esc.PENDENTE,
                                 faltam=["o RG da esposa dele"])) != "",
          "aceitou texto livre sobre a pessoa")
    marcar(situacao=esc.PENDENTE, faltam=["procuracao", "identidade"])
    caso = esc.casos_de(pasta, "exemplo-a")[0]
    checa(caso.situacao == esc.PENDENTE
          and caso.faltam == ("identidade", "procuracao"), f"{caso}")
    marcar(situacao=esc.COMPLETO, faltam=["procuracao"])
    caso = esc.casos_de(pasta, "exemplo-a")[0]
    checa(caso.situacao == esc.COMPLETO and caso.faltam == (),
          f"documentação completa não pode ter falta: {caso}")
    do_filiado = esc.de_cpf(pasta, A)
    checa(len(do_filiado) == 1 and do_filiado[0].escritorio == "exemplo-a"
          and do_filiado[0].situacao == esc.COMPLETO,
          f"o filiado não vê o próprio caso: {do_filiado}")
    checa(esc.de_cpf(pasta, B) == (), "inventou caso para quem não tem")
    print("  ok     a falta diz qual documento, e some quando completa")


# ----------------------------------------------------- a visão do sindicato

def teste_o_sindicato_ve_quantos_e_quantos_estao_parados():
    secao("a visão do sindicato")
    pasta = pasta_nova()
    encaminhar(pasta, [A, B], quando="2026-11-01T10:00:00+00:00")
    encaminhar(pasta, [C], quando="2026-11-24T10:00:00+00:00")
    esc.situar(pasta, B, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.RECEBIDO, quem="adv")
    r = {x["id"]: x for x in esc.resumo(
        pasta, agora="2026-11-26T10:00:00+00:00")}
    a = r["exemplo-a"]
    checa((a["casos"], a["encaminhados"], a["recebidos"], a["parados"])
          == (3, 2, 1, 1), f"{a}")
    checa(r["exemplo-b"]["casos"] == 0, "contou caso para quem não tem")
    checa(A not in json.dumps(r), "o resumo devolveu CPF")
    print("  ok     por escritório: quantos, em que situação, quantos parados")


def teste_desfazer_tira_o_caso_do_escritorio():
    pasta = pasta_nova()
    encaminhar(pasta, [A, B])
    checa(esc.desfazer(pasta, A, "ACAO-1", quem="gestor") is True
          and esc.desfazer(pasta, A, "ACAO-1", quem="gestor") is False,
          "desfazer não diz se havia o que desfazer")
    checa([c.cpf for c in esc.casos_de(pasta, "exemplo-a")] == [B],
          "o caso desfeito continua com o escritório")
    print("  ok     encaminhamento errado se desfaz")


def teste_quem_pede_para_sair_sai_dos_encaminhamentos():
    secao("o apagamento")
    pasta = pasta_nova()
    encaminhar(pasta, [A, B])
    esc.situar(pasta, A, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.PENDENTE, faltam=["procuracao"], quem="adv")
    with (pasta / esc.ARQUIVO).open("a", encoding="utf-8") as f:
        f.write("{isto não é json\n")
    saiu = esc.remover_pessoa(pasta, f"{A[:3]}.{A[3:6]}.{A[6:9]}-{A[9:]}")
    bruto = (pasta / esc.ARQUIVO).read_text(encoding="utf-8")
    checa(saiu == 2 and A not in bruto, f"saiu de {saiu} linhas")
    checa("{isto não é json" in bruto, "a linha ilegível foi descartada")
    checa([c.cpf for c in esc.casos_de(pasta, "exemplo-a")] == [B],
          "os outros mudaram")
    print("  ok     sai de todas as linhas; os outros ficam")


TESTES.extend([
    teste_o_cadastro_diz_quem_e_de_qual_escritorio,
    teste_cadastro_torto_e_nenhum_escritorio,
    teste_so_se_encaminha_quem_e_da_base_a_escritorio_que_existe,
    teste_encaminhar_de_novo_nao_duplica_nem_apaga_a_situacao,
    teste_o_escritorio_ve_so_o_que_e_dele,
    teste_so_o_escritorio_dono_muda_a_situacao,
    teste_falta_documento_diz_qual_e_de_lista_fechada,
    teste_o_sindicato_ve_quantos_e_quantos_estao_parados,
    teste_desfazer_tira_o_caso_do_escritorio,
    teste_quem_pede_para_sair_sai_dos_encaminhamentos,
])


# ------------------------------------------------ o Proto do escritório

def _casos_de_exemplo():
    return [
        {"nome": "MARIA DE EXEMPLO (FICTÍCIA)", "situacao": "PENDENTE",
         "faltam": ["procuracao"], "rotulo": "Ação X",
         "encaminhado_em": "2026-11-01T00:00:00+00:00"},
        {"nome": "JOSE DE EXEMPLO (FICTÍCIO)", "situacao": "ENCAMINHADO",
         "faltam": [], "rotulo": "Ação X",
         "encaminhado_em": "2026-11-20T00:00:00+00:00"},
        {"nome": "ANA DE EXEMPLO (FICTÍCIA)", "situacao": "ENCAMINHADO",
         "faltam": [], "rotulo": "Ação X",
         "encaminhado_em": "2026-11-10T00:00:00+00:00"},
        {"nome": "HELENA DE EXEMPLO (FICTÍCIA)", "situacao": "COMPLETO",
         "faltam": [], "rotulo": "Ação X",
         "encaminhado_em": "2026-11-02T00:00:00+00:00"},
    ]


def teste_o_proto_do_escritorio_responde_com_a_fila_dele():
    """O mesmo Proto, para o terceiro leitor: quem trabalha no escritório.
    Lista fechada de assuntos, sem modelo de linguagem, e SÓ com os casos
    que a rota do escritório já entrega — os dele."""
    secao("o Proto do escritório")
    from servidor import atendimento_do_escritorio as proto

    casos = _casos_de_exemplo()
    falar = lambda p: " ".join(  # noqa: E731
        proto.responder(proto.entender(p), casos, p))

    checa(proto.entender("quantos casos eu tenho?") == proto.FILA
          and "4 casos" in falar("quantos casos eu tenho?"),
          f"não contou a fila: {falar('quantos casos eu tenho?')}")
    r = falar("o que eu abro primeiro?")
    checa(proto.entender("o que eu abro primeiro?") == proto.PRIMEIRO
          and r.index("ANA") < r.index("JOSE"),
          f"o mais antigo ainda não aberto devia vir na frente: {r}")
    r = falar("de quem falta documento?")
    checa("MARIA" in r and "procuração" in r and "JOSE" not in r,
          f"não disse de quem falta, e o quê: {r}")
    checa("HELENA" in falar("quem está com a documentação completa?"),
          "não listou os completos")
    r = falar("como está a helena?")
    checa(proto.entender("como está a helena?") == proto.PESSOA
          and "HELENA" in r and "ocumentação completa" in r,
          f"não achou a pessoa pelo nome: {r}")
    checa("não" in falar("como está o fulano de tal?").lower(),
          "inventou resposta sobre quem não é caso dele")
    checa(proto.entender("qual o valor da causa?") == proto.NAO_ENTENDI
          and proto.entender("") == proto.AJUDA,
          "assunto fora da lista devia cair em 'não entendi'")
    checa(falar("quantos casos?").count("0 casos") == 0
          and "nenhum caso" in " ".join(proto.responder(proto.FILA, [])).lower(),
          "fila vazia devia ser dita, não contada em zeros")
    # AS NOVIDADES NOS TRIBUNAIS: repete a frase que o painel já diz.
    nova = [{"frase": "O STJ julgou o Tema 9.001 em 20/11/2026. No "
                      "Sindicato Z, 12 pessoas poderiam entrar com a ação."}]
    checa(proto.entender("teve novidade nos tribunais?") == proto.NOVIDADES
          and proto.entender("o STJ julgou algum tema?") == proto.NOVIDADES,
          "não reconheceu a pergunta sobre os tribunais")
    r = " ".join(proto.responder(proto.NOVIDADES, casos, novidades=nova))
    checa("julgou o Tema 9.001" in r and "simulação" in r,
          f"não repetiu a novidade, ou não disse que é simulação: {r}")
    checa("Não há novidade" in " ".join(
              proto.responder(proto.NOVIDADES, casos, novidades=[])),
          "sem novidade devia dizer que não há")
    checa(len(proto.SUGESTOES) >= 4, "sem sugestões não se sabe o que perguntar")
    print("  ok     fila, por onde começar, quem falta o quê, e busca por nome")


TESTES.extend([teste_o_proto_do_escritorio_responde_com_a_fila_dele])


# ------------------------------------------- o histórico e os avisos

def teste_o_historico_conta_o_caso_passo_a_passo():
    """CUSTÓDIA: quem encaminhou, quando o escritório recebeu, o que pediu,
    qual documento abriu. É o que responde "como o sindicato se
    responsabiliza pelos documentos" — e é o que não existia por e-mail."""
    secao("o histórico do caso")
    pasta = pasta_nova()
    encaminhar(pasta, [A], quando="2026-11-01T10:00:00+00:00")
    esc.registrar(pasta, "aviso", cpf=A, acao="ACAO-1",
                  escritorio="exemplo-a", para="escritorio", saiu=True)
    esc.situar(pasta, A, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.RECEBIDO, quem="adv")
    esc.registrar(pasta, "documento", cpf=A, escritorio="exemplo-a",
                  arquivo="sentenca.pdf")
    esc.situar(pasta, A, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.PENDENTE, faltam=["procuracao"], quem="adv")
    esc.registrar(pasta, "aviso", cpf=A, acao="ACAO-1",
                  escritorio="exemplo-a", para="filiado", saiu=False)
    passos = [h["o_que"] for h in esc.historico(pasta, A, "ACAO-1")]
    checa(passos == [
        "O sindicato encaminhou o caso a Escritório de Exemplo A (fictício).",
        "O escritório foi avisado por e-mail.",
        "O escritório confirmou o recebimento.",
        "O escritório abriu: sentença.",
        "O escritório pediu: procuração.",
        "O aviso por e-mail ao filiado não saiu.",
    ], f"o histórico: {passos}")
    checa(all(h["quando"] for h in esc.historico(pasta, A, "ACAO-1")),
          "passo sem data")
    checa(esc.historico(pasta, B, "ACAO-1") == [],
          "inventou histórico para quem não tem caso")
    print("  ok     seis passos, na ordem, em palavras")


def teste_o_escritorio_so_ve_o_historico_do_que_e_dele():
    """Reencaminhado, o caso muda de mãos — e o escritório novo não lê o que
    o anterior fez. O SINDICATO lê tudo: a custódia é dele."""
    pasta = pasta_nova()
    encaminhar(pasta, [A])
    esc.situar(pasta, A, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.RECEBIDO, quem="adv")
    encaminhar(pasta, [A], escritorio="exemplo-b")
    do_b = [h["o_que"] for h in esc.historico(pasta, A, "ACAO-1",
                                              so_do="exemplo-b")]
    checa(do_b == ["O sindicato encaminhou o caso a Escritório de Exemplo B "
                   "(fictício)."],
          f"o escritório B leu o que o A fez: {do_b}")
    checa(len(esc.historico(pasta, A, "ACAO-1")) == 3,
          "o sindicato devia ler o caminho inteiro")
    # E O HISTÓRICO NÃO MUDA O ESTADO: ato de registro não é ato de caso.
    checa(esc.casos_de(pasta, "exemplo-b")[0].situacao == esc.ENCAMINHADO,
          "registrar um passo mexeu na situação do caso")
    print("  ok     o escritório lê o dele; o sindicato lê tudo")


def teste_os_avisos_nao_levam_dado_de_ninguem():
    """E-MAIL É CARTÃO-POSTAL. O aviso diz que há o que ver e manda entrar
    no portal: não leva nome de filiado, CPF, nem o documento."""
    secao("os avisos por e-mail")
    assunto, corpo = esc.mensagem_ao_escritorio(
        sindicato="Sindicato de Exemplo", acao="Ação X", novos=3)
    checa("3 casos" in corpo and "Sindicato de Exemplo" in corpo
          and "Ação X" in corpo and "portal" in corpo.lower(),
          f"o aviso ao escritório não diz o essencial: {corpo}")
    assunto_f, corpo_f = esc.mensagem_ao_filiado(
        sindicato="Sindicato de Exemplo", escritorio="Escritório A",
        acao="Ação X", faltam=["procuracao", "identidade"])
    checa("procuração" in corpo_f and "documento de identidade" in corpo_f
          and "Escritório A" in corpo_f and "Sindicato de Exemplo" in corpo_f,
          f"o aviso ao filiado não diz o que falta: {corpo_f}")
    for texto in (assunto, corpo, assunto_f, corpo_f):
        checa(A not in texto and "\r" not in texto, "CPF ou CR no aviso")
    checa("\n" not in assunto and "\n" not in assunto_f,
          "assunto com quebra de linha")
    print("  ok     dizem o que há para ver, e mandam entrar no portal")


TESTES.extend([
    teste_o_historico_conta_o_caso_passo_a_passo,
    teste_o_escritorio_so_ve_o_historico_do_que_e_dele,
    teste_os_avisos_nao_levam_dado_de_ninguem,
])


# ------------------------------------------------ o lembrete de caso parado

class _Correio:
    def __init__(self, fora: bool = False) -> None:
        self.mandadas: list[tuple[str, str, str]] = []
        self.fora = fora

    def enviar_mensagem(self, destino, assunto, corpo):
        if self.fora:
            raise OSError("correio fora do ar")
        self.mandadas.append((destino, assunto, corpo))


def teste_caso_parado_ha_mais_de_sete_dias_e_lembrado():
    """O aviso da hora pode se perder, e o caso fica esperando sem ninguém
    saber. O lembrete repete — para o escritório, sobre o que ELE ainda não
    confirmou — e não vira spam: um por semana, por caso."""
    secao("o lembrete de caso parado")
    pasta = pasta_nova()
    encaminhar(pasta, [A, B], quando="2026-11-01T10:00:00+00:00")   # parados
    encaminhar(pasta, [C], quando="2026-11-24T10:00:00+00:00")      # recente
    esc.situar(pasta, B, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.RECEBIDO, quem="adv")                   # já aberto
    correio = _Correio()
    agora = "2026-11-26T10:00:00+00:00"

    r = esc.lembrar_parados(pasta, sindicato="Sindicato de Exemplo",
                            correio=correio, agora=agora)
    checa((r["casos"], r["escritorios"], r["falharam"]) == (1, 1, 0), f"{r}")
    checa(len(correio.mandadas) == 1
          and correio.mandadas[0][0] == "um@exemplo-a.invalid",
          f"o lembrete devia ir só ao escritório A: {correio.mandadas}")
    assunto, corpo = correio.mandadas[0][1:]
    checa("1 caso" in corpo and "25 dias" in corpo
          and "Sindicato de Exemplo" in corpo and A not in corpo
          and "\n" not in assunto,
          f"o lembrete não diz quantos e há quanto tempo: {corpo}")
    passos = [h["o_que"] for h in esc.historico(pasta, A, "ACAO-1")]
    checa(passos[-1] == "O escritório foi lembrado por e-mail de que o caso "
                        "espera a confirmação dele.",
          f"o lembrete não ficou no histórico: {passos}")

    # NO DIA SEGUINTE NÃO REPETE; uma semana depois, sim.
    esc.lembrar_parados(pasta, sindicato="S", correio=correio,
                        agora="2026-11-27T10:00:00+00:00")
    checa(len(correio.mandadas) == 1, "lembrou de novo no dia seguinte")
    r = esc.lembrar_parados(pasta, sindicato="S", correio=correio,
                            agora="2026-12-04T10:00:00+00:00")
    checa(len(correio.mandadas) == 2 and r["casos"] == 2,
          f"uma semana depois devia lembrar de A e, agora, de C: {r}")

    # QUEM CONFIRMOU não é mais lembrado.
    esc.situar(pasta, A, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.RECEBIDO, quem="adv")
    esc.situar(pasta, C, "ACAO-1", escritorio="exemplo-a",
               situacao=esc.RECEBIDO, quem="adv")
    r = esc.lembrar_parados(pasta, sindicato="S", correio=correio,
                            agora="2027-01-10T10:00:00+00:00")
    checa(r["casos"] == 0 and len(correio.mandadas) == 2,
          "lembrou de caso que o escritório já confirmou")
    print("  ok     lembra do que está parado, uma vez por semana, e para")


def teste_lembrete_que_nao_sai_e_tentado_de_novo_no_dia_seguinte():
    pasta = pasta_nova()
    encaminhar(pasta, [A], quando="2026-11-01T10:00:00+00:00")
    r = esc.lembrar_parados(pasta, sindicato="S", correio=_Correio(fora=True),
                            agora="2026-11-26T10:00:00+00:00")
    checa((r["casos"], r["falharam"]) == (1, 1), f"{r}")
    passos = [h["o_que"] for h in esc.historico(pasta, A, "ACAO-1")]
    checa(passos[-1] == "O lembrete por e-mail ao escritório não saiu.",
          f"a falha não ficou no histórico: {passos}")
    bom = _Correio()
    esc.lembrar_parados(pasta, sindicato="S", correio=bom,
                        agora="2026-11-27T10:00:00+00:00")
    checa(len(bom.mandadas) == 1,
          "lembrete que falhou devia ser tentado de novo no dia seguinte")
    print("  ok     correio fora: fica no histórico, e tenta de novo amanhã")


def teste_a_ferramenta_do_agendador_lembra_e_diz_como_foi():
    """O que o agendador roda todo dia. Sai com 0 quando não há o que
    lembrar ou o lembrete saiu, e com 2 quando a entidade não existe."""
    import os
    import subprocess

    from servidor import agenda, entidades

    raiz = pathlib.Path(tempfile.mkdtemp(prefix="esc-raiz-"))
    ent = entidades.Cadastro(raiz).criar("demo-lembra", "Sindicato de Exemplo")
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / esc.CADASTRO).write_text(json.dumps(CADASTRO), encoding="utf-8")
    encaminhar(pasta, [A], quando="2026-01-01T10:00:00+00:00")

    def rodar(entidade):
        return subprocess.run(
            [sys.executable, str(RAIZ / "ferramentas" / "lembrar_parados.py"),
             "--entidade", entidade, "--raiz", str(raiz)],
            capture_output=True, text=True,
            env={**os.environ, "PROTOCOL_MODO_ENSAIO": "1"})

    r = rodar("demo-lembra")
    checa(r.returncode == 0 and "1 caso" in r.stdout,
          f"{r.returncode} {r.stdout} {r.stderr[-300:]}")
    enviado = (raiz / "mensagens_enviadas.log")
    checa(enviado.exists() and "um@exemplo-a.invalid" in enviado.read_text("utf-8"),
          "a ferramenta não mandou o lembrete")
    checa(A not in r.stdout + r.stderr, "a saída da ferramenta levou CPF")
    checa(rodar("nao-existe").returncode == 2, "entidade inexistente não deu 2")
    checa("parados" in agenda.TAREFAS,
          "o lembrete não é tarefa do agendador: só rodaria se alguém lembrasse")
    print("  ok     a ferramenta lembra, e o agendador a conhece")


TESTES.extend([
    teste_caso_parado_ha_mais_de_sete_dias_e_lembrado,
    teste_lembrete_que_nao_sai_e_tentado_de_novo_no_dia_seguinte,
    teste_a_ferramenta_do_agendador_lembra_e_diz_como_foi,
])


def main() -> int:
    print("=" * 70)
    print("ESCRITÓRIOS — o encaminhamento do filiado, e o retorno")
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
