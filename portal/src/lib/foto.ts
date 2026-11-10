/**
 * A foto do celular vira PDF, NO NAVEGADOR.
 *
 * POR QUE EXISTE. O portal recusava toda imagem — e a base deste produto é
 * de aposentados com papel físico, para quem "o documento" é uma foto tirada
 * agora, com o celular. A mensagem antiga mandava a pessoa "converter antes
 * de enviar". Isto faz a conversão por ela.
 *
 * POR QUE AQUI, E NÃO NO SERVIDOR. O contrato de arquivos é "PDF, com o nome
 * do tipo", e é ele que impede um nome vindo do cliente de virar caminho no
 * disco. Aceitar JPG no servidor abriria esse contrato em meia dúzia de
 * lugares. Embrulhando a foto num PDF aqui, o servidor recebe o que sempre
 * recebeu: um PDF sem camada de texto, que ele aceita e marca como
 * AGUARDANDO LEITURA.
 *
 * E A FOTO NÃO SAI DO APARELHO PARA SER CONVERTIDA: é o próprio navegador
 * que desenha e monta. Nenhuma biblioteca, nenhum serviço.
 */

/** O maior lado da imagem, em pixels, depois de reduzida.
 *
 *  Foto de celular tem 12 megapixels e 5 MB; três delas estouram o pacote.
 *  2200 px no lado maior mantém legível uma página A4 fotografada (cerca de
 *  190 pontos por polegada) e deixa cada foto na casa de centenas de kB. */
const LADO_MAXIMO = 2200;
const QUALIDADE = 0.85;
/** O maior lado da PÁGINA, em pontos — o lado maior de uma A4. */
const PAGINA = 842;

export function ehImagemAceita(a: { type: string; name: string }): boolean {
  if (a.type === "image/jpeg" || a.type === "image/png") return true;
  // Sem tipo declarado (acontece em celular), vale a extensão.
  return a.type === "" && /\.(jpe?g|png)$/i.test(a.name);
}

const bytesDe = (texto: string): Uint8Array =>
  Uint8Array.from(texto, (c) => c.charCodeAt(0) & 0xff);

/** Um PDF de uma página com a foto ocupando a página inteira. PURA.
 *
 *  O JPEG entra INTACTO (`/DCTDecode`): PDF sabe guardar JPEG como está, e
 *  recodificar perderia qualidade de um documento que alguém vai ler.
 *
 *  A PÁGINA TEM A PROPORÇÃO DA FOTO. Uma A4 fixa esticaria o documento, e
 *  documento deformado é documento mais difícil de ler por gente.
 *
 *  OS DESLOCAMENTOS DA TABELA SÃO CONTADOS EM BYTES, não em caracteres: a
 *  foto é binária, e montar isto como texto erraria todos os deslocamentos
 *  depois dela — o arquivo "pareceria PDF" e não abriria no servidor.
 */
export function pdfDeJpeg(
  jpeg: Uint8Array,
  largura: number,
  altura: number,
): Uint8Array {
  const fator = PAGINA / Math.max(largura, altura);
  const w = (largura * fator).toFixed(2);
  const h = (altura * fator).toFixed(2);
  const desenho = `q ${w} 0 0 ${h} 0 0 cm /Im0 Do Q`;

  const objetos: Uint8Array[][] = [
    [bytesDe("<< /Type /Catalog /Pages 2 0 R >>")],
    [bytesDe("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")],
    [
      bytesDe(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] ` +
          "/Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>",
      ),
    ],
    [bytesDe(`<< /Length ${desenho.length} >>\nstream\n${desenho}\nendstream`)],
    [
      bytesDe(
        `<< /Type /XObject /Subtype /Image /Width ${largura} ` +
          `/Height ${altura} /ColorSpace /DeviceRGB /BitsPerComponent 8 ` +
          `/Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`,
      ),
      jpeg,
      bytesDe("\nendstream"),
    ],
  ];

  const cabecalho = bytesDe("%PDF-1.4\n");
  const partes: Uint8Array[] = [cabecalho];
  let posicao = cabecalho.length;
  const deslocamentos: number[] = [];
  objetos.forEach((pedacos, i) => {
    deslocamentos.push(posicao);
    for (const pedaco of [
      bytesDe(`${i + 1} 0 obj\n`),
      ...pedacos,
      bytesDe("\nendobj\n"),
    ]) {
      partes.push(pedaco);
      posicao += pedaco.length;
    }
  });

  const inicioDaTabela = posicao;
  partes.push(
    bytesDe(
      `xref\n0 ${objetos.length + 1}\n0000000000 65535 f \n` +
        deslocamentos
          .map((d) => `${String(d).padStart(10, "0")} 00000 n \n`)
          .join("") +
        `trailer\n<< /Size ${objetos.length + 1} /Root 1 0 R >>\n` +
        `startxref\n${inicioDaTabela}\n%%EOF\n`,
    ),
  );

  const saida = new Uint8Array(partes.reduce((n, p) => n + p.length, 0));
  let cursor = 0;
  for (const parte of partes) {
    saida.set(parte, cursor);
    cursor += parte.length;
  }
  return saida;
}

/** A foto, reduzida e embrulhada num PDF. SÓ EM NAVEGADOR: usa canvas.
 *
 *  Passa SEMPRE pelo canvas, mesmo quando o original já é JPEG, por três
 *  motivos: reduz a foto de 12 megapixels; aplica a orientação que a câmera
 *  gravou (sem isso, metade das fotos de celular sai deitada); e garante
 *  cores RGB, que é o que o PDF acima declara — JPEG em tons de cinza ou
 *  CMYK embrulhado como RGB abriria com as cores trocadas.
 *
 *  Fundo BRANCO antes de desenhar: PNG com transparência viraria fundo
 *  preto ao passar para JPEG, e texto preto sobre preto não se lê.
 */
export async function fotoParaPdf(arquivo: File): Promise<File> {
  const imagem = await createImageBitmap(arquivo, {
    imageOrientation: "from-image",
  });
  try {
    const fator = Math.min(
      1,
      LADO_MAXIMO / Math.max(imagem.width, imagem.height),
    );
    const largura = Math.max(1, Math.round(imagem.width * fator));
    const altura = Math.max(1, Math.round(imagem.height * fator));

    const tela = document.createElement("canvas");
    tela.width = largura;
    tela.height = altura;
    const contexto = tela.getContext("2d");
    if (!contexto) throw new Error("o navegador não deixou desenhar a imagem");
    contexto.fillStyle = "#ffffff";
    contexto.fillRect(0, 0, largura, altura);
    contexto.drawImage(imagem, 0, 0, largura, altura);

    const jpeg = await new Promise<Blob | null>((resolver) =>
      tela.toBlob(resolver, "image/jpeg", QUALIDADE),
    );
    if (!jpeg) throw new Error("o navegador não conseguiu converter a imagem");

    const pdf = pdfDeJpeg(
      new Uint8Array(await jpeg.arrayBuffer()),
      largura,
      altura,
    );
    const nome = arquivo.name.replace(/\.[^.]+$/, "") + ".pdf";
    return new File([pdf.buffer as ArrayBuffer], nome, {
      type: "application/pdf",
    });
  } finally {
    imagem.close();
  }
}
