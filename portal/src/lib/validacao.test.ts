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
