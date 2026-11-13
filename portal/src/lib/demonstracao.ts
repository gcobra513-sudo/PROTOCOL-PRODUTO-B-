/**
 * Os acessos da demonstração: com que CPF FICTÍCIO entrar, dito na tela.
 *
 * Quem abre o link de uma demonstração não tem como adivinhar um CPF que
 * entre. O servidor, e só em modo de demonstração, manda a lista; aqui ela é
 * só conferida e formatada. Sem a marca de demonstração vinda do servidor,
 * não há lista — o portal não decide sozinho que algo é demonstração.
 */
import type { Entidade } from "./envio";

export interface AcessoDaDemo {
  quem: string;
  /** Já formatado, como a pessoa vai digitar. */
  cpf: string;
  area: "cadastro" | "painel";
  gestor: boolean;
}

export function acessosDaDemonstracao(e: Entidade | null): AcessoDaDemo[] {
  if (!e?.demonstracao || !Array.isArray(e.acessos_da_demonstracao)) return [];
  const saida: AcessoDaDemo[] = [];
  for (const a of e.acessos_da_demonstracao) {
    if (!a || !/^\d{11}$/.test(a.cpf) || !a.quem) continue;
    const c = a.cpf;
    saida.push({
      quem: a.quem,
      cpf: `${c.slice(0, 3)}.${c.slice(3, 6)}.${c.slice(6, 9)}-${c.slice(9)}`,
      area: a.area === "painel" ? "painel" : "cadastro",
      gestor: a.area === "painel",
    });
  }
  return saida;
}
