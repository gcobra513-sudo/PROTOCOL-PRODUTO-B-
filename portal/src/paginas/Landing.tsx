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
  Bot,
  Briefcase,
  Check,
  ChevronDown,
  CircleHelp,
  FileSpreadsheet,
  Landmark,
  LayoutDashboard,
  ListChecks,
  MailX,
  Megaphone,
  MessagesSquare,
  PhoneCall,
  Send,
  Sparkles,
  ShieldCheck,
  Smartphone,
  UserCheck,
  UserRound,
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
    "O nosso sindicato terceiriza o jurídico para escritórios. O portal serve?",
    "Serve, e é onde ele mais ajuda. O sindicato encaminha o filiado ao escritório que cuida da ação, o escritório recebe os documentos organizados e marca o que falta, e o filiado acompanha. O que hoje vai por e-mail e WhatsApp fica registrado num lugar só.",
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

const TONS = {
  lilas: "bg-lilas text-acento",
  rosa: "bg-alerta/10 text-alerta",
  ambar: "bg-ambar text-tinta",
  ceu: "bg-ceu text-azul",
} as const;

function Passo({
  icone,
  titulo,
  children,
  tom = "lilas",
}: {
  icone: ReactNode;
  titulo: string;
  children: ReactNode;
  tom?: keyof typeof TONS;
}) {
  return (
    <div className="rounded-xl bg-carta p-6 shadow-cartao transition hover:-translate-y-1 hover:shadow-lg">
      <span className={`flex h-12 w-12 items-center justify-center rounded-xl ${TONS[tom]}`}>
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
                  responde, nome por nome, o que falta — e leva cada caso,
                  organizado, ao escritório que o sindicato contratou.
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
                  alt="O painel do sindicato: quantos filiados há na base, com quantos o sindicato não consegue falar, quantos se cadastraram e quantos já podem."
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
            <Passo tom="rosa" icone={<MailX className="h-5 w-5" aria-hidden="true" />} titulo="O cadastro não alcança todo mundo">
              E-mail antigo, telefone trocado, CPF digitado errado. O
              sindicato não sabe com quem não consegue falar até precisar.
            </Passo>
            <Passo tom="ambar" icone={<CircleHelp className="h-5 w-5" aria-hidden="true" />} titulo="Ninguém sabe quem tem o quê">
              Quem faz parte de qual ação, quem já entregou documento, o que
              falta de cada um: a resposta está espalhada em planilhas e
              pastas.
            </Passo>
            <Passo tom="ceu" icone={<PhoneCall className="h-5 w-5" aria-hidden="true" />} titulo="O telefone da sede não para">
              “Meu documento chegou?” “Em que pé está?” A mesma pergunta,
              respondida à mão, um filiado por vez.
            </Passo>
          </div>
        </section>

        {/* UMA FAIXA DE COR, de lado a lado: a página era um branco só, do
            título ao rodapé, e o olho não tinha onde descansar. */}
        <section id="como-funciona" className="mt-12 bg-gradient-to-br from-lilas via-ceu/60 to-lilas py-14">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <h2 className="text-center text-3xl font-bold text-tinta">Como funciona, em três passos</h2>
            <div className="relative mt-10 grid gap-8 md:grid-cols-3">
              <span aria-hidden="true" className="absolute left-[16%] right-[16%] top-8 hidden border-t-4 border-dashed border-acento/30 md:block" />
              {[
                [<FileSpreadsheet key="i" className="h-7 w-7" aria-hidden="true" />, "O sindicato envia a lista",
                  "A planilha de filiados que já existe, em Excel, do jeito que está. No mesmo dia o sindicato sabe com quem não consegue falar, e por quê."],
                [<Smartphone key="i" className="h-7 w-7" aria-hidden="true" />, "O filiado envia os documentos",
                  "Entra sem senha, com um código que chega no e-mail que o sindicato tem em cadastro, e envia pelo celular. Foto do papel serve."],
                [<UserCheck key="i" className="h-7 w-7" aria-hidden="true" />, "Cada um recebe a sua resposta",
                  "Para cada pessoa: de quais ações faz parte, o que pode ser feito em cada uma, o que falta — e de quem é a vez."],
              ].map(([icone, titulo, texto], n) => (
                <div key={String(titulo)} className="relative text-center">
                  <span className="relative mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-roxo text-white shadow-lg ring-8 ring-carta/70">
                    {icone}
                    <span className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full bg-azul text-sm font-bold text-white">
                      {n + 1}
                    </span>
                  </span>
                  <h3 className="mt-5 text-xl font-semibold text-tinta">{titulo}</h3>
                  <p className="mx-auto mt-2 max-w-xs text-[15px] leading-relaxed text-tinta/75">{texto}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* O QUE CADA LADO VÊ, com a tela ao lado do texto: descrever uma
            tela convence menos do que mostrá-la. */}
        <section className="mx-auto max-w-6xl space-y-4 px-4 py-14 sm:px-6">
          <h2 className="text-3xl font-bold text-tinta">O que cada um vê</h2>
          <div id="sindicato" className="grid items-center gap-8 rounded-xl bg-carta p-7 shadow-cartao md:grid-cols-2 sm:p-10">
            <div>
              <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-ceu text-azul">
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
              alt="A aba Filiados do painel, com o filtro Já pode ligado: 4 pessoas de 42 na base, a busca por nome e o botão de baixar a planilha."
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

        {/* A PONTE COM O ESCRITÓRIO. Sindicato que terceiriza o jurídico não
            tem problema de cadastro: tem problema de PASSAGEM — o filiado
            encaminhado por e-mail, o documento por WhatsApp, e ninguém
            sabendo o que chegou. */}
        <section id="escritorio" className="relative overflow-hidden bg-gradient-to-br from-roxo-fundo via-roxo to-azul py-16 text-white">
          <span aria-hidden="true" className="absolute -left-24 top-10 h-72 w-72 rounded-full bg-white/5" />
          <span aria-hidden="true" className="absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-white/5" />
          <div className="relative mx-auto max-w-6xl px-4 sm:px-6">
            <p className="text-sm font-semibold uppercase tracking-widest text-white/75">
              Para quem terceiriza o jurídico
            </p>
            <h2 className="mt-2 text-3xl font-bold sm:text-4xl">
              Do sindicato ao escritório, sem e-mail solto.
            </h2>
            <p className="mt-3 max-w-3xl text-[17px] leading-relaxed text-white/85">
              O sindicato faz a triagem e encaminha. O escritório contratado
              recebe o caso organizado. O filiado acompanha. Tudo no portal
              do sindicato, com registro de quem enviou, quem recebeu e
              quando.
            </p>

            {/* O DESENHO DO CAMINHO: três paradas e as setas entre elas. É
                o que hoje corre por e-mail e WhatsApp. */}
            <div className="mt-10 grid items-stretch gap-4 md:grid-cols-[1fr_auto_1fr_auto_1fr]">
              {[
                [<Send key="i" className="h-7 w-7" aria-hidden="true" />, "O sindicato encaminha",
                  "Cada ação tem o escritório que cuida dela. Um botão envia a ele os filiados daquela ação, e fica registrado."],
                null,
                [<Briefcase key="i" className="h-7 w-7" aria-hidden="true" />, "O escritório recebe",
                  "Um painel só com os casos dele: nome, CPF, contato e os documentos de cada pessoa. Ele confirma o recebimento e diz qual documento falta."],
                null,
                [<UserCheck key="i" className="h-7 w-7" aria-hidden="true" />, "O filiado acompanha",
                  "Na área dele: com qual escritório o caso está, em que situação, e o que falta enviar. Sem ligar para a sede."],
              ].map((item, n) =>
                item === null ? (
                  <span key={n} aria-hidden="true" className="flex items-center justify-center text-white/60">
                    <ArrowRight className="h-8 w-8 rotate-90 md:rotate-0" />
                  </span>
                ) : (
                  <div key={n} className="rounded-2xl bg-white/10 p-6 ring-1 ring-white/15 backdrop-blur">
                    <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-roxo shadow-lg">
                      {item[0]}
                    </span>
                    <h3 className="mt-4 text-xl font-semibold">{item[1]}</h3>
                    <p className="mt-2 text-[15px] leading-relaxed text-white/85">{item[2]}</p>
                  </div>
                ),
              )}
            </div>

            <ul className="mt-8 grid gap-x-8 gap-y-3 text-[16px] text-white/90 md:grid-cols-2">
              {[
                "O escritório vê só quem foi encaminhado a ele.",
                "O sindicato vê, por escritório, o que foi recebido e o que está parado.",
                "Cada documento aberto fica registrado, com quem abriu.",
                "Um escritório que atende vários sindicatos vê todos num painel só, com um login.",
              ].map((t) => (
                <li key={t} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/20">
                    <Check className="h-4 w-4" aria-hidden="true" />
                  </span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* AS TESES. É o argumento para o escritório: ele não precisa
            garimpar a base quando um tribunal decide — o portal já cruzou. */}
        <section id="teses" className="bg-gradient-to-br from-ceu/70 via-lilas/60 to-ceu/70 py-16">
          <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 sm:px-6 md:grid-cols-2">
            <div aria-hidden="true" className="rounded-2xl border-2 border-bom/30 bg-carta p-6 shadow-cartao">
              <div className="flex items-start gap-4">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-bom text-white">
                  <Megaphone className="h-6 w-6" />
                </span>
                <div>
                  <p className="text-lg font-bold text-tinta">Bom dia. Há uma novidade nos tribunais.</p>
                  <p className="mt-2 rounded-lg bg-papel p-3 text-[15px] leading-relaxed text-tinta">
                    O tribunal julgou o Tema 9.001 ontem. No Sindicato de
                    Demonstração, 5 pessoas poderiam entrar com a ação e
                    outras 37 dependem de alguma conferência.
                  </p>
                  <p className="mt-2 text-sm text-tinta/65">
                    Exemplo com tema e sindicato fictícios, como aparece no painel do escritório.
                  </p>
                </div>
              </div>
            </div>
            <div>
              <span className="inline-flex items-center gap-2 rounded-full bg-carta px-4 py-1.5 text-sm font-semibold text-acento">
                <Landmark className="h-4 w-4" aria-hidden="true" /> Teses e tribunais
              </span>
              <h2 className="mt-4 text-3xl font-bold text-tinta sm:text-4xl">
                O tribunal decidiu. O portal já sabe quem é alcançado.
              </h2>
              <p className="mt-3 text-[17px] leading-relaxed text-tinta/75">
                Acompanhamos os temas dos tribunais e as ações coletivas da
                carreira de cada sindicato. Quando um tema é julgado, o
                portal cruza com a base inteira e avisa o escritório e a
                diretoria, no painel e por e-mail.
              </p>
              <ul className="mt-5 space-y-3 text-[16px] text-tinta/85">
                {[
                  "Quantas pessoas teriam o caminho aberto, e quantas ainda dependem de alguma conferência.",
                  "Os dados e os documentos de cada uma já organizados, prontos para o escritório redigir.",
                  "Nada muda para o filiado antes de um advogado conferir a tese.",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-bom text-white">
                      <Check className="h-4 w-4" aria-hidden="true" />
                    </span>
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* O PROTO, com o lugar dele: é o que a diretoria mais pergunta
            ("isso responde sozinho?"), e estava numa linha de uma lista. */}
        <section id="proto" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <div className="grid items-center gap-10 md:grid-cols-2">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full bg-lilas px-4 py-1.5 text-sm font-semibold text-acento">
                <Sparkles className="h-4 w-4" aria-hidden="true" /> Assistente do portal
              </span>
              <h2 className="mt-4 text-3xl font-bold text-tinta sm:text-4xl">
                Proto: quem responde antes de o telefone tocar.
              </h2>
              <p className="mt-3 text-[17px] leading-relaxed text-tinta/75">
                Um assistente que fica no topo de cada área e responde na
                hora, com o que está no cadastro. Ele atende os três lados.
              </p>
              <ul className="mt-6 space-y-4">
                {[
                  [<UserRound key="i" className="h-5 w-5" aria-hidden="true" />, "Ao filiado", "“Meus documentos chegaram?” “O que falta eu fazer?”"],
                  [<LayoutDashboard key="i" className="h-5 w-5" aria-hidden="true" />, "À diretoria", "“Com quantos eu não consigo falar?” “O que resolver primeiro?”"],
                  [<Briefcase key="i" className="h-5 w-5" aria-hidden="true" />, "Ao escritório", "“O que eu abro primeiro?” “De quem falta documento?”"],
                ].map(([icone, quem, exemplos]) => (
                  <li key={String(quem)} className="flex items-start gap-4">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-roxo text-white">
                      {icone}
                    </span>
                    <span>
                      <strong className="block text-[17px] text-tinta">{quem}</strong>
                      <span className="text-[15px] text-tinta/70">{exemplos}</span>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-6 text-sm text-tinta/60">
                O Proto responde sobre uma lista fechada de assuntos e avisa
                quando não sabe. Ele não usa modelo de linguagem, e nenhum
                dado de filiado sai do portal.
              </p>
            </div>

            {/* UMA CONVERSA DESENHADA, para se ver do que se trata. As
                falas são as que o Proto dá de verdade na demonstração. */}
            <div aria-hidden="true" className="relative rounded-3xl bg-gradient-to-br from-roxo to-azul p-6 shadow-2xl sm:p-8">
              <span className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-ambar/80" />
              <span className="absolute -bottom-5 -left-5 h-16 w-16 rounded-full bg-ceu" />
              <div className="relative space-y-3">
                <div className="flex items-center gap-3 text-white">
                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-roxo">
                    <Bot className="h-7 w-7" />
                  </span>
                  <span>
                    <strong className="block text-lg">Proto</strong>
                    <span className="text-sm text-white/80">responde na hora</span>
                  </span>
                </div>
                <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-white/20 px-4 py-3 text-[15px] text-white">
                  Meus documentos chegaram?
                </p>
                <p className="w-fit max-w-[90%] rounded-2xl rounded-bl-sm bg-white px-4 py-3 text-[15px] text-slate-900">
                  Já recebemos de você: certidão de trânsito em julgado,
                  comprovante de contribuição, sentença. Não há documento seu
                  pendente agora.
                </p>
                <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-white/20 px-4 py-3 text-[15px] text-white">
                  Com quem está o meu caso?
                </p>
                <p className="w-fit max-w-[90%] rounded-2xl rounded-bl-sm bg-white px-4 py-3 text-[15px] text-slate-900">
                  O seu caso está com o Escritório de Exemplo A. A
                  documentação está completa: não falta nada da sua parte.
                </p>
              </div>
            </div>
          </div>
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
