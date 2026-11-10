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

## Reprojeções — quando o que muda é o DADO, não a forma

| data | o quê | feita em São Paulo? |
|---|---|---|
| 10/11/2026 | `documento.tem_texto` ficava em `false` para TODO documento. A coluna passou a ser lida (a fila de leitura humana do painel), então as linhas antigas precisam ser regravadas: `banco.reconstruir` com o diário de cada entidade, e `ingerir_documentos.py` de novo sobre os documentos do sindicato. As duas regravam a coluna com o valor medido | **não — PENDENTE** |

Sem isso, um banco antigo mostra no painel TODO documento como "aguardando
leitura". Não há SQL que resolva: o valor certo de cada linha só sai do
diário e dos próprios arquivos.
