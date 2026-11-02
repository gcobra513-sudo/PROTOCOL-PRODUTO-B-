# Apagamento a pedido — plano de implementação

> **Para quem executa:** SUB-SKILL OBRIGATÓRIA — use
> `superpowers:subagent-driven-development` (recomendada) ou
> `superpowers:executing-plans` para implementar tarefa por tarefa. Os
> passos usam `- [ ]` para acompanhamento.

**Objetivo:** atender pedido de eliminação (LGPD art. 18, VI) apagando o
filiado do banco, do disco e do diário, deixando um tombstone, e provando
pela medição que não sobrou nada.

**Arquitetura:** um módulo novo, `servidor/apagamento.py`, orquestra; cada
formato é removido por quem já o conhece (`deposito` o diário, `rol` os CSV,
`acervo` o `acervo.jsonl`, `banco` as tabelas). A ordem é
tombstone → diário → disco → banco, porque o diário é a autoridade e apagar
o banco antes deixa a `reconstruir` ressuscitar a pessoa. Não existe campo
"apagado": existe `vestigios()`, que mede.

**Pilha:** Python 3.13, psycopg3, Postgres 16/17, FastAPI. Sem dependência
nova.

**Spec:** `docs/superpowers/specs/2026-11-02-apagamento-a-pedido-design.md`

## Restrições globais

- **Teste antes do código, e ver o teste falhar pelo motivo certo.** Todo
  passo de implementação é precedido de um passo de teste vermelho.
- **Rodar a suíte inteira antes de dizer que algo está pronto:**
  `PROTOCOL_DATABASE_URL='...' python3 tests/rodar_todos.py`. Sem a
  variável a parte de banco é PULADA, e suíte pulada não está testada.
- **Nenhum CPF em claro em log, resposta ou tombstone.** Marcador é
  `portao.marcar_cpf(cpf)`; marcador curto para log é `_hash_curto`.
- **Nenhum dado pessoal real em teste.** CPF sintético com dígito válido,
  nome marcado `(CADASTRO FICTÍCIO)`, domínio `.invalid`/`.example`.
- **Comentário explica o PORQUÊ da decisão**, não o que a linha faz.
- **`leitura`, `processo` e `movimento` NÃO são apagados.** A spec diz por
  quê; nenhuma tarefa os toca.
- O esquema **não** ganha coluna de conclusão. Conclusão é `vestigios()`
  devolvendo vazio.

## Foco de revisão

Cinco classes de entrada que a spec implica e que precisam de teste
explícito, da mais provável para a menos:

1. **CPF formatado** (`529.982.247-25`) no pedido. Sem normalizar, nada é
   encontrado e a rota diz que apagou. → teste na Tarefa 10.
2. **CPF que não está na base.** Deve responder como qualquer outro, sem
   `404`: um `404` aqui é **oráculo** — revela quem está na base de um
   sindicato a quem já tem sessão de gestor de outra. → teste na Tarefa 10.
3. **Banco fora do ar.** O tombstone não grava, e então **nada é apagado** —
   falha fechada. Apagar sem registro é o pior resultado possível. → teste
   na Tarefa 6.
4. **`acervo.jsonl` com várias ingestões** contendo a mesma pessoa. É uma
   linha por INGESTÃO, com `pessoas` dentro: a remoção tem de varrer
   TODAS. → teste na Tarefa 4.
5. **Documentos em `historico/<cpf>/`** de reenvios anteriores.
   `vestigios` tem de olhar lá, senão sobra PDF de sentença em disco. →
   teste na Tarefa 5.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `servidor/apagamento.py` **(novo)** | orquestra a ordem; `vestigios()` |
| `servidor/banco.py` | tombstone, exclusão das tabelas, filtro na `reconstruir` |
| `servidor/deposito.py` | redação no diário (ele é dono do diário e da trava) |
| `servidor/rol.py` | remoção nos CSV (ele é dono do formato e do dialeto) |
| `servidor/acervo.py` | remoção no `acervo.jsonl` |
| `servidor/app.py` | a rota, a contagem no painel, o tombstone no portão |
| `ferramentas/ingerir_acervo.py` | pular CPF apagado e relatar |
| `ferramentas/apagar_filiado.py` **(novo)** | retomada pelo operador |
| `tests/testes_apagamento.py` **(novo)** | tarefas 1 a 8 |

