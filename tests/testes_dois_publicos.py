#!/usr/bin/env python3
"""
Toda frase do motor tem DOIS leitores, e cada um lê a sua.

O motor explica cada resposta: "esta pessoa consta do rol", "esta pessoa já
executou este título". Em terceira pessoa, porque a frase vai para o
veredicto guardado — a prova, que advogado e sindicato leem. Só que a MESMA
frase ia para a tela do próprio filiado, e lá ela lê como dossiê sobre outra
pessoa: quem abre "Minhas ações" e encontra "esta pessoa está fora do rol"
não sabe que é dela que se fala (T7).

Trocar "esta pessoa" por "você" no texto pronto não serve: "esta pessoa é
filiada" concorda com *pessoa*, e viraria "você é filiada" para um homem.
Então cada frase é ESCRITA duas vezes, na origem, por quem sabe o que ela
diz — e a segunda nunca usa adjetivo que dependa de quem lê.

O QUE ESTES TESTES FIXAM:

1. Não existe frase com um leitor só: o motor recusa texto cru.
2. A do filiado não fala dele em terceira pessoa, nem erra a concordância.
3. A do sindicato não chama o gestor de "você".
4. As duas saem da MESMA decisão: mesma quantidade, mesma ordem.
"""
from __future__ import annotations

import ast
import dataclasses
import itertools
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import dito, entendimentos, motor, participacao, pendencia  # noqa: E402

CATEGORIAS = RAIZ / "config" / "categorias"

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


# ----------------------------------------------------------- a matriz

def _catalogos() -> list[entendimentos.Catalogo]:
    """Catálogos que, juntos, levam o motor a cada ramo que escreve frase."""
    cru = entendimentos.carregar_categorias(CATEGORIAS)
    tudo = tuple(a.id for a in cru.acoes) + tuple(e.id for e in cru.entendimentos)
    hom = cru.homologando(tudo)
    gifa = hom.de("GIFA-2006")

    def com_acao(**trocas):
        return dataclasses.replace(
            hom, acoes=(dataclasses.replace(gifa, **trocas),))

    return [
        cru,                                    # nada homologado
        hom,                                    # tudo homologado
        cru.homologando(("GIFA-2006",)),        # o Tema 1.302 NÃO homologado
        com_acao(exige_rol=True),               # ação que exige rol
        com_acao(periodo_inicio=""),            # ação sem período
        com_acao(ajuizada_em="2012-01-01"),     # com prescrição a contar
        com_acao(situacao="em andamento"),      # coletiva não transitada
    ]


def _fatos():
    base = dict(cpf="11144477735", nome="PESSOA DE EXEMPLO (FICTÍCIA)",
                situacao="aposentado", data_ingresso="1992-04-01")
    for (titulo, rol, executou, propria, cargo, desde, entregues) in \
            itertools.product(
                (None, True, False), (None, True, False), (None, True, False),
                (None, True, False),
                ("Auditor-Fiscal da Receita Federal do Brasil", "",
                 "Cargo Que Ninguém Conhece",
                 "Analista Tributário da Receita Federal do Brasil"),
                ("1992-05", "", "2015-01"),
                ((), ("sentenca",))):
        yield motor.Fatos(**base, cargo=cargo, filiado_desde=desde,
                          tem_titulo=titulo, no_rol=rol, ja_executou=executou,
                          tem_acao_propria=propria,
                          documentos_entregues=entregues)


def _todas_as_frases() -> dict[str, str]:
    """{frase do sindicato: frase do filiado}, de toda a matriz."""
    achadas: dict[str, str] = {}
    for cat in _catalogos():
        for fatos in _fatos():
            quem = participacao.Filiado(
                cpf=fatos.cpf, cargo=fatos.cargo, situacao=fatos.situacao,
                filiado_desde=fatos.filiado_desde, no_rol=fatos.no_rol)
            frases = [m for p in participacao.participacoes(quem, cat)
                      for m in p.motivos]
            for o in motor.avaliar(fatos, cat):
                frases += [*o.motivos, *o.notas]
            for f in frases:
                achadas[str(f)] = dito.para_voce(f)
    return achadas


