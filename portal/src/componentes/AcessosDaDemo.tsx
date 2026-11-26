/**
 * Em demonstração: ENTRAR COMO cada um dos perfis, com um toque.
 *
 * A primeira versão listava CPFs para copiar e colar, e o código aparecia na
 * tela para digitar: quem assistia via um formulário de teste, não um
 * aplicativo. Agora cada perfil é um botão — "Entrar como o sindicato",
 * "como o escritório", "como o filiado" — e cada um cai na PRÓPRIA área,
 * que é o que o portal de verdade faz.
 *
 * O que o botão faz é o que a pessoa faria à mão: pede o código para aquele
 * CPF fictício e o confere. Só existe em modo de demonstração — a lista de
 * acessos vem do servidor (`lib/demonstracao.ts`), e no portal de verdade o
 * código vai para o e-mail e não volta na resposta.
 */
import { Briefcase, LayoutDashboard, UserRound } from "lucide-react";
import { useState } from "react";

import type { AcessoDaDemo } from "../lib/demonstracao";
import * as api from "../lib/envio";

export function AcessosDaDemo({
  acessos,
  apelido,
  onEntrar,
}: {
  acessos: AcessoDaDemo[];
  apelido: string;
  onEntrar: (token: string, cpf: string, tela: api.Tela) => void;
}) {
  const [indo, setIndo] = useState("");
  const [erro, setErro] = useState("");
  if (!acessos.length) return null;

  async function entrar(a: AcessoDaDemo) {
    setIndo(a.cpf);
    setErro("");
    try {
      const pedido = await api.pedirCodigo(apelido, a.cpf);
      if (!pedido.codigoDoEnsaio) {
        throw new Error("esta página não está em modo de demonstração");
      }
      const { token } = await api.conferirCodigo(apelido, a.cpf, pedido.codigoDoEnsaio);
      onEntrar(token, a.cpf, a.gestor ? "painel" : a.area === "escritorio" ? "escritorio" : "area");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível entrar");
    } finally {
      setIndo("");
    }
  }

  const icone = (a: AcessoDaDemo) =>
    a.gestor ? (
      <LayoutDashboard className="h-5 w-5" aria-hidden="true" />
    ) : a.area === "escritorio" ? (
      <Briefcase className="h-5 w-5" aria-hidden="true" />
    ) : (
      <UserRound className="h-5 w-5" aria-hidden="true" />
    );
  const onde = (a: AcessoDaDemo) =>
    a.gestor ? "Painel do sindicato" : a.area === "escritorio" ? "Painel do escritório" : "Área do filiado";

  return (
    <div className="mt-3 border-t border-tinta/15 pt-3 text-tinta">
      <p className="font-semibold">Entre na demonstração como:</p>
      <ul className="mt-2 grid gap-2 sm:grid-cols-2">
        {acessos.map((a) => (
          <li key={a.cpf}>
            <button
              type="button"
              disabled={Boolean(indo)}
              onClick={() => void entrar(a)}
              className="flex w-full items-center gap-3 rounded-lg bg-carta px-4 py-3 text-left shadow-cartao hover:bg-carta/70 disabled:opacity-60"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-acento text-carta">
                {icone(a)}
              </span>
              <span className="min-w-0">
                <span className="block text-[16px] font-semibold text-tinta">
                  {indo === a.cpf ? "Entrando…" : a.quem}
                </span>
                <span className="block text-sm text-tinta/65">
                  {onde(a)} · CPF de exemplo {a.cpf}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {erro ? <p className="mt-2 text-sm text-alerta">{erro}</p> : null}
      <p className="mt-2 text-sm">
        No portal de verdade cada pessoa entra com o próprio CPF e um código
        que chega no e-mail cadastrado pelo sindicato. Aqui tudo é fictício.
      </p>
    </div>
  );
}
