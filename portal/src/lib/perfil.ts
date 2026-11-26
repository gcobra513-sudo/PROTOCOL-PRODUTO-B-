/**
 * O MENU POR PERFIL: cada pessoa vê só o que é dela.
 *
 * O menu mostrava tudo para todos — o filiado via "Painel do sindicato", o
 * gestor via as áreas de filiado. Quem tem pouca prática com computador
 * clica no que está na tela, e o que estava na tela não era dele.
 *
 * ISTO NÃO É PERMISSÃO. Quem decide o que cada um pode é o servidor, em cada
 * rota; aqui só se decide o que a tela OFERECE.
 */
import type { Tela } from "./envio";

export interface Papeis {
  filiado: boolean;
  gestor: boolean;
  /** É de um escritório contratado pelo sindicato. */
  escritorio?: boolean;
}

/** `null`: ninguém entrou, ou o servidor ainda não respondeu. */
export function gruposDoMenu(
  papeis: Papeis | null,
): { filiado: boolean; sindicato: boolean; escritorio: boolean } {
  const escritorio = Boolean(papeis?.escritorio);
  // Antes de entrar a pessoa ainda não disse quem é: as duas portas ficam.
  // E se o servidor não soube dizer nenhum dos papéis, mostra tudo — um menu
  // vazio prende a pessoa numa tela sem saída.
  //
  // A PORTA DO ESCRITÓRIO SÓ APARECE PARA QUEM É DELE. É a porta de poucos:
  // no menu de todo mundo ela confundiria o filiado.
  if (!papeis || (!papeis.filiado && !papeis.gestor && !escritorio)) {
    return { filiado: true, sindicato: true, escritorio: false };
  }
  return { filiado: papeis.filiado, sindicato: papeis.gestor, escritorio };
}

const DE_FILIADO: readonly Tela[] = [
  "area", "cadastro", "acoes", "processos", "atendimento",
];

/** Para onde a pessoa vai quando entrou pela porta que não é a dela.
 *
 *  O gestor que digitou o CPF numa área de filiado veria tudo vazio, e o
 *  filiado que entrou pelo painel veria uma recusa. Levar cada um para a
 *  sua tela é o que ele queria ao entrar. */
export function telaDeChegada(papeis: Papeis | null, tela: Tela): Tela {
  if (!papeis) return tela;
  const so = (qual: "filiado" | "gestor" | "escritorio") =>
    Boolean(papeis[qual]) &&
    (["filiado", "gestor", "escritorio"] as const).every(
      (outro) => outro === qual || !papeis[outro],
    );
  // Quem é só do escritório tem uma tela, e é para ela que vai.
  if (so("escritorio")) return "escritorio";
  if (tela === "escritorio" && !papeis.escritorio) {
    if (papeis.gestor) return "painel";
    if (papeis.filiado) return "area";
    return tela;
  }
  if (so("gestor") && DE_FILIADO.includes(tela)) return "painel";
  if (so("filiado") && tela === "painel") return "area";
  return tela;
}
