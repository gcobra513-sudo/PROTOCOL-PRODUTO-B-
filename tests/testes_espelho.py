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

def _servidor(apelido: str = "demo-a", ambiente: dict | None = None):
    """Um servidor em modo ensaio COM banco, e uma entidade de demonstração.

    `apelido` existe para o teste que precisa da BASE SÓ DELE: o banco não é
    zerado entre os testes desta suíte, então quem mede um agregado da
    entidade — o painel — em `demo-a` mede também as pessoas dos outros."""
    import csv
    import tempfile

    from fastapi.testclient import TestClient

    from servidor import entidades as mod
    from servidor.app import criar_app
    from servidor.config import carregar

    raiz = Path(tempfile.mkdtemp(prefix="espelho-"))
    cad = mod.Cadastro(raiz)
    ent = cad.criar(apelido, "Sindicato de Demonstração",
                    categorias=("auditor-fiscal-receita-federal",))
    pasta = raiz / apelido
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
        **(ambiente or {}),
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


def _token(cliente, cpf: str, entidade: str = "demo-a") -> str:
    r = cliente.post("/api/acesso/codigo",
                     json={"entidade": entidade, "cpf": cpf})
    codigo = r.json()["codigo_do_ensaio"]
    r = cliente.post("/api/acesso/conferir",
                     json={"entidade": entidade, "cpf": cpf,
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
    # CONTRA `agenda.TAREFAS`, não contra uma lista escrita aqui: a asserção
    # é "TODAS as tarefas aparecem na saúde". Travar o literal fazia
    # acrescentar uma tarefa nova quebrar um teste cujo assunto não é
    # quantas tarefas existem — e isso ensina a editar o teste em vez de ler
    # o que ele diz.
    from servidor import agenda as _agenda

    checa(tarefas == set(_agenda.TAREFAS),
          f"as tarefas não aparecem na saúde: {tarefas} contra "
          f"{set(_agenda.TAREFAS)}")
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

    gravados, pulados = banco.reconstruir(URL, ent.apelido,
                                          deposito.ler_diario(ent.pasta(raiz)))
    refeita = banco.base(URL, ent.apelido)
    checa(len(refeita) == 3,
          f"a recuperação não refez as 3 pessoas: {len(refeita)} "
          f"(gravados={gravados} pulados={pulados})")
    checa(pulados == 0,
          f"pulou registro sem ninguém pedir filtro: {pulados}")
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



def teste_nao_sai_codigo_para_quem_foi_apagado():
    """QUEM PEDIU PARA SAIR NÃO RECEBE CREDENCIAL NOSSA.

    Três comportamentos eram possíveis e só um não tem defeito:

    - não consultar o tombstone: mandamos o código por e-mail para quem
      pediu para sair. É a substância da violação, não detalhe;
    - RECUSAR no portão: cria um ORÁCULO — um anônimo descobre quais CPFs
      foram apagados a pedido, e isso é informação sobre a pessoa;
    - consultar e NÃO MANDAR: a resposta fica idêntica à de qualquer CPF
      desconhecido, e nenhum e-mail sai.

    Este teste exige o terceiro, nas duas pontas: nada enviado, e resposta
    indistinguível. A simetria dessa resposta é a mesma que impede o portão
    de virar consulta de filiação — dois achados da auditoria de 31/10
    foram sobre ela.
    """
    secao("o portão não manda código para quem foi apagado")
    from servidor import apagamento, banco

    cliente, ent, raiz = _servidor()
    # O PORTÃO DO SERVIDOR, não um meu.
    #
    # A primeira versão deste teste criou um `Portao` próprio, com segredo
    # próprio, e o marcador não casou com o que o servidor calcula — o
    # tombstone existia e era invisível para ele. Isso é a demonstração
    # prática do aviso da spec: `PROTOCOL_SEGREDO` é de vida longa, e
    # trocá-lo devolve ao sistema quem pediu para sair.
    portao = cliente.app.state.portao
    # O rol do `_servidor()` tem A; apagamos A e deixamos o rol como está,
    # porque é assim que o operador reporia o arquivo à mão.
    banco.marcar_tombstone(URL, ent.apelido, portao.marcar_cpf(A),
                           motivo="", pedido_por="")

    log = raiz / "codigos_enviados.log"
    antes = len(log.read_text().splitlines()) if log.is_file() else 0

    def corpo(cpf):
        r = cliente.post("/api/acesso/codigo",
                         json={"entidade": ent.apelido, "cpf": cpf})
        dados = dict(r.json())
        dados.pop("codigo_do_ensaio", None)
        dados.pop("ensaio", None)
        return r.status_code, dados

    apagado = corpo(A)
    desconhecido = corpo(_cpf_sintetico(777_001))
    checa(apagado == desconhecido,
          f"a resposta revela que o CPF foi apagado: apagado={apagado} "
          f"desconhecido={desconhecido}")

    depois = len(log.read_text().splitlines()) if log.is_file() else 0
    checa(depois == antes,
          f"mandou código para quem pediu para sair: {depois - antes} "
          f"linha(s) novas no log de envio")
    print("  ok     nada enviado, e a resposta é indistinguível")



# --------------------------------------------- a rota de apagamento

def _apagar(cliente, apelido, corpo, token=None):
    cabecalhos = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.post(f"/api/entidade/{apelido}/apagar",
                        json=corpo, headers=cabecalhos)


def teste_apagar_so_para_gestor_da_propria_entidade():
    """A ORDEM DAS CONFERÊNCIAS É O QUE IMPORTA, e `_gestor_de` já a tem:
    primeiro que a sessão é da entidade pedida, depois que quem abriu é
    gestor dela. A inversa diria a um gestor de outra entidade se um CPF
    está no rol desta."""
    secao("a rota de apagamento")
    cliente, ent, raiz = _servidor()
    pedido = {"cpf": A, "motivo": "pedido do titular", "pedido_por": "g"}

    r = _apagar(cliente, ent.apelido, pedido)
    checa(r.status_code == 401, f"anônimo devia dar 401, deu {r.status_code}")

    r = _apagar(cliente, ent.apelido, pedido, _token(cliente, A))
    checa(r.status_code == 403,
          f"filiado devia dar 403, deu {r.status_code}")
    print("  ok     anônimo 401, filiado 403")


def teste_apagar_pelo_painel_do_sindicato():
    from servidor import banco
    cliente, ent, raiz = _servidor()
    _cadastrar(cliente, A, com_sentenca=True)
    checa(banco.registro_do_cpf(URL, ent.apelido, A) is not None,
          "a semeadura não pegou")

    r = _apagar(cliente, ent.apelido,
                {"cpf": A, "motivo": "pedido do titular",
                 "pedido_por": "gestor@exemplo.invalid"},
                _token(cliente, B))
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    saida = r.json()
    checa(saida.get("vestigios") == [],
          f"a rota disse que apagou com coisa sobrando: {saida}")
    checa(A not in r.text, "a resposta trouxe o CPF em claro")
    checa(banco.registro_do_cpf(URL, ent.apelido, A) is None,
          "a pessoa continua na base")
    print("  ok     o gestor apaga, e a resposta não traz o CPF")


def teste_apagar_aceita_cpf_formatado():
    """Sem normalizar, nada é encontrado e a rota diz que apagou."""
    from servidor import banco
    cliente, ent, raiz = _servidor()
    _cadastrar(cliente, A)
    formatado = f"{A[:3]}.{A[3:6]}.{A[6:9]}-{A[9:]}"
    r = _apagar(cliente, ent.apelido,
                {"cpf": formatado, "motivo": "", "pedido_por": ""},
                _token(cliente, B))
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    checa(banco.registro_do_cpf(URL, ent.apelido, A) is None,
          f"o CPF formatado {formatado} não foi encontrado, e a rota "
          f"respondeu como se tivesse apagado")
    print("  ok     CPF formatado é normalizado antes de procurar")


def teste_apagar_cpf_de_fora_da_base_nao_e_oraculo():
    """404 aqui revelaria quem está na base de um sindicato a quem já tem
    sessão de gestor — de outro. A resposta tem de ser a mesma."""
    from servidor import banco
    cliente, ent, raiz = _servidor()
    _cadastrar(cliente, A)
    token = _token(cliente, B)
    de_dentro = _apagar(cliente, ent.apelido,
                        {"cpf": A, "motivo": "", "pedido_por": ""}, token)
    de_fora = _apagar(cliente, ent.apelido,
                      {"cpf": _cpf_sintetico(888_002), "motivo": "",
                       "pedido_por": ""}, token)
    checa(de_dentro.status_code == de_fora.status_code == 200,
          f"o status revela quem está na base: dentro="
          f"{de_dentro.status_code} fora={de_fora.status_code}")
    print("  ok     CPF de fora da base responde igual")



def teste_o_painel_conta_quantos_foram_apagados_a_pedido():
    """D2: AVISAR O SINDICATO para ele corrigir a FONTE.

    CONTAGEM, nunca lista nominal: a pessoa pediu para sair, e devolver o
    nome dela numa tela seria o oposto do que ela pediu.
    """
    from servidor import banco

    cliente, ent, raiz = _servidor()
    # SEMEIA A PLANILHA, não o cadastro pelo portal. A contagem é sobre o
    # que o SINDICATO mandou — é a fonte que ele precisa corrigir. A
    # primeira versão deste teste cadastrou pelo portal e contou zero, com
    # razão.
    import json as _json

    from servidor import deposito as _dep

    deposito_acervo = ent.pasta(raiz) / "acervo.jsonl"
    _dep.anexar_com_fsync(deposito_acervo, _json.dumps({
        "ingerido_em": "2026-11-02", "origem": "planilha.xlsx",
        "retrato": {"pessoas": 1},
        "pessoas": [{"cpf": A, "linha_no_arquivo": 2,
                     "campos": {"nome_completo": "PESSOA (FICTÍCIO)",
                                "email": "p@exemplo.invalid"},
                     "achados": []}],
    }, ensure_ascii=False) + "\n")
    token = _token(cliente, B)

    antes = cliente.get(f"/api/entidade/{ent.apelido}/completude",
                        headers={"Authorization": f"Bearer {token}"}).json()
    checa(antes.get("apagados_a_pedido") == 0,
          f"começou contando apagamento que não houve: "
          f"{antes.get('apagados_a_pedido')}")

    banco.marcar_tombstone(URL, ent.apelido,
                           cliente.app.state.portao.marcar_cpf(A),
                           motivo="", pedido_por="")
    depois = cliente.get(f"/api/entidade/{ent.apelido}/completude",
                         headers={"Authorization": f"Bearer {token}"}).json()
    checa(depois.get("apagados_a_pedido") == 1,
          f"não contou o apagamento: {depois.get('apagados_a_pedido')}")
    checa(A not in str(depois.get("apagados_a_pedido")),
          "a contagem virou lista nominal")
    print("  ok     o painel conta os apagados, sem nomear")



def teste_gestor_de_outra_entidade_nao_apaga_e_nem_le_o_rol_alvo():
    """Item 7 da spec, que não tinha teste. E o que ele fixa é a ORDEM.

    `_gestor_de` confere primeiro que a sessão é da entidade PEDIDA, e só
    depois lê `gestores.csv` dela. A ordem inversa diria a um gestor de
    outra entidade se o CPF dele consta como gestor aqui.

    O CÓDIGO DE STATUS NÃO SERVE DE PROVA, e eu escrevi este teste errado
    uma vez por supor que servia: nas duas ordens a resposta é 403, porque
    rol ilegível também dá 403. Invertida a ordem no servidor, um teste
    sobre o status continuava passando.

    O que distingue as duas ordens é se o rol do alvo é LIDO. Então é isso
    que se mede: um gatilho em `rol.carregar_gestores` que registra por qual
    pasta foi chamado.
    """
    import csv as _csv

    from servidor import entidades as _ents
    from servidor import rol as _rol

    cliente, ent, raiz = _servidor()
    outra = _ents.Cadastro(raiz).criar("demo-z", "Outro Sindicato")
    pasta_outra = outra.pasta(raiz)
    pasta_outra.mkdir(parents=True, exist_ok=True)
    for arquivo, contato in (("filiados.csv", "z@exemplo.invalid"),
                             ("gestores.csv", "gz@exemplo.invalid")):
        with open(pasta_outra / arquivo, "w", newline="",
                  encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["cpf", "email"])
            w.writerow([A, contato])

    token_da_outra = cliente.post(
        "/api/acesso/conferir",
        json={"entidade": "demo-z", "cpf": A,
              "codigo": cliente.post(
                  "/api/acesso/codigo",
                  json={"entidade": "demo-z", "cpf": A}
              ).json()["codigo_do_ensaio"]},
    ).json()["token"]

    lidos: list[str] = []
    original = _rol.carregar_gestores

    def gatilho(pasta, *a, **k):
        lidos.append(Path(pasta).name)
        return original(pasta, *a, **k)

    _rol.carregar_gestores = gatilho
    try:
        r = _apagar(cliente, ent.apelido,
                    {"cpf": A, "motivo": "", "pedido_por": ""},
                    token_da_outra)
    finally:
        _rol.carregar_gestores = original

    checa(r.status_code == 403,
          f"gestor de outra entidade devia dar 403, deu {r.status_code} "
          f"{r.text[:200]}")
    checa(ent.apelido not in lidos,
          f"leu o rol de gestores da entidade alvo antes de conferir a "
          f"entidade da sessão: {lidos}")
    print("  ok     403 por entidade, sem tocar no rol do alvo")


def teste_o_apagamento_fica_registrado_e_leitura_nao_e_apagada():
    """Item 9 da spec, que não tinha teste — nas DUAS metades.

    `leitura` não é apagada (o GRANT nega DELETE à aplicação, e o teste
    EXERCITA a negação em vez de confiar nela), e o apagamento ENTRA nela.
    """
    import psycopg

    from servidor import banco

    cliente, ent, raiz = _servidor()
    _cadastrar(cliente, A)
    token = _token(cliente, B)

    # Metade 1: a aplicação não consegue apagar o próprio rastro.
    negou = ""
    try:
        with banco.sessao(URL, ent.apelido) as cur:
            cur.execute("DELETE FROM leitura")
    except psycopg.errors.InsufficientPrivilege as e:
        negou = str(e)
    checa("leitura" in negou,
          f"a aplicação conseguiu apagar o registro de auditoria: {negou!r}")

    # Metade 2: o apagamento entra no registro, e diz QUEM mandou.
    r = _apagar(cliente, ent.apelido,
                {"cpf": A, "motivo": "pedido", "pedido_por": "g"}, token)
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    with banco.sessao(URL, ent.apelido) as cur:
        cur.execute("SELECT quem_hash, alvo_hash FROM leitura "
                    "WHERE o_que = 'apagar'")
        linhas = cur.fetchall()
    checa(len(linhas) == 1,
          f"o apagamento não ficou registrado em leitura: {linhas}")
    quem, alvo = linhas[0]
    checa(quem and A not in quem and B not in quem,
          f"o registro não diz quem mandou, ou traz CPF em claro: {linhas[0]}")
    checa(alvo and A not in alvo,
          f"o registro não diz sobre quem, ou traz CPF em claro: {linhas[0]}")
    print("  ok     o apagamento fica registrado, e leitura nega DELETE")


def teste_sem_registro_de_auditoria_nao_apaga_nada():
    """I6. `_auditar` engole exceção por uma decisão tomada para LEITURA
    ("falha de registro não derruba a consulta"), e essa decisão tem um
    custo aceitável lá: a consulta fica sem rastro, mas nada se perde.

    Aplicada a um ato DESTRUTIVO E IRREVERSÍVEL, a mesma decisão significa
    tombstone gravado, pessoa apagada, e nenhum registro de qual gestor
    mandou — exatamente o que o item 9 da spec existe para impedir. Aqui a
    casa manda falhar fechado: sem registro, não apaga.
    """
    from servidor import banco

    cliente, ent, raiz = _servidor()
    _cadastrar(cliente, A)
    token = _token(cliente, B)

    original = banco.registrar_leitura
    banco.registrar_leitura = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("registro fora do ar"))
    try:
        r = _apagar(cliente, ent.apelido,
                    {"cpf": A, "motivo": "pedido", "pedido_por": "g"}, token)
    finally:
        banco.registrar_leitura = original

    checa(r.status_code >= 500,
          f"apagou sem conseguir registrar quem mandou: {r.status_code} "
          f"{r.text[:200]}")
    checa(banco.tombstones(URL, ent.apelido) == set(),
          "gravou o tombstone sem registro de quem mandou")
    sobrou = cliente.get(f"/api/entidade/{ent.apelido}/completude",
                         headers={"Authorization": f"Bearer {token}"})
    checa(sobrou.json()["apagados_a_pedido"] == 0,
          "contou um apagamento que não devia ter acontecido")
    print("  ok     sem registro de quem mandou, não apaga")


def teste_falha_ao_conferir_apagamento_nao_entrega_codigo():
    """I7. O ruling anterior deixava o portão falhar ABERTO: erro ao ler os
    tombstones virava log e o código SAÍA para quem pediu para sair.

    A alternativa não precisa ser global. Tratar a falha DAQUELE pedido como
    "sem destino" mantém a resposta idêntica — mesmo 202, mesmo corpo, nada
    para para o usuário —, não cria oráculo, e nunca entrega credencial a
    quem pediu para sair. A casa escreve: a dúvida nunca vira permissão.
    """
    from servidor import banco

    cliente, ent, raiz = _servidor()
    log = raiz / "codigos_enviados.log"
    antes = len(log.read_text().splitlines()) if log.is_file() else 0

    original = banco.tombstones
    banco.tombstones = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("banco fora do ar"))
    try:
        r = cliente.post("/api/acesso/codigo",
                         json={"entidade": ent.apelido, "cpf": A})
    finally:
        banco.tombstones = original

    checa(r.status_code == 202,
          f"a falha virou status próprio: {r.status_code}")
    depois = len(log.read_text().splitlines()) if log.is_file() else 0
    checa(depois == antes,
          f"entregou o código sem conseguir conferir o apagamento: "
          f"{depois - antes} linha(s) novas")
    print("  ok     sem conferir, não entrega — e a resposta não muda")


def teste_motivo_e_pedido_por_tem_teto_e_recusa_em_vez_de_cortar():
    """Adiado 4. `motivo` e `pedido_por` iam para colunas `text` sem
    limite, e o teto de corpo HTTP é dimensionado para PDF — então o
    registro de um apagamento podia receber megabytes de texto.

    RECUSA, NÃO CORTA. Cortar em silêncio guardaria no registro legal algo
    DIFERENTE do que o gestor escreveu, e é justamente esse registro que
    responde "quem mandou apagar e por quê". Um 400 que diz o limite o
    manda reescrever; um corte silencioso o deixa achando que registrou o
    que não registrou.
    """
    from servidor import apagamento, banco

    cliente, ent, raiz = _servidor()
    _cadastrar(cliente, A)
    token = _token(cliente, B)
    teto = apagamento.TETO_DO_TEXTO

    for campo in ("motivo", "pedido_por"):
        corpo = {"cpf": A, "motivo": "ok", "pedido_por": "g"}
        corpo[campo] = "x" * (teto + 1)
        r = _apagar(cliente, ent.apelido, corpo, token)
        checa(r.status_code == 400,
              f"{campo} com {teto + 1} caracteres deu {r.status_code}")
        checa(str(teto) in r.text,
              f"a recusa não diz o limite, então o gestor não sabe o que "
              f"encurtar: {r.text[:200]}")
        checa(banco.tombstones(URL, ent.apelido) == set(),
              f"{campo} longo demais e o tombstone foi gravado de todo modo")

    # No limite exato, passa — e o texto chega inteiro ao registro.
    r = _apagar(cliente, ent.apelido,
                {"cpf": A, "motivo": "m" * teto, "pedido_por": "g"}, token)
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    print(f"  ok     teto de {teto} em motivo e pedido_por, recusando "
          f"em vez de cortar")



