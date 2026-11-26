/**
 * O encaminhamento ao escritório, em palavras — para os três que o leem.
 *
 * A situação vem do servidor como código de uma lista fechada. Aqui ela vira
 * frase, e a frase muda com o leitor: o filiado precisa saber o que ELE faz
 * (quase sempre, nada); o escritório, o que abrir primeiro; o sindicato,
 * onde está parado.
 */
import type { CasoDoEscritorio, Encaminhamento, EscritorioDoSindicato } from "./envio";

const ROTULOS: Record<string, string> = {
  ENCAMINHADO: "Aguardando o escritório",
  RECEBIDO: "Recebido",
  PENDENTE: "Falta documento",
  COMPLETO: "Documentação completa",
};

/** Vazio para o que a tela não conhece: código cru não vai para a pessoa. */
export function rotuloDaSituacao(situacao: string): string {
  return ROTULOS[situacao] ?? "";
}

export function tomDaSituacao(situacao: string): "bom" | "alerta" | "neutro" {
  if (situacao === "COMPLETO") return "bom";
  if (situacao === "PENDENTE") return "alerta";
  return "neutro";
}

function dia(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

function lista(itens: string[]): string {
  if (itens.length <= 1) return itens.join("");
  return `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}`;
}

/** O que o FILIADO lê. Resposta inteira: com quem está, e o que ele faz.
 *  Vazio para situação desconhecida — frase inventada sobre o caso de
 *  alguém é pior que frase nenhuma. */
export function fraseParaOFiliado(e: Encaminhamento): string {
  if (e.situacao === "ENCAMINHADO") {
    const quando = dia(e.encaminhado_em);
    return (
      `O sindicato encaminhou o seu caso a este escritório${quando ? ` em ${quando}` : ""}. ` +
      "Ele ainda não confirmou o recebimento. Você não precisa fazer nada agora."
    );
  }
  if (e.situacao === "RECEBIDO") {
    return "O escritório recebeu o seu caso e está conferindo os documentos. Você não precisa fazer nada agora.";
  }
  if (e.situacao === "PENDENTE") {
    return (
      `O escritório recebeu o seu caso e precisa de: ${lista(e.faltam)}. ` +
      "Envie pelo seu cadastro, aqui no portal."
    );
  }
  if (e.situacao === "COMPLETO") {
    return "O escritório recebeu o seu caso e a documentação está completa. Não falta nada da sua parte.";
  }
  return "";
}

const ORDEM = ["ENCAMINHADO", "RECEBIDO", "PENDENTE", "COMPLETO"];

/** A fila do ESCRITÓRIO: o que ainda não foi aberto primeiro, o completo
 *  por último, e dentro de cada situação o mais antigo na frente. */
export function ordemDeTrabalho<T extends { situacao: string; encaminhado_em: string }>(
  casos: T[],
): T[] {
  const peso = (s: string) => {
    const i = ORDEM.indexOf(s);
    return i < 0 ? ORDEM.length : i;
  };
  return [...casos].sort(
    (a, b) =>
      peso(a.situacao) - peso(b.situacao) ||
      a.encaminhado_em.localeCompare(b.encaminhado_em),
  );
}

const n = (q: number, um: string, muitos: string) => `${q} ${q === 1 ? um : muitos}`;

/** O que o SINDICATO lê de cada escritório. Os parados na frente: é onde o
 *  filiado está ligando para a sede. */
export function resumoDoEscritorio(e: EscritorioDoSindicato): string[] {
  if (e.casos === 0) return ["Nenhum caso encaminhado ainda."];
  const linhas: string[] = [];
  if (e.parados > 0) {
    linhas.push(
      `${n(e.parados, "caso encaminhado", "casos encaminhados")} há mais de 7 dias ` +
        "que o escritório ainda não recebeu.",
    );
  }
  linhas.push(
    `${n(e.casos, "caso", "casos")} ao todo: ${e.encaminhados} aguardando o escritório, ` +
      `${n(e.recebidos, "recebido", "recebidos")}, ${e.pendentes} com documento faltando, ` +
      `${e.completos} com a documentação completa.`,
  );
  return linhas;
}


// ------------------------------------------------- o painel do escritório

function plano(texto: string): string {
  return (texto ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/** A fila, pelo que o escritório digitou e pela situação escolhida. O texto
 *  procura no nome e no CPF — é pelo CPF que o escritório casa o caso com
 *  os registros dele. */
export function filtrarCasos(
  casos: CasoDoEscritorio[],
  filtro: { texto: string; situacao: string; entidade?: string },
): CasoDoEscritorio[] {
  const texto = plano(filtro.texto).trim();
  const digitos = texto.replace(/\D/g, "");
  return casos.filter((c) => {
    if (filtro.entidade && c.entidade !== filtro.entidade) return false;
    if (filtro.situacao && c.situacao !== filtro.situacao) return false;
    if (!texto) return true;
    if (plano(c.nome).includes(texto)) return true;
    return digitos.length >= 3 && c.cpf.includes(digitos);
  });
}

/** Há quantos dias o caso foi encaminhado. Nulo se a data não se lê. */
export function diasNaFila(encaminhadoEm: string, agora: Date): number | null {
  const quando = Date.parse(encaminhadoEm);
  if (!encaminhadoEm || Number.isNaN(quando)) return null;
  return Math.max(0, Math.floor((agora.getTime() - quando) / 86_400_000));
}

function cpfPontuado(c: string): string {
  return c.length === 11 ? `${c.slice(0, 3)}.${c.slice(3, 6)}.${c.slice(6, 9)}-${c.slice(9)}` : c;
}

/** Uma célula de CSV. O que começa com `= + - @` ganha um apóstrofo: num
 *  Excel, um nome como `=CMD()` seria executado como fórmula por quem abre
 *  a planilha — e o nome vem de um cadastro que o escritório não digitou. */
function celula(valor: string): string {
  let v = (valor ?? "").replace(/[\r\n]+/g, " ");
  if (/^[=+\-@]/.test(v)) v = `'${v}`;
  return /[;"]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

/** Os casos do escritório, em planilha: para ele levar ao sistema dele. Com
 *  BOM e ponto e vírgula, que é como o Excel em português abre sem pedir. */
export function csvDosCasos(
  casos: CasoDoEscritorio[],
  possiveis: { tipo: string; rotulo: string }[],
): string {
  const rotulo = (t: string) => possiveis.find((p) => p.tipo === t)?.rotulo ?? t;
  // COM VÁRIOS SINDICATOS, a primeira coluna diz de qual é cada caso: sem
  // ela a planilha junta filiados de entidades diferentes numa lista só.
  const varios = casos.some((c) => c.sindicato);
  const linhas = [
    ["Nome", "CPF", "E-mail", "Telefone", "Ação", "Situação", "Falta", "Documentos enviados", "Encaminhado em"],
    ...casos.map((c) => [
      c.nome, cpfPontuado(c.cpf), c.email, c.telefone, c.rotulo,
      rotuloDaSituacao(c.situacao), c.faltam.map(rotulo).join(", "),
      c.documentos.map((d) => d.rotulo).join(", "), dia(c.encaminhado_em),
    ]),
  ].map((l, i) => (varios ? [i === 0 ? "Sindicato" : (casos[i - 1]?.sindicato ?? ""), ...l] : l));
  return "\uFEFF" + linhas.map((l) => l.map(celula).join(";")).join("\r\n") + "\r\n";
}
