#!/usr/bin/env python3
"""
As teses acompanhadas, quem cada uma alcança, e o que mudou.

É o argumento do produto para o escritório: "o tribunal julgou o Tema X, e
312 filiados do seu cliente são alcançados — os dados já estão organizados".
Para dizer isso sem enganar ninguém, três coisas têm de valer:

1. A LISTA É A DO CATÁLOGO da carreira daquele sindicato — temas e ações —,
   com a situação de cada um e se um advogado já conferiu.
2. O NÚMERO É UMA SIMULAÇÃO, E SE CHAMA ASSIM. "Poderiam" é quantos teriam
   o caminho aberto SE a tese fosse conferida. Não é "podem": isso só depois
   de um advogado conferir, e o veredicto de ninguém muda por causa da
   simulação.
3. NOVIDADE TEM DATA. É o que o tribunal julgou ou afetou nos últimos
   trinta dias. Tema sem data não vira notícia.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import entendimentos, motor, panorama, teses  # noqa: E402

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


CATALOGO = """
[catalogo]
versao = 1
categoria = "Carreira Exemplo T"
cargos = ["carreira exemplo t"]

[[entendimentos]]
id = "EX-T-JULGADO"
tribunal = "STJ"
tema = "9001"
situacao = "julgado"
julgado_em = "2026-11-20"
questao = "Questão de exemplo julgada."
tese = "Tese de exemplo, transcrita."
trilha = "ajuizar"
criterios = ["critério de exemplo"]
fonte = "exemplo://t-julgado"

[[entendimentos]]
id = "EX-T-AFETADO"
tribunal = "STJ"
tema = "9002"
situacao = "afetado"
afetado_em = "2026-11-10"
questao = "Questão de exemplo ainda não julgada."
tese = ""
trilha = "ajuizar"
fonte = "exemplo://t-afetado"

[[entendimentos]]
id = "EX-T-ANTIGO"
tribunal = "STJ"
tema = "9003"
situacao = "julgado"
julgado_em = "2020-01-15"
questao = "Questão antiga."
tese = "Tese antiga."
trilha = "ajuizar"
criterios = ["critério"]
fonte = "exemplo://t-antigo"