---

### Tarefa 1: o tombstone no banco

**Arquivos:** modificar `servidor/banco.py`; testar em
`tests/testes_apagamento.py` (criar).

**Interfaces — produz:**
- `marcar_tombstone(url: str, entidade: str, cpf_hash: str, motivo: str, pedido_por: str) -> None`
- `tombstones(url: str, entidade: str) -> set[str]` — os `cpf_hash` apagados

- [ ] **Passo 1: escrever o teste que falha**

```python
def teste_o_tombstone_guarda_o_pedido_e_nunca_o_cpf():
    banco.marcar_tombstone(URL, "demo-a", "marcador-de-teste",
                           motivo="pedido do titular",
                           pedido_por="gestor@exemplo.invalid")
    checa(banco.tombstones(URL, "demo-a") == {"marcador-de-teste"}, ...)
    with banco.sessao(URL, "demo-a") as cur:
        cur.execute("SELECT motivo, pedido_por FROM tombstone")
        checa(cur.fetchone() == ("pedido do titular",
                                 "gestor@exemplo.invalid"), ...)
```

- [ ] **Passo 2: rodar e confirmar que falha**

Rodar: `PROTOCOL_DATABASE_URL='...' python3 tests/testes_apagamento.py`
Esperado: FALHA com `AttributeError: module 'servidor.banco' has no attribute 'marcar_tombstone'`

- [ ] **Passo 3: implementar as duas em `servidor/banco.py`**

Ambas por `with sessao(url, entidade)`. `tombstones` devolve `set`, não
lista, porque o uso é pertinência em laço de ingestão.

- [ ] **Passo 4: rodar e confirmar que passa**
- [ ] **Passo 5: acrescentar `tests/testes_apagamento.py` a `tests/rodar_todos.py` e commitar**

---

### Tarefa 2: as exclusões no banco

**Arquivos:** modificar `servidor/banco.py`; testar em `tests/testes_apagamento.py`.

**Interfaces — produz:**
- `apagar_pessoa(url: str, entidade: str, cpf: str) -> dict[str, int]` — quantas linhas saíram de cada tabela

- [ ] **Passo 1: escrever o teste que falha**

Semeia uma pessoa por `projetar_acervo` e um cadastro por `reconstruir`,
chama `apagar_pessoa`, e afirma:

```python
    saiu = banco.apagar_pessoa(URL, "demo-a", CPF)
    checa(saiu["pessoa_afirmacao"] > 0 and saiu["pessoa"] == 1, ...)
    checa(banco.registro_do_cpf(URL, "demo-a", CPF) is None, ...)
    # leitura, processo e movimento NÃO são tocados
    checa("leitura" not in saiu and "processo" not in saiu, ...)
```

E um segundo teste: **a pessoa de OUTRA entidade com o mesmo CPF continua
intacta** (`registro_do_cpf(URL, "demo-b", CPF) is not None`).

- [ ] **Passo 2: rodar e confirmar que falha**
- [ ] **Passo 3: implementar `apagar_pessoa` em `servidor/banco.py`**

`DELETE ... WHERE cpf = %s` numa transação, nesta ordem, para não violar a
chave estrangeira de `pessoa_afirmacao.recebimento_id`: `achado`,
`documento`, `vinculo`, `oportunidade`, `aviso_enviado`, `pessoa_afirmacao`,
`pessoa`, e por último `recebimento` (pelos `recebimento_id` que restaram
órfãos daquele CPF). Usar `_digitos(cpf)`. Devolve `cur.rowcount` por
tabela.

- [ ] **Passo 4: rodar e confirmar que passa**
- [ ] **Passo 5: commitar**

---

### Tarefa 3: a redação no diário

**Arquivos:** modificar `servidor/deposito.py`; testar em `tests/testes_apagamento.py`.

