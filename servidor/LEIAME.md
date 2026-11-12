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

**Para pôr no ar de verdade** — serviço, TLS, cópia diária, banco — o passo
a passo é `implantacao/LEIAME.md`, e ele começa dizendo o que foi conferido
e o que não foi.

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
| `PROTOCOL_EMAIL_DE_QUEM_OPERA` | para onde vai o aviso de que a planilha de um sindicato deixou **pedido esperando** (troca de e-mail, entrada com e-mail repetido). Vazio não impede subir: avisa na subida, e a tarefa `pedidos` passa a falhar enquanto houver pedido — é assim que aparece em `/saude`. Endereço torto impede subir |
| `PROTOCOL_PORTAL_ESTATICO` | a pasta do portal compilado, para o **servidor** entregar as páginas no mesmo endereço da API — um webapp num serviço só. Compile com `VITE_API=/`. Vazio, quem entrega as páginas é o proxy da frente |
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

## O sindicato envia a base pelo painel

```
POST /api/entidade/{apelido}/planilha                   CSV ou .xlsx
POST /api/entidade/{apelido}/documentos-do-sindicato    PDFs, ou um .zip
```

**Em duas etapas.** Sem o campo `confirmar`, o servidor só lê e devolve o
que o arquivo traz — nada é gravado. Com `confirmar` igual ao `sha256` que a
prévia devolveu, grava; se o arquivo for outro, 409.

O miolo é `servidor/ingestao.py`, o **mesmo** de `ferramentas/ingerir_acervo.py`
e `ferramentas/ingerir_documentos.py`: as ferramentas continuam existindo,
para volumes que não cabem num envio pela web (o teto é o do pacote, 60 MB)
e para quem opera.

### A planilha liga o acesso — com uma trava

A planilha confirmada também decide **quem consegue entrar no portal**
(`filiados.csv`), e a regra tem dois lados:

| quem | o que a planilha faz |
|---|---|
| **novo no acesso**, com e-mail que sirva **e só dele** | entra na hora: o código vai para o e-mail da planilha |
| novo, com um e-mail que **outra pessoa usa** | **não entra.** A entrada fica *pedida*, no mesmo arquivo, até quem opera conferir |
| novo, num **domínio fora dos provedores comuns** que já passou de 3 pessoas | **não entra.** Pedida do mesmo jeito, com o motivo |
| **já entra**, e a planilha traz outro e-mail | **nada muda.** A troca fica *pedida* em `trocas_de_email.jsonl`, e o código continua indo para o e-mail de antes |
| já entra, e não está na planilha | continua entrando. A planilha **não tira** ninguém |
| novo, sem e-mail que sirva | entra na base, não no acesso |
| novo, com dois e-mails diferentes na planilha | nenhum é escolhido |
| pediu apagamento | não volta, nem à base nem ao acesso |

**Por que a trava.** O portão só é portão porque o e-mail não é escolhido
por quem entra. Se a planilha trocasse o e-mail de quem já entra, uma conta
de gestor comprometida virava todas as contas do sindicato: troca o e-mail,
pede o código, entra no lugar da pessoa. "Já entra" olha os **dois** róis —
o CPF de um gestor não vira "novo" por não estar em `filiados.csv`. E a
planilha não tira ninguém porque tirar e recolocar seria a porta dos fundos
da mesma troca.

**Um e-mail, uma pessoa — para quem é novo.** "Outra pessoa usa" quer dizer:
o e-mail já é de alguém no portão (filiado ou gestor), ou de outra pessoa
nova da mesma planilha, ou de uma entrada que ainda espera. Olhar só para
dentro da planilha não bastaria: uma pessoa por envio, e cada uma seria a
única do arquivo dela. Quando duas novas dividem o endereço, **nenhuma**
entra — escolher a dona seria resolver a divergência sozinho. Casal que
divide e-mail cai aqui e depende de aprovação; quem volta na planilha com
um e-mail só dela entra na hora, e o pedido some.

**"O mesmo e-mail" é a mesma CAIXA, não o mesmo texto.** `joana+1@x` e
`joana+2@x` caem no mesmo lugar (o que vem depois do `+` é etiqueta), e no
Gmail o ponto também não distingue. Comparando o texto, uma caixa só
recebia o código de quantas pessoas novas se quisesse, sem comprar domínio
nem criar conta (`rol.caixa`).

**E um domínio fora dos provedores comuns tem limite.** Quem controla um
domínio escreve um endereço diferente por pessoa, todos na mesma caixa.
Então, fora de `rol.PROVEDORES_COMUNS` (Gmail, Outlook, UOL…), um domínio
só recebe **3** pessoas no acesso sem conferência
(`rol.LIMITE_POR_DOMINIO`); passou disso, **nenhuma** das novas daquele
domínio entra. A conta inclui quem já entra e quem espera, e é pelo domínio
registrável — `a.exemplo.com.br` e `b.exemplo.com.br` são do mesmo dono —,
para que nem uma pessoa por envio nem um subdomínio por pessoa contornem.

