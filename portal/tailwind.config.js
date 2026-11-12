/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // As cores saem de variáveis CSS, definidas em `estilos.css`. Isso é o
      // que permite ter modo escuro mudando um lugar só, em vez de pôr
      // `dark:` em cada um dos dez componentes — e em vez de esquecer num
      // deles, que é o que acontece.
      //
      // NÃO é a identidade visual do Sindifisco nem de escritório. Quando
      // houver marca definida, troca-se aqui.
      colors: {
        tinta: "rgb(var(--tinta) / <alpha-value>)",
        papel: "rgb(var(--papel) / <alpha-value>)",
        carta: "rgb(var(--carta) / <alpha-value>)",
        borda: "rgb(var(--borda) / <alpha-value>)",
        acento: "rgb(var(--acento) / <alpha-value>)",
        alerta: "rgb(var(--alerta) / <alpha-value>)",
        bom: "rgb(var(--bom) / <alpha-value>)",
        lilas: "rgb(var(--lilas) / <alpha-value>)",
        ceu: "rgb(var(--ceu) / <alpha-value>)",
        ambar: "rgb(var(--ambar) / <alpha-value>)",
        // FIXAS: o fundo dos cartões de número, sempre com texto branco.
        roxo: { DEFAULT: "#5E35B1", fundo: "#4527A0" },
        azul: { DEFAULT: "#1E88E5", fundo: "#1565C0" },
      },
      fontFamily: {
        // Servida pelo próprio portal (`@fontsource`), nunca de um CDN: uma
        // fonte pedida a terceiro contaria a ele quem abriu o portal de qual
        // sindicato — e filiação sindical é dado sensível.
        sans: ["Roboto", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        cartao: "0 1px 2px rgb(18 25 38 / 0.04), 0 1px 12px rgb(18 25 38 / 0.04)",
      },
    },
  },
};