**Interfaces — produz:**
- `redigir_no_diario(entidade: Entidade, raiz: pathlib.Path, cpf: str) -> int` — quantos registros foram redigidos

- [ ] **Passo 1: escrever o teste que falha**

```python
def teste_a_redacao_mantem_o_protocolo_e_perde_o_conteudo():
    # dois cadastros da mesma pessoa, mais um de outra
    quantos = deposito.redigir_no_diario(ent, raiz, CPF)
    checa(quantos == 2, ...)
    registros = deposito.ler_diario(ent.pasta(raiz))
    meus = [r for r in registros if r.get("apagado_em")]
    checa(len(meus) == 2, ...)
    for r in meus:
        checa(r["protocolo"] and r["recebido_em"], "perdeu o protocolo")
        checa("linha" not in r and "arquivos" not in r, "sobrou conteúdo")
    # o registro da OUTRA pessoa fica intacto
    checa(any(r.get("linha", {}).get("cpf") == OUTRO for r in registros), ...)
```

- [ ] **Passo 2: rodar e confirmar que falha**
- [ ] **Passo 3: implementar `redigir_no_diario` em `servidor/deposito.py`**

Dentro de `_travada(pasta)`. Lê o diário, substitui cada registro cujo
`linha["cpf"]` normalizado casa por
`{"protocolo", "recebido_em", "entidade", "apagado_em"}`, e reescreve o
arquivo inteiro em `.parcial` com `fsync` e `replace`, como
`reconstruir_manifesto` já faz. Depois chama `reconstruir_manifesto`,
porque o manifesto é derivado.

Comentário obrigatório: `reconstruir` já pula registro sem `linha`
(`if not isinstance(linha, dict): continue`) — é isso que faz a redação
bastar sem mudar a projeção.

- [ ] **Passo 4: rodar e confirmar que passa**
- [ ] **Passo 5: commitar**

---

### Tarefa 4: os dois formatos de arquivo

**Arquivos:** modificar `servidor/rol.py` e `servidor/acervo.py`; testar em
`tests/testes_apagamento.py`.

**Interfaces — produz:**
- `rol.remover(pasta_entidade: pathlib.Path, cpf: str) -> int` — linhas tiradas dos dois CSV
- `acervo.remover_pessoa(caminho: pathlib.Path, cpf: str) -> int` — ocorrências tiradas

- [ ] **Passo 1: escrever os testes que falham**

Para o rol: CSV com três filiados e um gestor, remove um, afirma que
`carregar(pasta).email_de(CPF) is None` e que os outros dois continuam
legíveis — inclusive com `;` de Excel em português, que `_carregar` já
detecta.

Para o acervo, **o caso do foco de revisão 4**:

```python
def teste_remove_a_pessoa_de_TODAS_as_ingestoes():
    # acervo.jsonl com DUAS linhas de ingestão, a mesma pessoa nas duas
    quantas = acervo.remover_pessoa(caminho, CPF)
    checa(quantas == 2, f"removeu de só uma ingestão: {quantas}")
    pessoas, _ = acervo.ler(caminho)
    checa(all(p.cpf != CPF for p in pessoas), ...)
    # e as outras pessoas de cada ingestão continuam lá
```

- [ ] **Passo 2: rodar e confirmar que falham**
- [ ] **Passo 3: implementar as duas**

`rol.remover`: reescreve cada CSV preservando cabeçalho e dialeto
detectados, com troca atômica.

`acervo.remover_pessoa`: **o arquivo é uma linha por INGESTÃO, com uma
lista `pessoas` dentro** — não uma linha por pessoa. Varre todas as linhas,
filtra a lista `pessoas` de cada uma, e reescreve. Linha que fica sem
nenhuma pessoa é mantida (ela carrega `retrato` e `origem`, que são sobre o
arquivo e não sobre gente).

- [ ] **Passo 4: rodar e confirmar que passam**
- [ ] **Passo 5: commitar**

---

### Tarefa 5: `vestigios` — a medição

**Arquivos:** criar `servidor/apagamento.py`; testar em `tests/testes_apagamento.py`.

