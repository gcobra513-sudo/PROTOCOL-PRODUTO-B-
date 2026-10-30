# Regras deste repositório

Este arquivo é lido automaticamente no começo de toda sessão. O que está
aqui vale sem precisar ser repetido.

---

## A REGRA ZERO: ESTE REPOSITÓRIO É SÓ DO PRODUTO B

Existem dois produtos, e **confundi-los é o erro mais caro deste projeto**.

| | **Produto A** | **Produto B** — este |
|---|---|---|
| para quem | o escritório de advocacia | **sindicatos e cooperativas** |
| o que faz | monta e protocola petições em lote no PJe | organiza os dados do sindicato e diz, nome por nome, o que cada filiado pode fazer |
| onde vive | `gcobra513-sudo/PROTOCOL` | **aqui** |

**Nunca escreva "escritório" num texto que o filiado ou o sindicato vai
ler.** Quem fala com o filiado é o **sindicato**. Se um escritório existir na
relação, ele foi contratado pelo sindicato, e isso é contrato, não arquitetura.

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
