/**
 * Como o resultado do motor é ESCRITO para a pessoa.
 *
 * O motor devolve `PARTICIPA` / `NAO_PODE` / `FALTA`. Nenhuma dessas palavras
 * vai para a tela como está: são estados de máquina, e a pessoa que abre a
 * página é uma servidora aposentada querendo saber se tem algo a receber.
 *
 * AS DUAS REGRAS QUE ESTES RÓTULOS NÃO QUEBRAM:
 *
 * 1. **nada promete dinheiro.** Nem "você tem direito a", nem "você vai
 *    receber". `PODE` quer dizer que as condições do catálogo estão
 *    satisfeitas E que um advogado homologou — não quer dizer valor na conta,
 *    e a diferença entre as duas coisas, dita errado, cria expectativa de
 *    dinheiro em gente aposentada;
 * 2. **quem fala com o filiado é o SINDICATO.** Nenhum rótulo menciona
 *    escritório.
 *
 * E a tabela é FECHADA: um estado novo no Python sem rótulo aqui apareceria
 * como `undefined` na tela. O teste cobre os valores conhecidos um por um.
 */

/** Os estados de participação, como `nucleo/participacao.py` os devolve. */
export const ESTADOS = ["PARTICIPA", "INDETERMINADO", "NAO_PARTICIPA"] as const;
/** Os veredictos, como `nucleo/motor.py` os devolve. */
export const VEREDICTOS = ["PODE", "FALTA", "NAO_PODE"] as const;
/** As trilhas, como `nucleo/entendimentos.py` as nomeia. */
export const TRILHAS = ["executar", "ajuizar"] as const;

export type Estado = (typeof ESTADOS)[number];
export type Veredicto = (typeof VEREDICTOS)[number];
export type Trilha = (typeof TRILHAS)[number];
export type Tom = "bom" | "neutro" | "alerta";

const DO_ESTADO: Record<Estado, { rotulo: string; tom: Tom }> = {
  PARTICIPA: { rotulo: "Você faz parte", tom: "bom" },
  // "Ainda" é a palavra que importa: INDETERMINADO não é "não".
  INDETERMINADO: { rotulo: "Ainda não dá para dizer", tom: "neutro" },
  NAO_PARTICIPA: { rotulo: "Você não faz parte", tom: "alerta" },
};

const DO_VEREDICTO: Record<Veredicto, { rotulo: string; tom: Tom }> = {
  // NÃO é "você vai receber". É "as condições estão satisfeitas e um
  // advogado conferiu" — e quem transforma isso em valor é outra etapa.
  PODE: { rotulo: "Caminho aberto, já conferido", tom: "bom" },
  FALTA: { rotulo: "Falta informação", tom: "neutro" },
  NAO_PODE: { rotulo: "Não cabe", tom: "alerta" },
};

const DA_TRILHA: Record<Trilha, { rotulo: string; explicacao: string }> = {
  executar: {
    rotulo: "Cobrar o que já foi decidido",
    explicacao:
      "Só existe quando há uma decisão definitiva em seu favor. Sem ela não há o que cobrar, por boa que seja a tese.",
  },
  ajuizar: {
    rotulo: "Entrar com ação nova",
    explicacao:
      "Não depende de decisão anterior. Depende de você se encaixar nos critérios e de não ter ação própria sobre o mesmo assunto.",
  },
};

export function rotuloDoEstado(estado: string): string {
  return DO_ESTADO[estado as Estado]?.rotulo ?? estado;
}

export function tomDoEstado(estado: string): Tom {
  return DO_ESTADO[estado as Estado]?.tom ?? "neutro";
}

export function rotuloDoVeredicto(v: string): string {
  return DO_VEREDICTO[v as Veredicto]?.rotulo ?? v;
}

export function tomDoVeredicto(v: string): Tom {
  return DO_VEREDICTO[v as Veredicto]?.tom ?? "neutro";
}