**Interfaces — consome:** `banco.registro_do_cpf`, `banco.sessao`,
`deposito.ler_diario`, `rol.carregar`, `rol.carregar_gestores`,
`acervo.ler`.
**Produz:** `vestigios(url: str, entidade: Entidade, raiz: pathlib.Path, cpf: str) -> list[str]`

- [ ] **Passo 1: escrever o teste que falha**

Semeia uma pessoa **em todos os lugares** — banco, diário, PDF em
`entrega/<cpf>/`, PDF em `historico/<cpf>/<marca>/` (**foco de revisão 5**),
linha no `filiados.csv`, linha no `acervo.jsonl` — e afirma que
`vestigios` nomeia os seis. Depois, numa pessoa que nunca existiu, afirma
que devolve `[]`.

- [ ] **Passo 2: rodar e confirmar que falha**
- [ ] **Passo 3: implementar `vestigios`**

Devolve uma descrição por vestígio encontrado, legível por quem vai
consertar (`"banco: 17 linhas em pessoa_afirmacao"`,
`"disco: entrega/<marcador>/sentenca.pdf"`), **com marcador e nunca o CPF**.
Olha: as tabelas de `apagar_pessoa`, o diário, `entrega/<cpf>/`,
`historico/<cpf>/`, os dois CSV e o `acervo.jsonl`.

- [ ] **Passo 4: rodar e confirmar que passa**
- [ ] **Passo 5: commitar**

---

### Tarefa 6: `apagar` — a ordem e a retomada

**Arquivos:** modificar `servidor/apagamento.py`; testar em `tests/testes_apagamento.py`.

**Interfaces — produz:**
- `apagar(url, entidade: Entidade, raiz, cpf: str, *, motivo: str, pedido_por: str, marcar_cpf) -> dict`
  com as chaves `marcador`, `banco`, `diario`, `arquivos`, `rol`,
  `acervo`, `vestigios`.

`marcar_cpf` é injetado — é `portao.marcar_cpf`, e o módulo não importa o
portão para não acoplar apagamento a autenticação.

- [ ] **Passo 1: escrever o teste que falha — a asserção central da spec**

```python
def teste_depois_de_apagar_nao_sobra_nada():
    # pessoa semeada em todos os lugares, como na Tarefa 5
    saida = apagamento.apagar(URL, ent, raiz, CPF,
                              motivo="pedido do titular",
                              pedido_por="gestor@exemplo.invalid",
                              marcar_cpf=portao.marcar_cpf)
    checa(saida["vestigios"] == [], f"sobrou: {saida['vestigios']}")
    checa(portao.marcar_cpf(CPF) in banco.tombstones(URL, ent.apelido), ...)
    checa(CPF not in json.dumps(saida), "o CPF saiu na resposta")
```

- [ ] **Passo 2: o teste do foco de revisão 3 — falha fechada**

```python
def teste_sem_banco_nada_e_apagado():
    # url inválida: o tombstone não grava
    try:
        apagamento.apagar("postgresql://nao-existe/x", ent, raiz, CPF, ...)
        checa(False, "apagou sem conseguir registrar o tombstone")
    except Exception:
        pass
    checa(deposito.ler_diario(ent.pasta(raiz)), "o diário foi redigido "
          "mesmo sem tombstone — apagamos sem registro")
```

- [ ] **Passo 3: o teste da retomada**

Apaga, depois **repõe à mão** uma linha no `filiados.csv`, e afirma que
`vestigios` a enxerga e que um segundo `apagar` fecha em `[]`.

- [ ] **Passo 4: o teste de apagar duas vezes**

A spec exige (item 10): apagar a mesma pessoa duas vezes **não quebra** e
deixa **dois** tombstones — a tabela é log, e a chave
`(entidade, cpf_hash, apagado_em)` permite. A segunda chamada tem de
devolver `vestigios == []` e contagens zeradas, não erro.

