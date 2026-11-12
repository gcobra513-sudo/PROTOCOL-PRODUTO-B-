# Auditoria do produto — 10/11/2026

> A pergunta não foi "o código faz o que diz?" — isso a suíte responde, e ela
> está verde (442 grupos em Python, 94 testes no portal, ensaio de navegador
> inteiro). A pergunta foi **"o produto faz a frase dele?"**:
>
> *O sindicato manda a lista de filiados. O filiado manda os documentos dele.
> Nós dizemos, nome por nome: o que ele pode executar, o que pode ajuizar, e
> quanto.*
>
> Verde não responde isso, porque o que não existe não tem teste. Então esta
> auditoria mede o que NÃO está escrito. Os três experimentos estão em
> `docs/medicoes/` e rodam de novo:
>
> ```bash
> PROTOCOL_DATABASE_URL='postgresql://...' python3 docs/medicoes/2026-11-10-tres-superficies.py
> python3 docs/medicoes/2026-11-10-o-que-da-pode.py
> PROTOCOL_DATABASE_URL='postgresql://...' python3 docs/medicoes/2026-11-10-scanner-e-foto.py
> ```

## As respostas, em uma tabela

| Pergunta | Resposta |
|---|---|
| Recebe documentos do **filiado**? | Sim, mas só PDF com camada de texto. Scanner e foto são recusados |
| Recebe documentos do **sindicato**? | **Não pelo web app.** Só por linha de comando, operada por nós |
| Devolve a **organização dos dados**? | Em parte: painel com totais. Sem lista por pessoa, sem exportação |
| Diz o que pode **ajuizar ou executar**? | **Não.** Hoje não consegue dizer `PODE` por nenhum caminho |
| **Tratamento** dos dados correto? | A base técnica sim; três furos (itens 7 e 8) |
| **Armazenamento** correto? | O desenho sim; nada está no ar (item 6) |

## Os achados, na ordem de ataque

### 1. O produto não consegue dizer `PODE`, nem depois da homologação

**Medido** (`2026-11-10-o-que-da-pode.py`), com TUDO homologado em memória:

```
A) O MELHOR que o produto consegue montar hoje (sentença lida, respostas da pessoa):
   executar  GIFA-2006    FALTA     o rol de substituídos da ação coletiva
   ajuizar   STJ-T1410    FALTA     o julgamento do STJ, Tema 1.410; os critérios objetivos…

B) O mesmo, mais no_rol=True — fato que NENHUM caminho do produto preenche:
   executar  GIFA-2006    PODE
```

`grep -rn "no_rol="` em `nucleo/`, `servidor/` e `ferramentas/` não acha
nenhum lugar que grave esse fato: ele é `None` para toda pessoa, em todo
caminho. E o motor exige sabê-lo mesmo quando a ação declara
`exige_rol = false`, por causa do Tema 1.302.

**Falta:** a porta de entrada do rol de substituídos (código) e a regra para
ação SEM rol (jurídico).

**E HÁ UMA SEGUNDA TRAVA, medida no mesmo arquivo (caso C).** Mesmo com
`no_rol=True`, numa coletiva que o catálogo já registra como
`transitado_em_julgado`, quem não enviou sentença recebe:

```
C) No rol de coletiva TRANSITADA, sem sentença própria enviada:
   executar  GIFA-2006    FALTA     [VOCE] a sentença e a certidão de trânsito em julgado
```

O motor cobra DA PESSOA o título da AÇÃO. O portal pede esse documento como
"Sentença, se você tiver" — e quem é substituído numa coletiva normalmente
não tem: a sentença é uma só, a mesma para todos, e quem a tem é o
sindicato. Do jeito que está, cada filiado teria de enviar a cópia da
sentença coletiva para chegar a `PODE`. Se o título de uma coletiva deve
entrar UMA vez, pela ação, é pergunta para o jurídico — mas ela decide se o
produto destrava a base inteira ou uma pessoa por vez.