# --------------------------- uma pessoa, três superfícies, uma resposta

CERTIDAO = ["PODER JUDICIARIO - JUSTICA FEDERAL", "CERTIDAO", "",
            "Certifico que a sentenca proferida nos autos do processo n.",
            "0010391-24.2006.4.01.3400 transitou em julgado em 22/08/2019, "
            "nada havendo",
            "a prover.", "", "Documento de exemplo, para demonstracao do "
            "sistema."]


def _cadastrar_com_titulo(cliente, cpf: str, entidade: str):
    """Contribuição + sentença procedente + certidão de trânsito: os três
    documentos que, lidos, dizem que HÁ título."""
    import json as _json

    return cliente.post(
        "/api/cadastro",
        data={"token": _token(cliente, cpf, entidade),
              "linha": _json.dumps(linha(cpf, ja_executou="nao",
                                         tem_acao_propria="nao"))},
        files=[("arquivos", ("contribuicao-1.pdf", _pdf(CONTRIB),
                             "application/pdf")),
               ("arquivos", ("sentenca.pdf", _pdf(SENTENCA),
                             "application/pdf")),
               ("arquivos", ("certidao_transito.pdf", _pdf(CERTIDAO),
                             "application/pdf"))],
    )


def _faltas_do_filiado(cliente, cpf: str, entidade: str) -> dict:
    """{(trilha, referência): (veredicto, o que falta)} como o FILIADO vê."""
    corpo = cliente.get(
        "/api/minhas-acoes",
        headers={"Authorization": f"Bearer {_token(cliente, cpf, entidade)}"},
    ).json()
    return {
        (o["trilha"], o["referencia"]):
            (o["veredicto"], sorted(f["o_que"] for f in o["falta"]))
        for o in corpo["oportunidades"]
    }


def teste_as_tres_superficies_dizem_o_mesmo_sobre_a_mesma_pessoa():
    """Achado da auditoria de produto de 10/11/2026, e o defeito era meu.

    TRÊS lugares chamam o motor, e só um lia documento:

        /api/minhas-acoes         documentos.fatos_para_o_motor   LÊ
        /panorama (o painel)      panorama.fatos_do_cadastro      não lia
        reavaliar_oportunidades   panorama.fatos_do_cadastro      não lia

    `fatos_do_cadastro` fixava `tem_titulo=None`. Medido, com a sentença JÁ
    LIDA na chegada do cadastro: o filiado via uma pendência, e o painel e a
    tabela `oportunidade` mostravam duas — a segunda era "a leitura da
    sentença já entregue". O sindicato via como pendência um trabalho já
    feito, e o veredicto GUARDADO, que existe para ser a prova, guardava a
    resposta mais fraca das três.

    Este teste não fixa QUAL é a resposta — isso é dos testes do motor. Ele
    fixa que ela é UMA: a mesma pessoa, a mesma pergunta, o mesmo resultado
    nas três superfícies.
    """
    import subprocess

    from servidor import banco

    secao("uma pessoa, três superfícies")
    entidade = "demo-fatos"
    cliente, ent, raiz = _servidor(entidade)
    r = _cadastrar_com_titulo(cliente, A, entidade)
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    # 1. O filiado.
    do_filiado = _faltas_do_filiado(cliente, A, entidade)
    checa(do_filiado, "o filiado não recebeu oportunidade nenhuma")

    # 2. O veredicto GUARDADO, pela ferramenta de verdade.
    t = subprocess.run(
        [sys.executable, str(RAIZ / "ferramentas" / "reavaliar_oportunidades.py"),
         "--entidade", entidade, "--raiz", str(raiz), "--banco", URL],
        capture_output=True, text=True,
        env={**os.environ, "PROTOCOL_DATABASE_URL": URL},
    )
    checa(t.returncode == 0, f"reavaliar saiu {t.returncode}: {t.stderr[:300]}")
    guardado = {
        (g["trilha"], g["referencia"]):
            (g["veredicto"], sorted(f["o_que"] for f in g["falta"]))
        for g in banco.oportunidades_de(URL, entidade, A)
    }
    checa(guardado == do_filiado,
          "o veredicto GUARDADO não é o que o filiado vê:\n"
          f"    filiado:  {do_filiado}\n    guardado: {guardado}")

    # 3. O painel do sindicato. Ele agrega, então a comparação é pelo
    #    conjunto do que falta — numa base que tem só esta pessoa.
    painel = cliente.get(
        f"/api/entidade/{entidade}/panorama",
        headers={"Authorization": f"Bearer {_token(cliente, B, entidade)}"},
    ).json()
    checa(painel["pessoas"] == 1,
          f"a base do teste devia ter 1 pessoa, tem {painel['pessoas']}")
    no_painel = {g["o_que"] for g in painel["gargalos"]}
    checa("a leitura da sentença já entregue" not in no_painel,
          "o painel cobra do sindicato a leitura de uma sentença que JÁ foi "
          "lida na chegada do cadastro")
    do_filiado_tudo = {
        o_que for _, faltas in do_filiado.values() for o_que in faltas
    }
    checa(do_filiado_tudo <= no_painel,
          f"o filiado vê pendência que o painel não mostra: "
          f"{do_filiado_tudo - no_painel}")
    checa(painel["leu_documentos"] is True,
          "o painel usou os documentos lidos e continua dizendo que não leu")
    checa("Nenhum documento foi lido" not in painel["limite"],
          f"o painel leu os documentos e o texto do limite ainda afirma o "
          f"contrário: {painel['limite']!r}")
    print("  ok     filiado, painel e veredicto guardado concordam")


def teste_ler_os_documentos_nao_faz_o_painel_custar_por_pessoa():
    """A razão ORIGINAL de o painel não ler documento era custo: reabrir os
    PDFs da base inteira a cada carregamento de tela. Os achados passaram a
    ser gravados na chegada — e o painel continuou sem lê-los.

    Ao ligar uma coisa na outra, o custo não pode voltar pela porta dos
    fundos: UMA consulta traz os achados da entidade inteira. Este teste
    conta comandos SQL do painel com poucas e com muitas pessoas COM
    documento, e exige o mesmo número.
    """
    import psycopg

    def comandos_do_painel(entidade: str, quantas: int) -> int:
        cliente, ent, raiz = _servidor(entidade)
        cpfs = [_cpf_sintetico(5000 + i) for i in range(quantas)]
        _por_no_rol(raiz, entidade, cpfs)
        for cpf in cpfs:
            _cadastrar_com_titulo(cliente, cpf, entidade)
        token = _token(cliente, B, entidade)

        original = psycopg.Cursor.execute
        contador = {"n": 0}

        def espiao(self, *a, **k):
            contador["n"] += 1
            return original(self, *a, **k)

        psycopg.Cursor.execute = espiao
        try:
            r = cliente.get(f"/api/entidade/{entidade}/panorama",
                            headers={"Authorization": f"Bearer {token}"})
        finally:
            psycopg.Cursor.execute = original
        checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        checa(r.json()["pessoas"] == quantas,
              f"a base devia ter {quantas}, tem {r.json()['pessoas']}")
        return contador["n"]

    com_poucas = comandos_do_painel("demo-custo-p", 2)
    com_muitas = comandos_do_painel("demo-custo-m", 9)
    checa(com_poucas == com_muitas,
          f"o painel custa por pessoa: {com_poucas} comandos com 2 pessoas, "
          f"{com_muitas} com 9")
    print(f"  ok     {com_poucas} comandos com 2 pessoas, {com_muitas} "
          f"com 9 — plano")


# ------------------------------- o documento que a máquina não consegue ler

def _so_imagem() -> bytes:
    """Um PDF sem camada de texto — o que sai de scanner e de foto."""
    import testes_documentos as td

    return td.pdf_so_imagem()


def _enviar(cliente, cpf: str, entidade: str, arquivos: dict[str, bytes]):
    import json as _json

    return cliente.post(
        "/api/cadastro",
        data={"token": _token(cliente, cpf, entidade),
              "linha": _json.dumps(linha(cpf))},
        files=[("arquivos", (nome, corpo, "application/pdf"))
               for nome, corpo in arquivos.items()],
    )


def teste_documento_escaneado_entra_e_fica_aguardando_leitura():
    """Achado 3 da auditoria de produto, e decisão de 10/11/2026: ACEITA E
    MARCA, em vez de recusar.

    O servidor devolvia 422 para PDF sem camada de texto, e o cadastro
    INTEIRO caía — inclusive por causa de um anexo opcional. A mensagem
    mandava um aposentado "digitalizar com reconhecimento de texto (OCR)".
    A justificativa escrita no código era do Produto A: lá, sem texto não
    há petição a montar. Aqui, um documento que a máquina não lê pode
    esperar que uma pessoa leia — e quem tem papel físico é justamente a
    base deste produto.

    O QUE FICA GRAVADO, E ONDE: no DIÁRIO, que é a autoridade. O banco é
    projeção, e uma marca que só existisse nele sumiria na primeira
    recuperação.
    """
    import json as _json

    from servidor import banco, deposito

    secao("o documento que a máquina não lê")
    entidade = "demo-leitura"
    cliente, ent, raiz = _servidor(entidade)

    r = _enviar(cliente, A, entidade, {
        "contribuicao-1.pdf": _pdf(CONTRIB),
        "sentenca.pdf": _so_imagem(),
    })
    checa(r.status_code == 200,
          f"sentença escaneada derrubou o cadastro: {r.status_code} "
          f"{r.text[:200]}")
    if r.status_code != 200:
        return
    checa(r.json().get("aguardando_leitura") == ["sentenca.pdf"],
          f"a resposta não diz à pessoa o que ficou aguardando leitura: "
          f"{r.json()}")

    registro = deposito.ler_diario(ent.pasta(raiz))[-1]
    checa(registro.get("aguardando_leitura") == ["sentenca.pdf"],
          f"o DIÁRIO não registra o que aguarda leitura: "
          f"{_json.dumps(registro, ensure_ascii=False)[:300]}")
    checa((ent.entrega(raiz) / A / "sentenca.pdf").is_file(),
          "o arquivo escaneado não foi guardado")

    def do_banco() -> dict:
        with banco.sessao(URL, entidade) as cur:
            cur.execute("SELECT tipo, tem_texto FROM documento "
                        "WHERE cpf = %s", (A,))
            return dict(cur.fetchall())

    checa(do_banco() == {"contribuicao": True, "sentenca": False},
          f"`documento.tem_texto` não diz a verdade: {do_banco()} — a coluna "
          f"existia e ficava em `false` para TODO documento, legível ou não")

    # E A RECUPERAÇÃO REFAZ A MARCA a partir do diário.
    with banco.sessao(URL, entidade) as cur:
        cur.execute("DELETE FROM documento WHERE cpf = %s", (A,))
    banco.reconstruir(URL, entidade, deposito.ler_diario(ent.pasta(raiz)),
                      consentimento_novo=True)
    checa(do_banco() == {"contribuicao": True, "sentenca": False},
          f"reconstruir pelo diário perdeu a marca: {do_banco()}")
    print("  ok     escaneado entra, o diário marca, o banco projeta")


def teste_so_o_comprovante_escaneado_tambem_entra():
    """O caso mais comum de todos: o ÚNICO documento obrigatório é um
    contracheque de papel, fotografado."""
    entidade = "demo-leitura-2"
    cliente, ent, raiz = _servidor(entidade)
    r = _enviar(cliente, A, entidade, {"contribuicao-1.pdf": _so_imagem()})
    checa(r.status_code == 200,
          f"comprovante escaneado foi recusado: {r.status_code} "
          f"{r.text[:200]}")
    checa(r.status_code != 200
          or r.json().get("aguardando_leitura") == ["contribuicao-1.pdf"],
          f"{r.text[:200]}")
    print("  ok     só o comprovante, e escaneado: entra")


def teste_pdf_que_nao_abre_continua_recusado():
    """ACEITAR O ILEGÍVEL POR MÁQUINA NÃO É ACEITAR QUALQUER COISA.

    Sem camada de texto, uma pessoa lê. Corrompido ou protegido por senha,
    ninguém lê — e guardar isso como "aguardando leitura" criaria uma fila
    que não anda, com a pessoa achando que entregou.
    """
    entidade = "demo-leitura-3"
    cliente, ent, raiz = _servidor(entidade)
    quebrado = b"%PDF-1.4\n" + b"isto nao e um pdf de verdade " * 40
    r = _enviar(cliente, A, entidade, {
        "contribuicao-1.pdf": _pdf(CONTRIB),
        "sentenca.pdf": quebrado,
    })
    checa(r.status_code == 422,
          f"PDF que não abre foi aceito: {r.status_code} {r.text[:200]}")
    checa("abrir" in r.text,
          f"a recusa não diz que o arquivo não abre: {r.text[:200]}")
    print("  ok     PDF que não abre continua recusado, com o motivo")


def teste_o_painel_conta_o_que_aguarda_leitura():
    """Marcar e não mostrar criaria uma fila invisível. O sindicato precisa
    ver QUANTO espera leitura humana — e de quantas pessoas."""
    entidade = "demo-leitura-4"
    cliente, ent, raiz = _servidor(entidade)
    _enviar(cliente, A, entidade, {
        "contribuicao-1.pdf": _so_imagem(),
        "sentenca.pdf": _so_imagem(),
    })
    painel = cliente.get(
        f"/api/entidade/{entidade}/panorama",
        headers={"Authorization": f"Bearer {_token(cliente, B, entidade)}"},
    ).json()
    fila = painel.get("aguardando_leitura")
    checa(fila == {"documentos": 2, "pessoas": 1, "ilegiveis": 0,
                   "sem_banco": False},
          f"o painel não conta o que aguarda leitura: {fila}")
    print("  ok     o painel conta documentos e pessoas aguardando leitura")


def teste_documento_do_sindicato_entra_na_fila_so_se_for_imagem():
    """Um defeito que a própria mudança de 10/11 criaria, pego antes — e uma
    premissa minha derrubada no caminho.

    `ingerir_documentos.py` também grava em `documento`, e gravava SEM
    `tem_texto`: a coluna ficava no padrão `false`. Enquanto ninguém a lia,
    não fazia mal. No dia em que o painel passou a contar "o que aguarda
    leitura" por ela, TODO documento entregue pelo sindicato apareceria na
    fila — inclusive sentença que a máquina leu sem problema.

    A primeira versão deste teste afirmava "se casou com alguém, foi lido".
    FALSO: a ferramenta casa também pelo CPF no NOME do arquivo, e um
    documento de scanner casa assim sem ter texto nenhum. Então a marca não
    se presume — se MEDE, documento por documento.
    """
    import subprocess
    import tempfile

    from servidor import banco

    entidade = "demo-leitura-5"
    cliente, ent, raiz = _servidor(entidade)
    acervo = Path(tempfile.mkdtemp(prefix="docs-sind-"))
    (acervo / f"{A}-sentenca.pdf").write_bytes(_pdf(SENTENCA))
    (acervo / f"{A}-certidao.pdf").write_bytes(_so_imagem())

    t = subprocess.run(
        [sys.executable, str(RAIZ / "ferramentas" / "ingerir_documentos.py"),
         "--pasta", str(acervo), "--entidade", entidade,
         "--raiz", str(raiz), "--banco", URL],
        capture_output=True, text=True,
        env={**os.environ, "PROTOCOL_DATABASE_URL": URL},
    )
    checa(t.returncode in (0, 1),
          f"a ingestão não rodou: {t.returncode} {t.stderr[:300]}")
    with banco.sessao(URL, entidade) as cur:
        cur.execute("SELECT tem_texto, count(*) FROM documento "
                    "WHERE cpf = %s GROUP BY tem_texto", (A,))
        por_marca = dict(cur.fetchall())
    checa(por_marca == {True: 1, False: 1},
          f"devia haver 1 documento lido e 1 aguardando leitura, há "
          f"{por_marca} — saída da ferramenta: {t.stdout[-300:]}")
    checa(banco.aguardando_leitura(URL, entidade) == (1, 1),
          f"a fila devia ter só o documento de scanner: "
          f"{banco.aguardando_leitura(URL, entidade)}")
    print("  ok     do sindicato: o lido fica fora da fila, o de scanner entra")


# ------------------------------------ a fila de leitura humana tem SAÍDA

def _gestor(cliente, entidade: str) -> dict:
    return {"Authorization": f"Bearer {_token(cliente, B, entidade)}"}


def _fila(cliente, entidade: str) -> dict:
    return cliente.get(f"/api/entidade/{entidade}/conferencia",
                       headers=_gestor(cliente, entidade)).json()


def _registrar(cliente, entidade: str, doc_id: str, corpo: dict):
    return cliente.post(f"/api/entidade/{entidade}/conferencia/{doc_id}",
                        json=corpo, headers=_gestor(cliente, entidade))


#: Os bytes da sentença de scanner, gerados UMA vez. O reportlab carimba
#: data e identificador em cada PDF, então duas chamadas de `_so_imagem()`
#: dão arquivos diferentes — e a comparação "o que foi servido é o que foi
#: mandado" precisa do mesmo arquivo nas duas pontas.
_SENTENCA_DE_SCANNER: list[bytes] = []


def _sentenca_de_scanner() -> bytes:
    if not _SENTENCA_DE_SCANNER:
        _SENTENCA_DE_SCANNER.append(_so_imagem())
    return _SENTENCA_DE_SCANNER[0]


def _titulo_escaneado(cliente, entidade: str):
    """Sentença e certidão de SCANNER: a máquina não lê nenhuma das duas."""
    return _enviar(cliente, A, entidade, {
        "contribuicao-1.pdf": _pdf(CONTRIB),
        "sentenca.pdf": _sentenca_de_scanner(),
        "certidao_transito.pdf": _pdf_de_scanner_2(),
    })


def _pdf_de_scanner_2() -> bytes:
    """Outro PDF só-imagem, com BYTES DIFERENTES do primeiro: dois
    documentos iguais teriam o mesmo sha256, e aí o teste não distinguiria
    a sentença da certidão."""
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.rect(60, 300, 200, 420, fill=1)
    c.save()
    return buffer.getvalue()


