/**
 * As teses acompanhadas, ditas a quem vai propor a ação.
 *
 * O servidor manda a situação em código e o alcance em três contagens. Aqui
 * isso vira palavra — e o cuidado é um só: o número é uma SIMULAÇÃO, e a
 * frase tem de dizer "poderiam", nunca "podem".
 */
import { describe, expect, it } from "vitest";

import { alcanceEmPalavras, haQuanto, rotuloDaSituacaoDaTese, saudacao, tesesJuntas } from "./teses";

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

describe("as teses de vários sindicatos, juntas numa lista só", () => {
  const de = (id: string, extra = {}) => ({ ...tese, id, ...extra });
  const sindicatos = [
    { entidade: "a", nome: "Sindicato A", teses: [de("T1", { poderiam: 5, dependem: 37, fora: 0 }), de("ACAO", { tipo: "acao", data: "", situacao: "transitado_em_julgado", conferida: true, poderiam: 4, dependem: 1, fora: 2 })] },
    { entidade: "b", nome: "Sindicato B", teses: [de("T1", { poderiam: 0, dependem: 8, fora: 0 }), de("T2", { situacao: "afetado", data: "2026-11-15", poderiam: 0, dependem: 8, fora: 0 })] },
  ];

  it("a mesma tese em dois sindicatos vira UMA linha, com a soma e a divisão", () => {
    const t1 = tesesJuntas(sindicatos).find((t) => t.id === "T1")!;
    expect([t1.poderiam, t1.dependem]).toEqual([5, 45]);
    expect(t1.porSindicato).toEqual([
      { entidade: "a", nome: "Sindicato A", poderiam: 5, dependem: 37, fora: 0 },
      { entidade: "b", nome: "Sindicato B", poderiam: 0, dependem: 8, fora: 0 },
    ]);
  });

  it("o que tem data mais recente vem primeiro; o que não tem data, por último", () => {
    expect(tesesJuntas(sindicatos).map((t) => t.id)).toEqual(["T1", "T2", "ACAO"]);
  });

  it("sem sindicato nenhum, lista vazia", () => {
    expect(tesesJuntas([])).toEqual([]);
    expect(tesesJuntas([{ entidade: "a", nome: "A" }])).toEqual([]);
  });
});

describe("há quanto tempo", () => {
  const hoje = new Date(2026, 10, 27, 10);
  it("em palavras curtas", () => {
    expect(haQuanto("2026-11-27", hoje)).toBe("hoje");
    expect(haQuanto("2026-11-26", hoje)).toBe("ontem");
    expect(haQuanto("2026-11-15", hoje)).toBe("há 12 dias");
  });
  it("data que não se lê, ou no futuro, não vira palavra", () => {
    expect(haQuanto("", hoje)).toBe("");
    expect(haQuanto("2027-01-01", hoje)).toBe("");
  });
});
