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
   a lista do sindicato    ler o que os documentos    de quais ações ela
   + o que o filiado  -->  dizem: trânsito,       --> PARTICIPA, e o que
     manda no site         dispositivo, período       pode fazer em cada uma
```

**O cruzamento é o miolo.** A ação coletiva alcança uma categoria, num
período. Os comprovantes de contribuição provam o período de filiação.
Cruzar os dois responde a pergunta que o filiado faz primeiro — *de quais
ações eu faço parte?* — e só então vem *e o que posso fazer nelas?*.

E filiação parcial é participação parcial: quem foi filiada de 2005 a 2006
participa de uma ação que cobre 2003 a 2008, **mas só por aqueles 20 meses**.
É dessa interseção que o valor sai depois.

| Caixa | Estado | O que falta |
|---|---|---|
| **1. Entrada** | **PRONTA** | nada |
| **2. Entendimento** | **PRONTA, sem as fichas** | ler as fichas financeiras (é a caixa 4) |
| **3. Veredicto** | **PRONTA, sem o valor** | o valor é a caixa 4 |
| **4. Valor** | **não existe** | quanto, com humano assinando |

A caixa 1 está pronta de verdade: o portal recebe e confere documento no
aparelho da pessoa, o servidor valida e grava, a ingestão engole a planilha
suja do sindicato sem perder linha, e o acompanhamento de processo por número
funciona contra o DataJud.

A caixa 2 lê o PDF e tira dele número do processo, trânsito em julgado,
dispositivo, órgão julgador, período, valores e CPF — **cada achado com o
trecho de onde saiu**, para um humano conferir sem abrir o documento. Nada
que não tenha conferência própria (dígito verificador, frase inequívoca)
alimenta o motor sozinho.

A caixa 3 cruza isso com o catálogo de entendimentos e devolve, por pessoa, o
que ela pode executar e o que pode ajuizar — com o motivo de cada "não".

**Dois PDFs entram e "PODE executar" sai, sem ninguém digitar nada.** É o
teste `teste_do_pdf_ao_veredicto_sem_ninguem_digitar`.

**Falta a caixa 4: o valor.** É a parte perigosa, e por isso é a última.

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

Em `config/categorias/`, **um arquivo por categoria**: a ação coletiva e a
tese alcançam uma carreira, e um catálogo único só atende um cliente. O
sindicato declara em `entidades.json` quais categorias contratou, e é só
delas que o filiado dele recebe veredicto. Como entra uma categoria nova está
em `config/categorias/LEIA.md`.

As da carreira de Auditor-Fiscal, levantadas em 29/10/2026, com fonte:

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
brasileira. Existe trava de código que recusa entidade real fora do Brasil —
não é promessa, é impedimento.

**Esta frase já foi falsa pela metade, e vale registrar.** A trava morava em
`app._entidade`, que só é chamada por rota HTTP; o laço do agendador
resolvia entidade por `Cadastro.todas()` e não passava por ela. Auditoria
independente observou o mesmo servidor devolver 403 para um sindicato e, no
mesmo processo, ler os dados nominais dele e mandar o e-mail com
movimentação processual. A decisão agora é uma só — `entidades.atendivel` —
e os dois caminhos a chamam.

---

## O que está travado e não depende de mim

1. **Acesso ao GitHub** — `git push` responde 403. Reconectar em
   `claude.ai/connect-github`.
2. **Quem preenche o catálogo** — eu levantei cinco temas com fonte; quem
   marca `homologado = "S"` é advogado.
3. **Uma exportação real de sindicato** — a ingestão foi construída contra
   planilha que eu mesmo sujei imitando Excel brasileiro.
