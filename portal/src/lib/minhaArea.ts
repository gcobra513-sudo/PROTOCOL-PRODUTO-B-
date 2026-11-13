/**
 * MINHA ÁREA: o que a primeira tela de quem entrou diz.
 *
 * Ela RESUME as outras áreas — e por isso não diz nada que elas não digam.
 * Nenhuma função aqui dá veredicto: conta, aponta, e manda a pessoa para a
 * área que explica com os motivos. Um "você pode" num cartão de resumo seria
 * um veredicto sem a explicação, e é a explicação que o torna honesto.
 *
 * E ENQUANTO NÃO SABE, NÃO DIZ: cada cartão tem três estados — consultando,
 * não deu para consultar, e o dado. Nunca um zero no lugar de "não sei".
 */
import type { MeuCadastro, MeusProcessos, MinhasAcoes, Tela } from "./envio";

/** `null`: ainda consultando. `"erro"`: a consulta falhou. */
export type Consulta<T> = T | null | "erro";

export interface CartaoDaArea {
  estado: "bom" | "alerta" | "neutro";
  frase: string;
  /** O que o botão do cartão diz. */
  acao: string;
  tela: Tela;
}

function semDado(
  c: Consulta<unknown>,
  acao: string,
  tela: Tela,
): CartaoDaArea | null {
  if (c === null) return { estado: "neutro", frase: "Consultando…", acao, tela };
  if (c === "erro") {
    return {
      estado: "alerta",
      frase: "Não foi possível consultar agora.",
      acao,
      tela,
    };
  }
  return null;
}

/** "MARIA DA SILVA" → "Maria". Sem nome, vazio: a tela cumprimenta sem. */
export function primeiroNome(nome: string): string {
  const primeiro = nome.trim().split(/\s+/)[0] ?? "";
  if (!primeiro) return "";
  return primeiro.charAt(0).toUpperCase() + primeiro.slice(1).toLowerCase();
}

function soData(iso: string): string {
  const [ano, mes, dia] = (iso.slice(0, 10) || "").split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : iso;
}

export function cartaoDoCadastro(c: Consulta<MeuCadastro>): CartaoDaArea {
  const vazio = semDado(c, "Abrir meu cadastro", "cadastro");
  if (vazio) return vazio;
  const n = (c as MeuCadastro).documentos.length;
  if (n === 0) {
    return {
      estado: "alerta",
      frase: "Ainda não recebemos nenhum documento seu.",
      acao: "Enviar meus documentos",
      tela: "cadastro",
    };
  }
  return {
    estado: "bom",
    frase:
      n === 1
        ? "Já recebemos 1 tipo de documento seu."
        : `Já recebemos ${n} tipos de documento seus.`,
    acao: "Ver ou completar meu cadastro",
    tela: "cadastro",
  };
}

export function cartaoDasAcoes(c: Consulta<MinhasAcoes>): CartaoDaArea {
  const vazio = semDado(c, "Ver minhas ações", "acoes");
  if (vazio) return vazio;
  const n = (c as MinhasAcoes).acoes.filter(
    (a) => a.estado === "PARTICIPA",
  ).length;
  return {
    estado: "neutro",
    frase:
      n === 0
        ? "Ainda não deu para dizer de quais ações você faz parte."
        : n === 1
          ? "Você faz parte de 1 ação do seu sindicato."
          : `Você faz parte de ${n} ações do seu sindicato.`,
    acao: "Ver minhas ações",
    tela: "acoes",
  };
}

export function cartaoDosProcessos(c: Consulta<MeusProcessos>): CartaoDaArea {
  const vazio = semDado(c, "Ver meus processos", "processos");
  if (vazio) return vazio;
  const dados = c as MeusProcessos;
  const n = dados.processos.length;
  if (n === 0) {
    return {
      estado: "neutro",
      frase: "Você não informou nenhum processo.",
      acao: "Ver meus processos",
      tela: "processos",
    };
  }
  const partes = [
    n === 1 ? "Você acompanha 1 processo." : `Você acompanha ${n} processos.`,
  ];
  const ultimo = dados.processos
    .map((p) => p.ultimo_movimento)
    .filter((m): m is NonNullable<typeof m> => Boolean(m))
    .sort((a, b) => b.data.localeCompare(a.data))[0];
  if (ultimo) {
    partes.push(`Última movimentação: ${ultimo.nome}, em ${soData(ultimo.data)}.`);
  }
  // "Nada novo" só é verdade em relação à última vez que OLHAMOS. Sem essa
  // data, o silêncio seria lido como "não mudou nada".
  partes.push(
    dados.conferido_em
      ? `Conferido em ${soData(dados.conferido_em)}.`
      : "Ainda não conferimos o tribunal.",
  );
  return {
    estado: "neutro",
    frase: partes.join(" "),
    acao: "Ver meus processos",
    tela: "processos",
  };
}

/** O que depende da PRÓPRIA pessoa, e só isso. O que é do sindicato ou do
 *  tribunal ela não resolve — e listar aqui seria mandá-la ligar. */
export function oQueFaltaVoce(c: Consulta<MinhasAcoes>): string[] {
  if (!c || c === "erro") return [];
  return c.pendencias.filter((g) => g.quem === "VOCE").flatMap((g) => g.itens);
}

/** As perguntas que o Proto oferece de saída. */
export const PERGUNTAS_AO_PROTO = [
  "Em quais processos eu estou?",
  "O que falta eu fazer?",
  "Meus documentos chegaram?",
  "Meus dados estão certos?",
];
