# Como entra uma categoria nova

Um arquivo por categoria. **O nome do arquivo é o slug**, e é por ele que o
sindicato declara o que contratou.

Fechar contrato com um sindicato de outra carreira é **acrescentar um arquivo
aqui**. Não é mexer em Python — e existe um teste que falha se voltar a ser.

---

## Os dois passos

**1. O arquivo da categoria.** `config/categorias/<slug>.toml`:

```toml
[catalogo]
versao        = 1
levantado_em  = "2026-11-05"
categoria     = "Policial Militar do Distrito Federal"   # o nome canônico
cargos = [                       # como a carreira aparece escrita por aí
  "policial militar do distrito federal",
  "policial militar",
  "pmdf",
]
```

**2. O sindicato declara.** Em `<raiz>/entidades.json`:

```json
{
  "demo-pmdf": {
    "nome": "Sindicato de Exemplo",
    "categorias": ["policial-militar-df"]
  }
}
```

Pronto. Daí para frente o motor avalia os filiados dessa entidade contra as
ações e os entendimentos **dessa** categoria, e só dessa.

---

## O que cada campo decide, e o que acontece se faltar

| Campo | O que ele decide | Se faltar |
|---|---|---|
| `categoria` | o nome canônico, contra o qual o cargo da pessoa é comparado | o catálogo é recusado: catálogo sem categoria é catálogo de ninguém e, na prática, de todos |
| `cargos` | quais grafias são reconhecidas como essa carreira | o catálogo é recusado: sem grafia, todo filiado da carreira fica `INDETERMINADO` para sempre |
| `versao` | qual catálogo produziu um veredicto guardado | assume 0, e a auditoria perde a referência |

**`cargos` é para crescer.** Enquanto uma grafia não estiver lá, o cargo é
`INDETERMINADO` — nunca recusado. Recusar por diferença de grafia é tirar
direito de alguém por causa de um hífen. Acrescentar grafia é o trabalho
normal de quem opera o produto.

---

## As três coisas que o carregamento recusa

Rodam sobre a **pasta inteira**, mesmo quando a entidade contratou uma
categoria só: são defeitos que põem pessoa na carreira errada, e um defeito
desses não pode ficar esperando o contrato que o revele.

1. **a mesma grafia em duas categorias.** Uma venceria por ordem de leitura do
   diretório, e a pessoa iria para a carreira errada sem nada reclamar;
2. **o mesmo `id` em dois arquivos.** O motor pegaria um dos dois — qual,
   depende do diretório;
3. **ação ou entendimento declarando categoria diferente do arquivo.**
   Contaminação cruzada escrita à mão.

---

## Uma categoria sem nenhuma entrada é legítima

`analista-tributario-receita-federal.toml` não tem ação nem entendimento, e é
isso que ele é: a declaração de que a carreira **existe e é outra**.

Sem ele, um Analista Tributário que digitasse o cargo sairia como *"confirmar
a carreira"*. Com ele, sai como *"esta não é a sua carreira"* — que é
resposta. E funciona mesmo para um sindicato que não contratou essa categoria:
saber que a carreira existe é conhecimento do mundo, não do contrato.

**Declarar a existência de uma carreira não afirma nada sobre o direito de
ninguém. Inventar ação ou entendimento afirmaria** — e nada entra aqui sem
fonte conferida e sem `homologado = "S"` por advogado.

---

## O que NÃO decide isto aqui

Quais ações e quais entendimentos entram na categoria é decisão do jurídico,
com fonte citada. O catálogo de hoje tem `homologado = "N"` em tudo, e com
isso o motor **não autoriza nada** — corretamente.
