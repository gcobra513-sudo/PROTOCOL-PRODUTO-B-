/**
 * O que o navegador decide sobre um documento, ANTES de mandar.
 *
 * A REGRA MUDOU EM 10/11/2026. O navegador recusava PDF sem camada de texto
 * e toda imagem, com a mensagem "envie o PDF original ou escaneie com mais
 * nitidez" — para uma base de aposentados com papel físico. O cabeçalho do
 * módulo justificava com a PROCURAÇÃO e o nome do ADVOGADO: documentos do
 * Produto A, que este produto nem pede.
 *
 * Agora: o que a máquina não lê ENTRA, marcado, e uma pessoa lê.
 */
import { describe, expect, it } from "vitest";

import { decidir } from "./leitura";

const LONGO =
  "DECLARACAO DE CONTRIBUICAO SINDICAL. Declaramos que a pessoa filiada " +
  "contribuiu regularmente com a mensalidade no periodo de 03/2004 a " +
  "12/2018. CPF 111.444.777-35. Documento de exemplo.";

describe("a decisão sobre um documento", () => {
  it("PDF sem texto ENTRA, marcado como sem texto — não é recusa", () => {
    const d = decidir("", "111.444.777-35");
    expect(d.legivel).toBe(true);
    expect(d.temTexto).toBe(false);
    expect(d.motivoRecusa).toBe("");
  });

  it("carimbo de scanner (poucos caracteres) também conta como sem texto", () => {
    const d = decidir("Digitalizado com CamScanner", "111.444.777-35");
    expect(d.legivel).toBe(true);
    expect(d.temTexto).toBe(false);
  });

  it("PDF com texto continua sendo lido, e o CPF procurado", () => {
    const d = decidir(LONGO, "111.444.777-35");
    expect(d.temTexto).toBe(true);
    expect(d.cpfEncontrado).toBe(true);
  });

  it("sem texto, NÃO afirma nada sobre o CPF", () => {
    // Não achamos porque não lemos. Dizer "seu CPF não aparece" de um
    // documento que ninguém leu seria afirmar o que não dá para justificar.
    expect(decidir("", "111.444.777-35").cpfEncontrado).toBe(false);
  });

  it("CPF de outra pessoa no texto não vira o da pessoa", () => {
    expect(decidir(LONGO, "529.982.247-25").cpfEncontrado).toBe(false);
  });
});
