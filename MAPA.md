# PROTOCOL — Produto B. O mapa.

> Uma página. Se alguma coisa que eu escrever em outro arquivo contradisser
> esta, esta vence.

---

## O que a empresa vende

**O sindicato manda a lista de filiados. O filiado manda os documentos dele.
Nós dizemos, nome por nome: o que você pode executar, o que você pode
ajuizar, e quanto.**

Dois clientes, um produto:

- **o sindicato** contrata para organizar o acervo que ele já tem e para
  enxergar a base dele;
- **o filiado** entra num site, manda os documentos, e recebe a resposta.

---

## As três caixas

Tudo neste produto é uma destas três, e só estas três.

```
   1. ENTRADA              2. ENTENDIMENTO            3. VEREDICTO
   ----------              ---------------            ------------
   a lista do sindicato    ler o que os documentos    cruzar com as regras
   + o que o filiado  -->  dizem: cargo, período, --> e dizer, nome por nome:
     manda no site         verba, trânsito            pode executar? ajuizar?
                                                      quanto?
```

| Caixa | Estado | O que falta |
|---|---|---|
| **1. Entrada** | **PRONTA** | nada |
| **2. Entendimento** | **não existe** | ler a sentença e as fichas e extrair os fatos |
| **3. Veredicto** | **não existe** | o motor que cruza fatos × regras |

A caixa 1 está pronta de verdade: o portal recebe e confere documento no
aparelho da pessoa, o servidor valida e grava, a ingestão engole a planilha
suja do sindicato sem perder linha, e o acompanhamento de processo por número
funciona contra o DataJud. Tudo testado.

**As caixas 2 e 3 são o produto, e nenhuma das duas existe.** É aí que vai
todo o trabalho a partir de agora.

---

## A caixa 3, destrinchada

O veredicto tem **duas trilhas**, e misturá-las é o erro mais caro possível.

| | EXECUTAR | AJUIZAR |
|---|---|---|
| exige título? | **sim** — sentença transitada em nome da pessoa, ou coletiva em que ela é substituída | **não** |
| o que basta | o título + enquadramento + não ter executado antes | enquadrar-se no entendimento + não ter ação própria |
| quem é | quem já ganhou e não recebeu | quem nunca entrou |
| população | menor | maior |

Dizer "você pode executar" para quem tem tese favorável e nenhum título cria
expectativa de dinheiro em gente aposentada. Esse erro não se conserta.

---

## As regras que o motor usa

Em `config/entendimentos.toml`, levantadas em 29/10/2026, com fonte:

| Tema | O que decide | Situação |
|---|---|---|
| STJ **1.169** | dispensa liquidação prévia na execução | julgado |
| STJ **1.302** | se quem está fora do rol pode executar | **afetado, com suspensão nacional** |
| STJ **1.299** | 28,86% sobre a RAV, carreira de Auditor-Fiscal | julgado |
| STF **1.119** | alcance da coisa julgada coletiva | julgado |
| STJ **1.410** | prescrição do fundo de direito | a conferir |

E um título real e vivo: a coletiva da **GIFA**,
`0010391-24.2006.4.01.3400`, transitada, 600 movimentos no DataJud.

---

## A ordem do trabalho

Uma coisa de cada vez, e cada uma só começa quando a anterior tem teste
passando.

| | O quê | Entrega |
|---|---|---|
| **1** | **Motor do veredicto, sem valor** | dada uma pessoa, a lista do que ela pode executar e ajuizar, com o motivo de cada "não" |
| **2** | **Leitura dos documentos** | a sentença e as fichas viram fatos que o motor usa, em vez de o filiado digitar tudo |
| **3** | **Valor** | quanto, com humano assinando |
| **4** | **Tela** | mostrar isso para os dois lados |

A tela é a última de propósito. Já construí tela antes do motor uma vez nesta
sessão, e foi erro.

---

## As duas coisas difíceis, ditas de frente

**1. O valor é a parte perigosa.** Dizer "você pode executar" é informação.
Dizer "você tem R$ 180 mil a receber" é uma promessa, e um número errado
numa população de aposentados não se conserta com atualização de software.
Por isso o valor é a etapa 3 e não a 1, e por isso ele sai com assinatura de
gente.

**2. Nada nominal sai sem um advogado homologar.** O motor prepara; quem
assina é humano. Todo entendimento no catálogo nasce com `homologado = "N"` e
não produz veredicto até alguém marcar `"S"`.

---

## Onde cada coisa roda

| Onde | O quê | Observação |
|---|---|---|
| Netlify `protocol-portal-demo` | o site do filiado | recebe `dist` pronto, sem repositório ligado |
| Netlify `protocol-site-demo` | a landing | desatualizada |
| Render `protocol-servidor-demo` | o servidor | builda do GitHub, branch `main`, **região Virginia (EUA)** |

Antes do primeiro sindicato real o servidor precisa ir para região
brasileira. Já existe trava de código que recusa entidade real fora do
Brasil — não é promessa, é impedimento.

---

## O que está travado e não depende de mim

1. **Acesso ao GitHub** — `git push` responde 403. Reconectar em
   `claude.ai/connect-github`.
2. **Quem preenche o catálogo** — eu levantei cinco temas com fonte; quem
   marca `homologado = "S"` é advogado.
3. **Uma exportação real de sindicato** — a ingestão foi construída contra
   planilha que eu mesmo sujei imitando Excel brasileiro.