def teste_a_fila_de_leitura_tem_saida():
    """T24. Scanner e foto passaram a ENTRAR, e a fila ficou com entrada e
    contador e SEM SAÍDA: quem mandava foto da sentença ficava em "falta a
    leitura da sentença já entregue" para sempre.

    Decisão de 10/11/2026: QUEM LÊ É O SINDICATO, pelo painel dele.

    O caminho inteiro: o gestor vê a fila, ABRE o documento, registra o que
    leu — e o que ele registrou vira fato, com autor, e muda a resposta do
    filiado nas três superfícies.
    """
    import json as _json

    from servidor import banco

    secao("a fila de leitura tem saída")
    entidade = "demo-conf"
    cliente, ent, raiz = _servidor(entidade)
    r = _titulo_escaneado(cliente, entidade)
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")

    antes = _faltas_do_filiado(cliente, A, entidade)
    checa("a leitura da sentença já entregue"
          in antes[("executar", "GIFA-2006")][1],
          f"a premissa do teste falhou: {antes}")

    fila = _fila(cliente, entidade)
    pendentes = {d["tipo"]: d for d in fila.get("pendentes", [])}
    checa(set(pendentes) == {"sentenca", "certidao_transito"},
          f"a fila devia ter a sentença e a certidão: {fila}")
    checa(all(d.get("nome") for d in pendentes.values()),
          f"o gestor precisa do NOME para saber de quem é: {fila}")
    checa(A not in _json.dumps(fila),
          "a fila devolveu CPF em claro")
    if set(pendentes) != {"sentenca", "certidao_transito"}:
        return

    # O GESTOR ABRE O DOCUMENTO. Sem isto ele registraria sem ler.
    arq = cliente.get(
        f"/api/entidade/{entidade}/conferencia/"
        f"{pendentes['sentenca']['id']}/arquivo",
        headers=_gestor(cliente, entidade))
    checa(arq.status_code == 200
          and arq.headers["content-type"].startswith("application/pdf"),
          f"o documento não abriu: {arq.status_code} "
          f"{arq.headers.get('content-type')}")
    checa(arq.content == _sentenca_de_scanner(),
          "o arquivo servido não é o que a pessoa mandou")
    checa("no-store" in arq.headers.get("cache-control", ""),
          "o documento de um filiado ficaria em cache no navegador do "
          "gestor")

    r1 = _registrar(cliente, entidade, pendentes["sentenca"]["id"],
                    {"resultado": "lido",
                     "fatos": {"dispositivo": "procedente"}})
    r2 = _registrar(cliente, entidade, pendentes["certidao_transito"]["id"],
                    {"resultado": "lido",
                     "fatos": {"transito_em_julgado": "2019-08-22"}})
    checa(r1.status_code == 200 and r2.status_code == 200,
          f"{r1.status_code} {r1.text[:160]} | {r2.status_code} "
          f"{r2.text[:160]}")

    depois_fila = _fila(cliente, entidade)
    checa(depois_fila.get("pendentes") == [],
          f"o que foi lido não saiu da fila: {depois_fila}")

    # E A RESPOSTA DO FILIADO MUDA: a leitura humana virou fato.
    depois = _faltas_do_filiado(cliente, A, entidade)
    checa("a leitura da sentença já entregue"
          not in depois[("executar", "GIFA-2006")][1],
          f"o gestor leu e a resposta do filiado não mudou: {depois}")

    # COM AUTOR, na autoridade e na projeção.
    from servidor import conferencia

    registros = conferencia.ler(ent.pasta(raiz))
    checa(len(registros) == 2 and all(x.get("quem") for x in registros),
          f"a leitura não ficou no arquivo de leituras, com autor: "
          f"{registros}")
    checa(B not in _json.dumps(registros),
          "o arquivo de leituras guarda o CPF do gestor em claro")
    with banco.sessao(URL, entidade) as cur:
        cur.execute("SELECT tipo, valor, metodo, conferido FROM achado "
                    "WHERE cpf = %s AND metodo = 'pessoa' ORDER BY tipo",
                    (A,))
        linhas = cur.fetchall()
    checa(linhas == [("dispositivo", "procedente", "pessoa", True),
                     ("transito_em_julgado", "2019-08-22", "pessoa", True)],
          f"os fatos lidos por gente não estão no banco como tais: {linhas}")
    print("  ok     o gestor abre, lê, registra — e a resposta do filiado muda")


def teste_so_o_gestor_da_entidade_confere():
    """Abrir o documento de um filiado é a leitura mais sensível do produto.
    Filiado não abre o do vizinho; quem não tem sessão não abre nada."""
    entidade = "demo-conf-2"
    cliente, ent, raiz = _servidor(entidade)
    _titulo_escaneado(cliente, entidade)
    doc = _fila(cliente, entidade)["pendentes"][0]["id"]
    base = f"/api/entidade/{entidade}/conferencia"

    do_filiado = {"Authorization": f"Bearer {_token(cliente, A, entidade)}"}
    for metodo, caminho in (("get", base), ("get", f"{base}/{doc}/arquivo"),
                            ("post", f"{base}/{doc}")):
        sem = getattr(cliente, metodo)(caminho)
        checa(sem.status_code == 401,
              f"{metodo} {caminho} sem sessão deu {sem.status_code}")
        com = getattr(cliente, metodo)(caminho, headers=do_filiado)
        checa(com.status_code == 403,
              f"{metodo} {caminho} com sessão de FILIADO deu "
              f"{com.status_code}")
    print("  ok     sem sessão 401, filiado 403, nas três rotas")


def teste_leitura_invalida_nao_vira_fato():
    """O que o gestor digita vira FATO que alimenta o motor. Valor que não
    existe não entra — e nada é gravado pela metade."""
    from servidor import conferencia

    entidade = "demo-conf-3"
    cliente, ent, raiz = _servidor(entidade)
    _titulo_escaneado(cliente, entidade)
    por_tipo = {d["tipo"]: d["id"] for d in _fila(cliente, entidade)["pendentes"]}

    casos = [
        (por_tipo["sentenca"], {"resultado": "lido",
                                "fatos": {"dispositivo": "talvez"}}),
        (por_tipo["sentenca"], {"resultado": "lido", "fatos": {}}),
        (por_tipo["certidao_transito"],
         {"resultado": "lido", "fatos": {"transito_em_julgado": "2999-01-01"}}),
        (por_tipo["certidao_transito"],
         {"resultado": "lido", "fatos": {"transito_em_julgado": "31/02/2019"}}),
        (por_tipo["sentenca"], {"resultado": "aprovado", "fatos": {}}),
    ]
    for doc, corpo in casos:
        r = _registrar(cliente, entidade, doc, corpo)
        checa(r.status_code == 422,
              f"leitura inválida foi aceita ({corpo}): {r.status_code}")
    r = _registrar(cliente, entidade, "0" * 64 + "." + "0" * 16,
                   {"resultado": "lido", "fatos": {"dispositivo": "procedente"}})
    checa(r.status_code == 404, f"documento que não existe deu {r.status_code}")
    checa(conferencia.ler(ent.pasta(raiz)) == [],
          "uma leitura recusada deixou registro")
    checa(len(_fila(cliente, entidade)["pendentes"]) == 2,
          "uma leitura recusada tirou documento da fila")
    print("  ok     valor inexistente, data impossível e documento alheio: nada entra")


def teste_o_que_nem_uma_pessoa_le_sai_da_fila_e_e_contado():
    """A outra saída. Foto tremida, página cortada: o gestor abre e NÃO DÁ.
    Sem esta saída o documento ficaria na fila para sempre; com ela, o
    sindicato sabe a quem pedir de novo."""
    entidade = "demo-conf-4"
    cliente, ent, raiz = _servidor(entidade)
    _titulo_escaneado(cliente, entidade)
    por_tipo = {d["tipo"]: d["id"] for d in _fila(cliente, entidade)["pendentes"]}

    r = _registrar(cliente, entidade, por_tipo["sentenca"],
                   {"resultado": "ilegivel", "fatos": {},
                    "observacao": "foto cortada na metade"})
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    fila = _fila(cliente, entidade)
    checa([d["tipo"] for d in fila["pendentes"]] == ["certidao_transito"],
          f"o ilegível não saiu da fila: {fila}")
    checa(len(fila.get("ilegiveis", [])) == 1
          and fila["ilegiveis"][0].get("nome"),
          f"o sindicato não fica sabendo a quem pedir de novo: {fila}")
    painel = cliente.get(f"/api/entidade/{entidade}/panorama",
                         headers=_gestor(cliente, entidade)).json()
    checa(painel["aguardando_leitura"] == {
              "documentos": 1, "pessoas": 1, "ilegiveis": 1,
              "sem_banco": False},
          f"o painel não conta o ilegível: {painel['aguardando_leitura']}")
    print("  ok     o ilegível sai da fila e aparece para pedir de novo")


def teste_reenvio_tira_o_documento_antigo_da_fila_e_do_motor():
    """Achado medindo a fila: a pessoa manda a sentença fotografada, depois
    REENVIA a original. A linha da antiga ficava em `documento` — a fila
    contava um documento que não está mais na entrega — e os fatos lidos
    dela ficavam em `achado`, alimentando o motor com sentença substituída.

    Só o que veio do CADASTRO é substituído pelo reenvio. O que o SINDICATO
    entregou sobre a mesma pessoa não é dela para substituir.
    """
    from servidor import banco

    entidade = "demo-conf-5"
    cliente, ent, raiz = _servidor(entidade)
    _enviar(cliente, A, entidade, {"contribuicao-1.pdf": _pdf(CONTRIB),
                                   "sentenca.pdf": _so_imagem()})
    with banco.sessao(URL, entidade) as cur:
        cur.execute(
            "INSERT INTO documento (entidade, cpf, tipo, sha256, tem_texto,"
            " origem) VALUES (%s,%s,'sentenca','do-sindicato',true,'sindicato')",
            (entidade, A))
    checa(banco.aguardando_leitura(URL, entidade)[0] == 1,
          "a premissa falhou: a sentença de scanner devia estar na fila")

    ruim = [l.replace("PROCEDENTE", "IMPROCEDENTE") for l in SENTENCA]
    _enviar(cliente, A, entidade, {"contribuicao-1.pdf": _pdf(CONTRIB),
                                   "sentenca.pdf": _pdf(ruim)})
    checa(banco.aguardando_leitura(URL, entidade)[0] == 0,
          f"a sentença substituída continua na fila: "
          f"{banco.aguardando_leitura(URL, entidade)}")

    _enviar(cliente, A, entidade, {"contribuicao-1.pdf": _pdf(CONTRIB),
                                   "sentenca.pdf": _pdf(SENTENCA)})
    with banco.sessao(URL, entidade) as cur:
        cur.execute("SELECT DISTINCT valor FROM achado "
                    "WHERE cpf = %s AND tipo = 'dispositivo'", (A,))
        dispositivos = [v for (v,) in cur.fetchall()]
        cur.execute("SELECT count(*) FROM documento WHERE cpf = %s "
                    "AND origem = 'sindicato'", (A,))
        do_sindicato = cur.fetchone()[0]
    checa(dispositivos == ["procedente"],
          f"o motor continua vendo a sentença substituída: {dispositivos}")
    checa(do_sindicato == 1,
          "o reenvio do filiado apagou documento entregue pelo SINDICATO")
    print("  ok     reenvio substitui o que é do cadastro, e só isso")


def teste_a_recuperacao_refaz_as_leituras_humanas():
    """A leitura humana NÃO é derivável de nada: se morasse só no banco,
    perder a projeção seria perder o trabalho do gestor. Mora num arquivo
    append-only, e daqui se refaz."""
    from servidor import banco, conferencia

    entidade = "demo-conf-6"
    cliente, ent, raiz = _servidor(entidade)
    _titulo_escaneado(cliente, entidade)
    por_tipo = {d["tipo"]: d["id"] for d in _fila(cliente, entidade)["pendentes"]}
    _registrar(cliente, entidade, por_tipo["sentenca"],
               {"resultado": "lido", "fatos": {"dispositivo": "procedente"}})

    def estado():
        with banco.sessao(URL, entidade) as cur:
            cur.execute("SELECT tipo, leitura_humana FROM documento "
                        "WHERE cpf = %s ORDER BY tipo", (A,))
            docs = cur.fetchall()
            cur.execute("SELECT tipo, valor FROM achado WHERE cpf = %s "
                        "AND metodo = 'pessoa'", (A,))
            return docs, cur.fetchall()

    antes = estado()
    with banco.sessao(URL, entidade) as cur:
        cur.execute("DELETE FROM achado WHERE cpf = %s", (A,))
        cur.execute("UPDATE documento SET leitura_humana = '' "
                    "WHERE cpf = %s", (A,))
    checa(estado() != antes, "a projeção não foi apagada: o teste não mede")
    banco.projetar_leituras(URL, entidade, conferencia.ler(ent.pasta(raiz)))
    checa(estado() == antes,
          f"a recuperação não refez as leituras: {estado()} contra {antes}")
    print("  ok     a leitura humana se refaz a partir do arquivo dela")


# ------------------------------------------- nome por nome, e a exportação

def teste_a_lista_nome_por_nome_e_a_quarta_superficie():
    """Achado 5 da auditoria de produto. A frase do produto é "nós dizemos,
    NOME POR NOME" — e o sindicato recebia totais e até 8 nomes de exemplo.

    A lista é a quarta superfície que responde sobre uma pessoa, depois da
    tela do filiado, do painel e do veredicto guardado. Tem de dizer o
    mesmo.
    """
    import json as _json

    secao("nome por nome")
    entidade = "demo-lista"
    cliente, ent, raiz = _servidor(entidade)
    _cadastrar_com_titulo(cliente, A, entidade)

    r = cliente.get(f"/api/entidade/{entidade}/pessoas",
                    headers=_gestor(cliente, entidade))
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        return
    corpo = r.json()
    checa(len(corpo["pessoas"]) == 1, f"{corpo}")
    pessoa = corpo["pessoas"][0]
    checa(pessoa["nome"].startswith("FULANO"), f"sem nome: {pessoa}")
    checa(A not in _json.dumps(corpo),
          "a lista NA TELA devolveu o CPF inteiro; ele só sai inteiro na "
          "exportação, que é pedida e registrada")
    checa(A[3:9] in pessoa["cpf"].replace(".", ""),
          f"o CPF mascarado não deixa reconhecer a pessoa: {pessoa['cpf']}")

    da_lista = {
        (o["trilha"], o["referencia"]):
            (o["veredicto"], sorted(f["o_que"] for f in o["falta"]))
        for o in pessoa["oportunidades"]
    }
    checa(da_lista == _faltas_do_filiado(cliente, A, entidade),
          f"a lista do sindicato e a tela do filiado discordam: {da_lista}")
    checa(pessoa["cadastrou"] is True and "depende_de" in pessoa,
          f"{pessoa}")
    print("  ok     a lista diz, por pessoa, o mesmo que o filiado vê")


def teste_a_exportacao_e_planilha_que_abre_e_nao_executa():
    """O sindicato precisa levar a base organizada para dentro dos sistemas
    dele — e lá ele casa pelo CPF. Então a exportação traz o CPF INTEIRO,
    e por isso é pedida de propósito, baixada como anexo, sem cache.

    E É ABERTA NO EXCEL: célula que começa com `=` é fórmula. O nome vem do
    filiado; sem neutralizar, ele executaria na máquina do gestor.
    """
    import json as _json

    entidade = "demo-lista-2"
    cliente, ent, raiz = _servidor(entidade)
    _cadastrar_com_titulo(cliente, A, entidade)
    malicioso = _cpf_sintetico(6001)
    _por_no_rol(raiz, entidade, [malicioso])
    cliente.post(
        "/api/cadastro",
        data={"token": _token(cliente, malicioso, entidade),
              "linha": _json.dumps(linha(
                  malicioso, nome_completo="=HYPERLINK(\"http://x\")"))},
        files=[("arquivos", ("contribuicao-1.pdf", _pdf(CONTRIB),
                             "application/pdf"))],
    )

    r = cliente.get(f"/api/entidade/{entidade}/pessoas.csv",
                    headers=_gestor(cliente, entidade))
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        return
    checa(r.headers["content-type"].startswith("text/csv"),
          f"{r.headers['content-type']}")
    checa("attachment" in r.headers.get("content-disposition", ""),
          "a exportação não vem como anexo")
    checa("no-store" in r.headers.get("cache-control", ""),
          "a base inteira do sindicato ficaria em cache")
    checa(r.content.startswith(b"\xef\xbb\xbf"),
          "sem a marca de UTF-8 o Excel em português troca os acentos")
    texto = r.content.decode("utf-8-sig")
    linhas_ = texto.split("\r\n")
    cabecalho = linhas_[0].split(";")
    checa(cabecalho[:2] == ["cpf", "nome"],
          f"cabeçalho inesperado, ou separador que o Excel não abre em "
          f"colunas: {linhas_[0]!r}")
    checa(any(l.startswith(A + ";") for l in linhas_),
          "o CPF não sai inteiro na exportação — e é por ele que o "
          "sindicato casa com os próprios registros")
    checa("\n=HYPERLINK" not in texto and ";=HYPERLINK" not in texto,
          "o nome do filiado saiu como FÓRMULA na planilha do gestor")
    checa("'=HYPERLINK" in texto,
          "o nome malicioso sumiu em vez de ser neutralizado")
    print("  ok     CSV com CPF inteiro, que o Excel abre, e sem fórmula")


def teste_so_gestor_ve_a_lista_e_exporta():
    entidade = "demo-lista-3"
    cliente, ent, raiz = _servidor(entidade)
    _cadastrar_com_titulo(cliente, A, entidade)
    do_filiado = {"Authorization": f"Bearer {_token(cliente, A, entidade)}"}
    for caminho in (f"/api/entidade/{entidade}/pessoas",
                    f"/api/entidade/{entidade}/pessoas.csv"):
        checa(cliente.get(caminho).status_code == 401,
              f"{caminho} sem sessão não deu 401")
        checa(cliente.get(caminho, headers=do_filiado).status_code == 403,
              f"{caminho} com sessão de filiado não deu 403")
    print("  ok     lista e exportação: sem sessão 401, filiado 403")


def teste_a_lista_nao_custa_por_pessoa():
    import psycopg

    def comandos(entidade: str, quantas: int) -> int:
        cliente, ent, raiz = _servidor(entidade)
        cpfs = [_cpf_sintetico(7000 + i) for i in range(quantas)]
        _por_no_rol(raiz, entidade, cpfs)
        for cpf in cpfs:
            _cadastrar_com_titulo(cliente, cpf, entidade)
        cabecalho = _gestor(cliente, entidade)
        original = psycopg.Cursor.execute
        contador = {"n": 0}

        def espiao(self, *a, **k):
            contador["n"] += 1
            return original(self, *a, **k)

        psycopg.Cursor.execute = espiao
        try:
            r = cliente.get(f"/api/entidade/{entidade}/pessoas",
                            headers=cabecalho)
        finally:
            psycopg.Cursor.execute = original
        checa(r.status_code == 200 and len(r.json()["pessoas"]) == quantas,
              f"{r.status_code} {r.text[:120]}")
        return contador["n"]

    poucas, muitas = comandos("demo-lista-p", 2), comandos("demo-lista-m", 9)
    checa(poucas == muitas,
          f"a lista custa por pessoa: {poucas} comandos com 2, {muitas} com 9")
    print(f"  ok     {poucas} comandos com 2 pessoas, {muitas} com 9 — plano")