**ISTO CORRIGE UMA AFIRMAÇÃO MINHA.** Na entrega do veredicto guardado eu
escrevi — na spec, no `CHECKPOINTS.md`, na ferramenta e no commit — que "a
primeira transição de verdade vai ser a própria homologação: `FALTA → PODE`".
Não medi, e está errado: a homologação sozinha produz **zero** `PODE`. A
afirmação foi corrigida nos três lugares vivos; o commit fica como está, e
este parágrafo é o registro.

### 2. O painel e o veredicto guardado ignoravam os documentos já lidos

**Medido** (`2026-11-10-tres-superficies.py`), a MESMA pessoa nas três
superfícies, com a sentença lida na chegada do cadastro:

| superfície | o que falta para EXECUTAR |
|---|---|
| filiado (`/api/minhas-acoes`) | o rol |
| painel do sindicato (`/panorama`) | o rol **+ "a leitura da sentença já entregue"** |
| veredicto guardado (`oportunidade`) | o rol **+ "a leitura da sentença já entregue"** |

A sentença JÁ tinha sido lida. Três lugares chamam o motor e só um lia
documento: os outros dois usavam `panorama.fatos_do_cadastro`, que fixa
`tem_titulo=None`. O sindicato via como pendência um trabalho já feito — e,
no dia em que o item 1 for resolvido, veria `FALTA` onde o filiado vê `PODE`.

**Corrigido nesta mesma entrega** — ver a seção no fim.

### 3. Scanner e foto derrubam o cadastro inteiro

**Medido** (`2026-11-10-scanner-e-foto.py`), pelo HTTP de verdade:

```
contribuição ESCANEADA (PDF só imagem)   -> 422  "não tem texto selecionável… digitalize com OCR"
contribuição ok + SENTENÇA escaneada     -> 422  (o cadastro inteiro cai por um anexo opcional)
contribuição em FOTO (jpg)               -> 422  "arquivo fora do contrato"
```

A base é de aposentados com papel físico. E a justificativa escrita no código
é do **Produto A**: `validacao.py` diz que `ferramentas/conferir_entrega.py`
"REPROVA documento sem camada de texto" — ferramenta que nem existe neste
repositório. No A, sem texto não há petição; no B, um documento ilegível por
máquina pode esperar leitura humana. É a pergunta da Regra Zero: *"o B
precisa mesmo disso, ou estou carregando a hipótese do A junto?"*

**Proposta:** aceitar, guardar e marcar "aguardando leitura" (dono:
conferência). OCR local, no Brasil, depois.

### 4. O sindicato não tem porta de entrada

De 11 rotas HTTP, **uma** é upload: `POST /api/cadastro`, a do filiado.
Planilha (`ingerir_acervo.py`), documentos (`ingerir_documentos.py`), rol de
filiados e de gestores (arquivo posto à mão) e a criação da entidade
(trecho de Python) exigem alguém com acesso ao servidor. Serve a um piloto
assistido; não é "o sindicato manda a lista" como serviço.

### 5. Não há "nome por nome" para o sindicato

O painel devolve totais, até 8 nomes de exemplo por pendência (a tela mostra
3) e 50 inalcançáveis. Não há lista de pessoas com a situação de cada uma, e
`grep` por `FileResponse`, `text/csv` ou `Content-Disposition` em
`servidor/app.py` volta vazio: nenhuma exportação.

### 6. Nada está no ar

- nenhum artefato de implantação no repositório — Dockerfile, serviço,
  proxy, TLS, CI;
- a hospedagem decidida (Lightsail + Supabase Pro) não foi contratada, e sem
  ela não há backup do disco onde mora o diário, que é a AUTORIDADE;
- o banco pausou por inatividade em 03/11 — sinal de plano gratuito, que
  `docs/hospedagem.md` eliminou exatamente por isso. Com o banco pausado o
  portão falha fechado: ninguém recebe código;
- a migração `servidor/migracoes/2026-11-03-…sql` continua pendente em São
  Paulo;
- a confirmar quando houver acesso: se a aplicação conecta como
  `protocol_app` com senha própria (`BANCO.md` registra isso como pendência).

### 7. O rascunho vaza entre pessoas no computador compartilhado

