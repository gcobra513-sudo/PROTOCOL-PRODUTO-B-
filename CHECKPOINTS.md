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
| 10 | **Migração para região brasileira** | **agora** | — |
| 11 | O valor: a prescrição, e a recusa de dizer quanto | **pronto** | `f4ae30d` |

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
| **T10** | O **acervo** não é projetado no banco: só o cadastro. Por isso `pessoa.alcancavel` e `pessoa.tem_divergencia` ficam no padrão — calculá-las só com o cadastro daria um número diferente com o mesmo nome do que `completude` publica | projetar o acervo |
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
