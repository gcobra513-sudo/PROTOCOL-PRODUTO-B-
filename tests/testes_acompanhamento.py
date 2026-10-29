#!/usr/bin/env python3
"""
O coletor de movimentação: o carrapato.

NENHUM TESTE DAQUI TOCA A REDE. `coletar` recebe a função de consulta por
parâmetro, e as suítes injetam uma. Teste que depende do DataJud levaria 22 a
43 s por caso — medido — e ficaria vermelho quando o CNJ estivesse fora do ar,
que é exatamente quando eu preciso confiar na suíte.

O QUE ESTA SUÍTE PROTEGE, e são três coisas que o fluxo feliz não encosta:

**Falso silêncio.** A promessa do produto é "a gente te avisa". Um timeout do
DataJud que vire "nada novo" é o pior defeito possível aqui: o filiado fica
sem saber de uma sentença porque a nossa rede piscou, e ninguém percebe —
nem ele, nem nós. Falha tem de ser falha, nominal, e visível para quem agenda
a coleta.

**Dois graus do mesmo número.** O DataJud devolve G1 e G2 como registros
separados do MESMO `numeroProcesso`. Sem o grau na chave, cada coleta
"descobriria" de novo todos os movimentos do outro grau.

**Tribunal que não existe.** O alias sai do próprio número. `J=0` e `TR=99`
não têm alias, e sem trava viraria requisição a um índice inexistente — a
cada coleta, para sempre, porque o número ficaria na base.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from servidor import acompanhamento  # noqa: E402

TRF1 = "00012347020194013400"
TJDFT = "00076540520198070001"
TJSP = "00012344720198260100"
TRT10 = "00012344320195100003"
STJ = "00012349620193000000"
STF = "00012346420191000000"
SEM_TRIBUNAL = "00012344320194993400"   # J=4, TR=99
SEM_SEGMENTO = "00012340620190013400"   # J=0

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def mov(numero: str, grau: str, data: str, nome: str):
    return acompanhamento.Movimento(
        numero=numero, grau=grau, data=data, nome=nome
    )


def fonte(numero: str, grau: str, movimentos: list[tuple[str, str]]) -> dict:
    """Um `_source` como o DataJud devolve."""
    return {
        "numeroProcesso": numero,
        "grau": grau,
        "movimentos": [{"dataHora": d, "nome": n} for d, n in movimentos],
    }


# -------------------------------------------------------------------- aliases

def teste_alias_sai_do_proprio_numero():
    secao("o alias vem do número")
    for numero, esperado in (
        (TRF1, "api_publica_trf1"),
        (TJDFT, "api_publica_tjdft"),
        (TJSP, "api_publica_tjsp"),
        (TRT10, "api_publica_trt10"),
        (STJ, "api_publica_stj"),
    ):
        obtido = acompanhamento.alias_do_numero(numero)
        checa(obtido == esperado,
              f"{numero}: alias {obtido!r}, esperava {esperado!r}")
    print("  ok     TRF1, TJDFT, TJSP, TRT10 e STJ resolvidos pelo número")


def teste_tribunal_que_nao_existe_para_antes_de_sair_na_rede():
    """Review Focus 5. A trava é ANTES da requisição, não depois do 404:
    o número fica na base e seria tentado a cada coleta, para sempre."""
    for ruim in (SEM_TRIBUNAL, SEM_SEGMENTO, "123", ""):
        try:
            alias = acompanhamento.alias_do_numero(ruim)
        except acompanhamento.TribunalDesconhecido:
            continue
        checa(False, f"aceitou {ruim!r} e devolveu {alias!r}")
    print("  ok     segmento e tribunal inexistentes falham fechado")


def teste_o_stf_nao_tem_alias_e_isso_e_dito():
    """Medido em 29/10/2026: `api_publica_stf` devolve index_not_found, e a
    lista oficial de 65 endpoints não cita o STF. Há material comercial na
    internet afirmando o contrário — a API diz que não."""
    checa(not any("stf" in a for a in acompanhamento.ALIASES.values()),
          "inventou alias para o STF")
    try:
        acompanhamento.alias_do_numero(STF)
        checa(False, "número do STF devia falhar fechado")
    except acompanhamento.TribunalDesconhecido as e:
        checa("STF" in str(e) or "stf" in str(e).lower(),
              f"a mensagem não explica que é o STF: {e}")
    print("  ok     STF falha fechado, e a mensagem diz por quê")


def teste_sao_os_65_tribunais_medidos():
    checa(len(set(acompanhamento.ALIASES.values())) == 65,
          f"a tabela tem {len(set(acompanhamento.ALIASES.values()))} aliases "
          f"distintos; a lista oficial tem 65")
    print("  ok     65 aliases distintos, como a lista oficial")


# ------------------------------------------------------------------ novidades

def teste_mesmo_numero_em_dois_graus_nao_colide():
    """Review Focus 3."""
    secao("novidades")
    g1 = mov(TRF1, "G1", "2026-10-01", "Distribuição")
    g2 = mov(TRF1, "G2", "2026-10-01", "Distribuição")
    checa(g1.chave != g2.chave, "G1 e G2 colapsaram numa chave só")
    checa(acompanhamento.novidades([g1, g2], [g1, g2]) == [],
          "repetiu movimento já visto")
    print("  ok     G1 e G2 são chaves distintas, e recoleta não repete")


def teste_movimento_novo_e_so_o_que_nao_estava_antes():
    antes = [mov(TRF1, "G1", "2026-10-01", "Distribuição")]
    agora = antes + [mov(TRF1, "G1", "2026-10-20", "Sentença")]
    novos = acompanhamento.novidades(antes, agora)
    checa([m.nome for m in novos] == ["Sentença"],
          f"novidades erradas: {[m.nome for m in novos]}")
    print("  ok     só o que não estava antes")


def teste_movimento_que_desapareceu_nao_e_novidade():
    """O tribunal às vezes reclassifica e um movimento sai da lista. Isso não
    é novidade, e tratar ausência como evento criaria aviso do nada."""
    antes = [mov(TRF1, "G1", "2026-10-01", "Distribuição"),
             mov(TRF1, "G1", "2026-10-02", "Juntada")]
    agora = [mov(TRF1, "G1", "2026-10-01", "Distribuição")]
    checa(acompanhamento.novidades(antes, agora) == [],
          "movimento que saiu da lista virou novidade")
    print("  ok     movimento que saiu da lista não vira aviso")


# -------------------------------------------------------------------- coletar

def teste_coleta_agrupa_por_tribunal():
    secao("coleta")
    chamadas: list[tuple[str, tuple[str, ...]]] = []

    def espiao(numeros, chave, alias, timeout=0):
        chamadas.append((alias, tuple(sorted(numeros))))
        return {n: [fonte(n, "G1", [("2026-10-01", "Distribuição")])]
                for n in numeros}

    movs, erros = acompanhamento.coletar(
        [TRF1, TJDFT, TJSP], consultar=espiao)
    checa(erros == [], f"erros inesperados: {erros}")
    checa(len(movs) == 3, f"movimentos: {len(movs)}")
    checa(len(chamadas) == 3,
          f"esperava uma chamada por tribunal, houve {len(chamadas)}")
    print("  ok     uma chamada por tribunal, não uma por processo")


def teste_falha_de_rede_nao_vira_nada_novo():
    """Review Focus 4: o defeito mais grave possível neste módulo."""
    from ferramentas import conferir_datajud  # noqa: F401

    def explode(numeros, chave, alias, timeout=0):
        raise acompanhamento.ErroDeConsulta("HTTP 500 no DataJud")

    movs, erros = acompanhamento.coletar([TRF1], consultar=explode)
    checa(movs == [], f"inventou movimento depois de erro: {movs}")
    checa(len(erros) == 1 and "500" in erros[0],
          f"engoliu a falha: {erros}")
    checa(TRF1 in erros[0] or "trf1" in erros[0],
          f"a falha não diz de qual tribunal ou processo: {erros[0]}")
    print("  ok     erro de consulta é relatado, não silenciado")


def teste_um_tribunal_fora_do_ar_nao_derruba_os_outros():
    def meio_quebrado(numeros, chave, alias, timeout=0):
        if alias == "api_publica_tjdft":
            raise acompanhamento.ErroDeConsulta("timeout")
        return {n: [fonte(n, "G1", [("2026-10-01", "Distribuição")])]
                for n in numeros}

    movs, erros = acompanhamento.coletar([TRF1, TJDFT], consultar=meio_quebrado)
    checa(len(movs) == 1 and movs[0].numero == TRF1,
          f"o TRF1 foi perdido junto com o TJDFT: {movs}")
    checa(len(erros) == 1, f"erros: {erros}")
    print("  ok     tribunal fora do ar não leva os outros")


def teste_numero_invalido_nao_chega_na_rede():
    chamadas = []

    def espiao(numeros, chave, alias, timeout=0):
        chamadas.append(alias)
        return {n: [] for n in numeros}

    movs, erros = acompanhamento.coletar([SEM_TRIBUNAL], consultar=espiao)
    checa(chamadas == [], f"um número sem alias chegou na rede: {chamadas}")
    checa(len(erros) == 1, f"não relatou o número impossível: {erros}")
    checa(movs == [], "devolveu movimento de número impossível")
    print("  ok     número sem alias é relatado sem sair na rede")


def teste_processo_sem_registro_nao_e_erro():
    """Defasagem de ~1 dia: processo protocolado ontem pode não estar lá. Isso
    é estado normal, não falha — e tratar como falha faria o agendador gritar
    todo dia."""
    def vazio(numeros, chave, alias, timeout=0):
        return {n: [] for n in numeros}

    movs, erros = acompanhamento.coletar([TRF1], consultar=vazio)
    checa(movs == [] and erros == [],
          f"processo sem registro virou erro: movs={movs} erros={erros}")
    print("  ok     processo ainda não indexado não é erro")


def teste_movimento_sem_data_ou_sem_nome_nao_entra():
    """Registro incompleto do tribunal. Entrar com data vazia faria a chave
    colidir com outro movimento sem data, e os dois se esconderiam."""
    def torto(numeros, chave, alias, timeout=0):
        return {n: [{"numeroProcesso": n, "grau": "G1", "movimentos": [
            {"dataHora": "", "nome": "Sem data"},
            {"dataHora": "2026-10-01", "nome": ""},
            {"dataHora": "2026-10-02", "nome": "Boa"},
        ]}] for n in numeros}

    movs, erros = acompanhamento.coletar([TRF1], consultar=torto)
    checa([m.nome for m in movs] == ["Boa"],
          f"deixou entrar movimento incompleto: {[m.nome for m in movs]}")
    print("  ok     movimento sem data ou sem nome é descartado")


def teste_numero_repetido_na_entrada_nao_gera_movimento_duplicado():
    """ACHADO NA REVISÃO (Minor 1), reclassificado por efeito.

    Dois filiados na MESMA ação coletiva é o caso óbvio e comum. O número
    repetido era anexado duas vezes ao grupo do alias e reexpandido, gerando
    `Movimento`s com chave idêntica — e `novidades` reportava os dois. O
    efeito não é teórico: é a pessoa recebendo dois avisos do mesmo andamento.
    """
    secao("entrada repetida")

    def devolve(numeros, chave, alias, timeout=0):
        return {n: [fonte(n, "G1", [("2026-10-01", "Distribuição")])]
                for n in numeros}

    movs, erros = acompanhamento.coletar([TRF1, TRF1, TRF1], consultar=devolve)
    checa(len(movs) == 1,
          f"número repetido gerou {len(movs)} movimentos para o mesmo fato")
    checa(acompanhamento.novidades([], movs) == movs,
          "novidades deixou de ser idempotente")
    print("  ok     número repetido na entrada não duplica movimento")


def teste_pedaco_sem_digito_nao_vira_consulta():
    """ACHADO NA REVISÃO (Minor 10). Lixo no campo vinha do diário como
    número vazio e chegava em `_por_alias` como erro espúrio — ruído no
    canal cujo valor inteiro é ser sinal."""
    from servidor import validacao

    checa(validacao.numeros_de_acompanhamento("abc;;  ;%s" % TRF1) == [TRF1],
          f"pedaço sem dígito virou número: "
          f"{validacao.numeros_de_acompanhamento('abc;;%s' % TRF1)}")
    print("  ok     pedaço sem dígito é descartado antes de virar consulta")


def teste_resposta_parcial_do_datajud_e_falha_nao_silencio():
    """I7 — ACHADO NA REVISÃO.

    O Elasticsearch devolve HTTP 200 com `timed_out: true` e/ou
    `_shards.failed > 0` em falha parcial — e `docs/achados_datajud.md` §4
    MEDIU exatamente esse regime (o tjdft estourou 60 s). Vinha de volta como
    menos movimentos e ZERO falhas: falso silêncio, no único lugar onde ele é
    o pior defeito possível.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cd", RAIZ / "ferramentas" / "conferir_datajud.py")
    cd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cd)

    for parcial in ({"timed_out": True}, {"_shards": {"failed": 1, "total": 5}}):
        corpo = {"hits": {"hits": []}, **parcial}
        try:
            cd.conferir_resposta(corpo)
            checa(False, f"resposta parcial passou como boa: {parcial}")
        except cd.ErroDataJud:
            pass
    cd.conferir_resposta({"hits": {"hits": []},
                          "_shards": {"failed": 0, "total": 5}})
    print("  ok     timed_out e shard com falha viram erro, não silêncio")


