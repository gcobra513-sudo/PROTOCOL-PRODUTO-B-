# Auditoria de segurança do Produto B — registro

Corrida de **31/10/2026**, com a skill de auditoria de segurança da
Cloudflare (MIT, vendorizada em `.claude/skills/security-audit/`).

Este arquivo existe porque os artefatos da corrida ficaram fora do
repositório, num contêiner descartável. O que importa é isto.

## Como foi feita

**Quem escreveu o código não caça os próprios defeitos.** Eu sou o autor
de tudo o que foi auditado, então declarei isso no começo e deleguei
toda a caça a agentes independentes, cada um com um escopo fechado e
obrigado a medir localmente em vez de raciocinar. Eu só montei o livro de
cobertura, distribuí as unidades e consertei.

**10 unidades de cobertura**, todas cobertas: portão de acesso,
consultas do filiado, painel do gestor, envio de PDF, zip do sindicato,
banco e política de entidade, agendador, e-mail, portal, e uma varredura
ampla do repositório.

## O que NÃO quebrou

Vale mais registrar do que os achados, porque é o que não precisa de
vigilância:

- **Nenhuma injeção de SQL.** Varredura por AST de todo `execute` do
  projeto: cinco SQL não-constantes, todos de origem interna.
- **O isolamento entre sindicatos aguenta.** Sem `app.entidade`, zero
  linhas; `INSERT` e `UPDATE` cruzados recusados pela política; todas as
  13 chaves únicas começam por `entidade`.
- **Nenhuma rota de consulta aceita CPF por parâmetro.** A identidade do
  filiado vem só do marcador HMAC da sessão; `?cpf=` é ignorado.
- **Sem travessia de caminho**, nem no upload nem no zip.
- **Sem injeção de cabeçalho SMTP**, barrada em duas camadas
  independentes.
- **O arrendamento do agendador serializa**: 12 instâncias simultâneas,
  uma vencedora, e todas as expressões usam o relógio do BANCO.
- **Ninguém recebe movimentação de processo que não é seu.**
- **O portal não tem XSS**: nem `innerHTML`, nem `eval`, nem
  `dangerouslySetInnerHTML`.

## Os 13 achados confirmados — todos fechados

| severidade | o que era | conserto |
|---|---|---|
| **critical** | A URL do banco **com senha** aparece inteira em `GET /saude`, sem sessão, quando um subprocesso estoura o tempo | `9399aa6` |
| **high** | O limite de emissões por origem é contado sobre `X-Forwarded-For`, que o anônimo escolhe | `32c7a2d` |
| **high** | `/saude` devolve, sem autenticação, CPF e e-mail de filiado e a lista de todos os sindicatos atendidos | `9399aa6` |
| **high** | (mesma raiz) o campo também carrega os números de processo que o trabalho de fundo imprimiu | `9399aa6` |
| **high** | As três travas que recusam entidade real valiam só no HTTP — o agendador processava e **mandava e-mail** | `c94d04b` |
| **medium** | Falha de envio responde 502 só para quem está no rol — oráculo de filiação sindical | `6c505e5` |
| **medium** | Três pedidos anônimos trancavam um filiado nomeado fora da única porta do produto | `6c505e5` |
| **medium** | Bomba de descompactação: o teto do zip confiava no tamanho **declarado** no índice | `3f6e4a1` |
| **medium** | Cada cadastro reprojetava o diário **inteiro** — 21 comandos SQL por registro já existente | `7929f38` |
| **medium** | Campo de texto do filiado virava **fórmula viva** no `manifesto.csv` que o sindicato abre no Excel | `2b55dfa` |
| **medium** | A raiz de dados **padrão** não estava no `.gitignore`, ao contrário do que o código afirmava | `c8a49ae` |
| **low** | `/api/meu-cadastro` carregava a base nominal **inteira** para achar uma linha | `8ba7b31` |
| **low** | `/openapi.json` aberto a anônimo, publicando rotas e esquemas | `8ba7b31` |

Dois registros de severidade alta são a MESMA raiz, achada
independentemente por dois caçadores: `ultimo_detalhe` servido por
`/saude` sem sessão. São **12 defeitos distintos em 13 registros**.

