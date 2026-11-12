#!/bin/bash
# Cópia diária da raiz de dados — o DIÁRIO é a autoridade, e o banco se
# refaz a partir dele; o contrário não é verdade.
#
#     copia.sh [RAIZ] [DESTINO] [DIAS]
#
# O QUE ESTA CÓPIA NÃO É: ela fica NA MESMA MÁQUINA. Protege de apagar por
# engano e de arquivo corrompido; NÃO protege de perder o disco. Para isso é
# preciso o snapshot da Lightsail (console da AWS, "Snapshots automáticos"),
# que só quem tem a conta liga — e que mantém a cópia em São Paulo.
#
# NÃO MANDE ESTA CÓPIA PARA FORA DO BRASIL. É o cadastro inteiro dos filiados.
set -euo pipefail

RAIZ="${1:-/var/lib/protocol}"
DESTINO="${2:-/var/backups/protocol}"
DIAS="${3:-14}"

[ -d "$RAIZ" ] || { echo "raiz $RAIZ não existe" >&2; exit 2; }
umask 077
mkdir -p "$DESTINO"

ARQUIVO="$DESTINO/protocol-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
# Para um arquivo temporário e só então renomeia: cópia pela metade com nome
# de cópia inteira é pior que cópia nenhuma.
tar -C "$(dirname "$RAIZ")" -czf "$ARQUIVO.parcial" "$(basename "$RAIZ")"
# CONFERE antes de chamar de cópia: o tar tem de abrir e listar.
tar -tzf "$ARQUIVO.parcial" > /dev/null
mv "$ARQUIVO.parcial" "$ARQUIVO"

# Só apaga as antigas DEPOIS de a nova existir e abrir.
find "$DESTINO" -name 'protocol-*.tar.gz' -mtime "+$DIAS" -delete
echo "cópia: $ARQUIVO ($(du -h "$ARQUIVO" | cut -f1))"
