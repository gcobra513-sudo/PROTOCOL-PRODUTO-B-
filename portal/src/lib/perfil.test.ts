/**
 * O MENU POR PERFIL: cada pessoa vê só o que é dela.
 *
 * Antes o menu mostrava tudo para todos — o filiado via "Painel do
 * sindicato", o gestor via as áreas de filiado. Quem tem pouca prática com
 * computador clica no que está na tela, e o que estava na tela não era dele.
 */
import { describe, expect, it } from "vitest";

import { gruposDoMenu, telaDeChegada } from "./perfil";

const filiado = { filiado: true, gestor: false };
const gestor = { filiado: false, gestor: true };
const osDois = { filiado: true, gestor: true };

describe("o que o menu mostra", () => {
  it("antes de entrar, as duas portas: a pessoa ainda não disse quem é", () => {
    expect(gruposDoMenu(null)).toEqual({ filiado: true, sindicato: true });
  });
  it("o filiado não vê o painel do sindicato", () => {
    expect(gruposDoMenu(filiado)).toEqual({ filiado: true, sindicato: false });
  });
  it("o gestor não vê as áreas de filiado", () => {
    expect(gruposDoMenu(gestor)).toEqual({ filiado: false, sindicato: true });
  });
  it("quem é as duas coisas vê as duas", () => {
    expect(gruposDoMenu(osDois)).toEqual({ filiado: true, sindicato: true });
  });
  it("se o servidor não soube dizer, mostra tudo — menu vazio prende a pessoa", () => {
    expect(gruposDoMenu({ filiado: false, gestor: false })).toEqual({ filiado: true, sindicato: true });
  });
});

describe("para onde a pessoa vai ao entrar pela porta que não é a dela", () => {
  it("o gestor que entrou por uma área de filiado vai para o painel", () => {
    for (const tela of ["area", "cadastro", "acoes", "processos", "atendimento"] as const) {
      expect(telaDeChegada(gestor, tela)).toBe("painel");
    }
  });
  it("o filiado que entrou pelo painel vai para a Minha área", () => {
    expect(telaDeChegada(filiado, "painel")).toBe("area");
  });
  it("quem está na porta certa fica onde está", () => {
    expect(telaDeChegada(filiado, "processos")).toBe("processos");
    expect(telaDeChegada(gestor, "painel")).toBe("painel");
    expect(telaDeChegada(osDois, "painel")).toBe("painel");
    expect(telaDeChegada(osDois, "area")).toBe("area");
    expect(telaDeChegada(null, "painel")).toBe("painel");
    expect(telaDeChegada({ filiado: false, gestor: false }, "acoes")).toBe("acoes");
  });
});
