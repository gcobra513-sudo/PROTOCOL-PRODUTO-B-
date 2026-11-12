/**
 * A CASCA DO APLICATIVO: barra lateral, barra de cima, e o conteúdo num
 * painel claro. É a moldura de tudo o que fica "dentro" — o cadastro, as
 * áreas do filiado e o painel do sindicato. A página de entrada tem a dela.
 *
 * No celular a barra lateral vira gaveta, aberta pelo botão de menu: é no
 * celular que o filiado está, e uma barra fixa comeria um terço da tela.
 */
import {
  Gavel,
  Home,
  LayoutDashboard,
  ListChecks,
  Menu,
  MessagesSquare,
  Scale,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import type { Tela } from "../lib/envio";
import { cn } from "./ui";

export function Marca({ clara = false }: { clara?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-lg",
          clara ? "bg-white/15 text-white" : "bg-roxo text-white",
        )}
      >
        <Scale className="h-5 w-5" />
      </span>
      <span
        className={cn(
          "text-lg font-bold tracking-wide",
          clara ? "text-white" : "text-tinta",
        )}
      >
        PROTOCOL
      </span>
    </span>
  );
}

function Item({
  href,
  atual,
  icone,
  children,
}: {
  href: string;
  atual: boolean;
  icone: ReactNode;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      aria-current={atual ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[15px]",
        atual
          ? "bg-lilas font-medium text-acento"
          : "text-tinta/75 hover:bg-lilas/60 hover:text-acento",
      )}
    >
      {icone}
      {children}
    </a>
  );
}

function Grupo({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="border-b border-borda py-4 last:border-b-0">
      <p className="px-3 pb-2 text-sm font-medium text-tinta">{titulo}</p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

export function Casca({
  entidade,
  tela,
  comServidor,
  link,
  onPrivacidade,
  children,
}: {
  entidade?: string;
  tela: Tela;
  comServidor: boolean;
  /** O endereço de cada área, já com o sindicato do link. */
  link: (tela: Tela) => string;
  onPrivacidade: () => void;
  children: ReactNode;
}) {
  const [aberta, setAberta] = useState(false);
  const classeDoIcone = "h-5 w-5 shrink-0";
  const menu = (
    <nav aria-label="Áreas do portal" className="px-3">
      <Grupo titulo="Filiado">
        <Item href={link("cadastro")} atual={tela === "cadastro"} icone={<UserRound className={classeDoIcone} aria-hidden="true" />}>
          Meu cadastro
        </Item>
        {comServidor ? (
          <>
            <Item href={link("acoes")} atual={tela === "acoes"} icone={<ListChecks className={classeDoIcone} aria-hidden="true" />}>
              Minhas ações
            </Item>
            <Item href={link("processos")} atual={tela === "processos"} icone={<Gavel className={classeDoIcone} aria-hidden="true" />}>
              Meus processos
            </Item>
            <Item href={link("atendimento")} atual={tela === "atendimento"} icone={<MessagesSquare className={classeDoIcone} aria-hidden="true" />}>
              Atendimento
            </Item>
          </>
        ) : null}
      </Grupo>
      {comServidor ? (
        <Grupo titulo="Sindicato">
          <Item href={link("painel")} atual={tela === "painel"} icone={<LayoutDashboard className={classeDoIcone} aria-hidden="true" />}>
            Painel do sindicato
          </Item>
        </Grupo>
      ) : null}
      <Grupo titulo="Sobre">
        <Item href="./" atual={false} icone={<Home className={classeDoIcone} aria-hidden="true" />}>
          Página inicial
        </Item>
        <button
          type="button"
          onClick={onPrivacidade}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[15px] text-tinta/75 hover:bg-lilas/60 hover:text-acento"
        >
          <ShieldCheck className={classeDoIcone} aria-hidden="true" />
          Como tratamos os seus dados
        </button>
      </Grupo>
    </nav>
  );

  return (
    <div className="min-h-screen bg-carta lg:flex">
      {/* A barra lateral, no computador. */}
      <aside className="hidden w-64 shrink-0 lg:block">
        <div className="sticky top-0 max-h-screen overflow-y-auto">
          <div className="px-6 py-5">
            <Marca />
          </div>
          {menu}
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="flex items-center gap-3 px-4 py-3 sm:px-6 lg:py-4">
          <button
            type="button"
            onClick={() => setAberta((v) => !v)}
            aria-expanded={aberta}
            aria-controls="gaveta-do-menu"
            aria-label={aberta ? "Fechar o menu" : "Abrir o menu"}
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-lilas text-acento lg:hidden"
          >
            {aberta ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
          </button>
          <span className="lg:hidden">
            <Marca />
          </span>
          <div className="ml-auto min-w-0 text-right lg:ml-0 lg:text-left">
            <p className="text-xs font-semibold uppercase tracking-wide text-alerta">
              Protótipo — não é o portal oficial
            </p>
            <p className="truncate text-lg font-semibold text-tinta">
              {entidade ?? "Seus direitos, organizados"}
            </p>
          </div>
        </header>

        {aberta ? (
          <div id="gaveta-do-menu" className="border-y border-borda bg-carta pb-2 lg:hidden">
            {menu}
          </div>
        ) : null}

        <main className="min-h-[calc(100vh-4.5rem)] bg-papel px-4 py-6 sm:px-6 sm:py-8 lg:mr-4 lg:rounded-t-xl">
          {children}
        </main>
      </div>
    </div>
  );
}
