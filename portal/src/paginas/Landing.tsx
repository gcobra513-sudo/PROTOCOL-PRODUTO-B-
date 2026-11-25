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
  Check,
  ChevronDown,
  CircleHelp,
  FileSpreadsheet,
  LayoutDashboard,
  ListChecks,
  MailX,
  MessagesSquare,
  PhoneCall,
  ShieldCheck,
  Smartphone,
  UserCheck,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Aviso, Botao, Campo } from "../componentes/ui";
import { codigoDoSindicato, enderecoDaArea } from "../lib/entrada";
import * as api from "../lib/envio";
import retratoDaArea from "../retratos/area.jpg";
import retratoDosFiliados from "../retratos/filiados.jpg";
import retratoDoPainel from "../retratos/painel.jpg";
import retratoDoProto from "../retratos/proto.jpg";
import { DEMONSTRACAO, GUIA } from "./GuiaDaDemo";
import { Moldura, OQueNaoFazemos } from "./Publica";

/** As perguntas que uma diretoria faz na primeira conversa. Cada resposta
 *  repete uma regra do produto — nenhuma promete o que ele não faz. */
const PERGUNTAS: [string, string][] = [
  [
    "O que o sindicato precisa para começar?",
    "A planilha de filiados que já tem, do jeito que está. Não é preciso trocar de sistema nem arrumar a planilha antes.",
  ],
  [
    "O filiado precisa instalar aplicativo ou criar senha?",
    "Não. O portal abre no navegador do celular ou do computador. A entrada é com o CPF e um código que chega no e-mail que o sindicato tem em cadastro.",
  ],
  [
    "O portal decide quem tem direito?",
    "Não. Ele organiza os dados e mostra, para cada pessoa, o que está pronto e o que falta. Nada sai no nome de um filiado antes de um advogado conferir e assinar.",
  ],
  [
    "E quando falta informação sobre um filiado?",
    "O portal diz que falta, e o que falta. Ele nunca transforma dúvida em “pode”.",
  ],
  [
    "Onde ficam os dados dos filiados?",
    "No Brasil. Cada sindicato só enxerga os seus filiados, e os dados não são enviados a serviços de fora nem a modelos de inteligência artificial.",
  ],
  [
    "O Proto é uma inteligência artificial?",
    "Não. É um assistente automático que responde sobre uma lista fechada de assuntos, só com o que está no cadastro, e avisa quando não sabe.",
  ],
];

