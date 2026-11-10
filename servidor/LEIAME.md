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
| `PROTOCOL_RAIZ` | onde moram os dados. Padrão `dados_portal`. **As duas, `dados/` e `dados_portal/`, estão no `.gitignore`** — e `tests/testes_repositorio.py` confere isso contra este padrão. Se você apontar a raiz para outro lugar, acrescente esse lugar ao `.gitignore` |
| `PROTOCOL_ORIGENS` | endereços do portal, separados por vírgula |
| `PROTOCOL_SMTP_*` | `HOST`, `PORTA`, `USUARIO`, `SENHA`, `REMETENTE` |
| `PROTOCOL_EMISSOES_POR_CPF_HORA` | padrão 3 |
| `PROTOCOL_EMISSOES_POR_ORIGEM_HORA` | padrão 20. **Suba** se o sindicato atende vários filiados do mesmo computador da sede |
| `PROTOCOL_PROXIES_CONFIAVEIS` | endereços, separados por vírgula, de quem este servidor aceita `X-Forwarded-For`. **Vazio por padrão, e vazio significa não acreditar no cabeçalho.** Se o servidor fica atrás de proxy reverso e isto não estiver preenchido, a contagem acima vale para todos juntos — e aí o portão fecha para a fila. Se estiver preenchido com o endereço errado, a contagem volta a ser escolhida por quem pede |
| `PROTOCOL_MODO_ENSAIO` | `1` dispensa segredo e devolve o código na resposta. Nunca com gente de verdade |

## Apagamento a pedido (LGPD art. 18, VI)

Quem aciona é o **sindicato**, pelo painel: no fim do painel do gestor há
"Atender um pedido de apagamento", recolhido por padrão, com confirmação em
duas etapas — não há desfazer, e a confirmação é a única chance. A tela pede
**quem no sindicato está atendendo**, e sem isso não apaga: o registro de
autor é obrigatório.

Por baixo:

```
POST /api/entidade/{apelido}/apagar
     { "cpf": "...", "motivo": "...", "pedido_por": "..." }
```

**O registro de quem mandou é gravado ANTES, de forma síncrona, e se ele não
entra nada é apagado** (503). Em leitura, falha de registro não derruba a
consulta; num ato irreversível, a mesma escolha significaria pessoa apagada
sem autor.

`motivo` e `pedido_por` têm **teto de 500 caracteres, e passar do teto é
recusado com 400, não cortado**: o registro de um apagamento precisa guardar
exatamente o que o gestor escreveu.

**A remoção no rol preserva o dialeto do arquivo** — codificação (latin-1 do
Excel brasileiro continua latin-1), terminador de linha e permissão. O rol é
arquivo do sindicato, não nosso: reescrevê-lo em utf-8 funcionava para nós e
fazia ele ver `JOSÃ‰` onde escreveu `JOSÉ`.

A resposta traz o que saiu de cada lugar e, no fim, **`vestigios`**. Lista
vazia significa que terminou; **lista não vazia não é erro, é a resposta
honesta de que sobrou coisa** — e aí se reexecuta.

Para retomar um apagamento interrompido, ou só conferir se um pedido foi
atendido:

```bash
python3 ferramentas/apagar_filiado.py --entidade sindicato-x --cpf ...     --motivo "pedido do titular" --pedido-por gestor@sindicato-x.org.br
```

```bash
python3 ferramentas/apagar_filiado.py --entidade sindicato-x --cpf ... --conferir
```

`--conferir` só mede, não apaga. As duas saem com código **1** se sobrou
vestígio, para servir dentro de script.

### Duas coisas que quem opera precisa saber

**`PROTOCOL_SEGREDO` é de vida longa.** O tombstone guarda HMAC do CPF com
esse segredo. Trocá-lo faz os tombstones existentes **deixarem de casar**
com os CPFs que chegam — e a ingestão volta a aceitar quem pediu para sair.
Trocar o segredo exige reemitir os tombstones.

**O rol é colocado à mão, e isso é um buraco declarado.** Nada no produto
escreve `filiados.csv` ou `gestores.csv`. Se o operador repuser o arquivo
com um CPF apagado, o nome e o e-mail voltam ao disco e nenhuma trava
impede. O que sobra: nenhum e-mail sai (o portão consulta o tombstone), e
`--conferir` **detecta** a linha reposta. No dia em que existir rota de
ingestão de rol, ela consulta o tombstone como as outras duas.

