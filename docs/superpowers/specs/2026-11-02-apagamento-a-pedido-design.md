# Apagamento a pedido — desenho

> LGPD art. 18, VI. Primeira metade do **T11**; a segunda (persistir e
> reavaliar `oportunidade`) tem spec própria e vem depois.

## O que isto resolve

As tabelas `oportunidade` e `tombstone` existem no esquema desde o
checkpoint 9 e **ninguém escreve nelas**. Sem a segunda, o produto não
atende pedido de eliminação — e filiação sindical é dado sensível
(art. 11), num produto que guarda nome, CPF, e-mail, sentença e número de
processo de gente aposentada.

O prazo da lei para responder ao titular é de 15 dias. Hoje a resposta
seria "não temos como".

## Decisões tomadas, e por quem

| | Decisão | Quem decidiu |
|---|---|---|
| **D1** | **O sindicato aciona, pelo painel.** O sindicato tem a relação com o filiado e nos confiou o dado; sob a LGPD ele tende a ser o controlador e nós o operador, e é o controlador que responde ao titular. Coerente com a regra da casa: quem fala com o filiado é o sindicato | o dono do produto |
| **D2** | **A reingestão pula o CPF apagado e AVISA o sindicato.** O painel passa a dizer quantas pessoas da planilha dele estão apagadas a pedido, para ele corrigir a FONTE. Pular calado faria o sindicato reenviar o mesmo CPF para sempre, e silêncio é o que este produto evita em todo lugar. **"Reingestão" aqui são dois caminhos nomeados:** `ferramentas/ingerir_acervo.py` (a planilha) e `banco.reconstruir` (o diário). O **rol** não é um deles — ver "O rol é um buraco" | o dono do produto |
| **D3** | **O portão NÃO é bloqueado.** Ver "Consequências aceitas" | o dono do produto |
| **D4** | **Redação no lugar, no diário**, em vez de remover a linha. Ver "O diário" | o dono do produto |

## O que desaparece

**No banco** — a aplicação tem `DELETE` em todas estas:
`recebimento`, `pessoa_afirmacao`, `pessoa`, `documento`, `achado`,
`vinculo`, `oportunidade`, `aviso_enviado`.

**Em disco:** os PDFs em `entrega/<cpf>/`; as versões anteriores em
`historico/<cpf>/`; a linha da pessoa no `acervo.jsonl`; a linha dela no
`filiados.csv` e no `gestores.csv`; e o `manifesto.csv`, que é derivado e se
refaz com `deposito.reconstruir_manifesto`.

**No diário:** a redação descrita abaixo.

## O que NÃO desaparece, e por quê

**`leitura`** — o registro de auditoria. A aplicação não tem `DELETE` nela
de propósito: *"log que o próprio sistema apaga não é log de auditoria"*. E
ela guarda **marcador, nunca CPF em claro**, então não há dado pessoal ali
para eliminar. Apagar o rastro de quem consultou destruiria justamente a
prova que protege a pessoa.

**`processo` e `movimento`** — são sobre o processo, não sobre a pessoa. O
`vinculo` entre os dois vai embora; o número e os andamentos ficam, e podem
pertencer a outros filiados da mesma ação coletiva. Número de processo
sozinho não identifica ninguém.

## O diário (D4)

A linha da pessoa é **substituída** por um registro que mantém `protocolo` e
`recebido_em`, ganha `apagado_em`, e perde `linha` e `arquivos`. O arquivo é
reescrito inteiro com troca atômica — o mesmo mecanismo de
`reconstruir_manifesto`.

Duas razões:

1. **`reconstruir` já pula registro sem `linha`** — medido, não suposto
   (`servidor/banco.py`: `if not isinstance(linha, dict): continue`). A
   recuperação continua funcionando sem uma linha de mudança.
2. **A evidência de que houve um envio sobrevive.** Se a pessoa voltar com
   o protocolo na mão perguntando o que aconteceu, existe resposta. Remover
   a linha inteira tornaria o protocolo dela inexistente e a sequência do
   diário descontínua sem explicação.