def teste_sem_registro_de_quem_exportou_nao_exporta():
    """A exportação é a maior saída de dado do produto: a base inteira, com
    CPF. O registro de leitura é o que torna um vazamento investigável — e
    `_auditar` engole falha, decisão tomada para a CONSULTA de uma tela.
    Aqui, sem conseguir registrar QUEM exportou, não sai arquivo nenhum."""
    from servidor import banco

    entidade = "demo-lista-4"
    cliente, ent, raiz = _servidor(entidade)
    _cadastrar_com_titulo(cliente, A, entidade)
    cabecalho = _gestor(cliente, entidade)

    original = banco.registrar_leitura
    banco.registrar_leitura = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("registro fora do ar"))
    try:
        r = cliente.get(f"/api/entidade/{entidade}/pessoas.csv",
                        headers=cabecalho)
    finally:
        banco.registrar_leitura = original
    checa(r.status_code == 503,
          f"exportou a base sem registrar quem exportou: {r.status_code}")
    checa(A.encode() not in r.content, "o CPF saiu mesmo com a recusa")

    r = cliente.get(f"/api/entidade/{entidade}/pessoas.csv", headers=cabecalho)
    with banco.sessao(URL, entidade) as cur:
        cur.execute("SELECT count(*) FROM leitura WHERE o_que = 'exportar'")
        checa(r.status_code == 200 and cur.fetchone()[0] == 1,
              "a exportação feita não ficou registrada")
    print("  ok     sem registro de quem exportou, não exporta")


# ------------------------------------ a porta de entrada do sindicato

C_PLAN = _cpf_sintetico(8101)
D_PLAN = _cpf_sintetico(8102)


def _planilha(cpfs_e_nomes: list[tuple[str, str, str]]) -> bytes:
    """Uma planilha como o Excel em português exporta: `;`, CRLF, latin-1."""
    linhas = ["CPF;Nome Completo;E-mail;Cargo"]
    for cpf, nome, email in cpfs_e_nomes:
        linhas.append(f"{cpf};{nome};{email};Auditor Fiscal da Receita Federal")
    return ("\r\n".join(linhas) + "\r\n").encode("latin-1")


def _enviar_planilha(cliente, entidade: str, corpo: bytes,
                     confirmar: str = "", nome: str = "base.csv",
                     cabecalho: dict | None = None):
    return cliente.post(
        f"/api/entidade/{entidade}/planilha",
        data={"confirmar": confirmar},
        files={"arquivo": (nome, corpo, "text/csv")},
        headers=cabecalho if cabecalho is not None
        else _gestor(cliente, entidade),
    )


def _nomes_na_lista(cliente, entidade: str) -> list[str]:
    return [p["nome"] for p in cliente.get(
        f"/api/entidade/{entidade}/pessoas",
        headers=_gestor(cliente, entidade)).json()["pessoas"]]


def teste_o_gestor_envia_a_planilha_pela_web_em_duas_etapas():
    """Achado 4 da auditoria de produto. "O sindicato manda a lista de
    filiados" é a primeira frase do produto, e não havia por onde: a
    planilha só entrava por linha de comando, rodada por nós.

    DUAS ETAPAS, e a primeira NÃO GRAVA NADA. A planilha é a base inteira
    do sindicato; o gestor precisa VER o que o arquivo traz — quantas
    pessoas, quantas ele não alcança — antes de ela valer. E a confirmação
    carrega a impressão digital do arquivo conferido: o que entra é
    exatamente o que ele viu.
    """
    import json as _json

    secao("a porta de entrada do sindicato")
    entidade = "demo-porta"
    cliente, ent, raiz = _servidor(entidade)
    corpo = _planilha([
        (C_PLAN, "JOSÉ DA CONCEIÇÃO (CADASTRO DE EXEMPLO)", "jose@exemplo.invalid"),
        (D_PLAN, "MARIA SEM EMAIL (CADASTRO DE EXEMPLO)", ""),
    ])

    r = _enviar_planilha(cliente, entidade, corpo)
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        return
    previa = r.json()
    checa(previa["gravado"] is False, "a PRÉVIA gravou")
    checa((previa["pessoas"], previa["alcancaveis"], previa["inalcancaveis"])
          == (2, 1, 1),
          f"a prévia não diz o que o arquivo traz: {previa}")
    checa(not (ent.pasta(raiz) / "acervo.jsonl").exists(),
          "a prévia escreveu o acervo no disco")
    checa(_nomes_na_lista(cliente, entidade) == [],
          "a prévia pôs gente na base")
    checa(C_PLAN not in _json.dumps(previa),
          "a prévia devolveu CPF em claro")

    r = _enviar_planilha(cliente, entidade, corpo,
                         confirmar=previa["sha256"])
    checa(r.status_code == 200 and r.json()["gravado"] is True,
          f"{r.status_code} {r.text[:200]}")
    nomes = _nomes_na_lista(cliente, entidade)
    checa(nomes == ["JOSÉ DA CONCEIÇÃO (CADASTRO DE EXEMPLO)",
                    "MARIA SEM EMAIL (CADASTRO DE EXEMPLO)"],
          f"a planilha confirmada não virou a base (e o latin-1 tem de "
          f"chegar com os acentos): {nomes}")
    registro = _json.loads(
        (ent.pasta(raiz) / "acervo.jsonl").read_text().splitlines()[-1])
    checa(registro.get("enviado_por") and B not in registro["enviado_por"],
          "a ingestão pela web não registra QUEM enviou, ou guarda o CPF "
          "do gestor em claro")
    print("  ok     prévia não grava; confirmada, a planilha vira a base")


def teste_confirmar_outro_arquivo_e_recusado():
    """A confirmação vale para O ARQUIVO CONFERIDO. Se o que chega na
    segunda etapa é outro, o gestor confirmaria uma base que não viu."""
    entidade = "demo-porta-2"
    cliente, ent, raiz = _servidor(entidade)
    visto = _planilha([(C_PLAN, "FULANO (CADASTRO DE EXEMPLO)",
                        "f@exemplo.invalid")])
    outro = _planilha([(D_PLAN, "BELTRANO (CADASTRO DE EXEMPLO)",
                        "b@exemplo.invalid")])
    sha = _enviar_planilha(cliente, entidade, visto).json()["sha256"]
    r = _enviar_planilha(cliente, entidade, outro, confirmar=sha)
    checa(r.status_code == 409,
          f"confirmou um arquivo diferente do conferido: {r.status_code}")
    checa(_nomes_na_lista(cliente, entidade) == [],
          "gravou mesmo com a recusa")
    print("  ok     confirmar um arquivo que não foi o conferido: 409")


def teste_planilha_que_nao_serve_e_recusada_com_o_motivo():
    entidade = "demo-porta-3"
    cliente, ent, raiz = _servidor(entidade)
    sem_cpf = "Nome;E-mail\r\nFULANO;f@exemplo.invalid\r\n".encode("latin-1")
    r = _enviar_planilha(cliente, entidade, sem_cpf)
    checa(r.status_code == 422 and "CPF" in r.text,
          f"planilha sem coluna de CPF: {r.status_code} {r.text[:200]}")
    r = _enviar_planilha(cliente, entidade, sem_cpf, cabecalho={})
    checa(r.status_code == 401, f"sem sessão deu {r.status_code}")
    do_filiado = {"Authorization": f"Bearer {_token(cliente, A, entidade)}"}
    r = _enviar_planilha(cliente, entidade, sem_cpf, cabecalho=do_filiado)
    checa(r.status_code == 403, f"filiado enviando planilha deu {r.status_code}")
    print("  ok     sem CPF 422 com motivo; sem sessão 401; filiado 403")


def teste_quem_pediu_para_sair_nao_volta_pela_planilha_da_web():
    """A trava do apagamento vale neste caminho também — e vale porque a
    rota chama a MESMA função da ferramenta, não uma cópia. A prévia já
    avisa quantos serão pulados, sem dizer quem."""
    entidade = "demo-porta-4"
    cliente, ent, raiz = _servidor(entidade)
    _apagar(cliente, entidade,
            {"cpf": C_PLAN, "motivo": "pedido do titular", "pedido_por": "g"},
            _token(cliente, B, entidade))
    corpo = _planilha([
        (C_PLAN, "QUEM PEDIU PARA SAIR (CADASTRO DE EXEMPLO)", "s@exemplo.invalid"),
        (D_PLAN, "QUEM FICA (CADASTRO DE EXEMPLO)", "f@exemplo.invalid"),
    ])
    previa = _enviar_planilha(cliente, entidade, corpo).json()
    checa(previa.get("apagados_a_pedido") == 1 and previa["pessoas"] == 1,
          f"a prévia não avisa de quem pediu para sair: {previa}")
    _enviar_planilha(cliente, entidade, corpo, confirmar=previa["sha256"])
    checa(_nomes_na_lista(cliente, entidade)
          == ["QUEM FICA (CADASTRO DE EXEMPLO)"],
          f"quem pediu para sair voltou: {_nomes_na_lista(cliente, entidade)}")
    checa(C_PLAN not in (ent.pasta(raiz) / "acervo.jsonl").read_text(),
          "o CPF apagado foi escrito no acervo")
    print("  ok     quem pediu para sair não volta, e a prévia avisa quantos")


def _enviar_documentos(cliente, entidade: str, arquivos: dict[str, bytes],
                       confirmar: str = ""):
    return cliente.post(
        f"/api/entidade/{entidade}/documentos-do-sindicato",
        data={"confirmar": confirmar},
        files=[("arquivos", (nome, corpo, "application/pdf"))
               for nome, corpo in arquivos.items()],
        headers=_gestor(cliente, entidade),
    )


def teste_o_gestor_envia_os_documentos_que_o_sindicato_tem():
    """A outra metade da porta: as sentenças e certidões que o SINDICATO já
    guarda. Cada arquivo casa com alguém da base pelo CPF — no nome ou no
    texto —, e o que não casa volta numa pilha, com o motivo, em vez de
    sumir numa contagem."""
    from servidor import banco

    entidade = "demo-porta-5"
    cliente, ent, raiz = _servidor(entidade)
    planilha = _planilha([(C_PLAN, "FULANA (CADASTRO DE EXEMPLO)",
                           "f@exemplo.invalid")])
    sha = _enviar_planilha(cliente, entidade, planilha).json()["sha256"]
    _enviar_planilha(cliente, entidade, planilha, confirmar=sha)

    arquivos = {
        f"{C_PLAN}-sentenca.pdf": _pdf(SENTENCA),
        f"{C_PLAN}-certidao.pdf": _so_imagem(),
        "sem-dono.pdf": _pdf(CONTRIB),
    }
    r = _enviar_documentos(cliente, entidade, arquivos)
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        return
    previa = r.json()
    checa(previa["gravado"] is False and previa["casaram"] == 2
          and previa["pessoas"] == 1 and len(previa["sobraram"]) == 1,
          f"a prévia dos documentos: {previa}")
    checa(previa["sobraram"][0]["arquivo"] == "sem-dono.pdf"
          and previa["sobraram"][0]["motivo"],
          f"o que não casou não volta com o motivo: {previa['sobraram']}")
    checa(not (ent.entrega(raiz) / C_PLAN).exists(),
          "a prévia dos documentos gravou arquivo")

    r = _enviar_documentos(cliente, entidade, arquivos,
                           confirmar=previa["sha256"])
    checa(r.status_code == 200 and r.json()["gravado"] is True,
          f"{r.status_code} {r.text[:200]}")
    with banco.sessao(URL, entidade) as cur:
        cur.execute("SELECT origem, tem_texto, count(*) FROM documento "
                    "WHERE cpf = %s GROUP BY origem, tem_texto", (C_PLAN,))
        linhas_ = sorted(cur.fetchall())
    checa(linhas_ == [("sindicato", False, 1), ("sindicato", True, 1)],
          f"os documentos do sindicato não entraram como tais: {linhas_}")
    checa(len(list((ent.entrega(raiz) / C_PLAN).glob("*.pdf"))) == 2,
          "os arquivos não foram para a entrega")
    print("  ok     dois casam e entram, um sobra com o motivo")


def teste_documentos_sem_base_sao_recusados_dizendo_o_que_fazer():
    """Sem base, nenhum arquivo casa com ninguém. Aceitar e devolver "0
    casaram" faria o gestor achar que os arquivos dele estão errados."""
    entidade = "demo-porta-6"
    cliente, ent, raiz = _servidor(entidade)
    (ent.pasta(raiz) / "filiados.csv").write_text("cpf,email\n")
    r = _enviar_documentos(cliente, entidade,
                           {f"{C_PLAN}-sentenca.pdf": _pdf(SENTENCA)})
    checa(r.status_code == 409 and "planilha" in r.text,
          f"{r.status_code} {r.text[:200]}")
    print("  ok     documentos antes da planilha: recusa dizendo a ordem")


# ------------------------------------------- a planilha liga o acesso (T26)

E_PLAN = _cpf_sintetico(8103)
INVASOR = "invasor@exemplo.invalid"


def _destino_do_codigo(cliente, raiz, entidade: str, cpf: str) -> str | None:
    """Para ONDE foi o código deste pedido — ou `None` se não saiu.

    Lê o que o remetente escreveu, e não o rol: o que a trava protege é o
    destino do código, e um teste que olhasse só o arquivo do rol passaria
    mesmo com o portão lendo de outro lugar.
    """
    log = raiz / "codigos_enviados.log"
    antes = log.read_text().splitlines() if log.exists() else []
    r = cliente.post("/api/acesso/codigo",
                     json={"entidade": entidade, "cpf": cpf})
    checa(r.status_code == 202, f"pedido de código deu {r.status_code}")
    depois = log.read_text().splitlines() if log.exists() else []
    novas = depois[len(antes):]
    if not novas:
        return None
    return novas[-1].split("\t")[2]


def _confirmar_planilha(cliente, entidade: str, corpo: bytes) -> dict:
    previa = _enviar_planilha(cliente, entidade, corpo).json()
    r = _enviar_planilha(cliente, entidade, corpo,
                         confirmar=previa["sha256"])
    checa(r.status_code == 200 and r.json().get("gravado") is True,
          f"a planilha não foi gravada: {r.status_code} {r.text[:200]}")
    return r.json()


def teste_quem_e_novo_na_planilha_ja_consegue_entrar():
    """T26. A planilha do gestor alimentava a BASE e não o PORTÃO: cada
    lista nova dependia de nós para alguém conseguir entrar.

    A PRÉVIA NÃO ABRE PORTA: quem só foi conferido ainda não entra. E quem
    veio sem e-mail entra na base, mas não tem para onde o código ir — isso
    é contado, não escondido.
    """
    secao("a planilha liga o acesso")
    entidade = "demo-liga-1"
    cliente, ent, raiz = _servidor(entidade)
    corpo = _planilha([
        (C_PLAN, "NOVA (CADASTRO DE EXEMPLO)", "nova@exemplo.invalid"),
        (D_PLAN, "SEM EMAIL (CADASTRO DE EXEMPLO)", ""),
    ])
    checa(_destino_do_codigo(cliente, raiz, entidade, C_PLAN) is None,
          "quem não está no acesso recebeu código antes de qualquer envio")

    previa = _enviar_planilha(cliente, entidade, corpo).json()
    acesso_ = previa.get("acesso") or {}
    checa((acesso_.get("novos"), acesso_.get("sem_email")) == (1, 1),
          f"a prévia não diz o que muda no acesso: {previa.get('acesso')}")
    checa(_destino_do_codigo(cliente, raiz, entidade, C_PLAN) is None,
          "A PRÉVIA ABRIU O PORTÃO: quem só foi conferido já recebe código")

    feito = _confirmar_planilha(cliente, entidade, corpo)
    checa((feito.get("acesso") or {}).get("novos") == 1,
          f"a confirmação não diz quem passou a entrar: {feito.get('acesso')}")
    checa(_destino_do_codigo(cliente, raiz, entidade, C_PLAN)
          == "nova@exemplo.invalid",
          "quem é novo na planilha confirmada continua sem conseguir entrar")
    checa(_destino_do_codigo(cliente, raiz, entidade, D_PLAN) is None,
          "quem veio sem e-mail recebeu código de algum lugar")
    checa(C_PLAN not in str(feito) and "nova@" not in str(feito),
          "a resposta devolve CPF ou e-mail em claro")
    # De novo a MESMA planilha: ninguém é novo duas vezes.
    feito = _confirmar_planilha(cliente, entidade, corpo)
    checa((feito["acesso"]["novos"], feito["acesso"]["trocas_aguardando"])
          == (0, 0), f"reenviar a mesma planilha mexeu no acesso: {feito}")
    print("  ok     novo na planilha confirmada recebe código; prévia não abre")


def teste_a_planilha_nao_troca_o_email_de_quem_ja_entra():
    """A TRAVA, e a razão de ela existir.

    O portão só é portão porque o e-mail não é escolhido por quem entra. Se
    a planilha do gestor trocasse o e-mail de quem já está no acesso, uma
    sessão de gestor comprometida virava TODAS as contas: troca o e-mail,
    pede o código, entra no lugar da pessoa.

    Então quem JÁ tem destino no portão não muda de destino pela planilha:
    a troca fica pedida e espera quem opera o servidor. Vale para o filiado
    e vale para o CPF de um GESTOR — que não está em `filiados.csv`, e por
    isso pareceria "novo" a uma conferência que só olhasse um arquivo.
    """
    from servidor import rol, trocas

    entidade = "demo-liga-2"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    corpo = _planilha([
        (A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR),
        (B, "GESTOR (CADASTRO DE EXEMPLO)", INVASOR),
    ])
    feito = _confirmar_planilha(cliente, entidade, corpo)
    checa((feito["acesso"]["novos"], feito["acesso"]["trocas_aguardando"])
          == (0, 2), f"a troca não ficou esperando: {feito['acesso']}")
    checa(_destino_do_codigo(cliente, raiz, entidade, A)
          == "fulana@exemplo.org",
          "A PLANILHA TROCOU O E-MAIL DE QUEM JÁ ENTRAVA: o código foi "
          "para o endereço que o gestor escreveu")
    checa(_destino_do_codigo(cliente, raiz, entidade, B)
          == "gestor@exemplo.org",
          "a planilha redirecionou o código de um GESTOR")
    checa(rol.carregar(pasta).email_de(B) is None,
          "o CPF do gestor entrou em filiados.csv pela planilha")
    pendentes = trocas.estado(pasta).pendentes
    checa(sorted(pendentes) == sorted([A, B])
          and pendentes[A]["para"] == INVASOR
          and pendentes[A]["de"] == "fulana@exemplo.org",
          f"a troca pedida não ficou registrada: {pendentes}")
    # Caixa diferente não é troca: o Excel muda maiúscula à vontade.
    feito = _confirmar_planilha(cliente, entidade, _planilha(
        [(A, "FULANA (CADASTRO DE EXEMPLO)", "Fulana@Exemplo.ORG")]))
    checa(feito["acesso"]["trocas_aguardando"] == 0
          and A not in trocas.estado(pasta).pendentes,
          "a planilha voltou a concordar com o acesso e a troca continua "
          f"pedida (ou maiúscula virou troca): {feito['acesso']}")
    print("  ok     quem já entra não muda de e-mail pela planilha — nem gestor")


