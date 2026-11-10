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
import type {
  FilaDeLeitura,
  Gargalo,
  Mudancas,
  MudancaDeVeredicto,
  PessoaNaLista,
  PreviaDaPlanilha,
  ResultadoDoApagamento,
} from "./envio";

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

/** A frase de um grupo de mudança, no sentido certo.
 *
 *  OS DOIS SENTIDOS NA MESMA TELA, e confundi-los é o pior erro possível
 *  aqui: dizer "agora pode" a quem DEIXOU de poder faria o sindicato ligar
 *  para a pessoa com a notícia errada — e notícia errada sobre direito é o
 *  que destrói a confiança no produto inteiro.
 *
 *  `PODE` de um lado e qualquer outra coisa do outro basta para decidir o
 *  sentido: `FALTA` e `NAO_PODE` são os dois "não dá hoje", e a diferença
 *  entre eles não muda o que o gestor faz com a notícia.
 */
export function frasesDaMudanca(m: MudancaDeVeredicto): string {
  const quantos = pessoas(m.pessoas);
  const trilha = m.trilha === "executar" ? "executar" : "ajuizar";
  if (m.para === "PODE") {
    return `${quantos} passou a poder ${trilha} em ${m.referencia}.`;
  }
  if (m.de === "PODE") {
    return `${quantos} deixou de poder ${trilha} em ${m.referencia}.`;
  }
  return `${quantos} mudou de situação em ${m.referencia} ` +
    `(${m.de} para ${m.para}).`;
}

export interface ResumoDasMudancas {
  /** Ocupa espaço na tela? Nada mudou NÃO ocupa; não dar para saber ocupa. */
  mostra: boolean;
  frase: string;
  catalogo: string;
}

/** Se a seção de mudanças aparece, e com que manchete.
 *
 *  TRÊS ESTADOS, E O TERCEIRO É O QUE IMPORTA:
 *
 *    mudou alguma coisa   aparece, com a contagem
 *    nada mudou           NÃO aparece — seção vazia é ruído, e o painel
 *                         tem assunto melhor
 *    não dá para saber    APARECE, dizendo isso
 *
 *  O terceiro existe porque `total: 0` e "sem banco" produziriam a mesma
 *  tela se ninguém os separasse — e aí o painel tranquilizaria sem base.
 */
export function resumoDasMudancas(m: Mudancas): ResumoDasMudancas {
  if (m.sem_banco) {
    return {
      mostra: true,
      frase:
        "Não temos como saber o que mudou: este servidor está sem o banco " +
        "que guarda o veredicto anterior.",
      catalogo: m.catalogo,
    };
  }
  if (m.total <= 0) {
    return { mostra: false, frase: "", catalogo: m.catalogo };
  }
  return {
    mostra: true,
    frase:
      `${pessoas(m.total)} mudou de situação desde o catálogo anterior. ` +
      "Nada foi avisado a ninguém: quem fala com o filiado é o sindicato.",
    catalogo: m.catalogo,
  };
}

/** A fila de leitura humana, como o painel a diz.
 *
 *  Documento de foto ou de scanner ENTRA (decisão de 10/11/2026), e uma
 *  pessoa lê. Aceitar e não mostrar criaria uma fila invisível: o filiado
 *  acha que entregou, e o sindicato não sabe que há o que ler.
 *
 *  O QUE ESTA FRASE NÃO PODE FAZER é prometer o fluxo que ainda não existe.
 *  Hoje a fila tem entrada e contador, e NÃO tem saída: não há tela para
 *  registrar o que a pessoa leu. Então a frase diz o estado e a
 *  consequência — "a resposta fica incompleta" — e não diz "em análise".
 */
export function resumoDaFilaDeLeitura(f: FilaDeLeitura): {
  mostra: boolean;
  frase: string;
} {
  if (f.sem_banco) {
    return {
      mostra: true,
      frase:
        "Sem o banco, não dá para saber quantos documentos esperam leitura " +
        "por uma pessoa.",
    };
  }
  // O QUE NEM UMA PESSOA LEU. Sai da fila, e não pode sumir junto: é a
  // lista de a quem o sindicato tem de pedir o documento de novo.
  const semLeitura =
    f.ilegiveis > 0
      ? ` ${f.ilegiveis === 1 ? "1 documento" : `${f.ilegiveis} documentos`} ` +
        "não deu para ler nem por uma pessoa: é preciso pedir de novo a quem " +
        "mandou."
      : "";
  if (f.documentos <= 0) {
    return { mostra: f.ilegiveis > 0, frase: semLeitura.trim() };
  }
  const docs =
    f.documentos === 1
      ? "1 documento chegou"
      : `${f.documentos} documentos chegaram`;
  const espera = f.documentos === 1 ? "espera" : "esperam";
  return {
    mostra: true,
    frase:
      `${docs} como imagem (foto ou scanner), de ${pessoas(f.pessoas)}, e ` +
      `${espera} leitura por uma pessoa: a máquina não consegue ler. Até ` +
      "lá, a resposta sobre essas pessoas fica incompleta." +
      semLeitura,
  };
}

// ------------------------------------------------ o formulário de leitura

/** O que se pede ao gestor, por tipo de documento.
 *
 *  SÓ O QUE O MOTOR USA. Pedir que ele transcreva a sentença inteira é pedir
 *  um trabalho que ninguém faz e que ninguém usaria. Tipo que não
 *  conhecemos não ganha campo inventado: só se registra que foi lido.
 *
 *  A regra de verdade mora no servidor (`conferencia.validar`); isto existe
 *  para a tela não deixar o gestor descobrir a regra levando um erro. */
