/**
 * A página de entrada pergunta "de qual sindicato você é?" — e a pessoa
 * responde com o que tiver: o código que o sindicato passou, ou o link
 * inteiro que chegou no grupo. Os dois têm de dar no mesmo lugar.
 */
import { describe, expect, it } from "vitest";

import { codigoDoSindicato, enderecoDaArea, paginaDoLink } from "./entrada";

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

describe("as páginas públicas, pelo endereço", () => {
  it("reconhece as duas páginas de apresentação", () => {
    expect(paginaDoLink("?pagina=sindicato")).toBe("sindicato");
    expect(paginaDoLink("?pagina=Filiado")).toBe("filiado");
  });
  it("reconhece o guia da demonstração", () => {
    expect(paginaDoLink("?pagina=demonstracao")).toBe("demonstracao");
  });
  it("qualquer outra coisa é a página inicial", () => {
    expect(paginaDoLink("")).toBe("");
    expect(paginaDoLink("?pagina=admin")).toBe("");
    expect(paginaDoLink("?pagina=../../x")).toBe("");
  });
  it("dentro do portal de um sindicato não há página pública", () => {
    // Quem chegou pelo link do sindicato está no portal DELE: um `pagina=`
    // perdido no endereço não pode tirá-lo de lá.
    expect(paginaDoLink("?entidade=sind-df&pagina=sindicato")).toBe("");
  });
});
