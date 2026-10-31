# Onde roda a API do Produto B

Levantamento de **31/10/2026**. Todo número aqui foi lido na fonte oficial
naquela data — página de preços, API pública de preços do próprio provedor
ou documentação. O que não foi confirmado está marcado **não confirmado**.
Nada foi estimado de memória.

**Câmbio:** PTAX venda de 30/10/2026 = **R$ 5,4212/USD**, lido da API Olinda
do Banco Central.

---

## O requisito que elimina

Duas exigências, e as duas são eliminatórias:

1. **O servidor fica no Brasil.** Dado de filiado não sai do país.
2. **A máquina não hiberna.** O agendador é uma thread que acorda a cada
   6 horas (`servidor/agenda.py`, `ACORDAR_SEGUNDOS`). Plataforma que
   descarrega a aplicação por inatividade não executa o trabalho de fundo —
   e não avisa que não executou.

É a segunda exigência que mata a maioria das opções baratas.

---

## Eliminados antes da comparação

| Opção | Por que sai |
|---|---|
| **Render** | Sem região na América do Sul. |
| **AWS App Runner** | Não existe em `sa-east-1`. Medido no índice oficial de serviços por região da AWS: App Runner em 11 regiões, nenhuma na América do Sul. No mesmo índice, Lightsail, EC2 e ECS **estão** em `sa-east-1`. |
| **Google Cloud Run** | Tem a região, falha em três frentes ao mesmo tempo (abaixo). |
| **Oracle Always Free** | Tem a região, mas pode recolher a instância justamente por ela ficar quieta (abaixo). |
| **Square Cloud** | A página não diz o país do datacenter. Com "servidor no Brasil" sendo eliminatório, o silêncio já desqualifica. |

---

## A comparação

Config de referência: **1 vCPU, 1–2 GB RAM, 20–40 GB de disco**. É folgada
para FastAPI/uvicorn com um sindicato, 5.000 pessoas e baixa concorrência;
o pico de RAM vem do `pypdf`, não do tráfego.

| Provedor | Região no Brasil | Hiberna? | Menor config que serve | Disco | Operação que sobra |
|---|---|---|---|---|---|
| **AWS Lightsail** | `sa-east-1` São Paulo | **Não** (VM dedicada) | **US$ 7,00 = R$ 37,95** — 1 GB/2 vCPU/40 GB SSD | Incluso | Alta (VPS) |
| **Magalu Cloud** | `br-se1` São Paulo | **Não** | **R$ 54,99** — 1 vCPU/2 GB/20 GB (R$ 44,99 com 1 GB) | Incluso; extra R$ 0,58/GB/mês | Alta (VPS) |
| **Azure App Service B1** | Brazil South | Sim por padrão; **`Always On` desliga** | **US$ 14,60 = R$ 79,15** | Incluso (`/home`) | **Baixa** (PaaS) |
| **Vultr** | `sao` São Paulo | Não | **US$ 5,00 = R$ 27,11** — 1 vCPU/1 GB/25 GB NVMe | Incluso | Alta |
| **Akamai (Linode)** | `br-gru` São Paulo | Não | **US$ 7,00 = R$ 37,95** — base global é US$ 5,00, `br-gru` tem sobretaxa de 40 % | Incluso | Alta |
| **Fly.io** | `gru` São Paulo | **Depende** — `fly launch` gera `auto_stop_machines = "stop"`, que hiberna | **US$ 12,30 = R$ 66,70** — multiplicador **1,615** de `gru` | À parte, US$ 0,15/GB/mês | Baixa-média |
| **Azure VM B1s** | Brazil South | Não | US$ 12,26 = R$ 66,49 **+ disco** (não confirmado) | À parte | Alta |
| **Locaweb Cloud** | **Não confirmado** na própria Locaweb | Não | R$ 20,00 — 1 vCPU/1 GB/40 GB | Incluso | Alta |
| **Hostinger** | "Brazil", **sem dizer a cidade** | Não | R$ 29,99 só em contrato de 24 meses; **renovação R$ 59,99** | Incluso | Alta |
| **Guara Cloud** | São Paulo | **Não confirmado** | R$ 19,99 — 0,5 vCPU/1,5 GB | **Não confirmado** se persiste entre deploys | Baixa |
| **Google Cloud Run** | `southamerica-east1` | Sim, escala a zero | **US$ 59,10 = R$ 320,38** com CPU sempre alocada e `min-instances 1` | **Não tem** | Baixíssima |
| **Oracle Always Free** | `sa-saopaulo-1` / `sa-vinhedo-1` | Não hiberna — **pode ser apagada** | US$ 0,00 | 200 GB | Alta |

---

## Os dois "quase" que não passam

### Cloud Run: três problemas de uma vez

1. **O agendador em thread não roda no modo barato.** No faturamento por
   requisição, a CPU é cortada fora da requisição — uma espera de 6 horas
   não dispara de forma confiável. Precisa de faturamento por instância
   **e** `min-instances ≥ 1`.
2. **Com isso ligado, custa US$ 59,10/mês** — 8× o Lightsail, para uma
   carga mínima.
3. **Não tem disco persistente.** A pasta de entrega de PDF exigiria GCS ou
   Filestore: mais um componente, mais custo.

