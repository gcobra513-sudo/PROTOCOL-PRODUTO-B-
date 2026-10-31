/**
 * O painel do sindicato: o que ele diz e o que ele se recusa a dizer.
 *
 * O teste que importa é o do ACIONÁVEL. O maior gargalo da base pode ser um
 * tema afetado no STJ — e nenhuma decisão de diretoria o destrava. Apontar
 * esse como "o que resolver primeiro" manda o sindicato trabalhar no que não
 * depende dele.
 */
import { describe, expect, it } from "vitest";

import type { Gargalo } from "./envio";
import { fracao, pessoas, presosNoTribunal, primeiroAcionavel } from "./painel";

function g(quem: string, o_que: string, n: number): Gargalo {
  return { quem, titulo: "", explicacao: "", o_que, pessoas: n, exemplos: [] };
}

describe("o que o sindicato resolve primeiro", () => {
  it("escolhe o maior que depende do sindicato, não o maior da lista", () => {
    const lista = [
      g("TRIBUNAL", "o julgamento do STJ, Tema 1.302", 4000),
      g("CONFERENCIA", "a homologação da GIFA por advogado", 1204),
      g("VOCE", "os comprovantes de contribuição", 900),
      g("CONFERENCIA", "o rol de substituídos", 300),
    ];
    const alvo = primeiroAcionavel(lista);
    expect(alvo?.o_que).toContain("homologação");
    expect(alvo?.pessoas).toBe(1204);
  });

  it("devolve nulo quando nada depende do sindicato", () => {
    expect(primeiroAcionavel([g("TRIBUNAL", "o julgamento", 10)])).toBeNull();
    expect(primeiroAcionavel([])).toBeNull();
  });

  it("conta quem está parado no tribunal", () => {
    expect(
      presosNoTribunal([
        g("CONFERENCIA", "homologar", 5),
        g("TRIBUNAL", "o julgamento do Tema 1.302", 4000),
        g("TRIBUNAL", "o julgamento do Tema 1.410", 12),
      ]),
    ).toBe(4000);
    expect(presosNoTribunal([g("VOCE", "comprovantes", 3)])).toBe(0);
    expect(presosNoTribunal([])).toBe(0);
  });
});

describe("os números como o diretor lê", () => {
  it("plural certo", () => {
    expect(pessoas(1)).toBe("1 pessoa");
    expect(pessoas(0)).toBe("0 pessoas");
    expect(pessoas(12)).toBe("12 pessoas");
  });

  it("fração sempre com denominador", () => {
    // "3 participam" não diz nada: 3 de 4 e 3 de 4.000 são opostos.
    expect(fracao(3, 10)).toBe("3 de 10 (30%)");
    expect(fracao(0, 4812)).toBe("0 de 4812 (0%)");
  });

  it("sem base não inventa percentual", () => {
    expect(fracao(0, 0)).toBe("—");
  });
});
