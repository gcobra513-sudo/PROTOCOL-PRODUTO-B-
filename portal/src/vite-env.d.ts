/// <reference types="vite/client" />

/**
 * `?url` é sintaxe do Vite: devolve a URL do asset em vez do módulo. O
 * TypeScript não conhece esse sufixo, e sem esta declaração o `tsc` reprova
 * o import do worker do pdf.js.
 */
declare module "*?url" {
  const url: string;
  export default url;
}
