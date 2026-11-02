# Apagamento a pedido — as decisões que eu tomei, e o que custam se erradas

> Registro do ramo `apagamento-a-pedido` (14 commits, 550c4e3..dacd424).
> Spec: `docs/superpowers/specs/2026-11-02-apagamento-a-pedido-design.md`.
> Plano: `docs/superpowers/plans/2026-11-02-apagamento-a-pedido.md`.
>
> Isto era um arquivo de rascunho ignorado pelo git. Ficou aqui porque
> **três das decisões abaixo foram REVOGADAS pela revisão**, e uma decisão
> revogada vale mais registrada que apagada: ela mostra onde o meu
> raciocínio falhou e por quê.

## As três que foram revogadas

| Decisão original | Quem derrubou | O que ela custava de verdade |
|---|---|---|
| T2: `recebimento` só é apagado quando NINGUÉM mais o referencia | I1 | destruía a ingestão de TERCEIRO (medido: 1 antes, 0 depois). O meu texto afirmava o custo oposto |
| T7: `marcar_cpf` é OPCIONAL e sem ele `reconstruir` não filtra | I5 | ausência do argumento virava "não filtra", então a restauração de backup ressuscitava quem pediu para sair |
| T9: falha ao consultar o tombstone no portão não fecha o portão — loga e segue | I7 | entregava código de acesso a quem pediu para sair. Eu supus duas saídas, passar ou recusar; há uma terceira — tratar a falha DAQUELE pedido como "sem destino" |

**O que as três têm em comum:** cada uma escolheu a disponibilidade contra
a promessa, e em cada uma eu escrevi o custo da escolha errado — não por
falta de cuidado na redação, mas porque não medi antes de afirmar. É a
mesma lição da auditoria, aplicada a decisão em vez de a comentário.

## O ledger, íntegro

```
# SDD ledger — plan: docs/superpowers/plans/2026-11-02-apagamento-a-pedido.md

Pre-flight: varredura de interfaces compartilhadas (a spec é a autoridade).

| consome | produz | o que achei |
|---|---|---|
| T6 ← T5 | `vestigios(url, ent, raiz, cpf)` | casa |
| T6 ← T1 | `marcar_tombstone(url, entidade, cpf_hash, motivo, pedido_por)` | casa |
| T6 ← T2 | `apagar_pessoa(url, entidade, cpf) -> dict[str,int]` | casa |
| T6 ← T3 | `redigir_no_diario(ent, raiz, cpf) -> int` | casa |
| T6 ← T4 | `rol.remover(pasta, cpf)`, `acervo.remover_pessoa(caminho, cpf)` | casa |
| T8 ← T1 | `tombstones(url, entidade) -> set[str]` | casa |
| T9 ← T1 | idem | casa |
| T10 ← T6 | `apagar(..., marcar_cpf=portao.marcar_cpf)` | casa |
| T2/T6 ← `banco.reconstruir` | T7 muda o retorno de `int` para `tuple[int,int]` | **CONFLITO** |

Ruling: os testes das T2 e T6 chamam `reconstruir` apenas para semear — passam a IGNORAR o valor devolvido em vez de afirmá-lo. Assim a mudança de assinatura da T7 não os quebra e a migração da T7 fica restrita aos chamadores de produção. — Por quê: remove o conflito na origem em vez de pagá-lo depois; o valor de retorno não é o que aqueles testes provam. — Custo se errado: a T7 ainda tem de varrer `grep -rn "reconstruir("` e pode achar um chamador esquecido.

Ruling: em `servidor/apagamento.py` o parâmetro da entidade chama-se `ent` (o objeto `Entidade`), não `entidade`. — Por quê: em `banco.py` `entidade` é o APELIDO em texto, e o mesmo nome significando duas coisas entre módulos é o tipo de ambiguidade que já produziu achado nesta base. `app.py` já usa `ent` para o objeto. — Custo se errado: renomear um parâmetro.

Ruling: implementação em ramo `apagamento-a-pedido`, não em worktree separado. — Por quê: a isolação que importa aqui é `main` não receber código destrutivo antes da revisão, e isso o ramo dá; um segundo checkout exigiria preparar Postgres e dependências de novo sem ganho de segurança. — Custo se errado: nenhum que eu veja; o `main` fica intacto de qualquer jeito.

Ruling: os cabeçalhos das tarefas passam a ser `### Task N — Tarefa N: ...`. — Por quê: os scripts da skill casam `^#+\s+Task\s+[0-9]+` e o plano estava só em português, então nenhum brief era extraível e eu perderia a disciplina de livro de registro que a skill existe para dar. Âncora bilíngue satisfaz o script sem traduzir o plano. — Custo se errado: cabeçalho mais feio.