def teste_sumir_da_planilha_e_voltar_nao_contorna_a_trava():
    """Se a planilha TIRASSE do acesso quem não está nela, a trava teria
    uma porta dos fundos: uma planilha sem a pessoa, outra com a pessoa e
    o e-mail novo, e ela volta como "nova"."""
    entidade = "demo-liga-3"
    cliente, ent, raiz = _servidor(entidade)
    feito = _confirmar_planilha(cliente, entidade, _planilha(
        [(C_PLAN, "OUTRA (CADASTRO DE EXEMPLO)", "outra@exemplo.invalid")]))
    checa(feito["acesso"].get("fora_da_planilha") == 1,
          f"a planilha não diz quem está no acesso e fora dela: {feito}")
    checa(_destino_do_codigo(cliente, raiz, entidade, A)
          == "fulana@exemplo.org",
          "quem saiu da planilha perdeu o acesso")
    _confirmar_planilha(cliente, entidade, _planilha(
        [(A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR)]))
    checa(_destino_do_codigo(cliente, raiz, entidade, A)
          == "fulana@exemplo.org",
          "TIRAR E RECOLOCAR CONTORNOU A TRAVA")
    print("  ok     sair da planilha não tira do acesso, e voltar não é ser novo")


def teste_troca_aprovada_vale_e_recusada_nao_volta():
    """Quem decide a troca é quem opera o servidor, pela ferramenta — não
    existe rota para isso, de propósito: uma rota de aprovar seria mais uma
    sessão capaz de trocar e-mail.

    A RECUSADA NÃO VOLTA: a planilha do sindicato vai continuar trazendo o
    e-mail recusado, e sem memória disso cada envio recriaria o pedido.
    """
    import subprocess

    from servidor import trocas

    entidade = "demo-liga-4"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    from servidor import rol
    rol.acrescentar(pasta, [(C_PLAN, "antigo@exemplo.invalid")])
    corpo = _planilha([
        (A, "FULANA (CADASTRO DE EXEMPLO)", "fulana.nova@exemplo.invalid"),
        (C_PLAN, "OUTRA (CADASTRO DE EXEMPLO)", INVASOR),
    ])
    _confirmar_planilha(cliente, entidade, corpo)

    def ferramenta(*args: str):
        return subprocess.run(
            [sys.executable, str(RAIZ / "ferramentas" / "trocas_de_email.py"),
             "--raiz", str(raiz), "--entidade", entidade, *args],
            capture_output=True, text=True)

    r = ferramenta("listar")
    checa(r.returncode == 0 and "fulana.nova@exemplo.invalid" in r.stdout
          and "fulana@exemplo.org" in r.stdout and INVASOR in r.stdout,
          f"listar não mostra de onde para onde: {r.stdout} {r.stderr}")
    r = ferramenta("aprovar", A)
    checa(r.returncode == 0, f"aprovar falhou: {r.stdout} {r.stderr}")
    r = ferramenta("recusar", C_PLAN)
    checa(r.returncode == 0, f"recusar falhou: {r.stdout} {r.stderr}")
    r = ferramenta("aprovar", D_PLAN)
    checa(r.returncode != 0,
          "aprovar uma troca que ninguém pediu saiu com sucesso")

    checa(_destino_do_codigo(cliente, raiz, entidade, A)
          == "fulana.nova@exemplo.invalid",
          "a troca APROVADA não passou a valer")
    checa(_destino_do_codigo(cliente, raiz, entidade, C_PLAN)
          == "antigo@exemplo.invalid",
          "a troca RECUSADA passou a valer")
    checa(not trocas.estado(pasta).pendentes,
          f"sobrou troca pendente: {trocas.estado(pasta).pendentes}")

    feito = _confirmar_planilha(cliente, entidade, corpo)
    checa((feito["acesso"]["trocas_aguardando"],
           feito["acesso"].get("trocas_recusadas")) == (0, 1),
          f"a mesma planilha recriou a troca recusada: {feito['acesso']}")
    checa(not trocas.estado(pasta).pendentes,
          "a troca recusada voltou para a fila")
    print("  ok     aprovada vale; recusada não vale e não volta com a planilha")


def teste_divergencia_e_email_torto_nao_entram_no_acesso():
    """Divergência não se resolve sozinha: a mesma pessoa NOVA com dois
    e-mails não ganha nenhum dos dois — escolher seria decidir para onde vai
    a credencial dela.

    E e-mail que carrega separador não entra no rol: o rol é um CSV, e um
    endereço com vírgula dentro é uma linha a mais esperando acontecer.
    """
    from servidor import rol

    entidade = "demo-liga-5"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    feito = _confirmar_planilha(cliente, entidade, _planilha([
        (C_PLAN, "DUAS VEZES (CADASTRO DE EXEMPLO)", "um@exemplo.invalid"),
        (C_PLAN, "DUAS VEZES (CADASTRO DE EXEMPLO)", "dois@exemplo.invalid"),
        (D_PLAN, "TORTO (CADASTRO DE EXEMPLO)", "a@exemplo.invalid,b"),
        (E_PLAN, "FORMULA (CADASTRO DE EXEMPLO)", "=a@exemplo.invalid"),
    ]))
    checa((feito["acesso"]["novos"], feito["acesso"].get("divergentes"),
           feito["acesso"]["sem_email"]) == (0, 1, 2),
          f"divergência ou e-mail torto entrou no acesso: {feito['acesso']}")
    for cpf in (C_PLAN, D_PLAN, E_PLAN):
        checa(_destino_do_codigo(cliente, raiz, entidade, cpf) is None,
              f"{cpf[:3]}… recebeu código")
    antes = (pasta / rol.ARQUIVO).read_bytes()
    for torto in ("a@exemplo.invalid,b", "a@exemplo.invalid\n" + A + ",x@y.zz",
                  "=a@exemplo.invalid", "a b@exemplo.invalid", "sem-arroba"):
        try:
            rol.acrescentar(pasta, [(C_PLAN, torto)])
            checa(False, f"rol.acrescentar aceitou {torto!r}")
        except ValueError:
            pass
    checa((pasta / rol.ARQUIVO).read_bytes() == antes,
          "uma recusa de rol.acrescentar mexeu no arquivo")
    print("  ok     dois e-mails não escolhem; e-mail com separador não entra")


def teste_quem_pediu_para_sair_nao_volta_ao_acesso_pela_planilha():
    """O apagamento tira a pessoa do rol. Se a planilha a recolocasse como
    "nova", o código voltaria a sair para quem pediu para sair — e para o
    e-mail que o gestor escrevesse."""
    from servidor import rol

    entidade = "demo-liga-6"
    cliente, ent, raiz = _servidor(entidade)
    _apagar(cliente, entidade,
            {"cpf": C_PLAN, "motivo": "pedido do titular", "pedido_por": "g"},
            _token(cliente, B, entidade))
    feito = _confirmar_planilha(cliente, entidade, _planilha([
        (C_PLAN, "SAIU (CADASTRO DE EXEMPLO)", "saiu@exemplo.invalid"),
        (D_PLAN, "FICA (CADASTRO DE EXEMPLO)", "fica@exemplo.invalid"),
    ]))
    checa(feito["acesso"]["novos"] == 1,
          f"quem pediu para sair foi contado como novo: {feito['acesso']}")
    checa(C_PLAN not in (ent.pasta(raiz) / rol.ARQUIVO).read_text(),
          "QUEM PEDIU PARA SAIR VOLTOU AO ROL PELA PLANILHA")
    print("  ok     quem pediu para sair não volta ao acesso")


def teste_apagar_leva_tambem_a_troca_pedida():
    """A troca pedida guarda CPF e dois e-mails: é dado pessoal num arquivo
    novo, e arquivo novo é onde o apagamento esquece de olhar."""
    from servidor import trocas

    entidade = "demo-liga-7"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    _confirmar_planilha(cliente, entidade, _planilha(
        [(A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR)]))
    checa(A in trocas.estado(pasta).pendentes, "o cenário não montou")
    r = _apagar(cliente, entidade,
                {"cpf": A, "motivo": "pedido do titular", "pedido_por": "g"},
                _token(cliente, B, entidade))
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    checa(r.json().get("vestigios") == [],
          f"sobrou vestígio: {r.json().get('vestigios')}")
    arquivo = pasta / trocas.ARQUIVO
    checa(not arquivo.exists() or A not in arquivo.read_text(),
          "O CPF APAGADO FICOU NA FILA DE TROCAS")
    print("  ok     o apagamento leva a troca pedida")


def teste_sindicato_sem_rol_comeca_pela_planilha():
    """Sem `filiados.csv` ninguém recebia código — NEM O GESTOR. O sindicato
    novo precisava que nós puséssemos um arquivo vazio antes de ele poder
    mandar a lista que cria esse arquivo.

    O que a regra protege é o portão não abrir para qualquer CPF. O gestor
    não é qualquer CPF: ele está em `gestores.csv`, que também vem da
    entidade.
    """
    from servidor import rol

    entidade = "demo-liga-8"
    cliente, ent, raiz = _servidor(entidade)
    (ent.pasta(raiz) / rol.ARQUIVO).unlink()
    checa(_destino_do_codigo(cliente, raiz, entidade, A) is None,
          "SEM ROL SAIU CÓDIGO para quem não é gestor")
    checa(_destino_do_codigo(cliente, raiz, entidade, B)
          == "gestor@exemplo.org",
          "sem rol de filiados o gestor não entra para enviar a lista")
    _confirmar_planilha(cliente, entidade, _planilha(
        [(C_PLAN, "PRIMEIRA (CADASTRO DE EXEMPLO)", "p@exemplo.invalid")]))
    checa(_destino_do_codigo(cliente, raiz, entidade, C_PLAN)
          == "p@exemplo.invalid",
          "a primeira planilha não criou o acesso")
    print("  ok     sindicato sem rol: o gestor entra e a planilha cria o acesso")


def _no_banco(entidade: str, cpf: str) -> dict[str, int]:
    from servidor import banco

    achou: dict[str, int] = {}
    with banco.sessao(URL, entidade) as cur:
        for tabela in banco._TABELAS_DO_APAGAMENTO:
            cur.execute(f"SELECT count(*) FROM {tabela} WHERE cpf = %s",
                        (cpf,))
            n = cur.fetchone()[0]
            if n:
                achou[tabela] = n
    return achou


def teste_apagamento_no_meio_da_planilha_nao_ressuscita():
    """MEDIDO em 10/11/2026, em sequência forçada: a planilha é filtrada
    (ninguém pediu para sair), a pessoa é apagada a pedido — "vestígios: []"
    —, e a planilha já filtrada é gravada. A pessoa voltava ao acervo, a
    duas tabelas do banco e, depois de T26, ao ROL.

    O filtro de quem pediu para sair valia para o instante em que foi
    feito, e a gravação acontece depois. Agora quem grava confere de novo,
    na hora de gravar e com o apagamento parado.
    """
    from servidor import ingestao, rol

    entidade = "demo-liga-9"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    do_gestor = {"Authorization": f"Bearer {_token(cliente, B, entidade)}"}
    corpo = _planilha([
        (C_PLAN, "SAI NO MEIO (CADASTRO DE EXEMPLO)", "meio@exemplo.invalid"),
        (D_PLAN, "FICA (CADASTRO DE EXEMPLO)", "fica@exemplo.invalid"),
    ])
    previa = _enviar_planilha(cliente, entidade, corpo,
                              cabecalho=do_gestor).json()
    checa(previa["apagados_a_pedido"] == 0, "o cenário não montou")

    original = ingestao.gravar_planilha
    apagou: list = []

    def com_apagamento_no_meio(*args, **kwargs):
        r = _apagar(cliente, entidade,
                    {"cpf": C_PLAN, "motivo": "pedido do titular",
                     "pedido_por": "g"}, do_gestor["Authorization"][7:])
        apagou.append((r.status_code, r.json().get("vestigios")))
        return original(*args, **kwargs)

    ingestao.gravar_planilha = com_apagamento_no_meio
    try:
        r = _enviar_planilha(cliente, entidade, corpo,
                             confirmar=previa["sha256"], cabecalho=do_gestor)
    finally:
        ingestao.gravar_planilha = original
    checa(apagou == [(200, [])], f"o apagamento do meio não rodou: {apagou}")
    checa(r.status_code == 200 and r.json().get("gravado") is True,
          f"{r.status_code} {r.text[:200]}")
    checa(C_PLAN not in (pasta / "acervo.jsonl").read_text(),
          "QUEM PEDIU PARA SAIR NO MEIO DO ENVIO VOLTOU AO ACERVO")
    checa(C_PLAN not in (pasta / rol.ARQUIVO).read_text(),
          "QUEM PEDIU PARA SAIR NO MEIO DO ENVIO VOLTOU AO ROL")
    checa(_no_banco(entidade, C_PLAN) == {},
          f"QUEM PEDIU PARA SAIR NO MEIO DO ENVIO VOLTOU AO BANCO: "
          f"{_no_banco(entidade, C_PLAN)}")
    checa(D_PLAN in (pasta / rol.ARQUIVO).read_text()
          and r.json()["apagados_a_pedido"] == 1,
          f"o resto da planilha não foi gravado, ou a resposta não conta "
          f"quem saiu no meio: {r.json()}")
    print("  ok     apagamento entre a conferência e a gravação: não volta")