export function camposDaLeitura(tipo: string): string[] {
  if (tipo === "sentenca") return ["dispositivo", "numero_processo"];
  if (tipo === "certidao_transito") return ["transito_em_julgado"];
  if (tipo === "contribuicao") return ["periodo_inicio", "periodo_fim"];
  return [];
}

/** O que falta para poder registrar. Lista vazia = pode. Cada item é a
 *  frase que o gestor lê. */
export function faltaNaLeitura(
  tipo: string,
  valores: Record<string, string>,
): string[] {
  const v = (campo: string) => (valores[campo] ?? "").trim();
  if (tipo === "sentenca") {
    return v("dispositivo") ? [] : ["o que a sentença decidiu"];
  }
  if (tipo === "certidao_transito") {
    return v("transito_em_julgado") ? [] : ["a data do trânsito em julgado"];
  }
  if (tipo === "contribuicao") {
    if (!v("periodo_inicio") || !v("periodo_fim")) {
      return ["o período que o comprovante cobre"];
    }
    return v("periodo_fim") < v("periodo_inicio")
      ? ["o período termina antes de começar"]
      : [];
  }
  return [];
}

/** Os fatos que vão para o servidor: só os campos DO TIPO, e nunca vazio.
 *  Campo vazio mandado é pior que campo ausente — parece que alguém leu e
 *  não havia nada. */
export function fatosDaLeitura(
  tipo: string,
  valores: Record<string, string>,
): Record<string, string> {
  const saida: Record<string, string> = {};
  for (const campo of camposDaLeitura(tipo)) {
    const valor = (valores[campo] ?? "").trim();
    if (valor) saida[campo] = valor;
  }
  return saida;
}

const DISPOSITIVOS: Record<string, string> = {
  procedente: "Procedente",
  parcialmente_procedente: "Parcialmente procedente",
  improcedente: "Improcedente",
  extinto: "Extinto, sem decidir o pedido",
};

export function rotuloDoDispositivo(valor: string): string {
  return DISPOSITIVOS[valor] ?? valor;
}

// ----------------------------------------------------- nome por nome

const semAcento = (t: string) =>
  t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

/** O filtro da lista. `dono` é um dos três donos de pendência, ou `"PODE"`
 *  para quem já pode alguma coisa, ou vazio para todo mundo.
 *
 *  A BUSCA NÃO EXIGE ACENTO NEM MAIÚSCULA: o gestor digita "jose" e
 *  "joao", e exigir o acento seria fazer a busca falhar para quem escreve
 *  como todo mundo escreve.
 *
 *  Quem depende de dois donos aparece nos DOIS filtros. Escolher um só
 *  esconderia a pessoa de quem filtra por "o que depende de mim". */
export function filtrarPessoas(
  pessoas: PessoaNaLista[],
  filtro: { texto: string; dono: string },
): PessoaNaLista[] {
  const texto = semAcento(filtro.texto.trim());
  return pessoas.filter((p) => {
    if (texto && !semAcento(p.nome).includes(texto)) return false;
    if (filtro.dono === "PODE") return p.pode;
    if (filtro.dono) return p.depende_de.includes(filtro.dono);
    return true;
  });
}

/** As MESMAS palavras de `pendencia.ROTULO_CURTO` no servidor: a pendência
 *  com outro nome aqui faria o gestor achar que são coisas diferentes. */
const DEPENDE: Record<string, string> = {
  VOCE: "depende do filiado",
  CONFERENCIA: "depende do sindicato",
  TRIBUNAL: "depende do tribunal",
};

export function rotuloDoDono(dono: string): string {
  return DEPENDE[dono] ?? dono;
}

/** A situação de uma pessoa, numa linha. Quem não pode nada e não tem
 *  pendência não ganha estado inventado: nenhuma ação a alcança. */
export function situacaoDaPessoa(p: PessoaNaLista): string {
  const partes: string[] = [];
  if (p.pode) partes.push("já pode");
  for (const dono of p.depende_de) partes.push(rotuloDoDono(dono));
  return partes.length ? partes.join(" · ") : "sem ação que a alcance";
}

// ------------------------------------------------- a prévia da planilha

/** O que o gestor lê ANTES de confirmar a planilha.
 *
 *  A planilha é a base inteira do sindicato, e a confirmação é a única
 *  conferência que ela recebe. Então cada linha aqui é uma coisa que ele
 *  precisa saber para decidir — e o que não aconteceu NÃO vira linha:
 *  "0 pediram apagamento" em toda prévia é o ruído que ensina a não ler,
 *  justamente para o dia em que o número não for zero.
 */
export function resumoDaPlanilha(p: PreviaDaPlanilha): string[] {
  const linhas = [`${pessoas(p.pessoas)} no arquivo.`];
  if (p.inalcancaveis > 0) {
    linhas.push(
      `Você não consegue falar com ${p.inalcancaveis} ` +
        `(sem e-mail que sirva, ou CPF que não fecha) — ` +
        "elas entram na base, mas não conseguem usar o portal.",
    );
  }
  if (p.divergentes > 0) {
    linhas.push(
      `${p.divergentes === 1 ? "1 linha repete" : `${p.divergentes} linhas repetem`} ` +
        "uma pessoa com informação diferente (divergência): nada é escolhido " +
        "sozinho, e elas aparecem para você decidir.",
    );
  }
  if (p.colunas_ausentes.length) {
    linhas.push(`A planilha não trouxe: ${p.colunas_ausentes.join(", ")}.`);
  }
  if (p.apagados_a_pedido > 0) {
    linhas.push(
      `${pessoas(p.apagados_a_pedido)} desta planilha ` +
        `${p.apagados_a_pedido === 1 ? "pediu" : "pediram"} apagamento e NÃO ` +
        "será gravada. Tire do arquivo: enquanto estiver nele, todo envio vai " +
        "pular de novo.",
    );
  }
  return linhas;
}
