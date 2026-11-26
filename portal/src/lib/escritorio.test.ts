/**
 * O encaminhamento ao escritório, dito a cada um dos três que o leem.
 *
 * A mesma situação tem três leitores, e cada um precisa de uma frase: o
 * filiado quer saber com quem está e o que ele faz; o escritório, o que
 * chegou; o sindicato, onde está parado.
 */
import { describe, expect, it } from "vitest";

import {
  csvDosCasos,
  diasNaFila,
  filtrarCasos,
  fraseParaOFiliado,
  ordemDeTrabalho,
  resumoDoEscritorio,
  rotuloDaSituacao,
} from "./escritorio";

const enc = {
  acao: "X", rotulo: "Gratificação de Exemplo (ação FICTÍCIA)",
  escritorio: "Escritório de Exemplo A (fictício)", contato: "contato@exemplo-a.invalid",
  situacao: "ENCAMINHADO", faltam: [] as string[], encaminhado_em: "2026-11-20T10:00:00+00:00",
};

describe("o que o filiado lê sobre o caso dele", () => {
  it("encaminhado: com quem está, e que ele não precisa fazer nada", () => {
    expect(fraseParaOFiliado(enc)).toBe(
      "O sindicato encaminhou o seu caso a este escritório em 20/11/2026. Ele ainda não confirmou o recebimento. Você não precisa fazer nada agora.",
    );
  });
  it("falta documento: diz QUAIS, porque é a única coisa que depende dele", () => {
    expect(fraseParaOFiliado({ ...enc, situacao: "PENDENTE", faltam: ["procuração", "documento de identidade"] })).toBe(
      "O escritório recebeu o seu caso e precisa de: procuração e documento de identidade. Envie pelo seu cadastro, aqui no portal.",
    );
  });
  it("recebido e completo: resposta inteira, sem mandar ligar", () => {
    expect(fraseParaOFiliado({ ...enc, situacao: "RECEBIDO" })).toContain("está conferindo");
    expect(fraseParaOFiliado({ ...enc, situacao: "COMPLETO" })).toContain("Não falta nada da sua parte");
  });
  it("situação que a tela não conhece não vira frase inventada", () => {
    expect(fraseParaOFiliado({ ...enc, situacao: "OUTRA" })).toBe("");
  });
});

describe("os rótulos da situação", () => {
  it("são palavras de gente", () => {
    expect(rotuloDaSituacao("ENCAMINHADO")).toBe("Aguardando o escritório");
    expect(rotuloDaSituacao("RECEBIDO")).toBe("Recebido");
    expect(rotuloDaSituacao("PENDENTE")).toBe("Falta documento");
    expect(rotuloDaSituacao("COMPLETO")).toBe("Documentação completa");
    expect(rotuloDaSituacao("X")).toBe("");
  });
});

describe("a fila do escritório", () => {
  it("o que ainda não foi aberto vem primeiro, e o completo por último", () => {
    const casos = ["COMPLETO", "PENDENTE", "ENCAMINHADO", "RECEBIDO"].map((situacao, i) => ({
      situacao, encaminhado_em: `2026-11-0${i + 1}T00:00:00+00:00`,
    }));
    expect(ordemDeTrabalho(casos).map((c) => c.situacao)).toEqual([
      "ENCAMINHADO", "RECEBIDO", "PENDENTE", "COMPLETO",
    ]);
  });
  it("dentro da mesma situação, o mais antigo primeiro", () => {
    const casos = [
      { situacao: "ENCAMINHADO", encaminhado_em: "2026-11-09T00:00:00+00:00" },
      { situacao: "ENCAMINHADO", encaminhado_em: "2026-11-02T00:00:00+00:00" },
    ];
    expect(ordemDeTrabalho(casos).map((c) => c.encaminhado_em.slice(8, 10))).toEqual(["02", "09"]);
  });
});