# --------------------------------------------------------------- o tipo

def teste_a_frase_e_texto_comum_com_uma_segunda_leitura():
    """Continua sendo `str`: o veredicto guardado, as comparações e o JSON
    não mudam. O que muda é que ela carrega a versão do filiado."""
    secao("a frase")
    import json

    f = dito.dito("esta pessoa consta do rol", "o seu nome consta do rol")
    checa(f == "esta pessoa consta do rol" and isinstance(f, str),
          "a frase deixou de ser o texto do sindicato")
    checa(dito.para_voce(f) == "o seu nome consta do rol", "perdeu a do filiado")
    checa(json.dumps([f], ensure_ascii=False) == '["esta pessoa consta do rol"]',
          "no veredicto guardado tem de entrar o texto do sindicato")
    igual = dito.ambos("a ação não declara o período que cobre")
    checa(dito.para_voce(igual) == str(igual), "`ambos` não serve aos dois")
    for vazia in ("", "   "):
        try:
            dito.dito("esta pessoa consta do rol", vazia)
        except ValueError:
            pass
        else:
            checa(False, "aceitou frase do filiado vazia")
    print("  ok     é texto, serve ao guardado, e carrega a leitura do filiado")


def teste_texto_cru_e_recusado_em_vez_de_sair_com_um_leitor_so():
    """A trava. Uma frase nova escrita só em terceira pessoa não chega à
    tela do filiado calada: o motor a recusa onde ela nasce."""
    cru = "esta pessoa consta do rol"
    j = motor._Juizo()
    for nome, chamada in (
        ("motivo", lambda: j.motivo(cru)),
        ("impede", lambda: j.impede(cru)),
        ("nota", lambda: j.nota(cru)),
        ("falta_saber", lambda: j.falta_saber(pendencia.VOCE, "x", cru)),
        ("Oportunidade", lambda: motor.Oportunidade(
            trilha=motor.EXECUTAR, referencia="X", rotulo="X",
            veredicto=motor.FALTA, motivos=(cru,))),
        ("Oportunidade.notas", lambda: motor.Oportunidade(
            trilha=motor.EXECUTAR, referencia="X", rotulo="X",
            veredicto=motor.FALTA, notas=(cru,))),
        ("Participacao", lambda: participacao.Participacao(
            "X", "X", participacao.INDETERMINADO, motivos=(cru,))),
        ("para_voce", lambda: dito.para_voce(cru)),
    ):
        try:
            chamada()
        except TypeError:
            continue
        checa(False, f"{nome} aceitou frase com um leitor só")
    print("  ok     texto cru: recusado no juízo, na oportunidade e na participação")


def teste_nenhuma_frase_e_escrita_direto_no_motor():
    """A matriz abaixo exercita os ramos — mas um ramo que ela não alcance
    só mostraria o defeito em produção, como erro na tela de alguém. Este
    lê o CÓDIGO: toda frase passada ao juízo, e todo motivo de participação,
    é montada por `dito`, `ambos` ou `nao_homologado`."""
    fabricas = {"dito", "ambos", "nao_homologado"}

    def e_frase(no: ast.AST) -> bool:
        if isinstance(no, ast.IfExp):
            return e_frase(no.body) and e_frase(no.orelse)
        if isinstance(no, ast.Call):
            alvo = no.func
            nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", "")
            return nome in fabricas
        # Uma variável: foi montada antes, e a montagem é conferida onde está.
        return isinstance(no, (ast.Name, ast.Attribute, ast.Starred))

    crus: list[str] = []
    for arquivo, posicoes in (("nucleo/motor.py", {"motivo": 0, "impede": 0,
                                                   "nota": 0, "falta_saber": 2}),
                              ("nucleo/participacao.py", {})):
        arvore = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            if isinstance(no.func, ast.Attribute):
                metodo = no.func.attr
                dono = getattr(no.func.value, "id", "")
                if dono == "j" and metodo in posicoes:
                    arg = no.args[posicoes[metodo]]
                    if not e_frase(arg):
                        crus.append(f"{arquivo}:{no.lineno} j.{metodo}")
                if dono == "motivos" and metodo == "append":
                    if not e_frase(no.args[0]):
                        crus.append(f"{arquivo}:{no.lineno} motivos.append")
            for kw in no.keywords:
                if kw.arg in ("motivos", "notas") and isinstance(kw.value, ast.Tuple):
                    for elemento in kw.value.elts:
                        if not e_frase(elemento):
                            crus.append(f"{arquivo}:{no.lineno} {kw.arg}=(...)")
    checa(crus == [], f"frase escrita direto, com um leitor só: {crus}")
    print("  ok     no código, toda frase nasce com os dois leitores")


