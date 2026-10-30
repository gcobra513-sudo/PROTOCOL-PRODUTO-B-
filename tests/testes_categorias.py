#!/usr/bin/env python3
"""
O catálogo POR CATEGORIA — atender mais de um sindicato ao mesmo tempo.

POR QUE ISTO EXISTE. O catálogo era um arquivo único, com uma linha
`categoria = "Auditores-Fiscais da Receita Federal do Brasil"` no topo.
Funciona para um contrato. Com dois sindicatos de categorias diferentes, não:

  * o filiado de uma categoria era avaliado contra as ações da OUTRA. Na
    trilha EXECUTAR isso já estava barrado (`participacao.cruzar` confere a
    categoria da ação). Na trilha AJUIZAR **não havia conferência nenhuma** —
    `_avaliar_ajuizar` nunca olhava o cargo da pessoa. Um entendimento sobre
    o 28,86% da RAV da carreira de Auditor-Fiscal apareceria para um policial
    militar, e com os critérios preenchidos sairia PODE;
  * a tabela de sinônimos de cargo morava em Python. Enquanto morasse lá,
    acrescentar uma categoria era mexer no código — e é assim que a tabela
    para de crescer e todo mundo de uma carreira nova vira INDETERMINADO.

AS DUAS ASSIMETRIAS QUE ESTES TESTES PRENDEM, e as duas são deliberadas:

  cargo de OUTRA categoria conhecida  ->  NAO_PODE. É resposta.
  cargo NÃO reconhecido               ->  FALTA. Nunca PODE, nunca NAO_PODE.

A primeira protege de afirmar direito alheio. A segunda protege de tirar
direito de alguém por causa de uma grafia que a tabela ainda não conhece.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import entendimentos, motor  # noqa: E402
from nucleo import participacao as part  # noqa: E402

PASTA = RAIZ / "config" / "categorias"

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


# --------------------------------------------------------------- fixtureszinhas

def _escrever(pasta: Path, slug: str, corpo: str) -> Path:
    destino = pasta / f"{slug}.toml"
    destino.write_text(corpo, encoding="utf-8")
    return destino


#: Uma categoria inventada, de propósito, para o teste: cargo que não existe
#: em lugar nenhum. Categoria de verdade entra no catálogo por decisão do
#: jurídico, não por conveniência de suíte.
CATEGORIA_A = """
[catalogo]
versao = 3
categoria = "Carreira Exemplo A"
cargos = ["carreira exemplo a", "exemplo a", "cea"]

[[entendimentos]]
id = "EX-A-1"
tribunal = "STJ"
tema = "9001"
situacao = "julgado"
tese = "Tese de exemplo A, transcrita."
trilha = "ajuizar"
criterios = ["critério de exemplo A"]
fonte = "exemplo://a"

[[acoes_coletivas]]
id = "EX-A-ACAO"
descricao = "Ação coletiva de exemplo A"
situacao = "transitado_em_julgado"
periodo_inicio = "2000-01"
periodo_fim = "2009-12"
exige_rol = false
fonte = "exemplo://a-acao"
"""

CATEGORIA_B = """
[catalogo]
versao = 1
categoria = "Carreira Exemplo B"
cargos = ["carreira exemplo b", "exemplo b", "ceb"]

[[entendimentos]]
id = "EX-B-1"
tribunal = "STJ"
tema = "9002"
situacao = "julgado"
tese = "Tese de exemplo B, transcrita."
trilha = "ajuizar"
criterios = ["critério de exemplo B"]
fonte = "exemplo://b"