export function rotuloDaTrilha(t: string): string {
  return DA_TRILHA[t as Trilha]?.rotulo ?? t;
}

export function explicacaoDaTrilha(t: string): string {
  return DA_TRILHA[t as Trilha]?.explicacao ?? "";
}

/** "de 2004-01 a 2008-12 (60 meses)", ou "" quando não há interseção.
 *
 *  O período é o que o cálculo do valor vai usar depois. Mostrá-lo agora não
 *  é detalhe técnico: é a pessoa poder conferir se a nossa conta dos anos
 *  dela está certa, antes de qualquer valor existir. */
export function periodo(inicio: string, fim: string, meses: number): string {
  if (!inicio || !fim) return "";
  const m = meses === 1 ? "1 mês" : `${meses} meses`;
  return `de ${inicio} a ${fim} (${m})`;
}

/** O motivo sem repetir o nome da ação que já está no título logo acima.
 *
 *  O motor prefixa cada motivo com o rótulo porque ele devolve uma LISTA
 *  PLANA: a mesma frase pode ser de qualquer ação, e sem o prefixo quem lê a
 *  lista crua — o painel do sindicato, o diário — não saberia de qual. Na
 *  tela do filiado o nome está em negrito três linhas acima, e repeti-lo em
 *  cada item faz quatro linhas iguais que ninguém lê até o fim. */
export function semPrefixo(motivo: string, rotulo: string): string {
  const limpo = rotulo.replace(/^(Executar|Ajuizar):\s*/, "").trim();
  if (!limpo || !motivo.startsWith(limpo)) return motivo;
  const resto = motivo.slice(limpo.length).replace(/^\s*:?\s*/, "");
  if (!resto) return motivo;
  // Maiúscula no começo: o resto vinha de dentro da frase.
  return resto.charAt(0).toUpperCase() + resto.slice(1);
}

/** A primeira letra maiúscula, para a lista ler como lista.
 *
 *  Os motivos do motor começam ora com maiúscula ora com minúscula, porque
 *  alguns são frase inteira e outros continuam o rótulo que `semPrefixo`
 *  acabou de tirar. Numa lista com marcadores a mistura parece descuido —
 *  e descuido na tela é o que faz a pessoa duvidar do conteúdo. */
export function comoFrase(texto: string): string {
  const t = texto.trim();
  if (!t) return t;
  return t.charAt(0).toLocaleUpperCase("pt-BR") + t.slice(1);
}

/** A frase de uma linha no topo: o que a pessoa leva se não ler mais nada.
 *
 *  NÃO diz "nada encontrado" quando a lista está vazia — diz quantas ações
 *  foram olhadas. "Nada encontrado" soa a veredicto; "nenhuma ação a cruzar"
 *  é o fato. */
export function resumo(
  acoes: { estado: string }[],
  pendentesDoFiliado: number,
): string {
  if (acoes.length === 0) {
    return "Ainda não há ação a cruzar com os seus dados.";
  }
  const participa = acoes.filter((a) => a.estado === "PARTICIPA").length;
  const emAberto = acoes.filter((a) => a.estado === "INDETERMINADO").length;
  const partes: string[] = [];
  if (participa) {
    partes.push(
      participa === 1
        ? "Você faz parte de 1 ação"
        : `Você faz parte de ${participa} ações`,
    );
  }
  if (emAberto) {
    partes.push(
      emAberto === 1
        ? "1 ainda depende de conferência"
        : `${emAberto} ainda dependem de conferência`,
    );
  }
  if (partes.length === 0) {
    partes.push(
      acoes.length === 1
        ? "A única ação olhada não alcança você"
        : `Nenhuma das ${acoes.length} ações olhadas alcança você`,
    );
  }
  if (pendentesDoFiliado > 0) {
    partes.push(
      pendentesDoFiliado === 1
        ? "e há 1 item que depende de você"
        : `e há ${pendentesDoFiliado} itens que dependem de você`,
    );
  }
  return partes.join(", ").replace(/, e há/, " e há") + ".";
}
