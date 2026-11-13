# Pôr o servidor no ar

Do zero até o primeiro filiado receber código, numa máquina **AWS Lightsail
em `sa-east-1`** com Ubuntu — a escolha de `docs/hospedagem.md`. Cada passo
diz como conferir que deu certo, porque um passo que falha calado só aparece
três passos depois.

## O que foi ensaiado, e o que NÃO foi — dito antes de tudo

Em 13/11/2026 este passo a passo foi **ensaiado do zero** num contêiner
Ubuntu 24.04: `implantacao/ensaio/ensaiar.py` executa os blocos de comando
DESTE arquivo, um a um. 22 dos 30 rodam como estão escritos; os outros 8 são
trocados ou pulados, e o ensaio diz qual e por quê (não há systemd, GitHub
nem certificado público num contêiner). O ensaio achou dois defeitos que só a
máquina mostraria, e os dois estão corrigidos:

- **o portal não abria.** As pastas nasciam fechadas ao usuário do Caddy, e
  toda página respondia 403 (a API funcionava). Passo 2;
- **o e-mail não conferia para quem ia.** A conexão com o servidor de e-mail
  era cifrada, mas o certificado dele não era conferido: o código de acesso e
  a senha do envio foram entregues a um servidor de autoridade desconhecida,
  sem erro. Agora o envio falha em vez de seguir (`tests/testes_remetente.py`).

| | conferido como |
|---|---|
| os comandos dos passos 1 a 10 e "Atualizar depois" | **ensaiado**: rodados como estão escritos, na ordem, com o usuário `protocol` |
| `servidor/requirements.txt` basta para o servidor e as ferramentas | **ensaiado**, num ambiente Python recém-criado |
| o portal compila com o Node 18 que o Ubuntu 24.04 instala | **ensaiado** |
| `com-ambiente.sh` entrega a URL do banco inteira, com o `&` | **ensaiado**: o esquema é criado por ele, num banco cuja URL tem `&` |
| `Caddyfile` | **ensaiado** no Caddy 2.6.2 (o do Ubuntu 24.04): valida como está; entrega as páginas, a API e a saúde; redireciona http; manda os quatro cabeçalhos; recusa pedido de 85 MB |
| quem lê o quê | **ensaiado**: o usuário do Caddy lê o portal, e NÃO lê o ambiente, os dados nem a cópia |
| do gestor ao primeiro filiado com código | **ensaiado** por HTTPS: o gestor recebe o código por e-mail, entra, envia a planilha; o filiado recebe o código e entra |
| o limite de pedidos de código, atrás do Caddy | **medido**: de um mesmo endereço, forjando `X-Forwarded-For` a cada pedido, 20 passam e o 21º é recusado; outro endereço não paga por ele |
| `copia.sh` | **ensaiado** com o comando do `.service`: gera, fecha aos outros, e restaurada é igual à raiz de dados |
| o servidor só escreve na raiz de dados | **ensaiado** com o resto do sistema só para leitura |
| `protocol.service` e o temporizador da cópia | a SINTAXE, por `systemd-analyze verify`; e o servidor foi posto no ar com o usuário, a pasta, o ambiente, o comando, a pasta gravável e a máscara LIDOS do `.service`. **O systemd de verdade nunca os rodou** — nem o reinício em falha, nem o temporizador |
| o certificado público | **NÃO**: o ensaio usa a autoridade interna do Caddy. Pedir e renovar o certificado de verdade só acontece com o domínio apontado |
| a chave de implantação e o clone do GitHub | a chave é criada no ensaio; **o clone por ela, NÃO** |
| um provedor de e-mail de verdade | **NÃO**: o ensaio usa um servidor SMTP local |
| o conjunto inteiro, numa Lightsail | **nunca**. A primeira subida continua sendo a primeira numa máquina de verdade — mas não é mais o primeiro ensaio |

Para repetir o ensaio (só em máquina descartável):

