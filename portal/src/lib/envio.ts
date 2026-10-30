/**
 * O cliente do servidor do portal.
 *
 * O PORTAL FUNCIONA COM E SEM SERVIDOR, e isso é decisão, não transição
 * inacabada:
 *
 * - **com** `VITE_API` configurada, o cadastro é enviado e a pessoa recebe um
 *   protocolo. É o fluxo final;
 * - **sem** ela, o portal confere tudo no aparelho e a pessoa baixa o pacote
 *   para entregar ao escritório por fora. É o que já existia, e continua
 *   servindo para demonstração e para sindicato que ainda não tem servidor.
 *
 * O que não existe é um terceiro caminho que finge enviar. A tela diz qual dos
 * dois está valendo.
 *
 * TODA MENSAGEM DE ERRO QUE CHEGA DAQUI VAI PARA A TELA. O servidor responde
 * `{erro, problemas?}`; jogar isso fora e mostrar "algo deu errado" é
 * transformar um diagnóstico preciso — "falta o arquivo sentenca.pdf" — em
 * suporte por telefone.
 */
import type { DocumentoEnviado, Rascunho } from "./tipos";
import { linhaDoCadastro, nomearDocumentos } from "./exportar";

const BASE: string = (import.meta.env.VITE_API ?? "").replace(/\/+$/, "");

export function servidorLigado(): boolean {
  return BASE.length > 0;
}

/** O apelido da entidade, do mesmo `?entidade=` que a página inicial lê. */
export function entidadeDoLink(): string {
  try {
    return (new URLSearchParams(window.location.search).get("entidade") ?? "")
      .trim()
      .toLowerCase();
  } catch {
    return "";
  }
}

export class ErroDoServidor extends Error {
  problemas: string[];
  status: number;
  constructor(mensagem: string, status: number, problemas: string[] = []) {
    super(mensagem);
    this.name = "ErroDoServidor";
    this.status = status;
    this.problemas = problemas;
  }
}

async function pedir(caminho: string, corpo: unknown): Promise<any> {
  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}${caminho}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(corpo),
    });
  } catch {
    throw new ErroDoServidor(
      "Não conseguimos falar com o servidor. Confira a sua conexão.",
      0,
    );
  }
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    const d = dados?.detail ?? {};
    throw new ErroDoServidor(
      d.erro ?? "O servidor recusou o pedido.",
      resposta.status,
      Array.isArray(d.problemas) ? d.problemas : [],
    );
  }
  return dados;
}

export interface Entidade {
  apelido: string;
  nome: string;
  /** O SERVIDOR é quem sabe que isto é demonstração, não o portal: o código
   *  aqui é o mesmo nos dois casos, e deixá-lo adivinhar pelo endereço
   *  erraria no dia em que o endereço mudasse. */
  demonstracao?: boolean;
  aviso_demonstracao?: string;
}

export async function verEntidade(apelido: string): Promise<Entidade | null> {
  if (!servidorLigado() || !apelido) return null;
  try {
    const r = await fetch(`${BASE}/api/entidade/${encodeURIComponent(apelido)}`);
    if (!r.ok) return null;
    return (await r.json()) as Entidade;
  } catch {
    return null;
  }
}

export interface CodigoPedido {
  minutos: number;
  aviso: string;
  /** Só em PROTOCOL_MODO_ENSAIO. Existe para a tela poder DIZER que é ensaio. */
  codigoDoEnsaio?: string;
}

export async function pedirCodigo(
  entidade: string,
  cpf: string,
): Promise<CodigoPedido> {
  const d = await pedir("/api/acesso/codigo", { entidade, cpf });
  return {
    minutos: d.minutos ?? 15,
    aviso: d.aviso ?? "",
    codigoDoEnsaio: d.codigo_do_ensaio,
  };
}

export async function conferirCodigo(
  entidade: string,
  cpf: string,
  codigo: string,
): Promise<{ token: string; nome: string }> {
  const d = await pedir("/api/acesso/conferir", { entidade, cpf, codigo });
  return { token: d.token, nome: d.nome ?? "" };
}

export interface Recibo {
  protocolo: string;
  recebido_em: string;
  entidade: string;
  arquivos: Record<string, string>;
  substituiu_protocolo: string;
}

/**
 * Manda o cadastro. `arquivos` traz os bytes de verdade.
 *
 * Os nomes vão do CONTRATO, nunca do nome que a pessoa deu ao arquivo: o
 * servidor recusa qualquer nome fora do contrato, e mandar "Scan (3).pdf"
 * seria pedir 422 em cima de um cadastro correto.
 */
