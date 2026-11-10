# `oportunidade`: o veredicto guardado, e a prova de por que mudou

> Segunda metade do T11. A primeira foi o apagamento a pedido.
> Escrito em 02/11/2026.

## O que existe hoje

A tabela `oportunidade` está no esquema desde o checkpoint 9 e **ninguém
escreve nela**. O comentário acima dela diz o que ela promete:

> O VEREDICTO DO MOTOR, e `catalogo_versao` é o que torna o produto
> auditável: quando o STJ julgar o Tema 1.302, a gente reavalia e quem
> estava FALTA vira PODE — com a prova de por que mudou. Sem este campo, o
> veredicto de ontem é inexplicável hoje.

Medido nos dois bancos: **zero linhas.** No Supabase de São Paulo também.

## A dependência do T1, dita direito

> **CORREÇÃO DE 10/11/2026 — o que esta seção afirma abaixo está ERRADO num
> ponto, e fica escrito para o erro ser visível.** Ela diz que a
> homologação vai mostrar `FALTA → PODE`. Não medi quando escrevi. Medido
> depois (`docs/auditoria_do_produto.md`, item 1): com tudo homologado, o
> resultado continua `FALTA`, porque nenhum caminho do produto preenche o
> rol de substituídos, e o motor exige sabê-lo. **A homologação sozinha
> produz zero `PODE`.** O desenho da tabela e a razão de guardar o
> veredicto continuam valendo; a previsão sobre o primeiro efeito, não.

O T11 estava registrado como "depende do T1, porque hoje o motor não emite
nenhum `PODE` para persistir". Isso está certo e **não é um bloqueio** — e
ler direito muda o rumo desta entrega.

O motor emite `FALTA` e `NAO_PODE` hoje, e são eles que alimentam os
gargalos do painel. O que não existe é `PODE`, porque nada está homologado.
Então:

**a primeira transição de verdade que esta tabela vai registrar é a própria
homologação.** No dia em que um advogado marcar `homologado = "S"` e subir a
`versao` do catálogo, a reavaliação vai mostrar `FALTA → PODE` para todo
mundo que a tese alcança. Construir isto agora não é adiantar-se ao T1: é
montar o instrumento que vai MEDIR o efeito do T1 quando ele acontecer —
e sem o instrumento pronto antes, o efeito passa e ninguém consegue provar
qual catálogo produziu o quê.

**O que fica limitado, explicitamente:** até a homologação, a tabela guarda
`FALTA` e `NAO_PODE`. Nenhuma tela vai dizer "você pode" porque o motor não
diz, e isso é o comportamento correto, não uma pendência desta entrega.

## Dois achados que mudam o desenho

### 1. `catalogo_versao integer` está errado, e carrega a hipótese de um contrato só

O motor **já tem** o que a coluna queria ser:

```python
@property
def assinatura(self) -> str:
    """Quais catálogos, em que versão, produziram um veredicto.
    Vai junto do veredicto guardado."""
    return " ".join(f"{slug}@{self.versoes[slug]}" for slug in sorted(...))
```

`assinatura` devolve `"auditor-fiscal-receita-federal@2 analista@1"`. A
coluna é `integer`. Um sindicato com duas carreiras tem **duas versões**, e
não há inteiro que as represente — é a mesma hipótese de cliente único que o
catálogo já abandonou quando deixou de ser um arquivo só.

**Decisão:** a coluna vira `catalogo_assinatura text`. A tabela está vazia
nos dois bancos, então a troca não perde nada.

### 2. Versão declarada à mão não basta — e o próprio catálogo já registra isso

O TOML diz, no comentário da própria `versao`:

> 2: o catálogo virou um arquivo por categoria [...] Antes o topo dizia
> "Auditores-Fiscais ..." e a ação dizia "Auditor-Fiscal ...": **ninguém
> conferia, e nada casava.**

Guardar "este veredicto saiu do catálogo @2" vale exatamente o cuidado de
quem editou o arquivo. Editar o conteúdo e esquecer de subir a versão
produz dois veredictos diferentes citando a mesma origem — e aí a prova de
auditoria é falsa, que é pior que não ter prova.