def teste_lote_pede_resultados_suficientes():
    """I7, segunda metade. `size = 2 * len(numeros)` capava um lote de 100 em
    200 documentos; um processo em G1+G2+JE já estoura a média, e o excedente
    some sem erro — lido depois como "sem registro, defasagem é normal"."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cd", RAIZ / "ferramentas" / "conferir_datajud.py")
    cd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cd)

    checa(cd.TAMANHO_DA_RESPOSTA >= 4,
          f"o fator de documentos por processo é {cd.TAMANHO_DA_RESPOSTA}, e "
          f"um processo pode existir em G1, G2, JE e tribunal superior")
    print(f"  ok     a consulta pede {cd.TAMANHO_DA_RESPOSTA} documentos por processo")



TESTES.extend([
    teste_alias_sai_do_proprio_numero,
    teste_tribunal_que_nao_existe_para_antes_de_sair_na_rede,
    teste_o_stf_nao_tem_alias_e_isso_e_dito,
    teste_sao_os_65_tribunais_medidos,
    teste_mesmo_numero_em_dois_graus_nao_colide,
    teste_movimento_novo_e_so_o_que_nao_estava_antes,
    teste_movimento_que_desapareceu_nao_e_novidade,
    teste_coleta_agrupa_por_tribunal,
    teste_falha_de_rede_nao_vira_nada_novo,
    teste_um_tribunal_fora_do_ar_nao_derruba_os_outros,
    teste_numero_invalido_nao_chega_na_rede,
    teste_processo_sem_registro_nao_e_erro,
    teste_movimento_sem_data_ou_sem_nome_nao_entra,
    teste_numero_repetido_na_entrada_nao_gera_movimento_duplicado,
    teste_pedaco_sem_digito_nao_vira_consulta,
    teste_resposta_parcial_do_datajud_e_falha_nao_silencio,
    teste_lote_pede_resultados_suficientes,
])


def main() -> int:
    print("=" * 70)
    print("ACOMPANHAMENTO — o coletor, sem tocar a rede")
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
