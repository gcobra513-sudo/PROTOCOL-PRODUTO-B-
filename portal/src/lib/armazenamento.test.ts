/**
 * O rascunho é DE UMA PESSOA, e o navegador pode não ser.
 *
 * O sindicato atende vários filiados do mesmo computador da sede. Medido no
 * navegador em 12/11/2026: quem abria o portal depois de alguém que não
 * terminou caía DENTRO do cadastro dela — nome, CPF e e-mail na tela, sem
 * passar pelo portão. A chave do rascunho era uma só, e ele era restaurado
 * antes de qualquer identificação.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apagar, carregarDe, limpoPara, salvar } from "./armazenamento";
import { RASCUNHO_VAZIO, type Rascunho } from "./tipos";

const DELA = "862.883.667-57";
const DE_OUTRA = "111.444.777-35";

function rascunhoDe(cpf: string, nome: string): Rascunho {
  return {
    ...RASCUNHO_VAZIO,
    etapa: 3,
    identificacao: { ...RASCUNHO_VAZIO.identificacao, cpf, nome },
  };
}

let guardado: Map<string, string>;

beforeEach(() => {
  guardado = new Map();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => guardado.get(k) ?? null,
    setItem: (k: string, v: string) => void guardado.set(k, v),
    removeItem: (k: string) => void guardado.delete(k),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("o rascunho só volta para quem o escreveu", () => {
  it("a dona, depois do portão, reencontra o que digitou", () => {
    salvar(rascunhoDe(DELA, "SICRANA (CADASTRO DE EXEMPLO)"));
    // O CPF chega do portão sem máscara ou com: é a mesma pessoa.
    const volta = carregarDe("86288366757");
    expect(volta?.identificacao.nome).toBe("SICRANA (CADASTRO DE EXEMPLO)");
    expect(volta?.etapa).toBe(3);
  });

  it("outra pessoa não recebe nada — e o que estava guardado SOME", () => {
    salvar(rascunhoDe(DELA, "SICRANA (CADASTRO DE EXEMPLO)"));
    expect(carregarDe(DE_OUTRA)).toBeNull();
    // Não basta não mostrar: o que ficasse no navegador ficaria para o
    // próximo que soubesse onde olhar.
    expect([...guardado.values()].join("")).not.toContain("SICRANA");
    // …e a dona, se voltar depois, começa do zero. É o preço, e é o certo.
    expect(carregarDe(DELA)).toBeNull();
  });

  it("sem CPF conferido não há a quem devolver", () => {
    salvar(rascunhoDe(DELA, "SICRANA (CADASTRO DE EXEMPLO)"));
    expect(carregarDe("")).toBeNull();
    // Pergunta sem CPF NÃO apaga: é a tela antes do portão, e apagar ali
    // faria a dona perder o rascunho só por ter aberto a página.
    expect([...guardado.values()].join("")).toContain("SICRANA");
  });

  it("rascunho sem CPF não é de ninguém", () => {
    salvar(rascunhoDe("", "ALGUEM (CADASTRO DE EXEMPLO)"));
    expect(carregarDe(DELA)).toBeNull();
  });

  it("apagar tira tudo", () => {
    salvar(rascunhoDe(DELA, "SICRANA (CADASTRO DE EXEMPLO)"));
    apagar();
    expect(guardado.size).toBe(0);
  });
});

describe("trocar de pessoa na mesma aba", () => {
  it("começa limpo, só com o CPF novo", () => {
    const limpo = limpoPara(DE_OUTRA);
    expect(limpo.identificacao.cpf).toBe(DE_OUTRA);
    expect(limpo.identificacao.nome).toBe("");
    expect(limpo.documentos).toEqual([]);
    expect(limpo.etapa).toBe(0);
  });
});
