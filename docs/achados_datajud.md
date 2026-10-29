# O que o DataJud entrega, medido

Levantado em 29/10/2026 por requisição real deste contêiner, com a chave
pública do CNJ lida de `https://datajud-wiki.cnj.jus.br/api-publica/acesso/`.

Isto existe porque o Produto B vai acompanhar movimentação por número de
processo, e três características do DataJud decidem o desenho: a lista de
tribunais, o tempo de resposta e uma ausência.

---

## 1. A chave é pública e funciona

```
POST api-publica.datajud.cnj.jus.br/<alias>/_search
Authorization: APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==
```

HTTP 200 em `api_publica_trf1`, `api_publica_stj` e `api_publica_trt10`.
Não é credencial, é chave de acesso publicada — ver o comentário em
`ferramentas/conferir_datajud.py`.

## 2. São 65 aliases, e o acompanhamento não é só do TRF1

Da página oficial de endpoints, `api_publica_<sigla>`:

| Grupo | Quantos | Exemplos |
|---|---|---|
| Justiça Estadual | 30 (inclui 3 TJMs) | `api_publica_tjsp`, `api_publica_tjdft`, `api_publica_tjmsp` |
| Justiça Federal | 6 | `api_publica_trf1` … `api_publica_trf6` |
| Justiça do Trabalho | 24 | `api_publica_trt1` … `api_publica_trt24` |
| Tribunais Superiores | 4 | `api_publica_stj`, `api_publica_tst`, `api_publica_tse`, `api_publica_stm` |
| Eleitoral regional | 1 | `api_publica_tre` |

O alias sai do próprio número CNJ — os campos `J` (segmento) e `TR` (tribunal)
de `NNNNNNN-DD.AAAA.J.TR.OOOO`, que `processo_cnj.decompor` já extrai.

**Mas por TABELA, não por fórmula**, e a primeira versão desta linha dizia o
contrário. `f"api_publica_trf{tr}"` acerta a Justiça Federal e erra todo o
resto: `J=8, TR=07` é o `tjdft`, não "tj07"; `J=8, TR=26` é o `tjsp`. A
fórmula produziria requisição a índice inexistente com cara de código
elegante. A tabela está em `servidor/acompanhamento.py`, com teste contando
os 65.

**Consequência de produto:** acompanhar o processo que o filiado informar não
depende de ele ser do TRF1.

A primeira leitura disto foi que o servidor estava errado em recusar número de
outro tribunal (`servidor/validacao.py`, `exigir_trf1=True`). **Estava errada a
leitura.** Um teste que já existia na suíte do portal afirmava o contrário, com
razão: `numero_processo` é o processo da **sentença de origem**, e é dele que
sai o juízo da execução (CPC, art. 516, II). O Produto A protocola no TRF1 —
sentença do TRF5 se executa no TRF5, e protocolar no TRF1 seria incompetência
garantida. A trava fica.

A solução foi outra: **campo separado.** `acompanhar` recebe os números que o
filiado quer acompanhar e aceita qualquer um dos 65 tribunais; `numero_processo`
continua exigindo TRF1. São perguntas diferentes, e por isso são campos
diferentes.

**Fica uma divergência de tela**, e ela é real: o portal apenas AVISA quando o
número da sentença não é do TRF1 (`portal/src/etapas/E5Processo.tsx`), e o
servidor recusa. Quem tem sentença de outro tribunal preenche, é avisado, envia
e é reprovado. A correção é de produto, não de validação: a tela precisa dizer
*"este processo não é do TRF1 — informe-o em acompanhamento, não como o
processo da sua sentença"*.

## 3. O STF não está no DataJud

`api_publica_stf` devolve `index_not_found_exception`, e a página oficial de
endpoints não menciona o STF em lugar nenhum — nenhuma das 65 entradas.

Isto importa porque a segunda perna do Produto B é "avisar quando o
entendimento mudar". Pelo DataJud:

- **STJ: dá.** Tema repetitivo tem recurso representativo com número, e o
  número é consultável em `api_publica_stj`.
- **STF: não dá por aqui.** Precisa de outra fonte, e ela ainda não foi
  levantada.

Leitura provável do motivo, não medida: a competência do CNJ (CF, art. 103-B,
§4º) alcança os órgãos do Judiciário mas não o STF, e o DataJud é base do CNJ.

> Atenção ao pesquisar isto na internet: há material comercial afirmando que o
> DataJud cobre STJ **e** STF. A API e a lista oficial de endpoints dizem o
> contrário, e foi o que se mediu.

## 4. É lento, e isso decide a arquitetura

Tempo total por consulta, medido:

| Alias | Tempo |
|---|---|
| `api_publica_trf1` | 43,2 s |
| `api_publica_stj` | 28,3 s |
| `api_publica_trt10` | 22,1 s |
| `api_publica_tjdft` | estourou 60 s na primeira tentativa |

Já era conhecido do conferidor do Produto A, que mediu 15–30 s por chamada
**independente do número de processos pedidos** — e é por isso que ele
consulta em lotes de ~100.

**Consequência de produto:** a tela de consulta do filiado NÃO pode consultar
o DataJud ao vivo. Ela lê a nossa base; quem fala com o DataJud é o coletor,
em segundo plano. Uma tela que espera 40 s é uma tela que ninguém usa, e um
timeout de 60 s vira erro na cara do filiado.

## 4b. Ponta a ponta, medido

Coletor rodado de verdade em 29/10/2026 contra `0021535-29.2019.4.01.3500`,
processo real do TRF1, mais dois números sintéticos:

```
consultados ........... 3
movimentos lidos ...... 75
tribunais com falha ... 0
sem registro .......... 2   (os sintéticos)
tempo total ........... 1m22s  (duas chamadas: trf1 e tjdft)
```

Dois fatos que só a medição deu:

- **`dataHora` tem precisão de segundo** (`2026-07-10T13:31:55.000Z`). Os 75
  movimentos dão 75 chaves distintas — nenhuma colisão. Na tela vários
  parecem repetidos porque a impressão trunca a data, mas são movimentos
  diferentes no mesmo dia. Conferido, não suposto;
- **movimento não é intimação, e a lista mostra por quê**: aparecem
  "Publicação" e "Disponibilização no Diário da Justiça Eletrônico" como
  movimentos, dias depois do ato. Serve para saber que andou; não serve para
  contar prazo.

## 5. O que ele não entrega

- **não tem parte**: nada de nome nem de CPF. O vínculo CPF↔processo é sempre
  nosso, nunca dele. É o que mantém o CPF como chave de busca na nossa base e
  não como chave de descoberta contra o tribunal;
- **não tem peça**: só metadado e lista de movimentos (nome e data);
- **defasagem de ~1 dia**;
- **não é intimação**: movimento no DataJud não serve para contar prazo.
