# Quanto custa operar o Produto B

Preços lidos na fonte oficial em **31/10/2026**. Volumes medidos no próprio
código. **Câmbio: PTAX venda de 30/10/2026 = R$ 5,4212/USD**, da API Olinda
do Banco Central.

Todo total aqui carrega a data da cotação ao lado, porque de 23/10
(R$ 5,0377) a 26/10 (R$ 5,5007) a PTAX andou **9,2 % num fim de semana**.
Preço em dólar é linha de custo variável em reais.

---

## Antes do preço: o Termo de Uso do DataJud

O PDF oficial do CNJ (Termos de Uso v1.2, de 27/11/2023) contém:

- **3.3** — "A API é fornecida exclusivamente para fins legais, **não
  comerciais** e autorizados..."
- **3.8** — "...não modificar, distribuir, vender ou **explorar
  comercialmente a API ou qualquer informação derivada dela**."
- **3.11** — "...não usar a API para **coletar informações pessoais de
  terceiros**."
- **4.2** — "...**não coletar, armazenar ou processar dados pessoais
  originários da API**..."
- **4.6** — "...não compartilhar dados pessoais coletados por meio da API
  com terceiros."

A aceitação é tácita (item 1.2): usar a interface já é aceitar.

O aviso de movimentação é inteiramente baseado nessa API. Ele coleta
movimentação de pessoa física, armazena no nosso banco e entrega ao
sindicato — terceiro em relação ao filiado — num produto vendido.

**O custo monetário do DataJud é zero. O custo contratual não é.** Isto é
parecer de advogado, não arquitetura, e precisa ser resolvido antes de
vender a funcionalidade.

---

## O volume, medido no código

| | medido | onde |
|---|---|---|
| Cadência do agendador | **24 h** (acorda 6 h, vence 20 h → primeiro despertar depois de 20 h) | `agenda.py:176,178` |
| Rodadas por mês | 30 de cada tarefa | cálculo sobre o acima |
| Lote do DataJud | **100 processos por requisição** | `acompanhamento.py:100` |
| Requisições/mês (4.812 processos) | **1.470** | cálculo |
| Limite do CNJ | **120 req/min** (item 3.13 do Termo) | Termo de Uso v1.2 |
| E-mail: quem recebe | só quem marcou o opt-in, e só quem tem novidade | `banco.py:711` |
| E-mails/mês (pior caso: 50 % opt-in, 5 % novidade/dia) | **3.600** | cálculo |
| Linhas de banco por envio | **17** (um campo por linha) | `contrato_cadastro.json` |
| Teto de upload por envio | 60 MB | `config.py:29` |

A cadência de 24 h é importante: o código diz 20 h, mas com despertar de
6 h o primeiro vencimento cai em 24 h. São 30 rodadas por mês, não 36.

---

## Eliminado por medição: o plano gratuito não serve

**Supabase Free pausa o projeto após 7 dias de baixa atividade e NÃO volta
sozinho** — exige clique manual no painel. A regra literal:

> "A Free plan project is considered inactive if it does not receive
> sufficient user database activity over the past week."

A redação é deliberadamente vaga ("sufficient activity"), sem limiar
numérico publicado. Nosso processo de fundo acorda a cada 6 h e
provavelmente satisfaz — mas **apostar que não vai pausar é apostar numa
regra sem número**. Há ainda um segundo gatilho: estourar os 500 MB de
banco ou os 5 GB de egress do Free também pode pausar, pela Fair Use Policy.

**Neon Free suspende após 5 minutos** e a própria página diz
"cannot be turned off".

O piso que cumpre o requisito de forma contratual é plano pago.

---

## A conta

### Opção A — Lightsail `sa-east-1` + Supabase Pro

| item | R$/mês |
|---|---|
| VM Lightsail 1 GB/2 vCPU/40 GB `sa-east-1` (US$ 7,00) | 37,95 |
| **Supabase Pro** (US$ 25,00) — o piso que não pausa | **135,53** |
| Snapshot Lightsail 10 GB (US$ 0,05/GB) | 2,71 |
| Amazon SES, 3.600 e-mails (US$ 0,10/mil) | 1,95 |
| Domínio `.com.br` (R$ 40,00/ano) | 3,33 |
| TLS Let's Encrypt · Sentry free · UptimeRobot free | 0,00 |
| DataJud, 1.470 requisições | 0,00 |
| **total** | **R$ 181,47** |

### Opção B — Magalu Cloud `br-se1`, operador brasileiro

| item | R$/mês |
|---|---|
| VM Magalu 1 vCPU/2 GB/20 GB `br-se1` | 54,99 |
| DBaaS PostgreSQL 1 vCPU/4 GB/10 GB | 94,22 |
| Amazon SES, 3.600 e-mails | 1,95 |
| Domínio `.com.br` | 3,33 |
| TLS · Sentry free · UptimeRobot free | 0,00 |
| Snapshot Magalu | **tarifa não publicada** |
| **total (incompleto)** | **R$ 154,49** |

---

## Onde o dinheiro está

| fatia | item |
|---|---|
| **74,7 %** | Supabase Pro |
| 20,9 % | VM Lightsail |
| 1,8 % | domínio |
| 1,5 % | snapshot |
| **1,1 %** | **e-mail + DataJud somados** |

**O número de filiados não move a conta nessa escala.** 3.600 e-mails custam
R$ 1,95. O que se paga é o banco e a máquina, e nenhum dos dois cresce com
o número de pessoas até muito depois de 4.812.

