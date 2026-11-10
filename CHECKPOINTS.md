# Checkpoints

> Onde estamos, o que já está pronto, o que vem. Atualizado a cada entrega.
> Se este arquivo discordar do `MAPA.md`, o mapa vence no **o quê**; este
> vence no **quando**.

---

## Régua

| # | Checkpoint | Estado | Commit |
|---|---|---|---|
| 0 | Repositório próprio do Produto B, separado do A | **pronto** | `14df42e` |
| 1 | Regra zero gravada em `CLAUDE.md` | **pronto** | `01c188d` |
| 2 | Leitura de documentos: PDF vira fato, com procedência | **pronto** | `4af0ca1` |
| 3 | Motor do veredicto: executar / ajuizar / falta | **pronto** | `2e21766` |
| 4 | Cadastro certo: o que o B pede, não o que o A pedia | **pronto** | `6fd78d6` |
| 5 | Ação coletiva como entidade: categoria + período | **pronto** | `6fd78d6` |
| 6 | Cruzamento: de quais ações a pessoa participa | **pronto** | `adc96a2` |
| 7 | Portal do filiado pedindo o que o B pede | **pronto** | `73df604` |
| 7b | Catálogo por categoria: atender vários sindicatos | **pronto** | `0afa698` |
| 7c | Mostrar ao filiado de quais ações ele participa | **pronto** | `09af14c` |
| 8 | Painel do sindicato: o que resolver primeiro | **pronto** | `6700a89` |
| 9 | Banco ligado: diário é a autoridade, banco é a projeção | **pronto** | `dfca8a6` |
| 10 | **Migração para região brasileira** | **decidido, a contratar** | — |
| 17 | Auditoria de segurança independente: 13 achados, todos fechados | **pronto** | `a338473` |
| 18 | A Regra Zero conferida por programa: escritório deixa de ser arquitetura | **pronto** | — |
| 19 | Auditoria de PRODUTO: o produto faz a frase dele? | **feita — 10 achados, 4 fechados, e a fila de leitura com saída** | `docs/auditoria_do_produto.md` |
| 16 | O agendador, e o silêncio que ele podia criar | **pronto** | `deb55ce` |
| 15 | O aviso de movimentação: a promessa do formulário, cumprida | **pronto** | `e1bc2ab` |
| 14 | O portal reconhece quem já está na base | **pronto** | `5c3aef4` |
| 13 | Os documentos que o sindicato já tem entram | **pronto** | `5c3aef4` |
| 12 | A planilha do sindicato vira a base, não um relatório | **pronto** | `3597873` |
| 11 | O valor: a prescrição, e a recusa de dizer quanto | **pronto** | `f4ae30d` |

---

## Onde isto vai rodar — decidido em 01/11/2026

**AWS Lightsail `sa-east-1` (São Paulo) + Supabase Pro.** R$ 181,47/mês à
PTAX venda de 30/10/2026 (R$ 5,4212/USD). Os números e as alternativas
estão em `docs/hospedagem.md` e `docs/custo_da_operacao.md`.

A razão não é preço — é que **a invariante de isolamento já está provada
neste par exato, ao vivo**: entidade A vê só a linha dela, escrita cruzada
recusada, e a aplicação não consegue apagar o próprio registro de leitura.
Trocar o banco significa reprovar isso num modelo de privilégio diferente
(`neon_superuser`, `azure_pg_admin`, `rds_superuser` — cada um muda quem
assume papel). Não é custo em dinheiro: é risco sobre a promessa de que um
sindicato nunca vê o dado de outro.

O que foi medido e eliminou os outros:

| | por quê |
|---|---|
| Render | sem região na América do Sul |
| AWS App Runner | não existe em `sa-east-1` |
| Cloud Run | o agendador em thread exige CPU sempre alocada: US$ 59/mês, e sem disco persistente |
| Oracle Always Free | *"Idle Always Free compute instances may be reclaimed"* — a nossa carga é a definição de ociosa |
| Supabase Free · Neon Free | pausam por inatividade; o Neon em 5 min, sem opção de desligar |
| Azure Postgres Burstable | a própria Azure: *"Not recommended for production workloads"*. Produção começa em ~R$ 1.900/mês |
| Vultr | preço não confirmado: API exige credencial, páginas devolvem 403 |
| DigitalOcean · Scaleway · Hetzner · Railway · Heroku | nenhuma região no Brasil |

