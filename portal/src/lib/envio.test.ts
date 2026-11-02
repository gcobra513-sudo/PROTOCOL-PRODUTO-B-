/**
 * O que a tela MANDA pelo fio.
 *
 * ESTA É A CLASSE DE DEFEITO QUE NENHUMA OUTRA SUÍTE PEGA, e o `LEIAME.md`
 * do servidor já dizia isso com outras palavras: "o navegador mandando um
 * nome de campo que o servidor não espera". Os testes de `painel.ts` provam
 * o que a tela DIZ; os do servidor provam o que ele ACEITA. Entre os dois
 * havia um lugar sem teste, e é exatamente a tradução de nome de campo que
 * mora nele: no TypeScript o campo é `pedidoPor`, no corpo HTTP é
 * `pedido_por`, e nada conferia a tradução.
 *
 * Um erro aqui não daria erro: o servidor leria `corpo.get("pedido_por")`
 * como vazio, e apagaria a pessoa SEM REGISTRO DE QUEM MANDOU — que é o
 * mesmo defeito que a correção do I6 acabou de fechar do lado do servidor.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { apagarFiliado } from "./envio";

const RESPOSTA = {
  marcador: "abc", banco: {}, portao: 0, diario: 0, arquivos: 0,
  rol: 0, acervo: 0, logs: 0, email_conhecido: true, vestigios: [],
};

function fingirFetch(corpo: unknown = RESPOSTA, ok = true, status = 200) {
  const espia = vi.fn(async (_url: string, _opcoes: RequestInit) => ({
    ok,
    status,
    json: async () => corpo,
  }));
  vi.stubGlobal("fetch", espia);
  return espia;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apagarFiliado, no fio", () => {
  it("manda os nomes de campo que o servidor lê", async () => {
    const espia = fingirFetch();
    await apagarFiliado("sind-x", "T0K3N", {
      cpf: "111.444.777-35",
      motivo: "pedido do titular",
      pedidoPor: "gestor@exemplo.invalid",
    });

    const [url, opcoes] = espia.mock.calls[0]!;
    expect(url).toContain("/api/entidade/sind-x/apagar");
    expect(opcoes.method).toBe("POST");
    const corpo = JSON.parse(String(opcoes.body));
    // snake_case, como o servidor lê. `pedidoPor` aqui apagaria sem autor.
    expect(Object.keys(corpo).sort()).toEqual(["cpf", "motivo", "pedido_por"]);
    expect(corpo.pedido_por).toBe("gestor@exemplo.invalid");
  });

  it("manda o token do gestor, sem o qual a rota é 401", async () => {
    const espia = fingirFetch();
    await apagarFiliado("sind-x", "T0K3N", {
      cpf: "111.444.777-35", motivo: "", pedidoPor: "g",
    });
    const [, opcoes] = espia.mock.calls[0]!;
    const cabecalhos = opcoes.headers as Record<string, string>;
    expect(cabecalhos.Authorization).toBe("Bearer T0K3N");
    expect(cabecalhos["Content-Type"]).toBe("application/json");
  });

  it("escapa o apelido da entidade na URL", async () => {
    const espia = fingirFetch();
    await apagarFiliado("a/b", "T", {
      cpf: "111.444.777-35", motivo: "", pedidoPor: "g",
    });
    const [url] = espia.mock.calls[0]!;
    expect(url).toContain("a%2Fb");
  });

  it("erro do servidor sobe como erro, nunca como apagamento feito", async () => {
    // O 503 do I6 ("não conseguimos registrar quem pediu") chega aqui. Se
    // isto devolvesse o corpo em vez de levantar, a tela diria que apagou.
    fingirFetch({ detail: { erro: "sem registro, não apagamos nada" } },
                false, 503);
    await expect(
      apagarFiliado("sind-x", "T", {
        cpf: "111.444.777-35", motivo: "", pedidoPor: "g",
      }),
    ).rejects.toThrow("sem registro");
  });
});