describe("o que o sindicato lê de cada escritório", () => {
  const e = {
    id: "a", nome: "A", contato: "", acoes: [], casos: 10,
    encaminhados: 4, recebidos: 3, pendentes: 2, completos: 1, parados: 2,
  };
  it("os parados vêm na frente: é onde o filiado está ligando", () => {
    expect(resumoDoEscritorio(e)).toEqual([
      "2 casos encaminhados há mais de 7 dias que o escritório ainda não recebeu.",
      "10 casos ao todo: 4 aguardando o escritório, 3 recebidos, 2 com documento faltando, 1 com a documentação completa.",
    ]);
  });
  it("sem caso nenhum, diz isso em vez de uma fila de zeros", () => {
    expect(resumoDoEscritorio({ ...e, casos: 0, encaminhados: 0, recebidos: 0, pendentes: 0, completos: 0, parados: 0 }))
      .toEqual(["Nenhum caso encaminhado ainda."]);
  });
});

describe("o painel do escritório", () => {
  const caso = (nome: string, situacao: string, extra = {}) => ({
    cpf: "00000910066", nome, email: "a@exemplo.invalid", telefone: "",
    documentos: [{ arquivo: "sentenca.pdf", rotulo: "sentença" }],
    acao: "X", rotulo: "Ação de Exemplo", situacao, faltam: [] as string[],
    encaminhado_em: "2026-11-20T10:00:00+00:00", atualizado_em: "2026-11-20T10:00:00+00:00",
    ...extra,
  });
  const casos = [
    caso("MARIA DE EXEMPLO (FICTÍCIA)", "PENDENTE", { faltam: ["procuracao"] }),
    caso("JOSÉ DE EXEMPLO (FICTÍCIO)", "ENCAMINHADO"),
    caso("HELENA DE EXEMPLO (FICTÍCIA)", "COMPLETO"),
  ];

  it("filtra pela situação e pelo nome, sem ligar para acento nem maiúscula", () => {
    expect(filtrarCasos(casos, { texto: "", situacao: "PENDENTE" }).map((c) => c.nome)).toEqual(["MARIA DE EXEMPLO (FICTÍCIA)"]);
    expect(filtrarCasos(casos, { texto: "jose", situacao: "" }).map((c) => c.nome)).toEqual(["JOSÉ DE EXEMPLO (FICTÍCIO)"]);
    expect(filtrarCasos(casos, { texto: "helena", situacao: "PENDENTE" })).toEqual([]);
    expect(filtrarCasos(casos, { texto: "  ", situacao: "" })).toHaveLength(3);
  });

  it("acha também pelo CPF, com ou sem pontuação", () => {
    expect(filtrarCasos(casos, { texto: "000.009.100-66", situacao: "" })).toHaveLength(3);
    expect(filtrarCasos(casos, { texto: "99999", situacao: "" })).toEqual([]);
  });

  it("diz há quantos dias o caso está na fila", () => {
    expect(diasNaFila("2026-11-20T10:00:00+00:00", new Date("2026-11-26T12:00:00Z"))).toBe(6);
    expect(diasNaFila("2026-11-26T10:00:00+00:00", new Date("2026-11-26T12:00:00Z"))).toBe(0);
    // Data que não se lê não vira número: "há NaN dias" na tela é pior que nada.
    expect(diasNaFila("", new Date())).toBe(null);
  });

  it("a planilha dos casos abre no Excel e não executa fórmula", () => {
    const csv = csvDosCasos([
      ...casos,
      caso("=CMD() DE EXEMPLO", "RECEBIDO"),
    ], [{ tipo: "procuracao", rotulo: "procuração" }]);
    const linhas = csv.split("\r\n");
    expect(linhas[0]).toBe("\uFEFFNome;CPF;E-mail;Telefone;Ação;Situação;Falta;Documentos enviados;Encaminhado em");
    expect(linhas[1]).toBe("MARIA DE EXEMPLO (FICTÍCIA);000.009.100-66;a@exemplo.invalid;;Ação de Exemplo;Falta documento;procuração;sentença;20/11/2026");
    // Célula que começa com = + - @ viraria fórmula no Excel de quem abre.
    expect(linhas[4]?.startsWith("'=CMD()")).toBe(true);
  });
});
