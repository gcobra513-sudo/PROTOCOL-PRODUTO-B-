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

### 40 itens de endurecimento

Não são vulnerabilidades: não têm principal afetado nem fronteira
atravessada. São o que merece conserto quando houver folga. Os que eu
consideraria primeiro:

- `PROTOCOL_SEGREDO` aceita qualquer valor não vazio — um caractere
  passa, e dele derivam os três marcadores HMAC do portão.
- `/api/entidade/{apelido}/completude` devolve lista nominal **sem teto**
  e **sem registro de leitura**, enquanto `/panorama` limita a 8 nomes.
  É o caminho que transforma uma sessão de gestor comprometida em cópia
  integral da base.
- `SET LOCAL ROLE` é no-op **silencioso** fora de transação, e todo o RLS
  do produto pende dele. Uma linha conferindo `current_user` resolve.
- O Postgres reseta `app.entidade` para **string vazia**, não NULL. Hoje
  inócuo; deixa de ser no dia em que aparecer um pool de conexões.
- `texto_extraivel` devolve `(True, 0)` — isto é, **aprova** — quando
  `pypdf` não está instalado.
- Nenhuma dependência Python está fixada (tudo `>=`).
- Duas implementações de `so_digitos` divergem de verdade entre
  `nucleo/cadastro.py` e `servidor/validacao.py`.
- `ParaArquivo` grava e-mail e movimentação processual em claro, sem
  rotação nem retenção, e quem a seleciona no caminho de fundo é apenas
  a ausência de `PROTOCOL_SMTP_HOST` — não uma trava.

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
