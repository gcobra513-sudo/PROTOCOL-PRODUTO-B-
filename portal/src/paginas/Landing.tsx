/**
 * A PÁGINA DE ENTRADA do webapp: o que aparece para quem chega sem o link
 * de um sindicato.
 *
 * Ela faz duas coisas. Diz o que o produto é, para a diretoria que ouviu
 * falar; e leva para dentro quem já é de um sindicato atendido — pelo código
 * que o sindicato passou, ou colando o link inteiro. Não há lista de
 * sindicatos para escolher, de propósito (`lib/entrada.ts`).
 *
 * NENHUM BOTÃO AQUI É ENFEITE. Cada um leva a algum lugar que existe; o da
 * demonstração só aparece se o servidor tiver mesmo um sindicato de
 * demonstração para mostrar.
 */
import {
  ArrowRight,
  FileSpreadsheet,
  LayoutDashboard,
  ListChecks,
  MessagesSquare,
  ShieldCheck,
  Smartphone,
  UserCheck,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Marca } from "../componentes/Casca";
import { Aviso, Botao, Campo } from "../componentes/ui";
import { codigoDoSindicato, enderecoDaArea } from "../lib/entrada";
import * as api from "../lib/envio";

const DEMONSTRACAO = "demo-sindicato";

function Passo({ icone, titulo, children }: { icone: ReactNode; titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-xl bg-carta p-6 shadow-cartao">
      <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-lilas text-acento">
        {icone}
      </span>
      <h3 className="mt-4 text-lg font-semibold text-tinta">{titulo}</h3>
      <p className="mt-2 text-[15px] leading-relaxed text-tinta/70">{children}</p>
    </div>
  );
}

