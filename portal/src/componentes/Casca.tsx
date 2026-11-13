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
  CircleUserRound,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  MessagesSquare,
  Scale,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import type { Tela } from "../lib/envio";
import { cliqueQueNavega } from "../lib/sessao";
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
  onIr,
  children,
}: {
  href: string;
  atual: boolean;
  icone: ReactNode;
  /** Troca de área SEM recarregar a página. Ausente, o link é só um link. */
  onIr?: () => void;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      aria-current={atual ? "page" : undefined}
      onClick={(e) => {
        // O `href` continua aí: é ele que abre em outra aba, e a aba nova
        // começa sem sessão. O clique simples fica na página — recarregar
        // jogava fora a sessão, e cada área pedia um código novo.
        if (onIr && cliqueQueNavega(e)) {
          e.preventDefault();
          onIr();
        }
      }}
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
  onIr,
  temSessao,
  onSair,
  onPrivacidade,
  children,
}: {
  entidade?: string;
  tela: Tela;
  comServidor: boolean;
  /** O endereço de cada área, já com o sindicato do link. */
  link: (tela: Tela) => string;
  /** Troca de área por dentro da página, levando a sessão junto. */
  onIr: (tela: Tela) => void;
  /** Há alguém dentro? É o que faz o "Sair" aparecer. */
  temSessao: boolean;
  onSair: () => void;
  onPrivacidade: () => void;
  children: ReactNode;
}) {
  const [aberta, setAberta] = useState(false);
  const ir = (qual: Tela) => () => {
    setAberta(false);
    onIr(qual);
  };
  const classeDoIcone = "h-5 w-5 shrink-0";
  const menu = (
    <nav aria-label="Áreas do portal" className="px-3">
      <Grupo titulo="Filiado">
        {comServidor ? (
          <Item href={link("area")} atual={tela === "area"} onIr={ir("area")} icone={<CircleUserRound className={classeDoIcone} aria-hidden="true" />}>
            Minha área
          </Item>
        ) : null}
        <Item href={link("cadastro")} atual={tela === "cadastro"} onIr={ir("cadastro")} icone={<UserRound className={classeDoIcone} aria-hidden="true" />}>
          Meu cadastro
        </Item>
        {comServidor ? (
          <>
            <Item href={link("acoes")} atual={tela === "acoes"} onIr={ir("acoes")} icone={<ListChecks className={classeDoIcone} aria-hidden="true" />}>
              Minhas ações
            </Item>
            <Item href={link("processos")} atual={tela === "processos"} onIr={ir("processos")} icone={<Gavel className={classeDoIcone} aria-hidden="true" />}>
              Meus processos
            </Item>
            <Item href={link("atendimento")} atual={tela === "atendimento"} onIr={ir("atendimento")} icone={<MessagesSquare className={classeDoIcone} aria-hidden="true" />}>
              Pergunte ao Proto
            </Item>
          </>
        ) : null}
      </Grupo>
      {comServidor ? (
        <Grupo titulo="Sindicato">
          <Item href={link("painel")} atual={tela === "painel"} onIr={ir("painel")} icone={<LayoutDashboard className={classeDoIcone} aria-hidden="true" />}>
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
          {/* SÓ O NOME DO SINDICATO. O rótulo "Protótipo — não é o portal
              oficial" saiu daqui em 12/11/2026, por decisão do dono do
              produto. O que protege quem abre um servidor de teste continua
              existindo e é outra coisa: a faixa de DEMONSTRAÇÃO, que o
              servidor manda só para sindicato de demonstração. */}
          <div className="min-w-0 flex-1 text-right lg:text-left">
            <p className="truncate text-lg font-semibold text-tinta">
              {entidade ?? "Seus direitos, organizados"}
            </p>
          </div>
          {/* SAIR, SEMPRE À VISTA enquanto há alguém dentro. A sessão agora
              vale em todas as áreas, e no computador da sede quem levanta
              da cadeira precisa de um jeito de fechar a porta. */}
          {temSessao ? (
            <button
              type="button"
              onClick={onSair}
              className="flex h-10 shrink-0 items-center gap-2 rounded-lg border border-borda bg-carta px-3 text-[15px] font-medium text-tinta hover:bg-papel"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Sair
            </button>
          ) : null}
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