### O custo marginal do segundo sindicato

Mesma VM, mesmo banco, mais 3.600 e-mails: **cerca de R$ 2,00/mês.**

É isso que decide o preço de venda — não a planilha de infraestrutura.

---

## Correção da recomendação anterior

Em `docs/hospedagem.md` recomendei o **Lightsail**, e a primeira razão foi
colocar a API na mesma região do Supabase. Aquela análise **tomou a decisão
do Supabase como dada** e só comparou onde a API rodaria.

Precificando a pilha inteira, a ordem inverte:

- **Magalu custa R$ 26,98/mês menos** (R$ 154,49 contra R$ 181,47), porque o
  DBaaS de R$ 94,22 é mais barato que o Supabase Pro de R$ 135,53.
- **E a Magalu resolve a dúvida jurídica** que eu mesmo registrei como o
  item que não consegui confirmar: operador brasileiro, sem discussão sobre
  transferência internacional nem sobre acesso administrativo de fora do
  país.

Ou seja: a opção mais barata e a juridicamente mais simples são a mesma, e
não é a que eu havia recomendado. **Se o Supabase ainda não está em
produção, a Magalu é a escolha.** Se a migração do que já está lá custar
mais do que R$ 27/mês de economia, a conta muda — mas essa é uma decisão
de esforço, não de preço de tabela.

### Três ressalvas que podem reverter isso de novo

1. **A tarifa de snapshot da Magalu não é publicada.** A documentação diz
   que snapshot de volume é cobrado por GiB e tempo, mas não publica o
   preço, e não há SKU na API. O total da opção B está incompleto.
2. **O DBaaS da Magalu só tem disco de 10 GB e de 40 GB.** O de 10 GB custa
   R$ 94,22; o de 40 GB existe só na classe superior, **a partir de
   R$ 449,56** — salto de 4,8×. Quando o banco passar de 10 GB, a conta não
   sobe: ela pula de patamar. O Supabase, nesse ponto, cobra por GB
   (US$ 0,125/GB-mês acima dos 8 GB inclusos) e é mais previsível.
3. **Os preços em dólar são piso, não custo final.** Não medi IOF nem
   tributo sobre serviço importado, e nenhuma das páginas em USD os declara.
   Só os preços da Magalu vêm declaradamente com impostos inclusos — o que
   estreita a diferença real ainda mais a favor dela.

---

## E-mail: só um provedor atende o requisito

O corpo do aviso pode levar nome e CPF. Dos sete medidos, **só o Amazon SES
tem endpoint confirmado em `sa-east-1` com tarifa regional publicada** (o
índice oficial de serviços por região da AWS confirma SES em `sa-east-1`, e
a price list de São Paulo traz `Recipients:Send` a US$ 0,0001 por
destinatário — tarifa regional própria, não página de marketing).

| provedor | região no Brasil |
|---|---|
| **Amazon SES** | **sim, `sa-east-1` confirmado** |
| Resend | envia por `sa-east-1`, mas **armazena nos EUA**, e declara não assinar cláusulas de LGPD/ANPD |
| Mailgun | não — só EUA ou UE |
| SendGrid | não — residência só na UE |
| Postmark | não declara |
| Locaweb SMTP (R$ 33/mês) | empresa brasileira; **localização do servidor não declarada** |
| MailGrid (R$ 99,90/mês) | faturamento no Brasil; **infraestrutura não declarada** |

Para dado pessoal de filiado, "empresa brasileira" não é a mesma afirmação
que "processamento no Brasil".

---

## Armadilhas registradas

- **Supabase cobra compute por projeto, não por conta.** Um ambiente de
  homologação separado custa +US$ 10/mês. E não se pode misturar projeto
  pago e gratuito na mesma organização.
- **Egress do Supabase é cota da organização inteira**, somada entre
  projetos (250 GB no Pro, depois US$ 0,09/GB).
- **Resend Free tem teto diário de 100 e-mails** escondido atrás dos 3.000
  mensais. Um dia de assembleia estoura o diário sem chegar perto do mensal.
- **Ingestão de log no CloudWatch custa 22× o armazenamento** (R$ 4,88/GB
  contra R$ 0,22/GB-mês). Quem quebra a conta é escrever log.
- **Saída de dados da AWS `sa-east-1` custa R$ 0,81/GB**, contra R$ 0,10/GiB
  na Magalu — 8× mais. Se um dia servirmos PDF ao filiado, essa linha domina.
- **A franquia de transferência do Lightsail é metade em São Paulo.**
- **Sentry gratuito tem lookback de 30 dias.** Erro de 31 dias atrás não
  existe mais.
- **Promoção de primeiro período** no SES (6 meses), Mailgun (1 mês) e
  SendGrid (60 dias). A conta do mês 7 não é a do mês 1.

---

## O que falta medir

1. **Tamanho real de um PDF de sentença.** Usei 0,3 MB como suposição e dá
   4,2 GB para 4.812 pessoas; o teto do código (60 MB por envio) daria
   282 GB. A diferença decide se 40 GB de disco servem. **Medir com um lote
   real antes de fechar o plano.**
2. **Tarifa de snapshot da Magalu.**
3. **IOF e tributo sobre serviço importado** — tem de vir do contador ou da
   fatura, não de página de preço.
4. **Três números que só a realidade responde:** quantos filiados tem o
   primeiro sindicato de verdade, que fração tem processo em andamento, e
   quantos marcam o opt-in.
