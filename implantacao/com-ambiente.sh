#!/bin/bash
# Roda um comando com as variáveis do arquivo de ambiente do servidor.
#
#     com-ambiente.sh COMANDO [ARGUMENTOS...]
#
# Lê o arquivo COMO O SYSTEMD LÊ: linha a linha, sem interpretar. Carregar
# com `source` quebra exatamente onde importa — a URL do banco tem `&`, e o
# shell a parte ao meio em silêncio (visto ao ensaiar esta pasta: o servidor
# subiu apontando para o banco errado, sem erro nenhum).
#
# É para as ferramentas e para o `psql`: tudo o que precisa do mesmo banco e
# do mesmo segredo que o servidor usa.
set -euo pipefail

ARQUIVO="${PROTOCOL_ENV:-/etc/protocol/protocol.env}"
[ -r "$ARQUIVO" ] || { echo "não consigo ler $ARQUIVO" >&2; exit 2; }
[ "$#" -gt 0 ] || { echo "uso: com-ambiente.sh COMANDO [ARGUMENTOS...]" >&2; exit 2; }

while IFS= read -r linha || [ -n "$linha" ]; do
  case "$linha" in
    ''|'#'*) continue ;;
    PROTOCOL_*=*) export "$linha" ;;
    *) echo "linha que não entendo em $ARQUIVO: ${linha%%=*}" >&2; exit 2 ;;
  esac
done < "$ARQUIVO"

exec "$@"