O domínio da repartição ou da cooperativa tem centenas de filiados e é
legítimo. Quem diz isso é quem opera, **uma vez por sindicato**:

```bash
python3 ferramentas/trocas_de_email.py --raiz dados_portal --entidade sind-df confiar reparticao.gov.br
```

Isso grava o domínio em `<entidade>/dominios_confiados.txt`, põe no acesso
quem esperava **por causa do domínio** (quem divide a mesma caixa continua
esperando) e faz as próximas planilhas não segurarem mais ninguém dali.
`listar` mostra o comando pronto para cada domínio que está segurando gente.

Três coisas que são botão ou heurística, e não medição: o **3**; a lista de
provedores comuns, escrita à mão; e o corte do domínio registrável, feito
sem a lista pública de sufixos. As três erram para o lado de SEGURAR.

**Quem decide a troca e a entrada segurada é quem opera o servidor**, depois
de conferir por fora. `listar` mostra, para cada entrada segurada, de quem
mais é o e-mail:

```bash
python3 ferramentas/trocas_de_email.py --raiz dados_portal --entidade sind-df listar
```

```bash
python3 ferramentas/trocas_de_email.py --raiz dados_portal --entidade sind-df aprovar 11144477735
```

```bash
python3 ferramentas/trocas_de_email.py --raiz dados_portal --entidade sind-df recusar 11144477735
```

Não existe rota para aprovar, de propósito — e `tests/testes_repositorio.py`
falha se aparecer uma. A recusa fica guardada: a mesma planilha, reenviada,
não recria o pedido.

**Como ficamos sabendo de um pedido.** Por e-mail, em
`PROTOCOL_EMAIL_DE_QUEM_OPERA`, em dois momentos:

- **na hora**, quando a planilha confirmada cria um pedido novo. Reenviar a
  mesma planilha não avisa de novo;
- **todo dia**, pela tarefa `pedidos` do agendador
  (`ferramentas/avisar_pedidos.py`), enquanto houver pedido esperando. É o
  que cobre o e-mail da hora que se perdeu.

O e-mail traz **só contagens** — quantas trocas, quantas entradas, desde
quando, em qual sindicato — e o comando para olhar. Nunca CPF nem e-mail de
filiado: a caixa de quem opera não é o banco. Se o correio falhar na hora, a
planilha do sindicato entra do mesmo jeito. Sem endereço configurado e com
pedido esperando, a tarefa `pedidos` **falha**, e a falha aparece em
`/saude`. A linha `TROCA DE E-MAIL pedida ent=…` continua no log.

**O dono do e-mail de antes também fica sabendo.** Quando a planilha pede a
troca, quem HOJE recebe o código recebe uma mensagem, em nome do sindicato:
pediram a troca, ela ainda não vale, e — se não foi a pessoa — é para avisar
o sindicato. É a única pessoa que sabe se pediu.

- vai para o e-mail que o **portão tem hoje**, nunca para o pedido;
- **uma vez** por pessoa e endereço pedido — nem a planilha reenviada nem o
  lembrete diário repetem, e retirar e pedir de novo o mesmo não conta;
- **sem link**, sem CPF, e com o e-mail pedido **mascarado**
  (`in•••@exemplo.org`): a caixa antiga pode não ser mais dela;
- se o correio falhar, a planilha entra e a tarefa `pedidos` **tenta de novo
  todo dia**, até sair — só o que saiu fica registrado;
- não depende de `PROTOCOL_EMAIL_DE_QUEM_OPERA` estar definida.

`trocas_de_email.py listar` mostra, em cada troca, se o dono já foi avisado.
O texto da mensagem está em `servidor/trocas.py`, `mensagem_para_o_dono`.

`ferramentas/ingerir_acervo.py` segue a mesma regra, porque chama a mesma
função: rodada por nós, ela também só *pede* a troca.

**O que a trava NÃO cobre** (T27 em `CHECKPOINTS.md`): muitos domínios,
poucas pessoas em cada. Tomar N contas de gente nova passa a custar N/3
domínios registrados — deixa de ser grátis, não deixa de ser possível. E
contas criadas uma a uma num provedor comum passam: ali cada endereço é uma
conta que alguém teve de abrir.

### Quem grava dado de pessoa não atravessa o apagamento

O apagamento a pedido e tudo o que grava dado de uma pessoa — a planilha,
os documentos do sindicato, o cadastro do filiado, a leitura do gestor —
seguram a mesma trava (`.apagamento.trava`, na pasta da entidade), e cada
gravação **confere de novo, na hora de gravar**, se a pessoa ainda pode ser
gravada. Antes, um apagamento que chegasse no meio de uma dessas operações
era desfeito por ela. Para medir de novo:

```bash
PROTOCOL_DATABASE_URL='postgresql://...' python3 docs/medicoes/2026-11-12-apagamento-no-meio.py
```

