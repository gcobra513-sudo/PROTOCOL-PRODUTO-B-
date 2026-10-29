# O servidor do portal

Recebe o cadastro do filiado e grava a entrega que o motor de lote consome.

```
portal (navegador)  ──HTTP──>  servidor  ──disco──>  entrega/  ──>  motor
```

A entrega é exatamente a que `ferramentas/conferir_entrega.py` já lia antes
deste servidor existir. Não há adaptador entre os dois, e isso é verificado:
`tests/testes_servidor_portal.py` grava pelo HTTP e manda o verificador
consumir o resultado.

## Subir

Desenvolvimento:

```bash
PROTOCOL_MODO_ENSAIO=1 python3 -m servidor --recarregar
```

Produção:

```bash
export PROTOCOL_SEGREDO="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
export PROTOCOL_RAIZ=/var/lib/protocol   # padrão: ./dados_portal
export PROTOCOL_ORIGENS=https://portal.exemplo.org
export PROTOCOL_SMTP_HOST=smtp.exemplo.org
export PROTOCOL_SMTP_REMETENTE=portal@exemplo.org
export PROTOCOL_SMTP_USUARIO=...
export PROTOCOL_SMTP_SENHA=...
python3 -m servidor --porta 8000
```

Sem `PROTOCOL_SEGREDO` o servidor **não sobe**, e diz o que falta. Segredo
padrão é o mesmo que nenhum, com a desvantagem de parecer que existe.

## Variáveis

| Variável | Para quê |
|---|---|
| `PROTOCOL_SEGREDO` | assina código de acesso, token e marcador de CPF. Obrigatória |
| `PROTOCOL_RAIZ` | onde moram os dados. Padrão `dados_portal` — separada de `dados/`, que é versionada |
| `PROTOCOL_ORIGENS` | endereços do portal, separados por vírgula |
| `PROTOCOL_SMTP_*` | `HOST`, `PORTA`, `USUARIO`, `SENHA`, `REMETENTE` |
| `PROTOCOL_EMISSOES_POR_CPF_HORA` | padrão 3 |
| `PROTOCOL_EMISSOES_POR_ORIGEM_HORA` | padrão 20. **Suba** se o sindicato atende vários filiados do mesmo computador da sede |
| `PROTOCOL_MODO_ENSAIO` | `1` dispensa segredo e devolve o código na resposta. Nunca com gente de verdade |

## Cadastrar uma entidade

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from servidor.entidades import Cadastro
import pathlib
print(Cadastro(pathlib.Path('dados_portal')).criar('sind-df', 'Sindicato Tal'))
"
```

O link que a entidade distribui ao filiado é
`https://portal.exemplo.org/?entidade=sind-df`.

## O rol de filiados é obrigatório

`dados_portal/<entidade>/filiados.csv`:

```csv
cpf,email
526.018.159-06,fulano@exemplo.org
```

**Sem esse arquivo a entidade não emite código nenhum**, e o servidor grita no
log. O motivo está em `servidor/rol.py`: o código de acesso vai para o e-mail
que a entidade tem em cadastro, não para um e-mail digitado na tela. Se a
pessoa escolhesse o endereço, qualquer um reivindicaria o CPF de qualquer
outro. Um portão que abre para todos é pior que um fechado, porque parece que
existe.

## O que fica no disco

```
dados_portal/
  entidades.json
  acesso.sqlite3                     códigos e sessões, só em HMAC
  codigos_enviados.log               apenas quando não há SMTP configurado
  <entidade>/
    filiados.csv                     o rol, entregue pela entidade
    recebidos.jsonl                  diário append-only: a verdade
    entrega/
      manifesto.csv                  derivado do diário, 1 linha por CPF
      52601815906/                   os documentos
    historico/52601815906/<ts>/      o que um reenvio substituiu
```

O manifesto é **derivado**, nunca acumulado: apagá-lo não perde nada
(`deposito.reconstruir_manifesto`). O diário é que não se mexe.

## Verificar

```bash
python3 tests/testes_servidor_portal.py      # 14 grupos, inclui o laço fechado
python3 ferramentas/ensaio_portal.py         # navegador de verdade, ponta a ponta
```

O ensaio compila o portal apontando para um servidor em modo ensaio, preenche
as sete etapas num Chromium, anexa cinco PDFs, envia, lê o protocolo na tela e
manda o motor conferir a entrega. É o que pega o que nenhuma suíte pega: o
navegador mandando um nome de campo que o servidor não espera.

## Banco de consulta e a trava de região

O diário append-only continua sendo a verdade. O Postgres é camada de
**consulta**, derivada e reconstruível.

```bash
# o isolamento entre entidades, exercitado de verdade:
PROTOCOL_DATABASE_URL='postgresql://...sa-east-1...' python3 tests/testes_banco.py
```

Sem `PROTOCOL_DATABASE_URL` a parte de RLS é **pulada**, e o resumo diz isso.

**Entidade real só é atendida em região brasileira.** Declare
`PROTOCOL_REGIAO` (`sa-east-1`, `southamerica-east1`, `brazilsouth`, `gru`,
`br`). Sem isso, qualquer entidade sem o prefixo `demo-` recebe 503 com o
motivo. É trava de código, não de procedimento.

**A aplicação nunca consulta como superusuário.** `banco.sessao` faz
`SET LOCAL ROLE protocol_app` antes de qualquer consulta, porque superusuário
ignora RLS por completo — inclusive com `FORCE ROW LEVEL SECURITY` — e a URL
padrão da Supabase conecta como `postgres`, que é privilegiado.
