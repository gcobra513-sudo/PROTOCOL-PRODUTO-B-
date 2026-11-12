/**
 * A sessão do portal: UMA para todas as áreas, e só na memória.
 *
 * Medido em 12/11/2026: cada área (ações, processos, atendimento) pedia CPF
 * e código de novo — quatro visitas, quatro códigos, contra um limite de
 * três por hora. O quarto pedido responde igual aos outros, e a pessoa fica
 * esperando um e-mail que não chega.
 *
 * A sessão passa a valer entre as áreas SEM ser guardada no navegador: o
 * computador da sede é usado por uma pessoa depois da outra, e o que fica
 * guardado é o que a próxima encontra (T23). Por isso há duas saídas, e as
 * duas estão aqui: o tempo parado e a sessão que o servidor não aceita mais.
 */
import { describe, expect, it } from "vitest";

import { ErroDoServidor } from "./envio";
import {
  LIMITE_PARADO_MS,
  cliqueQueNavega,
  paradoDemais,
  sessaoMorreu,
} from "./sessao";

describe("a sessão parada se encerra sozinha", () => {
  const AGORA = 1_800_000_000_000;

  it("dentro do limite, continua", () => {
    expect(paradoDemais(AGORA - LIMITE_PARADO_MS + 1000, AGORA)).toBe(false);
    expect(paradoDemais(AGORA, AGORA)).toBe(false);
  });

  it("no limite, encerra — é o que protege quem saiu sem clicar em Sair", () => {
    expect(paradoDemais(AGORA - LIMITE_PARADO_MS, AGORA)).toBe(true);
    expect(paradoDemais(AGORA - LIMITE_PARADO_MS - 1, AGORA)).toBe(true);
  });

  it("relógio que andou para trás não encerra ninguém", () => {
    // O relógio do aparelho é acertado sozinho. Um salto para trás daria
    // tempo parado negativo — que não é "demais".
    expect(paradoDemais(AGORA + 60_000, AGORA)).toBe(false);
  });

  it("o limite é de minutos, não de horas", () => {
    // A sessão do servidor vale 4 horas. A tela aberta num computador
    // compartilhado não pode valer isso.
    expect(LIMITE_PARADO_MS).toBeLessThanOrEqual(30 * 60 * 1000);
    expect(LIMITE_PARADO_MS).toBeGreaterThanOrEqual(10 * 60 * 1000);
  });
});

describe("a sessão que o servidor não aceita mais", () => {
  it("401 é sessão morta: a tela volta ao portão", () => {
    expect(sessaoMorreu(new ErroDoServidor("sessão inválida", 401))).toBe(true);
  });

  it("403 NÃO é: é a pessoa certa na área errada", () => {
    // O filiado que abre o painel do sindicato recebe 403. Derrubar a
    // sessão dele por isso o faria pedir outro código à toa.
    expect(sessaoMorreu(new ErroDoServidor("não é gestor", 403))).toBe(false);
  });

  it("erro que não veio do servidor não derruba a sessão", () => {
    expect(sessaoMorreu(new Error("sem rede"))).toBe(false);
    expect(sessaoMorreu(undefined)).toBe(false);
  });
});

describe("o clique que troca de área sem recarregar", () => {
  const simples = { button: 0, metaKey: false, ctrlKey: false,
                    shiftKey: false, altKey: false, defaultPrevented: false };

  it("clique simples navega por dentro", () => {
    expect(cliqueQueNavega(simples)).toBe(true);
  });

  it("abrir em outra aba continua sendo do navegador", () => {
    // Ctrl/Cmd+clique e botão do meio são pedidos explícitos de outra aba.
    // Interceptá-los quebraria um gesto que a pessoa conhece — e a aba nova
    // começa sem sessão, que é o certo.
    expect(cliqueQueNavega({ ...simples, ctrlKey: true })).toBe(false);
    expect(cliqueQueNavega({ ...simples, metaKey: true })).toBe(false);
    expect(cliqueQueNavega({ ...simples, shiftKey: true })).toBe(false);
    expect(cliqueQueNavega({ ...simples, button: 1 })).toBe(false);
  });
});
