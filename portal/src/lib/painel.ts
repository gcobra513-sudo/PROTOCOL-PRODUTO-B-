/**
 * O que o painel do sindicato diz, a partir do panorama.
 *
 * A DISTINÇÃO QUE FAZ O PAINEL VALER: o maior gargalo da base **não é**
 * necessariamente o que o sindicato pode resolver. Um tema afetado no STJ
 * pode segurar a base inteira, e não há decisão de diretoria que o destrave.
 *
 * Então são duas frases diferentes, e confundi-las seria mandar o sindicato
 * trabalhar no que não depende dele:
 *
 *   o maior            quantas pessoas estão paradas, e no quê
 *   o maior ACIONÁVEL  o que a diretoria resolve amanhã e move mais gente
 *
 * A segunda é a que vale a reunião.
 */
import type { Gargalo } from "./envio";

/** O maior gargalo que o próprio sindicato destrava, ou nulo se não houver.
 *
 *  Os gargalos já vêm do servidor do maior para o menor, então o primeiro da
 *  categoria certa é o maior dela. Reordenar aqui seria duplicar uma regra
 *  que já tem dono. */
export function primeiroAcionavel(gargalos: Gargalo[]): Gargalo | null {
  return gargalos.find((g) => g.quem === "CONFERENCIA") ?? null;
}

/** Quanta gente está parada em pendência de tribunal — e só de tribunal.
 *
 *  Serve para a frase que evita trabalho inútil: dizer ao sindicato que
 *  N pessoas não dependem dele nem delas. */
export function presosNoTribunal(gargalos: Gargalo[]): number {
  return Math.max(
    0,
    ...gargalos.filter((g) => g.quem === "TRIBUNAL").map((g) => g.pessoas),
    0,
  );
}

/** "1 pessoa" / "12 pessoas". Plural errado num painel que o diretor mostra
 *  em reunião é o tipo de descuido que faz duvidar do número ao lado. */
export function pessoas(n: number): string {
  return n === 1 ? "1 pessoa" : `${n} pessoas`;
}

/** A fração de uma ação, como o painel mostra: "3 de 10 (30%)".
 *
 *  Sem denominador, "3 participam" não diz nada — 3 de 4 e 3 de 4.000 são
 *  situações opostas. */
export function fracao(parte: number, total: number): string {
  if (total <= 0) return "—";
  return `${parte} de ${total} (${Math.round((parte / total) * 100)}%)`;
}
