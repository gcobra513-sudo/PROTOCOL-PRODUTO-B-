# Pôr o servidor no ar

Do zero até o primeiro filiado receber código, numa máquina **AWS Lightsail
em `sa-east-1`** com Ubuntu — a escolha de `docs/hospedagem.md`. Cada passo
diz como conferir que deu certo, porque um passo que falha calado só aparece
três passos depois.

## O que NÃO foi conferido, dito antes de tudo

Esta pasta foi escrita sem uma máquina de verdade na frente. O que foi
medido e o que não foi:

| | conferido como |
|---|---|
| `servidor/requirements.txt` basta para o servidor e as ferramentas | **medido**, num ambiente Python limpo (faltava o driver do banco, e foi corrigido) |
| `protocol.env.exemplo` tem toda variável que o servidor lê, e preenchido faz o servidor subir sem aviso | **teste**, em `tests/testes_repositorio.py` |
| com o exemplo preenchido, o servidor SOBE fora do modo ensaio, lê o banco e não dá aviso de configuração | **medido**: subido de verdade no ambiente limpo, contra o banco de teste |
| `com-ambiente.sh` entrega a URL do banco inteira, com o `&` | **rodado**. A primeira versão desta prova usava `source`, que partiu a URL ao meio: o servidor subiu SEM banco e sem erro. Por isso o script existe |
| os caminhos do serviço, do Caddy, da cópia e deste passo a passo concordam | **teste**, no mesmo arquivo |
| `protocol.service` e o temporizador da cópia | só a SINTAXE, por `systemd-analyze verify`. Nunca rodaram |
| `copia.sh` | **rodado** numa pasta de teste: gera, confere que abre, grava com modo 600 |
| `Caddyfile` | **NÃO conferido**: não havia Caddy onde isto foi escrito. Rode `caddy validate` (passo 8) antes de confiar |
| o conjunto inteiro, numa Lightsail | **nunca**. A primeira subida é o primeiro ensaio |

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
sudo install -d -o protocol -g protocol -m 750 /srv/protocol /srv/protocol/portal /var/lib/protocol /var/backups/protocol
```

```bash
sudo install -d -o root -g protocol -m 750 /etc/protocol
```

`/var/lib/protocol` é a raiz de dados: o diário de cadastros mora ali, e é
ele a autoridade. `/var/backups/protocol` recebe a cópia diária.

## 3. O código

O repositório é privado. Crie no GitHub uma chave de implantação **só de
leitura** para esta máquina, e clone em `/srv/protocol/app`:

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
existe.

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

```bash
cd /srv/protocol/app && sudo -u protocol implantacao/com-ambiente.sh /srv/protocol/venv/bin/python -c "import os, pathlib; from servidor.entidades import Cadastro; print(Cadastro(pathlib.Path(os.environ['PROTOCOL_RAIZ'])).criar('sind-df', 'Sindicato Tal', categorias=('auditor-fiscal-receita-federal',)))"
```

Diga quem é gestor — `/var/lib/protocol/sind-df/gestores.csv`, com modo 600 e
dono `protocol`:

```csv
cpf,email
000.000.000-00,gestor@sindicato.exemplo.org
```

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

## Atualizar depois

```bash
cd /srv/protocol/app && sudo -u protocol git pull && sudo -u protocol /srv/protocol/venv/bin/pip install -r servidor/requirements.txt
```

Se `servidor/migracoes/` ganhou arquivo novo, aplique-o (passo 6) **antes**
de reiniciar. Depois refaça o portal (passo 7) e:

```bash
sudo systemctl restart protocol
```
