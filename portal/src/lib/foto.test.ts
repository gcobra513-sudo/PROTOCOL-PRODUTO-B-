/**
 * A foto do celular vira PDF NO NAVEGADOR.
 *
 * POR QUE AQUI, e não no servidor: o contrato de arquivos é "PDF, com o
 * nome do tipo", e é ele que impede um nome vindo do cliente de virar
 * caminho. Aceitar JPG no servidor abriria esse contrato em seis lugares.
 * Embrulhar a foto num PDF aqui deixa o servidor recebendo o que sempre
 * recebeu — um PDF sem camada de texto, que ele aceita e marca como
 * aguardando leitura.
 *
 * E é literalmente o que a mensagem de erro antiga mandava o aposentado
 * fazer sozinho: "converta antes de enviar".
 *
 * O que se testa aqui é a MONTAGEM do PDF, que é pura. A conversão da
 * imagem (canvas) só existe em navegador, e é exercitada pelo ensaio de
 * navegador, que manda uma foto de verdade e abre o resultado com um leitor
 * de PDF do lado do servidor.
 */
import { describe, expect, it } from "vitest";

import { ehImagemAceita, pdfDeJpeg } from "./foto";

// Um "JPEG" de teste: começa e termina com os marcadores de verdade, e tem
// bytes altos no meio — o que quebraria uma montagem feita com texto.
const JPEG = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 16, 200, 255, 0, 128,
                             37, 80, 68, 70, 0xff, 0xd9]);
const latin = (b: Uint8Array) =>
  Array.from(b, (x) => String.fromCharCode(x)).join("");

describe("o PDF que embrulha a foto", () => {
  const pdf = pdfDeJpeg(JPEG, 1200, 1600);
  const texto = latin(pdf);

  it("é um PDF, do cabeçalho ao fim", () => {
    expect(texto.startsWith("%PDF-1.")).toBe(true);
    expect(texto.trimEnd().endsWith("%%EOF")).toBe(true);
  });

  it("leva a foto INTACTA, como imagem JPEG", () => {
    expect(texto).toContain("/DCTDecode");
    expect(texto).toContain("/Width 1200");
    expect(texto).toContain("/Height 1600");
    expect(texto).toContain(`/Length ${JPEG.length}`);
    // os bytes da foto, um por um, sem recodificação
    expect(texto).toContain(latin(JPEG));
  });

  it("a página tem a proporção da foto, e não a estica", () => {
    // 1200x1600 é retrato 3:4. Uma página A4 fixa deformaria o documento,
    // e documento deformado é documento mais difícil de ler por gente.
    const m = texto.match(/\/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]/);
    expect(m).not.toBeNull();
    const [largura, altura] = [Number(m![1]), Number(m![2])];
    expect(largura / altura).toBeCloseTo(1200 / 1600, 2);
  });

  it("a tabela de referências aponta para onde cada objeto ESTÁ", () => {
    // É o que separa um PDF que abre de um que "parece PDF". Um deslocamento
    // errado aqui e o leitor do servidor não abre — e o cadastro é recusado.
    const inicio = Number(texto.match(/startxref\n(\d+)/)![1]);
    expect(texto.slice(inicio, inicio + 4)).toBe("xref");
    const entradas = [...texto.slice(inicio).matchAll(/^(\d{10}) 00000 n /gm)];
    expect(entradas.length).toBe(5);
    entradas.forEach((e, i) => {
      const onde = Number(e[1]);
      expect(texto.slice(onde, onde + `${i + 1} 0 obj`.length)).toBe(
        `${i + 1} 0 obj`,
      );
    });
  });
});

describe("o que conta como foto", () => {
  it("JPEG e PNG, pelo tipo ou pela extensão", () => {
    expect(ehImagemAceita({ type: "image/jpeg", name: "x" })).toBe(true);
    expect(ehImagemAceita({ type: "image/png", name: "x" })).toBe(true);
    expect(ehImagemAceita({ type: "", name: "IMG_0042.JPG" })).toBe(true);
    expect(ehImagemAceita({ type: "", name: "foto.jpeg" })).toBe(true);
  });

  it("PDF não é foto, e arquivo qualquer também não", () => {
    expect(ehImagemAceita({ type: "application/pdf", name: "a.pdf" })).toBe(false);
    expect(ehImagemAceita({ type: "", name: "planilha.xlsx" })).toBe(false);
  });
});
