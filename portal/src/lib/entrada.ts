/**
 * De qual sindicato a pessoa é, e para onde ela vai.
 *
 * O portal não tem lista de sindicatos — de propósito: a lista de clientes
 * é informação comercial, e um endereço público que a entregasse diria a
 * qualquer um quem contratou o serviço. Então a página de entrada PERGUNTA,
 * e a pessoa responde com o código que o sindicato passou, ou colando o
 * link inteiro que recebeu.
 */
import type { Tela } from "./envio";

/** O formato de um apelido de entidade — o mesmo que o servidor aceita. */
const CODIGO = /^[a-z0-9][a-z0-9-]{1,48}$/;

/** O código do sindicato, tirado do que a pessoa digitou ou colou. Vazio
 *  quando o texto não tem cara de código: ele vira parte de um endereço, e
 *  o que não é código não segue adiante. */
export function codigoDoSindicato(texto: string): string {
  const limpo = (texto ?? "").trim();
  if (!limpo) return "";
  const noLink = /[?&]entidade=([^&#\s]+)/i.exec(limpo);
  let candidato = limpo;
  if (noLink) {
    try {
      candidato = decodeURIComponent(noLink[1] ?? "");
    } catch {
      return "";
    }
  }
  candidato = candidato.trim().toLowerCase();
  return CODIGO.test(candidato) ? candidato : "";
}

/** O endereço de uma área do portal, para um sindicato. */
export function enderecoDaArea(tela: Tela, apelido: string): string {
  const q = new URLSearchParams();
  if (apelido) q.set("entidade", apelido);
  if (tela !== "cadastro") q.set("tela", tela);
  const busca = q.toString();
  return busca ? `?${busca}` : "./";
}