## Nome por nome, e a planilha da base

```
GET /api/entidade/{apelido}/pessoas        a lista, com o CPF mascarado
GET /api/entidade/{apelido}/pessoas.csv    a planilha, com o CPF inteiro
```

As duas só para gestor da própria entidade, e as duas saem do mesmo laço do
panorama. **A planilha é a maior saída de dado do produto**: o registro de
quem exportou é síncrono — sem ele, não exporta —, e o arquivo vem como
anexo, sem cache. Separador `;` e marca de UTF-8, que é como o Excel em
português abre; toda célula passa pela trava de fórmula.

## Scanner e foto: entram, e ficam aguardando leitura

Documento que **abre mas a máquina não lê** — página de scanner, foto de
celular — é ACEITO. O cadastro não cai. Três coisas acontecem:

- o **diário** registra quais arquivos daquele envio aguardam leitura
  (`aguardando_leitura`), e o banco projeta isso em `documento.tem_texto`;
- o **filiado** é avisado na hora e no recibo de que aquele documento vai
  ser lido por uma pessoa, e por isso demora mais;
- o **painel** do sindicato mostra quantos documentos esperam, e de quantas
  pessoas.

A foto (JPG, PNG) vira PDF **no navegador**, sem sair do aparelho. O servidor
continua recebendo só PDF.

O que continua recusado: arquivo que **não abre** — corrompido ou com senha.
Esse ninguém lê, e guardá-lo criaria uma fila que não anda.

### Quem lê: o sindicato, pelo painel

No painel do gestor aparece **"Documentos para ler"**. Ele abre o documento,
lê, e registra o que leu — ou que não deu para ler.

```
GET  /api/entidade/{apelido}/conferencia                  a fila
GET  /api/entidade/{apelido}/conferencia/{id}/arquivo     o PDF, para ler
POST /api/entidade/{apelido}/conferencia/{id}             registra a leitura
```

- o que o gestor registra **vira fato**, com o marcador dele como autor e
  `metodo = "pessoa"`. Só entram valores que existem;
- a autoridade é `<entidade>/leituras.jsonl`, append-only. O banco se refaz
  dele com `banco.projetar_leituras`;
- **abrir o documento é a leitura mais sensível do produto**: é onde o PDF
  de um filiado sai do servidor. Só gestor da própria entidade, só documento
  da fila dela, registrado em `leitura`, com `Cache-Control: no-store`;
- o que nem uma pessoa conseguiu ler sai da fila e aparece em "peça de
  novo", com o nome de quem mandou.

**O reenvio substitui.** Quando a pessoa manda de novo, o que ela tinha
mandado antes sai do banco — documento e fatos lidos dele. O que o sindicato
entregou sobre a mesma pessoa fica.

## O veredicto guardado, e a prova de por que mudou

A tabela `oportunidade` guarda o que o motor respondeu para cada pessoa, com
a **origem**: a assinatura que o catálogo DECLARA (`slug@2 outro@1`) e a
impressão digital MEDIDA do conteúdo dos arquivos.

```bash
python3 ferramentas/reavaliar_oportunidades.py --entidade sindicato-x
```

Roda sozinha também: é a tarefa **`reavaliar`** do agendador, a última da
rodada. A ferramenta nunca imprime CPF — quem precisa saber de quem é cada
mudança abre o painel, com sessão de gestor.

**APPEND-ONLY POR ASSINATURA.** Reavaliar sob catálogo novo INSERE em vez de
sobrescrever, e é isso que faz a transição existir: o veredicto antigo **não
é recalculável**, porque o catálogo que o produziu pode já ter sido editado
em disco.

**CONTEÚDO MUDADO SEM SUBIR A `versao` É RECUSADO** (código de saída 3). Se
já existe veredicto gravado com aquela assinatura e OUTRA impressão, alguém
editou o TOML e esqueceu de subir a versão — e aí a linha guardada citaria
uma origem que não produziu aquele resultado. Prova falsa é pior que prova
nenhuma, porque ninguém desconfia dela.

**NADA É AVISADO A NINGUÉM.** Esta parte registra e mostra ao sindicato; não
manda e-mail. Quem fala com o filiado é o sindicato, e a decisão de avisar é
dele — com advogado, não com agendador.