**Lido no código, NÃO ensaiado no navegador.** A chave do rascunho é única
(`sindilote.portal.rascunho.v1`, em `portal/src/lib/armazenamento.ts`), não
por CPF, e `App.tsx` a restaura na montagem, antes do portão. Quem abandona o
cadastro no computador da sede deixa nome, CPF, e-mail e processos para o
próximo. E o `LEIAME.md` do servidor prevê exatamente esse uso: *"o sindicato
atende vários filiados do mesmo computador da sede"*.

### 8. Jurídico

- **T16** — o aviso de privacidade que o filiado lê descreve o Produto A;
- **T5** — não há prazo de retenção: nada apaga por tempo.

### 9. Nunca vimos documento real

O leitor de sentença e a ingestão de planilha foram construídos contra
exemplos escritos por mim (T4). O acerto em documento de verdade é
desconhecido — não baixo, não alto: **não medido**.

### 10. A trilha AJUIZAR não tem conteúdo

Um único entendimento na trilha (`STJ-T1410`), pendente de julgamento e sem
critérios objetivos preenchidos. Depende de pesquisa jurídica (T2, T6).

## Achados menores, anotados

- o `LEIAME.md` do servidor abre dizendo que ele "grava a entrega que o
  **motor de lote** consome" — vocabulário e desenho do A; e cinco arquivos
  citam `ferramentas/conferir_entrega.py`, que não existe aqui;
- a chave do rascunho se chama `sindilote` — "lote" é vocabulário do A;
- enviar o cadastro gasta a sessão: para ver "de quais ações participo" logo
  depois, a pessoa pede outro código, contra um limite de 3 por hora.

## O que está sólido

Isolamento entre sindicatos imposto pelo banco; portão sem senha, com o
e-mail vindo do sindicato; apagamento que mede o que sobrou; diário como
autoridade; cada fato extraído carrega o trecho de origem; a carga do
catálogo RECUSA homologação sem a tese transcrita (medido — ela recusou a
minha, nesta auditoria); permissões de disco 0700/0600; região brasileira
escolhida para banco e e-mail.

## O item 2, fechado em 10/11/2026

A mesma medição, depois:

| superfície | o que falta para EXECUTAR |
|---|---|
| filiado (`/api/minhas-acoes`) | o rol |
| painel do sindicato (`/panorama`) | o rol — e `leu_documentos = true` |
| veredicto guardado (`oportunidade`) | o rol |

O que mudou:

- a regra do título (`titulo_de`) desceu de `servidor/documentos.py` para
  `nucleo/leitura.py`, onde o painel e a reavaliação a alcançam;
- passou a existir **um** construtor de fatos, `panorama.fatos_do_cadastro`,
  que recebe o que os documentos disseram. O antigo
  (`documentos.fatos_para_o_motor`) delega a ele;
- `banco.fatos_lidos_da_entidade` traz os achados da entidade inteira numa
  consulta — o painel custa 13 comandos SQL com 2 pessoas e 13 com 9.

E três guardas, cada uma provada com o defeito de volta:

| teste | o que pega |
|---|---|
| `teste_as_tres_superficies_dizem_o_mesmo_sobre_a_mesma_pessoa` | a divergência, depois que existe |
| `t_ha_um_so_lugar_que_monta_os_fatos_de_uma_pessoa` | um segundo construtor, antes de divergir |
| `teste_ler_os_documentos_nao_faz_o_painel_custar_por_pessoa` | uma consulta por pessoa (mutante: 16 comandos com 2, 37 com 9) |

O texto do painel que afirmava "nenhum documento foi lido" passou a dizer a
verdade nos dois estados.

## O item 3, fechado em 10/11/2026 — "aceita e marca como aguardando leitura"

A mesma medição, depois:

```
contribuição ESCANEADA (PDF só imagem)   -> 200
contribuição ok + SENTENÇA escaneada     -> 200
contribuição em FOTO (jpg), direto à API -> 422  (de propósito — ver abaixo)
```

O que mudou:

- **são duas perguntas, e eram uma.** `validacao.examinar_pdf` separa "abre?"
  de "tem texto?". O que não abre (corrompido, com senha) continua recusado:
  esse ninguém lê. O que abre sem texto ENTRA;
- **a marca mora no DIÁRIO** (`aguardando_leitura`, por registro), porque o
  banco é projeção e uma marca só nele sumiria na primeira recuperação;
