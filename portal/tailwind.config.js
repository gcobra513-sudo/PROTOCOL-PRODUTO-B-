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
      },
    },
  },
};
