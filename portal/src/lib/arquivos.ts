/**
 * Os bytes dos documentos, guardados SÓ na memória da aba.
 *
 * POR QUE NÃO VÃO PARA O RASCUNHO SALVO: o rascunho mora no armazenamento do
 * navegador, que sobrevive a fechar a aba e é legível por quem senta naquele
 * computador depois. Documento de identidade e procuração de 15 mil pessoas
 * guardados assim é vazamento esperando acontecer — e no computador da sede do
 * sindicato, que várias pessoas usam, é vazamento marcado para a próxima
 * semana.
 *
 * O PREÇO, assumido e dito na tela: recarregar a página perde os anexos, e a
 * pessoa reanexa. Tudo o que foi digitado continua lá. Perder três cliques é
 * melhor que guardar a identidade de alguém num lugar que ninguém controla.
 */
import type { TipoDocumento } from "./tipos";

const bytes = new Map<TipoDocumento, File>();

export function guardar(tipo: TipoDocumento, arquivo: File): void {
  bytes.set(tipo, arquivo);
}

export function esquecer(tipo: TipoDocumento): void {
  bytes.delete(tipo);
}

export function esquecerTudo(): void {
  bytes.clear();
}

export function tem(tipo: TipoDocumento): boolean {
  return bytes.has(tipo);
}

/** O mapa em si, para o envio. Mesma referência: não copiar arquivo sem razão. */
export function mapa(): Map<TipoDocumento, File> {
  return bytes;
}
