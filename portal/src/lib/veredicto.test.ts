/**
 * Os rótulos que a pessoa lê.
 *
 * A tabela é FECHADA de propósito: um estado novo no Python sem rótulo aqui
 * apareceria como `undefined` na tela, ou — pior — como `NAO_PARTICIPA` em
 * caixa alta no meio de uma frase.
 *
 * E os dois testes que não são sobre cobertura: nenhum rótulo promete
 * dinheiro, e nenhum menciona escritório. Os dois são regra do produto, não
 * estilo — prometer valor cria expectativa em gente aposentada, e quem fala
 * com o filiado é o sindicato.
 */
import { describe, expect, it } from "vitest";

import {
  ESTADOS,
  comoFrase,
  TRILHAS,
  VEREDICTOS,
  explicacaoDaTrilha,
  periodo,
  resumo,
  rotuloDaTrilha,
  rotuloDoEstado,
  rotuloDoVeredicto,
  semPrefixo,
  tomDoEstado,
  tomDoVeredicto,
} from "./veredicto";
import { TELAS, telaDoLink } from "./envio";

const TODOS = [
  ...ESTADOS.map((e) => rotuloDoEstado(e)),
  ...VEREDICTOS.map((v) => rotuloDoVeredicto(v)),
  ...TRILHAS.map((t) => rotuloDaTrilha(t)),
  ...TRILHAS.map((t) => explicacaoDaTrilha(t)),
];

describe("a tabela é fechada", () => {
  it("todo estado do Python tem rótulo em português e tom", () => {
    for (const e of ESTADOS) {
      expect(rotuloDoEstado(e), e).not.toBe(e);
      expect(rotuloDoEstado(e).length, e).toBeGreaterThan(4);
      expect(["bom", "neutro", "alerta"]).toContain(tomDoEstado(e));
    }
  });

  it("todo veredicto do Python tem rótulo e tom", () => {
    for (const v of VEREDICTOS) {
      expect(rotuloDoVeredicto(v), v).not.toBe(v);
      expect(["bom", "neutro", "alerta"]).toContain(tomDoVeredicto(v));
    }
  });

  it("toda trilha tem rótulo e explicação", () => {
    for (const t of TRILHAS) {
      expect(rotuloDaTrilha(t), t).not.toBe(t);
      expect(explicacaoDaTrilha(t).length, t).toBeGreaterThan(40);
    }
  });

  it("valor desconhecido devolve o próprio valor, não undefined", () => {
    // Fail-visible: um estado novo aparece cru na tela, e cru é feio o
    // suficiente para alguém consertar. `undefined` ninguém vê.
    expect(rotuloDoEstado("SEI_LA")).toBe("SEI_LA");
    expect(rotuloDoVeredicto("SEI_LA")).toBe("SEI_LA");
  });
});

describe("o que os rótulos não dizem", () => {
  it("nenhum promete dinheiro", () => {
    for (const texto of TODOS) {
      for (const proibido of [
        "vai receber",
        "tem direito a",
        "valor",
        "indeniza",
        "receberá",
        "garantido",
      ]) {
        expect(texto.toLowerCase(), texto).not.toContain(proibido);
      }
    }
  });

  it("nenhum menciona escritório", () => {
    // REGRA ZERO: quem fala com o filiado é o sindicato.
    for (const texto of TODOS) {
      expect(texto.toLowerCase(), texto).not.toContain("escritóri");
      expect(texto.toLowerCase(), texto).not.toContain("escritori");
    }
  });

  it("INDETERMINADO não soa como 'não'", () => {
    // "Ainda" é a palavra que separa lacuna de resposta. Sem ela, FALTA
    // vira recusa aos olhos de quem lê.
    expect(rotuloDoEstado("INDETERMINADO").toLowerCase()).toContain("ainda");
  });
});

describe("o período", () => {
  it("mostra a interseção e os meses", () => {
    expect(periodo("2004-01", "2008-12", 60)).toBe(
      "de 2004-01 a 2008-12 (60 meses)",
    );
  });

  it("um mês no singular", () => {
    expect(periodo("2008-12", "2008-12", 1)).toContain("(1 mês)");
  });

  it("sem interseção não inventa período", () => {
    expect(periodo("", "", 0)).toBe("");
    expect(periodo("2004-01", "", 0)).toBe("");
  });
});

