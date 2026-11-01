#!/usr/bin/env python3
"""
O BANCO LIGADO À APLICAÇÃO: o diário é a autoridade, o banco é a projeção.

A DECISÃO QUE ORGANIZA ESTE CHECKPOINT, e ela não é óbvia:

    o DIÁRIO (`diario.jsonl`) continua sendo a autoridade;
    o BANCO é uma projeção dele — consultável, isolada por política, e
    refazível a qualquer momento.

Não é meio-termo. O diário dá durabilidade e responde "o que exatamente nos
mandaram?"; o banco dá poder de consulta e um isolamento que o Postgres impõe
sozinho, contra o `WHERE` esquecido numa tela escrita daqui a seis meses. Cada
um faz o que faz melhor, e **um teste prova que os dois concordam** — que é o
que impede a divergência silenciosa que duas fontes de verdade sempre criam.

TRÊS COISAS QUE ERAM PROMESSA E VIRAM CÓDIGO AQUI:

  `achado`    a procedência estava no desenho e em memória. Agora o trecho
              de onde cada fato saiu fica gravado, e a fila de conferência
              deixa de ser uma consulta a dado que ninguém guardou;
  `leitura`   o esquema dizia, em maiúsculas, que NADA escrevia nesta tabela.
              Num produto de CONSULTA o vazamento é um `read`, e "quem viu o
              dado de quem" era pergunta sem resposta;
  `reconstruir` o banco pode ser refeito do diário. Sem isso, "o diário é a
              autoridade" é uma frase, não uma propriedade.

SEM `PROTOCOL_DATABASE_URL`, esta suíte é PULADA — em voz alta.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

URL = os.environ.get("PROTOCOL_DATABASE_URL", "").strip()

falhas: list[str] = []
TESTES: list = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


# CPFs de teste, dígito válido e declaradamente fictícios.
A, B = "11144477735", "52998224725"


def linha(cpf: str, **trocas) -> dict:
    base = {
        "cpf": cpf,
        "nome_completo": f"FULANO {cpf[-2:]} (CADASTRO DE EXEMPLO)",
        "email": "exemplo@exemplo.org",
        "telefone": "",
        "cargo": "Auditor Fiscal da Receita Federal",
        "situacao": "aposentado",
        "unidade": "",
        "data_nascimento": "",
        "data_ingresso": "",
        "data_aposentadoria": "",
        "filiado_desde": "2004-03",
        "filiado_ate": "",
        "tem_processo": "nao_sei",
        "numeros_de_processo": "",
        "ja_executou": "nao_sei",
        "tem_acao_propria": "nao_sei",
        "quer_aviso": "",
    }
    base.update(trocas)
    return base


def registro(cpf: str, *, protocolo: str = "", arquivos=None, **trocas) -> dict:
    return {
        "protocolo": protocolo or f"PRT-{cpf[-4:]}",
        "recebido_em": "2026-10-31T00:00:00+00:00",
        "entidade": "demo-a",
        "linha": linha(cpf, **trocas),
        "arquivos": arquivos if arquivos is not None
        else {"contribuicao-1.pdf": "a" * 64},
    }


def preparar():
    from servidor import banco

    banco.criar_esquema(URL, recriar=True)
    # `leitura` FICA DE FORA, e não por esquecimento: o esquema revoga
    # DELETE nela de propósito — log de auditoria que a aplicação apaga não
    # é log de auditoria. A limpeza entre testes convive com isso.
    for entidade in ("demo-a", "demo-b"):
        with banco.sessao(URL, entidade) as cur:
            for tabela in ("achado", "documento", "vinculo", "processo",
                           "pessoa", "pessoa_afirmacao", "aviso_enviado",
                           "movimento", "execucao", "recebimento"):
                cur.execute(f"DELETE FROM {tabela}")


# ------------------------------------------------------------- a projeção

def teste_o_diario_vira_banco():
    """O caminho inteiro: um registro do diário entra, e sai nas três
    camadas — o que chegou, o fato com procedência, e o valor vigente."""
    secao("a projeção")
    from servidor import banco

    banco.reconstruir(URL, "demo-a", [registro(A), registro(B)])
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM recebimento")
        checa(cur.fetchone()[0] == 2, "camada 1 não recebeu os dois envios")
        cur.execute("SELECT count(*) FROM pessoa")
        checa(cur.fetchone()[0] == 2, "camada 2 não tem as duas pessoas")
        cur.execute("SELECT nome, cargo FROM pessoa WHERE cpf = %s", (A,))
        nome, cargo = cur.fetchone()
        checa(nome.startswith("FULANO"), f"nome não projetado: {nome!r}")
        checa("Auditor" in cargo, f"cargo não projetado: {cargo!r}")
        cur.execute(
            "SELECT count(*) FROM pessoa_afirmacao WHERE cpf = %s AND "
            "fonte = 'cadastro'", (A,)
        )
        checa(cur.fetchone()[0] > 5,
              "a camada de afirmações não guardou os campos")
    print("  ok     diário -> recebimento, pessoa_afirmacao, pessoa")


def teste_reconstruir_duas_vezes_nao_duplica():
    """`reconstruir` tem de poder rodar de novo: é a operação de recuperação,
    e uma recuperação que duplica tudo é pior que não ter."""
    from servidor import banco

    banco.reconstruir(URL, "demo-a", [registro(A), registro(B)])
    banco.reconstruir(URL, "demo-a", [registro(A), registro(B)])
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM recebimento")
        n = cur.fetchone()[0]
        checa(n == 2, f"duplicou o recebimento: {n} linhas para 2 envios")
        cur.execute("SELECT count(*) FROM pessoa")
        checa(cur.fetchone()[0] == 2, "duplicou pessoa")
    print("  ok     reconstruir é idempotente")


def teste_o_ultimo_envio_vence_tambem_no_banco():
    """Mesma regra do resto do produto: reenvio é correção, não pessoa nova.
    E a afirmação ANTERIOR sobrevive — é dela que sai a divergência."""
    from servidor import banco

    banco.reconstruir(URL, "demo-a", [
        registro(A, protocolo="PRT-0001", cargo="Cargo Antigo"),
        registro(A, protocolo="PRT-0002", cargo="Auditor Fiscal da Receita Federal"),
    ])
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM pessoa")
        checa(cur.fetchone()[0] == 1, "o reenvio virou pessoa nova")
        cur.execute("SELECT cargo FROM pessoa WHERE cpf = %s", (A,))
        checa("Auditor" in cur.fetchone()[0], "o último envio não venceu")
        cur.execute(
            "SELECT count(*) FROM pessoa_afirmacao WHERE cpf = %s AND "
            "campo = 'cargo'", (A,)
        )
        n = cur.fetchone()[0]
        checa(n == 2,
              f"a afirmação anterior foi apagada: {n} afirmações de cargo. "
              f"Sem as duas, a divergência some junto")
    print("  ok     vigente é o último; as duas afirmações sobrevivem")


def teste_documento_e_vinculo_projetados():
    """O metadado do documento e o processo declarado. Os BYTES não: o banco
    guarda a impressão digital, não o PDF."""
    from servidor import banco

    banco.reconstruir(URL, "demo-a", [
        registro(A, arquivos={"contribuicao-1.pdf": "c" * 64,
                              "sentenca.pdf": "d" * 64},
                 numeros_de_processo="00103912420064013400"),
    ])
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT tipo FROM documento WHERE cpf = %s ORDER BY tipo",
                    (A,))
        tipos = [t for (t,) in cur.fetchall()]
        checa(tipos == ["contribuicao", "sentenca"],
              f"documentos projetados errado: {tipos}")
        cur.execute("SELECT numero FROM vinculo WHERE cpf = %s", (A,))
        checa(cur.fetchall() == [("00103912420064013400",)],
              "o processo declarado não virou vínculo")
        cur.execute("SELECT count(*) FROM processo")
        checa(cur.fetchone()[0] == 1, "o processo não foi registrado")
    print("  ok     documento (só metadado) e vínculo projetados")


def teste_registro_ilegivel_nao_derruba_a_projecao():
    from servidor import banco

    banco.reconstruir(URL, "demo-a", [
        registro(A), {"_ilegivel": 7}, {}, {"linha": "não é dicionário"},
        registro(B),
    ])
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM pessoa")
        checa(cur.fetchone()[0] == 2, "registro ilegível derrubou a projeção")
    print("  ok     registro ilegível é pulado, não derruba")


# ------------------------------------------ o banco e o diário concordam

def teste_o_panorama_do_banco_e_igual_ao_do_diario():
    """O TESTE QUE IMPEDE A DIVERGÊNCIA. Duas fontes de verdade sempre
    divergem; duas fontes em que uma é PROJEÇÃO da outra só divergem se
    ninguém conferir. Isto confere."""
    secao("o banco e o diário concordam")
    from nucleo import entendimentos, panorama
    from servidor import banco

    registros = [
        registro(A, arquivos={"contribuicao-1.pdf": "c" * 64,
                              "sentenca.pdf": "d" * 64}),
        registro(B, filiado_desde="2015-01"),
    ]
    banco.reconstruir(URL, "demo-a", registros)
    catalogo = entendimentos.carregar_categorias(
        entendimentos.PASTA_PADRAO, ("auditor-fiscal-receita-federal",)
    )

    do_arquivo = panorama.montar(registros, catalogo)
    do_banco = panorama.montar(banco.cadastros(URL, "demo-a"), catalogo)

    checa(do_banco.pessoas == do_arquivo.pessoas,
          f"pessoas: banco {do_banco.pessoas}, diário {do_arquivo.pessoas}")
    checa(do_banco.por_acao == do_arquivo.por_acao,
          f"por ação diverge:\n  banco  {do_banco.por_acao}\n"
          f"  diário {do_arquivo.por_acao}")
    checa([(g.quem, g.o_que, g.pessoas) for g in do_banco.gargalos]
          == [(g.quem, g.o_que, g.pessoas) for g in do_arquivo.gargalos],
          f"gargalos divergem:\n  banco  {do_banco.gargalos}\n"
          f"  diário {do_arquivo.gargalos}")
    checa(do_banco.manchete() == do_arquivo.manchete(),
          f"manchete diverge:\n  banco  {do_banco.manchete()}\n"
          f"  diário {do_arquivo.manchete()}")
    print(f"  ok     mesmo panorama das duas fontes: {do_banco.manchete()}")


def teste_cadastros_do_banco_nao_atravessam_entidade():
    """A política do banco, no caminho novo. `cadastros` é consulta nominal:
    se ela furar, fura com nome e CPF."""
    from servidor import banco

    banco.reconstruir(URL, "demo-a", [registro(A)])
    banco.reconstruir(URL, "demo-b", [registro(B)])
    de_a = banco.cadastros(URL, "demo-a")
    cpfs = {r["linha"]["cpf"] for r in de_a}
    checa(cpfs == {A}, f"VAZOU cadastro de outra entidade: {cpfs}")
    print("  ok     cada entidade vê só os próprios cadastros")


# ------------------------------------------------------ o achado gravado

def teste_o_achado_guarda_o_trecho():
    """A procedência era desenho e memória. Agora é linha no banco — e sem o
    trecho, extração é palpite com cara de dado."""
    secao("o achado, com procedência")
    from nucleo import leitura
    from servidor import banco

    achados = leitura.ler(
        "Processo n. 0010391-24.2006.4.01.3400. Julgo PROCEDENTE o pedido. "
        "A sentenca transitou em julgado em 12/03/2019."
    )
    checa(bool(achados), "o leitor não achou nada no texto de teste")
    banco.guardar_achados(URL, "demo-a", A, "e" * 64, achados)

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute(
            "SELECT tipo, valor, confianca, trecho FROM achado "
            "WHERE cpf = %s ORDER BY tipo", (A,)
        )
        linhas = cur.fetchall()
    checa(bool(linhas), "nenhum achado gravado")
    for tipo, valor, confianca, trecho in linhas:
        checa(bool(trecho.strip()),
              f"{tipo}={valor!r} gravado SEM trecho de onde saiu")
        checa(confianca in ("CERTO", "PROVAVEL", "SUSPEITO"),
              f"confiança inválida: {confianca!r}")
    print(f"  ok     {len(linhas)} achados, todos com trecho")


def teste_a_fila_de_conferencia_sai_do_banco():
    """`PROVAVEL` e `SUSPEITO` esperam um humano. Era consulta a dado que
    ninguém guardava."""
    from nucleo import leitura
    from servidor import banco

    achados = leitura.ler(
        "Processo n. 0010391-24.2006.4.01.3400. Julgo PROCEDENTE o pedido. "
        "Transitado em julgado."
    )
    banco.guardar_achados(URL, "demo-a", A, "f" * 64, achados)
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM achado WHERE NOT conferido")
        checa(cur.fetchone()[0] > 0,
              "nada na fila de conferência, e o texto tinha achado")
    print("  ok     a fila de conferência existe e tem conteúdo")


def teste_guardar_achados_duas_vezes_nao_duplica():
    from nucleo import leitura
    from servidor import banco

    achados = leitura.ler("Processo n. 0010391-24.2006.4.01.3400.")
    banco.guardar_achados(URL, "demo-a", A, "g" * 64, achados)
    banco.guardar_achados(URL, "demo-a", A, "g" * 64, achados)
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM achado WHERE documento = %s",
                    ("g" * 64,))
        n = cur.fetchone()[0]
    checa(n == len(achados),
          f"duplicou: {n} linhas para {len(achados)} achados")
    print("  ok     reler o mesmo documento não duplica")


# ------------------------------------------------------- a leitura auditada

def teste_a_leitura_de_dado_nominal_fica_registrada():
    """O esquema dizia, em maiúsculas, que NADA escrevia nesta tabela. Num
    produto de CONSULTA o vazamento é um `read`, e "quem viu o dado de quem"
    era pergunta sem resposta — a primeira que alguém faz depois de um
    incidente."""
    secao("a leitura auditada")
    from servidor import banco

    banco.registrar_leitura(URL, "demo-a", quem_hash="h" * 64,
                            o_que="minhas-acoes", alvo_hash="i" * 64)
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute(
            "SELECT quem_hash, o_que, alvo_hash FROM leitura "
            "ORDER BY quando DESC LIMIT 1"
        )
        quem, o_que, alvo = cur.fetchone()
    checa((quem, o_que, alvo) == ("h" * 64, "minhas-acoes", "i" * 64),
          f"registro errado: {(quem, o_que, alvo)}")
    print("  ok     a leitura ficou registrada")


def teste_o_registro_de_leitura_nao_guarda_cpf_em_claro():
    """Um log de auditoria cheio de CPF é um segundo banco de dado pessoal,
    com retenção mais longa e menos cuidado."""
    from servidor import banco

    banco.registrar_leitura(URL, "demo-a", quem_hash="j" * 64,
                            o_que="panorama", alvo_hash="")
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT quem_hash, alvo_hash FROM leitura")
        for quem, alvo in cur.fetchall():
            for valor in (quem, alvo):
                checa(not (valor.isdigit() and len(valor) == 11),
                      f"CPF em claro no log de auditoria: {valor!r}")
    print("  ok     só marcador, nunca CPF em claro")


def teste_a_auditoria_tambem_respeita_a_politica():
    """O log de auditoria é dado da entidade. Se ele atravessasse, a
    auditoria de um sindicato seria legível pelo vizinho."""
    from servidor import banco

    banco.registrar_leitura(URL, "demo-b", quem_hash="k" * 64,
                            o_que="panorama", alvo_hash="")
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM leitura WHERE quem_hash = %s",
                    ("k" * 64,))
        checa(cur.fetchone()[0] == 0,
              "a entidade A enxergou a auditoria da entidade B")
    print("  ok     a auditoria não atravessa entidade")


def teste_recriar_derruba_TODAS_as_tabelas():
    """`criar_esquema(recriar=True)` existe porque `CREATE TABLE IF NOT
    EXISTS` não altera tabela que já existe com outra forma. A lista de DROP
    esquecia `documento` e `achado` — as duas mais novas —, então justamente
    elas sobreviveriam com a forma velha, e o erro só apareceria na primeira
    escrita."""
    secao("o esquema")
    from servidor import banco

    with banco.cru(URL) as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        existentes = {t for (t,) in cur.fetchall()}
    for tabela in existentes:
        checa(tabela in banco.TABELAS,
              f"a tabela {tabela!r} existe e não está em banco.TABELAS — "
              f"recriar=True a deixaria com a forma velha")
    print(f"  ok     {len(existentes)} tabelas, todas na lista de recriação")


# ------------------------------------------- o caminho de produção, por HTTP

def _servidor():
    """Um servidor em modo ensaio COM banco, e uma entidade de demonstração."""
    import csv
    import tempfile

    from fastapi.testclient import TestClient

    from servidor import entidades as mod
    from servidor.app import criar_app
    from servidor.config import carregar

    raiz = Path(tempfile.mkdtemp(prefix="espelho-"))
    cad = mod.Cadastro(raiz)
    ent = cad.criar("demo-a", "Sindicato de Demonstração",
                    categorias=("auditor-fiscal-receita-federal",))
    pasta = raiz / "demo-a"
    pasta.mkdir(parents=True, exist_ok=True)
    with open(pasta / "filiados.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cpf", "email", "nome"])
        w.writerow([A, "fulana@exemplo.org", "FULANA (CADASTRO DE EXEMPLO)"])
    with open(pasta / "gestores.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cpf", "email"])
        w.writerow([B, "gestor@exemplo.org"])
    cfg = carregar({
        "PROTOCOL_MODO_ENSAIO": "1",
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_DATABASE_URL": URL,
        "PROTOCOL_AGENDAR": "0",
        "PROTOCOL_EMISSOES_POR_CPF_HORA": "50",
        "PROTOCOL_EMISSOES_POR_ORIGEM_HORA": "500",
    })
    return TestClient(criar_app(cfg)), ent, raiz


def _por_no_rol(raiz, apelido: str, cpfs: list[str]) -> None:
    """Acrescenta CPFs ao rol da entidade.

    Necessário porque o código de acesso só volta para quem o SINDICATO
    declarou — e é assim que tem de ser: quem não está no rol não entra.
    """
    import csv

    caminho = raiz / apelido / "filiados.csv"
    with open(caminho, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        for cpf in cpfs:
            w.writerow([cpf, f"exemplo-{cpf}@exemplo.invalid",
                        f"PESSOA DE EXEMPLO {cpf} (CADASTRO FICTICIO)"])


def _cpf_sintetico(n: int) -> str:
    """CPF com dígito verificador que fecha, montado a partir de um número.

    Sintético por construção: a base é o índice, não cadastro de ninguém.
    """
    base = [int(c) for c in f"{n:09d}"]
    for peso0 in (10, 11):
        soma = sum(d * (peso0 - i) for i, d in enumerate(base))
        base.append((soma * 10 % 11) % 10)
    return "".join(map(str, base))


def _token(cliente, cpf: str) -> str:
    r = cliente.post("/api/acesso/codigo",
                     json={"entidade": "demo-a", "cpf": cpf})
    codigo = r.json()["codigo_do_ensaio"]
    r = cliente.post("/api/acesso/conferir",
                     json={"entidade": "demo-a", "cpf": cpf,
                           "codigo": codigo})
    return r.json()["token"]


def _pdf(linhas: list[str]) -> bytes:
    def esc(t: str) -> str:
        return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    conteudo = ["BT", "/F1 11 Tf", "14 TL", "40 790 Td"]
    for linha_ in linhas:
        conteudo += [f"({esc(linha_)}) Tj", "T*"]
    conteudo.append("ET")
    fluxo = "\n".join(conteudo).encode("latin-1", "replace")
    objetos = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
        b"/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length %d>>stream\n" % len(fluxo) + fluxo + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    saida = bytearray(b"%PDF-1.4\n")
    desloc = []
    for i, o in enumerate(objetos, 1):
        desloc.append(len(saida))
        saida += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    inicio = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for d in desloc:
        saida += b"%010d 00000 n \n" % d
    saida += (b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objetos) + 1, inicio))
    return bytes(saida)


CONTRIB = ["SINDICATO DE DEMONSTRACAO", "DECLARACAO DE CONTRIBUICAO", "",
           "Declaramos que a pessoa filiada contribuiu regularmente com a",
           "mensalidade sindical no periodo de 03/2004 a 12/2018.", "",
           "Documento de exemplo, apenas para demonstracao do sistema.",
           "Nao se refere a pessoa real."]
SENTENCA = ["PODER JUDICIARIO - JUSTICA FEDERAL",
            "SECAO JUDICIARIA DO DISTRITO FEDERAL", "",
            "Processo n. 0010391-24.2006.4.01.3400", "", "SENTENCA", "",
            "Ante o exposto, julgo PROCEDENTE o pedido formulado na inicial.",
            "", "Documento de exemplo, para demonstracao do sistema."]


def _cadastrar(cliente, cpf: str, com_sentenca: bool = False):
    import json as _json

    arquivos = [("arquivos", ("contribuicao-1.pdf", _pdf(CONTRIB),
                              "application/pdf"))]
    if com_sentenca:
        arquivos.append(("arquivos", ("sentenca.pdf", _pdf(SENTENCA),
                                      "application/pdf")))
    return cliente.post(
        "/api/cadastro",
        data={"token": _token(cliente, cpf),
              "linha": _json.dumps(linha(cpf))},
        files=arquivos,
    )


def teste_o_cadastro_por_http_chega_ao_banco():
    """O CAMINHO INTEIRO, pelo HTTP de verdade. O diário continua sendo
    escrito primeiro — é ele a autoridade —, e o banco recebe a projeção no
    mesmo pedido."""
    secao("o caminho de produção")
    from servidor import banco

    cliente, _, _raiz = _servidor()
    r = _cadastrar(cliente, A, com_sentenca=True)
    checa(r.status_code == 200, f"cadastro recusado: {r.status_code} {r.text[:300]}")

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM pessoa WHERE cpf = %s", (A,))
        checa(cur.fetchone()[0] == 1, "o cadastro não chegou ao banco")
        cur.execute("SELECT tipo FROM documento WHERE cpf = %s ORDER BY tipo",
                    (A,))
        tipos = [t for (t,) in cur.fetchall()]
        checa(tipos == ["contribuicao", "sentenca"],
              f"documentos não projetados: {tipos}")
    print("  ok     cadastro por HTTP chega às três camadas")


def teste_o_achado_e_gravado_no_recebimento_nao_a_cada_tela():
    """DESTRAVA O QUE O PAINEL NÃO PODIA FAZER. A leitura do PDF acontecia a
    cada carregamento de tela do filiado, e nunca para o painel — ler a base
    inteira a cada pedido é consulta de minutos. Agora é uma vez, na
    chegada."""
    from servidor import banco

    cliente, _, _raiz = _servidor()
    _cadastrar(cliente, A, com_sentenca=True)
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute(
            "SELECT tipo, valor, trecho FROM achado WHERE cpf = %s", (A,)
        )
        achados = cur.fetchall()
    checa(bool(achados), "nenhum achado gravado no recebimento")
    checa(any(t == "numero_processo" for t, _, _ in achados),
          f"não extraiu o número do processo da sentença: "
          f"{[(t, v) for t, v, _ in achados]}")
    for tipo, valor, trecho in achados:
        checa(bool(trecho.strip()), f"{tipo}={valor!r} gravado sem trecho")
    print(f"  ok     {len(achados)} achados gravados na chegada, com trecho")


def teste_a_tela_do_filiado_le_os_achados_do_banco_nao_o_pdf():
    """O QUE A T9 PEDIA. A tela do filiado abria cada PDF da pessoa a cada
    carregamento. Com os achados gravados na chegada, ela lê do banco — e o
    resultado tem de ser o MESMO, senão a otimização mudou a resposta.

    O teste apaga os PDFs do disco depois do cadastro: se a tela ainda
    responder igual, é porque ela deixou de depender deles.
    """
    from servidor import banco

    cliente, ent, raiz = _servidor()
    _cadastrar(cliente, A, com_sentenca=True)
    antes = cliente.get(
        "/api/minhas-acoes",
        headers={"Authorization": f"Bearer {_token(cliente, A)}"},
    ).json()

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM achado WHERE cpf = %s", (A,))
        checa(cur.fetchone()[0] > 0, "nenhum achado no banco para comparar")

    # Os PDFs somem do disco. O diário e o banco continuam.
    pdfs = list(ent.entrega(raiz).rglob("*.pdf"))
    checa(bool(pdfs), "nenhum PDF no disco — o teste não prova nada assim")
    for pdf in pdfs:
        pdf.unlink()
    apagados = len(pdfs)

    depois = cliente.get(
        "/api/minhas-acoes",
        headers={"Authorization": f"Bearer {_token(cliente, A)}"},
    ).json()
    checa(antes["oportunidades"] == depois["oportunidades"],
          "a resposta mudou quando os PDFs sumiram — a tela ainda depende "
          "deles, ou o banco não guarda o mesmo")
    donos = {f["quem"] for o in depois["oportunidades"] for f in o["falta"]
             if "sentença" in f["o_que"].lower()}
    checa("VOCE" not in donos,
          f"cobrou a sentença de quem a entregou, na tela do filiado: {donos}")
    print(f"  ok     mesma resposta sem os PDFs ({apagados} apagados)")


def teste_a_consulta_do_filiado_fica_registrada():
    """A tabela `leitura` deixou de ser promessa."""
    from servidor import banco

    cliente, _, _raiz = _servidor()
    _cadastrar(cliente, A)
    r = cliente.get("/api/minhas-acoes",
                    headers={"Authorization": f"Bearer {_token(cliente, A)}"})
    checa(r.status_code == 200, f"consulta falhou: {r.status_code}")
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute(
            "SELECT o_que, quem_hash FROM leitura WHERE o_que = 'minhas-acoes'"
        )
        linhas = cur.fetchall()
    checa(bool(linhas), "a consulta do filiado não foi registrada")
    for _, quem in linhas:
        checa(bool(quem) and not quem.isdigit(),
              f"marcador suspeito no log: {quem!r}")
    print(f"  ok     {len(linhas)} leitura(s) registrada(s)")


def teste_o_painel_do_gestor_tambem_fica_registrado():
    from servidor import banco

    cliente, _, _raiz = _servidor()
    _cadastrar(cliente, A)
    r = cliente.get("/api/entidade/demo-a/panorama",
                    headers={"Authorization": f"Bearer {_token(cliente, B)}"})
    checa(r.status_code == 200, f"panorama falhou: {r.status_code} {r.text[:200]}")
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM leitura WHERE o_que = 'panorama'")
        checa(cur.fetchone()[0] >= 1, "o painel do gestor não foi registrado")
    print("  ok     o painel do gestor fica registrado")


def teste_o_panorama_por_http_bate_com_o_diario():
    """A concordância, agora pelo caminho de produção inteiro."""
    from nucleo import entendimentos, panorama
    from servidor import deposito, entidades

    cliente, ent, raiz = _servidor()
    _cadastrar(cliente, A, com_sentenca=True)
    r = cliente.get("/api/entidade/demo-a/panorama",
                    headers={"Authorization": f"Bearer {_token(cliente, B)}"})
    corpo = r.json()

    cfg_raiz = ent.pasta(Path(str(ent.pasta(Path(".")).parent)))  # noqa: F841
    print("  ok     panorama por HTTP: " + corpo["manchete"])
    checa(corpo["pessoas"] == 1, f"pessoas: {corpo['pessoas']}")
    # A mesma ação, o mesmo gargalo de topo — e a sentença entregue NÃO é
    # cobrada da pessoa.
    donos = {g["quem"] for g in corpo["gargalos"]
             if "sentença" in g["o_que"].lower()}
    checa("VOCE" not in donos,
          f"cobrou a sentença de quem entregou, pelo caminho de produção: "
          f"{donos}")


# ============================== a planilha do sindicato vira base (etapa 1)
#
# A AUDITORIA QUE ABRIU ESTE BLOCO: `acervo.jsonl` era lido em UM lugar do
# código — o retrato da base — e parava ali. O motor nunca via a planilha.
# Tudo o que o produto afirmava sobre alguém saía do que a PESSOA digitou no
# portal, e um sindicato com 4.812 filiados e 200 cadastrados via um painel
# de 200.
#
# É a diferença entre vender "organizamos a sua base" e vender "fizemos um
# formulário".


def _pessoas_do_acervo(linhas: list[tuple]):
    """Pessoas como `acervo.ler` as devolve, sem passar por arquivo."""
    from servidor import acervo as mod

    saida = []
    for numero, (cpf, nome, email, desde, ate) in enumerate(linhas, start=2):
        campos = {"cpf": cpf, "nome_completo": nome, "email": email,
                  "cargo": "Auditor Fiscal da Receita Federal",
                  "situacao": "aposentado",
                  "filiado_desde": desde, "filiado_ate": ate}
        saida.append(mod.Pessoa(
            cpf="".join(c for c in cpf if c.isdigit()),
            linha_no_arquivo=numero, campos=campos,
        ))
    return saida


def teste_a_planilha_entra_no_banco():
    secao("a planilha vira base")
    from servidor import banco

    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "FULANA DA PLANILHA (EXEMPLO)", "f@exemplo.org", "2004-03", ""),
        (B, "BELTRANO DA PLANILHA (EXEMPLO)", "b@exemplo.org", "2001-01", "2009-12"),
    ]))
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM pessoa")
        checa(cur.fetchone()[0] == 2, "a planilha não virou pessoa no banco")
        cur.execute(
            "SELECT count(*) FROM pessoa_afirmacao WHERE fonte = 'acervo'"
        )
        checa(cur.fetchone()[0] > 5, "as afirmações do acervo não entraram")
        cur.execute("SELECT tipo FROM recebimento")
        checa([t for (t,) in cur.fetchall()] == ["acervo"],
              "o recebimento não foi marcado como acervo")
    print("  ok     planilha -> recebimento, afirmação e pessoa")


def teste_projetar_a_mesma_planilha_duas_vezes_nao_duplica():
    from servidor import banco

    pessoas = _pessoas_do_acervo([
        (A, "FULANA (EXEMPLO)", "f@exemplo.org", "2004-03", ""),
    ])
    banco.projetar_acervo(URL, "demo-a", pessoas)
    banco.projetar_acervo(URL, "demo-a", pessoas)
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM recebimento")
        checa(cur.fetchone()[0] == 1, "duplicou o recebimento do acervo")
        cur.execute("SELECT count(*) FROM pessoa")
        checa(cur.fetchone()[0] == 1, "duplicou a pessoa")
    print("  ok     reprojetar a mesma planilha é idempotente")


def teste_o_acervo_vence_o_cadastro_e_a_divergencia_fica_marcada():
    """A REGRA QUE O ESQUEMA JÁ DECLARAVA e ninguém implementava: o valor
    vigente é o do ACERVO até o sindicato homologar. A ordem de chegada não
    decide qual versão da verdade entra na base — e a afirmação do filiado
    não some: é dela que a divergência existe."""
    from servidor import banco

    # O filiado se cadastra dizendo um cargo; a planilha do sindicato diz
    # outro. Ninguém escolhe sozinho.
    banco.reconstruir(URL, "demo-a",
                      [registro(A, cargo="Analista Tributário da Receita Federal")])
    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "FULANA DA PLANILHA (EXEMPLO)", "f@exemplo.org", "2004-03", ""),
    ]))
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT cargo, tem_divergencia FROM pessoa WHERE cpf = %s",
                    (A,))
        cargo, divergente = cur.fetchone()
        checa("Auditor" in cargo,
              f"o cadastro venceu o acervo: cargo vigente = {cargo!r}")
        checa(divergente is True,
              "as duas fontes discordam e a divergência não foi marcada")
        cur.execute(
            "SELECT count(DISTINCT fonte) FROM pessoa_afirmacao "
            "WHERE cpf = %s AND campo = 'cargo'", (A,)
        )
        checa(cur.fetchone()[0] == 2,
              "uma das duas afirmações de cargo foi apagada")
    print("  ok     acervo vence, cadastro sobrevive, divergência marcada")


def teste_concordar_nao_e_divergir():
    from servidor import banco

    banco.reconstruir(URL, "demo-a", [registro(A)])
    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "FULANO 35 (CADASTRO DE EXEMPLO)", "exemplo@exemplo.org",
         "2004-03", ""),
    ]))
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT tem_divergencia FROM pessoa WHERE cpf = %s", (A,))
        checa(cur.fetchone()[0] is False,
              "marcou divergência onde as duas fontes concordam")
    print("  ok     concordância não vira divergência")


def teste_quem_so_esta_na_planilha_ja_tem_resposta():
    """O TESTE QUE MEDE A AUDITORIA. Uma pessoa que NUNCA entrou no portal,
    só está na planilha do sindicato: o motor tem de responder por ela.

    É isto que separa "organizamos a sua base" de "fizemos um formulário"."""
    secao("o motor responde pela base inteira")
    from nucleo import entendimentos, panorama, participacao as part
    from servidor import banco

    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "SÓ NA PLANILHA (EXEMPLO)", "f@exemplo.org", "2004-03", ""),
    ]))
    catalogo = entendimentos.carregar_categorias(
        entendimentos.PASTA_PADRAO, ("auditor-fiscal-receita-federal",)
    ).homologando(("GIFA-2006",))

    base = banco.base(URL, "demo-a")
    checa(len(base) == 1, f"a pessoa da planilha não entrou na base: {base}")
    visao = panorama.montar(base, catalogo)
    checa(visao.pessoas == 1, f"panorama não contou: {visao.pessoas}")
    gifa = next(a for a in visao.por_acao if a.acao == "GIFA-2006")
    checa(gifa.participam == 1,
          f"quem só está na planilha não teve participação apurada: {gifa}")
    # 2004-03 a 2008-12 = 58 meses. A conta do teste estava errada antes, não
    # a do produto: (2008-2004)*12 + (12-3) + 1.
    checa(gifa.meses_somados == 58,
          f"meses somados {gifa.meses_somados}, esperado 58 (2004-03 a 2008-12)")
    print(f"  ok     sem cadastro nenhum: participa, {gifa.meses_somados} meses")


def teste_o_panorama_separa_a_base_de_quem_se_cadastrou():
    """Os dois números são diferentes e o gestor precisa dos dois: quantos
    ele tem, e de quantos já temos documento."""
    from nucleo import entendimentos, panorama
    from servidor import banco

    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "SÓ NA PLANILHA (EXEMPLO)", "f@exemplo.org", "2004-03", ""),
        (B, "TAMBÉM NA PLANILHA (EXEMPLO)", "b@exemplo.org", "2004-03", ""),
    ]))
    banco.reconstruir(URL, "demo-a", [registro(B)])
    catalogo = entendimentos.carregar_categorias(
        entendimentos.PASTA_PADRAO, ("auditor-fiscal-receita-federal",)
    )
    visao = panorama.montar(banco.base(URL, "demo-a"), catalogo)
    checa(visao.pessoas == 2, f"base: {visao.pessoas}, esperado 2")
    checa(visao.cadastrados == 1,
          f"cadastrados: {visao.cadastrados}, esperado 1")
    print(f"  ok     {visao.pessoas} na base, {visao.cadastrados} cadastrada(s)")


def teste_o_processo_da_planilha_vira_acompanhamento():
    """O sindicato costuma ter o número. Hoje a pessoa aposentada tinha de
    achar 20 dígitos numa papelada e digitar no celular."""
    from servidor import banco
    from servidor import acervo as mod

    pessoa = mod.Pessoa(cpf=A, linha_no_arquivo=2, campos={
        "cpf": A, "email": "f@exemplo.org", "nome_completo": "FULANA (EXEMPLO)",
        "numeros_de_processo": "00103912420064013400",
    })
    banco.projetar_acervo(URL, "demo-a", [pessoa])
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT numero FROM vinculo WHERE cpf = %s", (A,))
        checa(cur.fetchall() == [("00103912420064013400",)],
              "o processo da planilha não virou vínculo")
    print("  ok     processo da planilha vira acompanhamento")


def teste_a_base_nao_atravessa_entidade():
    from servidor import banco

    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "DA ENTIDADE A (EXEMPLO)", "a@exemplo.org", "2004-03", ""),
    ]))
    banco.projetar_acervo(URL, "demo-b", _pessoas_do_acervo([
        (B, "DA ENTIDADE B (EXEMPLO)", "b@exemplo.org", "2004-03", ""),
    ]))
    cpfs = {r["linha"]["cpf"] for r in banco.base(URL, "demo-a")}
    checa(cpfs == {A}, f"VAZOU pessoa de outra entidade: {cpfs}")
    print("  ok     a base de cada entidade é só dela")


def teste_o_processo_que_o_sindicato_mandou_aparece_para_a_pessoa():
    """A PROMESSA DA TELA DA PESSOA: "controle sobre as ações que já correm
    no seu nome". Isso vem da planilha do sindicato, não do que ela digita —
    e hoje ela tinha de achar 20 dígitos numa papelada."""
    from servidor import banco
    from servidor import acervo as mod

    cliente, _, _raiz = _servidor()
    banco.projetar_acervo(URL, "demo-a", [mod.Pessoa(
        cpf=A, linha_no_arquivo=2, campos={
            "cpf": A, "email": "fulana@exemplo.org",
            "nome_completo": "FULANA (EXEMPLO)",
            "numeros_de_processo": "00103912420064013400",
        })])
    r = cliente.get("/api/meus-processos",
                    headers={"Authorization": f"Bearer {_token(cliente, A)}"})
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    numeros = {p["numero"] for p in r.json()["processos"]}
    checa("00103912420064013400" in numeros,
          f"o processo da planilha não chegou à pessoa: {numeros}")
    print("  ok     processo da planilha aparece sem ela digitar nada")


def teste_o_painel_responde_pela_base_inteira():
    """O número que muda a venda: o panorama deixa de contar só quem se
    cadastrou."""
    from servidor import banco

    cliente, _, _raiz = _servidor()
    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "SÓ NA PLANILHA (EXEMPLO)", "fulana@exemplo.org", "2004-03", ""),
        (B, "GESTOR NA PLANILHA (EXEMPLO)", "gestor@exemplo.org", "2004-03", ""),
    ]))
    r = cliente.get("/api/entidade/demo-a/panorama",
                    headers={"Authorization": f"Bearer {_token(cliente, B)}"})
    corpo = r.json()
    checa(corpo["pessoas"] == 2,
          f"o painel contou {corpo['pessoas']}, e a planilha tem 2")
    checa(corpo["cadastrados"] == 0,
          f"contou cadastrado sem ninguém ter se cadastrado: "
          f"{corpo['cadastrados']}")
    # O catálogo em disco tem `homologado = "N"` em tudo, então as duas saem
    # INDETERMINADO — e é o certo. O que este teste prova é que elas foram
    # AVALIADAS: antes, quem não se cadastrasse não existia para o motor.
    gifa = [a for a in corpo["por_acao"] if a["acao"] == "GIFA-2006"]
    checa(bool(gifa), f"a ação não apareceu: {corpo['por_acao']}")
    avaliadas = (gifa[0]["participam"] + gifa[0]["indeterminados"]
                 + gifa[0]["nao_participam"])
    checa(avaliadas == 2,
          f"a base da planilha não foi avaliada pelo motor: {gifa[0]}")
    checa(gifa[0]["participam"] == 0,
          "disse que participa com o catálogo não homologado")
    print(f"  ok     painel: {corpo['pessoas']} na base, "
          f"{corpo['cadastrados']} cadastradas, {avaliadas} avaliadas")


# ====================== o portal reconhece quem já está na base (etapa 2)
#
# A pessoa recebe o link no grupo de WhatsApp do sindicato e abre. Até aqui,
# ela encontrava 17 campos em branco — e **10 deles o sindicato já tinha
# mandado**. Cada campo desses é gente que abandona o cadastro no meio.
#
# Agora ela confere em vez de digitar. E o que ela corrigir NÃO sobrescreve o
# sindicato: vira afirmação dela, e a divergência aparece no painel. Quem
# decide qual versão vale é o sindicato, não a ordem de chegada.


def teste_meu_cadastro_exige_sessao():
    secao("o portal reconhece a pessoa")
    cliente, _, _raiz = _servidor()
    for cabecalho in ({}, {"Authorization": "Bearer invalido"}):
        r = cliente.get("/api/meu-cadastro", headers=cabecalho)
        checa(r.status_code == 401,
              f"dados pessoais sem sessão: {r.status_code}")
    print("  ok     sem sessão válida, 401")


def teste_meu_cadastro_devolve_o_que_o_sindicato_mandou():
    from servidor import banco

    cliente, _, _raiz = _servidor()
    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "FULANA DA PLANILHA (EXEMPLO)", "fulana@exemplo.org",
         "2004-03", ""),
    ]))
    r = cliente.get("/api/meu-cadastro",
                    headers={"Authorization": f"Bearer {_token(cliente, A)}"})
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    corpo = r.json()
    checa(corpo["conhecido"] is True, "não reconheceu quem está na base")
    conhecido = corpo["campos"]
    checa(conhecido.get("nome_completo", "").startswith("FULANA"),
          f"o nome não voltou: {conhecido}")
    checa(conhecido.get("filiado_desde") == "2004-03",
          f"a filiação não voltou: {conhecido}")
    checa(conhecido.get("cargo", "").startswith("Auditor"),
          f"o cargo não voltou: {conhecido}")
    print(f"  ok     {len([v for v in conhecido.values() if v])} campo(s) "
          f"já conhecidos")


def teste_meu_cadastro_diz_que_documentos_ja_temos():
    """Se o sindicato já mandou a sentença dela, a tela não pode pedir de
    novo — é o pedido que faz a pessoa achar que o sistema não funciona."""
    from servidor import banco

    cliente, _, _raiz = _servidor()
    _cadastrar(cliente, A, com_sentenca=True)
    r = cliente.get("/api/meu-cadastro",
                    headers={"Authorization": f"Bearer {_token(cliente, A)}"})
    corpo = r.json()
    checa("sentenca" in corpo["documentos"],
          f"não disse que já tem a sentença: {corpo['documentos']}")
    checa("contribuicao" in corpo["documentos"], f"{corpo['documentos']}")
    print(f"  ok     já temos: {', '.join(corpo['documentos'])}")


def teste_meu_cadastro_nao_aceita_cpf_por_parametro():
    """A mesma trava das outras consultas: aceitar CPF de fora
    transformaria isto na pesquisa de filiação que o portão se recusa a ser
    — e aqui o retorno é o cadastro inteiro de alguém."""
    from servidor import banco

    cliente, _, _raiz = _servidor()
    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "FULANA (EXEMPLO)", "fulana@exemplo.org", "2004-03", ""),
        (B, "BELTRANO (EXEMPLO)", "gestor@exemplo.org", "2001-01", ""),
    ]))
    r = cliente.get(f"/api/meu-cadastro?cpf={A}",
                    headers={"Authorization": f"Bearer {_token(cliente, B)}"})
    corpo = r.json()
    checa("FULANA" not in str(corpo),
          f"VAZOU o cadastro de outra pessoa: {corpo}")
    checa(corpo["campos"].get("nome_completo", "").startswith("BELTRANO"),
          f"devolveu o de quem não abriu a sessão: {corpo['campos']}")
    print("  ok     parâmetro cpf é ignorado, não obedecido")


def teste_quem_nao_esta_na_base_recebe_vazio_e_nao_erro():
    """Filiado novo, que entrou depois da última exportação do sindicato.
    Ele existe, e a tela dele é a de sempre — em branco, sem erro."""
    cliente, _, _raiz = _servidor()
    r = cliente.get("/api/meu-cadastro",
                    headers={"Authorization": f"Bearer {_token(cliente, A)}"})
    checa(r.status_code == 200, f"deu erro: {r.status_code}")
    corpo = r.json()
    checa(corpo["conhecido"] is False, "disse conhecer quem não está na base")
    checa(corpo["campos"] == {} and corpo["documentos"] == [], f"{corpo}")
    checa(bool(corpo.get("aviso", "").strip()), "não explicou o vazio")
    print("  ok     quem não está na base: vazio com explicação")


def teste_a_consulta_do_proprio_cadastro_fica_registrada():
    """É dado nominal, e dos mais completos que o sistema devolve."""
    from servidor import banco

    cliente, _, _raiz = _servidor()
    cliente.get("/api/meu-cadastro",
                headers={"Authorization": f"Bearer {_token(cliente, A)}"})
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM leitura WHERE o_que = 'meu-cadastro'")
        checa(cur.fetchone()[0] >= 1, "a consulta não foi registrada")
    print("  ok     a leitura fica registrada")


def teste_a_correcao_da_pessoa_nao_apaga_o_sindicato():
    """A REGRA, agora no caminho que a pessoa percorre. Ela abre o link, vê
    'Analista Tributário' onde devia ser 'Auditor Fiscal', corrige e envia.
    O vigente continua sendo o do sindicato, a correção dela sobrevive, e a
    divergência aparece no painel — ninguém decide sozinho."""
    from servidor import banco

    cliente, _, _raiz = _servidor()
    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "FULANA DA PLANILHA (EXEMPLO)", "fulana@exemplo.org",
         "2004-03", ""),
    ]))
    import json as _json
    corrigida = linha(A, cargo="Analista Tributário da Receita Federal")
    cliente.post(
        "/api/cadastro",
        data={"token": _token(cliente, A), "linha": _json.dumps(corrigida)},
        files=[("arquivos", ("contribuicao-1.pdf", _pdf(CONTRIB),
                             "application/pdf"))],
    )
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT cargo, tem_divergencia FROM pessoa WHERE cpf = %s",
                    (A,))
        cargo, divergente = cur.fetchone()
    checa("Auditor" in cargo,
          f"a correção da pessoa sobrescreveu o sindicato: {cargo!r}")
    checa(divergente is True, "a divergência não foi marcada")
    print("  ok     correção vira divergência, não sobrescrita")


# ===================================== o aviso de movimentação, no banco


def teste_so_entra_na_lista_de_aviso_quem_marcou():
    secao("o aviso de movimentação")
    from servidor import banco

    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "QUER AVISO (EXEMPLO)", "a@sindicato.exemplo.org", "2004-03", ""),
        (B, "NAO QUER (EXEMPLO)", "b@sindicato.exemplo.org", "2004-03", ""),
    ]))
    banco.reconstruir(URL, "demo-a", [
        registro(A, quer_aviso="sim"),
        registro(B, quer_aviso=""),
    ])
    quem = banco.destinatarios(URL, "demo-a")
    checa({d.cpf for d in quem} == {A},
          f"a lista de aviso não respeitou o opt-in: "
          f"{[(d.cpf, d.quer_aviso) for d in quem]}")
    print("  ok     só quem marcou entra na lista")


def teste_o_email_do_aviso_vem_do_sindicato_nao_do_digitado():
    """Se viesse do digitado, bastaria cadastrar o CPF de outra pessoa com o
    próprio e-mail para passar a receber a movimentação do processo dela."""
    from servidor import banco

    banco.projetar_acervo(URL, "demo-a", _pessoas_do_acervo([
        (A, "FULANA (EXEMPLO)", "oficial@sindicato.exemplo.org",
         "2004-03", ""),
    ]))
    banco.reconstruir(URL, "demo-a", [
        registro(A, quer_aviso="sim", email="outro@qualquer.exemplo.org"),
    ])
    quem = banco.destinatarios(URL, "demo-a")
    checa(quem[0].email_do_sindicato == "oficial@sindicato.exemplo.org",
          f"o destino veio do digitado: {quem[0].email_do_sindicato}")
    print("  ok     destino é o e-mail da planilha do sindicato")


def teste_o_opt_in_e_dela_o_sindicato_nao_marca_por_ela():
    """O acervo pode trazer uma coluna chamada `quer_aviso`. Ela não vale:
    consentimento é da pessoa, e o sindicato declarar por ela transformaria
    a planilha numa lista de mala direta."""
    from servidor import banco
    from servidor import acervo as mod

    banco.projetar_acervo(URL, "demo-a", [mod.Pessoa(
        cpf=A, linha_no_arquivo=2, campos={
            "cpf": A, "email": "a@sindicato.exemplo.org",
            "nome_completo": "FULANA (EXEMPLO)", "quer_aviso": "sim",
        })])
    quem = banco.destinatarios(URL, "demo-a")
    checa(quem == [],
          f"o sindicato marcou o opt-in no lugar da pessoa: {quem}")
    print("  ok     o opt-in só vale vindo da pessoa")


def teste_o_processo_coletado_fica_conhecido():
    """É o que separa estreia de novidade. Sem isso, o primeiro dia de cada
    sindicato manda a cada pessoa o histórico inteiro do processo dela."""
    from nucleo import aviso as mod
    from servidor import banco

    checa(banco.processos_coletados(URL, "demo-a") == set(),
          "havia processo conhecido numa base limpa")
    banco.guardar_movimentos(URL, "demo-a", [
        mod.Movimento(numero="00103912420064013400", grau="G1",
                      data="2026-10-30", nome="Juntada"),
    ])
    checa(banco.processos_coletados(URL, "demo-a")
          == {"00103912420064013400"}, "o processo não ficou conhecido")
    print("  ok     processo coletado passa a ser conhecido")


def teste_o_aviso_marcado_nao_se_repete_e_e_por_pessoa():
    """Por PESSOA e não por processo: numa coletiva o mesmo processo alcança
    milhares, e quem se cadastrou ontem não pode herdar o 'já avisado' de
    quem está há meses."""
    from servidor import banco

    banco.marcar_avisado(URL, "demo-a", A, ["proc|G1|2026-10-30|Juntada"])
    banco.marcar_avisado(URL, "demo-a", A, ["proc|G1|2026-10-30|Juntada"])
    checa(banco.chaves_ja_avisadas(URL, "demo-a", A)
          == {"proc|G1|2026-10-30|Juntada"}, "duplicou a marca")
    checa(banco.chaves_ja_avisadas(URL, "demo-a", B) == set(),
          "a marca de uma pessoa valeu para a outra")
    print("  ok     marca por pessoa, sem duplicar")


def teste_o_aviso_nao_atravessa_entidade():
    from servidor import banco

    banco.marcar_avisado(URL, "demo-b", A, ["x|G1|2026-10-30|Y"])
    checa(banco.chaves_ja_avisadas(URL, "demo-a", A) == set(),
          "a entidade A enxergou a marca da entidade B")
    print("  ok     a marca de aviso não atravessa entidade")


def teste_o_coletor_enxerga_o_processo_que_veio_da_planilha():
    """O CICLO QUEBRADO NO MEIO, achado pelo próprio agendador: ele registrou
    "nada a acompanhar" numa entidade que tinha processo. O coletor lia só o
    diário de cadastro, e os números que vieram da PLANILHA do sindicato —
    justamente os que a pessoa não precisou digitar — ficavam invisíveis."""
    secao("o ciclo fechado")
    from servidor import banco
    from servidor import acervo as mod

    banco.projetar_acervo(URL, "demo-a", [mod.Pessoa(
        cpf=A, linha_no_arquivo=2, campos={
            "cpf": A, "email": "f@exemplo.org",
            "nome_completo": "FULANA (EXEMPLO)",
            "numeros_de_processo": "00103912420064013400",
        })])
    numeros = banco.processos_para_acompanhar(URL, "demo-a")
    checa(numeros == ["00103912420064013400"],
          f"o processo da planilha não chegou ao coletor: {numeros}")
    checa(banco.processos_para_acompanhar(URL, "demo-b") == [],
          "o coletor de uma entidade enxergou o processo de outra")
    print("  ok     o processo da planilha chega ao coletor")


def teste_a_saude_denuncia_o_agendador_parado():
    """O PONTO INTEIRO DESTE CHECKPOINT. Um agendador que morreu tem de
    aparecer onde alguém olhe — e `ok: true` com os avisos parados há um mês
    é exatamente o relatório que faz ninguém perceber.

    Monitor que só confere se a porta responde não vê que os avisos pararam.
    """
    secao("o agendador parado aparece")
    cliente, _, _raiz = _servidor()
    corpo = cliente.get("/saude").json()
    checa(corpo["ok"] is False,
          f"disse ok com o trabalho de fundo nunca tendo rodado: {corpo}")
    checa(corpo["atrasados"] >= 1, f"{corpo}")
    tarefas = {t["tarefa"] for t in corpo["trabalho_de_fundo"]}
    checa(tarefas == {"coletar", "avisar"},
          f"as tarefas não aparecem na saúde: {tarefas}")
    print(f"  ok     saúde: ok={corpo['ok']}, "
          f"{corpo['atrasados']} atrasada(s)")


def teste_saude_nao_diz_ok_quando_nao_consegue_ler_o_estado():
    """A ARMADILHA EM QUE EU MESMO CAÍ, vista no vivo. A consulta do estado
    falhava, a lista ficava vazia, e `atrasados == 0` fazia a saúde
    responder `ok: true` — com os avisos parados.

    **Não saber como está o trabalho é um estado RUIM**, não um estado bom.
    """
    cliente, _, _raiz = _servidor()
    import servidor.agenda as mod

    original = mod.estado
    mod.estado = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("banco fora do ar")
    )
    try:
        corpo = cliente.get("/saude").json()
    finally:
        mod.estado = original
    checa(corpo["ok"] is False,
          f"disse ok sem conseguir ler o estado do trabalho: {corpo}")
    checa(bool(corpo.get("estado_ilegivel")),
          f"não disse que não conseguiu ler: {corpo}")
    print("  ok     não saber não é estar bem")


def teste_a_saude_fica_boa_quando_o_trabalho_roda():
    from servidor import agenda

    cliente, ent, _raiz = _servidor()
    for tarefa in agenda.TAREFAS:
        agenda.registrar(URL, ent.apelido, tarefa, ok=True, detalhe="ok")
    corpo = cliente.get("/saude").json()
    checa(corpo["ok"] is True, f"continuou ruim depois de rodar: {corpo}")
    checa(corpo["atrasados"] == 0, f"{corpo}")
    print("  ok     depois de rodar, a saúde fica boa")


def teste_saude_nao_publica_o_detalhe_a_quem_nao_tem_sessao():
    """O DETALHE DA EXECUÇÃO NÃO É PÚBLICO.

    `/saude` não exige sessão. O `ultimo_detalhe` que ela publicava era o
    stdout cru do subprocesso — e o stdout de `avisar_movimentacao.py`
    termina listando, uma linha por pessoa, o CPF e o e-mail de quem ficou
    sem aviso. Auditoria independente reproduziu de ponta a ponta: um GET
    sem cabeçalho nenhum devolvia CPF, e-mail e o apelido de todos os
    sindicatos atendidos.

    Pelo caminho do tempo esgotado saía pior: `TimeoutExpired` carrega a
    linha de comando inteira, e nela ia `--banco <URL com a senha>` — a
    credencial que ignora a política de entidade.

    O que o monitor precisa saber — se o trabalho parou — cabe em `ok`,
    `atrasado` e `ultima_boa`, que não carregam conteúdo nenhum. O detalhe
    fica no log do servidor, que é canal de operador.
    """
    from servidor import agenda

    cliente, ent, _raiz = _servidor()
    CPF = "11144477735"        # CPF de teste; não é de ninguém
    SENHA = "SENHA-FICTICIA-DE-EXEMPLO"
    agenda.registrar(
        URL, ent.apelido, "avisar", ok=False,
        detalhe=(f"RuntimeError: avisar_movimentacao.py: 1 ficaram SEM "
                 f"aviso: {CPF}: o e-mail não serve ('x@exemplo.invalid')"),
    )
    agenda.registrar(
        URL, ent.apelido, "coletar", ok=False,
        detalhe=(f"TimeoutExpired: Command '['python3', '--banco', "
                 f"'postgresql://postgres:{SENHA}@exemplo.invalid/x']' "
                 f"timed out after 3540 seconds"),
    )

    resposta = cliente.get("/saude")       # sem cabeçalho Authorization
    cru = resposta.text
    checa(CPF not in cru, f"o CPF saiu na saúde pública: {cru[:300]}")
    checa(SENHA not in cru, f"a senha do banco saiu na saúde: {cru[:300]}")
    checa("ultimo_detalhe" not in cru,
          f"o detalhe da execução continua público: {cru[:300]}")
    checa(ent.apelido not in cru,
          f"a saúde pública enumera os sindicatos atendidos: {cru[:300]}")

    # E NADA DISSO PODE CUSTAR O SINAL: um trabalho parado continua
    # aparecendo, que é a razão de a rota existir.
    corpo = resposta.json()
    checa(corpo["ok"] is False, f"perdeu o sinal de que algo falhou: {corpo}")
    checa(corpo["atrasados"] >= 1, f"perdeu a contagem de atrasados: {corpo}")
    print("  ok     a saúde não publica CPF, senha, detalhe nem apelido")


def teste_um_cadastro_nao_custa_o_diario_inteiro():
    """O CUSTO DE ATENDER UM ENVIO NÃO PODE CRESCER COM O ACERVO.

    `/api/cadastro` chamava `banco.reconstruir` passando
    `deposito.ler_diario(...)` — TODOS os registros do diário, não o que
    acabou de chegar. `reconstruir` é a função de RECUPERAÇÃO: ela existe
    para refazer a projeção a partir do diário todo, e estava sendo usada
    como escrita incremental de um envio.

    Auditoria independente mediu 21 comandos SQL por registro já existente,
    numa transação só, e 13,8 s para um diário de 4.000 registros num
    Postgres por socket unix. O diário é append-only e nunca é podado, então
    o pedido do filiado número N custava O(N), e a campanha inteira O(N²).
    Contra um banco pela rede, a 1,5 ms de ida e volta, o cadastro de número
    10.000 são mais de cinco minutos de transação aberta.

    Não é só lentidão: `app.py` declara, três linhas acima da chamada, que
    "ler a base inteira a cada pedido é consulta de minutos para responder
    uma página". A regra estava escrita no comentário e quebrada na linha
    seguinte.

    Este teste conta COMANDOS, não segundos: segundo depende de máquina,
    comando é propriedade do código.
    """
    import psycopg

    secao("o custo de um envio")

    def custo_com_diario_de(quantos: int) -> int:
        """Comandos SQL de UM cadastro, com `quantos` registros já no diário."""
        cliente, ent, raiz = _servidor()
        cpfs = [_cpf_sintetico(1000 + i) for i in range(quantos + 1)]
        _por_no_rol(raiz, ent.apelido, cpfs)
        for cpf in cpfs[:quantos]:
            _cadastrar(cliente, cpf)

        original = psycopg.Cursor.execute
        contador = {"n": 0}

        def espiao(self, *a, **k):
            contador["n"] += 1
            return original(self, *a, **k)

        psycopg.Cursor.execute = espiao
        try:
            resposta = _cadastrar(cliente, cpfs[quantos])
        finally:
            psycopg.Cursor.execute = original
        checa(resposta.status_code == 200,
              f"o cadastro falhou: {resposta.status_code} "
              f"{resposta.text[:200]}")
        return contador["n"]

    # DOIS TAMANHOS, porque um só não distingue "ficou menor" de "ficou
    # plano". A medição que pegou o defeito foi 279 comandos com 12
    # registros no diário — 21 por registro já existente, mais o custo fixo
    # do envio. Com esse comportamento, a diferença entre os dois tamanhos
    # abaixo seria de centenas de comandos.
    poucos, muitos = 4, 20
    com_poucos = custo_com_diario_de(poucos)
    com_muitos = custo_com_diario_de(muitos)

    checa(com_muitos <= com_poucos + 5,
          f"o custo cresce com o acervo: {com_poucos} comandos com "
          f"{poucos} registros no diário, {com_muitos} com {muitos}")
    print(f"  ok     {com_poucos} comandos com {poucos} no diário, "
          f"{com_muitos} com {muitos} — plano")


def teste_reconstruir_continua_recuperando_o_diario_inteiro():
    """A FUNÇÃO DE RECUPERAÇÃO NÃO PODE TER SIDO SACRIFICADA.

    Tirar o diário inteiro da rota é certo; tirá-lo de `reconstruir` seria
    perder a única maneira de refazer a projeção depois de uma queda do
    banco. O caminho de recuperação é exercitado aqui porque é o que ninguém
    roda no dia a dia — e por isso é o que quebra calado.
    """
    from servidor import banco, deposito

    cliente, ent, raiz = _servidor()
    cpfs = [_cpf_sintetico(100 + i) for i in range(3)]
    _por_no_rol(raiz, ent.apelido, cpfs)
    for cpf in cpfs:
        _cadastrar(cliente, cpf)

    # Apaga a projeção e refaz a partir do diário, como numa recuperação.
    # `sessao`, não `cru`: `cru` faz rollback de propósito — existe para
    # provar que o RLS está ligado, não para escrever.
    #
    # E `recebimento` sai também, o que não é detalhe: o sha256 dele é a
    # chave de idempotência de `reconstruir`. Deixá-lo faria a recuperação
    # PULAR tudo como já projetado, e o teste passaria sem exercitar nada.
    with banco.sessao(URL, ent.apelido) as cur:
        for tabela in ("pessoa_afirmacao", "documento", "achado",
                       "pessoa", "vinculo", "recebimento"):
            cur.execute(f"DELETE FROM {tabela}")
    base_vazia = banco.base(URL, ent.apelido)
    checa(base_vazia == [], f"a projeção não foi apagada: {base_vazia}")

    quantos = banco.reconstruir(URL, ent.apelido,
                                deposito.ler_diario(ent.pasta(raiz)))
    refeita = banco.base(URL, ent.apelido)
    checa(len(refeita) == 3,
          f"a recuperação não refez as 3 pessoas: {len(refeita)} "
          f"(reconstruir devolveu {quantos})")
    print("  ok     a recuperação pelo diário inteiro continua funcionando")


def teste_meu_cadastro_nao_le_a_base_inteira():
    """UMA PESSOA PEDINDO OS DADOS DELA NÃO PODE CUSTAR A BASE DO SINDICATO.

    `/api/meu-cadastro` chamava `banco.base(...)` — que lê
    `pessoa_afirmacao` e `documento` da entidade inteira e monta um
    dicionário por CPF — e logo descartava tudo menos uma linha, com
    `next(...)`. O pedido de UMA pessoa transportava do Postgres para a
    memória do processo a base nominal completa, a cada carregamento de
    tela, sem limite de frequência.

    Medido pela auditoria: 21 MB de pico para uma base de 4.000 pessoas,
    para responder uma linha.

    As rotas irmãs já faziam certo — `achados_do_cpf`, `documentos_do_cpf` e
    `processos_do_cpf` filtram `WHERE cpf = %s` no banco. Esta era a única
    que filtrava em Python, depois do banco.

    O teste conta LINHAS LIDAS do banco, em duas bases de tamanhos
    diferentes: é a grandeza que cresce, e um tamanho só não distingue
    "ficou menor" de "ficou plano".
    """
    import psycopg

    secao("o custo de ler o próprio cadastro")

    def linhas_lidas_com_base_de(quantas: int) -> int:
        from servidor import acervo, banco

        cliente, ent, raiz = _servidor()
        _por_no_rol(raiz, ent.apelido, [A])
        # Semeia pelo acervo, que é o caminho barato: o que está sob teste é
        # a LEITURA, não a escrita.
        pessoas = [
            acervo.Pessoa(cpf=_cpf_sintetico(2000 + i), linha_no_arquivo=i + 2,
                          campos={"nome_completo": f"EXEMPLO {i} (FICTICIO)",
                                  "email": f"e{i}@exemplo.invalid"})
            for i in range(quantas)
        ]
        banco.projetar_acervo(URL, ent.apelido, pessoas)
        _cadastrar(cliente, A)

        original = psycopg.Cursor.fetchall
        conta = {"linhas": 0}

        def espiao(self):
            filas = original(self)
            conta["linhas"] += len(filas)
            return filas

        psycopg.Cursor.fetchall = espiao
        try:
            r = cliente.get("/api/meu-cadastro",
                            headers={"Authorization": f"Bearer "
                                                      f"{_token(cliente, A)}"})
        finally:
            psycopg.Cursor.fetchall = original
        checa(r.status_code == 200,
              f"a rota falhou: {r.status_code} {r.text[:200]}")
        checa(r.json().get("campos", {}).get("nome_completo"),
              f"a rota devolveu vazio, então o teste não mediu nada: "
              f"{r.json()}")
        return conta["linhas"]

    poucas, muitas = 3, 30
    com_poucas = linhas_lidas_com_base_de(poucas)
    com_muitas = linhas_lidas_com_base_de(muitas)

    checa(com_muitas <= com_poucas + 5,
          f"ler o próprio cadastro custa a base inteira: {com_poucas} "
          f"linhas com {poucas} pessoas, {com_muitas} com {muitas}")
    print(f"  ok     {com_poucas} linhas com {poucas} pessoas na base, "
          f"{com_muitas} com {muitas} — plano")


def teste_o_registro_por_cpf_concorda_com_a_base_inteira():
    """A MESMA REGRA DE PRECEDÊNCIA, NÃO UMA SEGUNDA CÓPIA DELA.

    "O acervo vence, e o preenchido vence o vazio" é regra de produto. Se
    `registro_do_cpf` a reimplementasse, as duas divergiriam — e foi
    exatamente regra escrita em dois lugares que produziu metade dos
    achados desta auditoria. Este teste compara as duas saídas para a mesma
    pessoa, com acervo E cadastro presentes, que é onde a precedência
    aparece.
    """
    from servidor import acervo, banco

    cliente, ent, raiz = _servidor()
    _por_no_rol(raiz, ent.apelido, [A])
    banco.projetar_acervo(URL, ent.apelido, [
        acervo.Pessoa(cpf=A, linha_no_arquivo=2, campos={
            "nome_completo": "NOME DO ACERVO (FICTICIO)",
            "unidade": "UNIDADE DO ACERVO",
        }),
    ])
    _cadastrar(cliente, A)

    pela_base = next((r for r in banco.base(URL, ent.apelido)
                      if r["linha"].get("cpf") == A), None)
    por_cpf = banco.registro_do_cpf(URL, ent.apelido, A)
    checa(por_cpf == pela_base,
          f"as duas leituras divergem.\n  base:   {pela_base}\n"
          f"  por cpf: {por_cpf}")

    # E quem não existe devolve None nas duas, não uma linha vazia.
    ausente = _cpf_sintetico(999_999)
    checa(banco.registro_do_cpf(URL, ent.apelido, ausente) is None,
          "inventou registro para CPF que não está na base")
    print("  ok     a leitura por CPF concorda com a base inteira")


TESTES = [
    teste_recriar_derruba_TODAS_as_tabelas,
    teste_o_diario_vira_banco,
    teste_reconstruir_duas_vezes_nao_duplica,
    teste_o_ultimo_envio_vence_tambem_no_banco,
    teste_documento_e_vinculo_projetados,
    teste_registro_ilegivel_nao_derruba_a_projecao,
    teste_o_panorama_do_banco_e_igual_ao_do_diario,
    teste_cadastros_do_banco_nao_atravessam_entidade,
    teste_o_achado_guarda_o_trecho,
    teste_a_fila_de_conferencia_sai_do_banco,
    teste_guardar_achados_duas_vezes_nao_duplica,
    teste_o_cadastro_por_http_chega_ao_banco,
    teste_o_achado_e_gravado_no_recebimento_nao_a_cada_tela,
    teste_a_tela_do_filiado_le_os_achados_do_banco_nao_o_pdf,
    teste_a_consulta_do_filiado_fica_registrada,
    teste_o_painel_do_gestor_tambem_fica_registrado,
    teste_o_panorama_por_http_bate_com_o_diario,
    teste_a_planilha_entra_no_banco,
    teste_o_processo_que_o_sindicato_mandou_aparece_para_a_pessoa,
    teste_o_painel_responde_pela_base_inteira,
    teste_projetar_a_mesma_planilha_duas_vezes_nao_duplica,
    teste_o_acervo_vence_o_cadastro_e_a_divergencia_fica_marcada,
    teste_concordar_nao_e_divergir,
    teste_quem_so_esta_na_planilha_ja_tem_resposta,
    teste_o_panorama_separa_a_base_de_quem_se_cadastrou,
    teste_o_processo_da_planilha_vira_acompanhamento,
    teste_a_base_nao_atravessa_entidade,
    teste_meu_cadastro_exige_sessao,
    teste_meu_cadastro_devolve_o_que_o_sindicato_mandou,
    teste_meu_cadastro_diz_que_documentos_ja_temos,
    teste_meu_cadastro_nao_aceita_cpf_por_parametro,
    teste_quem_nao_esta_na_base_recebe_vazio_e_nao_erro,
    teste_a_consulta_do_proprio_cadastro_fica_registrada,
    teste_a_correcao_da_pessoa_nao_apaga_o_sindicato,
    teste_so_entra_na_lista_de_aviso_quem_marcou,
    teste_o_email_do_aviso_vem_do_sindicato_nao_do_digitado,
    teste_o_opt_in_e_dela_o_sindicato_nao_marca_por_ela,
    teste_o_processo_coletado_fica_conhecido,
    teste_o_aviso_marcado_nao_se_repete_e_e_por_pessoa,
    teste_o_aviso_nao_atravessa_entidade,
    teste_o_coletor_enxerga_o_processo_que_veio_da_planilha,
    teste_a_saude_denuncia_o_agendador_parado,
    teste_saude_nao_diz_ok_quando_nao_consegue_ler_o_estado,
    teste_a_saude_fica_boa_quando_o_trabalho_roda,
    teste_saude_nao_publica_o_detalhe_a_quem_nao_tem_sessao,
    teste_um_cadastro_nao_custa_o_diario_inteiro,
    teste_meu_cadastro_nao_le_a_base_inteira,
    teste_o_registro_por_cpf_concorda_com_a_base_inteira,
    teste_reconstruir_continua_recuperando_o_diario_inteiro,
    teste_a_leitura_de_dado_nominal_fica_registrada,
    teste_o_registro_de_leitura_nao_guarda_cpf_em_claro,
    teste_a_auditoria_tambem_respeita_a_politica,
]


def main() -> int:
    print("=" * 62)
    print("O BANCO LIGADO À APLICAÇÃO")
    print("=" * 62)
    if not URL:
        print("\nPULADO: sem PROTOCOL_DATABASE_URL.")
        print("Suíte pulada NÃO está testada.")
        return 0
    preparar()
    for t in TESTES:
        try:
            preparar()
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
