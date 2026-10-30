/**
 * O que a conta do filiado guarda.
 *
 * A FORMA VEM DO CONTRATO, não daqui: `compartilhado/contrato_cadastro.json`
 * é lido pelo portal e pelo servidor, porque duas listas de campos mantidas
 * à mão divergem — e a divergência só aparece na primeira conta de verdade.
 *
 * O QUE O PRODUTO B PEDE, E O QUE ELE RECUSA PEDIR:
 *
 *   contribuição   prova o PERÍODO DE FILIAÇÃO, e é o cruzamento desse
 *                  período contra o da ação coletiva que responde "de quais
 *                  ações eu faço parte". É o único documento obrigatório
 *   carreira       cargo e situação definem a CATEGORIA alcançada
 *   sentença e     só se a pessoa tiver. Decidem se ela EXECUTA (tem
 *   certidão       título) ou AJUÍZA (não tem)
 *
 * Não se pede procuração, identidade nem comprovante de residência. São
 * documentos para LITIGAR, e exigi-los de quem só quer saber se tem direito
 * derruba a conclusão do cadastro sem melhorar resposta nenhuma.
 *
 * E duas coisas que o tipo deixa explícitas:
 *
 * 1. `nao_sei` é resposta completa em tudo que é judicial. A pessoa admitir
 *    que não sabe é muito melhor que chutar — número chutado é pior que
 *    campo vazio, porque ninguém sabe que está errado.
 * 2. nada de senha. Entra-se por CPF e código no e-mail que o SINDICATO
 *    cadastrou. Senha é a principal causa de abandono nesse tipo de conta, e
 *    é o que mais vaza.
 */

import contrato from "../../../compartilhado/contrato_cadastro.json";

export const CONTRATO = contrato;

export type Resposta = "sim" | "nao" | "nao_sei" | "";

export type SituacaoFuncional = "ativo" | "aposentado" | "pensionista" | "";

export interface Identificacao {
  nome: string;
  cpf: string;
  email: string;
  telefone: string;
  dataNascimento: string;
}

export interface Carreira {
  /** Define a CATEGORIA alcançada pelas ações coletivas. Sem ele não há
   *  cruzamento, e sem cruzamento não há resposta. */
  cargo: string;
  situacao: SituacaoFuncional;
  unidade: string;
  dataIngresso: string;
  dataAposentadoria: string;
}

export interface Filiacao {
  /** AAAA-MM. Vem dos comprovantes de contribuição, e é o campo mais
   *  importante da conta: é ele que decide de quais ações a pessoa faz
   *  parte. */
  desde: string;
  /** AAAA-MM, ou VAZIO para "ainda sou filiado". Vazio é resposta, não
   *  omissão — tratá-lo como omissão reprovaria quem está filiado hoje. */
  ate: string;
}

export interface Judicial {
  temProcesso: Resposta;
  /** De qualquer tribunal. Acompanhar não é protocolar. */
  numeros: string[];
  jaExecutou: Resposta;
  temAcaoPropria: Resposta;
}

export type TipoDocumento = "contribuicao" | "sentenca" | "certidao_transito";

export interface EspecDocumento {
  tipo: TipoDocumento;
  rotulo: string;
  obrigatorio: boolean;
  multiplos: boolean;
  ajuda: string;
}

/** Os documentos pedidos, direto do contrato. Acrescentar um é editar o
 *  JSON; o portal e o servidor passam a conhecê-lo juntos. */
export const DOCUMENTOS: EspecDocumento[] = Object.entries(
  CONTRATO.documentos as Record<
    string,
    { rotulo: string; obrigatorio: boolean; multiplos: boolean; ajuda: string }
  >,
).map(([tipo, d]) => ({ tipo: tipo as TipoDocumento, ...d }));

export interface DocumentoEnviado {
  /** Onde os bytes estão, em `lib/arquivos.ts`. Um NÚMERO e não o tipo,
   *  porque a contribuição aceita vários e uma chave por tipo faria o
   *  segundo comprovante apagar o primeiro. */
  chave: number;
  tipo: TipoDocumento;
  nomeOriginal: string;
  nomeFinal: string;
  tamanho: number;
  sha256: string;
  /** PDF de scanner não tem camada de texto, e sem texto não há o que ler.
   *  Avisar aqui poupa a pessoa de descobrir depois que o documento dela não
   *  serviu para nada. */
  temTexto: boolean;
  cpfEncontrado: boolean;
}

/** O nome com que o arquivo é guardado. Com índice quando o tipo aceita
 *  vários — três anos de contracheque são três arquivos do mesmo tipo. */
export function nomeDeArquivo(tipo: TipoDocumento, indice = 0): string {
  const espec = DOCUMENTOS.find((d) => d.tipo === tipo);
  return espec?.multiplos ? `${tipo}-${indice + 1}.pdf` : `${tipo}.pdf`;
}

export interface Rascunho {
  /** 2: a conta do Produto B. A 1 era o cadastro do Produto A, com
   *  procuração e endereço, e um rascunho velho no navegador de alguém não
   *  pode ser lido como se fosse desta versão. */
  versao: 2;
  atualizadoEm: string;
  etapa: number;
  identificacao: Identificacao;
  carreira: Carreira;
  filiacao: Filiacao;
  judicial: Judicial;
  documentos: DocumentoEnviado[];
  /** A declaração final: os dados são meus e são verdadeiros. */
  confirmou: boolean;
  /** Opcional, e não vem marcado. Opt-in pré-marcado não é opt-in. */
  querAviso: boolean;
}

export const RASCUNHO_VAZIO: Rascunho = {
  versao: 2,
  atualizadoEm: "",
  etapa: 0,
  identificacao: {
    nome: "",
    cpf: "",
    email: "",
    telefone: "",
    dataNascimento: "",
  },
  carreira: {
    cargo: "",
    situacao: "",
    unidade: "",
    dataIngresso: "",
    dataAposentadoria: "",
  },
  filiacao: { desde: "", ate: "" },
  judicial: {
    temProcesso: "",
    numeros: [],
    jaExecutou: "",
    temAcaoPropria: "",
  },
  documentos: [],
  confirmou: false,
  querAviso: false,
};

/** Quais documentos esta conta ainda precisa.
 *
 *  NÃO DEPENDE DO QUE A PESSOA DISSE SOBRE PROCESSO. Declarar "tenho
 *  processo" não passa a exigir sentença: ela pode saber o número e não ter
 *  o papel em mãos, e bloquear por isso a deixaria sem resposta — justamente
 *  ela, que é quem mais precisa. */
export function documentosFaltando(r: Rascunho): EspecDocumento[] {
  const enviados = new Set(r.documentos.map((d) => d.tipo));
  return DOCUMENTOS.filter((d) => d.obrigatorio && !enviados.has(d.tipo));
}
