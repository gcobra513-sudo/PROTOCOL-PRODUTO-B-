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
import type { Gargalo, ResultadoDoApagamento } from "./envio";

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

/** Como cada lugar do apagamento se chama na tela do gestor.
 *
 *  O vocabulário interno não sobe para a tela: "tombstone" e "vestígio" são
 *  palavras nossas, e um gestor de sindicato lendo "tombstone" num painel
 *  não aprende nada — desconfia. */
const LUGARES: [keyof ResultadoDoApagamento, string][] = [
  ["arquivos", "arquivos no disco (documentos entregues e histórico)"],
  ["diario", "envios redigidos no diário"],
  ["rol", "linhas na planilha de filiados"],
  ["acervo", "ingestões da planilha"],
  ["portao", "códigos e sessões de acesso"],
  ["logs", "linhas de registro"],
];

export interface ResumoDoApagamento {
  /** Terminou? É `vestigios` vazio, e nada mais. */
  terminou: boolean;
  frase: string;
  linhas: string[];
  nota?: string;
}

/** O que a tela diz depois de um apagamento.
 *
 *  A ÚNICA REGRA QUE NÃO SE QUEBRA AQUI: `vestigios` não vazio não pode ler
 *  como sucesso. O servidor devolve 200 com a lista cheia de propósito —
 *  dizer 200 e esconder o resto seria afirmar um apagamento que não
 *  aconteceu —, e uma tela que pintasse isso de verde desfaria essa
 *  honestidade na última polegada, que é justamente onde ela importa.
 *
 *  O `marcador` NÃO SOBE. Ele é HMAC do CPF: identificador estável por
 *  pessoa, e portanto mais um lugar com dado pessoal. Serve ao operador no
 *  log, não ao gestor na tela. */
export function resumoDoApagamento(
  saida: ResultadoDoApagamento,
): ResumoDoApagamento {
  const linhas: string[] = [];
  for (const [chave, texto] of LUGARES) {
    const n = Number(saida[chave] ?? 0);
    // ZERO NÃO VIRA LINHA: dez linhas com zero esconderiam a única que não
    // é zero, e é essa que o gestor precisa ver.
    if (n > 0) linhas.push(`${n} ${texto}`);
  }
  for (const [tabela, n] of Object.entries(saida.banco ?? {})) {
    if (n > 0) linhas.push(`${n} em ${tabela} (banco de consulta)`);
  }

  const sobrou = saida.vestigios?.length ?? 0;
  const terminou = sobrou === 0;
  return {
    terminou,
    linhas,
    frase: terminou
      ? "Pronto: nada sobrou desta pessoa nesta entidade."
      : `Ainda sobra coisa desta pessoa em ${sobrou} lugar(es). ` +
        "O apagamento NÃO terminou — é seguro repetir, e repetir é o que " +
        "resolve. Se insistir, avise quem opera o servidor.",
    nota: saida.email_conhecido
      ? undefined
      : "O sindicato não tinha e-mail desta pessoa em cadastro, então o " +
        "aviso de que o pedido foi atendido precisa sair por outro caminho.",
  };
}
