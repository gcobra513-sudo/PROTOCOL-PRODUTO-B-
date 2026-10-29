/**
 * Indicador de progresso. Os passos já concluídos são clicáveis para VOLTAR;
 * nunca para pular adiante.
 *
 * Deixar pular adiante parece gentileza e não é: a etapa 6 precisa do CPF
 * validado na 3 para procurar o CPF dentro do documento. Pular criaria um
 * estado em que o portal não sabe o que fazer, e o lugar de descobrir isso
 * não é com o filiado na tela.
 */
import { Check } from "lucide-react";

import { cn } from "./ui";

export function Progresso({
  etapas,
  atual,
  onVoltarPara,
}: {
  etapas: string[];
  atual: number;
  onVoltarPara: (i: number) => void;
}) {
  return (
    <nav aria-label="Progresso do cadastro">
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-2">
        {etapas.map((nome, i) => {
          const concluida = i < atual;
          const ehAtual = i === atual;
          const Marcador = (
            <span
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                "text-xs font-semibold",
                concluida && "bg-bom text-carta",
                ehAtual && "bg-acento text-carta",
                !concluida && !ehAtual && "bg-borda text-tinta/50",
              )}
            >
              {concluida ? (
                <Check className="h-4 w-4" aria-hidden="true" />
              ) : (
                i + 1
              )}
            </span>
          );
          const rotulo = (
            <span
              className={cn(
                "hidden text-sm sm:inline",
                ehAtual ? "font-medium text-tinta" : "text-tinta/60",
              )}
            >
              {nome}
            </span>
          );
          return (
            <li key={nome} className="flex items-center gap-1.5">
              {concluida ? (
                <button
                  type="button"
                  onClick={() => onVoltarPara(i)}
                  // `aria-label` em vez de rótulo visível + texto oculto: a
                  // primeira versão juntava os dois e o leitor de tela
                  // anunciava "Entrar Voltar para a etapa 1", que é confuso.
                  // Com aria-label o nome acessível é uma frase só.
                  aria-label={`Voltar para a etapa ${i + 1}: ${nome}`}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-1 py-0.5",
                    "hover:bg-papel focus-visible:outline focus-visible:outline-2",
                    "focus-visible:outline-acento",
                  )}
                >
                  {Marcador}
                  {rotulo}
                </button>
              ) : (
                <span
                  className="flex items-center gap-1.5 px-1 py-0.5"
                  aria-current={ehAtual ? "step" : undefined}
                >
                  {Marcador}
                  {rotulo}
                </span>
              )}
              {i < etapas.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "h-px w-3 sm:w-5",
                    i < atual ? "bg-bom" : "bg-borda",
                  )}
                />
              ) : null}
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-sm text-tinta/60 sm:hidden">
        Etapa {atual + 1} de {etapas.length}: {etapas[atual]}
      </p>
    </nav>
  );
}
