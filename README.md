# PROTOCOL — Produto B

**O sindicato manda a lista de filiados. O filiado manda os documentos dele.
Nós dizemos, nome por nome: o que ele pode executar, o que pode ajuizar, e
quanto.**

Este repositório é só do Produto B. O peticionamento em massa — o Produto A,
que monta e protocola petições em lote no PJe — vive em
[`gcobra513-sudo/PROTOCOL`](https://github.com/gcobra513-sudo/PROTOCOL).

---

## Por onde começar a ler

| Arquivo | O que responde |
|---|---|
| **[`MAPA.md`](MAPA.md)** | o que o produto faz, em três caixas. **Comece por aqui** |
| **[`BANCO.md`](BANCO.md)** | como o dado entra, onde fica, como sai, e por que é seguro |
| [`PRODUTO.md`](PRODUTO.md) | a especificação: regras invariáveis e decisões em aberto |
| [`docs/achados_datajud.md`](docs/achados_datajud.md) | o que a base pública do CNJ entrega — medido, não suposto |

Se algum arquivo contradisser o `MAPA.md`, o mapa vence.

---

## O que tem aqui

```
nucleo/         o veredicto: processo_cnj, entendimentos, motor
servidor/       a API: portão, cadastro, acervo, completude, acompanhamento
portal/         o site do filiado (React + Vite + TypeScript)
                quatro áreas, por `?tela=`: cadastro, acoes, processos, painel
config/         categorias/ — um catálogo de teses POR CATEGORIA
compartilhado/  o contrato de dados entre o portal e o resto
ferramentas/    linha de comando: ingerir acervo, coletar movimentação
tests/          as suítes
```

**O que NÃO está aqui é tão importante quanto o que está.** O motor de
peticionamento do Produto A — pipeline, competência, protocolo, render — não
foi trazido. O Produto B depende dele em exatamente zero linhas, e carregar
junto faria este repositório ter milhares de linhas que ninguém aqui executa.

---

## Rodar

```bash
pip install -r requirements.txt
```

```bash
python3 tests/rodar_todos.py
```

Com banco, para o isolamento entre entidades ser exercitado de verdade e não
apenas declarado:

```bash
PROTOCOL_DATABASE_URL='postgresql://...' python3 tests/rodar_todos.py
```

Sem a variável, a parte de RLS é **pulada** — e o resumo diz isso. Suíte
pulada não está testada.

O portal:

```bash
cd portal && npm install && npm run teste && npm run build
```

O servidor, em modo de demonstração:

```bash
PROTOCOL_MODO_ENSAIO=1 PROTOCOL_RAIZ=dados python3 -m uvicorn servidor.app:criar_app --factory --port 8000
```

---

## Estado, sem maquiagem

| Caixa do mapa | Estado |
|---|---|
| **1. Entrada** — o sindicato manda a lista, o filiado manda os documentos | **pronta** |
| **2. Entendimento** — ler o que os documentos dizem | **não existe** |
| **3. Veredicto** — o que esta pessoa pode fazer | **pronta, sem o valor** |
| **4. Valor** — quanto | **não existe** |

A caixa 3 funciona com o catálogo real de entendimentos, mas **nada nominal
sai dele**: toda tese nasce com `homologado = "N"`, e o motor se recusa a
produzir permissão a partir de entendimento não homologado. O motor prepara;
quem assina é advogado.

---

## As regras que não se quebram

- **Executar exige título. Ajuizar não.** Sem sentença transitada não há o
  que executar, por melhor que seja a tese. É o primeiro teste do repositório.
- **A dúvida nunca vira permissão.** `FALTA` não é "provavelmente pode".
- **Divergência não se resolve sozinha.** Quando o sindicato e o filiado
  discordam, marca e mostra — nunca escolhe.
- **O e-mail do portão vem do sindicato**, nunca de quem digita. Sem senha:
  código de seis dígitos no e-mail que a entidade cadastrou.
- **Um sindicato nunca vê o dado de outro**, e nós também não: a política é
  do banco, não da consulta.
- **Nenhum dado pessoal real em demonstração.** Só cadastro declaradamente
  fictício.
- **Nunca pedir credencial, senha ou certificado a ninguém.**

---

## O que está medido

Número aqui é medido, não estimado. Se algum estiver sem fonte ou sem data,
é defeito.

- **65 tribunais** no DataJud, e o alias sai do próprio número CNJ. **O STF
  não está lá** — conferido em 29/10/2026.
- **22 a 43 segundos** por consulta ao DataJud. Por isso nenhuma tela
  consulta ao vivo.
- A ação coletiva da **GIFA** (`0010391-24.2006.4.01.3400`) devolveu **600
  movimentos**, em 29/10/2026.
- **Superusuário do Postgres ignora RLS**, inclusive com `FORCE` — e a URL
  padrão da Supabase conecta assim. Descoberto por teste vermelho.
