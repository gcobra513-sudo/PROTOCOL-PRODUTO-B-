# Checkpoints

> Onde estamos, o que já está pronto, o que vem. Atualizado a cada entrega.
> Se este arquivo discordar do `MAPA.md`, o mapa vence no **o quê**; este
> vence no **quando**.

---

## Régua

| # | Checkpoint | Estado | Commit |
|---|---|---|---|
| 0 | Repositório próprio do Produto B, separado do A | **pronto** | `14df42e` |
| 1 | Regra zero gravada em `CLAUDE.md` | **pronto** | `01c188d` |
| 2 | Leitura de documentos: PDF vira fato, com procedência | **pronto** | `4af0ca1` |
| 3 | Motor do veredicto: executar / ajuizar / falta | **pronto** | `2e21766` |
| 4 | Cadastro certo: o que o B pede, não o que o A pedia | **pronto** | `6fd78d6` |
| 5 | Ação coletiva como entidade: categoria + período | **pronto** | `6fd78d6` |
| 6 | Cruzamento: de quais ações a pessoa participa | **pronto** | `adc96a2` |
| 7 | Portal do filiado pedindo o que o B pede | **pronto** | `76ad635` |
| 7b | **Mostrar ao filiado de quais ações ele participa** | **agora** | — |
| 8 | Painel do sindicato sobre o novo cadastro | a fazer | — |
| 9 | Banco ligado à aplicação (hoje lê de arquivo) | a fazer | — |
| 10 | Migração para região brasileira | a fazer | — |
| 11 | O valor: quanto, com assinatura humana | a fazer | — |

---

## O que está travado, e não é código

| | O quê | Quem destrava |
|---|---|---|
| **T1** | Nenhuma ação ou tese está homologada. O motor roda e não autoriza nada — corretamente | um advogado marca `homologado = "S"` |
| **T2** | A GIFA está no catálogo como **exemplo real que eu pesquisei**, não como decisão de vocês | o jurídico diz quais ações entram |
| **T3** | `exige_rol = false` na GIFA porque não tenho os autos. Se houver rol, muda quem participa | conferir nos autos |
| **T4** | Nenhuma exportação real de sindicato foi vista. A ingestão foi construída contra planilha que eu sujei imitando Excel brasileiro | o sindicato manda um arquivo |
| **T5** | Retenção e apagamento não têm prazo aprovado | parecer |

---

## Como ler o estado de verdade

```bash
PROTOCOL_DATABASE_URL='postgresql://...' python3 tests/rodar_todos.py
```

Verde não quer dizer "produto pronto": quer dizer "o que está escrito aqui
faz o que diz". O que não existe não tem teste, e está na tabela acima.

---

## Histórico, em uma linha cada

- **0** — O B dividia repositório com o peticionamento em massa. Medi o
  fechamento de dependências (três módulos) e trouxe só isso.
- **1** — Eu mesmo confundi A com B dentro do repositório do B. A regra foi
  para `CLAUDE.md`, que é lido sozinho em toda sessão.
- **2** — O portal já extraía texto do PDF; ninguém tirava fato. Agora cada
  achado carrega o trecho de onde saiu.
- **3** — Executar exige título, ajuizar não. É o primeiro teste do
  repositório.
- **4** — O portal pedia procuração (documento para litigar, do A). O B pede
  comprovante de contribuição, que prova o período de filiação.
- **5** — A ação coletiva não é só um número: alcança uma categoria, num
  período.
- **6** — Cruzar filiação com período responde "de quais ações eu faço
  parte". Filiação parcial é participação parcial.
- **7** — O portal pedia procuração, identidade e endereço (do A). Agora pede
  contribuição, carreira e filiação. Seis etapas em vez de sete, e a da
  filiação explica por que pergunta.
