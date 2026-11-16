/**
 * TELA CLARA OU ESCURA, escolhida por quem usa.
 *
 * As cores do portal são variáveis (`estilos.css`), e sem escolha nenhuma ele
 * segue o que o aparelho pede. Aqui é a escolha: um botão que leva ao outro
 * tema, e a lembrança dela neste navegador. Não é dado de ninguém — é uma
 * palavra, "claro" ou "escuro".
 */
export type Tema = "claro" | "escuro";

const CHAVE = "protocol.tema";

/** O que a pessoa escolheu neste navegador, ou nulo. Só aceita os dois
 *  valores que este arquivo grava: o que vier diferente não vira atributo. */
export function temaGuardado(
  armazem: Pick<Storage, "getItem"> | undefined = globalThis.localStorage,
): Tema | null {
  try {
    const v = armazem?.getItem(CHAVE);
    return v === "claro" || v === "escuro" ? v : null;
  } catch {
    return null; // navegador com o armazenamento bloqueado: segue o aparelho
  }
}

/** O tema que está valendo: a escolha, ou o que o aparelho pede. */
export function temaEmUso(guardado: Tema | null, aparelhoEscuro: boolean): Tema {
  return guardado ?? (aparelhoEscuro ? "escuro" : "claro");
}

export function outroTema(atual: Tema): Tema {
  return atual === "escuro" ? "claro" : "escuro";
}

function aparelhoEscuro(): boolean {
  return Boolean(globalThis.matchMedia?.("(prefers-color-scheme: dark)").matches);
}

/** Põe a escolha guardada na página. Chamada antes do primeiro desenho. */
export function aplicarTemaGuardado(): void {
  const guardado = temaGuardado();
  if (guardado) document.documentElement.dataset.tema = guardado;
}

export function temaAtual(): Tema {
  return temaEmUso(temaGuardado(), aparelhoEscuro());
}

/** Troca para o outro tema, guarda, e devolve o que ficou valendo. */
export function alternarTema(): Tema {
  const novo = outroTema(temaAtual());
  document.documentElement.dataset.tema = novo;
  try {
    globalThis.localStorage?.setItem(CHAVE, novo);
  } catch {
    // Sem armazenamento, vale só nesta visita.
  }
  return novo;
}