# --------------------------------------------------- o que cada um lê

#: Como a frase do filiado NÃO pode falar dele.
TERCEIRA = re.compile(
    r"\besta pessoa\b|\ba pessoa\b|\bdela\b|\bdele\b|\bela\b|\beste cpf\b",
    re.IGNORECASE)
#: Adjetivo que concorda com quem lê — e nós não sabemos quem lê.
CONCORDANCIA = re.compile(
    r"\bvocê (é|está|foi|era|fica|ficou) \w*[oa]\b"
    r"|\b(filiad|aposentad|substituíd|obrigad|inscrit|cadastrad|enquadrad)[oa]\b",
    re.IGNORECASE)
#: Como a frase do sindicato NÃO pode falar com o gestor.
SEGUNDA = re.compile(r"\bvocê\b|\bseus?\b|\bsuas?\b|\bsabemos\b", re.IGNORECASE)


def teste_a_frase_do_filiado_fala_com_ele():
    secao("o que cada um lê")
    frases = _todas_as_frases()
    checa(len(frases) >= 25,
          f"a matriz alcançou só {len(frases)} frases: ela encolheu, e o "
          f"teste deixou de conferir o que diz conferir")
    for sindicato, voce in sorted(frases.items()):
        achou = TERCEIRA.search(voce)
        checa(achou is None,
              f"a frase do FILIADO fala dele em terceira pessoa "
              f"({achou.group(0) if achou else ''!r}): {voce!r}")
        achou = CONCORDANCIA.search(voce)
        checa(achou is None,
              f"a frase do FILIADO depende de quem lê para concordar "
              f"({achou.group(0) if achou else ''!r}): {voce!r}")
    print(f"  ok     {len(frases)} frases: nenhuma fala do filiado como de outra pessoa")


def teste_a_frase_do_sindicato_nao_chama_o_gestor_de_voce():
    """O veredicto guardado é lido por advogado e por gestor. "Você já
    executou este título", ali, acusa quem está lendo."""
    for sindicato in sorted(_todas_as_frases()):
        achou = SEGUNDA.search(sindicato)
        checa(achou is None,
              f"a frase do SINDICATO fala com o leitor "
              f"({achou.group(0) if achou else ''!r}): {sindicato!r}")
    print("  ok     a do sindicato continua em terceira pessoa")


