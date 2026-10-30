/**
 * O contrato da conta, testado do lado do portal.
 *
 * Aqui: o portal produz. Em `tests/testes_cadastro.py`: o servidor valida o
 * que este arquivo produz, lendo o MESMO
 * `compartilhado/contrato_cadastro.json`. Se as duas pontas divergirem, uma
 * das duas suítes reprova.
 */
import { describe, expect, it } from "vitest";

import contrato from "../../../compartilhado/contrato_cadastro.json";
import {
  linhaDoCadastro,
  nomearDocumentos,
  numerosParaAcompanhar,
} from "./exportar";
import {
  DOCUMENTOS,
  RASCUNHO_VAZIO,
  documentosFaltando,
  nomeDeArquivo,
  type Rascunho,
} from "./tipos";

function completo(): Rascunho {
  return {
    ...RASCUNHO_VAZIO,
    identificacao: {
      nome: "FULANA DE TAL (CADASTRO DE EXEMPLO)",
      cpf: "111.444.777-35",
      email: "fulana@exemplo.org",
      telefone: "(61) 99999-0000",
      dataNascimento: "1958-06-27",
    },
    carreira: {
      cargo: "Auditor-Fiscal da Receita Federal do Brasil",
      situacao: "aposentado",
      unidade: "Delegacia da Receita Federal em Goiânia",
      dataIngresso: "1992-04-01",
      dataAposentadoria: "2018-06-30",
    },
    filiacao: { desde: "1992-05", ate: "" },
    judicial: {
      temProcesso: "nao_sei",
      numeros: [],
      jaExecutou: "nao",
      temAcaoPropria: "nao",
    },
    confirmou: true,
  };
}

describe("o que o Produto B pede", () => {
  it("não pede procuração, identidade nem comprovante de residência", () => {
    // A dívida do Produto A, paga. Nenhum desses melhora a resposta do B.
    const tipos = DOCUMENTOS.map((d) => d.tipo as string);
    for (const doA of ["procuracao", "identidade", "residencia"]) {
      expect(tipos).not.toContain(doA);
    }
  });

  it("pede contribuição, e só ela é obrigatória", () => {
    const obrigatorios = DOCUMENTOS.filter((d) => d.obrigatorio).map((d) => d.tipo);
    expect(obrigatorios).toEqual(["contribuicao"]);
  });

  it("aceita vários comprovantes de contribuição", () => {
    const espec = DOCUMENTOS.find((d) => d.tipo === "contribuicao")!;
    expect(espec.multiplos).toBe(true);
    // Um comprovante por ano é o caso normal, e o índice é POR TIPO.
    expect(nomeDeArquivo("contribuicao", 0)).toBe("contribuicao-1.pdf");
    expect(nomeDeArquivo("contribuicao", 2)).toBe("contribuicao-3.pdf");
    expect(nomeDeArquivo("sentenca")).toBe("sentenca.pdf");
  });

  it("sentença e certidão entram só se a pessoa tiver", () => {
    for (const tipo of ["sentenca", "certidao_transito"]) {
      const espec = DOCUMENTOS.find((d) => d.tipo === tipo)!;
      expect(espec.obrigatorio, `${tipo} não pode ser obrigatório`).toBe(false);
    }
  });
});

describe("a linha do cadastro", () => {
  it("tem exatamente os campos do contrato", () => {
    expect(Object.keys(linhaDoCadastro(completo())).sort()).toEqual(
      [...contrato.campos].sort(),
    );
  });

  it("preenche todos os obrigatórios do contrato", () => {
    const l = linhaDoCadastro(completo());
    for (const campo of contrato.obrigatorios) {
      expect(l[campo], `obrigatório ${campo}`).toBeTruthy();
    }
  });

  it("deixa filiado_ate VAZIO para quem ainda é filiado", () => {
    // Vazio é resposta, não omissão. Inventar uma data de saída tiraria a
    // pessoa das ações que correm hoje.
    expect(linhaDoCadastro(completo()).filiado_ate).toBe("");
  });

  it("junta os números de processo por ponto e vírgula, só dígitos", () => {
    const r = completo();
    r.judicial.numeros = ["0001234-70.2019.4.01.3400", "0007654-05.2019.8.07.0001"];
    expect(linhaDoCadastro(r).numeros_de_processo).toBe(
      "00012347020194013400;00076540520198070001",
    );
  });

  it("não repete número nem exporta vazio", () => {
    const n = "0001234-70.2019.4.01.3400";
    expect(numerosParaAcompanhar([n, n, "", "   "]).split(";")).toHaveLength(1);
  });
});

describe("os documentos", () => {
  it("numera vários do mesmo tipo por tipo, não pela posição geral", () => {
    const r = completo();
    r.documentos = [
      { chave: 1, tipo: "contribuicao", nomeOriginal: "a.pdf", nomeFinal: "", tamanho: 1,
        sha256: "x", temTexto: true, cpfEncontrado: true },
      { chave: 2, tipo: "sentenca", nomeOriginal: "b.pdf", nomeFinal: "", tamanho: 1,
        sha256: "y", temTexto: true, cpfEncontrado: true },
      { chave: 3, tipo: "contribuicao", nomeOriginal: "c.pdf", nomeFinal: "", tamanho: 1,
        sha256: "z", temTexto: true, cpfEncontrado: true },
    ];
    const nomes = nomearDocumentos(r);
    // O terceiro arquivo é o SEGUNDO comprovante — se o índice fosse global,
    // ele viraria "contribuicao-3.pdf" e o primeiro contracheque de alguém
    // ficaria com número de terceiro.
    expect(nomes.get(0)).toBe("contribuicao-1.pdf");
    expect(nomes.get(1)).toBe("sentenca.pdf");
    expect(nomes.get(2)).toBe("contribuicao-2.pdf");
  });

  it("diz o que falta enquanto a contribuição não vier", () => {
    const r = completo();
    expect(documentosFaltando(r).map((d) => d.tipo)).toEqual(["contribuicao"]);
    r.documentos = [
      { chave: 4, tipo: "contribuicao", nomeOriginal: "a.pdf", nomeFinal: "", tamanho: 1,
        sha256: "x", temTexto: true, cpfEncontrado: true },
    ];
    expect(documentosFaltando(r)).toEqual([]);
  });

  it("declarar processo NÃO passa a exigir sentença", () => {
    // A pessoa pode saber o número e não ter o papel em mãos.
    const r = completo();
    r.judicial.temProcesso = "sim";
    r.documentos = [
      { chave: 5, tipo: "contribuicao", nomeOriginal: "a.pdf", nomeFinal: "", tamanho: 1,
        sha256: "x", temTexto: true, cpfEncontrado: true },
    ];
    expect(documentosFaltando(r)).toEqual([]);
  });
});
