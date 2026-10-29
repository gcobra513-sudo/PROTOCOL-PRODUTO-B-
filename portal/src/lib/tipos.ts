/**
 * O que o portal coleta. Um tipo só, usado pelas sete etapas e pela
 * exportação — se um campo entra aqui, entra no manifesto.
 *
 * Três decisões que a especificação exige e que o tipo deixa explícitas:
 *
 * 1. `naoSei` existe em processo e nas declarações. É deliberado: a pessoa
 *    admitir que não sabe é MUITO melhor que chutar. Obrigar a preencher só
 *    produz dado falso, e dado falso num lote de 15 mil é pior que campo
 *    vazio — porque ninguém sabe que está errado.
 * 2. o portal NÃO pergunta "você tem direito?". Quem decide elegibilidade é
 *    o jurídico, com base nos dados. Perguntar criaria expectativa indevida
 *    e resposta sem valor.
 * 3. nada de senha. Acesso por CPF + código. Senha é a principal causa de
 *    abandono nesse tipo de cadastro.
 */

import contrato from "../../../compartilhado/contrato_entrega.json";

/**
 * O CONTRATO DE DADOS com o motor, lido do arquivo compartilhado.
 *
 * Não repita nome de arquivo aqui. O portal nomeava "residencia.pdf" e o
 * verificador esperava "comprovante_residencia.pdf" — três dos seis nomes
 * divergiam, e isso só apareceria quando a primeira entrega de verdade
 * chegasse, com todas as pastas reprovando por arquivo faltando.
 */
export const CONTRATO = contrato;

export type Resposta = "sim" | "nao" | "nao_sei" | "";

export type SituacaoFuncional = "ativo" | "aposentado" | "pensionista" | "";

export interface DadosPessoais {
  nome: string;
  cpf: string;
  matricula: string;
  rg: string;
  /** OBRIGATÓRIA. É dela que sai a prioridade de tramitação: o PJe tem
   *  "Idoso(a)" e "Idoso(a) maior de 80 anos" na aba Características, e este
   *  lote é de servidores aposentados. Sem ela, ninguém pede prioridade —
   *  e numa fila de cinco mil execuções isso é tempo de vida de quem espera. */
  dataNascimento: string;
  /** Campos de endereço. Pendente de confirmação: o PJe pode exigi-los para
   *  distribuir (ver pergunta 23 em PERGUNTAS_JURIDICO.md). Ficam no
   *  formulário porque pedir e não usar é barato; usar e não ter é caro. */
  cep: string;
  logradouro: string;
  numero: string;
  complemento: string;
  bairro: string;
  municipio: string;
  uf: string;
  email: string;
  telefone: string;
}

export interface Funcional {
  cargo: string;
  situacao: SituacaoFuncional;
  unidade: string;
  dataIngresso: string;
  dataAposentadoria: string;
}

export interface ProcessoOrigem {
  /** "sim" = informou o número; "nao_sei" = não sabe, e o escritório
   *  procura; "nao" = declara não ter sentença. O terceiro caso faltava, e
   *  obrigar quem não tem título a dizer "não sei" produziria uma lista de
   *  busca cheia de gente que não tem nada a procurar. */
  temProcesso: Resposta;
  numero: string;
  /** Observação livre de quem não sabe o número — "a ação foi pelo
   *  sindicato em 2015", por exemplo. Ajuda o escritório a procurar. */
  observacao: string;
  /** Os processos que a pessoa quer ACOMPANHAR. Campo separado de `numero`
   *  porque são perguntas diferentes: `numero` é a sentença de origem, que
   *  decide o juízo da execução e por isso exige TRF1; estes são qualquer
   *  um dos 65 tribunais do DataJud, porque acompanhar não é protocolar. */
  acompanhar: string[];
}

export type TipoDocumento =
  | "procuracao"
  | "identidade"
  | "residencia"
  | "sentenca"
  | "transito"
  | "fichas";

/** Nome fixo com que cada tipo é guardado — DO CONTRATO. */
export const NOME_DE_ARQUIVO = CONTRATO.arquivos as Record<TipoDocumento, string>;

