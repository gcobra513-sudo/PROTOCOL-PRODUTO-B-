/**
 * Olha o documento NO NAVEGADOR, antes de mandar.
 *
 * Duas coisas, as duas com a camada de texto do PDF:
 *
 *   1. dá para a MÁQUINA ler? Se der, os fatos saem sozinhos — número do
 *      processo, trânsito em julgado — e a resposta vem mais rápido;
 *   2. o documento parece ser da pessoa certa? Procura-se o CPF no texto, o
 *      que pega quem sobe por engano o documento do cônjuge.
 *
 * Isso tem uma consequência boa de privacidade que vale dizer: **o documento
 * não sai do dispositivo da pessoa** para ser conferido. Nada é enviado
 * para lugar nenhum nesta etapa.
 *
 * O QUE MUDOU EM 10/11/2026, e por quê. Este módulo RECUSAVA foto de celular
 * e PDF só-imagem — "envie o PDF original ou escaneie com mais nitidez" — e
 * o cabeçalho dele justificava com a PROCURAÇÃO e o nome do ADVOGADO:
 * documentos do Produto A, que este produto nem pede. Para uma base de
 * aposentados com papel físico, scanner e foto são o caso COMUM.
 *
 * Agora o que a máquina não lê ENTRA, marcado como sem texto, e uma pessoa
 * lê depois. Só é recusado o que NINGUÉM consegue ler: arquivo que não abre.
 * OCR continua não existindo aqui, e continua sendo decisão, não omissão.
 */
import { soDigitos } from "./validacao";

export interface Leitura {
  /** Dá para ACEITAR? Só é falso para o que ninguém lê: não abre. */
  legivel: boolean;
  /** A MÁQUINA lê? Falso = scanner ou foto: entra, e uma pessoa lê. */
  temTexto: boolean;
  cpfEncontrado: boolean;
  motivoRecusa: string;
  caracteres: number;
  sha256: string;
}

/** Abaixo disto o PDF não tem texto de verdade — tem carimbo de scanner. */
const MINIMO_DE_CARACTERES = 120;

export async function sha256(arquivo: File): Promise<string> {
  const buffer = await arquivo.arrayBuffer();
  const resumo = await crypto.subtle.digest("SHA-256", buffer);
  return [...new Uint8Array(resumo)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function textoDoPdf(arquivo: File): Promise<string> {
  // Import dinâmico: são ~400 KB que só fazem sentido baixar quando a pessoa
  // chega na etapa de documentos.
  const pdfjs = await import("pdfjs-dist");
  const worker = await import("pdfjs-dist/build/pdf.worker.mjs?url");
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;

  const dados = new Uint8Array(await arquivo.arrayBuffer());
  const doc = await pdfjs.getDocument({ data: dados }).promise;
  const partes: string[] = [];
  // Dez páginas bastam para achar CPF e nome, e evita travar o navegador num
  // conjunto de fichas financeiras de duzentas páginas.
  const limite = Math.min(doc.numPages, 10);
  for (let i = 1; i <= limite; i += 1) {
    const pagina = await doc.getPage(i);
    const conteudo = await pagina.getTextContent();
    partes.push(
      conteudo.items
        .map((item) => ("str" in item ? item.str : ""))
        .join(" "),
    );
  }
  return partes.join("\n");
}

/** O que se conclui do TEXTO de um PDF que abriu. Pura, e por isso testada.
 *
 *  Sem texto NÃO É RECUSA: é um documento que a máquina não lê e uma pessoa
 *  lê. E, sem texto, nada se afirma sobre o CPF — não achamos porque não
 *  lemos, e dizer "seu CPF não aparece" de um documento que ninguém leu
 *  seria afirmar o que não dá para justificar. */
export function decidir(
  texto: string,
  cpf: string,
): Omit<Leitura, "sha256"> {
  const limpo = texto.replace(/\s+/g, " ").trim();
  if (limpo.length < MINIMO_DE_CARACTERES) {
    return {
      legivel: true,
      temTexto: false,
      cpfEncontrado: false,
      motivoRecusa: "",
      caracteres: limpo.length,
    };
  }
  // O CPF pode aparecer com pontuação, sem, ou com espaços no meio. Comparar
  // só os dígitos do texto inteiro resolve os três casos de uma vez.
  const cpfLimpo = soDigitos(cpf);
  return {
    legivel: true,
    temTexto: true,
    cpfEncontrado:
      cpfLimpo.length === 11 && soDigitos(limpo).includes(cpfLimpo),
    motivoRecusa: "",
    caracteres: limpo.length,
  };
}

export async function ler(arquivo: File, cpf: string): Promise<Leitura> {
  const resumo = await sha256(arquivo);
  const recusa = (motivoRecusa: string): Leitura => ({
    legivel: false,
    temTexto: false,
    cpfEncontrado: false,
    motivoRecusa,
    caracteres: 0,
    sha256: resumo,
  });

  const ehPdf =
    arquivo.type === "application/pdf" ||
    arquivo.name.toLowerCase().endsWith(".pdf");
  if (!ehPdf) {
    // Foto (JPG, PNG) não chega aqui: `Documentos` a embrulha num PDF antes,
    // com `fotoParaPdf`. O que chega aqui sem ser PDF é outro tipo de
    // arquivo — planilha, texto —, e esse não é documento que se anexe.
    return recusa(
      "este arquivo não é um PDF nem uma foto. Envie o documento em PDF, " +
        "ou uma foto dele (JPG ou PNG).",
    );
  }

  let texto = "";
  try {
    texto = await textoDoPdf(arquivo);
  } catch (erro) {
    // ESTE NINGUÉM LÊ, nem gente: é a única recusa que sobrou.
    return recusa(
      "não conseguimos abrir este PDF. Ele pode estar corrompido ou " +
        "protegido por senha. Tente enviar o arquivo original, sem senha. " +
        `(detalhe: ${erro instanceof Error ? erro.message : "erro ao ler"})`,
    );
  }
  return { ...decidir(texto, cpf), sha256: resumo };
}