Task 1: complete (commits 260e868..e7429aa, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_apagamento.py → 2 grupos de teste passaram)
Task 2: Ruling: `recebimento` só é apagado quando NINGUÉM mais o referencia, em vez de "pelos ids daquele CPF" como o brief dizia. — Por quê: `projetar_acervo` grava UM recebimento por INGESTÃO, compartilhado por todas as pessoas da planilha, e a coluna é `ON DELETE SET NULL` — apagá-lo junto com uma pessoa anularia a procedência de todos os vizinhos, em silêncio. O brief glosava isso. Teste novo `teste_apagar_nao_estraga_o_dado_de_terceiro` fixa a regra. — Custo se errado: recebimento órfão de acervo sobrevive sem ninguém apontando para ele; ocupa espaço e não é dado pessoal.
Task 2: Ruling: `teste_apagar_nao_estraga_o_dado_de_terceiro` passou a semear e apagar por conta própria (CPFs C e D). — Por quê: a primeira versão só LIA e por isso passava antes de `apagar_pessoa` existir — nada apagava e a vizinha sobrevivia à toa. Teste que passa sem o código é achado sobre o teste. — Custo se errado: nenhum; o teste ficou mais lento e mais honesto.
Task 2: complete (commits e7429aa..ead45c1, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_apagamento.py → 5 grupos de teste passaram)
Task 3: complete (commits ead45c1..00e5211, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_apagamento.py → 7 grupos de teste passaram)
Task 4: complete (commits 00e5211..d340ba6, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_apagamento.py → 9 grupos de teste passaram)
Task 5: Ruling: `vestigios` lê o `acervo.jsonl` por `json.loads` linha a linha, e NÃO por `acervo.ler`. — Por quê: `acervo.ler` lê a PLANILHA do sindicato (CSV/xlsx); o `acervo.jsonl` é outro formato, uma linha por ingestão com lista `pessoas` dentro. Eu confundi os dois e o teste pegou — a varredura voltava sem achar nada no acervo. — Custo se errado: nenhum; é o formato real do arquivo.
Task 5: complete (commits d340ba6..9ed6ed0, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_apagamento.py → 11 grupos de teste passaram)
Task 6: complete (commits 9ed6ed0..f4495b8, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_apagamento.py → 15 grupos de teste passaram)
Task 7: Ruling: os testes da T7 ficaram em `tests/testes_apagamento.py`, não em `testes_espelho.py` como o brief dizia. — Por quê: eles precisam de `_semear_em_todo_lugar` e `_portao_de_teste`, que vivem na suíte de apagamento; levá-los para o espelho duplicaria a semeadura. — Custo se errado: nenhum; o filtro de `reconstruir` fica testado na suíte do assunto que o motiva.
Task 7: Ruling: `marcar_cpf` é OPCIONAL e sem ele `reconstruir` não filtra nada. — Por quê: `/api/cadastro` projeta o envio que a própria pessoa acabou de fazer, e isso é consentimento NOVO; barrá-lo por um tombstone antigo diria a quem voltou por vontade própria que ela não pode voltar. Quem precisa do filtro é a RECUPERAÇÃO de histórico, e passar o parâmetro é declarar isso. Teste `teste_sem_marcar_cpf_a_recuperacao_nao_filtra` fixa a assimetria. — Custo se errado: uma ferramenta de recuperação que esqueça o parâmetro ressuscita quem foi apagado — e é por isso que está no docstring da função, não só aqui.
Task 7: complete (commits f4495b8..1dc493f, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_apagamento.py → 17 grupos de teste passaram)
Task 8: Ruling: a ferramenta lê `PROTOCOL_SEGREDO` do ambiente em vez de chamar `config.carregar()`. — Por quê: `carregar()` exige SMTP configurado e levanta sem ele; uma ferramenta de ingestão de planilha não tem nada a ver com entregar e-mail, e pedir a configuração inteira a fazia falhar por um motivo que não era dela. Observado no teste. — Custo se errado: operador que rode a ingestão sem `PROTOCOL_SEGREDO` recebe recusa explícita em vez de ingestão sem filtro — que é o comportamento desejado.
Task 8: Ruling: sem conseguir ler os tombstones a ingestão NÃO grava nada (sai com 2). — Por quê: gravar sem a conferência pode recriar quem pediu para sair, e o pedido é obrigação legal. Falhar fechado. — Custo se errado: ingestão bloqueada por banco fora do ar, com mensagem dizendo exatamente isso.
Task 8: complete (commits 1dc493f..8040bba, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_apagamento.py → 18 grupos de teste passaram)
Task 9: Ruling: o teste do portão ficou em `tests/testes_espelho.py`, não em `testes_servidor_portal.py` como o brief dizia. — Por quê: o `Cenario` do portal sobe SEM banco, e o filtro de tombstone só roda com `cfg.tem_banco`; o teste não exercitaria nada. `_servidor()` do espelho sobe com banco. — Custo se errado: nenhum; o teste está na suíte que tem a dependência que ele precisa.
Task 9: Ruling: falha ao CONSULTAR o tombstone no portão não fecha o portão — loga e segue. — Por quê: o risco de deixar passar é um código entregue a quem pediu para sair; o risco de recusar é o portal parar para TODOS os filiados do sindicato por causa de um banco fora do ar. O segundo é maior. Difere da ingestão, que falha fechada porque lá ninguém está esperando resposta na tela. — Custo se errado: num banco intermitente, um código pode sair para quem foi apagado, e o log registra.
Task 9: Observação: a primeira versão do teste criou um `Portao` próprio e o marcador não casou com o do servidor — o tombstone existia e era invisível. É a demonstração prática do aviso da spec de que `PROTOCOL_SEGREDO` é de vida longa. Ficou escrito no teste.
Task 9: complete (commits 8040bba..27117a6, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/testes_espelho.py → 53 grupos de teste passaram)
Task 10: Ruling: a rota responde 503 quando `cfg.tem_banco` é falso, em vez de apagar só o disco. — Por quê: sem banco não há tombstone, e sem tombstone o apagamento não é retomável nem impede a próxima planilha de recriar a pessoa — seria apagamento que se desfaz. — Custo se errado: num servidor sem banco o apagamento fica indisponível, com mensagem dizendo exatamente por quê.
Task 10: Ruling: a contagem do painel é sobre as pessoas do ACERVO, não do cadastro. — Por quê: o aviso existe para o sindicato corrigir a FONTE, e a fonte é a planilha dele. Meu primeiro teste semeou pelo portal e contou zero — com razão. — Custo se errado: quem foi apagado e só existia como cadastro do portal não aparece na contagem; mas também não volta por planilha, que é o que a contagem serve para avisar.
Task 10: complete (commits 27117a6..6da8ab0, tests: env 'PROTOCOL_DATABASE_URL=postgresql://postgres@/protocol_teste?host=/tmp/pgb&port=54329' python3 tests/rodar_todos.py → Tudo verde.)

