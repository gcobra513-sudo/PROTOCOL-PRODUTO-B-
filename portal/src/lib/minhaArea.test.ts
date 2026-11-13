/**
 * MINHA ÁREA: a primeira tela de quem entrou, com tudo que é dele à vista.
 *
 * Ela RESUME o que as outras áreas dizem — e por isso não pode dizer nada
 * que elas não digam. Nenhum resumo aqui dá veredicto: conta, aponta, e
 * manda a pessoa para a área que explica.
 */
import { describe, expect, it } from "vitest";

import type * as api from "./envio";
import {
  cartaoDasAcoes,
  cartaoDoCadastro,
  cartaoDosProcessos,
  oQueFaltaVoce,
  primeiroNome,
} from "./minhaArea";

describe("o nome com que a tela cumprimenta", () => {
  it("é o primeiro nome, do jeito que se escreve", () => {
    expect(primeiroNome("MARIA DA SILVA (CADASTRO DE EXEMPLO)")).toBe("Maria");
    expect(primeiroNome("  joão  pedro ")).toBe("João");
  });
  it("sem nome, não inventa um", () => {
    expect(primeiroNome("")).toBe("");
  });
});

describe("enquanto não sabe, não diz", () => {
  it("consultando e erro têm frase própria, e nunca um número", () => {
    for (const cartao of [cartaoDoCadastro, cartaoDasAcoes, cartaoDosProcessos]) {
      expect(cartao(null).frase).toBe("Consultando…");
      expect(cartao("erro").frase).toBe("Não foi possível consultar agora.");
      expect(cartao("erro").estado).toBe("alerta");
      expect(cartao(null).frase + cartao("erro").frase).not.toMatch(/\d/);
    }
  });
});

describe("o cartão do cadastro", () => {
  const base = { conhecido: true, campos: {}, aviso: "" } as unknown as api.MeuCadastro;
  it("sem documento nenhum, pede o primeiro", () => {
    const c = cartaoDoCadastro({ ...base, documentos: [] });
    expect(c.frase).toBe("Ainda não recebemos nenhum documento seu.");
    expect(c.acao).toBe("Enviar meus documentos");
    expect(c.tela).toBe("cadastro");
  });
  it("com documentos, conta quantos tipos chegaram", () => {
    expect(cartaoDoCadastro({ ...base, documentos: ["contribuicao"] }).frase)
      .toBe("Já recebemos 1 tipo de documento seu.");
    expect(cartaoDoCadastro({ ...base, documentos: ["contribuicao", "sentenca"] }).frase)
      .toBe("Já recebemos 2 tipos de documento seus.");
  });
});

describe("o cartão das ações", () => {
  const acao = (estado: string) => ({ id: "x", rotulo: "X", estado, inicio: "", fim: "", meses: 0, motivos: [] });
  const base = { entidade: "", nome: "", filiado: "", categorias: [], catalogo: "", oportunidades: [], pendencias: [], aviso: "" };
  it("conta de quantas a pessoa faz parte — e NÃO diz o que ela pode", () => {
    const c = cartaoDasAcoes({ ...base, acoes: [acao("PARTICIPA"), acao("PARTICIPA"), acao("NAO_PARTICIPA")] });
    expect(c.frase).toBe("Você faz parte de 2 ações do seu sindicato.");
    // O veredicto é da área Minhas ações, com os motivos. Um resumo que
    // dissesse "você pode" seria um veredicto sem a explicação.
    expect(c.frase.toLowerCase()).not.toMatch(/pode|direito|receber|valor/);
    expect(c.tela).toBe("acoes");
  });
  it("sem nenhuma confirmada, diz que ainda não deu para dizer", () => {
    expect(cartaoDasAcoes({ ...base, acoes: [acao("INDETERMINADO")] }).frase)
      .toBe("Ainda não deu para dizer de quais ações você faz parte.");
    expect(cartaoDasAcoes({ ...base, acoes: [] }).frase)
      .toBe("Ainda não deu para dizer de quais ações você faz parte.");
  });
});

describe("o cartão dos processos", () => {
  const base = { nome: "", limite: "" };
  it("sem processo informado, diz isso", () => {
    expect(cartaoDosProcessos({ ...base, processos: [], conferido_em: "" }).frase)
      .toBe("Você não informou nenhum processo.");
  });
  it("com processo, traz a última movimentação e quando conferimos", () => {
    const c = cartaoDosProcessos({
      ...base,
      conferido_em: "2026-11-11T09:00:00+00:00",
      processos: [
        { numero: "1", tribunal: "TRF1", ultimo_movimento: { data: "2026-11-10", nome: "Conclusos para decisão", grau: "G1" } },
        { numero: "2", tribunal: "TRF1", ultimo_movimento: { data: "2026-10-01", nome: "Juntada", grau: "G1" } },
      ],
    });
    expect(c.frase).toBe(
      "Você acompanha 2 processos. Última movimentação: Conclusos para decisão, em 10/11/2026. Conferido em 11/11/2026.",
    );
  });
  it("se nunca conferimos o tribunal, diz que não conferiu — não diz 'nada novo'", () => {
    const c = cartaoDosProcessos({
      ...base, conferido_em: "",
      processos: [{ numero: "1", tribunal: "TRF1", ultimo_movimento: null }],
    });
    expect(c.frase).toBe("Você acompanha 1 processo. Ainda não conferimos o tribunal.");
  });
});

describe("o que falta a pessoa fazer", () => {
  it("é só o que depende DELA, na ordem em que veio", () => {
    const acoes = {
      pendencias: [
        { quem: "TRIBUNAL", titulo: "", explicacao: "", itens: ["julgamento"] },
        { quem: "VOCE", titulo: "", explicacao: "", itens: ["enviar a sentença", "enviar a certidão"] },
      ],
    } as unknown as api.MinhasAcoes;
    expect(oQueFaltaVoce(acoes)).toEqual(["enviar a sentença", "enviar a certidão"]);
    expect(oQueFaltaVoce(null)).toEqual([]);
    expect(oQueFaltaVoce("erro")).toEqual([]);
  });
});
