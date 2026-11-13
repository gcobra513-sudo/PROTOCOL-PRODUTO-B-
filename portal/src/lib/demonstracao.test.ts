/**
 * Os acessos da demonstração: com que CPF fictício entrar, dito NA TELA.
 *
 * Só existem quando o SERVIDOR diz que é demonstração. O portal não os
 * inventa nem os mostra por conta própria.
 */
import { describe, expect, it } from "vitest";

import { acessosDaDemonstracao } from "./demonstracao";

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