### Oracle Always Free: a regra de recuperação

Dois fatos lidos na documentação da Oracle:

- O limite do Ampere A1 hoje é **1.500 OCPU-horas e 9.000 GB-horas/mês**
  ("equivalente a 2 OCPUs e 12 GB"), não os 4 OCPU/24 GB que circulam. A
  data exata do corte não foi confirmada na Oracle.
- Citação literal: *"Idle Always Free compute instances **may be reclaimed
  by Oracle**."* Ociosa = em 7 dias, percentil 95 de CPU **abaixo de 20 %**,
  rede abaixo de 20 %, memória abaixo de 20 %.

Uma API com pouquíssimo acesso que acorda a cada 6 horas **cai exatamente
nessa definição**. O requisito é "não pode parar"; a regra do Always Free é
"se ficar quieta, posso recolher". Serve para desenvolver, não para produção.

---

## Recomendação: AWS Lightsail em `sa-east-1`

**US$ 7,00/mês (R$ 37,95) — 1 GB RAM, 2 vCPU, 40 GB SSD.**

Quatro razões, em ordem de peso:

1. **O banco já está no Supabase `sa-east-1`, e o Supabase roda sobre AWS.**
   A API na mesma região do mesmo provedor é a menor latência possível por
   conexão psycopg3 — o que importa quando se processa 5.000 pessoas em
   sequência. Nenhuma outra opção da tabela consegue isso.
2. **Postura jurídica consistente com a decisão já tomada.** Se `sa-east-1`
   serve para o dado do filiado no banco, serve para o mesmo dado na API.
   Escolher outro provedor só para a API não melhora nada: o dado continua
   num datacenter no Brasil operado por empresa estrangeira, como hoje no
   Supabase. Trocaria latência por zero ganho.
3. **Não hiberna e o preço é fechado.** VM dedicada, sempre ligada: o
   agendador roda sem truque. US$ 7,00 fixos, sem medidor — ao contrário do
   Cloud Run, do Fly (multiplicador 1,615) e do EC2 cru.
4. **Disco persistente incluso nos 40 GB**, sem contratar volume separado.

**O que se aceita junto:** operação de VPS. SO, kernel, renovação de TLS,
backup e monitoração ficam com a gente. **Automatizar a renovação do TLS e o
snapshot diário no primeiro dia** — senão o certificado vence em 90 dias e o
PDF do filiado fica sem cópia.

**Um limite específico de São Paulo:** o plano anuncia 2 TB de transferência,
mas em `sa-east-1` a AWS diz que o pacote é **metade** — 1 TB. Para esta
carga é folga enorme, mas o número muda com a região.

### Segunda opção: Magalu Cloud `br-se1` — R$ 54,99/mês

Fica em segundo por custo e por latência ao banco, **não por qualidade**.

É a escolha certa **se e quando** a conversa de conformidade mudar de "o
servidor está no Brasil" para "o operador é brasileiro". Aí a Magalu vira
primeira opção quase sozinha: empresa brasileira, datacenter em São Paulo,
contrato e fatura em BRL, suporte em português — e nenhuma discussão sobre
transferência internacional, cláusulas-padrão da ANPD ou acesso
administrativo de fora do país.

Os preços da Magalu são os mais verificáveis da lista: vêm da **API pública
de SKUs do próprio provedor** (297 SKUs de VM lidos), não de página de
marketing.

### Terceira, como nota: Azure App Service B1 em Brazil South

US$ 14,60/mês. É o único PaaS maduro da lista que tem região no Brasil, não
hiberna com `Always On`, tem `/home` persistente e cuida de TLS e SO. O
dobro do preço do Lightsail em troca de não administrar servidor.

---

## O que NÃO foi confirmado

1. Localização exata do datacenter da **Hostinger** (a página diz só
   "Brazil", sem cidade).
2. Localização do datacenter da **Locaweb** em fonte da própria Locaweb.
3. Preço do disco adicional da **Locaweb** e do block storage da **Vultr**.
4. **KingHost** e **UOL Host**: não há página oficial com tabela de VPS que
   sirva como número.
5. Preço do disco gerenciado da **Azure** em Brazil South (a VM B1s de
   US$ 12,26 está sem disco no total).
6. Preço on-demand do **EC2** em `sa-east-1` (a lista de preços da região
   tem 292 MB).
7. Data exata do corte do **Oracle** Always Free A1.
8. **Guara Cloud**: se o disco persiste entre deploys e se escala a zero. Os
   dois são requisitos nossos; a página não diz nenhum.
9. **Square Cloud**: país do datacenter, Dockerfile, comportamento em
   ociosidade.
10. Suporte a **volume no `gru` do Fly** especificamente. A doc de regiões
    marca `gru` para Managed Postgres mas não lista volume por região.
11. **A leitura jurídica.** A premissa de que servidor fisicamente no Brasil
    basta para afastar a transferência internacional não é nossa para
    decidir. Num provedor estrangeiro com datacenter no Brasil existe a
    questão separada de **acesso administrativo e suporte de fora do país**,
    que algumas leituras tratam como transferência mesmo com o dado
    armazenado aqui. Isso é interpretação jurídica — **levar a quem assina.**
    É essa dúvida que faz a Magalu valer mais do que custa.