[[acoes_coletivas]]
id = "EX-B-ACAO"
descricao = "Ação coletiva de exemplo B"
situacao = "transitado_em_julgado"
periodo_inicio = "2000-01"
periodo_fim = "2009-12"
exige_rol = false
fonte = "exemplo://b-acao"
"""


def duas_categorias() -> Path:
    pasta = Path(tempfile.mkdtemp())
    _escrever(pasta, "exemplo-a", CATEGORIA_A)
    _escrever(pasta, "exemplo-b", CATEGORIA_B)
    return pasta


def pessoa(cargo: str, **trocas) -> motor.Fatos:
    base = dict(
        cpf="11144477735",
        nome="FULANA DE TAL (CADASTRO DE EXEMPLO)",
        cargo=cargo,
        situacao="aposentado",
        filiado_desde="2001-01",
        filiado_ate="",
        tem_titulo=True,
        no_rol=True,
        ja_executou=False,
        tem_acao_propria=False,
    )
    base.update(trocas)
    return motor.Fatos(**base)


# ------------------------------------------------------- o catálogo em disco

def teste_o_catalogo_global_nao_existe_mais():
    """Enquanto o arquivo único existir, alguém vai carregá-lo — e vai
    atender o segundo sindicato com o catálogo do primeiro."""
    secao("o catálogo em disco")
    antigo = RAIZ / "config" / "entendimentos.toml"
    checa(not antigo.exists(),
          f"{antigo} ainda existe: o catálogo global é a própria confusão "
          f"que estamos tirando")
    checa(PASTA.is_dir(), f"{PASTA} não existe")
    arquivos = sorted(PASTA.glob("*.toml"))
    checa(bool(arquivos), f"nenhum catálogo de categoria em {PASTA}")
    print(f"  ok     {len(arquivos)} catálogo(s) em config/categorias/")


def teste_cada_arquivo_declara_a_sua_categoria_e_os_cargos():
    """Sem `categoria` não há a quem o catálogo se aplica; sem `cargos` não
    há como reconhecer a carreira de ninguém."""
    for arquivo in sorted(PASTA.glob("*.toml")):
        cat = entendimentos.carregar(arquivo)
        checa(len(cat.categorias) == 1,
              f"{arquivo.name}: um arquivo é de UMA categoria, veio "
              f"{cat.categorias}")
        checa(bool(cat.categorias and cat.categorias[0].strip()),
              f"{arquivo.name}: categoria vazia")
        checa(bool(cat.cargos.get(cat.categorias[0])),
              f"{arquivo.name}: nenhum cargo declarado para "
              f"{cat.categorias[0]!r}")
        checa(cat.slug_de(cat.categorias[0]) == arquivo.stem,
              f"{arquivo.name}: o slug não é o nome do arquivo")
        print(f"  ok     {arquivo.stem}: {cat.categorias[0][:34]} "
              f"({len(cat.cargos[cat.categorias[0]])} grafias)")


def teste_toda_entrada_pertence_a_categoria_do_arquivo():
    """A ação e o entendimento sabem de quem falam. É isso que permite ao
    motor recusar o que não é da pessoa."""
    for arquivo in sorted(PASTA.glob("*.toml")):
        cat = entendimentos.carregar(arquivo)
        dela = cat.categorias[0]
        for a in cat.acoes:
            checa(a.categoria == dela,
                  f"{arquivo.name}: ação {a.id} diz {a.categoria!r}")
        for e in cat.entendimentos:
            checa(e.categoria == dela,
                  f"{arquivo.name}: entendimento {e.id} diz {e.categoria!r}")
    print("  ok     toda ação e todo entendimento carregam a categoria")


# --------------------------------------- o que estava errado: a trilha AJUIZAR

def teste_ajuizar_nao_oferece_tese_de_outra_carreira():
    """O BUG QUE ESTE CHECKPOINT CONSERTA.

    `_avaliar_executar` já perguntava pela participação antes do título. A
    trilha AJUIZAR nunca perguntou nada: devolvia o entendimento para quem
    passasse. Com catálogo de uma categoria só isso não aparecia, porque a
    categoria era implícita. Com dois sindicatos, aparece — e aparece como
    PODE.
    """
    secao("ajuizar não atravessa categoria")
    cat = entendimentos.carregar_categorias(duas_categorias()).homologando(
        ("EX-A-1", "EX-B-1", "EX-A-ACAO", "EX-B-ACAO")
    )
    oportunidades = motor.avaliar(pessoa("Carreira Exemplo A"), cat)
    de_b = [o for o in oportunidades if o.referencia == "EX-B-1"]
    checa(len(de_b) == 1, f"o entendimento de B não foi avaliado: {de_b}")
    if de_b:
        o = de_b[0]
        checa(o.veredicto == motor.NAO_PODE,
              f"EX-B-1 para alguém da carreira A deu {o.veredicto}, e devia "
              f"ser NAO_PODE — oferecer tese de outra carreira é afirmar "
              f"direito que a pessoa não tem")
        checa(any("carreira" in m or "categoria" in m for m in o.motivos),
              f"o motivo não diz que é de outra carreira: {o.motivos}")
        print(f"  ok     EX-B-1 para carreira A: {o.veredicto}")


def teste_a_pessoa_recebe_a_tese_da_propria_carreira():
    """A outra metade: recusar o que não é dela não pode custar o que é."""
    cat = entendimentos.carregar_categorias(duas_categorias()).homologando(
        ("EX-A-1", "EX-B-1", "EX-A-ACAO", "EX-B-ACAO")
    )
    oportunidades = motor.avaliar(pessoa("Carreira Exemplo A"), cat)
    de_a = [o for o in oportunidades if o.referencia == "EX-A-1"]
    checa(len(de_a) == 1, "o entendimento da própria carreira sumiu")
    if de_a:
        checa(de_a[0].veredicto == motor.PODE,
              f"EX-A-1 para alguém da carreira A deu {de_a[0].veredicto}: "
              f"{de_a[0].motivos} / falta {de_a[0].falta}")
        print(f"  ok     EX-A-1 para carreira A: {de_a[0].veredicto}")


def teste_juntar_categorias_nao_muda_o_veredicto_de_quem_e_da_casa():
    """A REGRESSÃO QUE MAIS IMPORTA. Fechar contrato com o segundo sindicato
    não pode mexer na resposta que o primeiro já recebeu."""
    pasta = duas_categorias()
    ids = ("EX-A-1", "EX-A-ACAO", "EX-B-1", "EX-B-ACAO")
    so_a = entendimentos.carregar(pasta / "exemplo-a.toml").homologando(ids)
    com_b = entendimentos.carregar_categorias(pasta).homologando(ids)

    f = pessoa("Carreira Exemplo A")
    sozinho = {o.referencia: o.veredicto for o in motor.avaliar(f, so_a)}
    junto = {o.referencia: o.veredicto for o in motor.avaliar(f, com_b)}
    for ref, veredicto in sozinho.items():
        checa(junto.get(ref) == veredicto,
              f"{ref} era {veredicto} com um catálogo e virou "
              f"{junto.get(ref)} com dois")
    print(f"  ok     {len(sozinho)} veredictos de A idênticos com e sem B")


def teste_cargo_nao_reconhecido_nunca_vira_permissao():
    """A dúvida não vira permissão — nem na trilha nova.

    E, igualmente importante: não vira recusa. Um cargo que a tabela não
    conhece pode ser a mesma carreira escrita de outro jeito.
    """
    cat = entendimentos.carregar_categorias(duas_categorias()).homologando(
        ("EX-A-1", "EX-B-1", "EX-A-ACAO", "EX-B-ACAO")
    )
    oportunidades = motor.avaliar(pessoa("Cargo Que Ninguém Cadastrou"), cat)
    checa(not any(o.veredicto == motor.PODE for o in oportunidades),
          "um cargo desconhecido saiu com PODE: "
          + str([o.referencia for o in oportunidades if o]))
    das_teses = [o for o in oportunidades if o.trilha == motor.AJUIZAR]
    checa(bool(das_teses), "nenhuma trilha de ajuizar foi avaliada")
    for o in das_teses:
        checa(o.veredicto == motor.FALTA,
              f"{o.referencia}: cargo desconhecido deu {o.veredicto}, e "
              f"devia ser FALTA")
        checa(any("carreira" in f for f in o.falta),
              f"{o.referencia}: a falta não pede confirmar a carreira: "
              f"{o.falta}")
    print(f"  ok     cargo desconhecido: {len(das_teses)} teses em FALTA, "
          f"0 em PODE")


# ------------------------------------------------- integridade entre arquivos

def teste_id_repetido_em_dois_arquivos_e_erro():
    """Dois "GIFA-2006" diferentes em dois catálogos e o motor pega um deles.
    Qual, depende da ordem do diretório."""
    secao("integridade entre arquivos")
    pasta = Path(tempfile.mkdtemp())
    _escrever(pasta, "exemplo-a", CATEGORIA_A)
    _escrever(pasta, "exemplo-b", CATEGORIA_B.replace("EX-B-1", "EX-A-1"))
    try:
        entendimentos.carregar_categorias(pasta)
        checa(False, "aceitou o mesmo id em dois catálogos")
    except entendimentos.ErroDeCatalogo as e:
        checa("EX-A-1" in str(e), f"a mensagem não diz qual id: {e}")
        print("  ok     id repetido entre arquivos é recusado")


def teste_cargo_reivindicado_por_duas_categorias_e_erro():
    """O pior caso silencioso: a pessoa é posta na carreira errada porque
    duas categorias declaram a mesma grafia, e uma vence por ordem de
    leitura do diretório."""
    pasta = Path(tempfile.mkdtemp())
    _escrever(pasta, "exemplo-a", CATEGORIA_A)
    _escrever(pasta, "exemplo-b", CATEGORIA_B.replace(
        'cargos = ["carreira exemplo b", "exemplo b", "ceb"]',
        'cargos = ["carreira exemplo b", "exemplo a", "ceb"]',
    ))
    try:
        entendimentos.carregar_categorias(pasta)
        checa(False, "aceitou a mesma grafia de cargo em duas categorias")
    except entendimentos.ErroDeCatalogo as e:
        checa("exemplo a" in str(e).lower(),
              f"a mensagem não diz qual cargo: {e}")
        print("  ok     cargo em duas categorias é recusado")


def teste_acao_de_outra_categoria_dentro_do_arquivo_e_erro():
    """O arquivo é de uma categoria. Uma ação que diz outra é contaminação
    cruzada escrita à mão, e ninguém perceberia."""
    pasta = Path(tempfile.mkdtemp())
    _escrever(pasta, "exemplo-a", CATEGORIA_A + '\ncategoria = "Outra Coisa"\n')
    try:
        entendimentos.carregar(pasta / "exemplo-a.toml")
        checa(False, "aceitou ação declarando categoria diferente do arquivo")
    except entendimentos.ErroDeCatalogo as e:
        checa("categoria" in str(e).lower(), f"mensagem obscura: {e}")
        print("  ok     ação de outra categoria no arquivo é recusada")


def teste_catalogo_sem_categoria_e_erro():
    """Catálogo sem categoria é catálogo de ninguém — e, pior, de todos."""
    pasta = Path(tempfile.mkdtemp())
    _escrever(pasta, "sem-dono", '[catalogo]\nversao = 1\n')
    try:
        entendimentos.carregar(pasta / "sem-dono.toml")
        checa(False, "aceitou catálogo sem categoria")
    except entendimentos.ErroDeCatalogo as e:
        checa("categoria" in str(e).lower(), f"mensagem obscura: {e}")
        print("  ok     catálogo sem categoria é recusado")


def teste_a_versao_de_cada_catalogo_sobrevive_a_juncao():
    """O que torna o veredicto auditável: quando o Tema 1.302 for julgado,
    a reavaliação muda o resultado e dá para provar com qual catálogo o
    resultado anterior saiu. Uma versão só para o conjunto perderia isso."""
    cat = entendimentos.carregar_categorias(duas_categorias())
    checa(cat.versao_de("exemplo-a") == 3,
          f"versão de exemplo-a veio {cat.versao_de('exemplo-a')}, era 3")
    checa(cat.versao_de("exemplo-b") == 1,
          f"versão de exemplo-b veio {cat.versao_de('exemplo-b')}, era 1")
    checa("exemplo-a@3" in cat.assinatura and "exemplo-b@1" in cat.assinatura,
          f"a assinatura não identifica os catálogos: {cat.assinatura}")
    print(f"  ok     assinatura: {cat.assinatura}")


# --------------------------------------- a tabela de cargos é dado, não código

def teste_acrescentar_categoria_e_acrescentar_arquivo():
    """O TESTE QUE DIZ SE O PRODUTO ESCALA. Fechar contrato com um sindicato
    de outra categoria não pode exigir mexer em Python."""
    secao("acrescentar categoria é acrescentar arquivo")
    pasta = duas_categorias()
    _escrever(pasta, "exemplo-c", CATEGORIA_B
              .replace("Exemplo B", "Exemplo C")
              .replace("exemplo b", "exemplo c")
              .replace("ceb", "cec")
              .replace("EX-B", "EX-C"))
    cat = entendimentos.carregar_categorias(pasta)
    checa(cat.categoria_do_cargo("CEC") == "Carreira Exemplo C",
          f"a carreira nova não foi reconhecida: "
          f"{cat.categoria_do_cargo('CEC')!r}")
    checa("Carreira Exemplo C" in cat.categorias,
          f"a categoria nova não entrou: {cat.categorias}")
    print("  ok     três categorias, nenhuma linha de Python tocada")


def teste_participacao_nao_guarda_tabela_de_carreiras():
    """Enquanto a tabela morar no módulo, acrescentar categoria é mexer no
    código — e é assim que ela para de crescer."""
    fonte = (RAIZ / "nucleo" / "participacao.py").read_text("utf-8")
    checa("CATEGORIAS" not in fonte,
          "participacao.py ainda tem a tabela CATEGORIAS embutida")
    for nome in ("auditor", "receita federal", "analista tributario"):
        checa(nome not in fonte.lower(),
              f"participacao.py ainda nomeia uma carreira: {nome!r}")
    print("  ok     nenhuma carreira nomeada em participacao.py")


def teste_cargo_escrito_de_outro_jeito_casa_pelo_arquivo():
    """O sinônimo continua funcionando — só mudou de lugar."""
    cat = entendimentos.carregar_categorias(duas_categorias())
    for escrito in ("CEA", "  Exemplo   A  ", "carreira exemplo a"):
        achou = cat.categoria_do_cargo(escrito)
        checa(achou == "Carreira Exemplo A",
              f"{escrito!r} não casou com a carreira A: {achou!r}")
    checa(cat.categoria_do_cargo("Pedreiro") is None,
          "um cargo de fora casou com alguma categoria")
    checa(cat.categoria_do_cargo("") is None, "cargo vazio casou")
    print("  ok     grafias casam; desconhecido devolve None")


# -------------------------------------- a entidade declara o que contratou

def teste_entidade_declara_as_categorias_que_contratou():
    secao("a entidade declara o que contratou")
    import json

    from servidor import entidades

    raiz = Path(tempfile.mkdtemp())
    (raiz / "entidades.json").write_text(json.dumps({
        "demo-a": {"nome": "Sindicato de Exemplo A",
                   "categorias": ["exemplo-a"]},
        "demo-ab": {"nome": "Sindicato de Exemplo A e B",
                    "categorias": ["exemplo-a", "exemplo-b"]},
        "demo-sem": {"nome": "Sindicato sem categoria declarada"},
    }), encoding="utf-8")
    cadastro = entidades.Cadastro(raiz)
    checa(cadastro.resolver("demo-a").categorias == ("exemplo-a",),
          f"veio {cadastro.resolver('demo-a').categorias}")
    checa(cadastro.resolver("demo-ab").categorias
          == ("exemplo-a", "exemplo-b"),
          f"veio {cadastro.resolver('demo-ab').categorias}")
    print("  ok     uma entidade pode contratar mais de uma categoria")


def teste_entidade_sem_categoria_nao_recebe_todas():
    """FAIL-CLOSED. Ausência de declaração é "nenhuma", nunca "todas" — e a
    diferença é um sindicato recebendo o catálogo do outro."""
    import json

    from servidor import entidades

    raiz = Path(tempfile.mkdtemp())
    (raiz / "entidades.json").write_text(json.dumps({
        "demo-sem": {"nome": "Sindicato sem categoria declarada"},
    }), encoding="utf-8")
    ent = entidades.Cadastro(raiz).resolver("demo-sem")
    checa(ent.categorias == (),
          f"sem declaração veio {ent.categorias}, e devia vir vazio")

    cat = entendimentos.carregar_categorias(duas_categorias(),
                                            slugs=ent.categorias)
    checa(cat.acoes == () and cat.entendimentos == (),
          f"uma entidade sem categoria recebeu {len(cat.acoes)} ações e "
          f"{len(cat.entendimentos)} entendimentos")
    checa(motor.avaliar(pessoa("Carreira Exemplo A"), cat) == [],
          "uma entidade sem categoria recebeu veredictos")
    print("  ok     sem declaração: nenhuma ação, nenhum veredicto")


def teste_categoria_declarada_que_nao_existe_e_erro():
    """Erro de digitação no cadastro deixaria o sindicato sem catálogo e
    ninguém entenderia por quê. Falha alto."""
    pasta = duas_categorias()
    try:
        entendimentos.carregar_categorias(pasta, slugs=("exemplo-z",))
        checa(False, "aceitou categoria que não tem arquivo")
    except entendimentos.ErroDeCatalogo as e:
        checa("exemplo-z" in str(e), f"a mensagem não diz qual: {e}")
        print("  ok     categoria declarada sem arquivo é recusada")


TESTES = [
    teste_o_catalogo_global_nao_existe_mais,
    teste_cada_arquivo_declara_a_sua_categoria_e_os_cargos,
    teste_toda_entrada_pertence_a_categoria_do_arquivo,
    teste_ajuizar_nao_oferece_tese_de_outra_carreira,
    teste_a_pessoa_recebe_a_tese_da_propria_carreira,
    teste_juntar_categorias_nao_muda_o_veredicto_de_quem_e_da_casa,
    teste_cargo_nao_reconhecido_nunca_vira_permissao,
    teste_id_repetido_em_dois_arquivos_e_erro,
    teste_cargo_reivindicado_por_duas_categorias_e_erro,
    teste_acao_de_outra_categoria_dentro_do_arquivo_e_erro,
    teste_catalogo_sem_categoria_e_erro,
    teste_a_versao_de_cada_catalogo_sobrevive_a_juncao,
    teste_acrescentar_categoria_e_acrescentar_arquivo,
    teste_participacao_nao_guarda_tabela_de_carreiras,
    teste_cargo_escrito_de_outro_jeito_casa_pelo_arquivo,
    teste_entidade_declara_as_categorias_que_contratou,
    teste_entidade_sem_categoria_nao_recebe_todas,
    teste_categoria_declarada_que_nao_existe_e_erro,
]


def main() -> int:
    print("=" * 62)
    print("CATÁLOGO POR CATEGORIA — atender mais de um sindicato")
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