**Decisão:** guardar também uma **impressão digital medida do conteúdo**
(`catalogo_digest`), e **recusar gravar quando o conteúdo mudou e a
assinatura não**. A própria tabela é a memória: se já existe linha com
assinatura `slug@2` e digest `X`, e o catálogo de agora diz `slug@2` com
digest `Y`, a declaração está mentindo. Falha fechado, com a mensagem
dizendo qual arquivo subir de versão.

## Desenho

### A tabela é APPEND-ONLY, e a assinatura entra na chave

```sql
PRIMARY KEY (entidade, cpf, trilha, referencia, catalogo_assinatura)
```

Uma reavaliação sob catálogo novo **insere** uma linha nova em vez de
sobrescrever a antiga. Consequências, todas desejadas:

- **o histórico é a tabela**, e a transição é uma consulta entre duas
  linhas. Não precisa de tabela de mudança nem de coluna
  `veredicto_anterior`;
- o veredicto antigo **não é recalculável**: o catálogo que o produziu pode
  já ter sido editado em disco. Então ele tem de ser guardado, não derivado
  — é o mesmo argumento do diário append-only;
- cresce de forma medível: uma linha por pessoa, por oportunidade, por
  versão de catálogo. A 10 mil pessoas, 5 oportunidades e 3 versões por ano
  são 150 mil linhas/ano, contra os 4,6 KB/pessoa já medidos. Não é problema
  de escala; se um dia for, a poda é por assinatura antiga.

**Limitação declarada:** sob a MESMA assinatura, uma reavaliação sobrescreve
(upsert na chave). Então `FALTA → PODE` causado pela PESSOA completando o
cadastro — e não pelo catálogo — não deixa linha nova. Isso é deliberado:
esta tabela responde "qual catálogo produziu qual veredicto", e a história
das afirmações da pessoa já é append-only em `pessoa_afirmacao`.

### Onde se escreve

**Não em `banco.reconstruir`.** Ela é a operação de recuperação, projeta o
diário e não conhece catálogo. Acoplar o veredicto a ela faria a recuperação
depender de um arquivo de configuração — e uma recuperação que falha porque
o catálogo mudou é uma recuperação que não existe.

Em vez disso, o caminho que o repositório já usa para trabalho periódico:

```
ferramentas/reavaliar_oportunidades.py     o que alguém roda à mão
      ↑
tarefa "reavaliar" no agendador            chama a MESMA ferramenta
```

É a regra que `agenda.tarefas_padrao` já escreve: *"o agendador não é um
segundo caminho para a mesma coisa. Dois caminhos divergem, e o que roda
sozinho é o que ninguém olha."*

### O que a pessoa recebe: nada

**Nada nominal sai sem homologação humana**, e esta entrega não manda
e-mail a ninguém. Ela registra, e mostra ao **sindicato** quantas
oportunidades mudaram e quais. Quem fala com o filiado é o sindicato, e a
decisão de avisar é dele — com advogado, não com cron.

## Escopo

| | o quê |
|---|---|
| 1 | migração: `catalogo_versao` sai, entram `catalogo_assinatura` e `catalogo_digest`; a chave primária passa a incluir a assinatura |
| 2 | `Catalogo.digest`: impressão digital MEDIDA do conteúdo dos arquivos |
| 3 | `banco.registrar_oportunidades` — grava, idempotente, e RECUSA quando o conteúdo mudou e a assinatura não |
| 4 | `banco.oportunidades_de` e `banco.mudancas` — a leitura e a transição |
| 5 | `ferramentas/reavaliar_oportunidades.py` |
| 6 | tarefa `reavaliar` no agendador |
| 7 | o painel do sindicato mostra o que mudou |

## O que esta entrega NÃO faz

- **não avisa o filiado** (acima);
- **não poda** linhas de assinatura antiga — quando for preciso, é poda por
  assinatura, e hoje seria código sem uso;
- **não registra transição causada pela própria pessoa** sob a mesma
  assinatura (acima);
- **não faz nada aparecer como `PODE`** — isso depende do T1, e é do
  advogado.
