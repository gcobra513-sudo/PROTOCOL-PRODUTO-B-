/**
 * Os acessos da demonstração: com que CPF fictício entrar, dito NA TELA.
 *
 * Só existem quando o SERVIDOR diz que é demonstração. O portal não os
 * inventa nem os mostra por conta própria.
 */
import { describe, expect, it } from "vitest";

import { acessosDaDemonstracao, roteiroDaDemonstracao } from "./demonstracao";

const acessos = [
  { quem: "Gestor do sindicato", cpf: "00000900184", area: "painel" },
  { quem: "Filiado com processo", cpf: "00000910490", area: "cadastro" },
];

describe("os acessos da demonstração", () => {
  it("vêm formatados e com o destino de cada um", () => {
    const r = acessosDaDemonstracao(
      { apelido: "demo-x", nome: "X", demonstracao: true, acessos_da_demonstracao: acessos },
    );
    expect(r).toEqual([
      { quem: "Gestor do sindicato", cpf: "000.009.001-84", area: "painel", gestor: true },
      { quem: "Filiado com processo", cpf: "000.009.104-90", area: "cadastro", gestor: false },
    ]);
  });

  it("não existem se o servidor não disse que é demonstração", () => {
    expect(acessosDaDemonstracao({ apelido: "s", nome: "S", acessos_da_demonstracao: acessos })).toEqual([]);
    expect(acessosDaDemonstracao(null)).toEqual([]);
  });

  it("deixam de fora o que não tem forma de CPF", () => {
    const r = acessosDaDemonstracao({
      apelido: "demo-x", nome: "X", demonstracao: true,
      acessos_da_demonstracao: [{ quem: "x", cpf: "123", area: "painel" }, ...acessos],
    });
    expect(r.map((a) => a.quem)).toEqual(["Gestor do sindicato", "Filiado com processo"]);
  });
});

/**
 * O ROTEIRO: a ordem em que se apresenta, e com que acesso entrar em cada
 * parada. Ele sai DOS ACESSOS que o servidor mandou — parada sem acesso não
 * existe, porque um botão que leva a um portão sem CPF para digitar é
 * exatamente o tropeço que o guia veio evitar.
 */
describe("o roteiro da demonstração", () => {
  const todos = acessosDaDemonstracao({
    apelido: "demo-x",
    nome: "X",
    demonstracao: true,
    acessos_da_demonstracao: [
      ...acessos,
      { quem: "Filiado que pediu aviso", cpf: "00000912190", area: "cadastro" },
      { quem: "Filiado que ainda não entrou", cpf: "00000913081", area: "cadastro" },
    ],
  });

  it("começa pelo painel do sindicato, com o CPF do gestor", () => {
    const r = roteiroDaDemonstracao(todos, "demo-x");
    expect(r.map((p) => p.id)).toEqual(["painel", "filiado", "primeiro-acesso"]);
    expect(r[0]).toMatchObject({ cpf: "000.009.001-84", link: "?entidade=demo-x&tela=painel" });
  });

  it("mostra o filiado pela Minha área, e o primeiro acesso pelo cadastro", () => {
    const r = roteiroDaDemonstracao(todos, "demo-x");
    expect(r[1]).toMatchObject({ cpf: "000.009.104-90", link: "?entidade=demo-x&tela=area" });
    expect(r[2]).toMatchObject({ cpf: "000.009.130-81", link: "?entidade=demo-x" });
  });

  it("cada parada diz o que mostrar e o que falar", () => {
    for (const p of roteiroDaDemonstracao(todos, "demo-x")) {
      expect(p.titulo).not.toBe("");
      expect(p.mostrar.length).toBeGreaterThan(0);
      expect(p.falar).not.toBe("");
    }
  });

  it("mostra onde ver quem já pode, no painel e na tela do filiado", () => {
    // A demonstração tem quem pode (uma ação declaradamente fictícia): o
    // roteiro tem de levar até lá, ou a melhor tela fica sem ser aberta.
    const r = roteiroDaDemonstracao(todos, "demo-x");
    expect(r[0]?.mostrar.join(" ")).toContain("já podem");
    expect(r[1]?.mostrar.join(" ")).toContain("“Caminho aberto, já conferido”");
    // E a conta: é o que o sindicato pergunta em seguida ("quanto?").
    expect(r[1]?.mostrar.join(" ")).toContain("apuração preliminar");
    expect(r[0]?.mostrar.join(" ")).toContain("ficha financeira");
  });

  it("com um escritório entre os acessos, ele entra depois do painel", () => {
    // A ordem da conversa: o sindicato encaminha, o escritório recebe, o
    // filiado vê. E o acesso do escritório não é tomado por filiado.
    const comEscritorio = acessosDaDemonstracao({
      apelido: "demo-x", nome: "X", demonstracao: true,
      acessos_da_demonstracao: [
        ...acessos,
        { quem: "Escritório contratado", cpf: "00000905100", area: "escritorio" },
      ],
    });
    const r = roteiroDaDemonstracao(comEscritorio, "demo-x");
    expect(r.map((p) => p.id)).toEqual(["painel", "escritorio", "filiado"]);
    expect(r[1]).toMatchObject({ cpf: "000.009.051-00", link: "?entidade=demo-x&tela=escritorio" });
    expect(r[2]?.cpf).toBe("000.009.104-90");
  });

  it("parada sem acesso não aparece", () => {
    const soGestor = todos.filter((a) => a.gestor);
    expect(roteiroDaDemonstracao(soGestor, "demo-x").map((p) => p.id)).toEqual(["painel"]);
    expect(roteiroDaDemonstracao([], "demo-x")).toEqual([]);
  });

  it("não usa o vocabulário do Produto A", () => {
    // O escritório contratado passou a fazer parte do produto (26/11/2026),
    // e o roteiro fala dele. O que continua de fora é o trabalho de DENTRO
    // do escritório, que é do outro produto.
    const texto = JSON.stringify(roteiroDaDemonstracao(todos, "demo-x")).toLowerCase();
    for (const palavra of ["lote", "peticionamento", "pje", "pré-voo", "manifesto", "quarentena", "disjuntor"]) {
      expect(texto).not.toContain(palavra);
    }
  });
});
