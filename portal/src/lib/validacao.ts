/**
 * CPF e número de processo: validação com dígito verificador.
 *
 * POR QUE ISTO EXISTE EM DOIS LUGARES
 *
 * O algoritmo também vive em `src/sindilote/processo_cnj.py`, e duplicar
 * algoritmo é como se introduz divergência silenciosa. A especificação do
 * portal deixava a escolha entre portar (rápido, duplica) e expor como API
 * (uma fonte da verdade, mas depende de rede a cada dígito digitado).
 *
 * A saída: portar E travar. As duas implementações são testadas contra os
 * MESMOS vetores, em `compartilhado/vetores_validacao.json`. Se uma divergir,
 * um teste reprova — de qualquer dos dois lados. A pessoa ganha validação
 * instantânea e a divergência deixa de ser risco invisível.
 *
 * Quem mudar um lado roda os testes dos dois.
 */

export function soDigitos(valor: string): string {
  return (valor ?? "").replace(/\D/g, "");
}

// --------------------------------------------------------------------------
// CPF
// --------------------------------------------------------------------------

/** Devolve a lista de problemas. Vazia = CPF íntegro. */
export function conferirCpf(valor: string): string[] {
  const d = soDigitos(valor);
  if (!d) return ["informe o CPF"];
  if (d.length !== 11) {
    return [`o CPF tem 11 dígitos (você digitou ${d.length})`];
  }
  // Sequência repetida passa na conta dos dígitos mas não é CPF de ninguém.
  // 111.111.111-11 é o caso clássico, e é o que alguém digita para "testar".
  if (/^(\d)\1{10}$/.test(d)) {
    return ["este CPF não existe (todos os dígitos iguais)"];
  }
  const dv = (base: string, pesoInicial: number): number => {
    let soma = 0;
    for (let i = 0; i < base.length; i += 1) {
      soma += Number(base[i]) * (pesoInicial - i);
    }
    const resto = (soma * 10) % 11;
    return resto === 10 ? 0 : resto;
  };
  const d1 = dv(d.slice(0, 9), 10);
  const d2 = dv(d.slice(0, 10), 11);
  if (Number(d[9]) !== d1 || Number(d[10]) !== d2) {
    return ["este CPF parece ter um erro de digitação, confira"];
  }
  return [];
}

export function formatarCpf(valor: string): string {
  const d = soDigitos(valor).slice(0, 11);
  const p = [d.slice(0, 3), d.slice(3, 6), d.slice(6, 9), d.slice(9, 11)];
  let fora = p[0]!;
  if (p[1]) fora += `.${p[1]}`;
  if (p[2]) fora += `.${p[2]}`;
  if (p[3]) fora += `-${p[3]}`;
  return fora;
}

// --------------------------------------------------------------------------
// Número de processo (Res. CNJ 65/2008) — NNNNNNN-DD.AAAA.J.TR.OOOO
// --------------------------------------------------------------------------

export interface NumeroProcesso {
  sequencial: string;
  verificador: string;
  ano: string;
  segmento: string;
  tribunal: string;
  origem: string;
}

/** Nome de cada segmento da Justiça, pelo dígito J. */
export const SEGMENTOS: Record<string, string> = {
  "1": "Supremo Tribunal Federal",
  "2": "Conselho Nacional de Justiça",
  "3": "Superior Tribunal de Justiça",
  "4": "Justiça Federal",
  "5": "Justiça do Trabalho",
  "6": "Justiça Eleitoral",
  "7": "Justiça Militar da União",
  "8": "Justiça Estadual",
  "9": "Justiça Militar estadual",
};

export function decompor(valor: string): NumeroProcesso | null {
  const d = soDigitos(valor);
  if (d.length !== 20) return null;
  return {
    sequencial: d.slice(0, 7),
    verificador: d.slice(7, 9),
    ano: d.slice(9, 13),
    segmento: d.slice(13, 14),
    tribunal: d.slice(14, 16),
    origem: d.slice(16, 20),
  };
}

/**
 * Dígito verificador por ISO 7064 MOD 97-10, como manda a Res. CNJ 65/2008:
 * monta o número sem o verificador, acrescenta "00" e calcula 98 - (n mod 97).
 *
 * BigInt é obrigatório aqui: o número tem 20 dígitos e estoura o inteiro
 * seguro do JavaScript (2^53). Com `Number` o resultado sairia errado em
 * parte dos casos — errado de um jeito que passaria em teste superficial.
 */
export function calcularVerificador(p: Omit<NumeroProcesso, "verificador">): string {
  const base = `${p.sequencial}${p.ano}${p.segmento}${p.tribunal}${p.origem}00`;
  const resto = BigInt(base) % 97n;
  return String(98n - resto).padStart(2, "0");
}

/** Devolve a lista de problemas. Vazia = número íntegro. */
export function conferirProcesso(
  valor: string,
  opcoes: { exigirTrf1?: boolean } = {},
): string[] {
  const d = soDigitos(valor);
  if (!d) return ["informe o número do processo"];
  if (d.length !== 20) {
    return [
      `o número tem 20 dígitos (você digitou ${d.length}). ` +
        "Formato: NNNNNNN-DD.AAAA.J.TR.OOOO",
    ];
  }
  const p = decompor(d)!;
  const problemas: string[] = [];
  if (p.verificador !== calcularVerificador(p)) {
    problemas.push("este número parece ter um erro de digitação, confira");
  }
  const ano = Number(p.ano);
  const anoAtual = new Date().getFullYear();
  if (ano < 1960 || ano > anoAtual + 1) {
    problemas.push(`o ano ${p.ano} não parece certo`);
  }
  if (opcoes.exigirTrf1) {
    if (p.segmento !== "4") {
      const nome = SEGMENTOS[p.segmento] ?? "segmento desconhecido";
      problemas.push(
        `este número é da ${nome}, não da Justiça Federal. ` +
          "Confira se é o processo certo",
      );
    } else if (p.tribunal !== "01") {
      problemas.push(
        `este processo é do TRF${Number(p.tribunal)}, não do TRF1. ` +
          "Confira se é o processo certo",
      );
    }
  }
  return problemas;
}

export function formatarProcesso(valor: string): string {
  const d = soDigitos(valor).slice(0, 20);
  const p = [
    d.slice(0, 7),
    d.slice(7, 9),
    d.slice(9, 13),
    d.slice(13, 14),
    d.slice(14, 16),
    d.slice(16, 20),
  ];
  let fora = p[0]!;
  if (p[1]) fora += `-${p[1]}`;
  if (p[2]) fora += `.${p[2]}`;
  if (p[3]) fora += `.${p[3]}`;
  if (p[4]) fora += `.${p[4]}`;
  if (p[5]) fora += `.${p[5]}`;
  return fora;
}
