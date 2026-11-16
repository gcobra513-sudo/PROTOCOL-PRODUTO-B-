/**
 * TELA CLARA OU ESCURA, escolhida por quem usa.
 *
 * O portal já seguia o que o aparelho pede. Faltava a pessoa poder escolher
 * — quem enxerga mal com fundo escuro num celular que veio assim de fábrica
 * não sabe onde isso se muda no aparelho.
 */
import { describe, expect, it } from "vitest";

import { outroTema, temaEmUso, temaGuardado } from "./tema";

describe("o tema da tela", () => {
  it("sem escolha, segue o aparelho", () => {
    expect(temaEmUso(null, true)).toBe("escuro");
    expect(temaEmUso(null, false)).toBe("claro");
  });
  it("a escolha da pessoa vence o aparelho", () => {
    expect(temaEmUso("claro", true)).toBe("claro");
    expect(temaEmUso("escuro", false)).toBe("escuro");
  });
  it("o botão sempre leva ao outro", () => {
    expect(outroTema("claro")).toBe("escuro");
    expect(outroTema("escuro")).toBe("claro");
  });
  it("só aceita o que ele mesmo guardou", () => {
    const armazem = (v: string | null) => ({ getItem: () => v });
    expect(temaGuardado(armazem("escuro"))).toBe("escuro");
    expect(temaGuardado(armazem("claro"))).toBe("claro");
    expect(temaGuardado(armazem("javascript:alert(1)"))).toBeNull();
    expect(temaGuardado(armazem(null))).toBeNull();
    expect(temaGuardado({ getItem: () => { throw new Error("bloqueado"); } })).toBeNull();
  });
});
