/**
 * Conformidade entre o TypeScript e o Python.
 *
 * Os dois leem `compartilhado/vetores_validacao.json`. Se as implementações
 * divergirem, um destes testes reprova — e o espelho em Python
 * (`tests/testes_conformidade_portal.py`) reprova do outro lado.
 */
import { describe, expect, it } from "vitest";

import vetores from "../../../compartilhado/vetores_validacao.json";
import {
  calcularVerificador,
  destinoDoNumero,
  conferirCpf,
  conferirProcesso,
  decompor,
  formatarCpf,
  formatarProcesso,
} from "./validacao";

describe("CPF", () => {
  it.each(vetores.cpf.validos)("aceita %s", (valor) => {
    expect(conferirCpf(valor)).toEqual([]);
  });

  it.each(vetores.cpf.invalidos)("recusa $valor ($motivo)", ({ valor }) => {
    expect(conferirCpf(valor).length).toBeGreaterThan(0);
  });

  it("formata enquanto se digita, sem travar", () => {
    expect(formatarCpf("111")).toBe("111");
    expect(formatarCpf("111444")).toBe("111.444");
    expect(formatarCpf("11144477735")).toBe("111.444.777-35");
    // Mais dígitos do que cabe não pode quebrar nem crescer sem limite.
    expect(formatarCpf("111444777350000")).toBe("111.444.777-35");
  });
});

describe("número de processo", () => {
  it.each(vetores.processo_cnj.validos)("aceita $valor", ({ valor }) => {
    expect(conferirProcesso(valor)).toEqual([]);
  });

  it.each(vetores.processo_cnj.invalidos)(
    "recusa $valor ($motivo)",
    ({ valor }) => {
      expect(conferirProcesso(valor).length).toBeGreaterThan(0);
    },
  );

  it.each(vetores.processo_cnj.fora_do_trf1)(
    "avisa que $valor não é do TRF1 ($justica)",
    ({ valor }) => {
      // Íntegro como número...
      expect(conferirProcesso(valor)).toEqual([]);
      // ...mas avisa quando se exige TRF1. É aviso, não recusa: a pessoa pode
      // ter um processo de outro tribunal e ainda assim ser o processo dela.
      expect(conferirProcesso(valor, { exigirTrf1: true }).length)
        .toBeGreaterThan(0);
    },
  );

  it("usa BigInt, e o Number daria resposta DIFERENTE", () => {
    // A primeira versão deste teste comparava Number("000000191...") com
    // MAX_SAFE_INTEGER e reprovava: aquele número tem zeros à esquerda, então
    // como Number ele é pequeno. Asserção desleixada, que não provava nada.
    //
    // A conta que o algoritmo faz de verdade é sobre
    // sequencial+ano+segmento+tribunal+origem+"00". Com sequencial alto são
    // 20 dígitos significativos, e aí a precisão do Number se perde.
    const p = decompor("99999994820264013400")!;
    const base = `${p.sequencial}${p.ano}${p.segmento}${p.tribunal}${p.origem}00`;
    expect(base).toHaveLength(20);
    expect(Number(base)).toBeGreaterThan(Number.MAX_SAFE_INTEGER);

    const comBigInt = String(98n - (BigInt(base) % 97n)).padStart(2, "0");
    const comNumber = String(98 - (Number(base) % 97)).padStart(2, "0");
    expect(comBigInt).toBe("48");
    expect(comNumber).toBe("63");
    // É esta linha que justifica o BigInt: trocar por Number muda o dígito.
    expect(comNumber).not.toBe(comBigInt);
    expect(calcularVerificador(p)).toBe("48");
  });

  it("formata enquanto se digita", () => {
    expect(formatarProcesso("0000001")).toBe("0000001");
    expect(formatarProcesso("00000019120264013400")).toBe(
      "0000001-91.2026.4.01.3400",
    );
  });
});

// --------------------------------------------------------------------------
// Procuração e privacidade — os dois últimos itens da especificação.
// --------------------------------------------------------------------------
import { CONTROLADOR, temPendencia } from "../componentes/Privacidade";
import { A_PREENCHER, textoDaProcuracao } from "./procuracao";
import { RASCUNHO_VAZIO, type Rascunho } from "./tipos";