**A alternativa, se o Supabase um dia incomodar:** Akamai/Linode `br-gru`,
R$ 86,74/mês, 9 GB de disco e 14 dias de backup inclusos, com regra
literal a favor (*"charges accrue even if it's powered off"*).

**Duas coisas no primeiro dia, não depois:** renovação automática de TLS (o
certificado do Let's Encrypt vence em 90 dias) e snapshot diário
(US$ 0,05/GB/mês). Sem as duas, em três meses o portal cai e o PDF de
sentença está sem cópia.

**Atenção a um limite de São Paulo:** o bundle de US$ 7,00 anuncia 2 TB de
transferência, mas em `sa-east-1` a AWS entrega **metade**.

---

## Números medidos, que corrigem suposições anteriores

| | medido | onde |
|---|---|---|
| Cadência do agendador | **24 h**, não as 20 h da constante — o despertar é de 6 h, e o primeiro vencimento depois de 20 h cai em 24 | `servidor/agenda.py` |
| Banco por pessoa | **4,6 KB** pela planilha; ~9 KB com o envio do portal. A 100 mil pessoas o banco não chega a 1 GB | semeado e lido com `pg_database_size` |
| Custo de um cadastro | **27 comandos SQL**, independente do tamanho do diário (era 21 por registro já existente) | contador em `psycopg.Cursor.execute` |
| Ler o próprio cadastro | **18 linhas**, independente do tamanho da base (eram 78 com 30 pessoas) | contador em `fetchall` |
| Requisições ao DataJud | **1.470/mês** para 4.812 processos (lote de 100, 30 rodadas). O limite do CNJ é 120/min | `servidor/acompanhamento.py` |
| E-mails | **3.600/mês** no pior caso medido. Custa R$ 1,95 | cálculo sobre volume medido |
| Teto de corpo HTTP | 413 com **0 byte** enviado; sem `Content-Length`, conexão cortada em **2,7 MiB** de 200 MiB | uvicorn real em loopback |

**O gargalo de escala não é o banco: é o disco da máquina, por causa dos
PDFs.** Os 40 GB do Lightsail comportam ~45.000 pessoas supondo 0,9 MB por
pessoa — e **esses 0,9 MB são suposição minha, não medição**. O teto que o
código impõe é 60 MB por envio, o que no pior caso daria 282 GB. A
diferença entre 4 GB e 282 GB decide o plano de disco, e só um lote real
responde.

---

## O que está travado, e não é código

| | O quê | Quem destrava |
|---|---|---|
| **T1** | Nenhuma ação ou tese está homologada. O motor roda e não autoriza nada — corretamente | um advogado marca `homologado = "S"` |
| **T2** | A GIFA está no catálogo como **exemplo real que eu pesquisei**, não como decisão de vocês | o jurídico diz quais ações entram |
| **T3** | `exige_rol = false` na GIFA porque não tenho os autos. Se houver rol, muda quem participa | conferir nos autos |
| **T4** | Nenhuma exportação real de sindicato foi vista. A ingestão foi construída contra planilha que eu sujei imitando Excel brasileiro | o sindicato manda um arquivo |
| **T5** | Retenção e apagamento não têm prazo aprovado | parecer |
| **T12** | **Não há como calcular valor.** Faltam três coisas que nenhum código resolve: a FICHA FINANCEIRA de cada pessoa (base de cálculo mês a mês), o PERCENTUAL da verba (sai do dispositivo da sentença) e o ÍNDICE de correção com a tese que o sustenta. O motor recusa e nomeia cada um | o sindicato manda a ficha; o jurídico lê o dispositivo |
| **T13** | `ajuizada_em` da GIFA está **vazio**, e sem ele não há corte de prescrição. Não é inferível do número CNJ: o ano ali é o da AUTUAÇÃO, que pode não ser o do ajuizamento | conferir nos autos |
| **T15** | Pegamos **movimentação** (DataJud, ~1 dia de atraso), não **publicação/intimação**: o DJEN bloqueia o nosso acesso por região. Para cortar ligação serve; para prazo, não — e o texto do aviso diz isso | decidir se vale buscar acesso ao DJEN |
| **T11** | **AS DUAS METADES PRONTAS.** Primeira (apagamento a pedido, `docs/superpowers/plans/2026-11-02-apagamento-a-pedido.md`): o sindicato apaga **pela tela do painel**, com confirmação em duas etapas, o tombstone fica, a reingestão pula e avisa, a restauração de backup não ressuscita, e `vestigios()` MEDE que não sobrou nada em vez de um campo afirmar que sim. Dois revisores independentes reprovaram a primeira entrega — quatro sobrevivências de dado pessoal e sete defeitos — e a passada de correção fechou as onze. Segunda (`oportunidade` persistida, `docs/superpowers/specs/2026-11-02-oportunidade-persistida-design.md`): o veredicto é guardado com a prova de qual catálogo o produziu — a assinatura DECLARADA e o digest MEDIDO —, a tabela é append-only por assinatura, a tarefa `reavaliar` roda no agendador, e o painel diz o que mudou, com nome. **Uma previsão minha sobre isto estava ERRADA e foi corrigida em 10/11:** escrevi que a homologação mostraria `FALTA → PODE`. Medido, não mostra — a homologação sozinha produz zero `PODE`, porque nada informa o rol de substituídos (`docs/auditoria_do_produto.md`, item 1). O veredicto guardado também ignorava os documentos já lidos; corrigido na mesma data | **a migração no banco de São Paulo está PENDENTE** (`servidor/migracoes/LEIA.md`) |
| **T7** | Os motivos do motor são escritos na TERCEIRA pessoa ("esta pessoa consta do rol"), porque o mesmo texto serve o painel do sindicato. Na tela do próprio filiado isso lê como dossiê sobre outra pessoa. Trocar por "você" com substituição cega gera concordância errada — "esta pessoa é filiada" concorda com *pessoa*, e viraria "você é filiada" para um homem | decidir se o motor passa a emitir dois registros, um por público |
| **T8** | `ja_executou` vem da RESPOSTA DA PRÓPRIA PESSOA, não de base de execuções — essa base não existe. O motor conta com a resposta e deixa nota dizendo que foi declarada. Enquanto for assim, "não executei" errado só é pego pelo advogado na homologação | o sindicato fornecer a base de execuções já ajuizadas |
| **T19** | **O produto não consegue dizer `PODE` por nenhum caminho, nem homologado.** Duas travas medidas: (a) nada informa se a pessoa consta do rol de substituídos, e o motor exige saber mesmo com `exige_rol = false`; (b) o motor cobra DA PESSOA a sentença de uma coletiva que o catálogo já registra como transitada. `docs/auditoria_do_produto.md`, item 1 | código: a porta de entrada do rol. Jurídico: a regra para ação sem rol, e se o título da coletiva entra uma vez, pela ação |
| **T25** | **O fato que o gestor digita entra como CERTO e alimenta o motor.** A fila de leitura humana ganhou saída em 10/11 (T24, fechado: o sindicato abre, lê e registra pelo painel; a leitura fica em `leituras.jsonl`, com autor). Hoje isso não chega a `PODE` porque falta o rol (T19). No dia em que o rol existir, "procedente" e uma data de trânsito digitados por quem não é advogado bastam para `PODE executar`. `docs/auditoria_do_produto.md`, fim | o jurídico diz se a leitura do sindicato precisa de visto de advogado antes de valer. O lugar para o visto já existe (`achado.conferido`, `metodo = "pessoa"`) |
| **T26** | **FECHADO em 10/11 — a planilha do gestor liga o acesso, com trava.** Decisão: ligar. Quem é NOVO no portão entra na hora, com o e-mail da planilha; quem JÁ entra não muda de e-mail pela planilha — a troca fica pedida em `trocas_de_email.jsonl` e só vale por `ferramentas/trocas_de_email.py`, rodada por quem opera. A planilha não tira ninguém do acesso (tirar e recolocar seria a porta dos fundos da troca), "já entra" olha os dois róis (o CPF de um gestor não vira novo), e não há rota de aprovar — `testes_repositorio` falha se aparecer. Sindicato sem `filiados.csv` começa sozinho: o gestor entra e a primeira planilha cria o rol. Medido pelo DESTINO do código, não pelo arquivo; 14 mutantes. `servidor/LEIAME.md`, "A planilha liga o acesso" | — |
| **T27** | **Quem ainda não entrou recebe o PRIMEIRO e-mail que a planilha trouxer.** É o lado aceito da decisão de T26 ("gente nova entra direto"). Uma conta de gestor comprometida não troca o e-mail de quem já entra, mas pode pôr o próprio endereço em quem ainda não está no acesso — e em quantas pessoas quiser: nada impede o mesmo e-mail em 500 linhas novas. O que ela ganha é abrir cadastro no nome delas e impedi-las de entrar; os dados delas o gestor já vê pelo painel. E a troca pedida não avisa ninguém: quem opera só fica sabendo pela linha `TROCA DE E-MAIL pedida` no log | decidir se e-mail repetido em gente nova deve segurar a entrada, e se a troca pedida avisa o e-mail de antes |
| **T28** | **Os outros dois caminhos que gravam dado de pessoa conferem o apagamento ANTES e gravam DEPOIS.** Na planilha isso foi medido e corrigido em 10/11 (um apagamento no meio do envio era desfeito: `docs/auditoria_do_produto.md`). Os documentos do sindicato (`gravar_documentos`) e o cadastro do filiado em andamento (`depositar`) têm o mesmo desenho e NÃO seguram a trava do apagamento. **Lido no código, não medido** | código: medir em sequência forçada, como foi feito na planilha |
| **T22** | **Nada está no ar**: sem artefato de implantação, hospedagem não contratada, banco no plano que pausa, migração pendente. Item 6 | contratar a hospedagem |
| **T23** | **O rascunho do navegador é compartilhado entre pessoas** no computador da sede — lido no código, não ensaiado. Item 7 | código |
| **T16** | **O aviso de privacidade que o filiado lê descreve o PRODUTO A.** `portal/src/componentes/Privacidade.tsx` diz, em texto que vai para a tela: "montar a petição e apresentá-la em juízo", "a execução do **contrato** com o escritório", "quando o envio ao escritório for ligado", "o prazo em que o escritório é obrigado a guardar documentos de clientes". O B não protocola nada e quem fala com o filiado é o sindicato. São 4 trechos em JSX, medidos. **Não reescrevi**: aviso de privacidade é texto jurídico, e a base legal declarada ("execução do contrato com o escritório") é uma afirmação sobre com quem o filiado contratou — não é decisão de código | o jurídico diz qual é a base legal e quem é o controlador nesta relação |
| **T18** | **O B usa a palavra `manifesto`, que o `CLAUDE.md` lista como vocabulário do A.** Medido: 91 ocorrências em 10+ arquivos, incluindo o nome de um arquivo que o gestor ABRE (`manifesto.csv`) e uma coluna de contrato (`colunas_manifesto`). Ou a lista do `CLAUDE.md` está errada sobre esta palavra — ela pode ter querido dizer o manifesto de LOTE do A, que é outra coisa —, ou o B precisa renomear um artefato central. Não decidi sozinho porque renomear muda um nome que já está em uso | dizer qual das duas |
| **T6** | Só duas categorias existem em `config/categorias/`, e uma delas está lá sem entrada nenhuma, só para ser reconhecida como outra carreira. Nenhuma ação de nenhuma outra carreira foi pesquisada | o jurídico diz quais categorias e quais ações, por contrato |

---

## Como ler o estado de verdade

```bash
PROTOCOL_DATABASE_URL='postgresql://...' python3 tests/rodar_todos.py
```

Verde não quer dizer "produto pronto": quer dizer "o que está escrito aqui
faz o que diz". O que não existe não tem teste, e está na tabela acima.

Hoje são **489 grupos em Python e 136 testes no portal** (22 suítes mais o ensaio de navegador), e
16.280 linhas de teste contra 21.718 de código (teste: `tests/*.py` e `*.test.ts`; código: `nucleo`,
`servidor`, `ferramentas` e `portal/src`, sem os testes — contadas com `wc -l` em 10/11).

E uma coisa que a auditoria ensinou e que vale mais que o número:
**comentário não é teste.** Em sete dos doze defeitos encontrados havia um
comentário meu afirmando exatamente a propriedade que a medição derrubou —
que o tamanho do zip era conferido antes de descompactar, que CPF nunca
entrava no log, que a resposta nunca dizia se alguém está no rol, que a
trava de região era impedimento e não promessa. Cada uma era hipótese
nunca medida. O registro completo está em `docs/auditoria_seguranca.md`.

E a doença tinha um andar acima do código: **`servidor/LEIAME.md` mandava
rodar `ferramentas/ensaio_portal.py`** — um ensaio de navegador, ponta a
ponta, descrito em detalhe — **e esse arquivo nunca existiu em commit
nenhum.** Estava escrito, então passava por verificado.

**Agora existe, e roda dentro de `tests/rodar_todos.py`** (12 s;
`PROTOCOL_SEM_ENSAIO=1` pula, e o pulo aparece). Ele paga a dívida e mede o
que mais nada mede: trocando `onCarreira("cargo", v)` por
`onCarreira("unidade", v)` em `portal/src/etapas/Carreira.tsx`, **as 424
verificações de Python, os 89 testes do portal e o `tsc` continuam verdes** —
o campo da tela passa a escrever no lugar errado, chega ao disco vazio, e a
tela continua dizendo "enviado". O ensaio cai. Está dentro do `rodar_todos`
de propósito: verificação que ninguém roda é o mesmo que verificação que não
existe, e foi assim que a primeira versão desta promessa durou meses.

E uma terceira forma da mesma doença, que eu mesmo produzi: **rótulo de
gravidade também não é medição.** Cinco defeitos ficaram adiados como
"menores" depois da revisão. Ao atacá-los, um deles — "a ferramenta
constrói um `Portao` inteiro só para um HMAC" — era, medido, o apagamento
pela linha de comando **revogando a sessão no banco errado**: o servidor
abre o portão em `cfg.raiz`, a ferramenta abria em `.portao-ferramenta`.
A sessão da pessoa continuava viva por até quatro horas e a ferramenta
imprimia "nada sobrou". É o mesmo defeito que a revisão já havia achado
pelo caminho do servidor (S3), de volta por outra porta — e o HMAC casava
por acaso, porque ele só depende do segredo, o que deixou o tombstone
certo e o defeito invisível. O rótulo "menor" era uma hipótese sobre o
custo, escrita sem medir.

---

## Histórico, em uma linha cada

- **0** — O B dividia repositório com o peticionamento em massa. Medi o
  fechamento de dependências (três módulos) e trouxe só isso.
- **1** — Eu mesmo confundi A com B dentro do repositório do B. A regra foi
  para `CLAUDE.md`, que é lido sozinho em toda sessão.
- **2** — O portal já extraía texto do PDF; ninguém tirava fato. Agora cada
  achado carrega o trecho de onde saiu.
- **3** — Executar exige título, ajuizar não. É o primeiro teste do
  repositório.
- **4** — O portal pedia procuração (documento para litigar, do A). O B pede
  comprovante de contribuição, que prova o período de filiação.
- **5** — A ação coletiva não é só um número: alcança uma categoria, num
  período.
- **6** — Cruzar filiação com período responde "de quais ações eu faço
  parte". Filiação parcial é participação parcial.
- **7** — O portal pedia procuração, identidade e endereço (do A). Agora pede
  contribuição, carreira e filiação. Seis etapas em vez de sete, e a da
  filiação explica por que pergunta.
- **7b** — Era a tela do filiado; virou o catálogo, porque a tela seria
  construída contra a hipótese de um cliente só e refeita depois. O catálogo
  era um arquivo único de uma categoria: com dois sindicatos de carreiras
  diferentes, a trilha AJUIZAR oferecia a tese de uma carreira a quem era de
  outra — e, com os critérios preenchidos, oferecia como PODE. Agora é um
  arquivo por categoria, a entidade declara o que contratou, e a tabela de
  grafias de cargo saiu do Python. A tela virou 7c.
