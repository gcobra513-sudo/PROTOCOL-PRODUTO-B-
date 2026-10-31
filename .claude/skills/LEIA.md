# Skills de terceiros neste repositório

## `security-audit`

**De onde veio:** https://github.com/cloudflare/security-audit-skill
**Licença:** MIT, Cloudflare Inc. (a licença está em `security-audit/LICENSE`)
**Baixada em:** 31/10/2026

**O que é:** uma metodologia de auditoria de segurança — orientação de leitura
e, quando pedido explicitamente, um fluxo completo de auditoria com relatório.
Ela não roda sozinha: carregar não autoriza nada, e o próprio texto dela diz
isso.

**O que eu conferi antes de instalar**, porque skill é instrução que eu passo
a seguir e baixar sem ler seria o oposto do que ela prega:

- nenhuma chamada de rede e nenhuma leitura de variável de ambiente nos
  programas (`grep` por `fetch`, `http`, `process.env`: zero ocorrências nos
  validadores);
- os dois programas — `validate-findings.cjs` e `validate-coverage-ledger.cjs`
  — **só leem**: nenhum `writeFile`, `mkdir`, `unlink` ou equivalente. São
  validadores de JSON sem dependência externa, que recebem um caminho como
  argumento;
- os `spawnSync` que aparecem estão só nos arquivos `.test.cjs`, e chamam o
  próprio validador — é a suíte de teste dela mesma;
- rodei um validador contra um JSON vazio e ele recusou corretamente.

**O que ela NÃO substitui:** a suíte deste repositório. `tests/rodar_todos.py`
continua sendo o que diz se o produto faz o que diz.

**Para remover:** `rm -rf .claude/skills/security-audit`