[[acoes_coletivas]]
id = "EX-T-ACAO"
descricao = "Ação coletiva de exemplo T"
situacao = "transitado_em_julgado"
periodo_inicio = "2000-01"
periodo_fim = "2009-12"
exige_rol = false
fonte = "exemplo://t-acao"
"""


def catalogo():
    pasta = Path(tempfile.mkdtemp())
    (pasta / "exemplo-t.toml").write_text(CATALOGO, encoding="utf-8")
    return entendimentos.carregar_categorias(pasta, ("exemplo-t",))


def registro(cpf: str, cargo: str = "Carreira Exemplo T", **extra) -> dict:
    linha = {"cpf": cpf, "nome_completo": f"PESSOA {cpf[-2:]} (FICTÍCIA)",
             "cargo": cargo, "situacao": "aposentado",
             "filiado_desde": "2001-01", "filiado_ate": "",
             "ja_executou": "nao_sei", "tem_acao_propria": "nao_sei"}
    linha.update(extra)
    return {"protocolo": f"P-{cpf}", "linha": linha,
            "arquivos": {"contribuicao-1.pdf": "x" * 64}}


A, B, C = "11144477735", "52998224725", "01234567890"


def teste_a_lista_e_a_do_catalogo_com_a_situacao_de_cada_uma():
    secao("as teses acompanhadas")
    lista = teses.do_catalogo(catalogo())
    por_id = {t.id: t for t in lista}
    checa(set(por_id) == {"EX-T-JULGADO", "EX-T-AFETADO", "EX-T-ANTIGO",
                          "EX-T-ACAO"}, f"{sorted(por_id)}")
    j, a, acao = (por_id[k] for k in ("EX-T-JULGADO", "EX-T-AFETADO",
                                      "EX-T-ACAO"))
    checa(j.tipo == "tema" and j.rotulo == "STJ, Tema 9.001"
          and j.situacao == "julgado" and j.data == "2026-11-20"
          and j.conferida is False and j.fonte == "exemplo://t-julgado",
          f"{j}")
    checa(a.situacao == "afetado" and a.data == "2026-11-10", f"{a}")
    checa(acao.tipo == "acao" and acao.rotulo == "Ação coletiva de exemplo T",
          f"{acao}")
    conferida = teses.do_catalogo(catalogo().homologando(("EX-T-JULGADO",)))
    checa({t.id: t.conferida for t in conferida}["EX-T-JULGADO"] is True,
          "a tese homologada no catálogo não aparece como conferida")
    print("  ok     temas e ações, com situação, data, fonte e conferência")


def teste_o_impacto_e_uma_simulacao_e_nao_muda_o_veredicto_de_ninguem():
    secao("quem cada tese alcança")
    cat = catalogo()
    registros = [
        registro(A, tem_acao_propria="nao"),                 # poderia
        registro(B),                                         # depende
        registro(C, cargo="Outra Carreira Qualquer Z"),      # não reconhecida
    ]
    imp = teses.impacto(cat, registros)
    j = imp["EX-T-JULGADO"]
    checa((j["poderiam"], j["dependem"]) == (1, 2),
          f"julgado: um poderia, dois dependem de algo: {j}")
    a = imp["EX-T-AFETADO"]
    checa(a["poderiam"] == 0 and a["dependem"] == 3,
          f"tema ainda não julgado: ninguém poderia, mesmo conferido: {a}")
    # A SIMULAÇÃO NÃO VAZA: o veredicto de verdade continua sem PODE.
    de_verdade = panorama.por_pessoa(registros, cat)
    checa(not any(p.pode for p in de_verdade),
          "simular o impacto mudou o veredicto real de alguém")
    # E a tese JÁ conferida conta com o que ela diz hoje.
    conf = teses.impacto(cat.homologando(("EX-T-JULGADO",)), registros)
    checa(conf["EX-T-JULGADO"]["poderiam"] == 1, f"{conf['EX-T-JULGADO']}")
    checa(teses.impacto(cat, []) and all(
              v == {"poderiam": 0, "dependem": 0, "fora": 0}
              for v in teses.impacto(cat, []).values()),
          "base vazia devia dar zero em tudo, para toda tese")
    print("  ok     poderiam / dependem / fora — e o veredicto real não muda")


def teste_novidade_e_o_que_tem_data_recente():
    secao("as novidades")
    lista = teses.do_catalogo(catalogo())
    novas = teses.novidades(lista, hoje="2026-11-26")
    checa([(n.id, n.evento) for n in novas]
          == [("EX-T-JULGADO", "julgado"), ("EX-T-AFETADO", "afetado")],
          f"as novidades, da mais recente para a mais antiga: "
          f"{[(n.id, n.evento) for n in novas]}")
    checa(teses.novidades(lista, hoje="2027-06-01") == [],
          "novidade de seis meses atrás continua sendo notícia")
    checa(teses.novidades(lista, hoje="2026-11-19") == [
              n for n in teses.novidades(lista, hoje="2026-11-19")
              if n.id == "EX-T-AFETADO"],
          "anunciou um julgamento com data no futuro")
    frase = teses.frase_da_novidade(novas[0], sindicato="Sindicato Z",
                                    poderiam=12, dependem=30)
    checa(frase == "O STJ julgou o Tema 9.001 em 20/11/2026. No Sindicato Z, "
                   "12 pessoas poderiam entrar com a ação e outras 30 "
                   "dependem de alguma conferência. A tese ainda não foi "
                   "conferida por advogado.",
          f"a frase da novidade: {frase}")
    afet = teses.frase_da_novidade(novas[1], sindicato="Sindicato Z",
                                   poderiam=0, dependem=42)
    checa("vai julgar" in afet and "42 pessoas" in afet
          and "poderiam" not in afet,
          f"tema afetado não pode prometer nada: {afet}")
    print("  ok     só o que tem data nos últimos trinta dias, em frase")


TESTES.extend([
    teste_a_lista_e_a_do_catalogo_com_a_situacao_de_cada_uma,
    teste_o_impacto_e_uma_simulacao_e_nao_muda_o_veredicto_de_ninguem,
    teste_novidade_e_o_que_tem_data_recente,
])


# ------------------------------------------------- o aviso da manhã

class _Correio:
    def __init__(self, fora: bool = False) -> None:
        self.mandadas: list[tuple[str, str, str]] = []
        self.fora = fora

    def enviar_mensagem(self, destino, assunto, corpo):
        if self.fora:
            raise OSError("correio fora do ar")
        self.mandadas.append((destino, assunto, corpo))


DEMO = {"PROTOCOL_CATEGORIAS_DA_DEMONSTRACAO":
        str(RAIZ / "implantacao" / "demo" / "categorias"),
        "PROTOCOL_MODO_ENSAIO": "1"}


def _sindicato():
    """Um sindicato em disco, com a carreira fictícia da demonstração, um
    gestor, um escritório contratado e duas pessoas no diário."""
    import json

    from servidor import deposito, entidades, escritorios

    raiz = Path(tempfile.mkdtemp(prefix="teses-"))
    ent = entidades.Cadastro(raiz).criar(
        "demo-teses", "Sindicato de Exemplo",
        categorias=("servidor-de-exemplo",))
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "gestores.csv").write_text(
        "cpf,email\n52998224725,gestor@exemplo.invalid\n", encoding="utf-8")
    (pasta / escritorios.CADASTRO).write_text(json.dumps({"escritorios": [
        {"id": "exemplo-a", "nome": "Escritório de Exemplo A (fictício)",
         "contato": "", "acoes": [],
         "pessoas": [{"cpf": "01234567890",
                      "email": "equipe@exemplo-a.invalid"}]}]}),
        encoding="utf-8")
    for r in (registro(A, cargo="Servidor de Exemplo", tem_acao_propria="nao"),
              registro(B, cargo="Servidor de Exemplo")):
        deposito.anexar_com_fsync(pasta / deposito.DIARIO,
                                  json.dumps(r) + "\n")
    return ent, raiz


def teste_a_novidade_e_avisada_uma_vez_a_quem_decide():
    """O "bom dia" do escritório: o tribunal julgou, tantas pessoas do seu
    cliente seriam alcançadas. Vai para o escritório contratado e para a
    diretoria; não leva nome de ninguém; e não repete no dia seguinte."""
    secao("o aviso da manhã")
    from servidor import vigia

    ent, raiz = _sindicato()
    visao = vigia.da_entidade(ent, raiz, ambiente=DEMO, hoje="2026-11-26")
    checa(len(visao["novidades"]) >= 1
          and "julgou" in visao["novidades"][0]["frase"]
          and "1 pessoa poderia" in visao["novidades"][0]["frase"],
          f"a novidade do sindicato: {visao['novidades']}")
    correio = _Correio()
    r = vigia.avisar_novidades(ent, raiz, correio=correio, ambiente=DEMO,
                               hoje="2026-11-26")
    checa(r["novas"] >= 1 and r["avisados"] == 2 and r["falharam"] == 0,
          f"{r}")
    checa(sorted(m[0] for m in correio.mandadas)
          == ["equipe@exemplo-a.invalid", "gestor@exemplo.invalid"],
          f"devia ir ao escritório e ao gestor: {[m[0] for m in correio.mandadas]}")
    assunto, corpo = correio.mandadas[0][1:]
    checa("Bom dia" in corpo and "julgou" in corpo and "simulação" in corpo
          and "Sindicato de Exemplo" in corpo
          and A not in corpo and "PESSOA" not in corpo
          and "\n" not in assunto,
          f"o aviso da manhã: {corpo}")
    de_novo = vigia.avisar_novidades(ent, raiz, correio=correio, ambiente=DEMO,
                                     hoje="2026-11-27")
    checa(de_novo["novas"] == 0 and len(correio.mandadas) == 2,
          "avisou a mesma novidade duas vezes")
    print("  ok     vai ao escritório e ao gestor, uma vez, sem nome de ninguém")


def teste_aviso_que_nao_saiu_e_tentado_de_novo():
    from servidor import vigia

    ent, raiz = _sindicato()
    r = vigia.avisar_novidades(ent, raiz, correio=_Correio(fora=True),
                               ambiente=DEMO, hoje="2026-11-26")
    checa(r["avisados"] == 0 and r["falharam"] == 2, f"{r}")
    bom = _Correio()
    vigia.avisar_novidades(ent, raiz, correio=bom, ambiente=DEMO,
                           hoje="2026-11-27")
    checa(len(bom.mandadas) == 2,
          "a novidade que não saiu foi dada por avisada")
    print("  ok     correio fora: a novidade continua por avisar")


def teste_a_ferramenta_do_agendador_avisa_as_teses():
    import os
    import subprocess

    from servidor import agenda

    ent, raiz = _sindicato()
    r = subprocess.run(
        [sys.executable, str(RAIZ / "ferramentas" / "avisar_teses.py"),
         "--entidade", ent.apelido, "--raiz", str(raiz)],
        capture_output=True, text=True,
        env={**os.environ, **DEMO, "PROTOCOL_DATABASE_URL": ""})
    checa(r.returncode == 0, f"{r.returncode} {r.stdout} {r.stderr[-400:]}")
    checa(A not in r.stdout + r.stderr, "a saída da ferramenta levou CPF")
    checa("teses" in agenda.TAREFAS,
          "o aviso das teses não é tarefa do agendador")
    print("  ok     a ferramenta roda, e o agendador a conhece")


TESTES.extend([
    teste_a_novidade_e_avisada_uma_vez_a_quem_decide,
    teste_aviso_que_nao_saiu_e_tentado_de_novo,
    teste_a_ferramenta_do_agendador_avisa_as_teses,
])


def main() -> int:
    print("=" * 70)
    print("TESES — o que se acompanha, quem alcança, e o que mudou")
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
