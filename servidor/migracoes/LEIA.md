# Migrações

`esquema.sql` é a forma de AGORA, e é o que um banco novo recebe.

**`CREATE TABLE IF NOT EXISTS` não altera tabela existente.** Então um banco
que já está em produção não ganha a forma nova por reaplicar o esquema — ele
fica com a forma velha, e o erro só aparece na primeira escrita. Isso já
aconteceu neste repositório com `documento` e `achado`, e está registrado no
cabeçalho de `banco.TABELAS`.

Por isso toda mudança de forma entra também aqui, como arquivo datado, para
rodar uma vez em cada banco que já existe:

```bash
psql "$PROTOCOL_DATABASE_URL" -f servidor/migracoes/<arquivo>.sql
```

| arquivo | aplicada em São Paulo? |
|---|---|
| `2026-11-03-oportunidade-origem-do-catalogo.sql` | **sim — 12/11/2026** |
| `2026-11-10-documento-origem-e-leitura-humana.sql` | **sim — 12/11/2026** |

**Conferido em 12/11/2026, depois de aplicar:** a forma do banco de São Paulo
é IDÊNTICA à de um banco recém-criado por `banco.criar_esquema` — mesma
impressão digital em `conferir_forma.sql` (126 itens: colunas, padrões,
chaves, restrições e isolamento ligado e forçado nas 13 tabelas) e em
`conferir_politicas.sql` (13 políticas, 48 permissões de `protocol_app`).

Antes de aplicar a primeira, que remove uma coluna, foi medido que
`oportunidade` continuava com 0 linhas — a condição que o cabeçalho dela
exige. O banco inteiro estava vazio: 0 em `pessoa`, `documento`,
`recebimento`, `achado`, `tombstone` e `execucao`.

Para conferir de novo, a qualquer momento — impressões iguais nos dois
lados querem dizer que não falta migração:

```bash
psql "$URL_DE_PRODUCAO" -At -f servidor/migracoes/conferir_forma.sql
```

```bash
psql "$URL_DE_UM_BANCO_NOVO" -At -f servidor/migracoes/conferir_forma.sql
```

A coluna da direita é para ser mantida à mão, e ela é a única coisa aqui que
não é verificável por teste: a suíte roda com `recriar=True`, que derruba e
recria, então ela nunca exercita a migração contra um banco antigo. **Suíte
verde não quer dizer que o banco de produção foi migrado.**

## Reprojeções — quando o que muda é o DADO, não a forma

| data | o quê | feita em São Paulo? |
|---|---|---|
| 10/11/2026 | `documento.tem_texto` ficava em `false` para TODO documento. A coluna passou a ser lida (a fila de leitura humana do painel), então as linhas antigas precisam ser regravadas: `banco.reconstruir` com o diário de cada entidade, e `ingerir_documentos.py` de novo sobre os documentos do sindicato. As duas regravam a coluna com o valor medido | **não se aplica — medido em 12/11: 0 linhas em `documento`. Não há linha antiga** |

Sem isso, um banco antigo mostra no painel TODO documento como "aguardando
leitura". Não há SQL que resolva: o valor certo de cada linha só sai do
diário e dos próprios arquivos.
| 10/11/2026 | `documento.origem` nasce `'cadastro'` em toda linha antiga, e para documento que veio do sindicato isso está errado. Rodar `ingerir_documentos.py` de novo regrava `'sindicato'`. **Antes de qualquer reenvio de filiado**: o reenvio substitui o que é `'cadastro'` | **não se aplica — 0 linhas em `documento` em 12/11** |

## Recuperar a projeção inteira, na ordem

1. `banco.reconstruir` com o diário (`recebidos.jsonl`) de cada entidade;
2. `ingerir_acervo.py` e `ingerir_documentos.py` sobre o que o sindicato
   entregou;
3. `banco.projetar_leituras` com `leituras.jsonl` — POR ÚLTIMO, porque a
   leitura humana é sobre um documento, e o documento tem de já estar lá.
