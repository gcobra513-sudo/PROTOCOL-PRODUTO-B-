import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import "./estilos.css";
import { aplicarTemaGuardado } from "./lib/tema";

// Antes do primeiro desenho: senão a tela pisca no tema errado.
aplicarTemaGuardado();

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
