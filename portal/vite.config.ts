import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // Caminhos RELATIVOS nos assets. Com o padrão ("/"), o `index.html`
  // referencia /assets/... e o site só funciona servido na raiz de um
  // domínio. Relativo funciona em qualquer subpasta — e é o que permite
  // abrir a pasta `dist` em qualquer hospedagem, ou num link de revisão.
  base: "./",
  plugins: [react()],
  server: { port: 5173, host: "127.0.0.1" },
  // Sem variáveis de ambiente com segredo: este portal não guarda segredo
  // nenhum no navegador. Ver a nota sobre privacidade em ESPEC_PORTAL.md.
});