## O padrão que os une

Em sete dos doze, o código tinha um comentário afirmando exatamente a
propriedade que o teste derrubou:

- `documentos_do_sindicato.py`: "**O tamanho é conferido ANTES de
  descompactar**" — era, pelo número que o atacante escolhe.
- `app.py`: "O QUE NUNCA ENTRA NO LOG: CPF, nome, endereço, e-mail" — o
  CPF entrava na tabela `execucao` e saía numa resposta HTTP pública.
- `app.py`: "O QUE A RESPOSTA NUNCA DIZ: se um CPF está ou não no rol" —
  a falha de entrega dizia.
- `_origem`: "só o primeiro valor, que é o cliente" — é o contrário:
  proxy conforme acrescenta ao FIM.
- `acesso.py`: o teto por CPF "protege a caixa de outra pessoa" — e
  trancava o dono fora da única porta do produto.
- `MAPA.md`: "não é promessa, é impedimento" — era impedimento no HTTP e
  não no caminho que manda e-mail.
- `.gitignore`: "NUNCA versionar cadastro de gente" — guardava `dados/`
  quando a raiz padrão é `dados_portal/`.

**Comentário explica o PORQUÊ de uma decisão; ele não prova que a
decisão funciona.** Cada um desses era uma hipótese minha que nunca
tinha sido medida. Agora cada um tem teste que eu vi falhar pelo motivo
certo antes de consertar.

## O que ficou aberto

### Um achado que depende da implantação, não do código

**POST /api/cadastro materializa o multipart inteiro (derrame em /tmp) antes da verificacao do token**

O handler valida o token de sessao apenas no corpo da funcao, mas o FastAPI resolve a dependencia de formulario ANTES de executar o corpo. O parser multipart do Starlette derrama os arquivos em SpooledTemporaryFile (disco acima de 1 MiB por arquivo, ate max_files=1000) durante o parsing, antes de qualquer checagem de autenticacao. Os tetos da aplicacao so rodam depois. Nao ha middleware ASGI nem limite de corpo no repositorio.

**O que falta saber:** O impacto compartilhado depende de controles fora do repositorio: limite de tamanho de corpo no proxy reverso a frente do uvicorn, e dimensionamento/isolamento de /tmp no host.

### Um canal que medi e não fechei

O ramo de quem está no rol executa a entrega de e-mail DENTRO do pedido,
então demora mais: 0,855 ms de diferença de mediana com o remetente mais
barato que existe, e mais com SMTP real. Fechar exige tirar a entrega do
caminho do pedido — mudança de desenho, não ajuste de ramo, e não em
módulo de autenticação de passagem. Está registrado no docstring de
`servidor/app.py`.

### 40 itens de endurecimento — o estado de cada um, em 16/11/2026

Não eram vulnerabilidades: não tinham principal afetado nem fronteira
atravessada. Foram revistos um a um; o código entre parênteses é o do livro
da auditoria.

**Fechados (34), cada um com teste que falhou antes do conserto:**