function Celular({ src, alt }: { src: string; alt: string }) {
  return (
    <span className="block w-[46%] max-w-[210px] overflow-hidden rounded-[1.4rem] border-4 border-tinta/80 bg-papel shadow-cartao">
      <img src={src} alt={alt} width={1082} height={2202} loading="lazy" className="block aspect-[9/16] w-full object-cover object-top" />
    </span>
  );
}

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
    void api.verEntidade(DEMONSTRACAO).then((e) => setTemDemonstracao(Boolean(e?.demonstracao)));
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
    <Moldura atual="" onPrivacidade={onPrivacidade}>
        {/* A ABERTURA DIZ O QUE É, em uma frase, e MOSTRA a tela. Antes ela
            abria com uma pergunta ("Quem foi buscar?") que só fazia sentido
            para quem já conhecia o problema; quem chegava sem contexto saía
            sem saber o que o produto era. A pergunta desceu um andar. */}
        <section className="mx-auto max-w-6xl px-4 pt-6 sm:px-6 sm:pt-10">
          <div className="relative overflow-hidden rounded-2xl bg-roxo px-6 py-10 text-white sm:px-12 sm:py-14">
            <span aria-hidden="true" className="absolute -right-16 -top-24 h-80 w-80 rounded-full bg-roxo-fundo opacity-60" />
            <span aria-hidden="true" className="absolute -right-40 top-10 h-80 w-80 rounded-full bg-roxo-fundo opacity-40" />
            <div className="relative grid items-center gap-10 lg:grid-cols-2">
              <div>
                <p className="text-sm font-semibold uppercase tracking-widest text-white/80">
                  Para sindicatos e cooperativas
                </p>
                <h1 className="mt-4 text-4xl font-bold leading-tight sm:text-5xl">
                  O portal que mostra a cada filiado onde ele está nas ações do
                  sindicato.
                </h1>
                <p className="mt-5 text-lg leading-relaxed text-white/85">
                  O sindicato envia a planilha de filiados que já tem. O
                  filiado envia os documentos pelo celular. O PROTOCOL
                  responde, nome por nome: de quais ações a pessoa faz parte,
                  o que já pode ser feito e o que ainda falta.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  {temDemonstracao ? (
                    <a
                      href={GUIA}
                      className="inline-flex h-12 items-center gap-2 rounded-lg bg-white px-5 text-[15px] font-semibold text-roxo hover:bg-white/90"
                    >
                      Ver a demonstração <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    </a>
                  ) : null}
                  <a
                    href="#acesso"
                    className={
                      temDemonstracao
                        ? "inline-flex h-12 items-center rounded-lg border border-white/50 px-5 text-[15px] font-semibold text-white hover:bg-white/10"
                        : "inline-flex h-12 items-center gap-2 rounded-lg bg-white px-5 text-[15px] font-semibold text-roxo hover:bg-white/90"
                    }
                  >
                    Acessar o portal
                  </a>
                </div>
                <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-[15px] text-white/85">
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" aria-hidden="true" />Começa com uma planilha</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" aria-hidden="true" />Sem senha para o filiado</li>
                  <li className="flex items-center gap-2"><Check className="h-4 w-4" aria-hidden="true" />Abre no celular</li>
                </ul>
              </div>
              <figure>
                <img
                  src={retratoDoPainel}
                  width={1800}
                  height={1140}
                  alt="O painel do sindicato: quantos filiados há na base, com quantos o sindicato não consegue falar, quantos se cadastraram e o que resolver primeiro."
                  className="w-full rounded-xl shadow-2xl ring-1 ring-white/20"
                />
                <figcaption className="mt-3 text-sm text-white/75">
                  Tela real do painel do sindicato, com cadastro fictício.
                </figcaption>
              </figure>
            </div>
          </div>
        </section>

        <section id="problema" className="mx-auto max-w-6xl px-4 pt-12 sm:px-6">
          <h2 className="text-3xl font-bold text-tinta">A ação foi ganha. Quem foi buscar?</h2>
          <p className="mt-3 max-w-3xl text-[17px] leading-relaxed text-tinta/70">
            O sindicato ganha a ação coletiva, mas cada filiado precisa
            aparecer, com os documentos certos, para receber a sua parte. É
            aí que o direito se perde.
          </p>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <Passo icone={<MailX className="h-5 w-5" aria-hidden="true" />} titulo="O cadastro não alcança todo mundo">
              E-mail antigo, telefone trocado, CPF digitado errado. O
              sindicato não sabe com quem não consegue falar até precisar.
            </Passo>
            <Passo icone={<CircleHelp className="h-5 w-5" aria-hidden="true" />} titulo="Ninguém sabe quem tem o quê">
              Quem faz parte de qual ação, quem já entregou documento, o que
              falta de cada um: a resposta está espalhada em planilhas e
              pastas.
            </Passo>
            <Passo icone={<PhoneCall className="h-5 w-5" aria-hidden="true" />} titulo="O telefone da sede não para">
              “Meu documento chegou?” “Em que pé está?” A mesma pergunta,
              respondida à mão, um filiado por vez.
            </Passo>
          </div>
        </section>

        <section id="como-funciona" className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <h2 className="text-2xl font-bold text-tinta">Como funciona, em três passos</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <Passo icone={<FileSpreadsheet className="h-5 w-5" aria-hidden="true" />} titulo="1. O sindicato envia a lista">
              A planilha de filiados que já existe, em Excel, do jeito que
              está. No mesmo dia o sindicato sabe com quem não consegue
              falar, e por quê.
            </Passo>
            <Passo icone={<Smartphone className="h-5 w-5" aria-hidden="true" />} titulo="2. O filiado envia os documentos">
              Entra sem senha, com um código que chega no e-mail que o
              sindicato tem em cadastro, e envia pelo celular. Foto do papel
              serve.
            </Passo>
            <Passo icone={<UserCheck className="h-5 w-5" aria-hidden="true" />} titulo="3. Cada um recebe a sua resposta">
              Para cada pessoa: de quais ações faz parte, o que pode ser
              feito em cada uma, o que falta — e de quem é a vez.
            </Passo>
          </div>
        </section>

        {/* O QUE CADA LADO VÊ, com a tela ao lado do texto: descrever uma
            tela convence menos do que mostrá-la. */}
        <section className="mx-auto max-w-6xl space-y-4 px-4 pb-12 sm:px-6">
          <h2 className="text-2xl font-bold text-tinta">O que cada um vê</h2>
          <div id="sindicato" className="grid items-center gap-8 rounded-xl bg-carta p-7 shadow-cartao md:grid-cols-2 sm:p-10">
            <div>
              <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-ceu text-azul-fundo">
                <LayoutDashboard className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-xl font-bold text-tinta">O sindicato vê a base inteira</h3>
              <ul className="mt-4 space-y-3 text-[16px] leading-relaxed text-tinta/75">
                <li>O retrato da base: quem falta, o que falta, e o que resolver primeiro.</li>
                <li>Nome por nome: o que cada filiado já pode e de quem depende o resto.</li>
                <li>A lista de filiados com os contatos, que sai em planilha.</li>
                <li>Um sindicato nunca vê o dado de outro, e os dados ficam no Brasil.</li>
              </ul>
              <a href="?pagina=sindicato" className="mt-5 inline-flex items-center gap-2 text-[16px] font-semibold text-acento underline">
                Ver como funciona para o sindicato <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
            <img
              src={retratoDosFiliados}
              width={1800}
              height={1140}
              loading="lazy"
              alt="A aba Filiados do painel: a lista nome por nome, com busca, filtros e o botão de baixar a planilha da base."
              className="w-full rounded-lg ring-1 ring-tinta/10"
            />
          </div>
          <div id="filiado" className="grid items-center gap-8 rounded-xl bg-carta p-7 shadow-cartao md:grid-cols-2 sm:p-10">
            <div className="flex justify-center gap-4 md:order-2">
              <Celular src={retratoDaArea} alt="A Minha área do filiado no celular: cadastro e documentos, ações e processos." />
              <Celular src={retratoDoProto} alt="O Proto respondendo, no celular, se os documentos do filiado chegaram." />
            </div>
            <div>
              <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-lilas text-acento">
                <MessagesSquare className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-xl font-bold text-tinta">O filiado vê só o que é dele</h3>
              <ul className="mt-4 space-y-3 text-[16px] leading-relaxed text-tinta/75">
                <li>Em quais processos está, e se alguma coisa andou.</li>
                <li>Se os documentos chegaram, e o que ainda falta.</li>
                <li>O Proto, um assistente que responde na hora, sem ligar para a sede.</li>
              </ul>
              <a href="?pagina=filiado" className="mt-5 inline-flex items-center gap-2 text-[16px] font-semibold text-acento underline">
                Ver como funciona para o filiado <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
          </div>
          <p className="text-sm text-tinta/60">
            As telas acima são reais, tiradas da demonstração. Todo cadastro que aparece nelas é fictício.
          </p>
        </section>

        <OQueNaoFazemos />

        <section id="perguntas" className="mx-auto max-w-6xl px-4 pb-12 sm:px-6">
          <h2 className="text-2xl font-bold text-tinta">Perguntas frequentes</h2>
          <div className="mt-6 space-y-3">
            {PERGUNTAS.map(([pergunta, resposta]) => (
              <details key={pergunta} className="group rounded-xl bg-carta p-5 shadow-cartao">
                <summary className="cursor-pointer list-none text-[17px] font-semibold text-tinta marker:hidden">
                  <span className="flex items-center justify-between gap-4">
                    {pergunta}
                    <ChevronDown className="h-5 w-5 shrink-0 text-acento transition-transform group-open:rotate-180" aria-hidden="true" />
                  </span>
                </summary>
                <p className="mt-3 text-[16px] leading-relaxed text-tinta/75">{resposta}</p>
              </details>
            ))}
          </div>
        </section>

        {temDemonstracao ? (
          <section className="mx-auto max-w-6xl px-4 pb-12 sm:px-6">
            <div className="flex flex-wrap items-center justify-between gap-5 rounded-2xl bg-roxo px-7 py-8 text-white sm:px-10">
              <div className="max-w-2xl">
                <h2 className="text-2xl font-bold">Veja funcionando antes de decidir</h2>
                <p className="mt-2 text-[16px] leading-relaxed text-white/85">
                  Um sindicato de demonstração, com filiados fictícios, para
                  abrir o painel e a área do filiado como eles são.
                </p>
              </div>
              <a
                href={GUIA}
                className="inline-flex h-12 items-center gap-2 rounded-lg bg-white px-5 text-[15px] font-semibold text-roxo hover:bg-white/90"
              >
                Abrir a demonstração <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
          </section>
        ) : null}

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
    </Moldura>
  );
}
