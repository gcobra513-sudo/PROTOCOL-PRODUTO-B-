/**
 * A sessão do portal, do lado do navegador: as regras que não dependem de
 * tela. O porquê de cada uma está em `sessao.test.ts`.
 *
 * O TOKEN NÃO MORA AQUI, nem em lugar nenhum que sobreviva à página: ele
 * fica na memória do `App`. Guardá-lo no navegador pouparia um código a
 * quem recarrega a página — e entregaria a sessão à próxima pessoa do
 * computador da sede.
 */
import { ErroDoServidor } from "./envio";

/** Quanto tempo a tela pode ficar parada com a sessão aberta.
 *
 *  BOTÃO, NÃO MEDIÇÃO. Curto demais derruba quem foi buscar um papel no meio
 *  do cadastro; longo demais deixa a tela de alguém aberta para o próximo. O
 *  rascunho do cadastro volta depois de entrar de novo; os anexos, não. */
export const LIMITE_PARADO_MS = 20 * 60 * 1000;

export function paradoDemais(
  ultimaAtividade: number,
  agora: number,
  limite = LIMITE_PARADO_MS,
): boolean {
  return agora - ultimaAtividade >= limite;
}

/** O servidor recusou a SESSÃO (venceu, ou foi encerrada). */
export function sessaoMorreu(erro: unknown): boolean {
  return erro instanceof ErroDoServidor && erro.status === 401;
}

/** Este clique troca de área por dentro da página? */
export function cliqueQueNavega(e: {
  button: number;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
  defaultPrevented: boolean;
}): boolean {
  return (
    e.button === 0 &&
    !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey &&
    !e.defaultPrevented
  );
}