`sudo python3 implantacao/ensaio/ensaiar.py --maquina-descartavel --banco URL-DE-UM-BANCO-VAZIO`

## Antes de começar — o que só você contrata

- a instância Lightsail em **São Paulo (`sa-east-1`)**, com IP fixo e as
  portas 80 e 443 abertas;
- o **domínio**, com o DNS já apontando para esse IP;
- o banco no Supabase, em `sa-east-1`, **num plano que não pausa** — pausado,
  ninguém recebe código de acesso;
- uma conta de **SMTP** para o envio dos códigos;
- a caixa de e-mail que vai receber os avisos de pedido esperando.

Nenhum desses segredos passa por este repositório nem por quem o escreve:
eles são digitados por você, na máquina, no passo 5.

## 1. Pacotes

```bash
sudo apt-get update && sudo apt-get install -y python3-venv git caddy nodejs npm postgresql-client
```

Confere: `python3 --version` é 3.11 ou mais novo, e `caddy version` responde.

## 2. O usuário e as pastas

```bash
sudo useradd --system --home /srv/protocol --shell /usr/sbin/nologin protocol
```

```bash
sudo install -d -o protocol -g protocol -m 750 /var/lib/protocol /var/backups/protocol
```

```bash
sudo install -d -o protocol -g protocol -m 751 /srv/protocol
```

```bash
sudo install -d -o protocol -g protocol -m 755 /srv/protocol/portal
```

```bash
sudo install -d -o root -g protocol -m 750 /etc/protocol
```

Os modos são diferentes de propósito. O Caddy roda como o usuário `caddy`,
que não é do grupo `protocol`: ele precisa PASSAR por `/srv/protocol` (751)
e LER `/srv/protocol/portal` (755) — com 750 nos dois, toda página do portal
responde 403 (visto no ensaio). Os dados, a cópia e o ambiente ficam
fechados para ele.

`/var/lib/protocol` é a raiz de dados: o diário de cadastros mora ali, e é
ele a autoridade. `/var/backups/protocol` recebe a cópia diária.

## 3. O código

O repositório é privado, e a máquina o lê com uma chave de implantação
**só de leitura**, que nasce aqui e não sai daqui:

```bash
sudo -u protocol ssh-keygen -q -t ed25519 -N '' -C protocol-implantacao -f /srv/protocol/.ssh/id_ed25519
```

```bash
sudo cat /srv/protocol/.ssh/id_ed25519.pub
```

Cole essa linha (a `.pub`, que não é segredo) no GitHub: repositório →
Settings → Deploy keys → Add deploy key, **sem** marcar "Allow write
access". Depois clone em `/srv/protocol/app` — na primeira vez o `ssh`
pergunta se confia no GitHub; confira a impressão digital com a que o
GitHub publica antes de responder `yes`:

```bash
sudo -u protocol git clone git@github.com:gcobra513-sudo/protocol-produto-b-.git /srv/protocol/app
```

## 4. O Python

```bash
sudo -u protocol python3 -m venv /srv/protocol/venv
```

```bash
sudo -u protocol /srv/protocol/venv/bin/pip install -r /srv/protocol/app/servidor/requirements.txt
```

Confere: `sudo -u protocol /srv/protocol/venv/bin/python -c "import psycopg, fastapi, pypdf, openpyxl"` não reclama.

## 5. O ambiente

```bash
sudo install -m 640 -o root -g protocol /srv/protocol/app/implantacao/protocol.env.exemplo /etc/protocol/protocol.env
```

Edite `/etc/protocol/protocol.env` e preencha — o arquivo explica cada
linha. O segredo do portão é gerado ali mesmo:

```bash
python3 -c 'import secrets;print(secrets.token_urlsafe(32))'
```

**Guarde esse segredo fora da máquina também.** Sem ele não se reconhece
quem foi apagado a pedido, e uma restauração de cópia traria a pessoa de
volta.