export function Landing({ onPrivacidade }: { onPrivacidade: () => void }) {
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState("");
  const [indo, setIndo] = useState(false);
  const [temDemonstracao, setTemDemonstracao] = useState(false);
  const comServidor = api.servidorLigado();

  useEffect(() => {
    if (!comServidor) return;
    void api.verEntidade(DEMONSTRACAO).then((e) => setTemDemonstracao(Boolean(e)));
  }, [comServidor]);

  async function entrar(tela: api.Tela) {
    setErro("");
    const codigo = codigoDoSindicato(texto);
    if (!codigo) {
      setErro(
        "Digite o código que o seu sindicato passou, ou cole o link que ele enviou.",
      );
      return;
    }
    if (!comServidor) {
      window.location.assign(enderecoDaArea("cadastro", codigo));
      return;
    }
    setIndo(true);
    try {
      // CONFERE COM O SERVIDOR antes de sair da página: mandar a pessoa para
      // um portal que não existe é o tipo de erro que ela não sabe consertar.
      const existe = await api.verEntidade(codigo);
      if (!existe) {
        setErro(
          "Não encontramos um sindicato com esse código. Confira com o seu sindicato o link do portal.",
        );
        return;
      }
      window.location.assign(enderecoDaArea(tela, codigo));
    } finally {
      setIndo(false);
    }
  }

  return (
    <div className="min-h-screen bg-papel">
      <header className="bg-carta">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Marca />
          <nav aria-label="Nesta página" className="hidden gap-6 text-[15px] text-tinta/75 md:flex">
            <a href="#como-funciona" className="hover:text-acento">Como funciona</a>
            <a href="#sindicato" className="hover:text-acento">Para o sindicato</a>
            <a href="#filiado" className="hover:text-acento">Para o filiado</a>
          </nav>
          <a
            href="#acesso"
            className="inline-flex h-10 items-center rounded-lg bg-acento px-4 text-[15px] font-medium text-carta shadow-sm hover:bg-acento/90"
          >
            Acessar
          </a>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-6xl px-4 pt-6 sm:px-6 sm:pt-10">
          <div className="relative overflow-hidden rounded-2xl bg-roxo px-6 py-12 text-white sm:px-12 sm:py-16">
            <span aria-hidden="true" className="absolute -right-16 -top-24 h-80 w-80 rounded-full bg-roxo-fundo opacity-60" />
            <span aria-hidden="true" className="absolute -right-40 top-10 h-80 w-80 rounded-full bg-roxo-fundo opacity-40" />
            <div className="relative max-w-2xl">
              <p className="text-sm font-semibold uppercase tracking-widest text-white/80">
                Para sindicatos e cooperativas
              </p>
              <h1 className="mt-4 text-4xl font-bold leading-tight sm:text-5xl">
                A ação foi ganha. Quem foi buscar?
              </h1>
              <p className="mt-5 text-lg leading-relaxed text-white/85">
                O sindicato manda a lista de filiados. O filiado manda os
                documentos. Nós dizemos, nome por nome, o que cada um pode
                fazer com o que já foi decidido.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <a
                  href="#acesso"
                  className="inline-flex h-12 items-center gap-2 rounded-lg bg-white px-5 text-[15px] font-semibold text-roxo hover:bg-white/90"
                >
                  Acessar o portal <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </a>
                {temDemonstracao ? (
                  <a
                    href={enderecoDaArea("cadastro", DEMONSTRACAO)}
                    className="inline-flex h-12 items-center rounded-lg border border-white/50 px-5 text-[15px] font-semibold text-white hover:bg-white/10"
                  >
                    Ver a demonstração
                  </a>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <section id="como-funciona" className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <h2 className="text-2xl font-bold text-tinta">Como funciona</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <Passo icone={<FileSpreadsheet className="h-5 w-5" aria-hidden="true" />} titulo="1. A lista">
              O sindicato envia a planilha de filiados que já tem, em Excel,
              do jeito que está. No mesmo dia sabe com quem não consegue
              falar, e por quê.
            </Passo>
            <Passo icone={<Smartphone className="h-5 w-5" aria-hidden="true" />} titulo="2. Os documentos">
              O filiado entra sem senha, com um código no e-mail que o
              sindicato tem em cadastro, e envia pelo celular. Foto do papel
              serve.
            </Passo>
            <Passo icone={<UserCheck className="h-5 w-5" aria-hidden="true" />} titulo="3. A resposta">
              Para cada pessoa: de quais ações faz parte, o que pode ser
              feito em cada uma, o que falta — e de quem é a vez.
            </Passo>
          </div>
        </section>

        <section className="mx-auto grid max-w-6xl gap-4 px-4 pb-12 sm:px-6 md:grid-cols-2">
          <div id="sindicato" className="rounded-xl bg-carta p-7 shadow-cartao">
            <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-ceu text-azul-fundo">
              <LayoutDashboard className="h-5 w-5" aria-hidden="true" />
            </span>
            <h2 className="mt-4 text-xl font-bold text-tinta">Para o sindicato</h2>
            <ul className="mt-4 space-y-3 text-[15px] leading-relaxed text-tinta/75">
              <li>O retrato da base: quem falta, o que falta, e o que resolver primeiro.</li>
              <li>Nome por nome: o que cada filiado já pode e de quem depende o resto.</li>
              <li>Um sindicato nunca vê o dado de outro, e os dados ficam no Brasil.</li>
            </ul>
          </div>
          <div id="filiado" className="rounded-xl bg-carta p-7 shadow-cartao">
            <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-lilas text-acento">
              <MessagesSquare className="h-5 w-5" aria-hidden="true" />
            </span>
            <h2 className="mt-4 text-xl font-bold text-tinta">Para o filiado</h2>
            <ul className="mt-4 space-y-3 text-[15px] leading-relaxed text-tinta/75">
              <li>Em quais processos está, e se alguma coisa andou.</li>
              <li>Se os documentos chegaram, e o que ainda falta.</li>
              <li>Um atendimento que responde na hora, sem ligar para a sede.</li>
            </ul>
          </div>
        </section>

        <section id="acesso" className="mx-auto max-w-6xl px-4 pb-14 sm:px-6">
          <div className="rounded-2xl bg-carta p-7 shadow-cartao sm:p-10">
            <div className="grid gap-8 md:grid-cols-2 md:items-start">
              <div>
                <h2 className="text-2xl font-bold text-tinta">Acessar o portal</h2>
                <p className="mt-3 text-[15px] leading-relaxed text-tinta/70">
                  Cada sindicato tem o seu portal. Digite o código que o seu
                  sindicato passou, ou cole o link que ele enviou.
                </p>
                <ul className="mt-5 space-y-2 text-[15px] text-tinta/75">
                  <li className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-bom" aria-hidden="true" />
                    Sem senha: o código chega no e-mail do cadastro.
                  </li>
                  <li className="flex items-center gap-2">
                    <ListChecks className="h-4 w-4 text-bom" aria-hidden="true" />
                    Nunca pedimos senha nem certificado a ninguém.
                  </li>
                </ul>
              </div>
              <div className="space-y-4">
                <Campo
                  rotulo="Código ou link do seu sindicato"
                  valor={texto}
                  onChange={(v) => {
                    setTexto(v);
                    setErro("");
                  }}
                  placeholder="Ex.: sind-df"
                  autoComplete="off"
                />
                {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}
                {!comServidor ? (
                  <Aviso tom="neutro">
                    Esta página está sem servidor: dá para ver como o cadastro
                    funciona, mas nada é consultado nem enviado.
                  </Aviso>
                ) : null}
                <div className="flex flex-wrap gap-3">
                  <Botao disabled={indo} onClick={() => void entrar("area")}>
                    Sou filiado
                  </Botao>
                  <Botao tipo="secundario" disabled={indo} onClick={() => void entrar("painel")}>
                    Sou do sindicato
                  </Botao>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-carta">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm text-tinta/65 sm:px-6">
          <span>PROTOCOL — para sindicatos e cooperativas.</span>
          <button type="button" onClick={onPrivacidade} className="text-acento underline">
            Como tratamos os seus dados
          </button>
        </div>
      </footer>
    </div>
  );
}