export interface DocumentoEnviado {
  tipo: TipoDocumento;
  nomeOriginal: string;
  /** Nome fixo com que o arquivo é guardado. Com 15 mil pastas,
   *  "Documento (1).pdf" é inútil. */
  nomeFinal: string;
  tamanho: number;
  sha256: string;
  /** Resultado da leitura do conteúdo. Ver `lib/leitura.ts`. */
  legivel: boolean;
  cpfEncontrado: boolean;
  motivoRecusa: string;
}

export interface Declaracoes {
  jaExecutou: Resposta;
  jaRecebeu: Resposta;
  outroAdvogado: Resposta;
  /** A quarta não é pergunta, é declaração: protege o escritório contra a
   *  exigência de demonstrar que o autor sabia da ação e quis entrar com
   *  ela (Recomendação CNJ 159/2024). */
  cienciaEIniciativa: boolean;
  /** O opt-in de aviso por e-mail. Não vem marcado: opt-in pré-marcado não
   *  é opt-in. É também o que sustenta o tratamento depois — cadastro
   *  colhido sem ele não dá para acompanhar sem reconvocar a pessoa. */
  querAviso: boolean;
}

export interface Rascunho {
  versao: 1;
  atualizadoEm: string;
  etapa: number;
  pessoais: DadosPessoais;
  funcional: Funcional;
  processo: ProcessoOrigem;
  documentos: DocumentoEnviado[];
  declaracoes: Declaracoes;
}

export const RASCUNHO_VAZIO: Rascunho = {
  versao: 1,
  atualizadoEm: "",
  etapa: 0,
  pessoais: {
    nome: "", cpf: "", matricula: "", rg: "", dataNascimento: "",
    cep: "", logradouro: "",
    numero: "", complemento: "", bairro: "", municipio: "", uf: "",
    email: "", telefone: "",
  },
  funcional: {
    cargo: "", situacao: "", unidade: "", dataIngresso: "",
    dataAposentadoria: "",
  },
  processo: { temProcesso: "", numero: "", observacao: "", acompanhar: [] },
  documentos: [],
  declaracoes: {
    jaExecutou: "", jaRecebeu: "", outroAdvogado: "",
    cienciaEIniciativa: false,
    querAviso: false,
  },
};

/** Quais nomes de arquivo o motor exige só de quem TEM processo. */
const SO_COM_PROCESSO = new Set(CONTRATO.se_tem_processo);

const _DOCUMENTOS_BASE: {
  tipo: TipoDocumento;
  rotulo: string;
  porque: string;
  obrigatorio: boolean;
  /** Derivado do contrato: `true` quando o motor só exige este arquivo de
   *  quem declarou ter processo. Não é regra do portal — é a regra do
   *  verificador de entrega, lida de lá. */
  soComProcesso?: boolean;
}[] = [
  {
    tipo: "procuracao",
    rotulo: "Procuração",
    porque: "é o que autoriza o advogado a agir por você",
    obrigatorio: true,
  },
  {
    tipo: "identidade",
    rotulo: "Documento de identidade",
    porque: "qualificação na petição",
    obrigatorio: true,
  },
  {
    tipo: "residencia",
    rotulo: "Comprovante de residência",
    porque: "endereço, e é item que os tribunais conferem em ações em massa",
    obrigatorio: true,
  },
  {
    tipo: "sentenca",
    soComProcesso: true,
    rotulo: "Sentença do seu processo",
    porque: "é o que vai ser executado",
    obrigatorio: true,
  },
  {
    tipo: "transito",
    soComProcesso: true,
    rotulo: "Certidão de trânsito em julgado",
    porque: "diz a partir de quando o prazo conta",
    obrigatorio: true,
  },
  {
    tipo: "fichas",
    rotulo: "Fichas financeiras ou contracheques",
    porque: "base para calcular o valor devido",
    obrigatorio: false,
  },
];


/**
 * A lista final, com `soComProcesso` **derivado do contrato** em vez de
 * escrito à mão. Se o contrato mudar de ideia sobre quais arquivos dependem
 * de ter processo, o portal acompanha sem ninguém lembrar de editar aqui.
 */
export const DOCUMENTOS = _DOCUMENTOS_BASE.map((d) => ({
  ...d,
  soComProcesso: SO_COM_PROCESSO.has(NOME_DE_ARQUIVO[d.tipo]),
}));