describe("o resumo de uma linha", () => {
  it("sem ação nenhuma, não diz 'nada encontrado'", () => {
    // "Nada encontrado" soa a veredicto. O fato é que não havia o que cruzar.
    const r = resumo([], 0);
    expect(r.toLowerCase()).not.toContain("nada encontrado");
    expect(r).toContain("ação a cruzar");
  });

  it("conta quem participa e quem está em aberto", () => {
    const r = resumo(
      [
        { estado: "PARTICIPA" },
        { estado: "INDETERMINADO" },
        { estado: "INDETERMINADO" },
        { estado: "NAO_PARTICIPA" },
      ],
      2,
    );
    expect(r).toContain("faz parte de 1 ação");
    expect(r).toContain("2 ainda dependem de conferência");
    expect(r).toContain("2 itens que dependem de você");
  });

  it("quando nada alcança a pessoa, diz isso sem rodeio", () => {
    const r = resumo([{ estado: "NAO_PARTICIPA" }], 0);
    expect(r).toContain("não alcança você");
  });

  it("um item pendente fica no singular", () => {
    expect(resumo([{ estado: "PARTICIPA" }], 1)).toContain(
      "1 item que depende de você",
    );
  });
});

describe("as áreas do portal", () => {
  it("o link escolhe a área, e desconhecido cai no cadastro", () => {
    // As três telas de consulta existiam como arquivo e NENHUMA era
    // alcançável. Este teste é o que impede isso de voltar.
    const ir = (busca: string) => telaDoLink(busca);
    expect(ir("?tela=acoes")).toBe("acoes");
    expect(ir("?entidade=demo-a&tela=processos")).toBe("processos");
    expect(ir("?tela=painel")).toBe("painel");
    expect(ir("?tela=cadastro")).toBe("cadastro");
    expect(ir("?tela=sei-la")).toBe("cadastro");
    expect(ir("?entidade=demo-a")).toBe("cadastro");
    // Os links antigos continuam valendo: quebrar o link de quem já o tem é
    // mandar a pessoa ligar.
    expect(ir("?painel")).toBe("painel");
    expect(ir("?consulta")).toBe("processos");
  });

  it("toda área declarada é uma das quatro", () => {
    expect([...TELAS]).toEqual(["cadastro", "acoes", "processos", "painel"]);
  });
});

describe("o motivo sem o nome repetido", () => {
  const GIFA = "Gratificação de Incremento da Fiscalização e Arrecadação (GIFA)";

  it("tira o prefixo que já está no título acima", () => {
    expect(
      semPrefixo(`${GIFA}: ainda não homologado — quem assina é gente`, GIFA),
    ).toBe("Ainda não homologado — quem assina é gente");
  });

  it("tira também o prefixo da trilha do rótulo", () => {
    expect(semPrefixo(`${GIFA}: não se sabe do rol`, `Executar: ${GIFA}`)).toBe(
      "Não se sabe do rol",
    );
  });

  it("deixa intacto o motivo que não começa pelo rótulo", () => {
    const m = "não é possível afirmar que não há execução em curso";
    expect(semPrefixo(m, GIFA)).toBe(m);
  });

  it("não devolve vazio quando o motivo é só o rótulo", () => {
    // Melhor repetir o nome que mostrar uma linha em branco.
    expect(semPrefixo(GIFA, GIFA)).toBe(GIFA);
    expect(semPrefixo(`${GIFA}:`, GIFA)).toBe(`${GIFA}:`);
  });

  it("rótulo vazio não quebra", () => {
    expect(semPrefixo("alguma coisa", "")).toBe("alguma coisa");
  });
});

describe("a lista lê como lista", () => {
  it("põe a primeira letra em maiúscula", () => {
    expect(comoFrase("não se sabe se há título")).toBe(
      "Não se sabe se há título",
    );
  });

  it("não mexe no que já começa maiúsculo, nem em texto vazio", () => {
    expect(comoFrase("Ainda não homologado")).toBe("Ainda não homologado");
    expect(comoFrase("")).toBe("");
    expect(comoFrase("   ")).toBe("");
  });

  it("acento na primeira letra sobrevive", () => {
    expect(comoFrase("órgão julgador ausente")).toBe("Órgão julgador ausente");
  });
});
