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
| **T11** | `oportunidade` e `tombstone` existem como tabela e ninguém escreve nelas. Sem a primeira não há reavaliação com prova quando um tema for julgado; sem a segunda não há apagamento a pedido (LGPD art. 18, VI) | checkpoint próprio |
| **T7** | Os motivos do motor são escritos na TERCEIRA pessoa ("esta pessoa consta do rol"), porque o mesmo texto serve o painel do sindicato. Na tela do próprio filiado isso lê como dossiê sobre outra pessoa. Trocar por "você" com substituição cega gera concordância errada — "esta pessoa é filiada" concorda com *pessoa*, e viraria "você é filiada" para um homem | decidir se o motor passa a emitir dois registros, um por público |
| **T8** | `ja_executou` vem da RESPOSTA DA PRÓPRIA PESSOA, não de base de execuções — essa base não existe. O motor conta com a resposta e deixa nota dizendo que foi declarada. Enquanto for assim, "não executei" errado só é pego pelo advogado na homologação | o sindicato fornecer a base de execuções já ajuizadas |
| **T6** | Só duas categorias existem em `config/categorias/`, e uma delas está lá sem entrada nenhuma, só para ser reconhecida como outra carreira. Nenhuma ação de nenhuma outra carreira foi pesquisada | o jurídico diz quais categorias e quais ações, por contrato |

---

## Como ler o estado de verdade

```bash
PROTOCOL_DATABASE_URL='postgresql://...' python3 tests/rodar_todos.py
```

Verde não quer dizer "produto pronto": quer dizer "o que está escrito aqui
faz o que diz". O que não existe não tem teste, e está na tabela acima.

Hoje são **382 grupos em Python e 79 testes no portal**, e 10.320 linhas de
teste contra 10.357 de código.

E uma coisa que a auditoria ensinou e que vale mais que o número:
**comentário não é teste.** Em sete dos doze defeitos encontrados havia um
comentário meu afirmando exatamente a propriedade que a medição derrubou —
que o tamanho do zip era conferido antes de descompactar, que CPF nunca
entrava no log, que a resposta nunca dizia se alguém está no rol, que a
trava de região era impedimento e não promessa. Cada uma era hipótese
nunca medida. O registro completo está em `docs/auditoria_seguranca.md`.

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