```python
    primeira = apagamento.apagar(...)
    segunda = apagamento.apagar(...)
    checa(segunda["vestigios"] == [], ...)
    with banco.sessao(URL, ent.apelido) as cur:
        cur.execute("SELECT count(*) FROM tombstone")
        checa(cur.fetchone()[0] == 2, "o segundo pedido não ficou registrado")
```

- [ ] **Passo 5: rodar e confirmar que os quatro falham**
- [ ] **Passo 6: implementar `apagar`**

Na ordem da spec: `marcar_tombstone` **primeiro e sozinho** (se levantar,
propaga e nada mais acontece), depois `redigir_no_diario`, depois os
arquivos (`entrega/<cpf>/` e `historico/<cpf>/` por `shutil.rmtree`),
depois `rol.remover` e `acervo.remover_pessoa`, depois `apagar_pessoa`, e
por fim `vestigios`.

- [ ] **Passo 7: rodar e confirmar que passam**
- [ ] **Passo 8: commitar**

---

### Tarefa 7: `reconstruir` consulta o tombstone

**Arquivos:** modificar `servidor/banco.py`; testar em `tests/testes_espelho.py`.

**Interfaces — modifica:** `reconstruir` passa a devolver
`tuple[int, int]` — gravados e pulados por tombstone. **Todos os chamadores
existentes mudam** (`servidor/app.py`, `ferramentas/`, testes).

- [ ] **Passo 1: escrever o teste que falha — o cenário de backup**

```python
def teste_restaurar_backup_nao_ressuscita_quem_foi_apagado():
    # cadastra, guarda uma CÓPIA do diário, apaga, restaura a cópia
    gravados, pulados = banco.reconstruir(URL, ent.apelido,
                                          diario_antes_do_apagamento)
    checa(pulados == 1, f"não pulou o apagado: {pulados}")
    checa(banco.registro_do_cpf(URL, ent.apelido, CPF) is None,
          "a restauração de backup ressuscitou quem pediu para sair")
```

- [ ] **Passo 2: rodar e confirmar que falha**
- [ ] **Passo 3: implementar**

`reconstruir` lê `tombstones(...)` uma vez antes do laço e pula o registro
cujo `marcar_cpf(cpf)` está no conjunto. Precisa do `marcar_cpf` — recebe
como parâmetro opcional `marcar_cpf=None`, e **sem ele não pula nada**,
para não quebrar os chamadores que não têm portão. Comentário dizendo que
chamador de produção passa.

- [ ] **Passo 4: atualizar TODOS os chamadores e rodar a suíte inteira**

Inclui `tests/testes_apagamento.py`, que as tarefas 2 e 6 usam para semear
— ele chama `reconstruir` e passa a receber tupla. `grep -rn
"reconstruir(" --include=*.py .` antes de dizer que terminou.
- [ ] **Passo 5: commitar**

---

### Tarefa 8: a ingestão da planilha pula e relata

**Arquivos:** modificar `ferramentas/ingerir_acervo.py`; testar em `tests/testes_apagamento.py`.

- [ ] **Passo 1: escrever o teste que falha**

Roda a ferramenta por `subprocess` sobre uma planilha com três CPFs, um
deles com tombstone, e afirma que a saída traz
`1 pessoa(s) apagada(s) a pedido — pulada(s)` e que `acervo.ler` do
arquivo gravado não tem aquele CPF.

- [ ] **Passo 2: rodar e confirmar que falha**
- [ ] **Passo 3: implementar**

Com `--banco`, lê `tombstones` e filtra as pessoas antes de gravar. Imprime
a contagem. **Nunca imprime o CPF pulado** — a pessoa pediu para sair.

- [ ] **Passo 4: rodar e confirmar que passa**
- [ ] **Passo 5: commitar**

---

### Tarefa 9: o portão consulta o tombstone

**Arquivos:** modificar `servidor/app.py` (`pedir_codigo`); testar em
`tests/testes_servidor_portal.py`.

- [ ] **Passo 1: escrever o teste que falha**

```python
def teste_nao_sai_codigo_para_quem_foi_apagado():
    # CPF no rol, com tombstone gravado
    apagado = _corpo_comparavel(pedir_codigo(CPF_APAGADO))
    desconhecido = _corpo_comparavel(pedir_codigo(OUTRO_CPF))
    checa(apagado == desconhecido,
          "a resposta revela que este CPF foi apagado")
    checa(enviados == 0, "mandou código para quem pediu para sair")
```