function pessoa(): Rascunho {
  return {
    ...RASCUNHO_VAZIO,
    pessoais: {
      ...RASCUNHO_VAZIO.pessoais,
      nome: "MARIA SILVA SOUZA",
      cpf: "111.444.777-35",
      rg: "1234567",
      logradouro: "Rua das Flores",
      numero: "100",
      bairro: "Centro",
      municipio: "Brasília",
      uf: "DF",
      cep: "70000-000",
    },
  };
}

describe("modelo de procuração", () => {
  it("traz os poderes para EXECUTAR, que é o que costuma faltar", () => {
    const t = textoDaProcuracao(pessoa(), "direto_ao_advogado");
    for (const termo of [
      "cumprimento de sentença",
      "dar quitação",
      "levantar",
      "precatório",
    ]) {
      expect(t.toLowerCase(), `falta: ${termo}`).toContain(termo.toLowerCase());
    }
  });

  it("traz os poderes para SUBSTABELECER", () => {
    const t = textoDaProcuracao(pessoa(), "direto_ao_advogado");
    expect(t.toLowerCase()).toContain("substabelecer");
    expect(t.toLowerCase()).toContain("reserva de iguais poderes");
  });

  it("usa os dados que a pessoa já preencheu", () => {
    const t = textoDaProcuracao(pessoa(), "direto_ao_advogado");
    expect(t).toContain("MARIA SILVA SOUZA");
    expect(t).toContain("111.444.777-35");
    expect(t).toContain("Rua das Flores, 100");
    expect(t).toContain("Brasília/DF");
  });

  it("NÃO inventa nome nem OAB de advogado", () => {
    const t = textoDaProcuracao(pessoa(), "direto_ao_advogado");
    // Documento assinado por milhares de pessoas não pode trazer advogado
    // inventado. Os campos saem como marcadores a preencher.
    expect(t).toContain("[NOME COMPLETO DO ADVOGADO]");
    expect(t).toContain("[OAB/UF Nº]");
    expect(A_PREENCHER.length).toBeGreaterThan(0);
  });

  it("atende os dois caminhos, porque a decisão é jurídica e está pendente", () => {
    const direto = textoDaProcuracao(pessoa(), "direto_ao_advogado");
    const sindicato = textoDaProcuracao(pessoa(), "ao_sindicato");
    expect(direto).toContain("[NOME COMPLETO DO ADVOGADO]");
    expect(sindicato).toContain("[NOME DA ENTIDADE SINDICAL]");
    expect(direto).not.toBe(sindicato);
    // As cláusulas essenciais valem nos dois.
    for (const t of [direto, sindicato]) {
      expect(t.toLowerCase()).toContain("substabelecer");
      expect(t.toLowerCase()).toContain("cumprimento de sentença");
    }
  });

  it("funciona com o formulário vazio, sem quebrar", () => {
    const t = textoDaProcuracao(RASCUNHO_VAZIO, "direto_ao_advogado");
    expect(t).toContain("[NOME DO OUTORGANTE]");
    expect(t).toContain("PROCURAÇÃO");
  });
});

describe("termo de privacidade", () => {
  it("avisa que o controlador não foi preenchido", () => {
    // Enquanto houver marcador, a tela mostra o aviso de protótipo. Subir
    // isto para gente de verdade com "[CNPJ]" no texto seria indefensável.
    expect(temPendencia()).toBe(true);
  });

  it("tem campo para encarregado e canal de direitos", () => {
    expect(CONTROLADOR).toHaveProperty("encarregado");
    expect(CONTROLADOR).toHaveProperty("canal");
  });
});

describe("para onde vai o número que a pessoa digitou", () => {
  it("processo do TRF1 serve como processo da sentença", () => {
    expect(destinoDoNumero("0001234-70.2019.4.01.3400")).toBe("sentenca");
  });

  it("processo de outro tribunal vai para acompanhamento, não para a sentença", () => {
    // A execução corre no juízo que decidiu (CPC, art. 516, II), e o Produto
    // A protocola no TRF1. A tela tem de DIZER isso, em vez de deixar a
    // pessoa enviar e ser recusada pelo servidor.
    expect(destinoDoNumero("0007654-05.2019.8.07.0001")).toBe("acompanhar");
    expect(destinoDoNumero("0001234-06.2019.4.05.8300")).toBe("acompanhar");
  });

  it("número que não fecha o dígito não vai para lugar nenhum", () => {
    expect(destinoDoNumero("0001234-71.2019.4.01.3400")).toBe("invalido");
  });

  it("campo vazio é vazio, não é erro", () => {
    expect(destinoDoNumero("")).toBe("vazio");
  });
});
