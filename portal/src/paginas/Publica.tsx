/**
 * AS PÁGINAS DE APRESENTAÇÃO: uma para a diretoria do sindicato, uma para o
 * filiado — e a moldura (cabeçalho e rodapé) que elas dividem com a página
 * inicial.
 *
 * SEPARADAS porque são duas conversas. A diretoria quer saber o que passa a
 * enxergar da própria base; o filiado quer saber o que resolve sem ligar
 * para a sede. Numa página só, cada um lia metade que não era para ele.
 *
 * O TEXTO É O DA APRESENTAÇÃO AO SINDICATO, e não inventa nada além dela:
 * o que o produto faz, o que não faz, e nenhuma promessa de valor.
 */
import {
  ArrowRight,
  Camera,
  FileSpreadsheet,
  Gavel,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  MessagesSquare,
  PhoneOff,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { BotaoDeTema } from "../componentes/BotaoDeTema";
import { Marca } from "../componentes/Casca";
import { enderecoDaArea } from "../lib/entrada";
import * as api from "../lib/envio";

/** Para onde levam os botões "Acessar": a caixa de acesso da página inicial. */
export const ACESSO = "./#acesso";

export function Moldura({
  atual,
  onPrivacidade,
  children,
}: {
  /** Qual item do menu é a página em que se está. */
  atual: "" | "sindicato" | "filiado";
  onPrivacidade: () => void;
  children: ReactNode;
}) {
  const item = (href: string, rotulo: string, ativo: boolean) => (
    <a
      href={href}
      aria-current={ativo ? "page" : undefined}
      className={
        ativo ? "font-semibold text-acento" : "hover:text-acento"
      }
    >
      {rotulo}
    </a>
  );
  return (
    <div className="min-h-screen bg-papel">
      <header className="bg-carta">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-4 sm:px-6">
          <a href="./" aria-label="PROTOCOL — página inicial">
            <Marca />
          </a>
          {/* À VISTA TAMBÉM NO CELULAR: um menu que só existe em tela grande
              deixava as duas páginas sem porta para quem está no telefone. */}
          <nav
            aria-label="Páginas"
            className="order-3 flex w-full gap-5 text-[15px] text-tinta/75 md:order-none md:w-auto md:gap-6"
          >
            {item("./", "Início", atual === "")}
            {item("?pagina=sindicato", "Para o sindicato", atual === "sindicato")}
            {item("?pagina=filiado", "Para o filiado", atual === "filiado")}
          </nav>
          <a
            href={ACESSO}
            className="inline-flex h-10 items-center rounded-lg bg-acento px-4 text-[15px] font-medium text-carta shadow-sm hover:bg-acento/90"
          >
            Acessar
          </a>
        </div>
      </header>

      <main>{children}</main>

      <footer className="bg-carta">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm text-tinta/65 sm:px-6">
          <span>PROTOCOL — para sindicatos e cooperativas.</span>
          <span className="flex flex-wrap items-center gap-5">
            <BotaoDeTema className="inline-flex items-center gap-2 text-tinta/75 hover:text-acento" />
            <button type="button" onClick={onPrivacidade} className="text-acento underline">
              Como tratamos os seus dados
            </button>
          </span>
        </div>
      </footer>
    </div>
  );
}

export function Abertura({
  sobre,
  titulo,
  children,
  acoes,
}: {
  sobre: string;
  titulo: string;
  children: ReactNode;
  acoes?: ReactNode;
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 pt-6 sm:px-6 sm:pt-10">
      <div className="relative overflow-hidden rounded-2xl bg-roxo px-6 py-12 text-white sm:px-12 sm:py-16">
        <span aria-hidden="true" className="absolute -right-16 -top-24 h-80 w-80 rounded-full bg-roxo-fundo opacity-60" />
        <span aria-hidden="true" className="absolute -right-40 top-10 h-80 w-80 rounded-full bg-roxo-fundo opacity-40" />
        <div className="relative max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-white/80">
            {sobre}
          </p>
          <h1 className="mt-4 text-4xl font-bold leading-tight sm:text-5xl">{titulo}</h1>
          <p className="mt-5 text-lg leading-relaxed text-white/85">{children}</p>
          {acoes ? <div className="mt-8 flex flex-wrap gap-3">{acoes}</div> : null}
        </div>
      </div>
    </section>
  );
}

export function BotaoClaro({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      className="inline-flex h-12 items-center gap-2 rounded-lg bg-white px-5 text-[15px] font-semibold text-roxo hover:bg-white/90"
    >
      {children} <ArrowRight className="h-4 w-4" aria-hidden="true" />
    </a>
  );
}

export function Secao({
  titulo,
  subtitulo,
  children,
}: {
  titulo: string;
  subtitulo?: string;
  children: ReactNode;
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h2 className="text-2xl font-bold text-tinta">{titulo}</h2>
      {subtitulo ? (
        <p className="mt-2 max-w-3xl text-[17px] leading-relaxed text-tinta/70">{subtitulo}</p>
      ) : null}
      <div className="mt-6">{children}</div>
    </section>
  );
}

export function Quadro({
  icone,
  titulo,
  children,
}: {
  icone?: ReactNode;
  titulo: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl bg-carta p-6 shadow-cartao">
      {icone ? (
        <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-lilas text-acento">
          {icone}
        </span>
      ) : null}
      <h3 className="text-lg font-semibold text-tinta">{titulo}</h3>
      <p className="mt-2 text-[16px] leading-relaxed text-tinta/70">{children}</p>
    </div>
  );
}

const icone = "h-5 w-5";

/** O QUE NÓS NÃO FAZEMOS. Vai nas três páginas: é o que permite confiar no
 *  que a tela diz, e é a mesma lista para quem contrata e para quem usa. */
export function OQueNaoFazemos() {
  return (
    <Secao
      titulo="O que nós não fazemos"
      subtitulo="É por isso que dá para confiar no que a tela diz."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Quadro titulo="Não dizemos “pode” na dúvida">
          Quando falta informação, a resposta é “falta”: o que falta e de quem
          depende.
        </Quadro>
        <Quadro titulo="Não prometemos valor sem a conta">
          Sem a ficha financeira e o que a sentença fixou, não há número.
        </Quadro>
        <Quadro titulo="Nada sai sem a assinatura de um advogado">
          O sistema prepara. A decisão é de quem assina.
        </Quadro>
        <Quadro titulo="Não pedimos senha nem certificado">
          A ninguém: nem ao sindicato, nem ao filiado.
        </Quadro>
      </div>
    </Secao>
  );
}

/** O sindicato de demonstração, quando o servidor tem um. */
const DEMONSTRACAO = "demo-sindicato";

export function ParaOSindicato({ onPrivacidade }: { onPrivacidade: () => void }) {
  // O BOTÃO SÓ APARECE SE HOUVER O QUE MOSTRAR: num servidor de verdade não
  // há sindicato de demonstração, e um botão que leva a lugar nenhum é
  // enfeite.
  const [demonstracao, setDemonstracao] = useState("");
  useEffect(() => {
    if (!api.servidorLigado()) return;
    void api.verEntidade(DEMONSTRACAO).then((e) => {
      if (e) setDemonstracao(enderecoDaArea("painel", DEMONSTRACAO));
    });
  }, []);
  return (
    <Moldura atual="sindicato" onPrivacidade={onPrivacidade}>
      <Abertura
        sobre="Para a diretoria do sindicato"
        titulo="Do cadastro bagunçado a cada filiado com a sua resposta"
        acoes={
          <>
            <BotaoClaro href={ACESSO}>Acessar o portal</BotaoClaro>
            {demonstracao ? (
              <a
                href={demonstracao}
                className="inline-flex h-12 items-center rounded-lg border border-white/50 px-5 text-[15px] font-semibold text-white hover:bg-white/10"
              >
                Ver a demonstração
              </a>
            ) : null}
          </>
        }
      >
        O sindicato sabe, nome por nome, o que cada filiado pode fazer com o
        que já foi decidido.
      </Abertura>

      <Secao
        titulo="Três perguntas, sem abrir uma pasta"
        subtitulo="Se a resposta está em planilhas, em pastas e na memória de alguém, ela não está em lugar nenhum."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <Quadro titulo="1.">Quantos filiados têm hoje uma sentença pronta para cobrar?</Quadro>
          <Quadro titulo="2.">Com quantos deles o sindicato consegue falar?</Quadro>
          <Quadro titulo="3.">Quantos ligam toda semana só para saber do processo?</Quadro>
        </div>
      </Secao>

      <Secao
        titulo="O painel do sindicato"
        subtitulo="Ao abrir, a diretoria vê na hora:"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Quadro icone={<Users className={icone} aria-hidden="true" />} titulo="Quantos filiados estão na base">
            A planilha que o sindicato já tem, do jeito que está, vira um
            cadastro só.
          </Quadro>
          <Quadro icone={<PhoneOff className={icone} aria-hidden="true" />} titulo="Quantos estão sem contato, e por quê">
            E quem são: a lista de quem precisa ser procurado, com o motivo de
            cada um.
          </Quadro>
          <Quadro icone={<UserRound className={icone} aria-hidden="true" />} titulo="Quantos já entraram no portal">
            E quem ainda falta entrar, para o sindicato chamar.
          </Quadro>
          <Quadro icone={<FileSpreadsheet className={icone} aria-hidden="true" />} titulo="Quais documentos esperam leitura">
            Foto e cópia que a máquina não leu ficam numa fila, para uma
            pessoa do sindicato ler e registrar.
          </Quadro>
        </div>
      </Secao>

      <Secao
        titulo="O que resolver primeiro"
        subtitulo="Toda pendência tem dono. A fila começa pelo que destrava mais gente, e mostra quem precisa agir."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <Quadro titulo="Do filiado">Um documento que só ele tem.</Quadro>
          <Quadro titulo="Do sindicato">Uma conferência, uma lista.</Quadro>
          <Quadro titulo="Do tribunal">Um julgamento que não saiu.</Quadro>
        </div>
      </Secao>

      <Secao
        titulo="Nome por nome"
        subtitulo="“Como está o meu processo?” A pergunta que chegava por telefone agora tem resposta na tela, para cada filiado."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <Quadro icone={<ListChecks className={icone} aria-hidden="true" />} titulo="O que cada um já pode fazer">
            E de quem depende o resto.
          </Quadro>
          <Quadro icone={<LayoutDashboard className={icone} aria-hidden="true" />} titulo="Busca e filtro">
            Pelo nome, e por quem precisa agir.
          </Quadro>
          <Quadro icone={<FileSpreadsheet className={icone} aria-hidden="true" />} titulo="A lista inteira em planilha">
            Com os contatos que constam, para o sindicato ligar.
          </Quadro>
        </div>
      </Secao>

      <Secao titulo="O que o sindicato ganha">
        <div className="grid gap-4 md:grid-cols-2">
          <Quadro titulo="A base em ordem">
            Um cadastro só, com o que falta à mostra e o caminho para
            completar.
          </Quadro>
          <Quadro titulo="Menos telefone na sede">
            O filiado acompanha a própria situação e tira dúvidas com o Proto,
            o assistente do portal. A diretoria também pergunta a ele.
          </Quadro>
          <Quadro titulo="Resposta com prova">
            Cada informação lida de um documento mostra o trecho de onde saiu.
          </Quadro>
          <Quadro titulo="Os dados protegidos">
            Um sindicato não vê os dados de outro. Tudo fica armazenado no
            Brasil.
          </Quadro>
        </div>
      </Secao>

      <OQueNaoFazemos />

      <Secao titulo="Comece com uma planilha">
        <div className="grid gap-4 md:grid-cols-3">
          <Quadro titulo="1.">O sindicato envia a lista de filiados que já tem.</Quadro>
          <Quadro titulo="2.">Escolhe uma ação que já ganhou.</Quadro>
          <Quadro titulo="3.">Recebe o retrato da base, nome por nome.</Quadro>
        </div>
        <p className="mt-5 text-[17px] text-tinta/70">
          Para cada filiado: o que já pode fazer, o que falta e de quem depende.
        </p>
      </Secao>
    </Moldura>
  );
}

export function ParaOFiliado({ onPrivacidade }: { onPrivacidade: () => void }) {
  return (
    <Moldura atual="filiado" onPrivacidade={onPrivacidade}>
      <Abertura
        sobre="Para o filiado"
        titulo="Você resolve pelo celular"
        acoes={<BotaoClaro href={ACESSO}>Entrar no portal do meu sindicato</BotaoClaro>}
      >
        O que hoje você pergunta por telefone, respondido na hora: em quais
        processos está, o que mudou e o que falta.
      </Abertura>

      <Secao titulo="Como funciona para você">
        <div className="grid gap-4 md:grid-cols-3">
          <Quadro icone={<KeyRound className={icone} aria-hidden="true" />} titulo="Entra sem senha">
            Você digita o CPF e recebe um código no e-mail que o seu sindicato
            tem em cadastro. Nada para decorar.
          </Quadro>
          <Quadro icone={<Camera className={icone} aria-hidden="true" />} titulo="Manda os documentos por foto">
            Comprovante, sentença, certidão. Foto do papel serve.
          </Quadro>
          <Quadro icone={<Gavel className={icone} aria-hidden="true" />} titulo="Acompanha os seus processos">
            O que andou, e quando conferimos pela última vez.
          </Quadro>
        </div>
      </Secao>

      <Secao
        titulo="Conheça o Proto"
        subtitulo="O assistente do filiado no portal. Responde na hora, com o que está no seu cadastro."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl bg-carta p-6 shadow-cartao">
            <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-roxo text-white">
              <MessagesSquare className={icone} aria-hidden="true" />
            </span>
            <h3 className="text-lg font-semibold text-tinta">Pergunte ao Proto</h3>
            <ul className="mt-3 space-y-2">
              {[
                "Em quais processos eu estou?",
                "O que falta eu fazer?",
                "Meus documentos chegaram?",
                "Meus dados estão certos?",
              ].map((p) => (
                <li key={p} className="rounded-lg bg-lilas px-4 py-3 text-base font-medium text-acento">
                  {p}
                </li>
              ))}
            </ul>
          </div>
          <div className="space-y-4">
            <Quadro icone={<ShieldCheck className={icone} aria-hidden="true" />} titulo="Ele não dá parecer nem promete valor">
              Quando não sabe, diz o que falta e de quem depende.
            </Quadro>
            <Quadro titulo="Os seus dados não vão para inteligência artificial externa">
              O Proto responde com o que já está no seu cadastro, e a sua
              pergunta não fica guardada.
            </Quadro>
          </div>
        </div>
      </Secao>

      <Secao
        titulo="Como você chega"
        subtitulo="Cada sindicato tem o seu portal. Abre no navegador, no computador e no celular. Nada para instalar."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <Quadro titulo="1.">O seu sindicato envia o link do portal dele.</Quadro>
          <Quadro titulo="2.">O portal abre com o nome do seu sindicato no topo.</Quadro>
          <Quadro titulo="3.">Você entra e só vê o que é seu.</Quadro>
        </div>
      </Secao>

      <OQueNaoFazemos />
    </Moldura>
  );
}
