#!/usr/bin/env python3
"""
O isolamento entre entidades, provado no banco.

POR QUE RLS, SE O SERVIDOR JÁ FILTRA

Porque o erro mais provável num produto multi-entidade não é alguém burlar o
portão: é um `WHERE entidade = ...` esquecido numa consulta nova. O portão
protege a porta; o RLS protege contra a nossa própria distração, seis meses
depois, quando outra pessoa acrescentar uma tela.

RLS NÃO TESTADO É PIOR QUE RLS NENHUM, porque parece seguro. Então o primeiro
teste deste arquivo é o que tenta ler SEM declarar a entidade e exige não ler
nada — se ele passasse por acidente (tabela vazia, por exemplo), os seguintes
pegariam.

E `FORCE ROW LEVEL SECURITY`, não só `ENABLE`: sem o FORCE, o DONO da tabela
ignora a política. Como as migrações criam as tabelas com o mesmo papel que a
aplicação usaria num descuido, o ENABLE sozinho seria decoração.

SEM `PROTOCOL_DATABASE_URL`, esta suíte é PULADA — em voz alta. Suíte
silenciosamente não executada é o que faz alguém achar que está testado.
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


def preparar():
    from servidor import banco

    # recriar: o esquema mudou de forma, e CREATE TABLE IF NOT EXISTS
    # não altera tabela existente.
    banco.criar_esquema(URL, recriar=True)
    # Limpar DENTRO de cada sessão: com o RLS ligado, um DELETE só alcança a
    # entidade da sessão — que é exatamente o que se quer provar, e também o
    # que faz a limpeza precisar de uma passada por entidade.
    for entidade in ("demo-a", "demo-b"):
        with banco.sessao(URL, entidade) as cur:
            cur.execute("DELETE FROM pessoa")
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute(
            "INSERT INTO pessoa (entidade, cpf, nome) VALUES (%s,%s,%s)",
            ("demo-a", "11144477735", "FULANA DE TAL (CADASTRO DE EXEMPLO)"),
        )
        cur.execute(
            "INSERT INTO pessoa (entidade, cpf, nome) VALUES (%s,%s,%s)",
            ("demo-a", "52998224725", "BELTRANO DE TAL (CADASTRO DE EXEMPLO)"),
        )
    with banco.sessao(URL, "demo-b") as cur:
        cur.execute(
            "INSERT INTO pessoa (entidade, cpf, nome) VALUES (%s,%s,%s)",
            ("demo-b", "52601815906", "SICRANA DE TAL (CADASTRO DE EXEMPLO)"),
        )


def teste_sem_declarar_a_entidade_nao_le_nada():
    """O teste que prova que o RLS está LIGADO. Se ele falhar, nenhum outro
    deste arquivo significa coisa alguma."""
    secao("isolamento")
    from servidor import banco

    with banco.cru(URL) as cur:          # sem SET LOCAL app.entidade
        cur.execute("SELECT count(*) FROM pessoa")
        quantas = cur.fetchone()[0]
    checa(quantas == 0,
          f"leu {quantas} pessoa(s) sem declarar a entidade — o RLS não está "
          f"protegendo nada")
    print("  ok     sem app.entidade, zero linhas")


def teste_uma_entidade_nao_le_a_outra():
    from servidor import banco

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM pessoa")
        de_a = cur.fetchone()[0]
    with banco.sessao(URL, "demo-b") as cur:
        cur.execute("SELECT count(*) FROM pessoa")
        de_b = cur.fetchone()[0]
    checa(de_a == 2, f"demo-a deveria ver 2, viu {de_a}")
    checa(de_b == 1, f"demo-b deveria ver 1, viu {de_b}")
    print("  ok     cada entidade vê só a própria base")


def teste_consulta_sem_filtro_nao_vaza():
    """O erro real que isto protege: alguém escreve uma tela nova e esquece o
    WHERE. A consulta abaixo NÃO tem filtro nenhum."""
    from servidor import banco

    with banco.sessao(URL, "demo-b") as cur:
        cur.execute("SELECT cpf FROM pessoa")     # sem WHERE, de propósito
        cpfs = {linha[0] for linha in cur.fetchall()}
    checa(cpfs == {"52601815906"},
          f"consulta sem WHERE vazou: {cpfs}")
    print("  ok     consulta sem WHERE devolve só a entidade da sessão")


def teste_nao_da_para_escrever_na_entidade_alheia():
    """Isolamento de ESCRITA, não só de leitura. Sem `WITH CHECK`, demo-b
    poderia inserir linha marcada como demo-a — e aí o vazamento é para
    dentro."""
    from servidor import banco

    with banco.sessao(URL, "demo-b") as cur:
        try:
            cur.execute(
                "INSERT INTO pessoa (entidade, cpf, nome) VALUES (%s,%s,%s)",
                ("demo-a", "11144477700", "INVASOR (CADASTRO DE EXEMPLO)"),
            )
            checa(False, "demo-b escreveu uma linha marcada como demo-a")
        except Exception:
            pass
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM pessoa")
        checa(cur.fetchone()[0] == 2,
              "a linha do invasor entrou na base de demo-a")
    print("  ok     escrita também é isolada")


def teste_o_dono_da_tabela_tambem_obedece():
    """`ENABLE` sozinho não vale para o dono da tabela. Sem `FORCE`, a
    política seria decoração para quem rodou as migrações."""
    from servidor import banco

    with banco.cru(URL) as cur:
        cur.execute(
            "SELECT relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relname = 'pessoa'"
        )
        ligado, forcado = cur.fetchone()
    checa(ligado, "RLS não está habilitado na tabela pessoa")
    checa(forcado, "falta FORCE ROW LEVEL SECURITY — o dono da tabela ignora "
                   "a política")
    print("  ok     RLS habilitado E forçado")


# ------------------------------------------------------------ trava de região

def teste_entidade_real_fora_do_brasil_e_recusada():
    secao("trava de região")
    from fastapi.testclient import TestClient

    from servidor.app import criar_app
    from servidor.config import carregar

    import tempfile
    raiz = Path(tempfile.mkdtemp(prefix="regiao-"))
    from servidor import entidades as mod
    cad = mod.Cadastro(raiz)
    cad.criar("sindicato-real", "Sindicato Real")
    cad.criar("demo-teste", "Demonstração")

    cfg = carregar({
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_SEGREDO": "x" * 40,
        "PROTOCOL_REGIAO": "us-west-2",
        "PROTOCOL_SMTP_HOST": "smtp.exemplo.org",
        "PROTOCOL_SMTP_REMETENTE": "portal@exemplo.org",
    })
    cliente = TestClient(criar_app(cfg))
    r = cliente.get("/api/entidade/sindicato-real")
    checa(r.status_code == 503,
          f"atendeu entidade real fora do Brasil: {r.status_code}")
    checa("região" in r.text.lower() or "regiao" in r.text.lower(),
          f"a recusa não explica que é a região: {r.text[:200]}")
    print("  ok     entidade real fora do Brasil é recusada, com o motivo")


def teste_entidade_de_demonstracao_roda_em_qualquer_regiao():
    """A trava não pode fechar a demonstração: lá não há dado pessoal."""
    from fastapi.testclient import TestClient

    from servidor.app import criar_app
    from servidor.config import carregar

    import tempfile
    raiz = Path(tempfile.mkdtemp(prefix="regiao-"))
    from servidor import entidades as mod
    mod.Cadastro(raiz).criar("demo-teste", "Demonstração")

    cfg = carregar({
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_SEGREDO": "x" * 40,
        "PROTOCOL_REGIAO": "us-west-2",
        "PROTOCOL_SMTP_HOST": "smtp.exemplo.org",
        "PROTOCOL_SMTP_REMETENTE": "portal@exemplo.org",
    })
    r = TestClient(criar_app(cfg)).get("/api/entidade/demo-teste")
    checa(r.status_code == 200,
          f"a trava de região fechou a demonstração: {r.status_code}")
    print("  ok     a demonstração roda em qualquer região")


def teste_regiao_brasileira_libera():
    from fastapi.testclient import TestClient

    from servidor.app import criar_app
    from servidor.config import carregar

    import tempfile
    raiz = Path(tempfile.mkdtemp(prefix="regiao-"))
    from servidor import entidades as mod
    mod.Cadastro(raiz).criar("sindicato-real", "Sindicato Real")

    cfg = carregar({
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_SEGREDO": "x" * 40,
        "PROTOCOL_REGIAO": "sa-east-1",
        "PROTOCOL_SMTP_HOST": "smtp.exemplo.org",
        "PROTOCOL_SMTP_REMETENTE": "portal@exemplo.org",
    })
    r = TestClient(criar_app(cfg)).get("/api/entidade/sindicato-real")
    checa(r.status_code == 200,
          f"região brasileira foi recusada: {r.status_code} {r.text[:200]}")
    print("  ok     sa-east-1 atende entidade real")


# ------------------------------------------------- as três camadas (BANCO.md)

def teste_a_divergencia_sobrevive_no_banco():
    """A regra do produto, imposta pelo ESQUEMA e não pelo Python.

    Numa tabela larga, gravar o segundo valor apaga o primeiro e a
    divergência some junto. `pessoa_afirmacao` guarda TODA afirmação já
    feita, com a fonte — e é isso que permite ao sindicato homologar depois.
    """
    secao("as três camadas")
    from servidor import banco

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("DELETE FROM pessoa_afirmacao")
        cur.execute("DELETE FROM pessoa")
        cur.execute(
            "INSERT INTO recebimento (entidade, tipo, payload) "
            "VALUES (%s,%s,%s) RETURNING id",
            ("demo-a", "acervo", '{"origem":"planilha"}'),
        )
        rec = cur.fetchone()[0]
        for fonte, valor in (("acervo", "joao@sindicato.org"),
                             ("cadastro", "joao@pessoal.com")):
            cur.execute(
                "INSERT INTO pessoa_afirmacao "
                "(entidade, cpf, campo, valor, fonte, recebimento_id) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                ("demo-a", "52998224725", "email", valor, fonte, rec),
            )
        cur.execute(
            "INSERT INTO pessoa (entidade, cpf, email, tem_divergencia) "
            "VALUES (%s,%s,%s,%s)",
            ("demo-a", "52998224725", "joao@sindicato.org", True),
        )
        cur.execute(
            "SELECT fonte, valor FROM pessoa_afirmacao "
            "WHERE cpf = %s AND campo = 'email' ORDER BY fonte",
            ("52998224725",),
        )
        guardadas = dict(cur.fetchall())
        cur.execute("SELECT email, tem_divergencia FROM pessoa WHERE cpf = %s",
                    ("52998224725",))
        vigente, divergente = cur.fetchone()

    checa(len(guardadas) == 2,
          f"uma das afirmações foi perdida: {guardadas}")
    checa(vigente == "joao@sindicato.org",
          f"o valor vigente devia ser o do ACERVO, veio {vigente!r} — se o "
          f"filiado pudesse trocar o e-mail, o código de acesso viraria "
          f"enfeite")
    checa(divergente, "a divergência não foi marcada")
    print("  ok     as duas afirmações sobrevivem, e o rol vence até homologar")


def teste_oportunidade_guarda_a_versao_do_catalogo():
    """O que torna o veredicto auditável: quando o Tema 1.302 for julgado, a
    reavaliação muda o resultado — e dá para provar por quê."""
    from servidor import banco

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("DELETE FROM oportunidade")
        cur.execute(
            "INSERT INTO oportunidade (entidade, cpf, trilha, referencia, "
            "veredicto, motivos, catalogo_versao) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            ("demo-a", "52998224725", "executar", "GIFA-2006", "FALTA",
             '["fora do rol, Tema 1.302 pendente"]', 1),
        )
        cur.execute("SELECT veredicto, catalogo_versao FROM oportunidade")
        checa(cur.fetchone() == ("FALTA", 1), "o veredicto não foi guardado")
        try:
            cur.execute(
                "INSERT INTO oportunidade (entidade, cpf, trilha, referencia, "
                "veredicto, catalogo_versao) VALUES (%s,%s,%s,%s,%s,%s)",
                ("demo-a", "11144477735", "executar", "X", "TALVEZ", 1),
            )
            checa(False, "o banco aceitou um veredicto que não existe")
        except Exception:
            pass
    print("  ok     veredicto versionado, e valor inválido é recusado")


def teste_apagar_pessoa_deixa_tombstone():
    """Filiação sindical é dado sensível e a eliminação tem de funcionar. O
    tombstone é o que concilia isso com a camada 1 ser append-only: deixa de
    ser imutável e passa a ser AUDITÁVEL."""
    from servidor import banco

    with banco.sessao(URL, "demo-a") as cur:
        # NÃO se limpa o tombstone: apagar a auditoria é justamente o que
        # este esquema impede, e o teste seguinte prova.
        cur.execute("DELETE FROM pessoa WHERE cpf = %s", ("52998224725",))
        cur.execute(
            "INSERT INTO tombstone (entidade, cpf_hash, motivo, pedido_por) "
            "VALUES (%s,%s,%s,%s)",
            ("demo-a", "hash-sintetico", "LGPD art. 18, VI", "titular"),
        )
        cur.execute("SELECT count(*) FROM pessoa WHERE cpf = %s",
                    ("52998224725",))
        checa(cur.fetchone()[0] == 0, "a pessoa não foi apagada")
        cur.execute("SELECT motivo FROM tombstone "
                    "WHERE cpf_hash = 'hash-sintetico' ORDER BY apagado_em DESC")
        checa(cur.fetchone()[0] == "LGPD art. 18, VI",
              "o tombstone não registrou o motivo")
    print("  ok     apaga a pessoa e deixa registro de que apagou")


def teste_a_auditoria_nao_pode_ser_reescrita():
    """A aplicação não reescreve o próprio log. Se pudesse, ele não serviria
    para nada depois de um incidente."""
    from servidor import banco

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute(
            "INSERT INTO leitura (entidade, quem_hash, o_que) VALUES (%s,%s,%s)",
            ("demo-a", "hash", "meus-processos"),
        )
    for sql in ("UPDATE leitura SET o_que = 'nada'", "DELETE FROM leitura"):
        with banco.sessao(URL, "demo-a") as cur:
            try:
                cur.execute(sql)
                checa(False, f"a aplicação conseguiu executar: {sql}")
            except Exception:
                pass
    print("  ok     log de leitura e tombstone são só escrita e leitura")


def teste_toda_tabela_tem_politica():
    """A regra do esquema: nenhuma tabela sem entidade, nenhuma sem política.
    Uma tabela nova que escape disso é a porta do próximo vazamento."""
    from servidor import banco

    with banco.cru(URL) as cur:
        cur.execute("""
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity
                   OR NOT EXISTS (SELECT 1 FROM pg_policy p
                                  WHERE p.polrelid = c.oid))
        """)
        desprotegidas = [linha[0] for linha in cur.fetchall()]
        cur.execute("""
            SELECT c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND NOT EXISTS (SELECT 1 FROM pg_attribute a
                              WHERE a.attrelid = c.oid
                                AND a.attname = 'entidade' AND a.attnum > 0)
        """)
        sem_entidade = [linha[0] for linha in cur.fetchall()]
    checa(desprotegidas == [],
          f"tabelas sem RLS forçado ou sem política: {desprotegidas}")
    checa(sem_entidade == [],
          f"tabelas sem coluna `entidade`: {sem_entidade}")
    print("  ok     toda tabela tem entidade, RLS forçado e política")



TESTES.extend([
    teste_sem_declarar_a_entidade_nao_le_nada,
    teste_uma_entidade_nao_le_a_outra,
    teste_consulta_sem_filtro_nao_vaza,
    teste_nao_da_para_escrever_na_entidade_alheia,
    teste_o_dono_da_tabela_tambem_obedece,
    teste_a_divergencia_sobrevive_no_banco,
    teste_oportunidade_guarda_a_versao_do_catalogo,
    teste_apagar_pessoa_deixa_tombstone,
    teste_a_auditoria_nao_pode_ser_reescrita,
    teste_toda_tabela_tem_politica,
])

#: A trava de região não precisa de banco: roda sempre.
SEM_BANCO = [
    teste_entidade_real_fora_do_brasil_e_recusada,
    teste_entidade_de_demonstracao_roda_em_qualquer_regiao,
    teste_regiao_brasileira_libera,
]


def _rodar(casos: list) -> None:
    for teste in casos:
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


def main() -> int:
    print("=" * 70)
    print("BANCO — isolamento entre entidades e trava de região")
    print("=" * 70)
    _rodar(SEM_BANCO)
    if not URL:
        print("\n  --     RLS PULADO: defina PROTOCOL_DATABASE_URL para "
              "exercitar o isolamento no banco")
    else:
        preparar()
        _rodar(TESTES)
    print("-" * 70)
    if falhas:
        print(f"{len(falhas)} falha(s):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    quantos = len(SEM_BANCO) + (len(TESTES) if URL else 0)
    # A última linha é o que o relatório geral mostra. Sem isto, "3 grupos
    # passaram" esconderia que o isolamento NÃO foi exercitado — e suíte
    # pulada que parece aprovada é o que faz alguém confiar no que não testou.
    pulo = "" if URL else "  [RLS PULADO: sem PROTOCOL_DATABASE_URL]"
    print(f"{quantos} grupos de teste passaram{pulo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
