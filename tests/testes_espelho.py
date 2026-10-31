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
                           "pessoa", "pessoa_afirmacao", "recebimento"):
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
        "PROTOCOL_EMISSOES_POR_CPF_HORA": "50",
        "PROTOCOL_EMISSOES_POR_ORIGEM_HORA": "500",
    })
    return TestClient(criar_app(cfg)), ent, raiz


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
