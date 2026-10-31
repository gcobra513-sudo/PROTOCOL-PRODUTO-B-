#!/usr/bin/env python3
"""
O PANORAMA: a mesma resposta do filiado, somada, para quem dirige o sindicato.

A PERGUNTA DO GESTOR NÃO É A DO FILIADO. O filiado pergunta "e eu?". O
diretor pergunta **"o que eu faço primeiro?"** — e a resposta útil não é uma
lista de 4.812 pessoas, é uma frase:

    Homologar a GIFA destrava 1.204 pessoas.

Uma decisão, mil pessoas. Nada no produto dizia isso: `completude` conta o
estado da BASE (quem não se alcança, o que falta de cadastro) e para aí.

POR ISSO OS GARGALOS SAEM ORDENADOS POR QUANTAS PESSOAS DESTRAVAM, e
separados por quem destrava — a mesma divisão da tela do filiado, pela mesma
razão invertida: lá serve para a pessoa saber que não precisa ligar; aqui
serve para o sindicato saber o que resolver primeiro, e o que não adianta
tentar resolver porque depende do tribunal.

O QUE ESTE MÓDULO NÃO FAZ, e é decisão: **não lê documento**. Rodar a leitura
de PDF de toda a base a cada carregamento de painel é consulta de minutos
para responder uma tela. O que ele usa é o CADASTRO — cargo e período de
filiação, que é o que decide participação — mais a LISTA DE ARQUIVOS que cada
pessoa entregou, que o diário já guarda. Saber que a sentença chegou basta
para a pendência deixar de ser da pessoa; ler o que ela diz é outra etapa, e
é por pessoa.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import entendimentos, motor, panorama, pendencia  # noqa: E402
from nucleo import participacao as part  # noqa: E402

CATEGORIAS = RAIZ / "config" / "categorias"
AFRFB = "Auditor-Fiscal da Receita Federal do Brasil"

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def acervo(homologar: tuple[str, ...] = ()) -> entendimentos.Catalogo:
    return entendimentos.carregar_categorias(CATEGORIAS).homologando(homologar)


def registro(cpf: str, *, cargo: str = AFRFB, desde: str = "2004-03",
             ate: str = "", arquivos: tuple[str, ...] = ("contribuicao-1.pdf",),
             nome: str = "", **extra) -> dict:
    """Um registro do diário, na forma que `deposito` grava."""
    linha = {
        "cpf": cpf,
        "nome_completo": nome or f"FULANO {cpf[-2:]} (CADASTRO DE EXEMPLO)",
        "email": "exemplo@exemplo.org",
        "cargo": cargo,
        "situacao": "aposentado",
        "filiado_desde": desde,
        "filiado_ate": ate,
        "ja_executou": "nao_sei",
        "tem_acao_propria": "nao_sei",
        "quer_aviso": "",
    }
    linha.update(extra)
    return {"protocolo": f"PRT-{cpf}", "linha": linha,
            "arquivos": {a: "x" * 64 for a in arquivos}}


# CPFs de teste, com dígito válido e declaradamente fictícios.
A, B, C = "11144477735", "52998224725", "01234567890"


# ------------------------------------------------------------ a aritmética

def teste_conta_pessoa_nao_linha():
    """A mesma regra de `completude`, e pelo mesmo motivo: reenvio é
    correção, não filiado novo. Contar envios diria ao diretor que ele tem
    mais gente do que tem."""
    secao("a aritmética")
    p = panorama.montar(
        [registro(A), registro(A, desde="2005-01"), registro(B)],
        acervo(("GIFA-2006",)),
    )
    checa(p.pessoas == 2, f"contou {p.pessoas} pessoas para 2 CPFs")
    print(f"  ok     3 envios, 2 pessoas")


def teste_o_ultimo_envio_vence():
    """Quem corrigiu o cadastro tem de ser contado pelo que corrigiu."""
    fora = registro(A, desde="2015-01")      # entrou depois da GIFA acabar
    dentro = registro(A, desde="2004-03")    # corrigiu: entra
    p = panorama.montar([fora, dentro], acervo(("GIFA-2006",)))
    gifa = next(x for x in p.por_acao if x.acao == "GIFA-2006")
    checa(gifa.participam == 1,
          f"o último envio não venceu: participam={gifa.participam}")
    print("  ok     o último envio de cada CPF é o que conta")


def teste_a_soma_bate_com_o_motor_pessoa_a_pessoa():
    """A trava que protege de erro de contagem. O panorama é uma SOMA, e uma
    soma que não bate com as parcelas é uma afirmação falsa dita a um diretor
    de sindicato com a nossa assinatura."""
    cat = acervo(("GIFA-2006",))
    registros = [registro(A), registro(B, desde="2015-01"),
                 registro(C, cargo="Guarda Municipal de Exemplo")]
    p = panorama.montar(registros, cat)

    for pa in p.por_acao:
        acao = cat.de(pa.acao)
        contado = {part.PARTICIPA: 0, part.INDETERMINADO: 0,
                   part.NAO_PARTICIPA: 0}
        for r in registros:
            linha = r["linha"]
            quem = part.Filiado(
                cpf=linha["cpf"], cargo=linha["cargo"],
                filiado_desde=linha["filiado_desde"],
                filiado_ate=linha["filiado_ate"],
            )
            contado[part.cruzar(quem, acao, cat).estado] += 1
        checa((pa.participam, pa.indeterminados, pa.nao_participam)
              == (contado[part.PARTICIPA], contado[part.INDETERMINADO],
                  contado[part.NAO_PARTICIPA]),
              f"{pa.acao}: panorama diz "
              f"{(pa.participam, pa.indeterminados, pa.nao_participam)}, o "
              f"motor pessoa a pessoa diz {tuple(contado.values())}")
        checa(pa.participam + pa.indeterminados + pa.nao_participam
              == p.pessoas,
              f"{pa.acao}: as três contagens não somam {p.pessoas}")
    print(f"  ok     {len(p.por_acao)} ação(ões): soma bate com o motor")


def teste_meses_somados_so_de_quem_participa():
    """A base do cálculo do valor, quando ele existir. Somar os meses de quem
    não participa inflaria a conta antes de ela existir."""
    cat = acervo(("GIFA-2006",))
    p = panorama.montar(
        [registro(A, desde="2003-01", ate="2008-12"),   # a ação inteira: 72
         registro(B, desde="2015-01")],                 # fora
        cat,
    )
    gifa = next(x for x in p.por_acao if x.acao == "GIFA-2006")
    checa(gifa.meses_somados == 72,
          f"meses somados = {gifa.meses_somados}, esperado 72")
    print(f"  ok     meses somados: {gifa.meses_somados}")


# -------------------------------------------------------------- os gargalos

def teste_gargalos_ordenados_por_quantas_pessoas_destravam():
    """O QUE FAZ O PAINEL VALER. O diretor não precisa da lista de pendências:
    precisa de qual delas, resolvida, move mais gente."""
    secao("os gargalos")
    # Um sozinho com cargo estranho, três na carreira: a homologação segura
    # os quatro, a conferência de carreira segura um.
    p = panorama.montar(
        [registro(A), registro(B), registro(C, cargo="Cargo Desconhecido")],
        acervo(),
    )
    checa(bool(p.gargalos), "nenhum gargalo apurado")
    quantidades = [g.pessoas for g in p.gargalos]
    checa(quantidades == sorted(quantidades, reverse=True),
          f"os gargalos não vieram do maior para o menor: {quantidades}")
    maior = p.gargalos[0]
    checa(maior.pessoas == 3,
          f"o maior gargalo segura {maior.pessoas}, e são 3 pessoas")
    print(f"  ok     maior gargalo: {maior.pessoas} pessoas — {maior.o_que}")


def teste_cada_gargalo_sabe_quem_destrava():
    """A mesma divisão da tela do filiado, pela razão invertida: aqui serve
    para o sindicato saber o que NÃO adianta tentar resolver."""
    p = panorama.montar([registro(A)], acervo(("STJ-T1410",)))
    for g in p.gargalos:
        checa(g.quem in pendencia.DONOS, f"gargalo sem dono: {g!r}")
    donos = {g.quem for g in p.gargalos}
    checa(pendencia.TRIBUNAL in donos,
          f"o tema pendente não virou gargalo de tribunal: {donos}")
    checa(pendencia.CONFERENCIA in donos,
          f"a homologação não virou gargalo de conferência: {donos}")
    print(f"  ok     donos presentes: {sorted(donos)}")


def teste_gargalo_traz_exemplos_nominais_mas_limitados():
    """Contagem não serve para agir: o gestor não liga para um número. Mas
    devolver 4.812 nomes a cada carregamento de painel é outro problema — de
    tamanho e de exposição. Traz alguns, e diz o total."""
    muitos = [registro(f"{i:011d}", cargo="Cargo Desconhecido")
              for i in range(1, 31)]
    p = panorama.montar(muitos, acervo(), exemplos=5)
    carreira = [g for g in p.gargalos if "carreira" in g.o_que.lower()]
    checa(bool(carreira), "a conferência de carreira não virou gargalo")
    g = carreira[0]
    checa(g.pessoas == 30, f"deveria segurar 30 pessoas, segura {g.pessoas}")
    checa(len(g.exemplos) == 5,
          f"trouxe {len(g.exemplos)} exemplos, e o limite era 5")
    print(f"  ok     {g.pessoas} pessoas, {len(g.exemplos)} exemplos")


def teste_quem_ja_entregou_a_sentenca_nao_e_cobrado_dela():
    """O NÚMERO FALSO QUE QUASE FOI DITO AO DIRETOR. Sem olhar os arquivos
    entregues, "falta a sentença" apareceria para TODA a base — inclusive
    para quem já mandou. O diário guarda o nome dos arquivos de cada envio, e
    isso basta: a pendência deixa de ser da pessoa e passa a ser de leitura.
    Ler o que a sentença diz é outra etapa, e é por pessoa."""
    cat = acervo(("GIFA-2006",))
    sem = panorama.montar([registro(A)], cat)
    com = panorama.montar(
        [registro(A, arquivos=("contribuicao-1.pdf", "sentenca.pdf"))], cat
    )

    def dono_da_sentenca(p):
        for g in p.gargalos:
            if "sentença" in g.o_que.lower():
                return g.quem
        return None

    checa(dono_da_sentenca(sem) == pendencia.VOCE,
          f"quem não mandou: dono {dono_da_sentenca(sem)}")
    checa(dono_da_sentenca(com) == pendencia.CONFERENCIA,
          f"quem JÁ MANDOU continua sendo cobrado: "
          f"dono {dono_da_sentenca(com)}")
    print("  ok     sentença entregue vira pendência de leitura, não de envio")


# ---------------------------------------------------------- as travas de base

def teste_entidade_sem_categoria_tem_panorama_vazio():
    """Fail-closed, igual à tela do filiado: ausência de declaração é
    nenhuma categoria, nunca todas."""
    secao("as travas")
    p = panorama.montar([registro(A)], entendimentos.VAZIO)
    checa(p.por_acao == () and p.gargalos == (),
          f"entidade sem categoria recebeu panorama: {p}")
    checa(p.pessoas == 1, "deixou de contar as pessoas")
    checa("categoria" in p.manchete().lower(),
          f"a manchete não explica o vazio: {p.manchete()!r}")
    print(f"  ok     sem categoria: {p.manchete()}")


def teste_base_vazia_nao_inventa_numero():
    """A ação continua listada — ela é do CATÁLOGO, não da base, e some-la
    esconderia do gestor que ela existe para a categoria dele. O que não pode
    existir é contagem: zero pessoas é zero em toda coluna, e gargalo nenhum
    (gargalo com 0 pessoas é pendência que não segura ninguém)."""
    p = panorama.montar([], acervo(("GIFA-2006",)))
    checa(p.pessoas == 0, "contou gente numa base vazia")
    for pa in p.por_acao:
        checa((pa.participam, pa.indeterminados, pa.nao_participam,
               pa.meses_somados) == (0, 0, 0, 0),
              f"{pa.acao}: contagem não zerada numa base vazia: {pa}")
    checa(p.gargalos == (), f"inventou gargalo sem ninguém: {p.gargalos}")
    checa(p.aptos == 0, "contou apto numa base vazia")
    checa(bool(p.manchete().strip()), "manchete vazia")
    checa("0" in p.manchete() or "ningu" in p.manchete().lower()
          or "nenhum" in p.manchete().lower(),
          f"a manchete não diz que não há ninguém: {p.manchete()!r}")
    print(f"  ok     base vazia: {p.manchete()}")


def teste_o_panorama_declara_que_nao_leu_documento():
    """Número que vai para o cliente é medido, e o que NÃO foi medido tem de
    ser dito. O painel não leu nenhum PDF, e deixar isso implícito faria o
    diretor achar que a coluna de títulos foi conferida."""
    p = panorama.montar([registro(A)], acervo(("GIFA-2006",)))
    checa(p.leu_documentos is False,
          "disse que leu documentos, e não leu nenhum")
    print("  ok     declara que não leu documento")


def teste_nada_homologado_nenhum_pode():
    """A trava que vem de fora do código, também na soma."""
    p = panorama.montar([registro(A), registro(B)], acervo())
    checa(p.aptos == 0,
          f"contou {p.aptos} aptos com o catálogo não homologado")
    print("  ok     catálogo não homologado: 0 aptos")


def teste_a_manchete_nomeia_o_maior_gargalo_e_de_quem_ele_e():
    """Uma decisão, mil pessoas. É esta frase que o diretor leva da reunião.

    E ELA TEM DE DIZER DE QUEM É. Visto no navegador: a manchete apontava o
    maior gargalo da base — que era uma pendência DO FILIADO — enquanto o
    cartão logo abaixo apontava o maior que o SINDICATO resolve. Duas frases
    coladas uma na outra nomeando coisas diferentes como "a" prioridade.
    """
    p = panorama.montar([registro(A), registro(B), registro(C)], acervo())
    m = p.manchete()
    maior = p.gargalos[0]
    checa(str(maior.pessoas) in m,
          f"a manchete não traz o número do maior gargalo: {m!r}")
    checa(pendencia.TITULOS[maior.quem].lower() in m.lower()
          or pendencia.ROTULO_CURTO[maior.quem].lower() in m.lower(),
          f"a manchete não diz de quem é o gargalo que ela aponta: {m!r}")
    checa("escritóri" not in m.lower(),
          f"REGRA ZERO: a manchete fala de escritório: {m!r}")
    print(f"  ok     {m}")


def teste_cada_dono_tem_rotulo_curto_para_caber_na_frase():
    """"O que o sindicato está conferindo" é título de cartão; no meio de uma
    frase ele não cabe. O rótulo curto existe para isso, e as três formas têm
    de existir — faltar uma deixaria `KeyError` numa manchete."""
    for dono in pendencia.DONOS:
        curto = pendencia.ROTULO_CURTO[dono]
        checa(bool(curto.strip()) and len(curto) < 28,
              f"{dono}: rótulo curto ruim: {curto!r}")
    print("  ok     " + " | ".join(pendencia.ROTULO_CURTO[d]
                                   for d in pendencia.DONOS))


def teste_registro_ilegivel_nao_derruba_o_panorama():
    """Uma linha truncada por queda no meio da escrita não pode apagar o
    painel inteiro — `deposito.ler_diario` devolve `{'_ilegivel': n}`."""
    p = panorama.montar(
        [registro(A), {"_ilegivel": 7}, {}, {"linha": "isto não é dicionário"},
         registro(B)],
        acervo(("GIFA-2006",)),
    )
    checa(p.pessoas == 2, f"contou {p.pessoas} pessoas, e são 2 legíveis")
    print("  ok     registro ilegível é pulado, não derruba")


TESTES = [
    teste_conta_pessoa_nao_linha,
    teste_o_ultimo_envio_vence,
    teste_a_soma_bate_com_o_motor_pessoa_a_pessoa,
    teste_meses_somados_so_de_quem_participa,
    teste_gargalos_ordenados_por_quantas_pessoas_destravam,
    teste_cada_gargalo_sabe_quem_destrava,
    teste_gargalo_traz_exemplos_nominais_mas_limitados,
    teste_quem_ja_entregou_a_sentenca_nao_e_cobrado_dela,
    teste_entidade_sem_categoria_tem_panorama_vazio,
    teste_base_vazia_nao_inventa_numero,
    teste_o_panorama_declara_que_nao_leu_documento,
    teste_nada_homologado_nenhum_pode,
    teste_a_manchete_nomeia_o_maior_gargalo_e_de_quem_ele_e,
    teste_cada_dono_tem_rotulo_curto_para_caber_na_frase,
    teste_registro_ilegivel_nao_derruba_o_panorama,
]


def main() -> int:
    print("=" * 62)
    print("PANORAMA — a resposta do filiado, somada para o sindicato")
    print("=" * 62)
    for t in TESTES:
        try:
            t()
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{t.__name__} levantou {type(e).__name__}: {e}")
    print()
    if falhas:
        print(f"FALHOU ({len(falhas)}):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
