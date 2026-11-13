/**
 * Em demonstração: com que CPF entrar, dito na própria tela.
 *
 * Visto na primeira demonstração hospedada: a tela pedia um CPF e quem
 * abria o link não tinha como saber qual. A lista vem do servidor, que só a
 * manda em modo de demonstração (`lib/demonstracao.ts`).
 */
import { useState } from "react";

import type { AcessoDaDemo } from "../lib/demonstracao";
import { enderecoDaArea } from "../lib/entrada";

export function AcessosDaDemo({
  acessos,
  apelido,
}: {
  acessos: AcessoDaDemo[];
  apelido: string;
}) {
  const [copiado, setCopiado] = useState("");
  if (!acessos.length) return null;

  async function copiar(cpf: string) {
    try {
      await navigator.clipboard.writeText(cpf);
      setCopiado(cpf);
    } catch {
      // Sem permissão de área de transferência: o CPF está escrito ao lado,
      // e dá para digitar.
      setCopiado("");
    }
  }

  return (
    <div className="mt-3 border-t border-alerta/20 pt-3 text-tinta">
      <p className="font-semibold">Para entrar, use um destes CPFs de exemplo:</p>
      <ul className="mt-2 space-y-2">
        {acessos.map((a) => (
          <li key={a.cpf} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <code className="rounded bg-white px-2 py-1 text-base font-semibold">
              {a.cpf}
            </code>
            <button
              type="button"
              onClick={() => void copiar(a.cpf)}
              className="rounded border border-tinta/20 bg-white px-2 py-1 text-sm underline-offset-2 hover:underline"
            >
              {copiado === a.cpf ? "Copiado" : "Copiar"}
            </button>
            <span>
              {a.quem}
              {" — "}
              <a className="underline" href={enderecoDaArea(a.area, apelido)}>
                {a.gestor ? "abre o Painel do sindicato" : "abre a área do filiado"}
              </a>
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm">
        Depois de digitar o CPF e pedir o código, ele aparece na própria tela.
        Todos os cadastros aqui são fictícios.
      </p>
    </div>
  );
}