| item | o que era | como ficou |
|---|---|---|
| h1-1 | `PROTOCOL_SEGREDO` aceitava um caractere | menos de 24 não sobe |
| h1-2 | em ensaio o segredo é por processo | o aviso de subida diz para rodar um processo só |
| h1-3 | `codigos` e `emissoes` nunca eram podadas | cada emissão poda o que já não conta (e as sessões vencidas) |
| h1-4 | `/api/acesso/conferir` sem teto por origem | 5 tentativas por código que a origem pode pedir |
| h1-5 | `/conferir` não conferia o CPF | CPF malformado não chega ao portão |
| h1-6 | só quem está FORA do rol deixava linha no registro | os dois ramos deixam a mesma linha |
| H1, H2 | `/completude` sem registro, sem teto e com CPF | registra, teto de 200, sem os dicionários por CPF |
| H3 | 403 "suspensa" e 404 "não existe" para anônimo | suspensa responde como inexistente |
| H4 | duas `so_digitos` divergentes (eram quatro) | uma só, de 0 a 9 |
| h3 | documento do sindicato gravado sem a trava e por cima do do filiado | com a trava do depósito, e nunca sobrescreve |
| h4-1 | `SET LOCAL ROLE` podia não pegar, calado | confere `current_user`; sem o papel, não roda |
| h4-2 | política casava com entidade vazia | `NULLIF` nas políticas |
| h4-3 | a sequência entregava o contador global | só `USAGE` |
| h4-4 | chave estrangeira atravessava sindicatos | chave composta com a entidade |
| h4-5 | o mesmo recebimento podia entrar duas vezes | índice único e `ON CONFLICT` |
| h4-7 | três listas de tabelas à mão | o esquema varre as tabelas que existem |
| h4-8 | `EXCEPTION WHEN OTHERS` engolia qualquer erro | só as causas esperadas |
| h5-1 | URL do banco na linha de comando do filho | vai pelo ambiente (já estava) |
| h5-2 | `/saude` listava e contava os sindicatos | sem lista; a contagem, só com a chave do monitor |
| h5-3 | ferramentas escolhiam SMTP por outra regra | a mesma do servidor: HOST e REMETENTE |
| h5-5 | atraso medido pelo relógio da instância | pelo relógio do banco |
| h5-6 | chave do aviso podia colidir | campos escapados; a chave comum não muda |
| h5-7 | nome do andamento ia cru para o e-mail | numa linha, com teto de 200 |
| h5-8 | `@app.on_event`, descontinuado e sem teste | ciclo de vida do app, com teste |
| h6-1 | sem `pypdf` a conferência aprovava | sem `pypdf` o servidor não sobe |
| h6-4 | acervo estragado virava erro 500 cru | recusa que diz o que fazer |
| h6-5 | o 503 de região devolvia a região configurada | explica, sem o valor |
| h6-6 | nenhum cabeçalho de proteção | `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `no-store` |
| h6-7 | validação do manifesto do Produto A, sem uso | removida |
| h6-9 | teste de região vermelho sem banco | (já estava corrigido) |
| h6-10 | filtro de esquema do link sem teste | função própria, com teste |
| h6-11 | rascunho no navegador sem prazo | 30 dias, e é apagado |
| h6-12 | limite por origem burlável pelo cabeçalho | proxies confiáveis (já estava) |

**Fechados em parte (3):**

- **h4-6** — o papel `protocol_app` continua com `LOGIN`. O comentário do
  esquema deixou de afirmar que "sem senha ele não loga": isso só vale onde
  a hospedagem exige senha, e é coisa a conferir na implantação.
- **h6-2** — as dependências do servidor têm teto na versão maior, e o
  `requirements.txt` da raiz deixou de instalar o que era do Produto A.
  **Não há arquivo de trava com versões exatas e impressões digitais.**
- **h6-3** — o `vite` subiu para 5.4.21. O que vai para o navegador não tem
  vulnerabilidade conhecida (`npm audit --omit=dev`: zero). **As ferramentas
  de desenvolvimento ainda têm 8 avisos** (esbuild, vitest, postcss,
  tinypool), que só se resolvem trocando de versão maior.

**Aceitos como estão (2):**

- **h5-4** — o envio para arquivo continua sem rotação. Só existe em modo
  ensaio, onde não há dado de pessoa.
- **h6-8** — `portal/dist/` local pode ficar velho. A pasta é ignorada pelo
  git, e a imagem e o passo a passo compilam o portal na hora.

**Não era pendência (1):** h1-7 lista o que a auditoria CONFIRMOU.

## Uma correção ao relatório recebido

A auditoria descreveu a bomba de descompactação dizendo que `read(-1)`
ignora o tamanho declarado em todo caminho. Medi, e no Python 3.13 deste
ambiente `_read1` **trunca** pelo declarado; o furo está em `read(-1)`
pedir tudo numa única chamada de descompressão. O defeito é real — 64 KiB
de arquivo levaram o processo a 141 MiB de pico — e o conserto é o mesmo,
mas o comentário no código conta a versão medida, não a recebida.

## A suíte

Saiu de 342 para **384 grupos** em Python, mais 79 testes do portal.
Cada conserto entrou com teste que falhou primeiro pelo motivo certo.