## 6. O banco

Banco **novo** — cria as tabelas na forma de hoje:

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh /srv/protocol/venv/bin/python -c "import os; from servidor import banco; banco.criar_esquema(os.environ['PROTOCOL_DATABASE_URL'])"
```

`com-ambiente.sh` roda um comando com as variáveis de
`/etc/protocol/protocol.env`, lidas como o systemd lê. **Não carregue esse
arquivo com `source`**: a URL do banco tem `&`, e o shell a parte ao meio
sem avisar.

Banco que **já existe**: `criar_esquema` NÃO altera tabela existente. O de
São Paulo já recebeu as duas migrações abaixo em 12/11/2026, e a forma dele
foi conferida (`servidor/migracoes/LEIA.md`) — **não as rode de novo ali**.
Para qualquer outro banco antigo, aplique na ordem, uma vez:

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh sh -c 'psql "$PROTOCOL_DATABASE_URL" -v ON_ERROR_STOP=1 -f servidor/migracoes/2026-11-03-oportunidade-origem-do-catalogo.sql'
```

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh sh -c 'psql "$PROTOCOL_DATABASE_URL" -v ON_ERROR_STOP=1 -f servidor/migracoes/2026-11-10-documento-origem-e-leitura-humana.sql'
```

**Confere a forma**, em qualquer dos dois casos: a impressão digital do
banco de produção tem de ser igual à de um banco recém-criado pelo esquema.

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh sh -c 'psql "$PROTOCOL_DATABASE_URL" -At -f servidor/migracoes/conferir_forma.sql'
```

Compare com a mesma consulta rodada num banco novo (o de teste serve).
Diferente quer dizer que falta migração — ou que sobra coluna.

Depois, as reprojeções de `servidor/migracoes/LEIA.md`, e marque lá o que foi
aplicado — é a única tabela deste repositório que só uma pessoa mantém.

## 7. O portal

```bash
cd /srv/protocol/app/portal && sudo -u protocol npm ci && sudo -u protocol env VITE_API=https://portal.exemplo.org npx vite build --outDir /srv/protocol/portal --emptyOutDir
```

`VITE_API` é o endereço público do próprio portal: o Caddy entrega as
páginas e a API pelo mesmo domínio. Confere: `/srv/protocol/portal/index.html`
existe, e o Caddy consegue lê-lo — `sudo -u caddy head -c 20 /srv/protocol/portal/index.html`
não reclama. O Node 18 que o Ubuntu 24.04 instala basta (medido no ensaio).

## 8. Os serviços

```bash
sudo cp /srv/protocol/app/implantacao/protocol.service /srv/protocol/app/implantacao/protocol-copia.service /srv/protocol/app/implantacao/protocol-copia.timer /etc/systemd/system/
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now protocol.service protocol-copia.timer
```

Confere o servidor, ainda sem o Caddy:

```bash
curl -s http://127.0.0.1:8000/saude
```

Tem de responder JSON com `"modo_ensaio": false` e `"envio_de_email": "smtp"`.
Rode de novo depois de alguns segundos e olhe `"envio"`: a primeira chamada
manda conferir a conexão com o servidor de e-mail (abre, confere o
certificado, entra com a conta — sem mandar mensagem) e responde
`"conferindo"`; a seguinte tem de dizer `"ok"`. Se disser `"falhando"`, nenhum
código de acesso vai sair: `journalctl -u protocol | grep 'ENVIO DE E-MAIL'`
diz se foi a conexão ou a entrega, e o tipo do erro.
Se o serviço não subiu, `journalctl -u protocol -n 50` diz o que falta — o
servidor explica por extenso, em vez de dar um rastro de erro.

Agora o Caddy. Troque o domínio no arquivo, **valide**, e só então ligue:

```bash
sudo cp /srv/protocol/app/implantacao/Caddyfile /etc/caddy/Caddyfile
```