def teste_as_duas_dizem_a_mesma_coisa():
    """Mesma decisão, duas redações. Onde a do sindicato fala de pessoa, a
    do filiado tem de falar com ele — e não virar frase genérica; e os
    dados (rótulo da ação, datas, cargo) têm de estar nas duas."""
    frases = _todas_as_frases()
    de_pessoa = {s: v for s, v in frases.items() if TERCEIRA.search(s)}
    checa(len(de_pessoa) >= 10,
          f"só {len(de_pessoa)} frases falam da pessoa: a matriz encolheu")
    for sindicato, voce in sorted(de_pessoa.items()):
        checa(SEGUNDA.search(voce) is not None,
              f"a do sindicato fala da pessoa e a do filiado não fala com "
              f"ele:\n      {sindicato!r}\n      {voce!r}")
    for sindicato, voce in sorted(frases.items()):
        for dado in re.findall(r"\d{2}/\d{4}|\d{4}-\d{2}|GIFA|Tema [\d.]+|FORA",
                               sindicato):
            checa(dado in voce,
                  f"{dado!r} está na frase do sindicato e sumiu da do "
                  f"filiado: {voce!r}")
    print(f"  ok     {len(de_pessoa)} frases sobre a pessoa: as duas redações batem")


def teste_cada_oportunidade_tem_as_duas_listas_do_mesmo_tamanho():
    cat = _catalogos()[1]
    fatos = motor.Fatos(cpf="11144477735",
                        cargo="Auditor-Fiscal da Receita Federal do Brasil",
                        filiado_desde="1992-05", tem_titulo=True, no_rol=False,
                        ja_executou=False, tem_acao_propria=False)
    for o in motor.avaliar(fatos, cat):
        do_filiado = [dito.para_voce(m) for m in o.motivos]
        checa(len(do_filiado) == len(o.motivos) and all(do_filiado),
              f"{o.referencia}: listas de tamanhos diferentes")
    gifa = next(o for o in motor.avaliar(fatos, cat)
                if o.referencia == "GIFA-2006")
    juntas = " ".join(dito.para_voce(m) for m in gifa.motivos)
    checa("FORA do rol" in juntas and "seu" in juntas.lower(),
          f"fora do rol, dito ao filiado: {juntas!r}")
    checa("esta pessoa está FORA do rol" in " ".join(gifa.motivos),
          f"fora do rol, no guardado: {gifa.motivos}")
    print("  ok     a mesma oportunidade, lida pelos dois")


# --------------------------------------------------- os títulos do painel

def teste_o_painel_do_sindicato_nao_le_titulo_escrito_para_o_filiado():
    """O defeito espelhado. Na lista "tudo o que está parado" do painel, a
    pendência que é DO FILIADO aparecia com o rótulo "O que depende de você"
    — e quem lê o painel é o gestor."""
    secao("os títulos, por leitor")
    for dono in pendencia.DONOS:
        do_sindicato = pendencia.TITULOS_DO_SINDICATO[dono]
        explicacao = pendencia.EXPLICACOES_DO_SINDICATO[dono]
        checa(not re.search(r"\bvocê\b", do_sindicato + " " + explicacao,
                            re.IGNORECASE),
              f"{dono}: o texto do sindicato chama o gestor de você: "
              f"{do_sindicato!r} / {explicacao!r}")
    checa("filiado" in pendencia.TITULOS_DO_SINDICATO[pendencia.VOCE].lower(),
          "a pendência do filiado não diz, ao gestor, que é do filiado")
    checa("você" in pendencia.TITULOS[pendencia.VOCE].lower(),
          "o título do FILIADO deixou de falar com ele")
    print("  ok     cada dono tem um título para o filiado e outro para o gestor")


TESTES.extend([
    teste_a_frase_e_texto_comum_com_uma_segunda_leitura,
    teste_texto_cru_e_recusado_em_vez_de_sair_com_um_leitor_so,
    teste_nenhuma_frase_e_escrita_direto_no_motor,
    teste_a_frase_do_filiado_fala_com_ele,
    teste_a_frase_do_sindicato_nao_chama_o_gestor_de_voce,
    teste_as_duas_dizem_a_mesma_coisa,
    teste_cada_oportunidade_tem_as_duas_listas_do_mesmo_tamanho,
    teste_o_painel_do_sindicato_nao_le_titulo_escrito_para_o_filiado,
])


def main() -> int:
    print("=" * 70)
    print("DOIS PÚBLICOS — a frase do sindicato e a frase do filiado")
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
        for f in falhas[:40]:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
