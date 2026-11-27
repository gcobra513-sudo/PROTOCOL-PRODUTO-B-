/**
 * As teses acompanhadas, em palavras.
 *
 * O alcance vem do servidor como três contagens, e é uma SIMULAÇÃO: quantas
 * pessoas teriam o caminho aberto se a tese fosse conferida por advogado.
 * Por isso a frase diz "poderiam" enquanto ninguém conferiu, e só diz
 * "podem" depois — a diferença entre as duas palavras é a regra do produto.
 */
import type { Tese } from "./envio";

export function saudacao(agora: Date): string {
  const h = agora.getHours();
  if (h >= 5 && h < 12) return "Bom dia";
  if (h >= 12 && h < 18) return "Boa tarde";
  return "Boa noite";
}

const DO_TEMA: Record<string, string> = {
  julgado: "Julgado",
  afetado: "Vai ser julgado",
  a_conferir: "Situação a conferir",
};
const DA_ACAO: Record<string, string> = {
  transitado_em_julgado: "Ação com trânsito em julgado",
  em_andamento: "Ação em andamento",
};

/** Vazio para o código que a tela não conhece. */
export function rotuloDaSituacaoDaTese(t: Pick<Tese, "tipo" | "situacao">): string {
  return (t.tipo === "acao" ? DA_ACAO : DO_TEMA)[t.situacao] ?? "";
}

const pessoas = (n: number, um: string, muitos: string) =>
  `${n} ${n === 1 ? `pessoa ${um}` : `pessoas ${muitos}`}`;

export function alcanceEmPalavras(
  t: Pick<Tese, "tipo" | "situacao" | "conferida" | "poderiam" | "dependem" | "fora">,
): string {
  if (t.poderiam + t.dependem + t.fora === 0) return "Ninguém da base é alcançado por enquanto.";
  if (t.tipo === "tema" && t.situacao === "afetado") {
    return `Ainda não há tese. ${pessoas(t.dependem, "é", "são")} da carreira que o tema alcança.`;
  }
  const abre = t.conferida ? "Conferida por advogado:" : "Se for conferida por advogado:";
  const verbo = t.conferida ? ["pode", "podem"] : ["poderia", "poderiam"];
  return (
    `${abre} ${pessoas(t.poderiam, verbo[0]!, verbo[1]!)}, ` +
    `${t.dependem} ${t.dependem === 1 ? "depende" : "dependem"} de alguma conferência e ` +
    `${t.fora} ${t.fora === 1 ? "fica" : "ficam"} de fora.`
  );
}


// ------------------------------------------- vários sindicatos, uma lista

export interface TeseJunta extends Tese {
  /** Como a soma se divide: um item por sindicato que tem esta tese. */
  porSindicato: { entidade: string; nome: string; poderiam: number; dependem: number; fora: number }[];
}

/** As teses de todos os sindicatos do escritório, UMA LINHA POR TESE.
 *
 *  Cada sindicato traz as teses da carreira dele, e a mesma tese aparece em
 *  mais de um. Mostrar uma lista por sindicato fazia o escritório ler o
 *  mesmo tema várias vezes para somar de cabeça — e a pergunta dele é uma
 *  só: "este julgamento alcança quantas pessoas, e de quem?".
 *
 *  A ordem é a da notícia: o que tem a data mais recente primeiro. */
export function tesesJuntas(
  sindicatos: { entidade: string; nome: string; teses?: Tese[] }[],
): TeseJunta[] {
  const juntas = new Map<string, TeseJunta>();
  for (const s of sindicatos) {
    for (const t of s.teses ?? []) {
      const atual =
        juntas.get(t.id) ?? { ...t, poderiam: 0, dependem: 0, fora: 0, porSindicato: [] };
      atual.poderiam += t.poderiam;
      atual.dependem += t.dependem;
      atual.fora += t.fora;
      atual.porSindicato.push({
        entidade: s.entidade, nome: s.nome,
        poderiam: t.poderiam, dependem: t.dependem, fora: t.fora,
      });
      juntas.set(t.id, atual);
    }
  }
  return [...juntas.values()].sort((a, b) => (b.data || "").localeCompare(a.data || ""));
}

/** "hoje", "ontem", "há 12 dias". Vazio para data ilegível ou no futuro. */
export function haQuanto(data: string, agora: Date): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(data ?? "");
  if (!m) return "";
  const dia = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const hoje = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate());
  const dias = Math.round((hoje.getTime() - dia.getTime()) / 86_400_000);
  if (dias < 0) return "";
  if (dias === 0) return "hoje";
  if (dias === 1) return "ontem";
  return `há ${dias} dias`;
}