```bash
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

Confere: `curl -s https://portal.exemplo.org/saude` responde o mesmo JSON, e
o navegador abre o portal com cadeado.

## 9. O primeiro sindicato

Veja as carreiras que dá para contratar, e crie — o sindicato, as carreiras
dele e quem é gestor, de uma vez:

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh /srv/protocol/venv/bin/python ferramentas/sindicatos.py --raiz /var/lib/protocol categorias
```

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh /srv/protocol/venv/bin/python ferramentas/sindicatos.py --raiz /var/lib/protocol criar sind-df "Sindicato Tal" --categoria auditor-fiscal-receita-federal --gestor 000.000.000-00=gestor@sindicato.exemplo.org
```

A ferramenta confere tudo antes de gravar — o apelido, a carreira, o CPF e
o e-mail do gestor — e recusa em vez de criar pela metade. O arquivo de
gestores nasce com modo 600. **O apelido decide se é demonstração:** só os
que começam por `demo-` são; qualquer outro é sindicato de verdade.

Confere:

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh /srv/protocol/venv/bin/python ferramentas/sindicatos.py --raiz /var/lib/protocol listar
```

Para pôr ou tirar um gestor depois: `sindicatos.py gestor sind-df nomear CPF
EMAIL` e `... tirar CPF`. Gestor não nomeia gestor, e por isso não há botão
para isso no painel.

Daí em diante é o sindicato: o gestor entra em
`https://portal.exemplo.org/?entidade=sind-df&tela=painel`, envia a planilha,
e os filiados passam a receber código. Se os filiados usam o e-mail da
repartição, a primeira planilha fica quase toda segurada até você confiar no
domínio — o e-mail de aviso chega, e o comando está em `servidor/LEIAME.md`.

As ferramentas de quem opera rodam do mesmo jeito, com o ambiente do
servidor:

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh /srv/protocol/venv/bin/python ferramentas/trocas_de_email.py --raiz /var/lib/protocol --entidade sind-df listar
```

## 10. A cópia

O temporizador do passo 8 já copia a raiz de dados todo dia, às 04:30, para
`/var/backups/protocol`, e guarda 14 dias. Confere no dia seguinte:

```bash
systemctl list-timers protocol-copia.timer && ls -la /var/backups/protocol
```

**Essa cópia fica na mesma máquina.** Protege de apagar por engano; não
protege de perder o disco. Ligue também, no console da Lightsail, os
**snapshots automáticos** da instância — é a única cópia fora do disco, e ela
fica em São Paulo. Nenhuma cópia destes dados sai do Brasil.

## Ficar sabendo quando parar

`/saude` responde `"ok": false` em três casos, e os três são "o portal está
de pé mas não está entregando": trabalho de fundo atrasado, estado que não
deu para ler, e **envio de e-mail falhando** (`"envio": "falhando"`). O
último existe porque quem pede o código lê "código enviado" mesmo quando o
envio falha — a tela não pode dizer outra coisa sem revelar quem está no
cadastro do sindicato —, então é só por aqui que quem opera fica sabendo.

**Nada neste repositório olha `/saude` por você.** Aponte um monitor de fora
para `https://<domínio>/saude`, a cada poucos minutos, alertando quando a
resposta não trouxer `"ok": true` (e não só quando a porta não responder). A
rota não exige sessão e não publica dado de filiado nem nome de sindicato.

Envio marcado como falhando por causa de uma ENTREGA só volta a `"ok"` quando
um envio de verdade der certo — entrar no portal você mesmo é o teste.

## Atualizar depois

```bash
cd /srv/protocol/app && sudo -u protocol git pull && sudo -u protocol /srv/protocol/venv/bin/pip install -r servidor/requirements.txt
```

Se `servidor/migracoes/` ganhou arquivo novo, aplique-o (passo 6) **antes**
de reiniciar. Depois refaça o portal (passo 7) e:

```bash
sudo systemctl restart protocol
```