- **`documento.tem_texto` passou a dizer a verdade.** A coluna existia e
  ficava em `false` para TODO documento, legível ou não — só não fazia
  estrago porque ninguém a lia;
- **a foto vira PDF no navegador** (`portal/src/lib/foto.ts`), sem sair do
  aparelho e sem biblioteca. O servidor continua recebendo só PDF, e por
  isso o JPG mandado direto à API segue recusado: o contrato de nomes de
  arquivo, que impede nome de cliente de virar caminho, não foi aberto;
- o filiado é AVISADO, na hora e no recibo, de que aquele documento vai ser
  lido por uma pessoa e demora mais; o painel do sindicato mostra quantos
  documentos esperam, e de quantas pessoas.

A prova de ponta a ponta é o ensaio de navegador, que passou a mandar os
três jeitos — PDF com texto, PDF de scanner e uma foto JPG de verdade — e
confere no disco que a foto chegou como um PDF que ABRE. Desligando a
conversão no portal, o ensaio cai.

**Um defeito que esta mudança criaria, pego antes:** `ingerir_documentos.py`
também gravava `documento` sem `tem_texto`. No dia em que o painel passou a
contar a fila por essa coluna, todo documento do sindicato apareceria como
aguardando leitura. E a primeira correção que pensei — "se casou com alguém,
foi lido" — era falsa: a ferramenta casa também pelo CPF no NOME do arquivo.
Agora mede, documento por documento.

### O que NÃO foi feito, e é a próxima dívida (T24)

**A fila tem entrada e contador, e não tem saída.** Não existe tela para uma
pessoa REGISTRAR o que leu num documento de imagem — o dispositivo, o
trânsito, o período. Enquanto isso não existir, a resposta de quem mandou
foto fica em `FALTA: a leitura da sentença já entregue`, para sempre. O
painel diz isso sem prometer fluxo ("a resposta fica incompleta"), e a frase
tem teste para não dizer "em análise".

## T24, fechado em 10/11/2026 — a fila de leitura ganhou saída

Decisão: **quem lê é o sindicato, pelo painel dele.**

O gestor vê "Documentos para ler", ABRE o documento, e registra uma de duas
coisas: o que leu, nos poucos campos que o motor usa (o dispositivo da
sentença, a data do trânsito, o período do comprovante), ou que não deu para
ler — e aí o documento vai para a lista de a quem pedir de novo.

- o que ele registra vira FATO, com `metodo = "pessoa"` e o marcador dele
  como autor; só entram valores que existem (dispositivo é um de quatro,
  data de verdade e não futura);
- a autoridade é um arquivo append-only, `leituras.jsonl`: a leitura humana
  não é derivável de nada, e o banco se refaz dele
  (`banco.projetar_leituras`);
- abrir o documento é a leitura mais sensível do produto — é onde o PDF de um
  filiado sai do servidor. Só gestor da própria entidade, só documento da
  fila dela, registrado em `leitura`, e `no-store`;
- o arquivo de leituras guarda CPF e o que a sentença diz: sai no apagamento
  a pedido. A varredura de bytes de `vestigios` o achou SOZINHA antes de eu
  ensinar o `apagar` a limpá-lo — a rede fazendo o trabalho dela num lugar
  criado no mesmo dia.

Provado de ponta a ponta pelo ensaio de navegador, que ganhou a fase do
meio: o filiado manda foto e scanner, o gestor abre a sentença, registra as
duas leituras, a fila esvazia, e o apagamento não deixa nada.

**Dois defeitos antigos achados no caminho, e corrigidos:**

1. **O reenvio não substituía.** A pessoa mandava a sentença fotografada e
   depois reenviava a original: a linha da antiga ficava em `documento` — a
   fila contava um documento que não estava mais na entrega — e os fatos
   lidos dela ficavam em `achado`, alimentando o motor com sentença
   substituída. Agora o reenvio tira o que veio do CADASTRO, e só isso: o
   que o sindicato entregou sobre a mesma pessoa não é dela para substituir
   (`documento.origem`).
2. **Dois reenvios no mesmo segundo quebravam o depósito**, DEPOIS de o
   diário já ter gravado: a pasta de histórico era nomeada só pelo segundo.
   Achado por um teste que reenviava três vezes seguidas.

