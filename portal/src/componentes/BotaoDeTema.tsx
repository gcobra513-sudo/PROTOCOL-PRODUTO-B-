/**
 * O botão de tela clara/escura. Diz PARA ONDE vai, e não onde está: "Tela
 * escura" quando a tela está clara. Um interruptor que mostra o estado atual
 * obriga a pessoa a adivinhar se clicar liga ou desliga.
 */
import { Moon, Sun } from "lucide-react";
import { useState } from "react";

import { alternarTema, temaAtual } from "../lib/tema";

export function BotaoDeTema({ className = "" }: { className?: string }) {
  const [tema, setTema] = useState(temaAtual);
  const Icone = tema === "escuro" ? Sun : Moon;
  return (
    <button type="button" onClick={() => setTema(alternarTema())} className={className}>
      <Icone className="h-5 w-5 shrink-0" aria-hidden="true" />
      {tema === "escuro" ? "Tela clara" : "Tela escura"}
    </button>
  );
}
