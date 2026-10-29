/**
 * O contrato de dados, testado dos dois lados.
 *
 * Aqui: o portal produz o manifesto. Em
 * `tests/testes_contrato_entrega.py`: o verificador do motor consome o que
 * este arquivo produz, e reprova se as colunas ou os nomes de arquivo
 * divergirem.
 */
import { describe, expect, it } from "vitest";

import contrato from "../../../compartilhado/contrato_entrega.json";
import { linhaDoManifesto, manifestoCsv } from "./exportar";
import { DOCUMENTOS, NOME_DE_ARQUIVO, RASCUNHO_VAZIO, type Rascunho } from "./tipos";

function completo(): Rascunho {
  return {
    ...RASCUNHO_VAZIO,
    pessoais: {
      ...RASCUNHO_VAZIO.pessoais,
      nome: "MARIA SILVA SOUZA",
      cpf: "111.444.777-35",
      email: "maria@exemplo.com",
      telefone: "(61) 99999-0000",
      cep: "70000-000",
      logradouro: "Rua das Flores",
      numero: "100",
      bairro: "Centro",
      municipio: "Brasília",
      uf: "DF",
    },
    funcional: {
      ...RASCUNHO_VAZIO.funcional,
      cargo: "Auditor-Fiscal",
      situacao: "ativo",
      dataIngresso: "2005-03-01",
    },
    processo: {
      temProcesso: "sim",
      numero: "0000001-91.2026.4.01.3400",
      observacao: "",
      acompanhar: [],
    },
    declaracoes: {
      jaExecutou: "nao",
      jaRecebeu: "nao",
      outroAdvogado: "nao",
      cienciaEIniciativa: true,
      querAviso: false,
    },
  };
}

/** Um rascunho com números para acompanhar. */
function acompanhando(numeros: string[]): Rascunho {
  const r = completo();
  r.processo.acompanhar = numeros;
  return r;
}

describe("manifesto", () => {
  it("tem exatamente as colunas do contrato, na ordem", () => {
    const csv = manifestoCsv([completo()]);
    const cabecalho = csv.split("\r\n")[0]!.split(",");
    expect(cabecalho).toEqual(contrato.colunas_manifesto);
  });

  it("preenche todos os campos que o verificador exige", () => {
    const l = linhaDoManifesto(completo());
    // Estes são os que o conferir_entrega.py reprova quando vazios.
    for (const campo of [
      "cpf", "nome_completo", "logradouro", "municipio", "uf", "cep",
      "situacao", "tem_processo", "ciencia_e_iniciativa",
    ]) {
      expect(l[campo], `campo ${campo}`).toBeTruthy();
    }
  });

  it("deixa ciencia_e_iniciativa VAZIO quando não foi declarada", () => {
    const r = completo();
    r.declaracoes.cienciaEIniciativa = false;
    // Vazio é o que faz o verificador reprovar — e tem de reprovar.
    expect(linhaDoManifesto(r).ciencia_e_iniciativa).toBe("");
  });

  it("não escreve número de processo de quem não tem", () => {
    const r = completo();
    r.processo.temProcesso = "nao_sei";
    r.processo.numero = "0000001-91.2026.4.01.3400";  // resquício do rascunho
    // Levar um número que a pessoa disse não conhecer seria inventar dado.
    expect(linhaDoManifesto(r).numero_processo).toBe("");
  });

  it("escapa vírgula e aspas, senão a planilha quebra", () => {
    const r = completo();
    r.pessoais.nome = 'SOUZA, MARIA "DA SILVA"';
    const csv = manifestoCsv([r]);
    expect(csv).toContain('"SOUZA, MARIA ""DA SILVA"""');
    // Uma linha de cabeçalho e uma de dados — a vírgula não criou coluna.
    expect(csv.trimEnd().split("\r\n")).toHaveLength(2);
  });
});

describe("nomes de arquivo", () => {
  it("são os do contrato, para todos os tipos", () => {
    for (const d of DOCUMENTOS) {
      expect(NOME_DE_ARQUIVO[d.tipo], `tipo ${d.tipo}`).toBe(
        (contrato.arquivos as Record<string, string>)[d.tipo],
      );
    }
  });

  it("cobre os obrigatórios do motor", () => {
    const gerados = DOCUMENTOS.map((d) => NOME_DE_ARQUIVO[d.tipo]);
    for (const esperado of contrato.obrigatorios) {
      expect(gerados).toContain(esperado);
    }
  });

  it("marca como condicional exatamente o que o contrato diz", () => {
    const condicionais = DOCUMENTOS.filter((d) => d.soComProcesso).map(
      (d) => NOME_DE_ARQUIVO[d.tipo],
    );
    expect(condicionais.sort()).toEqual([...contrato.se_tem_processo].sort());
  });
});

describe("acompanhamento", () => {
  const TRF1 = "0001234-70.2019.4.01.3400";
  const TJDFT = "0007654-05.2019.8.07.0001";

  it("junta os números por ponto e vírgula, só dígitos", () => {
    const l = linhaDoManifesto(acompanhando([TRF1, TJDFT]));
    expect(l.acompanhar).toBe("00012347020194013400;00076540520198070001");
  });

  it("não repete número nem exporta vazio", () => {
    const l = linhaDoManifesto(acompanhando([TRF1, TRF1, "", "   "]));
    expect((l.acompanhar ?? "").split(";")).toHaveLength(1);
  });

  it("aceita processo de outro tribunal — acompanhar não é protocolar", () => {
    const l = linhaDoManifesto(acompanhando([TJDFT]));
    expect(l.acompanhar).toBe("00076540520198070001");
  });

  it("exporta o opt-in como sim ou vazio, nunca como booleano", () => {
    const sim = completo();
    sim.declaracoes.querAviso = true;
    expect(linhaDoManifesto(sim).quer_aviso).toBe("sim");
    expect(linhaDoManifesto(completo()).quer_aviso).toBe("");
  });

  it("NÃO leva os campos do portal para o manifesto do motor", () => {
    // O manifesto é do Produto A e não sabe de acompanhamento. Se estes
    // campos entrassem no CSV, o verificador reprovaria coluna que não tem.
    const cabecalho = manifestoCsv([acompanhando([TRF1])]).split("\r\n")[0]!;
    expect(cabecalho).not.toContain("acompanhar");
    expect(cabecalho).not.toContain("quer_aviso");
  });
});
