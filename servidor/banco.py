"""
A camada de consulta em Postgres, com o isolamento no banco.

O DIÁRIO CONTINUA SENDO A VERDADE. Este banco é derivado e reconstruível:
`deposito.py` grava append-only com fsync e resolve queda no meio da
gravação, e trocar isso por "o banco é a verdade" jogaria fora uma
propriedade que já está testada.

O QUE O RLS COMPRA, se o servidor já filtra: proteção contra a NOSSA
distração. O erro provável num produto multi-entidade não é alguém burlar o
portão — é um `WHERE entidade = ...` esquecido numa tela nova, daqui a seis
meses. O portão protege a porta; a política protege o que vem depois dela.

COMO SE USA, e é só assim:

    with banco.sessao(url, "sindicato-x") as cur:
        cur.execute("SELECT cpf FROM pessoa")      # sem WHERE: já é da entidade

`cru` existe para UM propósito: o teste que prova que, sem declarar a
entidade, não se lê nada. Nenhum código de produção deve chamá-lo.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import pathlib

ESQUEMA = pathlib.Path(__file__).with_name("esquema.sql")

#: Regiões em que uma entidade REAL pode ser atendida.
#:
#: A LGPD não exige armazenamento no Brasil — o que ela exige é que a
#: transferência internacional tenha mecanismo, e desde 23/08/2025 isso
#: significa as cláusulas-padrão da ANPD (Res. CD/ANPD 19/2024). Manter o dado
#: numa região brasileira elimina a pergunta em vez de respondê-la.
REGIOES_BRASILEIRAS = frozenset({
    "sa-east-1",            # AWS São Paulo (e Supabase)
    "southamerica-east1",   # Google Cloud São Paulo
    "brazilsouth",          # Azure
    "gru",                  # Fly.io São Paulo
    "br",                   # provedor nacional, declarado assim
})


def regiao_e_brasileira(regiao: str) -> bool:
    return (regiao or "").strip().lower() in REGIOES_BRASILEIRAS


#: O papel sob o qual TODA consulta roda.
PAPEL = "protocol_app"

#: TODAS as tabelas do esquema, e esta lista é a de `recriar=True`.
#:
#: Ela esquecia `documento` e `achado` — as duas mais novas. `CREATE TABLE IF
#: NOT EXISTS` não altera tabela existente, então justamente as duas que mais
#: mudam de forma sobreviveriam com a forma velha, e o erro só apareceria na
#: primeira escrita. Um teste confere que nenhuma tabela do banco está fora
#: desta lista.
TABELAS = (
    "recebimento", "pessoa_afirmacao", "pessoa", "documento", "achado",
    "processo", "vinculo", "movimento", "oportunidade", "leitura",
    "aviso_enviado", "tombstone",
)


def _conectar(url: str):
    import psycopg

    return psycopg.connect(url, autocommit=False)


def _assumir_papel(cur) -> None:
    """Troca para o papel da aplicação, sempre, antes de qualquer consulta.

    ISTO NÃO É ZELO. Superusuário IGNORA RLS por completo — inclusive com
    `FORCE ROW LEVEL SECURITY` —, e a URL que a Supabase entrega por padrão
    conecta como `postgres`, que é privilegiado. Sem esta linha, as políticas
    ficariam perfeitas no `pg_policy` e não protegeriam absolutamente nada.

    Descoberto por teste vermelho em 29/10/2026: com a conexão como
    `postgres`, a consulta sem `app.entidade` devolvia as três linhas das duas
    entidades.
    """
    cur.execute(f"SET LOCAL ROLE {PAPEL}")


def criar_esquema(url: str, recriar: bool = False) -> None:
    """Aplica `esquema.sql`.

    `recriar=True` DERRUBA as tabelas antes, e existe porque
    `CREATE TABLE IF NOT EXISTS` não altera tabela que já existe com outra
    forma — a coluna nova simplesmente não aparece, e o erro só surge na
    primeira escrita. É para TESTE e desenvolvimento.

    EM PRODUÇÃO ISTO APAGA TUDO. Antes do primeiro sindicato real, o lugar
    da evolução do esquema é uma migração versionada, não este parâmetro.
    """
    with _conectar(url) as cx:
        with cx.cursor() as cur:
            if recriar:
                cur.execute(
                    "DROP TABLE IF EXISTS " + ", ".join(TABELAS) + " CASCADE"
                )
            cur.execute(ESQUEMA.read_text(encoding="utf-8"))
        cx.commit()


@contextlib.contextmanager
def sessao(url: str, entidade: str):
    """Uma transação com `app.entidade` declarado.

    `set_config(..., true)` e não `SET`: o terceiro argumento `true` é o
    "local", e faz o valor morrer com a transação. Com `SET`, uma conexão
    reaproveitada de um pool carregaria a entidade do pedido anterior — e o
    vazamento seria intermitente, que é o pior tipo.

    E `set_config` em vez de `SET LOCAL` por outro motivo: `SET LOCAL` não
    aceita parâmetro vinculado, o que obrigaria a interpolar o apelido da
    entidade no SQL à mão. Apelido vem de URL.
    """
    if not entidade:
        raise ValueError("sessão exige entidade — sem ela a política barra tudo")
    with _conectar(url) as cx:
        with cx.cursor() as cur:
            _assumir_papel(cur)
            cur.execute("SELECT set_config('app.entidade', %s, true)",
                        (entidade,))
            yield cur
        cx.commit()


@contextlib.contextmanager
def cru(url: str):
    """SEM `app.entidade`. Só para o teste que prova que o RLS está ligado.

    Assume o papel da aplicação do mesmo jeito: um teste que rodasse como
    superusuário provaria o contrário do que pretende.
    """
    with _conectar(url) as cx:
        with cx.cursor() as cur:
            _assumir_papel(cur)
            yield cur
        cx.rollback()


# =====================================================================
# A PROJEÇÃO: o diário é a autoridade, o banco é a vista consultável
#
# NÃO SÃO DUAS FONTES DE VERDADE. É uma fonte e uma projeção dela, e a
# diferença é tudo: duas fontes divergem em silêncio; uma projeção só diverge
# se ninguém conferir — e um teste confere, comparando o panorama montado das
# duas pontas.
#
# O diário dá durabilidade e responde "o que exatamente nos mandaram?". O
# banco dá poder de consulta e um isolamento que o Postgres impõe sozinho,
# contra o `WHERE` esquecido numa tela escrita daqui a seis meses.
# =====================================================================

#: Campos do cadastro projetados como afirmação. Vem do contrato, não de uma
#: lista à mão: lista à mão esquece o campo novo, e o campo esquecido some da
#: projeção sem ninguém ver.
def _campos_do_contrato() -> tuple[str, ...]:
    from nucleo import cadastro as conta

    return conta.CAMPOS


def _impressao(registro: dict) -> str:
    """A impressão digital do registro. É a chave de idempotência.

    `sort_keys` porque a ordem das chaves de um dicionário não é informação —
    sem ele, o mesmo envio relido daria hash diferente e `reconstruir`
    duplicaria tudo a cada execução.
    """
    return hashlib.sha256(
        json.dumps(registro, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _tipo_do_arquivo(nome: str) -> str:
    """UMA definição só, em `nucleo/panorama.py`. Duas cópias desta regra
    divergem — e divergiram: a de lá exigia `.pdf`, esta não, e o painel
    passou a cobrar a sentença de quem já a tinha entregue."""
    from nucleo import panorama

    return panorama.tipo_do_arquivo(nome)


def reconstruir(url: str, entidade: str, registros) -> int:
    """Projeta o diário no banco. Devolve quantos registros foram gravados.

    **IDEMPOTENTE**, e tem de ser: esta é a operação de recuperação, e uma
    recuperação que duplica tudo a cada execução é pior que não ter nenhuma.
    A chave é a impressão digital do próprio registro.

    REGISTRO ILEGÍVEL É PULADO. `deposito.ler_diario` devolve
    `{"_ilegivel": n}` para a linha truncada por queda no meio da escrita, e
    derrubar a projeção inteira por causa dela trocaria um defeito pequeno
    por um grande.

    O QUE ESTA FUNÇÃO NÃO PROJETA, e é deliberado: `pessoa.alcancavel` e
    `pessoa.tem_divergencia`. As duas se calculam cruzando o ACERVO com o
    cadastro, e o acervo ainda não é projetado. Escrevê-las só com o cadastro
    daria um número diferente com o mesmo nome do que `completude` publica —
    e dois números com um nome só é o pior tipo de erro de relatório.
    """
    campos = _campos_do_contrato()
    gravados = 0
    with sessao(url, entidade) as cur:
        for registro in registros or ():
            if not isinstance(registro, dict):
                continue
            linha = registro.get("linha")
            if not isinstance(linha, dict):
                continue
            cpf = "".join(c for c in str(linha.get("cpf") or "") if c.isdigit())
            if not cpf:
                continue

            marca = _impressao(registro)
            quando = str(registro.get("recebido_em") or "") or None

            cur.execute(
                "SELECT id FROM recebimento WHERE entidade = %s AND sha256 = %s",
                (entidade, marca),
            )
            ja = cur.fetchone()
            if ja:
                recebimento_id = ja[0]
            else:
                cur.execute(
                    "INSERT INTO recebimento (entidade, tipo, recebido_em, "
                    "origem, payload, sha256) VALUES "
                    "(%s, 'cadastro', COALESCE(%s::timestamptz, now()), %s, "
                    "%s::jsonb, %s) RETURNING id",
                    (entidade, quando, str(registro.get("protocolo") or ""),
                     json.dumps(registro, ensure_ascii=False), marca),
                )
                recebimento_id = cur.fetchone()[0]
                gravados += 1

            # CAMADA 2 — toda afirmação sobrevive. Gravar por cima apagaria a
            # anterior, e a divergência sumiria junto com ela.
            for campo in campos:
                cur.execute(
                    "INSERT INTO pessoa_afirmacao (entidade, cpf, campo, "
                    "valor, fonte, recebimento_id, afirmado_em) VALUES "
                    "(%s, %s, %s, %s, 'cadastro', %s, "
                    "COALESCE(%s::timestamptz, now())) "
                    "ON CONFLICT DO NOTHING",
                    (entidade, cpf, campo, str(linha.get(campo) or ""),
                     recebimento_id, quando),
                )

            # O VIGENTE sai das DUAS fontes, com o acervo vencendo — não do
            # último que escreveu. Ver `_recalcular_pessoa`.
            _recalcular_pessoa(cur, entidade, cpf)

            # O DOCUMENTO: só o metadado. Os bytes ficam no disco — PDF em
            # coluna faz o banco inchar e não melhora resposta nenhuma.
            for nome, soma in (registro.get("arquivos") or {}).items():
                tipo = _tipo_do_arquivo(nome)
                if not tipo:
                    continue
                cur.execute(
                    "INSERT INTO documento (entidade, cpf, tipo, sha256) "
                    "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (entidade, cpf, tipo, str(soma)),
                )

            # CAMADA 3 — o processo que a pessoa declarou acompanhar.
            from nucleo import cadastro as conta

            for numero in conta.numeros_de_processo(
                linha.get("numeros_de_processo") or ""
            ):
                cur.execute(
                    "INSERT INTO processo (entidade, numero) VALUES (%s,%s) "
                    "ON CONFLICT DO NOTHING", (entidade, numero),
                )
                cur.execute(
                    "INSERT INTO vinculo (entidade, cpf, numero) "
                    "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (entidade, cpf, numero),
                )
    return gravados


#: Campos que o acervo e o cadastro podem afirmar sobre a mesma pessoa. É
#: sobre eles que a divergência se mede — e só sobre eles: comparar um campo
#: que só uma das fontes tem marcaria divergência em toda linha.
CAMPOS_COMUNS = (
    "nome_completo", "email", "telefone", "cargo", "situacao", "unidade",
    "data_nascimento", "data_ingresso", "data_aposentadoria",
    "filiado_desde", "filiado_ate",
)


def _vigentes(cur, cpf: str) -> dict[str, dict[str, str]]:
    """campo -> {fonte: último valor afirmado}."""
    cur.execute(
        "SELECT DISTINCT ON (campo, fonte) campo, fonte, valor "
        "FROM pessoa_afirmacao WHERE cpf = %s "
        "ORDER BY campo, fonte, afirmado_em DESC, id DESC", (cpf,)
    )
    saida: dict[str, dict[str, str]] = {}
    for campo, fonte, valor in cur.fetchall():
        saida.setdefault(campo, {})[fonte] = valor
    return saida


def _recalcular_pessoa(cur, entidade: str, cpf: str) -> None:
    """O valor VIGENTE de uma pessoa, das duas fontes.

    **O ACERVO VENCE**, e isso estava escrito no esquema desde o começo sem
    ninguém implementar: o valor vigente é o do sindicato até ele homologar
    outra coisa. A ordem de chegada não decide qual versão da verdade entra
    na base — se decidisse, quem se cadastrasse depois reescreveria o
    cadastro do sindicato só por ter chegado por último.

    E A AFIRMAÇÃO DO FILIADO NÃO SOME: ela continua na camada 2, e é dela que
    a divergência existe. Divergência não se resolve sozinha: marca e mostra.
    """
    por_campo = _vigentes(cur, cpf)

    def valor(campo: str) -> str:
        fontes = por_campo.get(campo, {})
        # Preenchido vence vazio, e entre dois preenchidos o acervo vence.
        return (fontes.get("acervo") or fontes.get("cadastro") or "").strip()

    divergente = any(
        (por_campo.get(c, {}).get("acervo") or "").strip()
        and (por_campo.get(c, {}).get("cadastro") or "").strip()
        and (por_campo[c]["acervo"].strip()
             != por_campo[c]["cadastro"].strip())
        for c in CAMPOS_COMUNS
    )

    # ALCANÇÁVEL: CPF que fecha E e-mail que serve, de QUALQUER fonte — quem
    # se cadastrou com e-mail bom é alcançável ainda que a planilha do
    # sindicato não tenha o dela.
    #
    # NÃO É O MESMO NÚMERO que `completude.inalcancaveis` publica, e não deve
    # ser: aquele mede a QUALIDADE DA EXPORTAÇÃO do sindicato, e por isso
    # olha só a planilha. São duas perguntas, e juntá-las daria dois números
    # com um nome só.
    from nucleo import cadastro as conta

    emails = [v for fontes in [por_campo.get("email", {})]
              for v in fontes.values() if v and v.strip()]
    alcancavel = bool(conta.cpf_valido(cpf)) and any(
        conta.EMAIL.match(e.strip()) for e in emails
    )

    cur.execute(
        "INSERT INTO pessoa (entidade, cpf, nome, email, cargo, situacao, "
        "data_nascimento, alcancavel, tem_divergencia, atualizado_em) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now()) "
        "ON CONFLICT (entidade, cpf) DO UPDATE SET "
        "nome = EXCLUDED.nome, email = EXCLUDED.email, "
        "cargo = EXCLUDED.cargo, situacao = EXCLUDED.situacao, "
        "data_nascimento = EXCLUDED.data_nascimento, "
        "alcancavel = EXCLUDED.alcancavel, "
        "tem_divergencia = EXCLUDED.tem_divergencia, atualizado_em = now()",
        (entidade, cpf, valor("nome_completo"), valor("email"),
         valor("cargo"), valor("situacao"), valor("data_nascimento"),
         alcancavel, divergente),
    )


def projetar_acervo(url: str, entidade: str, pessoas) -> int:
    """A planilha do sindicato vira base consultável.

    ERA O BURACO DO PRODUTO: `acervo.jsonl` alimentava UMA tela — o retrato
    da base — e parava ali. O motor nunca via a planilha, e tudo o que o
    produto afirmava sobre alguém saía do que a PESSOA digitara no portal.
    Um sindicato com 4.812 filiados e 200 cadastrados via um painel de 200.

    `pessoas` são as de `acervo.ler`: uma por LINHA, e a mesma pessoa pode
    aparecer em várias. Consolidamos por CPF com a regra do leitor —
    preenchido vence vazio —, porque a divergência DENTRO da planilha já foi
    marcada lá, como achado, e remarcá-la aqui não acrescenta nada.
    """
    linhas = [p for p in pessoas or () if getattr(p, "cpf", "")]
    if not linhas:
        return 0

    # Um recebimento por INGESTÃO, não por linha: o que chegou foi o arquivo.
    marca = hashlib.sha256(
        json.dumps([[p.cpf, p.linha_no_arquivo, p.campos] for p in linhas],
                   sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    consolidado: dict[str, dict[str, str]] = {}
    for p in linhas:
        alvo = consolidado.setdefault(p.cpf, {})
        for campo, valor in (p.campos or {}).items():
            if str(valor or "").strip() or campo not in alvo:
                alvo[campo] = str(valor or "").strip()

    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT id FROM recebimento WHERE entidade = %s AND sha256 = %s",
            (entidade, marca),
        )
        ja = cur.fetchone()
        if ja:
            recebimento_id = ja[0]
        else:
            cur.execute(
                "INSERT INTO recebimento (entidade, tipo, origem, payload, "
                "sha256) VALUES (%s, 'acervo', %s, %s::jsonb, %s) "
                "RETURNING id",
                (entidade, f"{len(linhas)} linha(s)",
                 json.dumps({"linhas": len(linhas)}), marca),
            )
            recebimento_id = cur.fetchone()[0]

        from nucleo import cadastro as conta

        for cpf, campos in consolidado.items():
            for campo, valor in campos.items():
                cur.execute(
                    "INSERT INTO pessoa_afirmacao (entidade, cpf, campo, "
                    "valor, fonte, recebimento_id) "
                    "VALUES (%s,%s,%s,%s,'acervo',%s) ON CONFLICT DO NOTHING",
                    (entidade, cpf, campo, valor, recebimento_id),
                )
            _recalcular_pessoa(cur, entidade, cpf)

            for numero in conta.numeros_de_processo(
                campos.get("numeros_de_processo") or ""
            ):
                cur.execute(
                    "INSERT INTO processo (entidade, numero) VALUES (%s,%s) "
                    "ON CONFLICT DO NOTHING", (entidade, numero),
                )
                cur.execute(
                    "INSERT INTO vinculo (entidade, cpf, numero, fonte) "
                    "VALUES (%s,%s,%s,'acervo') ON CONFLICT DO NOTHING",
                    (entidade, cpf, numero),
                )
    return len(consolidado)


def base(url: str, entidade: str) -> list[dict]:
    """TODA a base da entidade — a planilha do sindicato mais os cadastros.

    É o que o motor passa a responder. `cadastros()` continua existindo e
    continua sendo só o cadastro: é ele que o teste de concordância compara
    com o diário, e misturar as fontes ali apagaria essa garantia.

    Cada registro sai com `fonte_cadastro`, para que o panorama possa dizer
    quantos da base já mandaram documento — são dois números diferentes, e o
    gestor precisa dos dois.
    """
    linhas: dict[str, dict] = {}
    fontes: dict[str, set] = {}
    arquivos: dict[str, dict] = {}
    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT DISTINCT ON (cpf, campo, fonte) cpf, campo, fonte, valor "
            "FROM pessoa_afirmacao "
            "ORDER BY cpf, campo, fonte, afirmado_em DESC, id DESC"
        )
        for cpf, campo, fonte, valor in cur.fetchall():
            fontes.setdefault(cpf, set()).add(fonte)
            alvo = linhas.setdefault(cpf, {"cpf": cpf})
            # O acervo vence, e o preenchido vence o vazio.
            atual = alvo.get(campo, "")
            if fonte == "acervo":
                if str(valor or "").strip() or not atual:
                    alvo[campo] = valor
            elif not str(atual or "").strip():
                alvo[campo] = valor
        cur.execute("SELECT cpf, tipo, sha256 FROM documento")
        for cpf, tipo, soma in cur.fetchall():
            arquivos.setdefault(cpf, {})[tipo] = soma

    return [
        {
            "protocolo": "",
            "linha": linha,
            "arquivos": arquivos.get(cpf, {}),
            "fonte_cadastro": "cadastro" in fontes.get(cpf, set()),
        }
        for cpf, linha in sorted(linhas.items())
    ]


def cadastros(url: str, entidade: str) -> list[dict]:
    """Os cadastros desta entidade, na MESMA FORMA que o diário entrega.

    Mesma forma de propósito: `panorama.montar` não precisa saber de onde o
    dado veio, e é isso que permite ao teste comparar os dois caminhos sem
    adaptador no meio — adaptador no meio do teste é onde a divergência se
    esconde.

    Reconstrói da CAMADA 2, não do payload cru da camada 1. Ler o payload de
    volta seria ler o arquivo através do banco e não provaria projeção
    nenhuma; assim, um campo perdido na projeção faz o teste de concordância
    reprovar.
    """
    linhas: dict[str, dict] = {}
    arquivos: dict[str, dict] = {}
    with sessao(url, entidade) as cur:
        # DISTINCT ON com ORDER BY afirmado_em DESC: o vigente é o ÚLTIMO
        # afirmado, e as anteriores continuam na tabela.
        cur.execute(
            "SELECT DISTINCT ON (cpf, campo) cpf, campo, valor "
            "FROM pessoa_afirmacao WHERE fonte = 'cadastro' "
            "ORDER BY cpf, campo, afirmado_em DESC"
        )
        for cpf, campo, valor in cur.fetchall():
            linhas.setdefault(cpf, {})[campo] = valor
        cur.execute("SELECT cpf, tipo, sha256 FROM documento")
        for cpf, tipo, soma in cur.fetchall():
            arquivos.setdefault(cpf, {})[tipo] = soma

    return [
        {"protocolo": "", "linha": linha, "arquivos": arquivos.get(cpf, {})}
        for cpf, linha in sorted(linhas.items())
    ]


def guardar_achados(url: str, entidade: str, cpf: str, documento: str,
                    achados) -> int:
    """Os fatos extraídos de um documento, COM O TRECHO de onde saíram.

    O trecho é a razão de o produto poder afirmar o que afirma: um humano
    confere a extração lendo uma linha, sem abrir o PDF. Extração sem trecho
    é palpite com cara de dado — por isso ele é coluna, não comentário.

    Gravado UMA VEZ, no recebimento. Reler o PDF a cada carregamento de tela
    é consulta de minutos para responder uma página.
    """
    gravados = 0
    with sessao(url, entidade) as cur:
        for a in achados or ():
            cur.execute(
                "INSERT INTO achado (entidade, cpf, documento, tipo, valor, "
                "confianca, trecho, posicao, metodo) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (entidade, cpf, documento, a.tipo, a.valor, a.confianca,
                 a.trecho, a.posicao, a.metodo),
            )
            gravados += cur.rowcount
    return gravados


def achados_do_cpf(url: str, entidade: str, cpf: str) -> list:
    """Os achados gravados desta pessoa, na forma que `leitura` devolve.

    Mesma forma de propósito: quem consome não precisa saber se o fato veio
    de um PDF lido agora ou de uma linha gravada na chegada.
    """
    from nucleo import leitura as mod

    digitos = "".join(c for c in str(cpf or "") if c.isdigit())
    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT tipo, valor, confianca, trecho, posicao, metodo "
            "FROM achado WHERE cpf = %s ORDER BY posicao, tipo", (digitos,)
        )
        return [
            mod.Achado(tipo=t, valor=v, confianca=c, trecho=tr,
                       posicao=pos, metodo=m)
            for t, v, c, tr, pos, m in cur.fetchall()
        ]


def processos_do_cpf(url: str, entidade: str, cpf: str) -> list[str]:
    """Os processos ligados a esta pessoa, venham de onde vierem.

    É a promessa da tela dela — "controle sobre as ações que já correm no seu
    nome" —, e ela só se cumpre com os números que o SINDICATO mandou: pedir
    a uma aposentada que ache 20 dígitos numa papelada e digite no celular é
    pedir que ela desista.
    """
    digitos = "".join(c for c in str(cpf or "") if c.isdigit())
    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT numero FROM vinculo WHERE cpf = %s ORDER BY numero",
            (digitos,),
        )
        return [n for (n,) in cur.fetchall()]


def documentos_do_cpf(url: str, entidade: str, cpf: str) -> tuple[str, ...]:
    """Que TIPOS de documento esta pessoa entregou — não o que eles dizem.

    É o que faz a pendência mudar de dono: quem mandou a sentença está
    esperando leitura, não providência.
    """
    digitos = "".join(c for c in str(cpf or "") if c.isdigit())
    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT DISTINCT tipo FROM documento WHERE cpf = %s ORDER BY tipo",
            (digitos,),
        )
        return tuple(t for (t,) in cur.fetchall())


def guardar_movimentos(url: str, entidade: str, movimentos) -> int:
    """A movimentação coletada, no banco. Devolve quantas linhas são novas.

    `movimento` existia no esquema e ninguém escrevia nela — a coleta ficava
    só no diário em arquivo. Sem ela no banco não há como saber quais
    processos JÁ FORAM COLETADOS ANTES, e sem isso o aviso não consegue
    distinguir estreia de novidade.
    """
    novas = 0
    with sessao(url, entidade) as cur:
        for m in movimentos or ():
            cur.execute(
                "INSERT INTO movimento (entidade, numero, grau, data, nome) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (entidade, m.numero, m.grau, m.data, m.nome),
            )
            novas += cur.rowcount
    return novas


def processos_coletados(url: str, entidade: str) -> set[str]:
    """Os processos de que já se viu movimentação alguma vez.

    É o que separa ESTREIA de novidade. Um processo que não está aqui está
    sendo coletado pela primeira vez, e o histórico dele — a GIFA tem 600
    movimentos — não pode virar e-mail para ninguém.
    """
    with sessao(url, entidade) as cur:
        cur.execute("SELECT DISTINCT numero FROM movimento")
        return {n for (n,) in cur.fetchall()}


def chaves_ja_avisadas(url: str, entidade: str, cpf: str = "") -> set[str]:
    with sessao(url, entidade) as cur:
        if cpf:
            cur.execute(
                "SELECT chave FROM aviso_enviado WHERE cpf = %s", (cpf,)
            )
        else:
            cur.execute("SELECT cpf, chave FROM aviso_enviado")
            return {f"{c}|{k}" for c, k in cur.fetchall()}
        return {k for (k,) in cur.fetchall()}


def marcar_avisado(url: str, entidade: str, cpf: str, chaves,
                   motivo: str = "enviado") -> None:
    """Marca DEPOIS de a mensagem sair.

    A ordem é uma escolha com custo, e a escolha é esta: marcar antes e
    falhar o envio deixa a pessoa sem saber da sentença dela para sempre;
    enviar antes e falhar a marcação a faz receber duas vezes amanhã. Entre
    nunca saber e saber duas vezes, saber duas vezes.

    `motivo='estreia'` marca o histórico de um processo visto pela primeira
    vez — que NÃO foi avisado e não deve ser. Sem essa marca, a proteção da
    estreia dura um dia: o processo fica "conhecido", o histórico continua
    não-avisado, e na rodada seguinte a pessoa recebe os 600 movimentos que
    a estreia tinha evitado. Medido no vivo.
    """
    with sessao(url, entidade) as cur:
        for k in chaves or ():
            cur.execute(
                "INSERT INTO aviso_enviado (entidade, cpf, chave, motivo) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (entidade, cpf, k, motivo),
            )


def destinatarios(url: str, entidade: str) -> list:
    """Quem pediu aviso, com o e-mail do SINDICATO e os processos dele.

    O e-mail sai do acervo — a planilha do sindicato —, nunca do que a pessoa
    digitou: se fosse o digitado, bastaria alguém cadastrar o CPF de outra
    pessoa com o próprio e-mail para passar a receber a movimentação do
    processo dela.
    """
    from nucleo import aviso as mod

    quer: dict[str, bool] = {}
    email: dict[str, str] = {}
    nome: dict[str, str] = {}
    processos: dict[str, list[str]] = {}
    with sessao(url, entidade) as cur:
        cur.execute(
            "SELECT DISTINCT ON (cpf, campo, fonte) cpf, campo, fonte, valor "
            "FROM pessoa_afirmacao WHERE campo IN "
            "('quer_aviso', 'email', 'nome_completo') "
            "ORDER BY cpf, campo, fonte, afirmado_em DESC, id DESC"
        )
        for cpf, campo, fonte, valor in cur.fetchall():
            if campo == "quer_aviso":
                # O opt-in é DELA: o sindicato não marca por ela.
                if fonte == "cadastro":
                    quer[cpf] = str(valor or "").strip().lower() == "sim"
            elif campo == "email" and fonte == "acervo":
                email[cpf] = valor
            elif campo == "nome_completo" and not nome.get(cpf):
                nome[cpf] = valor
        cur.execute("SELECT cpf, numero FROM vinculo")
        for cpf, numero in cur.fetchall():
            processos.setdefault(cpf, []).append(numero)

    return [
        mod.Destinatario(
            cpf=cpf, nome=nome.get(cpf, ""),
            email_do_sindicato=email.get(cpf, ""),
            quer_aviso=True, processos=tuple(sorted(processos.get(cpf, []))),
        )
        for cpf, pediu in sorted(quer.items()) if pediu
    ]


def registrar_leitura(url: str, entidade: str, *, quem_hash: str,
                      o_que: str, alvo_hash: str = "") -> None:
    """Quem viu dado nominal de quem, e quando.

    NUM PRODUTO DE CONSULTA O VAZAMENTO É UM `read`, não um `write`. Sem este
    registro, "quem viu o dado de quem" é pergunta sem resposta — e é a
    primeira que alguém faz depois de um incidente.

    SÓ MARCADOR, NUNCA CPF EM CLARO: um log de auditoria cheio de CPF é um
    segundo banco de dado pessoal, com retenção mais longa e menos cuidado
    que o primeiro.
    """
    with sessao(url, entidade) as cur:
        cur.execute(
            "INSERT INTO leitura (entidade, quem_hash, o_que, alvo_hash) "
            "VALUES (%s,%s,%s,%s)",
            (entidade, quem_hash, o_que, alvo_hash),
        )