## Passada única de correção (os dois revisores disseram NÃO para o merge)

Final: fixed C1/S1 CPF sobrevivia no `retrato` e a reingestão replantava — `teste_o_retrato_de_verdade_nao_guarda_cpf_nenhum` RED→GREEN (mutante: `_limpar_retrato` sem `divergencias` → cai)
Final: fixed S3 `cpf_hash` sobrevivia em `acesso.sqlite3` e a sessão aberta seguia válida (apagamento reversível por 4 h) — `Portao.esquecer` chamado logo depois do tombstone
Final: fixed S5/C2 `rol.remover` partia pela primeira coluna e `_carregar` lê por cabeçalho; nunca convergia — coluna achada por cabeçalho
Final: fixed S2 PDF em `.parcial/<protocolo>` — protocolos capturados antes da redação
Final: fixed S4/I11 logs da raiz — `_limpar_logs` e varredura de bytes cobrindo a raiz
Final: fixed I1 `DELETE FROM recebimento ... NOT EXISTS` destruía ingestão de TERCEIRO (medido 1 antes → 0 depois) — DELETE escopado por `r.entidade` e ids candidatos
Final: fixed I3 a reescrita do diário destruía linha truncada de terceiro e não tinha fsync — linhas brutas preservadas e fsync antes do replace
Final: fixed I5 `marcar_cpf=None` significava "não filtra" — `reconstruir` falha fechado
Final: fixed I7 o portão falhava ABERTO ao conferir tombstone — `teste_falha_ao_conferir_apagamento_nao_entrega_codigo` RED→GREEN
Final: fixed I6 `_auditar` engolia exceção num ato irreversível — `teste_sem_registro_de_auditoria_nao_apaga_nada` RED→GREEN
Final: fixed I8 as duas lacunas nominais da spec (itens 7 e 9) mais o dublê do retrato