As três tarefas agendadas seguem a mesma regra. `avisar` e `reavaliar`
conferem cada pessoa de novo, uma a uma, antes de mandar o e-mail ou guardar
o veredicto (`apagamento.se_ainda_esta`); `coletar` relê a lista de
processos na hora de gravar. Quando alguém sai no meio da rodada, a saída
da tarefa diz **quantas** pessoas foram puladas — nunca quem.

```bash
PROTOCOL_DATABASE_URL='postgresql://...' python3 docs/medicoes/2026-11-12-apagamento-e-as-tarefas-agendadas.py
```

**O que a coleta acompanha:** só processo que alguém da base ainda tem
(`vinculo`). O processo de quem pediu para sair deixa de ser consultado no
tribunal; o coletivo continua enquanto sobrar um filiado nele. O NÚMERO do
processo continua na tabela `processo` — T29 em `CHECKPOINTS.md`.

## O atendimento ao filiado

```
POST /api/atendimento        {"pergunta": "em quais processos eu estou?"}
```

A conversa em que o filiado pergunta o que perguntaria por telefone: em que
processo estou, mudou alguma coisa, meus documentos chegaram, o que falta, o
que posso fazer.

**Não é um modelo de linguagem**, e não por falta de tempo: dado de filiado
não vai para modelo de linguagem (`CLAUDE.md`). O assunto é reconhecido
pelas palavras, numa lista fechada (`nucleo/atendimento.py`), e a resposta é
escrita com o que as rotas das telas devolvem — `meus-processos`,
`minhas-acoes`, `meu-cadastro`. **Ele não apura nada por conta própria**:
uma segunda apuração seria uma segunda resposta para a mesma pessoa.

- não aceita CPF: responde sobre quem abriu a sessão;
- "falta informação" é dito como falta; valor, ele diz que não calcula;
- o que não reconhece, diz que não entendeu — não chuta um assunto;
- a pergunta **não é guardada nem logada**: é texto livre. O log leva só o
  assunto reconhecido.

## A página de entrada, e o portal num endereço só

Sem `?entidade=` no endereço, o portal mostra a página de entrada: o que o
produto é, e um campo para o código (ou o link colado) do sindicato. Não há
lista de sindicatos para escolher — a lista de clientes não é pública. O
código é conferido com o servidor antes de sair da página.

Com `PROTOCOL_PORTAL_ESTATICO` o servidor entrega as páginas e a API juntos:

```bash
cd portal && VITE_API=/ npx vite build --outDir /srv/protocol/portal --emptyOutDir
```

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

### O rol de substituídos: o sindicato envia, pelo painel

O motor pergunta se a pessoa consta do rol da ação coletiva. Quem tem a
lista é o sindicato, que ajuizou.

```
GET  /api/entidade/{apelido}/rol-de-substituidos            as ações e o rol de cada uma, em contagens
POST /api/entidade/{apelido}/rol-de-substituidos            envia (duas etapas: a prévia não grava)
POST /api/entidade/{apelido}/rol-de-substituidos/retirar    desfaz o rol de uma ação
```

- o arquivo é planilha com coluna de CPF, ou PDF com texto. Rol só com nome
  não entra;
- o rol é de **uma** ação, e só ação do catálogo que a entidade contratou;
- quem não está na lista só é dado como fora se o gestor declarar que ela é
  o rol inteiro **e** a lista tiver sido lida inteira;
- o CPF de quem não é da base é contado e não fica guardado; quem entra na
  base depois do envio fica sem resposta até o reenvio;
- a autoridade é `<entidade>/rol_de_substituidos.jsonl`, uma linha por ato.
  Não há projeção no banco: as quatro superfícies leem o arquivo;
- a resposta é **declarada**, e o motor diz isso em nota.

As regras e o porquê de cada uma estão no cabeçalho de
`servidor/substituidos.py`. Não confundir com `rol.py`, que é o rol de quem
entra no portal.

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

Para o sindicato começar sozinho falta só dizer quem é gestor —
`dados_portal/<entidade>/gestores.csv`, mesmo formato do rol abaixo. Com
isso o gestor entra, envia a planilha pelo painel, e os filiados passam a
receber código. `filiados.csv` não precisa mais ser posto à mão.

## O rol de filiados

`dados_portal/<entidade>/filiados.csv`, criado pela primeira planilha que o
gestor confirmar (ou posto à mão):

```csv
cpf,email
526.018.159-06,fulano@exemplo.org
```

**Sem esse arquivo nenhum filiado recebe código**, e o servidor grita no
log. (O gestor recebe: é ele quem envia a lista que cria o arquivo.) O motivo está em `servidor/rol.py`: o código de acesso vai para o e-mail
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
    filiados.csv                     o rol: quem entra, e para onde vai o código
    gestores.csv                     quem abre o painel — posto por quem opera
    trocas_de_email.jsonl            trocas de e-mail pedidas pela planilha
    dominios_confiados.txt           domínios que quem opera confiou para este sindicato
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