"Append-only" passa a significar **"não se edita o conteúdo"**, não "não se
apaga nunca" — e o tombstone é a prova de que a remoção foi deliberada.

## A ordem, e o que sobra quando falha no meio

Apagar toca banco e disco, e não há transação que cubra os dois. A ordem
decide o estado residual.

```
1. TOMBSTONE, commitado SOZINHO
2. redação no diário
3. arquivos em disco
4. projeção no banco
5. vestigios() — e só então a rota responde
```

**Por que o tombstone primeiro:** é ele que torna a operação retomável e
que ativa o bloqueio de reingestão imediatamente. Na mesma transação das
exclusões, uma falha desfaria o tombstone junto — a pessoa teria pedido
para sair, o processo teria caído, e não haveria registro de que alguém
pediu nada.

**Por que o diário antes do banco, e isto é a correção de um erro meu.** O
diário é a autoridade; o banco é projeção dele. Apagando o banco primeiro,
uma falha antes da redação deixa o diário intacto — e a próxima
`reconstruir`, que é a operação de RECUPERAÇÃO, **ressuscita a pessoa**. O
apagamento seria desfeito pela função que existe para consertar as coisas.
Na ordem correta a falha é estritamente melhor: a recuperação não traz
ninguém de volta porque não há o que trazer, e as sobras são o que
`vestigios()` enxerga e a segunda passada limpa.

## `vestigios()` — medir, não declarar

```
vestigios(entidade, raiz, cpf) -> list[str]
```

O que ainda existe desta pessoa, em qualquer lugar: linhas no banco,
arquivos em disco, linhas em CSV, registros no diário.

`apagar()` a chama no fim. **Se sobrou qualquer coisa, a rota não diz que
apagou** — devolve o que sobrou, e o operador reexecuta.

A mesma função serve de três coisas: a confirmação dentro de `apagar`, a
asserção do teste, e a ferramenta de retomada.

**Isto é deliberado e é a lição do dia.** Sete dos doze defeitos da
auditoria de 31/10 eram um comentário afirmando uma propriedade que ninguém
mediu. Um campo `apagado = true` é a mesma categoria de afirmação. Medir que
não sobrou nada é diferente de declarar que se apagou — e é por isso que o
esquema **não** ganha coluna de conclusão.

## `reconstruir` consulta o tombstone

Não é defesa em profundidade: é a única coisa que faz o apagamento
sobreviver a uma **restauração de backup**, que é o cenário mais provável de
todos. Restaurado um snapshot do diário anterior ao pedido, `reconstruir`
traria a pessoa de volta e ninguém perceberia.

`reconstruir` passa a pular CPF com tombstone, e a devolver quantos pulou —
pular calado seria o mesmo silêncio que D2 rejeita.

## A interface

```
POST /api/entidade/{apelido}/apagar
     { "cpf": "...", "motivo": "...", "pedido_por": "..." }
```

Autorização por `_gestor_de(apelido, pedido)`, como `/panorama` e
`/completude`: sessão da própria entidade **e** CPF em `gestores.csv`.
Registra leitura com `_auditar`.

Resposta: o marcador curto do CPF (nunca o CPF), o que foi apagado por
categoria, e `vestigios` — vazio quando terminou.

`motivo` e `pedido_por` são texto livre e vão no tombstone. Servem para o
sindicato responder ao titular depois: *"apagamos em tal data, a pedido de
quem"*.

## O aviso no painel (D2)

`/completude` ganha uma contagem: quantos CPFs da planilha do sindicato
estão apagados a pedido. Contagem, **não lista nominal** — a pessoa pediu
para sair, e devolver o nome dela numa tela seria o oposto.

## Consequências aceitas

**O portão não é bloqueado (D3), e a distinção importa.** A pessoa apagada
continua conseguindo **pedir** código — a rota não a recusa, que é o que D3
declinou. O que muda é que **nenhum e-mail sai para ela**: `pedir_codigo`
consulta o tombstone depois de resolver o destino e trata CPF apagado como
destino inexistente.

