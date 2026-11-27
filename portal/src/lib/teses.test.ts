/**
 * As teses acompanhadas, ditas a quem vai propor a ação.
 *
 * O servidor manda a situação em código e o alcance em três contagens. Aqui
 * isso vira palavra — e o cuidado é um só: o número é uma SIMULAÇÃO, e a
 * frase tem de dizer "poderiam", nunca "podem".
 */
import { describe, expect, it } from "vitest";

import { alcanceEmPalavras, rotuloDaSituacaoDaTese, saudacao } from "./teses";

const tese = {
  id: "T", tipo: "tema", rotulo: "STJ, Tema 9.001", tribunal: "STJ", situacao: "julgado",
  data: "2026-11-20", questao: "", tese: "", fonte: "", conferida: false,
  poderiam: 12, dependem: 30, fora: 3,
};

describe("a saudação do painel", () => {
  it("muda com a hora de quem lê", () => {
    expect(saudacao(new Date(2026, 10, 27, 8))).toBe("Bom dia");
    expect(saudacao(new Date(2026, 10, 27, 14))).toBe("Boa tarde");
    expect(saudacao(new Date(2026, 10, 27, 20))).toBe("Boa noite");
    expect(saudacao(new Date(2026, 10, 27, 3))).toBe("Boa noite");
  });
});

describe("a situação de uma tese", () => {
  it("em palavras de quem acompanha tribunal", () => {
    expect(rotuloDaSituacaoDaTese(tese)).toBe("Julgado");
    expect(rotuloDaSituacaoDaTese({ ...tese, situacao: "afetado" })).toBe("Vai ser julgado");
    expect(rotuloDaSituacaoDaTese({ ...tese, situacao: "a_conferir" })).toBe("Situação a conferir");
    expect(rotuloDaSituacaoDaTese({ ...tese, tipo: "acao", situacao: "transitado_em_julgado" })).toBe("Ação com trânsito em julgado");
  });
  it("código que a tela não conhece não vira rótulo inventado", () => {
    expect(rotuloDaSituacaoDaTese({ ...tese, situacao: "xyz" })).toBe("");
  });
});

describe("o alcance de uma tese na base", () => {
  it("não conferida: é simulação, e a frase diz 'poderiam'", () => {
    expect(alcanceEmPalavras(tese)).toBe(
      "Se for conferida por advogado: 12 pessoas poderiam, 30 dependem de alguma conferência e 3 ficam de fora.",
    );
  });
  it("conferida: já vale, e a frase diz 'podem'", () => {
    expect(alcanceEmPalavras({ ...tese, conferida: true })).toBe(
      "Conferida por advogado: 12 pessoas podem, 30 dependem de alguma conferência e 3 ficam de fora.",
    );
  });
  it("tema que ainda vai ser julgado não promete nada", () => {
    expect(alcanceEmPalavras({ ...tese, situacao: "afetado", poderiam: 0, dependem: 45, fora: 0 })).toBe(
      "Ainda não há tese. 45 pessoas são da carreira que o tema alcança.",
    );
  });
  it("base vazia é dita, não contada em zeros", () => {
    expect(alcanceEmPalavras({ ...tese, poderiam: 0, dependem: 0, fora: 0 })).toBe(
      "Ninguém da base é alcançado por enquanto.",
    );
  });
});
