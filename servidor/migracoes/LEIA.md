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
| `2026-11-03-oportunidade-origem-do-catalogo.sql` | **não — PENDENTE** |

A coluna da direita é para ser mantida à mão, e ela é a única coisa aqui que
não é verificável por teste: a suíte roda com `recriar=True`, que derruba e
recria, então ela nunca exercita a migração contra um banco antigo. **Suíte
verde não quer dizer que o banco de produção foi migrado.**