### Uma coisa que o painel diz e que não é "zero"

Sem banco, o painel mostra **"não temos como saber o que mudou"**, e não
"nada mudou". São respostas diferentes: a segunda é o relatório
tranquilizador que faz ninguém perceber.

## Migrar um banco que já existe

`esquema.sql` é a forma de agora, e `CREATE TABLE IF NOT EXISTS` **não
altera tabela existente**. Banco que já está no ar precisa da migração
datada:

```bash
psql "$PROTOCOL_DATABASE_URL" -f servidor/migracoes/<arquivo>.sql
```

`servidor/migracoes/LEIA.md` tem a lista e diz quais já foram aplicadas.
**Suíte verde não quer dizer que o banco de produção foi migrado** — a suíte
roda com `recriar=True`, que derruba e recria, então ela nunca exercita a
migração contra um banco antigo.

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

### Uma regra do `manifesto.csv` que quem lê por programa precisa saber

O manifesto é feito para ser **aberto por gente, no Excel**. Célula que
começa com `=`, `+`, `-`, `@`, tabulação ou retorno de carro é tratada como
**fórmula** por Excel, LibreOffice e Google Sheets — então um filiado que
digitasse `=HYPERLINK(...)` no nome tinha aquilo executado na máquina de
quem abrisse o arquivo. E quem abre é o gestor do sindicato, que confia no
arquivo porque fomos nós que o geramos.

Por isso, no manifesto, **célula que começa com um desses caracteres sai com
um apóstrofo na frente** (`'=HYPERLINK(...)`). Nada é apagado: o texto da
pessoa continua inteiro e visível, inclusive para o gestor, que é quem
precisa ver o que ela escreveu.

Quem consome o manifesto por programa deve remover um apóstrofo inicial
quando ele existir. O **diário** (`recebidos.jsonl`) não tem essa
transformação: ele guarda o que chegou, exatamente, e é a autoridade.

## Verificar

```bash
python3 tests/testes_servidor_portal.py      # 56 grupos, inclui o laço fechado
```

```bash
python3 ferramentas/ensaio_portal.py                       # Chromium de verdade
PROTOCOL_DATABASE_URL='postgresql://...' python3 ferramentas/ensaio_portal.py
```

O ensaio **roda sozinho no fim de `tests/rodar_todos.py`**, e custa cerca de
12 segundos. `PROTOCOL_SEM_ENSAIO=1` o pula, e o pulo aparece na saída.

O que ele faz: semeia uma entidade de demonstração num diretório
temporário, gera cinco PDFs com camada de texto, compila o portal apontando
para um servidor em modo ensaio, sobe os dois, e dirige um Chromium — a tela
de início, o portão lendo o código **na tela**, as seis etapas, os cinco
anexos, o envio, o protocolo lido na tela. Depois **confere o disco de fora
do navegador**: o diário campo por campo, os cinco PDFs na entrega, o
manifesto. Com banco, segue como gestor e apaga o filiado **pelo painel**,
exigindo que a confirmação avise que não se desfaz, e mede que não sobrou
nada — e que quem **não** pediu para sair continua lá.

**O que só ele pega.** Os testes do servidor provam o que ele ACEITA; os do
portal provam o que a tela DIZ. Nenhum dos dois roda React num navegador
contra o servidor, e entre eles mora uma classe de defeito que não dá erro:
o campo da tela escrevendo no lugar errado do rascunho chega ao disco como
**campo vazio**, e a tela continua dizendo "enviado". Medido: trocando
`onCarreira("cargo", v)` por `onCarreira("unidade", v)` em
`portal/src/etapas/Carreira.tsx`, as 424 verificações de Python, os 89 testes
do portal e o `tsc` continuam todos verdes — e o ensaio cai.

**Este arquivo já prometeu este ensaio antes de ele existir.** Até
02/11/2026 havia aqui a mesma linha de comando e a mesma descrição, e o
arquivo não existia em commit nenhum. Estava escrito, então passava por
verificado — a doença que a auditoria encontrou sete vezes nos comentários
do código, um andar acima. É por isso que ele agora roda dentro de
`rodar_todos.py`: verificação que ninguém roda é o mesmo que verificação que
não existe.

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
