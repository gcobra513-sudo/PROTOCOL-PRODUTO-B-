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
