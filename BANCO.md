# O banco de dados, de ponta a ponta

> Companheiro do `MAPA.md`. O mapa diz o que o produto faz; este diz como os
> dados entram, onde ficam, como saem, e por que a promessa de segurança é
> verificável em vez de ser propaganda.

---

## A pergunta que isto responde

*"As informações vão entrar lá, vão se organizar de forma aleatória, a gente
faz o pull com filtro?"*

**Não.** Dado não cai num monte para ser filtrado depois. Filtrar depois é
exatamente como se vaza: basta uma consulta nova esquecer o filtro.

Aqui o dado passa por **três camadas**, cada uma com uma responsabilidade, e
o isolamento entre sindicatos é imposto **pelo banco**, não pela consulta.

```
  CAMADA 1               CAMADA 2                 CAMADA 3
  RECEBIMENTO            FATOS                    CONSULTA
  ───────────            ─────                    ────────
  o que chegou,          o que isso quer          o que a tela
  exatamente como        dizer, com a             pergunta
  chegou                 procedência de
                         cada campo
  append-only            derivada,                derivada,
  imutável               reconstruível            reconstruível
```

Se a camada 2 ou a 3 corromper, apaga e reconstrói da 1. Se a 1 se perder,
perdeu-se o dado. É por isso que só ela é imutável.

---

## Camada 1 — Recebimento

Uma linha por **coisa que chegou**. Nada é editado, nunca.

```sql
recebimento(
  id, entidade, tipo, recebido_em, origem, payload jsonb, sha256
)
```

`tipo` é `acervo` (a planilha do sindicato) ou `cadastro` (o filiado pelo
site). `payload` é o que chegou, inteiro, sem interpretação. `sha256` é a
impressão digital, para provar que não mudou.

**Por que guardar o bruto:** quando o cadastro de alguém sair errado, a
pergunta é *"o que exatamente nos mandaram?"*. Sem a camada 1 a resposta é
"não sei, já tratamos".

---

## Camada 2 — Fatos, com procedência

Aqui está a decisão de desenho que mais importa, e ela vem de uma regra do
produto: **quando o sindicato e o filiado discordam, ninguém decide sozinho.**

Isso é impossível numa tabela larga de pessoa, porque gravar o segundo valor
apaga o primeiro. Então são duas tabelas:

```sql
-- toda afirmação que alguém já fez sobre alguém, nunca sobrescrita
pessoa_afirmacao(
  entidade, cpf, campo, valor, fonte, recebimento_id, afirmado_em
)

-- o valor vigente, derivado: o que a tela lê
pessoa(
  entidade, cpf, nome, email, cargo, situacao, ..., tem_divergencia bool
)
```

`fonte` é `acervo` ou `cadastro`. Quando as duas discordam num campo,
`pessoa` mantém o do acervo, `tem_divergencia` fica verdadeiro, e as duas
afirmações continuam em `pessoa_afirmacao` para o sindicato homologar.

**A exceção que não é negociável:** o e-mail do portão vem do rol do
sindicato, sempre. O filiado propõe; quem homologa é o sindicato. Se o
filiado pudesse trocar o próprio e-mail, o código de acesso viraria enfeite.

---

## Camada 3 — Consulta

O resto é derivado e existe para a tela não fazer conta:

```sql
processo(entidade, numero, tribunal)
vinculo(entidade, cpf, numero, fonte)        -- quem acompanha o quê
movimento(entidade, numero, grau, data, nome)
oportunidade(entidade, cpf, trilha, referencia, veredicto, motivos,
             catalogo_versao, avaliado_em)
```

**`oportunidade` guarda a versão do catálogo que a produziu**, e isso é o
que torna o produto auditável: quando o STJ julgar o Tema 1.302, a gente
reavalia, e quem estava `FALTA` vira `PODE` — **com a prova de por que
mudou**. Sem esse campo, o veredicto de ontem é inexplicável hoje.

---

## O isolamento, e por que ele é verificável

Toda tabela tem `entidade`. Toda tabela tem política. A aplicação **nunca**
escreve `WHERE entidade = ...` — ela declara quem é no começo da transação e
o banco faz o resto:

```sql
SELECT set_config('app.entidade', 'sindicato-x', true);
SELECT cpf FROM pessoa;        -- sem WHERE: já vem só do sindicato-x
```

Uma consulta nova que esqueça o filtro devolve **zero linhas**, não as
linhas de outro sindicato. É a diferença entre "a gente toma cuidado" e "não
dá para errar".

**E uma coisa que eu descobri medindo, não lendo:** superusuário do Postgres
**ignora RLS por completo**, inclusive com `FORCE`. A URL que a Supabase
entrega por padrão conecta como `postgres`, que é privilegiado — então
políticas perfeitas protegeriam exatamente nada. Por isso toda consulta faz
`SET LOCAL ROLE protocol_app` antes de qualquer coisa, e há teste que
reprova se isso cair.

---

## Onde isso roda, e o que eu recomendo