export async function enviarCadastro(
  token: string,
  rascunho: Rascunho,
  arquivos: Map<number, File>,
): Promise<Recibo> {
  const corpo = new FormData();
  corpo.append("token", token);
  corpo.append("linha", JSON.stringify(linhaDoCadastro(rascunho)));

  // O nome vem do contrato e leva índice quando o tipo aceita vários — três
  // anos de contracheque são três arquivos do mesmo tipo, e mandar os três
  // como "contribuicao.pdf" faria o último apagar os outros no servidor.
  const nomes = nomearDocumentos(rascunho);
  rascunho.documentos.forEach((doc, posicao) => {
    const arquivo = arquivos.get(doc.chave);
    if (!arquivo) {
      throw new ErroDoServidor(
        `O arquivo "${doc.nomeOriginal}" não está mais na memória do ` +
          `navegador. Anexe de novo antes de enviar.`,
        0,
      );
    }
    corpo.append("arquivos", arquivo, nomes.get(posicao) ?? doc.nomeOriginal);
  });

  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}/api/cadastro`, {
      method: "POST",
      body: corpo,
    });
  } catch {
    throw new ErroDoServidor(
      "O envio não completou. Confira a sua conexão e tente de novo — " +
        "nada foi gravado.",
      0,
    );
  }
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    const d = dados?.detail ?? {};
    throw new ErroDoServidor(
      d.erro ?? "O servidor recusou o cadastro.",
      resposta.status,
      Array.isArray(d.problemas) ? d.problemas : [],
    );
  }
  return dados as Recibo;
}

/** Documentos no rascunho cujos bytes já não estão na memória. */
export function documentosParaReanexar(
  enviados: DocumentoEnviado[],
  arquivos: Map<string, File>,
): DocumentoEnviado[] {
  return enviados.filter((d) => !arquivos.has(d.tipo));
}

// ------------------------------------------------------- consulta (Produto B)

export interface ProcessoAcompanhado {
  numero: string;
  tribunal: string;
  ultimo_movimento: { data: string; nome: string; grau: string } | null;
}

export interface MeusProcessos {
  nome: string;
  processos: ProcessoAcompanhado[];
  limite: string;
}

/** O que o filiado logado acompanha. O CPF NÃO viaja: o servidor filtra pela
 *  sessão, e mandar CPF aqui transformaria a consulta em pesquisa de
 *  filiação. */
export async function meusProcessos(token: string): Promise<MeusProcessos> {
  const r = await fetch(`${BASE}/api/meus-processos`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    throw new ErroDoServidor(
      corpo?.detail?.erro ?? "não foi possível consultar",
      r.status,
    );
  }
  return {
    nome: corpo.nome ?? "",
    processos: corpo.processos ?? [],
    limite: corpo.limite ?? "",
  };
}

export interface Retrato {
  linhas: number;
  total: number;
  alcancaveis: number;
  inalcancaveis: number;
  divergentes: number;
  cadastrados: number;
  sem_cadastro: number;
  fora_do_acervo: number;
  com_processo: number;
  nao_sabe_o_processo: number;
  sem_processo: number;
  acompanhando: number;
  processos_acompanhados: number;
  querem_aviso: number;
  falta_por_campo: Record<string, number>;
  falta_nominal: Record<string, string[]>;
  inalcancaveis_por_cpf: Record<string, string>;
}

export interface Inalcancavel {
  chave: string;
  nome: string;
  motivo: string;
}

export interface PainelDoGestor {
  nome: string;
  manchete: string;
  retrato: Retrato;
  inalcancaveis: Inalcancavel[];
  tem_acervo: boolean;
}

export async function verCompletude(
  apelido: string,
  token: string,
): Promise<PainelDoGestor> {
  const r = await fetch(
    `${BASE}/api/entidade/${encodeURIComponent(apelido)}/completude`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    throw new ErroDoServidor(
      corpo?.detail?.erro ?? "não foi possível abrir o painel",
      r.status,
    );
  }
  return {
    nome: corpo.nome ?? "",
    manchete: corpo.manchete ?? "",
    retrato: corpo.retrato,
    inalcancaveis: corpo.inalcancaveis ?? [],
    tem_acervo: Boolean(corpo.tem_acervo),
  };
}

/** Qual tela o link pede: o cadastro, a consulta do filiado ou o painel. */
export type Tela = "cadastro" | "consulta" | "painel";

export function telaDoLink(): Tela {
  try {
    const q = new URLSearchParams(window.location.search);
    if (q.has("painel")) return "painel";
    if (q.has("consulta")) return "consulta";
  } catch {
    /* sem window: cai no cadastro, que é o padrão */
  }
  return "cadastro";
}