Final: Ruling: o portão, ao não conseguir conferir o tombstone, trata a falha DAQUELE pedido como `destino = None` em vez de deixar passar — mesma resposta 202, mesmo corpo, nenhum oráculo novo, e nunca entrega credencial a quem pode ter pedido para sair; o ruling anterior (T9) supunha só duas saídas, passar ou recusar, e estava errado — custo se errado: enquanto o banco estiver fora, nenhum filiado recebe código, e a falha fica no log
Final: Ruling: a rota de apagamento registra a auditoria de forma SÍNCRONA e falha fechado (503) em vez de usar `_auditar` — `_auditar` engole exceção por uma decisão tomada para LEITURA, onde registro perdido não perde dado; num ato irreversível isso significaria pessoa apagada sem autor — custo se errado: apagamento adiado enquanto o banco estiver fora
Final: Ruling: o teste do item 7 mede se o rol do alvo foi LIDO, não o código de status — escrevi-o primeiro sobre o status e o mutante (ordem invertida em `_gestor_de`) PASSOU, porque rol ilegível também dá 403 — custo se errado: nenhum, o mutante agora cai
Final: Ruling: o teste do retrato usa `dataclasses.asdict(retratar(...))` e varre recursivamente, em vez de escrever as chaves à mão — foi um dublê (`{"pessoas": 1}`) que deixou o C1 passar pela suíte inteira; assim um campo novo indexado por CPF no `Retrato` quebra o teste no dia em que for criado — custo se errado: nenhum

Final: minor (deferred): `vestigios(url="")` pula o banco em silêncio — devia dizer que não conferiu
Final: minor (deferred): `rol.remover` reescreve em utf-8 enquanto promete preservar latin-1
Final: minor (deferred): `apagar_filiado.py` e `ingerir_acervo.py` constroem um `Portao` inteiro só para um HMAC
Final: minor (deferred): sem limite de tamanho em `motivo` e `pedido_por`
Final: minor (deferred): arrumação em `apagamento.py` — carga dupla do rol, imports embutidos
Final: fixed I9 o painel nunca foi tocado e `apagados_a_pedido` chegava no JSON e não aparecia em tela nenhuma — `resumoDoApagamento` (6 testes) + `apagarFiliado` (4 testes de contrato de fio) RED→GREEN, componente `ApagarAPedido` em Painel.tsx; suíte 21 suítes Python verdes, 89 no portal, tsc limpo, build limpo

Final: Ruling: o I9 foi re-graduado de "decisão do parceiro" para Critical e corrigido nesta mesma passada — a spec diz "o sindicato apaga pelo painel" e, entregue como estava, só quem tem `curl` apagava: o recurso não chegava a quem ele serve e passava por pronto na contagem — custo se errado: uma tela a mais no painel
Final: Ruling: `servidor/LEIAME.md` mandava rodar `ferramentas/ensaio_portal.py`, descrito em detalhe, e o arquivo nunca existiu em commit nenhum — corrigi o documento em vez de escrever o ensaio, e registrei o ensaio de navegador como dívida declarada; escrevê-lo agora seria abrir um projeto dentro de uma passada de correção — custo se errado: segue sem verificação de navegador, e a classe de defeito fica coberta só pelos testes de contrato de fio
Final: Ruling: dois testes meus que eu escrevi errado foram reescritos depois de o MUTANTE PASSAR — o do item 7 (conferia status, e rol ilegível também dá 403) e o do retrato (dublê `{"pessoas": 1}`) — e passei a verificar cada guarda nova com mutante, o que achou os dois — custo se errado: nenhum
```