**Supabase, em São Paulo (`sa-east-1`), usada como Postgres gerenciado — e
só isso.**

| | |
|---|---|
| **a favor** | Postgres de verdade, RLS nativo, região brasileira, backup gerenciado, barato no começo |
| **contra, e tem de ser dito** | a Supabase expõe uma API REST automática sobre as tabelas. Se a política estiver errada, a tabela está na internet |

**A configuração que eu recomendo, e as três linhas importam:**

1. **Desligar a Data API** (a REST automática). Quem fala com o banco é o
   nosso servidor, mais ninguém. Uma superfície a menos é uma superfície a
   menos.
2. **Nunca usar a chave `service_role`** na aplicação — ela existe
   justamente para passar por cima do RLS.
3. **Conectar com um papel próprio**, `protocol_app`, sem `BYPASSRLS` e dono
   de nada.

Com isso, a Supabase vira "Postgres gerenciado em São Paulo com backup", que
é exatamente o que a gente precisa, sem a parte que assusta.

**Alternativas, se você preferir não depender dela:** AWS RDS em `sa-east-1`
(mais caro, mais trabalho, zero surpresa), ou um provedor nacional. O
esquema é Postgres puro — `esquema.sql` roda em qualquer um dos três, sem
mudar uma linha. **Isso é de propósito:** nada aqui usa recurso exclusivo da
Supabase, então trocar de provedor é mudar uma variável de ambiente.

---

## A propaganda, e o que a sustenta

Você quer vender "banco de dados seguro, que não tira proveito dos dados dos
filiados". Isso só vale se for verificável. Cada linha abaixo tem uma coisa
no código que a sustenta:

| O que se promete | O que sustenta |
|---|---|
| **Um sindicato nunca vê os dados de outro** | RLS com `FORCE`, política em toda tabela, papel sem `BYPASSRLS`. Teste que lê sem declarar entidade e exige zero linhas |
| **Nós mesmos não cruzamos dados entre sindicatos** | a mesma política vale para a aplicação. Para fazer um produto agregado seria preciso mudar o esquema e o papel — mudança que aparece no histórico do Git |
| **O dado fica no Brasil** | região `sa-east-1`, e trava de código que recusa atender entidade real fora de região brasileira |
| **Ninguém entra no lugar de ninguém** | sem senha: código de 6 dígitos no e-mail que o **sindicato** cadastrou |
| **A coleta no tribunal não leva dado de ninguém** | o coletor toca só número de processo e movimento. Sem CPF, sem nome, sem entidade |
| **O sindicato leva os dados dele embora quando quiser** | exportação por entidade, e é a mesma consulta que o painel já faz |
| **Apagamos quando pedirem** | ver abaixo — e aqui há um problema real a resolver |

---

## O problema do apagamento, dito de frente

Filiação sindical é dado sensível (LGPD, art. 11). Um pedido de eliminação
(art. 18, VI) tem de ser atendido.

**E isso conflita com a camada 1 ser append-only.** Hoje, no arquivo
`acervo.jsonl`, cada ingestão guarda uma cópia inteira da base — de milhares
de pessoas que nunca usaram o portal. Apagar uma pessoa exigiria reescrever o
arquivo, quebrando a propriedade que o torna confiável.

**A saída, no banco:** `DELETE` por pessoa é permitido na camada 1, e deixa
um **tombstone** — linha dizendo *quem foi apagado, quando, a pedido de
quem* —, sem o dado. O log para de ser imutável e passa a ser *auditável*,
que é o que a lei pede. Append-only vira "não se edita", não "não se apaga
nunca".

Se você quiser a camada 1 verdadeiramente imutável, existe o caminho de
cifrar o payload por pessoa e, no pedido de eliminação, destruir a chave — o
dado continua lá e vira ruído. É mais caro e mais difícil de operar. Minha
recomendação é o tombstone.

---

## Retenção

Nada disso funciona sem prazo. Proposta, para o jurídico aprovar ou mudar:

| Dado | Prazo |
|---|---|
| recebimento (camada 1) | 5 anos, ou até o fim do contrato com o sindicato + 6 meses |
| documentos (PDF) | enquanto houver caso ativo; depois, 6 meses |
| log de leitura | 1 ano |
| pessoa / fatos | enquanto durar o contrato |

Sem prazo declarado, a resposta a "por quanto tempo vocês guardam?" é "para
sempre", e essa é a pior resposta possível numa negociação com sindicato.

---

## O que falta, para não parecer pronto

1. **O log de leitura existe como tabela e nada escreve nele.** Num produto
   de consulta o vazamento é um `read`, e hoje "quem viu o dado de quem" não
   tem resposta.
2. **A migração do diário em disco para o banco não foi feita.** As telas de
   hoje leem o arquivo. O banco está testado e vazio.
3. **Nenhum prazo de retenção foi aprovado** por ninguém.
4. **A trava de região existe; a migração para São Paulo não aconteceu.** O
   servidor segue em Virginia, atendendo só demonstração.