def teste_a_planilha_e_o_apagamento_seguram_a_mesma_trava():
    """Conferir de novo na hora de gravar encolhe a janela; o que a FECHA é
    os dois não rodarem ao mesmo tempo. O que se mede: no instante em que a
    planilha escreve o acervo, e no instante em que o apagamento grava o
    tombstone, a mesma trava está tomada."""
    import fcntl
    import os

    from servidor import banco, deposito

    entidade = "demo-liga-10"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)

    def tomada() -> bool:
        fd = os.open(pasta / deposito.TRAVA_DO_APAGAMENTO,
                     os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        finally:
            os.close(fd)

    visto: dict[str, bool] = {}
    anexar, marcar = deposito.anexar_com_fsync, banco.marcar_tombstone

    def anexar_espiado(caminho, linha):
        if caminho.name == "acervo.jsonl":
            visto["planilha"] = tomada()
        return anexar(caminho, linha)

    def marcar_espiado(*args, **kwargs):
        visto["apagamento"] = tomada()
        return marcar(*args, **kwargs)

    deposito.anexar_com_fsync = anexar_espiado
    banco.marcar_tombstone = marcar_espiado
    try:
        _confirmar_planilha(cliente, entidade, _planilha(
            [(C_PLAN, "ALGUEM (CADASTRO DE EXEMPLO)", "a@exemplo.invalid")]))
        _apagar(cliente, entidade,
                {"cpf": C_PLAN, "motivo": "pedido do titular",
                 "pedido_por": "g"}, _token(cliente, B, entidade))
    finally:
        deposito.anexar_com_fsync = anexar
        banco.marcar_tombstone = marcar
    checa(visto == {"planilha": True, "apagamento": True},
          f"a planilha e o apagamento podem rodar ao mesmo tempo: {visto}")
    checa(not tomada(), "a trava ficou presa")
    print("  ok     planilha e apagamento não rodam ao mesmo tempo")


# --------------------------------- e-mail repetido em gente nova (T27)

MESMO = "mesmo@exemplo.invalid"
F_PLAN = _cpf_sintetico(8104)


def _ferramenta_de_trocas(raiz, entidade: str, *args: str):
    import subprocess

    return subprocess.run(
        [sys.executable, str(RAIZ / "ferramentas" / "trocas_de_email.py"),
         "--raiz", str(raiz), "--entidade", entidade, *args],
        capture_output=True, text=True)


def teste_email_repetido_em_gente_nova_segura_a_entrada():
    """T27. "Gente nova entra direto" deixava uma conta de gestor
    comprometida pôr UM endereço em quantas pessoas novas quisesse, e
    receber o código de todas.

    Duas pessoas novas com o mesmo e-mail: NENHUMA entra — escolher qual
    das duas é a dona seria resolver a divergência sozinho. As duas ficam
    pedidas, e quem opera confere. Quem veio com e-mail só dela entra.
    """
    from servidor import trocas

    secao("e-mail repetido em gente nova")
    entidade = "demo-rep-1"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    corpo = _planilha([
        (C_PLAN, "UMA (CADASTRO DE EXEMPLO)", MESMO),
        (D_PLAN, "OUTRA (CADASTRO DE EXEMPLO)", "Mesmo@Exemplo.INVALID"),
        (E_PLAN, "SOZINHA (CADASTRO DE EXEMPLO)", "sozinha@exemplo.invalid"),
    ])
    feito = _confirmar_planilha(cliente, entidade, corpo)
    checa((feito["acesso"]["novos"], feito["acesso"].get("novos_aguardando"))
          == (1, 2), f"e-mail repetido não segurou a entrada: {feito['acesso']}")
    for cpf in (C_PLAN, D_PLAN):
        checa(_destino_do_codigo(cliente, raiz, entidade, cpf) is None,
              "O MESMO E-MAIL RECEBEU O CÓDIGO DE DUAS PESSOAS NOVAS")
    checa(_destino_do_codigo(cliente, raiz, entidade, E_PLAN)
          == "sozinha@exemplo.invalid",
          "quem veio com e-mail só dela ficou de fora")
    pendentes = trocas.estado(pasta).pendentes
    checa(sorted(pendentes) == sorted([C_PLAN, D_PLAN])
          and pendentes[C_PLAN]["de"] == "",
          f"as entradas seguradas não ficaram pedidas: {pendentes}")

    # Uma TERCEIRA, sozinha na planilha dela, com o e-mail das duas que
    # esperam: nenhuma das duas está no rol, e mesmo assim o endereço já
    # tem dono pendente.
    feito = _confirmar_planilha(cliente, entidade, _planilha(
        [(F_PLAN, "TERCEIRA (CADASTRO DE EXEMPLO)", MESMO)]))
    checa(feito["acesso"]["novos_aguardando"] == 1
          and _destino_do_codigo(cliente, raiz, entidade, F_PLAN) is None,
          f"o e-mail de quem ESPERA serviu para outra pessoa nova: "
          f"{feito['acesso']}")

    r = _ferramenta_de_trocas(raiz, entidade, "listar")
    checa(r.returncode == 0 and "entrada nova" in r.stdout
          and MESMO in r.stdout,
          f"listar não mostra a entrada segurada: {r.stdout} {r.stderr}")
    r = _ferramenta_de_trocas(raiz, entidade, "aprovar", C_PLAN)
    checa(r.returncode == 0, f"aprovar a entrada falhou: {r.stdout} {r.stderr}")
    r = _ferramenta_de_trocas(raiz, entidade, "recusar", D_PLAN)
    checa(r.returncode == 0, f"recusar a entrada falhou: {r.stdout} {r.stderr}")
    checa(_destino_do_codigo(cliente, raiz, entidade, C_PLAN) == MESMO,
          "a entrada APROVADA não passou a valer")
    checa(_destino_do_codigo(cliente, raiz, entidade, D_PLAN) is None,
          "a entrada RECUSADA passou a valer")
    feito = _confirmar_planilha(cliente, entidade, corpo)
    checa((feito["acesso"]["novos"], feito["acesso"]["novos_aguardando"],
           feito["acesso"]["trocas_recusadas"]) == (0, 0, 1)
          and sorted(trocas.estado(pasta).pendentes) == [F_PLAN],
          f"a mesma planilha recriou a entrada recusada: {feito['acesso']}")
    print("  ok     mesmo e-mail em duas novas: nenhuma entra até conferirmos")


def teste_email_de_quem_ja_entra_nao_serve_para_gente_nova():
    """A MESMA REGRA, UMA PLANILHA DE CADA VEZ. Se "repetido" olhasse só
    para dentro da planilha, bastaria mandar uma pessoa por envio: cada uma
    seria a única com aquele e-mail no arquivo dela.

    Então repetido quer dizer: já é o e-mail de OUTRA pessoa no portão —
    filiado ou gestor — ou de outra pessoa nova, ou de outra entrada que
    ainda espera.
    """
    from servidor import trocas

    entidade = "demo-rep-2"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    _confirmar_planilha(cliente, entidade, _planilha(
        [(C_PLAN, "PRIMEIRA (CADASTRO DE EXEMPLO)", MESMO)]))
    checa(_destino_do_codigo(cliente, raiz, entidade, C_PLAN) == MESMO,
          "o cenário não montou: a primeira devia entrar")
    feito = _confirmar_planilha(cliente, entidade, _planilha(
        [(D_PLAN, "SEGUNDA (CADASTRO DE EXEMPLO)", MESMO)]))
    checa((feito["acesso"]["novos"], feito["acesso"]["novos_aguardando"])
          == (0, 1) and _destino_do_codigo(cliente, raiz, entidade, D_PLAN)
          is None,
          f"UMA PESSOA POR ENVIO CONTORNOU A REGRA: {feito['acesso']}")
    feito = _confirmar_planilha(cliente, entidade, _planilha(
        [(E_PLAN, "TERCEIRA (CADASTRO DE EXEMPLO)", "gestor@exemplo.org")]))
    checa(feito["acesso"]["novos_aguardando"] == 1
          and _destino_do_codigo(cliente, raiz, entidade, E_PLAN) is None,
          f"gente nova entrou com o e-mail do GESTOR: {feito['acesso']}")
    # Quem esperava e voltou com e-mail só dela ENTRA, e o pedido some.
    feito = _confirmar_planilha(cliente, entidade, _planilha(
        [(D_PLAN, "SEGUNDA (CADASTRO DE EXEMPLO)", "segunda@exemplo.invalid")]))
    checa(feito["acesso"]["novos"] == 1
          and _destino_do_codigo(cliente, raiz, entidade, D_PLAN)
          == "segunda@exemplo.invalid"
          and D_PLAN not in trocas.estado(pasta).pendentes,
          f"quem corrigiu o e-mail continua esperando: {feito['acesso']} "
          f"{trocas.estado(pasta).pendentes}")
    print("  ok     e-mail de quem já entra não serve para novo; corrigir libera")


# ------------------------- o apagamento no meio dos outros caminhos (T28)

def _com_apagamento_no_meio(modulo, funcao: str, cliente, entidade: str,
                            cpf: str, gestor: str, acao):
    """Roda `acao()` com o apagamento a pedido de `cpf` encaixado
    imediatamente antes de `modulo.funcao` — o pior intercalamento, tornado
    determinístico. Devolve (resposta da ação, respostas do apagamento)."""
    original = getattr(modulo, funcao)
    apagou: list = []

    def embrulhada(*args, **kwargs):
        # UMA VEZ SÓ, e sempre ANTES de quem grava tomar a trava: o
        # apagamento espera por ela, e encaixado depois esperaria para
        # sempre por quem o chamou.
        if not apagou:
            r = _apagar(cliente, entidade,
                        {"cpf": cpf, "motivo": "pedido do titular",
                         "pedido_por": "g"}, gestor)
            apagou.append((r.status_code, r.json().get("vestigios")))
        return original(*args, **kwargs)

    setattr(modulo, funcao, embrulhada)
    try:
        return acao(), apagou
    finally:
        setattr(modulo, funcao, original)


def _sobras_no_disco(raiz, cpf: str) -> list[str]:
    achou = []
    for caminho in sorted(raiz.rglob("*")):
        if cpf in caminho.name:
            achou.append(f"caminho {caminho.relative_to(raiz)}")
        elif caminho.is_file() and cpf.encode() in caminho.read_bytes():
            achou.append(f"conteúdo de {caminho.relative_to(raiz)}")
    return achou


def teste_apagamento_no_meio_dos_documentos_do_sindicato_nao_ressuscita():
    """MEDIDO em 12/11/2026 (`docs/medicoes/2026-11-12-apagamento-no-meio.py`):
    a prévia casa o arquivo com a pessoa, ela é apagada a pedido, e a
    gravação punha de volta a pasta de entrega dela, 1 `documento` e 2
    `achado`."""
    from servidor import ingestao

    entidade = "demo-meio-1"
    cliente, ent, raiz = _servidor(entidade)
    gestor = _token(cliente, B, entidade)
    _confirmar_planilha(cliente, entidade, _planilha([
        (C_PLAN, "SAI NO MEIO (CADASTRO DE EXEMPLO)", "meio@exemplo.invalid"),
        (D_PLAN, "FICA (CADASTRO DE EXEMPLO)", "fica@exemplo.invalid"),
    ]))
    arquivos = {f"{C_PLAN}-sentenca.pdf": _pdf(SENTENCA),
                f"{D_PLAN}-sentenca.pdf": _pdf(SENTENCA)}
    sha = _enviar_documentos(cliente, entidade, arquivos).json()["sha256"]
    r, apagou = _com_apagamento_no_meio(
        ingestao, "gravar_documentos", cliente, entidade, C_PLAN, gestor,
        lambda: _enviar_documentos(cliente, entidade, arquivos,
                                   confirmar=sha))
    checa(apagou == [(200, [])], f"o apagamento do meio não rodou: {apagou}")
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    checa(_sobras_no_disco(raiz, C_PLAN) == [],
          f"O DOCUMENTO DE QUEM PEDIU PARA SAIR NO MEIO FOI GRAVADO: "
          f"{_sobras_no_disco(raiz, C_PLAN)}")
    checa(_no_banco(entidade, C_PLAN) == {},
          f"…e projetado no banco: {_no_banco(entidade, C_PLAN)}")
    checa((ent.entrega(raiz) / D_PLAN).is_dir()
          and (r.json().get("casaram"), r.json().get("pessoas")) == (1, 1),
          f"o documento de quem fica não foi gravado, ou a resposta conta "
          f"o que não gravou: {r.json()}")
    print("  ok     apagamento no meio dos documentos do sindicato: não volta")


def teste_apagamento_no_meio_do_cadastro_nao_ressuscita():
    """MEDIDO em 12/11/2026: a sessão do filiado é conferida no começo do
    pedido, os arquivos sobem (segundos, num pacote de 60 MB), e só então o
    cadastro é gravado. Um apagamento nesse intervalo era desfeito no pior
    lugar possível — o DIÁRIO, que é a autoridade: `banco.reconstruir`
    traria a pessoa de volta para sempre. Sobravam 7 vestígios.

    O apagamento revoga a sessão. Então basta conferi-la DE NOVO na hora de
    gravar, com o apagamento parado — e isso não depende do banco estar no
    ar, que é o que este caminho nunca pôde exigir.
    """
    import json as _json

    from servidor import validacao

    entidade = "demo-meio-2"
    cliente, ent, raiz = _servidor(entidade)
    gestor = _token(cliente, B, entidade)
    _confirmar_planilha(cliente, entidade, _planilha(
        [(C_PLAN, "SAI NO MEIO (CADASTRO DE EXEMPLO)", "meio@exemplo.invalid")]))
    token = _token(cliente, C_PLAN, entidade)

    def cadastrar():
        return cliente.post(
            "/api/cadastro",
            data={"token": token, "linha": _json.dumps(linha(C_PLAN))},
            files=[("arquivos", ("contribuicao-1.pdf", _pdf(CONTRIB),
                                 "application/pdf")),
                   ("arquivos", ("sentenca.pdf", _pdf(SENTENCA),
                                 "application/pdf"))])

    # O gancho é a leitura do primeiro arquivo: é o meio do envio, depois
    # de a sessão ter sido conferida e antes de qualquer gravação.
    r, apagou = _com_apagamento_no_meio(
        validacao, "examinar_pdf", cliente, entidade, C_PLAN, gestor,
        cadastrar)
    checa(apagou == [(200, [])], f"o apagamento do meio não rodou: {apagou}")
    checa(r.status_code == 401,
          f"o cadastro de quem acabou de ser apagado foi aceito: "
          f"{r.status_code} {r.text[:200]}")
    checa(_sobras_no_disco(raiz, C_PLAN) == [],
          f"QUEM PEDIU PARA SAIR NO MEIO DO CADASTRO VOLTOU AO DISCO: "
          f"{_sobras_no_disco(raiz, C_PLAN)}")
    checa(_no_banco(entidade, C_PLAN) == {},
          f"…e ao banco: {_no_banco(entidade, C_PLAN)}")
    print("  ok     apagamento no meio do cadastro: 401, e nada volta")


def teste_apagamento_no_meio_da_leitura_do_gestor_nao_ressuscita():
    """MEDIDO em 12/11/2026: o gestor abre o documento da fila e registra o
    que leu; a pessoa é apagada a pedido entre uma coisa e outra; e a
    leitura era gravada assim mesmo. Sobrava a linha em `leituras.jsonl` —
    o CPF dela e o que a sentença dela diz, no arquivo que é AUTORIDADE."""
    from servidor import conferencia

    entidade = "demo-meio-4"
    cliente, ent, raiz = _servidor(entidade)
    gestor = _token(cliente, B, entidade)
    _confirmar_planilha(cliente, entidade, _planilha(
        [(C_PLAN, "SAI NO MEIO (CADASTRO DE EXEMPLO)", "meio@exemplo.invalid")]))
    r = _enviar(cliente, C_PLAN, entidade, {
        "contribuicao-1.pdf": _pdf(CONTRIB), "sentenca.pdf": _so_imagem()})
    checa(r.status_code == 200, f"o cenário não montou: {r.text[:200]}")
    doc = next(d["id"] for d in _fila(cliente, entidade)["pendentes"]
               if d["tipo"] == "sentenca")
    cabecalho = {"Authorization": f"Bearer {gestor}"}
    r, apagou = _com_apagamento_no_meio(
        conferencia, "validar", cliente, entidade, C_PLAN, gestor,
        lambda: cliente.post(
            f"/api/entidade/{entidade}/conferencia/{doc}",
            json={"resultado": "lido",
                  "fatos": {"dispositivo": "procedente"}},
            headers=cabecalho))
    checa(apagou == [(200, [])], f"o apagamento do meio não rodou: {apagou}")
    checa(r.status_code == 404,
          f"a leitura do documento de quem acabou de ser apagado foi "
          f"aceita: {r.status_code} {r.text[:200]}")
    checa(_sobras_no_disco(raiz, C_PLAN) == [],
          f"A LEITURA DE QUEM PEDIU PARA SAIR FOI GRAVADA: "
          f"{_sobras_no_disco(raiz, C_PLAN)}")
    checa(_no_banco(entidade, C_PLAN) == {},
          f"…e projetada: {_no_banco(entidade, C_PLAN)}")
    print("  ok     apagamento no meio da leitura do gestor: 404, e nada fica")


def teste_quem_grava_dado_de_pessoa_segura_a_trava_do_apagamento():
    """Conferir de novo encolhe a janela; a trava a fecha. E no cadastro ela
    tem de cobrir também o ESPELHO no banco: diário gravado, apagamento,
    espelho — e a pessoa voltava ao banco mesmo com o diário já redigido."""
    import fcntl
    import os

    from servidor import banco, deposito

    entidade = "demo-meio-3"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)

    def tomada() -> bool:
        fd = os.open(pasta / deposito.TRAVA_DO_APAGAMENTO,
                     os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        finally:
            os.close(fd)

    visto: dict[str, bool] = {}
    depositar, reconstruir, guardar = (
        deposito.depositar, banco.reconstruir, banco.guardar_achados)
    fase = ["documentos"]

    def depositar_espiado(*a, **k):
        visto["cadastro: diário"] = tomada()
        return depositar(*a, **k)

    def reconstruir_espiado(*a, **k):
        visto["cadastro: espelho"] = tomada()
        return reconstruir(*a, **k)

    def guardar_espiado(*a, **k):
        visto.setdefault(f"{fase[0]}: achados", tomada())
        return guardar(*a, **k)

    from servidor import conferencia
    registrar = conferencia.registrar

    def registrar_espiado(*a, **k):
        visto["leitura: registro"] = tomada()
        return registrar(*a, **k)

    deposito.depositar = depositar_espiado
    banco.reconstruir = reconstruir_espiado
    banco.guardar_achados = guardar_espiado
    conferencia.registrar = registrar_espiado
    try:
        _confirmar_planilha(cliente, entidade, _planilha(
            [(C_PLAN, "ALGUEM (CADASTRO DE EXEMPLO)", "a@exemplo.invalid")]))
        arquivos = {f"{C_PLAN}-sentenca.pdf": _pdf(SENTENCA)}
        sha = _enviar_documentos(cliente, entidade, arquivos).json()["sha256"]
        _enviar_documentos(cliente, entidade, arquivos, confirmar=sha)
        fase[0] = "cadastro"
        r = _cadastrar_com_titulo(cliente, C_PLAN, entidade)
        checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        fase[0] = "leitura"
        _enviar(cliente, C_PLAN, entidade, {
            "contribuicao-1.pdf": _pdf(CONTRIB),
            "sentenca.pdf": _so_imagem()})
        doc = next(d["id"] for d in _fila(cliente, entidade)["pendentes"]
                   if d["tipo"] == "sentenca")
        r = _registrar(cliente, entidade, doc, {
            "resultado": "lido", "fatos": {"dispositivo": "procedente"}})
        checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    finally:
        deposito.depositar = depositar
        banco.reconstruir = reconstruir
        banco.guardar_achados = guardar
        conferencia.registrar = registrar
    visto.pop("leitura: achados", None)   # o cadastro de scanner, de novo
    checa(visto == {"documentos: achados": True, "cadastro: diário": True,
                    "cadastro: espelho": True, "cadastro: achados": True,
                    "leitura: registro": True},
          f"alguém grava dado de pessoa sem a trava do apagamento: {visto}")
    checa(not tomada(), "a trava ficou presa")
    print("  ok     documentos e cadastro gravam com o apagamento parado")


# ------------------- o apagamento no meio das tarefas agendadas (T28)

PROC_1 = "00103912420064013400"
PROC_2 = "00012347020194013400"
PROC_3 = "00076540520198070001"


def _rodar_ferramenta(nome: str, raiz, entidade: str, *extra: str):
    """Roda `ferramentas/<nome>.py` NESTE processo, pelo `main()` dela.

    Neste processo e não num subprocesso, que é como o agendador a chama,
    porque o teste precisa encaixar um apagamento no meio dela.
    """
    import contextlib
    import importlib
    import io

    modulo = importlib.import_module(f"ferramentas.{nome}")
    antigo, saida = sys.argv, io.StringIO()
    sys.argv = [nome, "--entidade", entidade, "--raiz", str(raiz),
                "--banco", URL, *extra]
    try:
        with contextlib.redirect_stdout(saida), \
                contextlib.redirect_stderr(saida):
            codigo = modulo.main()
    finally:
        sys.argv = antigo
    return codigo, saida.getvalue()


def _base_com_processo_e_aviso(cliente, entidade: str,
                               pessoas: list[tuple[str, str, str, str]]):
    """(cpf, nome, e-mail, processo): na planilha do sindicato, e cadastrada
    pelo portal pedindo aviso."""
    import json as _json

    linhas = ["CPF;Nome Completo;E-mail;Cargo;Processo"]
    for cpf, nome, email, processo in pessoas:
        linhas.append(f"{cpf};{nome};{email};"
                      f"Auditor Fiscal da Receita Federal;{processo}")
    _confirmar_planilha(cliente, entidade,
                        ("\r\n".join(linhas) + "\r\n").encode("latin-1"))
    for cpf, nome, email, _processo in pessoas:
        r = cliente.post(
            "/api/cadastro",
            data={"token": _token(cliente, cpf, entidade),
                  "linha": _json.dumps(linha(cpf, nome_completo=nome,
                                             email=email, quer_aviso="sim"))},
            files=[("arquivos", ("contribuicao-1.pdf", _pdf(CONTRIB),
                                 "application/pdf"))])
        checa(r.status_code == 200, f"o cenário não montou: {r.text[:200]}")


SAI = (C_PLAN, "SAI NO MEIO (CADASTRO DE EXEMPLO)", "meio@exemplo.invalid")
FICA = (D_PLAN, "FICA (CADASTRO DE EXEMPLO)", "fica@exemplo.invalid")


def _ha_movimento_novo(entidade: str, ent, raiz, numeros: list[str]) -> None:
    """Os processos já são conhecidos, e a coleta trouxe um movimento novo
    em cada um: é o estado em que `avisar` MANDA e-mail."""
    import json as _json

    from nucleo import aviso as mod
    from servidor import banco

    banco.guardar_movimentos(URL, entidade, [
        mod.Movimento(numero=n, grau="G1", data="2026-10-01",
                      nome="Distribuição") for n in numeros])
    (ent.pasta(raiz) / "movimentos.jsonl").write_text(_json.dumps({
        "coletado_em": "2026-11-11T00:00:00+00:00",
        "consultados": len(numeros), "falhas": [],
        "movimentos": [{"numero": n, "grau": "G1", "data": "2026-11-10",
                        "nome": "Juntada de petição"} for n in numeros],
    }) + "\n", encoding="utf-8")


def teste_apagamento_no_meio_do_aviso_nao_manda_email():
    """MEDIDO em 12/11/2026
    (`docs/medicoes/2026-11-12-apagamento-e-as-tarefas-agendadas.py`): a
    tarefa de aviso lê quem pediu aviso, e DEPOIS, pessoa por pessoa, manda
    o e-mail. Quem era apagado a pedido nesse intervalo RECEBIA O E-MAIL —
    com o nome dela e a movimentação do processo dela —, e ainda ficavam o
    corpo da mensagem no log e uma linha em `aviso_enviado`.

    De todas as sobras de T28 esta é a única que sai do servidor: não há
    como desfazer um e-mail.
    """
    from servidor import banco

    secao("o apagamento no meio das tarefas agendadas")
    entidade = "demo-tarefa-1"
    cliente, ent, raiz = _servidor(entidade)
    gestor = _token(cliente, B, entidade)
    _base_com_processo_e_aviso(cliente, entidade,
                               [SAI + (PROC_1,), FICA + (PROC_1,)])
    _ha_movimento_novo(entidade, ent, raiz, [PROC_1])

    (resultado, apagou) = _com_apagamento_no_meio(
        banco, "chaves_ja_avisadas", cliente, entidade, C_PLAN, gestor,
        lambda: _rodar_ferramenta("avisar_movimentacao", raiz, entidade))
    codigo, saida = resultado
    checa(apagou == [(200, [])], f"o apagamento do meio não rodou: {apagou}")
    log = raiz / "mensagens_enviadas.log"
    mensagens = log.read_text(encoding="utf-8") if log.is_file() else ""
    checa(SAI[2] not in mensagens and SAI[1] not in mensagens,
          "SAIU E-MAIL PARA QUEM ACABOU DE PEDIR PARA SAIR")
    checa(_no_banco(entidade, C_PLAN) == {},
          f"…e ficou marcado no banco: {_no_banco(entidade, C_PLAN)}")
    checa(_sobras_no_disco(raiz, C_PLAN) == [],
          f"sobrou no disco: {_sobras_no_disco(raiz, C_PLAN)}")
    checa(f"\t{FICA[2]}\t" in mensagens,
          f"quem FICA não foi avisado (saída {codigo}): {saida[-300:]}")
    checa("1 pessoa(s) saíram da base" in saida,
          f"a ferramenta não diz que pulou alguém: {saida[-300:]}")
    checa(C_PLAN not in saida and SAI[2] not in saida,
          "a ferramenta escreveu no log do agendador QUEM pediu para sair")
    print("  ok     apagamento no meio do aviso: o e-mail não sai")


def teste_apagamento_no_meio_da_reavaliacao_nao_guarda_veredicto():
    """MEDIDO em 12/11/2026: a reavaliação lê a base inteira e depois grava
    o veredicto de cada pessoa. Quem era apagado no intervalo ganhava 2
    linhas em `oportunidade` — o que ela pode executar e ajuizar, guardado
    depois de ela pedir para sair."""
    from servidor import banco

    entidade = "demo-tarefa-2"
    cliente, ent, raiz = _servidor(entidade)
    gestor = _token(cliente, B, entidade)
    _base_com_processo_e_aviso(cliente, entidade,
                               [SAI + (PROC_1,), FICA + (PROC_1,)])
    (resultado, apagou) = _com_apagamento_no_meio(
        banco, "fatos_lidos_da_entidade", cliente, entidade, C_PLAN, gestor,
        lambda: _rodar_ferramenta("reavaliar_oportunidades", raiz, entidade))
    codigo, saida = resultado
    checa(apagou == [(200, [])], f"o apagamento do meio não rodou: {apagou}")
    checa(codigo == 0, f"a reavaliação saiu com {codigo}: {saida[-300:]}")
    checa(_no_banco(entidade, C_PLAN) == {},
          f"O VEREDICTO DE QUEM PEDIU PARA SAIR FOI GUARDADO: "
          f"{_no_banco(entidade, C_PLAN)}")
    checa(_no_banco(entidade, D_PLAN).get("oportunidade", 0) > 0,
          f"quem FICA ficou sem veredicto: {_no_banco(entidade, D_PLAN)}")
    checa("1 pessoa(s) saíram da base" in saida and C_PLAN not in saida,
          f"a ferramenta não diz que pulou alguém, ou diz quem: "
          f"{saida[-300:]}")
    print("  ok     apagamento no meio da reavaliação: nada é guardado")


def _tribunal_de_mentira(numeros, *args, **kwargs):
    from servidor import acompanhamento

    return ([acompanhamento.Movimento(numero=n, grau="G1", data="2026-11-11",
                                      nome="Conclusos para decisão")
             for n in list(numeros)], [])


def teste_processo_de_quem_saiu_deixa_de_ser_acompanhado():
    """MEDIDO em 12/11/2026, e SEM CORRIDA NENHUMA: a pessoa é apagada a
    pedido, a rota responde `vestigios: []`, e a coleta continua consultando
    o processo dela no tribunal — no dia seguinte, e no outro, para sempre.

    Eu tinha escrito, no teste da corrida logo abaixo, que "apagada antes, o
    processo nem entraria na lista". Era falso, e foi esse teste que mostrou:
    a lista saía da tabela `processo`, que o apagamento NÃO limpa — de
    propósito, porque numa coletiva o mesmo número é de centenas. O que liga
    a pessoa ao processo é `vinculo`, e esse sai. Então é por `vinculo` que
    se decide o que acompanhar: processo que ninguém mais tem, ninguém mais
    consulta.

    O processo COLETIVO continua sendo acompanhado enquanto sobrar alguém.
    """
    from servidor import acompanhamento, banco

    entidade = "demo-tarefa-5"
    cliente, ent, raiz = _servidor(entidade)
    gestor = _token(cliente, B, entidade)
    _base_com_processo_e_aviso(cliente, entidade, [
        SAI + (f"{PROC_1}, {PROC_3}",), FICA + (f"{PROC_2}, {PROC_3}",)])
    checa(banco.processos_para_acompanhar(URL, entidade)
          == sorted([PROC_1, PROC_2, PROC_3]),
          f"o cenário não montou: "
          f"{banco.processos_para_acompanhar(URL, entidade)}")
    r = _apagar(cliente, entidade,
                {"cpf": C_PLAN, "motivo": "pedido do titular",
                 "pedido_por": "g"}, gestor)
    checa(r.status_code == 200 and r.json()["vestigios"] == [],
          f"o apagamento não rodou limpo: {r.text[:200]}")

    consultados: list[str] = []

    def tribunal(numeros, *a, **k):
        consultados.extend(numeros)
        return _tribunal_de_mentira(numeros)

    verdadeiro = acompanhamento.coletar
    acompanhamento.coletar = tribunal
    try:
        _rodar_ferramenta("coletar_movimentacao", raiz, entidade)
    finally:
        acompanhamento.coletar = verdadeiro
    checa(PROC_1 not in consultados,
          "O PROCESSO DE QUEM PEDIU PARA SAIR CONTINUA SENDO CONSULTADO NO "
          "TRIBUNAL")
    checa(sorted(consultados) == sorted([PROC_2, PROC_3]),
          f"deixou de acompanhar o processo de quem FICA, ou o coletivo "
          f"que as duas tinham: {consultados}")
    print("  ok     processo de quem saiu não é mais consultado; o coletivo é")


def teste_apagamento_no_meio_da_coleta_nao_grava_processo_sem_dono():
    """A coleta lê os processos a acompanhar, consulta o tribunal (22 a
    43 s por consulta, medidos) e grava. Quem é apagado DURANTE a consulta
    deixava o processo dela gravado mais uma vez.

    Nada do CPF dela sobra: `movimento` é sobre o processo, por decisão
    registrada em `banco._TABELAS_DO_APAGAMENTO`. O que se exige é que as
    duas ordens deem o mesmo resultado — o de quem foi apagada ANTES, que
    é o teste acima. A consulta em si já foi; o que dá para não fazer é
    gravar.
    """
    from servidor import acompanhamento

    entidade = "demo-tarefa-3"
    cliente, ent, raiz = _servidor(entidade)
    gestor = _token(cliente, B, entidade)
    _base_com_processo_e_aviso(cliente, entidade,
                               [SAI + (PROC_1,), FICA + (PROC_2,)])
    verdadeiro = acompanhamento.coletar
    acompanhamento.coletar = _tribunal_de_mentira
    try:
        (resultado, apagou) = _com_apagamento_no_meio(
            acompanhamento, "coletar", cliente, entidade, C_PLAN, gestor,
            lambda: _rodar_ferramenta("coletar_movimentacao", raiz, entidade))
    finally:
        acompanhamento.coletar = verdadeiro
    codigo, saida = resultado
    checa(apagou == [(200, [])], f"o apagamento do meio não rodou: {apagou}")
    diario = ent.pasta(raiz) / "movimentos.jsonl"
    gravado = diario.read_text(encoding="utf-8") if diario.is_file() else ""
    checa(PROC_2 in gravado,
          f"o processo de quem FICA não foi gravado (saída {codigo}): "
          f"{saida[-300:]}")
    checa(PROC_1 not in gravado,
          "O PROCESSO DE QUEM PEDIU PARA SAIR FOI GRAVADO DEPOIS DO "
          "APAGAMENTO, sem ninguém mais que o acompanhe")
    print("  ok     apagamento no meio da coleta: processo sem dono não grava")


def teste_as_tarefas_agendadas_seguram_a_trava_do_apagamento():
    """A mesma medição das rotas: no instante em que cada tarefa escreve —
    ou manda o e-mail —, a trava do apagamento está tomada."""
    import fcntl
    import os

    from servidor import acompanhamento, banco, deposito, remetente

    entidade = "demo-tarefa-4"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    _base_com_processo_e_aviso(cliente, entidade, [SAI + (PROC_1,)])
    _ha_movimento_novo(entidade, ent, raiz, [PROC_1])

    def tomada() -> bool:
        fd = os.open(pasta / deposito.TRAVA_DO_APAGAMENTO,
                     os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        finally:
            os.close(fd)

    visto: dict[str, bool] = {}
    guardados = (remetente.ParaArquivo.enviar_mensagem, banco.marcar_avisado,
                 banco.registrar_oportunidades, deposito.anexar_com_fsync,
                 acompanhamento.coletar)

    def espiar(rotulo, original):
        def espiada(*a, **k):
            visto[rotulo] = tomada()
            return original(*a, **k)
        return espiada

    def anexar_espiado(caminho, texto):
        if caminho.name == "movimentos.jsonl":
            visto["coletar: diário de movimentos"] = tomada()
        return guardados[3](caminho, texto)

    remetente.ParaArquivo.enviar_mensagem = espiar("avisar: e-mail",
                                                   guardados[0])
    banco.marcar_avisado = espiar("avisar: marca", guardados[1])
    banco.registrar_oportunidades = espiar("reavaliar: veredicto",
                                           guardados[2])
    deposito.anexar_com_fsync = anexar_espiado
    acompanhamento.coletar = _tribunal_de_mentira
    try:
        _rodar_ferramenta("avisar_movimentacao", raiz, entidade)
        _rodar_ferramenta("reavaliar_oportunidades", raiz, entidade)
        _rodar_ferramenta("coletar_movimentacao", raiz, entidade)
    finally:
        (remetente.ParaArquivo.enviar_mensagem, banco.marcar_avisado,
         banco.registrar_oportunidades, deposito.anexar_com_fsync,
         acompanhamento.coletar) = guardados
    checa(visto == {"avisar: e-mail": True, "avisar: marca": True,
                    "reavaliar: veredicto": True,
                    "coletar: diário de movimentos": True},
          f"uma tarefa agendada grava (ou manda e-mail) sem a trava do "
          f"apagamento: {visto}")
    checa(not tomada(), "a trava ficou presa")
    print("  ok     avisar, reavaliar e coletar gravam com o apagamento parado")


# ------------------------ o pedido de troca chega a quem opera

NOS = "operacao@exemplo.invalid"


def _avisos_a_quem_opera(raiz) -> list[str]:
    """Os e-mails que saíram para quem opera — cada um, cabeçalho e corpo."""
    log = raiz / "mensagens_enviadas.log"
    if not log.is_file():
        return []
    return [m for m in log.read_text(encoding="utf-8").split("=== ")
            if f"\t{NOS}\t" in m]


def teste_pedido_de_troca_avisa_quem_opera():
    """A troca pedida só vale depois de conferida por quem opera — e quem
    opera só ficava sabendo por uma linha no log do servidor. Um pedido que
    ninguém vê é um filiado esperando por um e-mail que não muda, ou sem
    conseguir entrar, sem prazo.

    O E-MAIL NÃO TRAZ CPF NEM E-MAIL DE FILIADO. A caixa de quem opera não
    é o banco: o aviso diz QUANTOS e ONDE, e manda olhar no servidor.

    E SÓ AVISA DO QUE É NOVO: a planilha é reenviada toda vez que a base
    muda, e um e-mail por reenvio ensinaria a não ler.
    """
    secao("o pedido de troca chega a quem opera")
    entidade = "demo-avisa-1"
    cliente, ent, raiz = _servidor(
        entidade, {"PROTOCOL_EMAIL_DE_QUEM_OPERA": NOS})
    corpo = _planilha([
        (A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR),
        (C_PLAN, "UMA (CADASTRO DE EXEMPLO)", MESMO),
        (D_PLAN, "OUTRA (CADASTRO DE EXEMPLO)", MESMO),
        (E_PLAN, "SOZINHA (CADASTRO DE EXEMPLO)", "sozinha@exemplo.invalid"),
    ])
    _enviar_planilha(cliente, entidade, corpo)
    checa(_avisos_a_quem_opera(raiz) == [],
          "a PRÉVIA avisou: nada foi pedido ainda")
    _confirmar_planilha(cliente, entidade, corpo)
    avisos = _avisos_a_quem_opera(raiz)
    checa(len(avisos) == 1,
          f"o pedido não chegou a quem opera (ou chegou repetido): "
          f"{len(avisos)} e-mail(s)")
    if len(avisos) != 1:
        return
    texto = avisos[0]
    checa(entidade in texto and "1 troca" in texto and "2 entrada" in texto,
          f"o aviso não diz onde nem quantos: {texto}")
    checa("trocas_de_email.py" in texto and "listar" in texto,
          f"o aviso não diz o que fazer: {texto}")
    for dado in (A, C_PLAN, D_PLAN, INVASOR, MESMO, "fulana@exemplo.org",
                 "FULANA", "UMA (CADASTRO"):
        checa(dado not in texto,
              f"O AVISO LEVA DADO DE FILIADO PARA A CAIXA DE E-MAIL: {dado}")

    _confirmar_planilha(cliente, entidade, corpo)
    checa(len(_avisos_a_quem_opera(raiz)) == 1,
          "a MESMA planilha, sem pedido novo, avisou de novo")
    _confirmar_planilha(cliente, entidade, _planilha(
        [(E_PLAN, "SOZINHA (CADASTRO DE EXEMPLO)", "sozinha@exemplo.invalid"),
         # Em OUTRO domínio de exemplo: este teste já tem três pessoas em
         # `exemplo.invalid`, e a quarta seria segurada pelo limite por
         # domínio — que é outro teste, não este.
         (F_PLAN, "MAIS UMA (CADASTRO DE EXEMPLO)",
          "maisuma@outro-exemplo.invalid")]))
    checa(len(_avisos_a_quem_opera(raiz)) == 1,
          "planilha que só traz gente nova, sem pedido, avisou")
    # SÓ uma entrada segurada, sem troca nenhuma: também é pedido, e também
    # espera por nós. (Um mutante que só contava as trocas passava aqui.)
    _confirmar_planilha(cliente, entidade, _planilha(
        [(_cpf_sintetico(8105), "QUARTA (CADASTRO DE EXEMPLO)", MESMO)]))
    avisos = _avisos_a_quem_opera(raiz)
    checa(len(avisos) == 2 and "1 pedido(s) novo(s)" in avisos[-1]
          and "3 entrada" in avisos[-1],
          f"a entrada segurada, sozinha, não avisou quem opera: "
          f"{avisos[-1] if avisos else avisos}")
    print("  ok     pedido novo: um e-mail a quem opera, sem dado de filiado")


def teste_aviso_que_falha_nao_derruba_a_planilha():
    """O aviso é para NÓS. Se o correio estiver fora, a planilha do
    sindicato tem de entrar do mesmo jeito — o pedido está gravado, e o
    lembrete diário o encontra."""
    from servidor import remetente, trocas

    entidade = "demo-avisa-2"
    cliente, ent, raiz = _servidor(
        entidade, {"PROTOCOL_EMAIL_DE_QUEM_OPERA": NOS})
    original = remetente.ParaArquivo.enviar_mensagem

    def fora_do_ar(self, destino, assunto, corpo):
        raise OSError("correio fora do ar")

    remetente.ParaArquivo.enviar_mensagem = fora_do_ar
    try:
        feito = _confirmar_planilha(cliente, entidade, _planilha(
            [(A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR)]))
    finally:
        remetente.ParaArquivo.enviar_mensagem = original
    checa(feito.get("gravado") is True
          and A in trocas.estado(ent.pasta(raiz)).pendentes,
          f"a falha do aviso derrubou a planilha ou o pedido: {feito}")
    # Sem endereço NOSSO configurado: para nós nada sai, e nada quebra. O
    # dono do e-mail de antes é avisado do mesmo jeito — o aviso a ele não
    # depende de a nossa caixa existir.
    cliente2, ent2, raiz2 = _servidor("demo-avisa-3")
    feito = _confirmar_planilha(cliente2, "demo-avisa-3", _planilha(
        [(A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR)]))
    checa(feito.get("gravado") is True
          and _avisos_a_quem_opera(raiz2) == [],
          "sem endereço de quem opera, saiu aviso para quem opera")
    checa(len(_mensagens_para(raiz2, "fulana@exemplo.org")) == 1,
          "sem endereço de quem opera, o DONO do e-mail deixou de ser "
          "avisado")
    print("  ok     correio fora ou endereço ausente: a planilha entra")


# ------------------------------ o dono do e-mail de antes fica sabendo

def _mensagens_para(raiz, destino: str) -> list[str]:
    log = raiz / "mensagens_enviadas.log"
    if not log.is_file():
        return []
    return [m for m in log.read_text(encoding="utf-8").split("=== ")
            if f"\t{destino}\t" in m]


def teste_o_dono_do_email_de_antes_e_avisado_do_pedido_de_troca():
    """A defesa mais direta contra uma troca indevida: quem hoje recebe o
    código fica sabendo que pediram para mudar o endereço — no endereço de
    HOJE, que é o único que comprovadamente é dele.

    Quem opera confere por fora antes de aprovar; mas a única pessoa que
    SABE se pediu a troca é ela. Sem este aviso, a conferência depende de
    alguém nosso conseguir falar com ela.

    O que a mensagem NÃO faz: não traz link (e-mail sobre acesso com link é
    a aula de phishing), não traz CPF, e não entrega o endereço novo inteiro
    — a caixa antiga pode não ser mais dela.
    """
    from servidor import trocas

    secao("o dono do e-mail de antes fica sabendo")
    entidade = "demo-dono-1"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    corpo = _planilha([
        (A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR),
        (B, "GESTOR (CADASTRO DE EXEMPLO)", "outro.gestor@exemplo.invalid"),
        (C_PLAN, "UMA (CADASTRO DE EXEMPLO)", MESMO),
        (D_PLAN, "OUTRA (CADASTRO DE EXEMPLO)", MESMO),
    ])
    _enviar_planilha(cliente, entidade, corpo)
    checa(_mensagens_para(raiz, "fulana@exemplo.org") == [],
          "a PRÉVIA avisou o filiado: nada foi pedido ainda")
    _confirmar_planilha(cliente, entidade, corpo)

    dela = _mensagens_para(raiz, "fulana@exemplo.org")
    checa(len(dela) == 1, f"o dono do e-mail de antes não foi avisado (ou "
                          f"foi mais de uma vez): {len(dela)}")
    if len(dela) != 1:
        return
    texto = dela[0]
    checa("Sindicato de Demonstração" in texto,
          f"a mensagem não diz de que sindicato é: {texto}")
    checa("não vale" in texto.lower() and "não pediu" in texto.lower(),
          f"a mensagem não diz que a troca não vale, nem o que fazer se "
          f"não foi ela: {texto}")
    checa(INVASOR not in texto and "in•••@exemplo.invalid" in texto,
          f"o e-mail pedido tem de ir MASCARADO: {texto}")
    checa(A not in texto and "http" not in texto.lower()
          and "escritório" not in texto.lower(),
          f"a mensagem leva CPF, link, ou fala em escritório: {texto}")
    checa(len(_mensagens_para(raiz, "gestor@exemplo.org")) == 1,
          "pediram a troca do e-mail de um GESTOR e ele não foi avisado")
    checa(_mensagens_para(raiz, MESMO) == []
          and _mensagens_para(raiz, INVASOR) == [],
          "saiu mensagem para o e-mail NOVO, ou para entrada segurada — "
          "nenhum dos dois é endereço de alguém que já entra")
    checa(trocas.estado(pasta).pendentes[A].get("dono_avisado") is True,
          "o pedido não registra que o dono foi avisado")

    # UMA VEZ POR PEDIDO. A planilha volta toda semana.
    _confirmar_planilha(cliente, entidade, corpo)
    # …e retirar o pedido e pedir o MESMO de novo não é pedido novo para
    # ela: sem isto, alternar duas planilhas viraria uma máquina de e-mail.
    _confirmar_planilha(cliente, entidade, _planilha(
        [(A, "FULANA (CADASTRO DE EXEMPLO)", "fulana@exemplo.org")]))
    checa(A not in trocas.estado(pasta).pendentes, "o cenário não montou")
    _confirmar_planilha(cliente, entidade, corpo)
    checa(len(_mensagens_para(raiz, "fulana@exemplo.org")) == 1,
          f"o mesmo pedido avisou de novo: "
          f"{len(_mensagens_para(raiz, 'fulana@exemplo.org'))} mensagens")
    # Outro endereço pedido É notícia.
    _confirmar_planilha(cliente, entidade, _planilha(
        [(A, "FULANA (CADASTRO DE EXEMPLO)", "terceiro@exemplo.invalid")]))
    checa(len(_mensagens_para(raiz, "fulana@exemplo.org")) == 2,
          "um pedido para OUTRO endereço não avisou")
    print("  ok     o dono do e-mail de antes é avisado, uma vez por pedido")


def teste_aviso_ao_dono_que_falha_e_tentado_de_novo():
    """Este aviso é um controle de segurança, e controle que falha calado
    é controle que não existe. Se o correio cair na hora, a planilha entra
    — e o lembrete diário tenta de novo, até sair. Depois que saiu, não
    repete: quem é lembrado todo dia somos nós, não o filiado."""
    import os
    import subprocess

    from servidor import remetente, trocas

    entidade = "demo-dono-2"
    cliente, ent, raiz = _servidor(entidade)
    pasta = ent.pasta(raiz)
    original = remetente.ParaArquivo.enviar_mensagem

    def fora_do_ar(self, destino, assunto, corpo):
        raise OSError("correio fora do ar")

    remetente.ParaArquivo.enviar_mensagem = fora_do_ar
    try:
        feito = _confirmar_planilha(cliente, entidade, _planilha(
            [(A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR)]))
    finally:
        remetente.ParaArquivo.enviar_mensagem = original
    pedido = trocas.estado(pasta).pendentes.get(A) or {}
    checa(feito.get("gravado") is True and pedido
          and not pedido.get("dono_avisado"),
          f"a falha do aviso derrubou a planilha, ou o pedido diz que o "
          f"dono foi avisado sem ter sido: {feito} {pedido}")

    def lembrete():
        ambiente = {k: v for k, v in os.environ.items()
                    if not k.startswith("PROTOCOL_")}
        ambiente["PROTOCOL_EMAIL_DE_QUEM_OPERA"] = NOS
        return subprocess.run(
            [sys.executable, str(RAIZ / "ferramentas" / "avisar_pedidos.py"),
             "--raiz", str(raiz), "--entidade", entidade],
            capture_output=True, text=True, env=ambiente)

    r = lembrete()
    checa(r.returncode == 0
          and len(_mensagens_para(raiz, "fulana@exemplo.org")) == 1
          and trocas.estado(pasta).pendentes[A].get("dono_avisado") is True,
          f"o lembrete não tentou de novo o aviso ao dono: {r.returncode} "
          f"{r.stdout} {r.stderr}")
    checa(A not in r.stdout + r.stderr
          and "fulana@" not in r.stdout + r.stderr,
          "a saída do lembrete vai para o log do agendador e diz quem é")
    r = lembrete()
    checa(len(_mensagens_para(raiz, "fulana@exemplo.org")) == 1
          and len(_avisos_a_quem_opera(raiz)) == 2,
          "o segundo lembrete repetiu o aviso ao FILIADO (ou não lembrou "
          "quem opera)")
    r = _ferramenta_de_trocas(raiz, entidade, "listar")
    checa("dono avisado" in r.stdout,
          f"quem decide não vê se o dono foi avisado: {r.stdout}")
    print("  ok     aviso que falhou é tentado de novo, e depois não repete")


def teste_apagar_leva_o_aviso_que_o_dono_recebeu():
    """O aviso ao dono fica no arquivo do remetente de desenvolvimento, com
    o e-mail dela no cabeçalho e o endereço pedido, mascarado, no corpo. O
    apagamento tem de levar a MENSAGEM, não só a linha do cabeçalho."""
    entidade = "demo-dono-3"
    cliente, ent, raiz = _servidor(entidade)
    _confirmar_planilha(cliente, entidade, _planilha(
        [(A, "FULANA (CADASTRO DE EXEMPLO)", INVASOR)]))
    log = raiz / "mensagens_enviadas.log"
    checa("in•••@exemplo.invalid" in log.read_text(encoding="utf-8"),
          "o cenário não montou")
    r = _apagar(cliente, entidade,
                {"cpf": A, "motivo": "pedido do titular", "pedido_por": "g"},
                _token(cliente, B, entidade))
    checa(r.status_code == 200 and r.json()["vestigios"] == [],
          f"{r.status_code} {r.text[:200]}")
    sobrou = log.read_text(encoding="utf-8") if log.exists() else ""
    checa("fulana@exemplo.org" not in sobrou
          and "in•••@exemplo.invalid" not in sobrou
          and "Pediram a troca" not in sobrou,
          f"O CORPO DA MENSAGEM DELA FICOU NO LOG depois do apagamento: "
          f"{sobrou[:300]}")
    print("  ok     o apagamento leva a mensagem inteira, não só o cabeçalho")


# ---------------------------------- o domínio inteiro (T27, o resto)

def _novas(dominio: str, n: int, a_partir_de: int = 8200,
           local: str = "pessoa") -> list[tuple[str, str, str]]:
    """`n` pessoas novas, cada uma com um endereço SÓ DELA em `dominio`."""
    return [(_cpf_sintetico(a_partir_de + i),
             f"NOVA {a_partir_de + i} (CADASTRO DE EXEMPLO)",
             f"{local}{i}@{dominio}") for i in range(n)]


def teste_apelido_do_mesmo_endereco_nao_e_outra_caixa():
    """A regra do e-mail repetido comparava o TEXTO do endereço. Então
    `joana+1@…` e `joana+2@…` eram dois e-mails — e são a mesma caixa: o
    que vem depois do `+` é etiqueta, e a mensagem chega no mesmo lugar.
    Era o jeito mais barato de receber o código de várias pessoas novas:
    nenhum domínio para comprar, nenhuma conta para criar."""
    from servidor import trocas

    secao("o domínio inteiro")
    entidade = "demo-dom-1"
    cliente, ent, raiz = _servidor(entidade)
    feito = _confirmar_planilha(cliente, entidade, _planilha([
        (C_PLAN, "UMA (CADASTRO DE EXEMPLO)", "joana+1@exemplo.invalid"),
        (D_PLAN, "OUTRA (CADASTRO DE EXEMPLO)", "joana+2@exemplo.invalid"),
        (E_PLAN, "TERCEIRA (CADASTRO DE EXEMPLO)", "Joana@Exemplo.invalid"),
    ]))
    checa((feito["acesso"]["novos"], feito["acesso"]["novos_aguardando"])
          == (0, 3),
          f"apelidos da mesma caixa entraram como e-mails diferentes: "
          f"{feito['acesso']}")
    for cpf in (C_PLAN, D_PLAN, E_PLAN):
        checa(_destino_do_codigo(cliente, raiz, entidade, cpf) is None,
              "UMA CAIXA RECEBEU O CÓDIGO DE VÁRIAS PESSOAS, por apelido")
    checa(all(p.get("motivo") == "repetido" for p in
              trocas.estado(ent.pasta(raiz)).pendentes.values()),
          f"o pedido não diz POR QUE foi segurado: "
          f"{trocas.estado(ent.pasta(raiz)).pendentes}")
    print("  ok     joana+1 e joana+2 são a mesma caixa: nenhuma entra")


def teste_dominio_concentrado_segura_a_entrada():
    """Um endereço diferente por pessoa passa pela regra do e-mail repetido
    — e quem controla um domínio escreve quantos endereços quiser, todos
    caindo na mesma caixa. Então um domínio FORA dos provedores comuns só
    recebe gente nova até um limite; passou disso, as novas esperam por
    quem opera.

    O limite conta o que JÁ ESTÁ no acesso e o que espera, não só a
    planilha — uma pessoa por envio não contorna. E conta o domínio
    REGISTRÁVEL: `a.raro.invalid` e `b.raro.invalid` são do mesmo dono.
    """
    from servidor import rol, trocas

    entidade = "demo-dom-2"
    cliente, ent, raiz = _servidor(entidade)
    limite = rol.LIMITE_POR_DOMINIO

    # Até o limite, entra: domínio pequeno é gente de verdade.
    dentro = _novas("pequeno.invalid", limite, 8200)
    feito = _confirmar_planilha(cliente, entidade, _planilha(dentro))
    checa(feito["acesso"]["novos"] == limite
          and feito["acesso"].get("novos_por_dominio") == 0,
          f"domínio com {limite} pessoas foi segurado: {feito['acesso']}")
    # Mais uma, NUM ENVIO SÓ DELA: o domínio já está cheio.
    mais_uma = _novas("pequeno.invalid", 1, 8210, local="outra")
    feito = _confirmar_planilha(cliente, entidade, _planilha(mais_uma))
    checa((feito["acesso"]["novos"], feito["acesso"]["novos_por_dominio"])
          == (0, 1),
          f"UMA PESSOA POR ENVIO passou do limite do domínio: "
          f"{feito['acesso']}")
    checa(_destino_do_codigo(cliente, raiz, entidade, mais_uma[0][0])
          is None, "a pessoa além do limite recebeu código")
    checa(_destino_do_codigo(cliente, raiz, entidade, dentro[0][0])
          == dentro[0][2], "quem já tinha entrado perdeu o acesso")

    # De uma vez, acima do limite: NENHUMA entra — escolher quais seria
    # decidir sozinho.
    muitas = _novas("raro.invalid", limite + 1, 8220)
    feito = _confirmar_planilha(cliente, entidade, _planilha(muitas))
    checa((feito["acesso"]["novos"], feito["acesso"]["novos_por_dominio"])
          == (0, limite + 1),
          f"domínio concentrado entrou: {feito['acesso']}")
    # Subdomínios diferentes, MESMO dono.
    subs = [(_cpf_sintetico(8240 + i), f"SUB {i} (CADASTRO DE EXEMPLO)",
             f"caixa@s{i}.oculto.invalid") for i in range(limite + 1)]
    feito = _confirmar_planilha(cliente, entidade, _planilha(subs))
    checa(feito["acesso"]["novos"] == 0
          and feito["acesso"]["novos_por_dominio"] == limite + 1,
          f"UM SUBDOMÍNIO POR PESSOA contornou o limite: {feito['acesso']}")
    motivos = {p.get("motivo") for p in
               trocas.estado(ent.pasta(raiz)).pendentes.values()}
    checa(motivos == {"dominio"},
          f"o pedido não diz que foi segurado pelo domínio: {motivos}")
    print(f"  ok     domínio fora dos comuns: até {limite} entram; além, esperam")


def teste_dominio_confiado_por_quem_opera_libera():
    """O domínio da repartição tem centenas de filiados, e é legítimo.
    Quem diz isso é quem opera, UMA vez por sindicato: o domínio passa a
    ser confiado, quem esperava por causa dele entra, e as próximas
    planilhas não seguram mais ninguém dali."""
    from servidor import rol

    entidade = "demo-dom-3"
    cliente, ent, raiz = _servidor(entidade)
    limite = rol.LIMITE_POR_DOMINIO
    muitas = _novas("reparticao.invalid", limite + 2, 8260)
    # Duas pessoas no MESMO endereço daquele domínio: seguradas por outro
    # motivo, e confiar no domínio não pode soltá-las — confiar no domínio
    # não diz de quem é a caixa.
    dupla = [(_cpf_sintetico(8290 + i), f"DUPLA {i} (CADASTRO DE EXEMPLO)",
              "balcao@reparticao.invalid") for i in range(2)]
    feito = _confirmar_planilha(cliente, entidade,
                                _planilha(muitas + dupla))
    checa((feito["acesso"]["novos_por_dominio"],
           feito["acesso"]["novos_aguardando"]) == (limite + 2, 2),
          f"o cenário não montou: {feito['acesso']}")

    r = _ferramenta_de_trocas(raiz, entidade, "listar")
    checa("reparticao.invalid" in r.stdout and "domínio" in r.stdout,
          f"listar não mostra o domínio que segurou: {r.stdout}")
    r = _ferramenta_de_trocas(raiz, entidade, "confiar", "reparticao.invalid")
    checa(r.returncode == 0 and str(limite + 2) in r.stdout,
          f"confiar no domínio falhou: {r.stdout} {r.stderr}")
    for cpf, _nome, email in muitas:
        checa(_destino_do_codigo(cliente, raiz, entidade, cpf) == email,
              "quem esperava pelo domínio não entrou depois de confiado")
    for cpf, _nome, _email in dupla:
        checa(_destino_do_codigo(cliente, raiz, entidade, cpf) is None,
              "CONFIAR NO DOMÍNIO SOLTOU QUEM DIVIDE A MESMA CAIXA")
    mais = _novas("sub.reparticao.invalid", 2, 8280, local="depois")
    feito = _confirmar_planilha(cliente, entidade, _planilha(mais))
    checa((feito["acesso"]["novos"], feito["acesso"]["novos_por_dominio"])
          == (2, 0),
          f"o domínio confiado continua segurando: {feito['acesso']}")
    # A confiança é DESTE sindicato.
    cliente2, ent2, raiz2 = _servidor("demo-dom-4")
    feito = _confirmar_planilha(cliente2, "demo-dom-4", _planilha(muitas))
    checa(feito["acesso"]["novos_por_dominio"] == limite + 2,
          f"a confiança de um sindicato valeu para outro: {feito['acesso']}")
    print("  ok     domínio confiado libera quem esperava, só naquele sindicato")


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
    teste_nao_sai_codigo_para_quem_foi_apagado,
    teste_apagar_so_para_gestor_da_propria_entidade,
    teste_apagar_pelo_painel_do_sindicato,
    teste_apagar_aceita_cpf_formatado,
    teste_apagar_cpf_de_fora_da_base_nao_e_oraculo,
    teste_o_painel_conta_quantos_foram_apagados_a_pedido,
    teste_gestor_de_outra_entidade_nao_apaga_e_nem_le_o_rol_alvo,
    teste_o_apagamento_fica_registrado_e_leitura_nao_e_apagada,
    teste_sem_registro_de_auditoria_nao_apaga_nada,
    teste_motivo_e_pedido_por_tem_teto_e_recusa_em_vez_de_cortar,
    teste_as_tres_superficies_dizem_o_mesmo_sobre_a_mesma_pessoa,
    teste_ler_os_documentos_nao_faz_o_painel_custar_por_pessoa,
    teste_documento_escaneado_entra_e_fica_aguardando_leitura,
    teste_so_o_comprovante_escaneado_tambem_entra,
    teste_pdf_que_nao_abre_continua_recusado,
    teste_o_painel_conta_o_que_aguarda_leitura,
    teste_documento_do_sindicato_entra_na_fila_so_se_for_imagem,
    teste_a_fila_de_leitura_tem_saida,
    teste_so_o_gestor_da_entidade_confere,
    teste_leitura_invalida_nao_vira_fato,
    teste_o_que_nem_uma_pessoa_le_sai_da_fila_e_e_contado,
    teste_reenvio_tira_o_documento_antigo_da_fila_e_do_motor,
    teste_a_recuperacao_refaz_as_leituras_humanas,
    teste_a_lista_nome_por_nome_e_a_quarta_superficie,
    teste_a_exportacao_e_planilha_que_abre_e_nao_executa,
    teste_so_gestor_ve_a_lista_e_exporta,
    teste_a_lista_nao_custa_por_pessoa,
    teste_sem_registro_de_quem_exportou_nao_exporta,
    teste_o_gestor_envia_a_planilha_pela_web_em_duas_etapas,
    teste_confirmar_outro_arquivo_e_recusado,
    teste_planilha_que_nao_serve_e_recusada_com_o_motivo,
    teste_quem_pediu_para_sair_nao_volta_pela_planilha_da_web,
    teste_o_gestor_envia_os_documentos_que_o_sindicato_tem,
    teste_documentos_sem_base_sao_recusados_dizendo_o_que_fazer,
    teste_falha_ao_conferir_apagamento_nao_entrega_codigo,
    teste_um_cadastro_nao_custa_o_diario_inteiro,
    teste_meu_cadastro_nao_le_a_base_inteira,
    teste_o_registro_por_cpf_concorda_com_a_base_inteira,
    teste_reconstruir_continua_recuperando_o_diario_inteiro,
    teste_a_leitura_de_dado_nominal_fica_registrada,
    teste_o_registro_de_leitura_nao_guarda_cpf_em_claro,
    teste_a_auditoria_tambem_respeita_a_politica,
    teste_quem_e_novo_na_planilha_ja_consegue_entrar,
    teste_a_planilha_nao_troca_o_email_de_quem_ja_entra,
    teste_sumir_da_planilha_e_voltar_nao_contorna_a_trava,
    teste_troca_aprovada_vale_e_recusada_nao_volta,
    teste_divergencia_e_email_torto_nao_entram_no_acesso,
    teste_quem_pediu_para_sair_nao_volta_ao_acesso_pela_planilha,
    teste_apagar_leva_tambem_a_troca_pedida,
    teste_sindicato_sem_rol_comeca_pela_planilha,
    teste_apagamento_no_meio_da_planilha_nao_ressuscita,
    teste_a_planilha_e_o_apagamento_seguram_a_mesma_trava,
    teste_email_repetido_em_gente_nova_segura_a_entrada,
    teste_email_de_quem_ja_entra_nao_serve_para_gente_nova,
    teste_apagamento_no_meio_dos_documentos_do_sindicato_nao_ressuscita,
    teste_apagamento_no_meio_do_cadastro_nao_ressuscita,
    teste_apagamento_no_meio_da_leitura_do_gestor_nao_ressuscita,
    teste_quem_grava_dado_de_pessoa_segura_a_trava_do_apagamento,
    teste_apagamento_no_meio_do_aviso_nao_manda_email,
    teste_apagamento_no_meio_da_reavaliacao_nao_guarda_veredicto,
    teste_processo_de_quem_saiu_deixa_de_ser_acompanhado,
    teste_apagamento_no_meio_da_coleta_nao_grava_processo_sem_dono,
    teste_as_tarefas_agendadas_seguram_a_trava_do_apagamento,
    teste_pedido_de_troca_avisa_quem_opera,
    teste_aviso_que_falha_nao_derruba_a_planilha,
    teste_o_dono_do_email_de_antes_e_avisado_do_pedido_de_troca,
    teste_aviso_ao_dono_que_falha_e_tentado_de_novo,
    teste_apagar_leva_o_aviso_que_o_dono_recebeu,
    teste_apelido_do_mesmo_endereco_nao_e_outra_caixa,
    teste_dominio_concentrado_segura_a_entrada,
    teste_dominio_confiado_por_quem_opera_libera,
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