Exige **as duas coisas**: nenhum e-mail, e resposta indistinguível. Recusar
seria oráculo de apagamento.

- [ ] **Passo 2: rodar e confirmar que falha**
- [ ] **Passo 3: implementar**

Depois de resolver `destino` e antes de `correio.enviar`: se
`cfg.tem_banco` e `portao.marcar_cpf(cpf)` está em
`banco.tombstones(cfg.banco_url, ent.apelido)`, trata como
`destino is None` — mesmo `return` de 202, mesma linha de log.

- [ ] **Passo 4: rodar e confirmar que passa**
- [ ] **Passo 5: commitar**

---

### Tarefa 10: a rota, o painel e a ferramenta

**Arquivos:** modificar `servidor/app.py`; criar
`ferramentas/apagar_filiado.py`; testar em `tests/testes_servidor_portal.py`.

- [ ] **Passo 1: escrever os testes de autorização que falham**

Anônimo `401`; filiado da entidade `403`; gestor de **outra** entidade
`403`; gestor da própria `200`. E que o `403` do gestor de outra entidade
vem **antes** de qualquer leitura do `gestores.csv` da entidade alvo —
`_gestor_de` já garante a ordem, o teste a fixa.

- [ ] **Passo 2: os dois testes do foco de revisão 1 e 2**

```python
def teste_apagar_aceita_cpf_formatado():
    r = apagar(apelido, {"cpf": "529.982.247-25", ...})
    checa(r.json()["vestigios"] == [], ...)

def teste_apagar_cpf_que_nao_existe_nao_e_oraculo():
    conhecido = apagar(apelido, {"cpf": CPF_DA_BASE, ...})
    estranho  = apagar(apelido, {"cpf": CPF_DE_FORA, ...})
    checa(conhecido.status_code == estranho.status_code == 200,
          "o status revela quem está na base")
```

- [ ] **Passo 3: rodar e confirmar que falham**
- [ ] **Passo 4: implementar a rota**

`POST /api/entidade/{apelido}/apagar`, corpo `{cpf, motivo, pedido_por}`.
`_gestor_de` primeiro; `validacao.cpf_valido` recusa `400`;
`_auditar(ent, "apagar", quem_hash=sessao.cpf_hash, alvo_hash=marcador)`;
chama `apagamento.apagar`. Responde `{marcador, apagado: {...}, vestigios}`
— **`vestigios` não vazio não vira erro**, vira a resposta honesta de que
sobrou coisa.

- [ ] **Passo 5: a contagem no painel**

`/completude` ganha `apagados_a_pedido: int` — quantos CPFs do
`acervo.jsonl` têm tombstone. **Contagem, nunca lista nominal.**

- [ ] **Passo 6: a ferramenta de retomada**

`ferramentas/apagar_filiado.py --entidade X --cpf Y --motivo Z
--pedido-por W`, e `--conferir` que só roda `vestigios` e imprime. Sai com
código `1` se sobrou vestígio, para servir em script.

- [ ] **Passo 7: rodar a suíte inteira, Python e portal**
- [ ] **Passo 8: commitar**

---

## Ao terminar

- [ ] `PROTOCOL_DATABASE_URL='...' python3 tests/rodar_todos.py` — tudo verde, nada pulado
- [ ] `npm --prefix portal run teste`
- [ ] `CHECKPOINTS.md`: T11 vira "primeira metade pronta", com o commit
- [ ] `servidor/LEIAME.md`: a rota nova e a ferramenta; que o rol é
      colocado à mão (a dívida declarada na spec); e que
      **`PROTOCOL_SEGREDO` é de vida longa** — o tombstone guarda HMAC com
      ele, e trocá-lo faz os tombstones deixarem de casar com os CPFs que
      chegam, devolvendo ao sistema quem pediu para sair. Trocar o segredo
      exige reemitir os tombstones.