### A pergunta que isto abre, e não é de código (T25)

**O fato que o gestor digita entra como CERTO e alimenta o motor.** Hoje
isso não chega a `PODE` — falta o rol (item 1). No dia em que o rol existir,
"procedente" e uma data de trânsito digitados por um gestor, que não é
advogado, bastam para o motor dizer `PODE executar` sobre aquela pessoa. A
regra da casa é "o software prepara; quem assina é advogado". Se a leitura
feita pelo sindicato precisa de um visto de advogado antes de valer para
`PODE`, é decisão do jurídico — e o lugar para o visto já existe: a coluna
`achado.conferido` e o `metodo = "pessoa"` distinguem esses fatos de todos
os outros.

## O item 5, fechado em 10/11/2026 — nome por nome, e a planilha

O painel ganhou a lista: cada pessoa da base, o que ela já pode, e de quem
depende o resto — com busca pelo nome (sem exigir acento) e filtro por dono
da pendência. E a exportação: `GET /api/entidade/{apelido}/pessoas.csv`.

- **a lista sai do MESMO laço do panorama** (`panorama.por_pessoa`). É a
  quarta superfície que responde sobre uma pessoa, e há teste exigindo que
  diga o mesmo que a tela do filiado;
- **na tela o CPF vem mascarado; na planilha, inteiro** — é por ele que o
  sindicato casa a lista com os registros dele. Por isso a exportação é a
  maior saída de dado do produto, e o registro de QUEM exportou é síncrono:
  sem registro, não sai arquivo;
- o dialeto é o do Excel em português (`;` e marca de UTF-8), e toda célula
  passa pela trava de fórmula — o nome vem do filiado;
- a lista custa 10 comandos SQL com 2 pessoas e 10 com 9.

**Um vazamento pequeno achado lendo o laço:** `nome = fatos.nome or cpf`.
Quem não tinha nome na base aparecia nos exemplos de cada pendência, no
painel, pelo CPF em claro. Corrigido, com teste.

O ensaio de navegador confere a planilha como o navegador a BAIXOU.

## O item 4, fechado em parte em 10/11/2026 — a porta de entrada do sindicato

O painel do gestor ganhou "Enviar a base do sindicato":

```
POST /api/entidade/{apelido}/planilha                   CSV ou .xlsx
POST /api/entidade/{apelido}/documentos-do-sindicato    PDFs, ou um .zip
```

- **em duas etapas, e a primeira não grava nada.** O servidor LÊ e devolve o
  que o arquivo traz — quantas pessoas, quantas o sindicato não alcança,
  quantas pediram apagamento; quantos documentos acharam o dono e quais
  sobraram, com o motivo. A confirmação leva a impressão digital do arquivo
  conferido, e é recusada (409) se o arquivo for outro;
- **o miolo é o MESMO da linha de comando.** Ele desceu das duas
  ferramentas para `servidor/ingestao.py`, e a ferramenta e a rota chamam as
  mesmas funções. As travas vieram junto sem serem reescritas: quem pediu
  para sair não volta pela planilha, e sem conseguir ler os tombstones nada
  é gravado;
- **a planilha entra em .xlsx**, que é o que o sindicato tem. A mesma
  planilha suja de teste, em CSV e em .xlsx, dá as mesmas pessoas, campos e
  achados. Um .xlsx é um zip: o tamanho declarado é somado antes de abrir;
- a ingestão pela web registra QUEM enviou, no próprio arquivo de acervo.

O ensaio de navegador confere: o gestor envia uma planilha .xlsx, a pessoa
não aparece na base antes da confirmação, aparece depois, e está na
planilha que ele baixa.

### O que CONTINUA nas mãos de quem opera o servidor

| | por quê |
|---|---|
| criar a entidade | é o contrato: quem é cliente, e que carreiras contratou |
| `gestores.csv` — quem é gestor | alguém tem de nomear o primeiro, e gestor não nomeia gestor |
| aprovar troca de e-mail de quem já entra | é a trava de T26 — ver abaixo |

