/**
 * O preenchimento do que o sindicato já mandou.
 *
 * O teste que mais importa é o de NÃO SOBRESCREVER: a pessoa está entrando
 * justamente para corrigir o que está errado, e apagar a correção dela no
 * meio da digitação é o pior momento possível para fazer isso.
 */
import { describe, expect, it } from "vitest";

import { camposDoSindicato, jaTemos, preencher } from "./conhecido";
import { RASCUNHO_VAZIO, type Rascunho } from "./tipos";

const DO_SINDICATO = {
  nome_completo: "FULANA DE TAL (CADASTRO DE EXEMPLO)",
  cpf: "111.444.777-35",
  email: "fulana@exemplo.org",
  cargo: "Auditor-Fiscal da Receita Federal do Brasil",
  situacao: "aposentado",
  filiado_desde: "2004-03",
  filiado_ate: "",
};

describe("o que o sindicato mandou", () => {
  it("preenche o que está em branco", () => {
    const r = preencher(RASCUNHO_VAZIO, DO_SINDICATO);
    expect(r.identificacao.nome).toContain("FULANA");
    expect(r.identificacao.cpf).toBe("111.444.777-35");
    expect(r.carreira.cargo).toContain("Auditor-Fiscal");
    expect(r.filiacao.desde).toBe("2004-03");
  });

  it("NÃO sobrescreve o que a pessoa já digitou", () => {
    // Ela está corrigindo. Correção não se desfaz.
    const digitado: Rascunho = {
      ...RASCUNHO_VAZIO,
      carreira: { ...RASCUNHO_VAZIO.carreira, cargo: "Analista Tributário" },
    };
    const r = preencher(digitado, DO_SINDICATO);
    expect(r.carreira.cargo).toBe("Analista Tributário");
    // e o resto continua sendo preenchido
    expect(r.identificacao.nome).toContain("FULANA");
  });

  it("campo vazio no sindicato não apaga nada nem marca nada", () => {
    const digitado: Rascunho = {
      ...RASCUNHO_VAZIO,
      filiacao: { desde: "1999-01", ate: "2010-12" },
    };
    const r = preencher(digitado, DO_SINDICATO);
    expect(r.filiacao.ate).toBe("2010-12");
    expect(camposDoSindicato(DO_SINDICATO).has("filiacao.ate")).toBe(false);
  });

  it("não quebra com retorno vazio nem com campo que não existe", () => {
    expect(preencher(RASCUNHO_VAZIO, {})).toEqual(RASCUNHO_VAZIO);
    const r = preencher(RASCUNHO_VAZIO, { campo_inventado: "x" });
    expect(r).toEqual(RASCUNHO_VAZIO);
  });

  it("não toca no que a pessoa tem de responder sozinha", () => {
    // `ja_executou`, `tem_acao_propria` e `quer_aviso` são DELA: o sindicato
    // não sabe, e preencher por ele seria responder no lugar dela.
    const r = preencher(RASCUNHO_VAZIO, {
      ...DO_SINDICATO,
      ja_executou: "sim",
      tem_acao_propria: "sim",
      quer_aviso: "sim",
    });
    expect(r.judicial.jaExecutou).toBe(RASCUNHO_VAZIO.judicial.jaExecutou);
    expect(r.judicial.temAcaoPropria).toBe(
      RASCUNHO_VAZIO.judicial.temAcaoPropria,
    );
    expect(r.querAviso).toBe(RASCUNHO_VAZIO.querAviso);
  });
});

describe("marcar de onde veio", () => {
  it("marca só os campos que vieram preenchidos", () => {
    const marcados = camposDoSindicato(DO_SINDICATO);
    expect(marcados.has("identificacao.nome")).toBe(true);
    expect(marcados.has("carreira.cargo")).toBe(true);
    expect(marcados.has("filiacao.desde")).toBe(true);
    expect(marcados.has("filiacao.ate")).toBe(false);
    expect(marcados.has("carreira.unidade")).toBe(false);
  });
});

describe("os documentos que já temos", () => {
  it("traduz o tipo para o que a pessoa entende", () => {
    expect(jaTemos(["sentenca", "contribuicao"])).toEqual([
      "sentença",
      "comprovante de contribuição",
    ]);
  });

  it("tipo desconhecido aparece cru em vez de sumir", () => {
    // Fail-visible: cru é feio o suficiente para alguém consertar; sumido,
    // ninguém vê.
    expect(jaTemos(["coisa_nova"])).toEqual(["coisa_nova"]);
    expect(jaTemos([])).toEqual([]);
  });
});

describe("o que ainda falta anexar", () => {
  it("não pede o que o sindicato já mandou", async () => {
    // Era o que travava a pessoa na etapa de documentos, pedindo um
    // comprovante que o sindicato já tinha entregado.
    const { tiposFaltando } = await import("../etapas/Documentos");
    expect(tiposFaltando([], [])).toEqual(["contribuicao"]);
    expect(tiposFaltando([], ["contribuicao"])).toEqual([]);
  });

  it("documento que não é obrigatório não aparece de qualquer jeito", async () => {
    const { tiposFaltando } = await import("../etapas/Documentos");
    expect(tiposFaltando([], ["sentenca"])).toEqual(["contribuicao"]);
  });
});