O resultado observável é **idêntico** ao de qualquer CPF desconhecido: o
mesmo `202`, o mesmo corpo. Isso não é só aceitável, é obrigatório — a
simetria dessa resposta é o que impede o portão de virar consulta de
filiação, e dois achados da auditoria de 31/10 foram exatamente sobre ela.

Se você entender que isto já é "bloquear o portão" e contraria D3, é para
mudar: diga, e a alternativa é não consultar o tombstone ali — ao custo de
mandarmos código para quem pediu para sair.

## O rol é um buraco, e é melhor dizer

**Nada no produto escreve `filiados.csv` ou `gestores.csv`** — a única
escrita é `semente.py`, que serve a demonstração. O rol é colocado à mão
pelo operador.

Consequência: **não há caminho de ingestão do rol para o tombstone
interceptar.** Se o operador repuser o arquivo com o CPF apagado, o nome e o
e-mail da pessoa voltam ao disco, e nenhuma trava impede. O que resta é:

- `pedir_codigo` consulta o tombstone, então **nenhum e-mail sai** mesmo com
  a linha de volta no arquivo;
- `vestigios()` **detecta** a linha reintroduzida, porque varre os CSV.

Não estou inventando uma trava que não existe. O rol entra como **dívida
declarada**: no dia em que existir uma rota de ingestão de rol, ela consulta
o tombstone como as outras duas. Até então, a contagem no painel (D2) e o
`vestigios()` são o que avisa.

**Se ela voltar e preencher o cadastro por vontade própria, volta a
existir.** Isso é consentimento novo, não apagamento falhado. É decisão, não
acidente.

**`PROTOCOL_SEGREDO` é de vida longa.** O tombstone guarda `cpf_hash`, que é
HMAC com esse segredo. Trocá-lo faz os tombstones existentes deixarem de
casar com os CPFs que chegam, e a reingestão volta a aceitar quem foi
apagado. A tabela `leitura` já tem a mesma característica — o problema não é
novo, mas a consequência passa a ser maior. **Trocar o segredo exige
reemitir os tombstones.**

## O que os testes têm de provar

1. **Depois de apagar, `vestigios` devolve vazio** — a asserção central, e
   ela varre banco, disco, CSV e diário.
2. **O tombstone sobrevive** com `motivo` e `pedido_por`, e **sem o CPF em
   claro**.
3. **A reingestão da planilha com o CPF apagado não recria a pessoa**, e
   relata que pulou.
3b. **`pedir_codigo` não manda e-mail para CPF apagado**, e a resposta
   continua idêntica à de um CPF desconhecido — status e corpo, comparados
   como o teste de simetria do portão já faz.
4. **`reconstruir` com o diário ANTERIOR ao apagamento não ressuscita** —
   o teste da restauração de backup.
5. **O diário mantém o protocolo e perde o conteúdo**: `protocolo` e
   `recebido_em` presentes, `linha` e `arquivos` ausentes.
6. **Falha no meio deixa estado retomável**: com o tombstone gravado e as
   exclusões interrompidas, uma segunda passada termina e `vestigios` fecha
   em vazio.
7. **Só gestor da própria entidade apaga**: anônimo 401, filiado 403,
   gestor de outra entidade 403 — e o 403 vem ANTES de qualquer leitura do
   rol da entidade alvo.
8. **Apagar não atravessa entidade**: o mesmo CPF noutra entidade continua
   intacto.
9. **`leitura` não é apagada**, e o registro do próprio apagamento entra
   nela.
10. **Apagar duas vezes não quebra** e deixa dois tombstones.

## Fora do escopo

- Bloquear o portão (D3).
- Apagamento acionado pela própria pessoa (D1).
- Retenção com prazo — é **T5**, e depende de parecer.
- Rota de ingestão de rol: o rol continua sendo colocado à mão, e a dívida
  está declarada acima.
- `oportunidade`: segunda metade do T11, spec própria.
