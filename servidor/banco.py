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
                    "DROP TABLE IF EXISTS "
                    "recebimento, pessoa_afirmacao, pessoa, processo, "
                    "vinculo, movimento, oportunidade, leitura, tombstone "
                    "CASCADE"
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
