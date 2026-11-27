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