**A planilha passou a ligar o acesso (T26, decidido e fechado em 10/11).**
A decisão foi ligar, com trava: quem é novo entra direto, e a troca de
e-mail de quem já entra só vale depois de conferida por quem opera o
servidor. Medido por HTTP, olhando para ONDE o código foi (o arquivo do
remetente), e não para o rol:

- pessoa nova na planilha confirmada recebe código no e-mail da planilha; a
  prévia não abre porta;
- quem já entrava continua recebendo no e-mail de antes — filiado **e
  gestor**, cujo CPF não está em `filiados.csv` e pareceria novo a uma
  conferência que olhasse um arquivo só;
- tirar a pessoa da planilha e recolocá-la com outro e-mail não contorna;
- aprovada pela ferramenta, a troca vale; recusada, não vale e não volta;
- quem pediu apagamento não volta ao rol, e o apagamento leva a troca pedida;
- sindicato sem `filiados.csv`: o gestor entra, envia, e o rol nasce.

Catorze mutantes, um por trava; todos derrubam teste. O ensaio de navegador
cobre o caminho inteiro: alguém que só existe na planilha do gestor passa
pelo portão num navegador limpo, e o disco confirma que o e-mail de quem já
entrava não mudou — com a trava removida, o ensaio falha no disco **com a
tela ainda dizendo "não vale"**, que é o caso para o qual a conferência no
disco existe.

**Dois achados no caminho, medidos e corrigidos.**

1. O rol tinha um escritor só (o apagamento). Com a planilha viraram dois,
   ambos reescrevendo o arquivo inteiro. Os três escritores agora seguram
   uma trava de arquivo.

2. **Um apagamento no meio de um envio de planilha era desfeito.** Em
   sequência forçada, por HTTP: a prévia confere quem pediu para sair
   (ninguém); a pessoa é apagada a pedido, e a rota responde
   `vestigios: []`; a planilha conferida é gravada. Resultado medido: a
   pessoa de volta no `acervo.jsonl`, em `pessoa` e `pessoa_afirmacao` (5
   linhas) e — depois de T26 — no rol. O portão não entregava código, pelo
   tombstone; o dado voltava. O defeito do acervo e do banco é anterior a
   T26; T26 o estendeu ao rol, e foi assim que apareceu.

   Correção: `ingestao.gravar_planilha` confere os apagados **de novo, na
   hora de gravar**, e segura a mesma trava que `apagamento.apagar`. São
   duas coisas, e cada uma tem o seu mutante: conferir de novo encolhe a
   janela, a trava a fecha.

**12/11 — T27 e T28.**

*E-mail repetido em gente nova segura a entrada* (decisão de 12/11). Quem é
novo só entra direto com um e-mail que seja só dele. "Repetido" olha o
portão inteiro e as entradas que esperam, não só a planilha — medido: uma
pessoa por envio não contorna, e o e-mail de um gestor não serve para gente
nova. O que não fecha: um domínio inteiro, com um endereço por pessoa.

*T28, medido* (`docs/medicoes/2026-11-12-apagamento-no-meio.py`, sequência
forçada: o apagamento roda inteiro, pela rota, imediatamente antes de quem
grava). Eu tinha escrito "lido, não medido" para dois caminhos. Medidos, os
dois vazavam — e apareceu um terceiro que eu não tinha listado:

| caminho | sobrava da pessoa apagada |
|---|---|
| planilha | 0 (corrigida em 10/11; fica como controle) |
| documentos do sindicato | 3 — a pasta de entrega, 1 `documento`, 2 `achado` |
| cadastro do filiado | 7 — pasta de entrega, `manifesto.csv`, **`recebidos.jsonl`**, e 23 linhas em 4 tabelas |
| leitura do gestor | 1 — `leituras.jsonl`: o CPF e o que a sentença diz |

O do cadastro é o pior: o diário é a autoridade, e `banco.reconstruir`
traria a pessoa de volta a cada recuperação.

Correção, a mesma nos quatro: conferir **de novo na hora de gravar**, com o
apagamento parado por uma trava comum. O que se confere muda com o caminho,
e no cadastro a escolha importa — ele confere a **sessão** (que o apagamento
revoga), e não o tombstone, porque o cadastro tem de entrar com o banco
fora do ar. Depois: 0 sobras nos quatro; o cadastro responde 401 e a
leitura, 404. Quatorze mutantes desta rodada, todos derrubam teste.

