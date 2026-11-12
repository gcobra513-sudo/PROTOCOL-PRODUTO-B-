"""O veredicto guardado, e a prova de por que mudou.

A tabela `oportunidade` existia no esquema desde o checkpoint 9 e NINGUÉM
ESCREVIA NELA. O comentário acima dela prometia o produto auditável: quando
o tribunal julgar, a reavaliação muda o resultado, e a linha guardada diz de
qual catálogo o resultado anterior saiu.

O QUE ESTES TESTES PROVAM, e é diferente de "a função foi chamada":

1. que o veredicto guardado diz de qual catálogo saiu — a assinatura
   DECLARADA e a impressão digital MEDIDA do conteúdo;
2. que editar o catálogo sem subir a versão é RECUSADO, porque aí a prova
   de origem está mentindo, e prova falsa é pior que prova nenhuma;
3. que a transição aparece — `FALTA` de ontem, `PODE` de hoje, as duas
   linhas lado a lado;
4. que nada disso atravessa entidade.

SEM BANCO ESTA SUÍTE É PULADA, e o resumo diz isso. Suíte pulada não está
testada.

Spec: `docs/superpowers/specs/2026-11-02-oportunidade-persistida-design.md`
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

URL = os.environ.get("PROTOCOL_DATABASE_URL", "").strip()

falhas: list[str] = []


def checa(cond: bool, msg: str) -> None:
    if not cond:
        falhas.append(msg)


def secao(titulo: str) -> None:
    print(f"\n-- {titulo}")


def preparar() -> None:
    from servidor import banco

    banco.criar_esquema(URL, recriar=True)


def _cpf(n: int) -> str:
    """CPF sintético com dígito que fecha. A base é o índice, não ninguém."""
    base = [int(c) for c in f"{n:09d}"]
    for peso0 in (10, 11):
        soma = sum(d * (peso0 - i) for i, d in enumerate(base))
        base.append((soma * 10 % 11) % 10)
    return "".join(map(str, base))


A = _cpf(7001)
B = _cpf(7002)
#: Para os testes da ferramenta, que rodam sobre ENTIDADE PRÓPRIA.
#: Reusar `demo-a` e `A` fez o primeiro teste da ferramenta ler as
#: linhas montadas à mão dos testes de banco e acusar um `PODE` que
#: o motor não tinha emitido — contaminação entre testes, achada pelo
#: próprio teste.
C = _cpf(7003)
D = _cpf(7004)


# ------------------------------------------------------------- o esquema

def teste_a_assinatura_entra_na_chave_e_o_inteiro_sai():
    """A coluna era `catalogo_versao integer`, e o inteiro é a hipótese de
    um contrato só.

    Um sindicato com duas carreiras tem DUAS versões de catálogo, e não há
    inteiro que as represente. O motor já tinha a resposta pronta —
    `Catalogo.assinatura`, que devolve `"slug@2 outro@1"` — e a coluna não
    conseguia guardá-la.

    E A ASSINATURA ENTRA NA CHAVE PRIMÁRIA, o que faz a tabela ser
    append-only: reavaliar sob catálogo novo INSERE em vez de sobrescrever.
    Tem de ser assim porque o veredicto antigo NÃO é recalculável — o
    catálogo que o produziu pode já ter sido editado em disco. É o mesmo
    argumento do diário.
    """
    secao("o esquema")
    from servidor import banco

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'oportunidade' AND table_schema = 'public'
        """)
        colunas = {linha[0] for linha in cur.fetchall()}
        cur.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a
              ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'oportunidade'::regclass AND i.indisprimary
        """)
        chave = {linha[0] for linha in cur.fetchall()}

    checa("catalogo_versao" not in colunas,
          "`catalogo_versao integer` continua lá, e com duas carreiras não "
          "há inteiro que represente duas versões")
    checa("catalogo_assinatura" in colunas,
          f"falta `catalogo_assinatura`: {sorted(colunas)}")
    checa("catalogo_digest" in colunas,
          f"falta `catalogo_digest`, a impressão MEDIDA do conteúdo: "
          f"{sorted(colunas)}")
    checa("catalogo_assinatura" in chave,
          f"a assinatura não está na chave primária, então reavaliar "
          f"sobrescreve o veredicto anterior: {sorted(chave)}")
    print("  ok     assinatura na chave, inteiro fora, digest presente")


def teste_oportunidade_tem_a_politica_e_o_force():
    """Toda tabela tem política, e FORCE — sem o FORCE o DONO da tabela
    ignora a política, e as migrações rodam como dono."""
    from servidor import banco

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("""
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class WHERE oid = 'oportunidade'::regclass
        """)
        ligada, forcada = cur.fetchone()
        cur.execute("SELECT count(*) FROM pg_policy "
                    "WHERE polrelid = 'oportunidade'::regclass")
        politicas = cur.fetchone()[0]
    checa(ligada, "RLS não está ligada em oportunidade")
    checa(forcada, "falta FORCE ROW LEVEL SECURITY em oportunidade")
    checa(politicas >= 1, "oportunidade não tem política nenhuma")
    print("  ok     RLS ligada, forçada, e com política")


# -------------------------------------------- a impressão do catálogo

def _catalogo_em_pasta(tmp: Path, troca: tuple[str, str] | None = None):
    """Uma cópia dos catálogos de verdade, opcionalmente com um byte trocado.

    CÓPIA DOS DE VERDADE, e não um TOML inventado aqui: um catálogo de
    brinquedo mediria o digest de um arquivo que não se parece com o que roda
    em produção, e o que interessa é justamente a sensibilidade ao conteúdo
    REAL.
    """
    import shutil

    from nucleo import entendimentos as ent

    tmp.mkdir(parents=True, exist_ok=True)
    for origem in sorted(Path(RAIZ / "config" / "categorias").glob("*.toml")):
        destino = tmp / origem.name
        texto = origem.read_text(encoding="utf-8")
        if troca and troca[0] in texto:
            texto = texto.replace(*troca, 1)
        destino.write_text(texto, encoding="utf-8")
    return ent.carregar_categorias(tmp)


def teste_o_digest_muda_com_o_conteudo_e_a_assinatura_nao():
    """Tarefa 2, e é o teste que justifica a coluna existir.

    A assinatura é o que o catálogo DIZ de si. O digest é o que ele É.
    Enquanto os dois concordam, a assinatura basta; é quando divergem que a
    linha guardada passaria a citar uma origem falsa — e divergir é fácil,
    porque subir a `versao` é disciplina de quem edita, e o comentário do
    próprio TOML registra que já falhou: "ninguém conferia, e nada casava".
    """
    secao("a impressão do catálogo")
    import tempfile

    base = Path(tempfile.mkdtemp(prefix="catalogo-"))
    original = _catalogo_em_pasta(base / "antes")

    checa(original.assinatura,
          "o catálogo de verdade não tem assinatura nenhuma")
    checa(len(original.digest) >= 12,
          f"o digest é curto demais para servir de impressão: "
          f"{original.digest!r}")

    # UM BYTE trocado no texto de um entendimento — não na versão.
    mexido = _catalogo_em_pasta(
        base / "depois", ("homologado = \"N\"", "homologado = \"S\""))
    checa(mexido.assinatura == original.assinatura,
          "trocar o conteúdo mudou a assinatura declarada, e o teste deixa "
          "de medir a divergência que a coluna existe para pegar")
    checa(mexido.digest != original.digest,
          "o conteúdo mudou e o digest não: a impressão não está medindo o "
          "conteúdo")

    # E é ESTÁVEL: ler a mesma pasta duas vezes dá a mesma impressão, senão
    # toda reavaliação pareceria catálogo novo.
    de_novo = _catalogo_em_pasta(base / "antes")
    checa(de_novo.digest == original.digest,
          "o digest mudou sem o conteúdo mudar — toda reavaliação pareceria "
          "catálogo novo, e a tabela cresceria sem motivo")
    print("  ok     o digest segue o conteúdo; a assinatura, a declaração")


def teste_a_origem_e_RECORTADA_pelo_contrato():
    """Eu escrevi este teste primeiro ao contrário, e a hipótese estava errada.

    A primeira versão exigia que o digest NÃO mudasse com o contrato, pelo
    argumento de que "de qual catálogo saiu este veredicto" tem de ter uma
    resposta só. Mas `restrito_a` já recorta `versoes` pelo contrato — e está
    certo, por dois motivos que só aparecem olhando o efeito:

    1. **linha nova sem nada ter mudado.** A tabela é append-only por
       assinatura. Se a assinatura de um sindicato mudasse porque o catálogo
       de uma carreira que ele NÃO contratou foi editado, a reavaliação
       inseriria uma linha por pessoa por oportunidade — com veredicto
       idêntico. Crescimento sem informação.
    2. **a recusa falsa.** Se o digest cobrisse a pasta inteira e a
       assinatura só o contratado, editar o arquivo alheio faria os dois
       divergirem, e a trava de "conteúdo mudou sem subir versão" recusaria
       gravar para quem não tem nada a ver com aquilo.

    Então os DOIS são recortados pelo contrato, e é por isso que eles podem
    ser comparados: eles só divergem quando a declaração mente.
    """
    import tempfile

    from nucleo import entendimentos as ent

    base = Path(tempfile.mkdtemp(prefix="catalogo-contrato-"))
    inteiro = _catalogo_em_pasta(base)
    slugs = sorted(inteiro.slugs.values())
    checa(len(slugs) >= 2,
          f"o teste precisa de duas categorias em disco, achei {slugs}")

    so_uma = ent.carregar_categorias(base, (slugs[0],))
    checa(so_uma.digest != inteiro.digest,
          "o digest não foi recortado pelo contrato, e aí ele discorda da "
          "assinatura por um motivo que não é mentira nenhuma")
    checa(so_uma.assinatura.count("@") == 1,
          f"a assinatura de um contrato de uma categoria cita mais de uma: "
          f"{so_uma.assinatura!r}")

    # E O QUE IMPORTA: mexer no arquivo que ESTE sindicato não contratou não
    # muda a origem dele.
    outro_slug = slugs[1]
    mexido = Path(tempfile.mkdtemp(prefix="catalogo-alheio-"))
    for origem in sorted(base.glob("*.toml")):
        texto = origem.read_text(encoding="utf-8")
        if origem.stem == outro_slug:
            texto = texto.replace("homologado = \"N\"",
                                  "homologado = \"S\"", 1)
        (mexido / origem.name).write_text(texto, encoding="utf-8")
    depois = ent.carregar_categorias(mexido, (slugs[0],))
    checa(depois.digest == so_uma.digest,
          "editar o catálogo de uma carreira NÃO contratada mudou a origem "
          "deste sindicato, e isso inseriria linha nova sem nada ter mudado")
    print("  ok     a origem é recortada pelo contrato, nas duas colunas")


# ------------------------------------------------------ a gravação

def _oportunidade(referencia: str, veredicto: str, trilha: str = "ajuizar",
                  faltas: tuple[str, ...] = ()):
    from nucleo import dito, motor, pendencia

    return motor.Oportunidade(
        trilha=trilha,
        referencia=referencia,
        rotulo=f"Rótulo de {referencia}",
        veredicto=veredicto,
        categoria="Auditor-Fiscal da Receita Federal do Brasil",
        motivos=(dito.ambos("porque sim"), dito.ambos("e porque isto")),
        falta=tuple(pendencia.Falta(quem="CONFERENCIA", o_que=f) for f in faltas),
    )


def teste_grava_o_veredicto_com_a_origem():
    """O que a linha guarda: o veredicto, os motivos, o que falta — e DE QUAL
    CATÁLOGO saiu, nas duas formas."""
    secao("a gravação")
    from servidor import banco

    quantas = banco.registrar_oportunidades(
        URL, "demo-a", A,
        [_oportunidade("TEMA-1302", "FALTA", faltas=("o rol da coletiva",))],
        assinatura="slug@1", digest="digest-do-conteudo-1",
    )
    checa(quantas == 1, f"gravou {quantas} em vez de 1")

    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT cpf, trilha, referencia, veredicto, motivos, "
                    "falta, catalogo_assinatura, catalogo_digest "
                    "FROM oportunidade")
        linhas = cur.fetchall()
    checa(len(linhas) == 1, f"{len(linhas)} linha(s) em oportunidade")
    cpf, trilha, ref, ver, motivos, falta, assinatura, digest = linhas[0]
    checa(cpf == A and trilha == "ajuizar" and ref == "TEMA-1302",
          f"a chave saiu diferente: {linhas[0][:3]}")
    checa(ver == "FALTA", f"veredicto {ver!r}")
    checa(motivos == ["porque sim", "e porque isto"],
          f"os motivos não chegaram inteiros: {motivos}")
    checa(falta == [{"quem": "CONFERENCIA", "o_que": "o rol da coletiva"}],
          f"a falta perdeu o DONO, e sem dono a tela volta a ser um saco "
          f"único de pendências: {falta}")
    checa(assinatura == "slug@1" and digest == "digest-do-conteudo-1",
          f"a origem não ficou: {assinatura!r} {digest!r}")
    print("  ok     veredicto, motivos, falta com dono, e a origem")


def teste_gravar_duas_vezes_o_mesmo_nao_duplica():
    """IDEMPOTENTE, e tem de ser: a reavaliação roda por agendador, e um
    agendador que duplica a cada rodada enche a tabela de linhas iguais."""
    from servidor import banco

    for _ in range(3):
        banco.registrar_oportunidades(
            URL, "demo-a", A,
            [_oportunidade("TEMA-1302", "FALTA", faltas=("o rol da coletiva",))],
            assinatura="slug@1", digest="digest-do-conteudo-1",
        )
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT count(*) FROM oportunidade WHERE cpf = %s", (A,))
        quantas = cur.fetchone()[0]
    checa(quantas == 1, f"três gravações iguais deixaram {quantas} linhas")
    print("  ok     gravar o mesmo três vezes deixa uma linha")


def teste_catalogo_novo_INSERE_em_vez_de_sobrescrever():
    """O append-only, e é ele que faz a transição existir.

    O veredicto antigo NÃO é recalculável: o catálogo que o produziu pode já
    ter sido editado em disco. Sobrescrever apagaria a única prova de que
    ontem a resposta era outra.
    """
    from servidor import banco

    banco.registrar_oportunidades(
        URL, "demo-a", A, [_oportunidade("TEMA-1302", "PODE")],
        assinatura="slug@2", digest="digest-do-conteudo-2",
    )
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT catalogo_assinatura, veredicto FROM oportunidade "
                    "WHERE cpf = %s ORDER BY catalogo_assinatura", (A,))
        linhas = cur.fetchall()
    checa(linhas == [("slug@1", "FALTA"), ("slug@2", "PODE")],
          f"as duas linhas não estão lado a lado: {linhas}")
    print("  ok     catálogo novo insere; o veredicto de ontem fica")


def teste_conteudo_mudado_com_assinatura_igual_e_RECUSADO():
    """A trava inteira desta entrega.

    Subir a `versao` do TOML é disciplina de quem edita, e o comentário da
    própria `versao` registra o dia em que a disciplina falhou: "ninguém
    conferia, e nada casava". Se o conteúdo muda e a assinatura não, a linha
    guardada passa a citar uma origem que não produziu aquele veredicto — e
    prova falsa é PIOR que prova nenhuma, porque ninguém desconfia dela.

    Então recusa, e a mensagem diz o que fazer: subir a versão do arquivo.
    E NADA é gravado — nem a linha nova, nem metade dela.
    """
    from servidor import banco

    antes = banco.oportunidades_de(URL, "demo-a", A)
    caiu = ""
    try:
        banco.registrar_oportunidades(
            URL, "demo-a", A, [_oportunidade("TEMA-1302", "PODE")],
            assinatura="slug@2", digest="OUTRO-digest-sem-subir-a-versao",
        )
    except banco.CatalogoIncoerente as e:
        caiu = str(e)
    checa(caiu, "gravou com a origem mentindo")
    checa("versao" in caiu or "versão" in caiu,
          f"a recusa não diz o que fazer: {caiu!r}")
    checa("slug@2" in caiu,
          f"a recusa não diz QUAL catálogo subir de versão: {caiu!r}")
    checa(banco.oportunidades_de(URL, "demo-a", A) == antes,
          "a recusa deixou alguma coisa gravada")
    print("  ok     origem mentindo é recusada, e nada é gravado")


def teste_o_veredicto_nao_atravessa_entidade():
    """Um sindicato nunca vê o dado de outro, e a política é do banco."""
    from servidor import banco

    banco.registrar_oportunidades(
        URL, "demo-b", B, [_oportunidade("TEMA-1302", "FALTA")],
        assinatura="slug@1", digest="digest-do-conteudo-1",
    )
    checa(banco.oportunidades_de(URL, "demo-a", B) == [],
          "a entidade A vê o veredicto da B")
    with banco.sessao(URL, "demo-b") as cur:
        cur.execute("SELECT count(*) FROM oportunidade WHERE cpf = %s", (A,))
        checa(cur.fetchone()[0] == 0, "a entidade B vê o veredicto da A")
    print("  ok     o veredicto guardado não atravessa entidade")


# ------------------------------------------------------- a transição

def teste_a_transicao_aparece_entre_duas_assinaturas():
    """A pergunta que o sindicato faz: "o que mudou quando o catálogo subiu?"

    É para responder isto que a tabela é append-only. A resposta não é
    derivável do catálogo de hoje — o de ontem pode já ter sido editado em
    disco —, então ela sai da comparação entre duas linhas guardadas.
    """
    secao("a transição")
    from servidor import banco

    mudou = banco.mudancas(URL, "demo-a")
    checa(len(mudou) == 1, f"devia haver 1 transição, há {len(mudou)}: {mudou}")
    m = mudou[0]
    checa(m["cpf"] == A and m["referencia"] == "TEMA-1302",
          f"a transição é de outra coisa: {m}")
    checa(m["de"] == "FALTA" and m["para"] == "PODE",
          f"a transição saiu errada: {m['de']} -> {m['para']}")
    checa(m["assinatura_anterior"] == "slug@1"
          and m["assinatura"] == "slug@2",
          f"a transição não diz entre quais catálogos: {m}")
    print("  ok     FALTA -> PODE, e entre quais catálogos")


def teste_veredicto_igual_sob_catalogo_novo_NAO_e_transicao():
    """Catálogo novo que não muda a resposta de alguém não é notícia.

    Sem isto, subir a versão do catálogo faria o painel anunciar a base
    inteira como "mudou" — e um painel que grita tudo não aponta nada.
    """
    from servidor import banco

    banco.registrar_oportunidades(
        URL, "demo-a", A, [_oportunidade("TEMA-1302", "PODE")],
        assinatura="slug@3", digest="digest-do-conteudo-3",
    )
    mudou = banco.mudancas(URL, "demo-a")
    checa(len(mudou) == 1,
          f"PODE -> PODE entrou como transição: {mudou}")
    print("  ok     mesma resposta sob catálogo novo não é transição")


def teste_a_transicao_pode_ser_recortada_pela_assinatura():
    """O painel pergunta pelo catálogo DE AGORA, não pela história inteira."""
    from servidor import banco

    banco.registrar_oportunidades(
        URL, "demo-a", A, [_oportunidade("TEMA-1302", "FALTA")],
        assinatura="slug@4", digest="digest-do-conteudo-4",
    )
    checa(len(banco.mudancas(URL, "demo-a")) == 2,
          "a história inteira devia ter duas transições")
    so_agora = banco.mudancas(URL, "demo-a", assinatura="slug@4")
    checa(len(so_agora) == 1 and so_agora[0]["para"] == "FALTA",
          f"o recorte pela assinatura não funcionou: {so_agora}")
    checa(banco.mudancas(URL, "demo-a", assinatura="slug@1") == [],
          "a primeira avaliação de alguém não é transição — não havia antes")
    print("  ok     a transição se recorta pelo catálogo de agora")


def teste_a_transicao_nao_atravessa_entidade():
    from servidor import banco

    checa(banco.mudancas(URL, "demo-b") == [],
          "a entidade B vê transição da A")
    print("  ok     a transição não atravessa entidade")


# -------------------------------------------------------- a ferramenta

def _entidade_com_catalogo(apelido: str, slug: str):
    """Uma entidade em disco que CONTRATOU uma categoria de verdade."""
    import tempfile

    from servidor import entidades

    raiz = Path(tempfile.mkdtemp(prefix="reavaliar-"))
    ent = entidades.Cadastro(raiz).criar(apelido, "Sindicato de Exemplo",
                                         categorias=(slug,))
    ent.pasta(raiz).mkdir(parents=True, exist_ok=True)
    return ent, raiz


def _semear_pessoas(apelido: str, cpfs: tuple[str, ...]) -> None:
    from servidor import banco

    registros = [{
        "protocolo": f"PRT-{i}",
        "recebido_em": "2026-11-02T00:00:00+00:00",
        "entidade": apelido,
        "linha": {
            "cpf": cpf,
            # NOME SEM O CPF DENTRO. A primeira versão escrevia
            # f"PESSOA {cpf}", e isso derrotava a asserção de que a resposta
            # da API não traz CPF em claro: o CPF aparecia no JSON, dentro
            # do nome, e o teste acusava um vazamento que era do dublê.
            "nome_completo": f"PESSOA DE EXEMPLO {i + 1} (FICTÍCIA)",
            "email": f"exemplo-{cpf}@exemplo.invalid",
            "cargo": "Auditor Fiscal da Receita Federal",
            "situacao": "aposentado",
            "filiado_desde": "2004-03",
        },
        "arquivos": {"contribuicao": "a" * 64},
    } for i, cpf in enumerate(cpfs)]
    banco.reconstruir(URL, apelido, registros, consentimento_novo=True)


def _rodar_ferramenta(ent, raiz, catalogos: Path | None = None):
    import subprocess

    comando = [sys.executable,
               str(RAIZ / "ferramentas" / "reavaliar_oportunidades.py"),
               "--entidade", ent.apelido, "--raiz", str(raiz),
               "--banco", URL]
    if catalogos is not None:
        comando += ["--catalogos", str(catalogos)]
    return subprocess.run(comando, capture_output=True, text=True,
                          env={**os.environ, "PROTOCOL_DATABASE_URL": URL})


def teste_a_ferramenta_avalia_a_base_e_grava():
    """O caminho inteiro, com o catálogo e o motor DE VERDADE.

    Os testes acima montam `Oportunidade` à mão para isolar o banco. Este
    não: ele lê os catálogos de `config/categorias/`, roda o motor, e exige
    que o que saiu dali esteja na tabela. É o que pega a diferença entre
    "a função grava o que eu passei" e "o produto grava o que o motor diz".
    """
    secao("a ferramenta")
    from servidor import banco

    ent, raiz = _entidade_com_catalogo(
        "demo-ferramenta", "auditor-fiscal-receita-federal")
    _semear_pessoas("demo-ferramenta", (C, D))

    r = _rodar_ferramenta(ent, raiz)
    checa(r.returncode == 0,
          f"saiu {r.returncode}:\n{r.stdout}\n{r.stderr}")
    checa(C not in r.stdout + r.stderr and D not in r.stdout + r.stderr,
          "a ferramenta imprimiu CPF")

    guardadas = banco.oportunidades_de(URL, "demo-ferramenta", C)
    checa(guardadas, "não gravou veredicto nenhum para quem está na base")
    assinaturas = {g["catalogo_assinatura"] for g in guardadas}
    checa(any("@" in a for a in assinaturas),
          f"a assinatura guardada não parece de catálogo: {assinaturas}")
    checa(all(g["catalogo_digest"] for g in guardadas),
          "gravou sem a impressão do conteúdo")
    # E o que o motor diz hoje: nada homologado, então nada pode.
    checa(all(g["veredicto"] in ("FALTA", "NAO_PODE") for g in guardadas),
          f"algo saiu como PODE sem homologação: "
          f"{[g['veredicto'] for g in guardadas]}")
    print(f"  ok     {len(guardadas)} veredicto(s) do motor de verdade, "
          f"com origem")


def teste_a_ferramenta_RECUSA_catalogo_que_mudou_sem_subir_versao():
    """E o código de saída tem de DISTINGUIR a mentira do trabalho parcial.

    O 1 das outras ferramentas significa "rodou, mas algo ficou de fora" —
    o trabalho andou. Catálogo mentindo é o contrário: nada andou, e ninguém
    deve tentar de novo até alguém subir a `versao`. O agendador levanta nos
    dois casos (só o 0 é sucesso), mas quem LÊ o registro precisa saber qual
    dos dois aconteceu.
    """
    import shutil
    import tempfile

    ent, raiz = _entidade_com_catalogo(
        "demo-mentira", "auditor-fiscal-receita-federal")
    _semear_pessoas("demo-mentira", (C,))

    original = Path(tempfile.mkdtemp(prefix="cat-ok-"))
    for arquivo in sorted((RAIZ / "config" / "categorias").glob("*.toml")):
        shutil.copy(arquivo, original / arquivo.name)
    primeira = _rodar_ferramenta(ent, raiz, original)
    checa(primeira.returncode == 0,
          f"a primeira rodada falhou:\n{primeira.stdout}\n{primeira.stderr}")

    # Conteúdo trocado, versão NÃO.
    mexido = Path(tempfile.mkdtemp(prefix="cat-mentira-"))
    for arquivo in sorted(original.glob("*.toml")):
        texto = arquivo.read_text(encoding="utf-8")
        if arquivo.stem == "auditor-fiscal-receita-federal":
            texto = texto.replace("homologado = \"N\"",
                                  "homologado = \"S\"", 1)
        (mexido / arquivo.name).write_text(texto, encoding="utf-8")

    r = _rodar_ferramenta(ent, raiz, mexido)
    checa(r.returncode not in (0, 1),
          f"a recusa saiu {r.returncode}, e o agendador trata 0 e 1 como "
          f"rodada boa — a mentira ficaria registrada como sucesso")
    saida = r.stdout + r.stderr
    checa("versao" in saida or "versão" in saida,
          f"a recusa não diz o que fazer:\n{saida}")
    print("  ok     catálogo mentindo: recusa, e o agendador marca falha")


# ------------------------------------------------------- o agendador

def teste_reavaliar_e_tarefa_do_agendador():
    """Uma reavaliação que só roda quando alguém se lembra de rodar é uma
    reavaliação que não acontece — e o produto todo depende de ela acontecer
    no dia em que o tribunal julgar.

    ÚLTIMA NA ORDEM, de propósito: nada hoje depende dela, e pô-la entre
    `coletar` e `avisar` sugeriria uma dependência que não existe. No dia em
    que o veredicto alimentar um aviso, a ordem tem de ser revista.
    """
    secao("o agendador")
    from servidor import agenda, config

    # `pedidos` entrou depois (12/11/2026) e fica por ÚLTIMO: é o lembrete
    # a quem opera, e uma falha de correio nossa não pode atrasar o que é
    # do filiado. `reavaliar` continua depois de `coletar` e `avisar`.
    checa(list(agenda.TAREFAS)
          == ["coletar", "avisar", "reavaliar", "pedidos"],
          f"a ordem ou o conjunto está diferente: {agenda.TAREFAS}")

    cfg = config.carregar({
        "PROTOCOL_RAIZ": "dados_portal",
        "PROTOCOL_MODO_ENSAIO": "1",
    })
    tarefas = agenda.tarefas_padrao(cfg)
    checa("reavaliar" in tarefas,
          f"a tarefa não está ligada a ferramenta nenhuma: "
          f"{sorted(tarefas)}")
    checa(set(tarefas) == set(agenda.TAREFAS),
          f"TAREFAS e tarefas_padrao discordam: {sorted(tarefas)} contra "
          f"{sorted(agenda.TAREFAS)} — e quem roda é o segundo, então uma "
          f"tarefa declarada e não ligada apareceria como atrasada para "
          f"sempre")
    print("  ok     reavaliar é tarefa do agendador, e está ligada")


# ------------------------------------------------------------ o painel

def teste_o_panorama_mostra_o_que_mudou():
    """Tarefa 7. Guardar o veredicto e não mostrar a mudança deixaria o
    produto com a prova no banco e o gestor sem a notícia.

    E A NOTÍCIA PRECISA DE NOME. "3 pessoas mudaram de FALTA para PODE" não
    é acionável; o gestor liga para gente. O painel já mostra nomes em
    "quem você não alcança", e é a mesma tela, com sessão de gestor.
    """
    secao("o painel")
    import json as _json

    from fastapi.testclient import TestClient

    from servidor import banco, config, entidades
    from servidor.app import criar_app

    import tempfile

    raiz = Path(tempfile.mkdtemp(prefix="painel-oportunidade-"))
    ent = entidades.Cadastro(raiz).criar(
        "demo-painel", "Sindicato de Exemplo",
        categorias=("auditor-fiscal-receita-federal",))
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    import csv as _csv

    for arquivo in ("filiados.csv", "gestores.csv"):
        with open(pasta / arquivo, "w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["cpf", "email"])
            w.writerow([C, "gestor@exemplo.invalid"])

    _semear_pessoas("demo-painel", (C,))

    # A ASSINATURA DE HOJE É A DO CATÁLOGO DE VERDADE, e não uma inventada
    # aqui: a rota mostra o que mudou no catálogo DE AGORA, e esse filtro é
    # o certo — sem ele o painel repetiria a história inteira a cada
    # abertura. Escrevi o teste com assinatura inventada na primeira versão
    # e ele não media nada: o filtro descartava as duas linhas.
    from nucleo import entendimentos as _ent

    catalogo = _ent.carregar_categorias(
        _ent.PASTA_PADRAO, ("auditor-fiscal-receita-federal",))
    de_hoje = catalogo.assinatura
    slug = de_hoje.split("@")[0]
    de_ontem = f"{slug}@0"

    # Duas avaliações: a de ontem e a de hoje, com a transição no meio.
    banco.registrar_oportunidades(
        URL, "demo-painel", C, [_oportunidade("GIFA-2006", "FALTA")],
        assinatura=de_ontem, digest="impressao-de-ontem")
    banco.registrar_oportunidades(
        URL, "demo-painel", C, [_oportunidade("GIFA-2006", "PODE")],
        assinatura=de_hoje, digest=catalogo.digest)

    cfg = config.carregar({
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_MODO_ENSAIO": "1",
        "PROTOCOL_DATABASE_URL": URL,
    })
    cliente = TestClient(criar_app(cfg))
    codigo = cliente.post("/api/acesso/codigo",
                          json={"entidade": "demo-painel", "cpf": C}
                          ).json()["codigo_do_ensaio"]
    token = cliente.post("/api/acesso/conferir",
                         json={"entidade": "demo-painel", "cpf": C,
                               "codigo": codigo}).json()["token"]
    r = cliente.get("/api/entidade/demo-painel/panorama",
                    headers={"Authorization": f"Bearer {token}"})
    checa(r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    corpo = r.json()
    checa("mudancas" in corpo,
          f"o panorama não traz as mudanças: {sorted(corpo)}")
    m = corpo["mudancas"]
    checa(m["total"] == 1, f"{m}")
    checa(m["sem_banco"] is False,
          "disse que não há banco, e há — e aí a tela diria 'não dá para "
          "saber' com o dado na mão")
    grupo = m["grupos"][0]
    checa(grupo["referencia"] == "GIFA-2006" and grupo["de"] == "FALTA"
          and grupo["para"] == "PODE", f"{grupo}")
    checa(grupo["pessoas"] == 1, f"{grupo}")
    checa(grupo["exemplos"] and "EXEMPLO" in grupo["exemplos"][0],
          f"a mudança não traz nome, e o gestor liga para gente: {grupo}")
    checa(C not in _json.dumps(corpo),
          "o panorama devolveu CPF em claro")
    print("  ok     o panorama diz o que mudou, com nome e sem CPF")


def teste_sem_banco_o_painel_diz_que_nao_sabe():
    """A diferença entre "nada mudou" e "não dá para saber".

    Sem banco não há veredicto guardado, e devolver `total: 0` afirmaria que
    nada mudou — que é exatamente o relatório tranquilizador que faz ninguém
    perceber. A dúvida não vira resposta.
    """
    from fastapi.testclient import TestClient

    from servidor import config, entidades
    from servidor.app import criar_app

    import csv as _csv
    import tempfile

    raiz = Path(tempfile.mkdtemp(prefix="painel-sem-banco-"))
    ent = entidades.Cadastro(raiz).criar(
        "demo-sem-banco", "Sindicato de Exemplo",
        categorias=("auditor-fiscal-receita-federal",))
    pasta = ent.pasta(raiz)
    pasta.mkdir(parents=True, exist_ok=True)
    for arquivo in ("filiados.csv", "gestores.csv"):
        with open(pasta / arquivo, "w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["cpf", "email"])
            w.writerow([C, "gestor@exemplo.invalid"])

    cfg = config.carregar({
        "PROTOCOL_RAIZ": str(raiz),
        "PROTOCOL_MODO_ENSAIO": "1",
    })
    cliente = TestClient(criar_app(cfg))
    codigo = cliente.post("/api/acesso/codigo",
                          json={"entidade": "demo-sem-banco", "cpf": C}
                          ).json()["codigo_do_ensaio"]
    token = cliente.post("/api/acesso/conferir",
                         json={"entidade": "demo-sem-banco", "cpf": C,
                               "codigo": codigo}).json()["token"]
    corpo = cliente.get("/api/entidade/demo-sem-banco/panorama",
                        headers={"Authorization": f"Bearer {token}"}).json()
    m = corpo["mudancas"]
    checa(m["sem_banco"] is True,
          f"não avisou que não tem como saber: {m}")
    checa(m["grupos"] == [], f"inventou grupo sem banco: {m}")
    print("  ok     sem banco, diz que não sabe em vez de dizer que é zero")


TESTES = [
    teste_a_assinatura_entra_na_chave_e_o_inteiro_sai,
    teste_oportunidade_tem_a_politica_e_o_force,
    teste_o_digest_muda_com_o_conteudo_e_a_assinatura_nao,
    teste_a_origem_e_RECORTADA_pelo_contrato,
    teste_grava_o_veredicto_com_a_origem,
    teste_gravar_duas_vezes_o_mesmo_nao_duplica,
    teste_catalogo_novo_INSERE_em_vez_de_sobrescrever,
    teste_conteudo_mudado_com_assinatura_igual_e_RECUSADO,
    teste_o_veredicto_nao_atravessa_entidade,
    teste_a_transicao_aparece_entre_duas_assinaturas,
    teste_veredicto_igual_sob_catalogo_novo_NAO_e_transicao,
    teste_a_transicao_pode_ser_recortada_pela_assinatura,
    teste_a_transicao_nao_atravessa_entidade,
    teste_a_ferramenta_avalia_a_base_e_grava,
    teste_a_ferramenta_RECUSA_catalogo_que_mudou_sem_subir_versao,
    teste_reavaliar_e_tarefa_do_agendador,
    teste_o_panorama_mostra_o_que_mudou,
    teste_sem_banco_o_painel_diz_que_nao_sabe,
]


def main() -> int:
    print("=" * 70)
    print("O VEREDICTO GUARDADO")
    print("=" * 70)
    if not URL:
        print("PULADO: defina PROTOCOL_DATABASE_URL. Suíte pulada não está "
              "testada.")
        return 0
    preparar()
    for teste in TESTES:
        try:
            teste()
        except Exception as e:  # noqa: BLE001
            import traceback

            falhas.append(f"{teste.__name__} levantou "
                          f"{type(e).__name__}: {e}")
            traceback.print_exc()
    print("-" * 70)
    if falhas:
        print(f"FALHOU ({len(falhas)}):")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print(f"{len(TESTES)} grupos de teste passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
