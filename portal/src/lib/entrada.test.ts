/**
 * A página de entrada pergunta "de qual sindicato você é?" — e a pessoa
 * responde com o que tiver: o código que o sindicato passou, ou o link
 * inteiro que chegou no grupo. Os dois têm de dar no mesmo lugar.
 */
import { describe, expect, it } from "vitest";

import { codigoDoSindicato, enderecoDaArea } from "./entrada";

describe("o código do sindicato, do jeito que a pessoa colar", () => {
  it("aceita o código puro, com espaço e maiúscula", () => {
    expect(codigoDoSindicato("  Sind-DF ")).toBe("sind-df");
  });

  it("tira o código de dentro do link que o sindicato mandou", () => {
    expect(codigoDoSindicato("https://portal.exemplo.org/?entidade=sind-df&tela=acoes")).toBe("sind-df");
    expect(codigoDoSindicato("portal.exemplo.org/?entidade=Sind-DF")).toBe("sind-df");
  });

  it("não inventa código a partir de texto que não é um", () => {
    // O código vira parte de um endereço: o que não tem cara de código não
    // segue adiante, nem para o servidor.
    expect(codigoDoSindicato("")).toBe("");
    expect(codigoDoSindicato("meu sindicato")).toBe("");
    expect(codigoDoSindicato("../../etc")).toBe("");
    expect(codigoDoSindicato("https://portal.exemplo.org/")).toBe("");
  });
});

describe("o endereço de cada área", () => {
  it("o cadastro é o endereço sem `tela`", () => {
    expect(enderecoDaArea("cadastro", "sind-df")).toBe("?entidade=sind-df");
  });

  it("as outras áreas levam a tela", () => {
    expect(enderecoDaArea("painel", "sind-df")).toBe("?entidade=sind-df&tela=painel");
  });

  it("sem sindicato, volta para a página de entrada", () => {
    expect(enderecoDaArea("cadastro", "")).toBe("./");
  });
});
