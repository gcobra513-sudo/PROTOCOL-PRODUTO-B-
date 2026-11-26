# Regras deste repositório

Este arquivo é lido automaticamente no começo de toda sessão. O que está
aqui vale sem precisar ser repetido.

---

## A REGRA ZERO: ESTE REPOSITÓRIO É SÓ DO PRODUTO B

Existem dois produtos, e **confundi-los é o erro mais caro deste projeto**.

| | **Produto A** | **Produto B** — este |
|---|---|---|
| para quem | o escritório de advocacia, no trabalho de dentro dele | **sindicatos e cooperativas** — e a ponte deles com os escritórios que contratam |
| o que faz | monta e protocola petições em lote no PJe | organiza os dados do sindicato e diz, nome por nome, o que cada filiado pode fazer |
| onde vive | `gcobra513-sudo/PROTOCOL` | **aqui** |

**O escritório contratado faz parte do Produto B — só como a outra ponta
da ponte** (decidido em 26/11/2026). O sindicato terceiriza o jurídico: ele
faz a triagem e encaminha o filiado ao escritório que cuida daquela ação. O B
cuida dessa passagem: o encaminhamento, a custódia do documento e o retorno
ao filiado (`servidor/escritorios.py`).

- Quem fala com o filiado continua sendo o **sindicato**. O escritório
  aparece para ele pelo nome, para dizer com quem o caso está.
- O escritório vê **só** quem lhe foi encaminhado, e a situação que ele
  marca é de lista fechada — sem texto livre sobre uma pessoa.
- Com um login, o escritório vê os sindicatos que o cadastraram **com o
  mesmo CPF e o mesmo e-mail** — e nem um a mais. Um sindicato continua não
  vendo o dado de outro: quem atravessa é o escritório, e só para onde cada
  sindicato o autorizou.
- **O núcleo não sabe de escritório.** O que alguém pode ou não pode fazer
  não depende de quem vai propor a ação.
- O que acontece **dentro** do escritório depois que o documento chega
  (montar a peça, propor a ação) continua sendo do Produto A. O B termina em
  "documentação completa".

**Nunca traga código do Produto A para cá.** Se algo do A parece necessário,
a pergunta certa é "o B precisa mesmo disso, ou estou carregando a hipótese
do A junto?".

**Vocabulário que é do A e não se usa aqui:** lote, peticionamento,
protocolo no PJe, pré-voo, manifesto, quarentena, disjuntor, motor de lote.

---

## O que o Produto B faz, em uma frase

**O sindicato manda a lista de filiados. O filiado manda os documentos dele.
Nós dizemos, nome por nome: o que ele pode executar, o que pode ajuizar, e
quanto.**

---

## As regras que não se quebram

- **Executar exige título. Ajuizar não.** Sem sentença transitada não há o
  que executar, por melhor que seja a tese.
- **A dúvida nunca vira permissão.** `FALTA` não é "provavelmente pode".
- **Divergência não se resolve sozinha.** Marca e mostra, nunca escolhe.
- **Nunca afirmar o que não dá para justificar.** Todo fato extraído carrega
  o trecho de onde saiu.
- **Nada nominal sai sem homologação humana.** O software prepara; quem
  assina é advogado.
- **O e-mail do portão vem do sindicato**, nunca de quem digita. Sem senha.
- **Um sindicato nunca vê o dado de outro, e nós também não.** A política é
  do banco, não da consulta.
- **Dado de filiado não sai do Brasil.** Nem para nuvem, nem para modelo de
  linguagem.
- **Nenhum dado pessoal real em demonstração.** Só cadastro declaradamente
  fictício.
- **Nunca pedir credencial, senha ou certificado a ninguém.**

---

## Como se trabalha aqui

- **Teste antes do código**, e ver o teste falhar pelo motivo certo.
- **Rodar a suíte inteira** antes de dizer que algo está pronto, e mostrar a
  saída. Se falhou, dizer que falhou.
- **Número que vai para o cliente é medido, não estimado.**
- **Na dúvida, falhar fechado**: não aprova, não adivinha — para e diz por quê.
- **Comentário explica o PORQUÊ da decisão**, não o que a linha faz.
- **Avisar quando o pedido não dá para entregar, ANTES de construir.**

```bash
python3 tests/rodar_todos.py
```

```bash
PROTOCOL_DATABASE_URL='postgresql://...' python3 tests/rodar_todos.py
```

Sem a variável, a parte de banco é **pulada** — e o resumo diz isso. Suíte
pulada não está testada.
