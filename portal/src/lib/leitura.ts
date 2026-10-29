/**
 * Lê o conteúdo dos documentos enviados, NO NAVEGADOR.
 *
 * A especificação exige duas coisas no envio:
 *
 *   1. o arquivo precisa ser legível por computador — se a pessoa fotografar
 *      a procuração, o arquivo é só uma imagem e ninguém consegue LER o nome
 *      do advogado nela;
 *   2. o documento tem de ser da pessoa certa — procura-se o CPF dentro do
 *      texto, o que pega quem sobe por engano o documento do cônjuge.
 *
 * As duas são feitas aqui, no navegador, com a camada de texto do PDF. Isso
 * tem uma consequência boa de privacidade que vale dizer: **o documento não
 * sai do dispositivo da pessoa** para ser conferido. Nada é enviado para
 * lugar nenhum nesta etapa.
 *
 * O QUE NÃO FAZ, e é honesto declarar: OCR de imagem. Foto de celular e PDF
 * só-imagem são RECUSADOS com a mensagem da especificação — "envie o PDF
 * original ou escaneie com mais nitidez". Recusar na hora incomoda;
 * descobrir no fim é pior, porque não há mais tempo de pedir de novo.
 * Reconhecer texto em foto exigiria OCR (servidor ou ~10 MB de modelo no
 * navegador) e fica como decisão, não como omissão.
 */
import { soDigitos } from "./validacao";

export interface Leitura {
  legivel: boolean;
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

export async function ler(arquivo: File, cpf: string): Promise<Leitura> {
  const resumo = await sha256(arquivo);
  const base: Leitura = {
    legivel: false,
    cpfEncontrado: false,
    motivoRecusa: "",
    caracteres: 0,
    sha256: resumo,
  };

  const ehPdf =
    arquivo.type === "application/pdf" ||
    arquivo.name.toLowerCase().endsWith(".pdf");

  if (!ehPdf) {
    return {
      ...base,
      motivoRecusa:
        "este arquivo é uma imagem, e não conseguimos ler o texto dela. " +
        "Envie o PDF original, ou escaneie o documento em PDF.",
    };
  }

  let texto = "";
  try {
    texto = await textoDoPdf(arquivo);
  } catch (erro) {
    return {
      ...base,
      motivoRecusa:
        "não conseguimos abrir este PDF. Ele pode estar corrompido ou " +
        "protegido por senha. Tente enviar o arquivo original. " +
        `(detalhe: ${erro instanceof Error ? erro.message : "erro ao ler"})`,
    };
  }

  const limpo = texto.replace(/\s+/g, " ").trim();
  if (limpo.length < MINIMO_DE_CARACTERES) {
    return {
      ...base,
      caracteres: limpo.length,
      motivoRecusa:
        "não conseguimos ler este documento — ele parece ser só uma imagem " +
        "dentro de um PDF. Envie o PDF original, ou escaneie com mais " +
        "nitidez usando a opção de reconhecer texto.",
    };
  }

  // O CPF pode aparecer com pontuação, sem, ou com espaços no meio. Comparar
  // só os dígitos do texto inteiro resolve os três casos de uma vez.
  const digitosDoTexto = soDigitos(limpo);
  const cpfLimpo = soDigitos(cpf);
  const achou = cpfLimpo.length === 11 && digitosDoTexto.includes(cpfLimpo);

  return {
    legivel: true,
    cpfEncontrado: achou,
    motivoRecusa: "",
    caracteres: limpo.length,
    sha256: resumo,
  };
}