**12/11, mais tarde — as três tarefas agendadas, medidas**
(`docs/medicoes/2026-11-12-apagamento-e-as-tarefas-agendadas.py`).

| tarefa | com um apagamento no meio da rodada |
|---|---|
| `avisar` | **1 e-mail enviado** a quem tinha acabado de pedir para sair, com o nome e a movimentação do processo; o corpo no log; 1 `aviso_enviado` |
| `reavaliar` | 2 linhas em `oportunidade` — o veredicto dela, guardado depois |
| `coletar` | nada do CPF, do nome ou do e-mail; o processo dela gravado mais uma vez |

O e-mail é a única sobra de T28 que sai do servidor, e não se desfaz.

**E uma afirmação minha que a medição derrubou.** Ao escrever o teste da
coleta eu registrei que, apagada ANTES, o processo da pessoa "nem entraria
na lista". Falso. Sem corrida nenhuma, o processo de quem foi apagado
continuava sendo consultado no tribunal a cada coleta (2 de 2, medido): a
lista saía da tabela `processo`, que o apagamento não limpa de propósito.
A varredura dizia `vestigios: []` — corretamente, pelo que ela mede — e o
tratamento continuava. A lista passou a sair de `vinculo`: processo que
ninguém mais tem, ninguém mais consulta; o coletivo continua enquanto
sobrar um filiado nele.

Correção das tarefas: `avisar` e `reavaliar` conferem cada pessoa de novo,
uma a uma, com o apagamento parado até o e-mail sair ou o veredicto ser
gravado; `coletar` relê a lista na hora de gravar. A trava é por pessoa, e
não pela rodada, para um apagamento pedido no painel esperar um e-mail e
não quatro mil. Depois: 0 em tudo. Sete mutantes, todos derrubam teste.

T28 fecha. Fica T29, para o jurídico: o NÚMERO do processo de quem saiu
continua em `processo` (e o que já foi coletado, em `movimento` e
`movimentos.jsonl`). Numa ação própria, o número identifica a pessoa.

**12/11, por último — os avisos do pedido de troca.** O pedido passou a
chegar a quem opera (na hora e em lembrete diário, só com contagens) e ao
dono do e-mail de antes (uma vez, sem link, com o endereço pedido
mascarado; o que falha é tentado de novo). Três coisas que os mutantes
mostraram, e que valem mais que a contagem:

- dois mutantes do aviso a quem opera e um do aviso ao dono SOBREVIVERAM à
  primeira rodada. Cada um era um buraco de teste: nenhum caso só com
  entrada segurada; a função de aviso nunca chamada sem pedido; e nada
  cobrindo quem saiu do acesso com a troca ainda pedida — caso em que o
  mutante mandava o aviso para o endereço PEDIDO. Os três têm teste agora;
- o teste do apagamento passou de primeira, e por isso não valia: só o
  mutante mostrou que ele mede alguma coisa. Mediu um defeito **anterior**:
  o apagamento tirava do log de mensagens a linha do cabeçalho (que tem o
  e-mail) e deixava o CORPO — o aviso de movimentação, com o nome da pessoa
  e o processo dela, sem dono aparente. Só existe no remetente de
  desenvolvimento (sem SMTP); agora sai a mensagem inteira;
- a suíte do servidor quebrou em dois testes meus da rodada anterior, que
  afirmavam "sem endereço nosso, nenhum e-mail sai". Deixou de ser verdade
  de propósito: o aviso ao dono não depende da nossa caixa.


### Uma observação para o dia em que houver planilha real (soma ao item 9)

CPF que começa com zero, guardado no Excel como NÚMERO, perde o zero:
`01234567890` vira `1234567890`, com dez dígitos, e é marcado como "CPF que
não fecha" — a pessoa entra como inalcançável. Cerca de um em cada dez CPFs
começa com zero. O leitor não completa o zero sozinho, e isso é deliberado
(não adivinha); mas é o primeiro lugar para olhar quando uma planilha real
trouxer inalcançáveis demais.
