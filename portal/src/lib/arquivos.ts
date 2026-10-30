/**
 * Os bytes dos documentos, guardados SÓ na memória da aba.
 *
 * POR QUE NÃO VÃO PARA O RASCUNHO SALVO: o rascunho mora no armazenamento do
 * navegador, que sobrevive a fechar a aba e é legível por quem senta naquele
 * computador depois. Documento de milhares de pessoas guardado assim é
 * vazamento esperando acontecer — e no computador da sede do sindicato, que
 * várias pessoas usam, é vazamento marcado para a próxima semana.
 *
 * O PREÇO, assumido e dito na tela: recarregar a página perde os anexos, e a
 * pessoa reanexa. Tudo o que foi digitado continua lá. Perder três cliques é
 * melhor que guardar o documento de alguém num lugar que ninguém controla.
 *
 * A CHAVE É UM NÚMERO, NÃO O TIPO. A contribuição aceita vários arquivos —
 * um comprovante por ano é o caso normal —, e uma chave por tipo faria o
 * segundo comprovante apagar o primeiro em silêncio.
 */

let proximo = 1;
const bytes = new Map<number, File>();

/** Guarda e devolve a chave com que o arquivo será recuperado. */
export function guardar(arquivo: File): number {
  const chave = proximo++;
  bytes.set(chave, arquivo);
  return chave;
}

export function esquecer(chave: number): void {
  bytes.delete(chave);
}

export function esquecerTudo(): void {
  bytes.clear();
}

export function tem(chave: number): boolean {
  return bytes.has(chave);
}

export function pegar(chave: number): File | undefined {
  return bytes.get(chave);
}

/** O mapa em si, para o envio. Mesma referência: não copiar arquivo sem razão. */
export function mapa(): Map<number, File> {
  return bytes;
}
