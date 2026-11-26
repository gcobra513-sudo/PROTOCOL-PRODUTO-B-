/**
 * O PROTO, NO TOPO DA ÁREA — onde se vê que há alguém ali para ajudar.
 *
 * Ele era um cartão no fim da tela e uma aba entre cinco: quem não sabia que
 * existia não o encontrava. Aqui ele abre a área de cada um dos três
 * públicos, com cara de assistente e as perguntas que ele sabe responder já
 * escritas. Tocar numa delas abre a conversa ali mesmo.
 *
 * É O MESMO PROTO das outras telas: lista fechada de assuntos, sem modelo de
 * linguagem, e a pergunta não fica guardada. A faixa só muda onde ele mora.
 */
import { Bot, ChevronUp, Sparkles } from "lucide-react";
import { useState } from "react";

import type { RespostaDoAtendimento } from "../lib/envio";
import { Conversa } from "./Conversa";

export function ProtoNoTopo({
  para,
  abertura,
  sugestoes,
  perguntar,
  consultando,
  onSessaoMorta,
  onEscolher,
}: {
  /** A quem ele fala nesta área, numa frase. */
  para: string;
  abertura: string[];
  sugestoes: string[];
  perguntar: (pergunta: string) => Promise<RespostaDoAtendimento>;
  consultando: string;
  onSessaoMorta: () => void;
  /** Com isto, a pergunta escolhida é levada a outra tela (a conversa
   *  inteira do filiado) em vez de abrir aqui. */
  onEscolher?: (pergunta: string) => void;
}) {
  const [aberta, setAberta] = useState(false);
  const [primeira, setPrimeira] = useState("");

  return (
    <section
      aria-label="Proto, o assistente do portal"
      className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-roxo to-azul p-5 text-white shadow-cartao sm:p-6"
    >
      <span aria-hidden="true" className="absolute -right-12 -top-16 h-52 w-52 rounded-full bg-white/10" />
      <span aria-hidden="true" className="absolute -bottom-20 right-24 h-44 w-44 rounded-full bg-white/5" />
      <div className="relative flex flex-wrap items-start gap-4">
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white text-roxo shadow-lg">
          <Bot className="h-8 w-8" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-widest text-white/80">
            <Sparkles className="h-4 w-4" aria-hidden="true" /> Assistente do portal
          </p>
          <h2 className="mt-1 text-2xl font-bold">Oi, eu sou o Proto.</h2>
          <p className="mt-1 max-w-2xl text-[16px] leading-relaxed text-white/90">{para}</p>
        </div>
        {aberta ? (
          <button
            type="button"
            onClick={() => setAberta(false)}
            className="inline-flex items-center gap-1 rounded-lg border border-white/40 px-3 py-2 text-sm font-medium hover:bg-white/10"
          >
            Fechar <ChevronUp className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {aberta ? (
        <div className="relative mt-5 rounded-xl bg-carta p-4 text-tinta">
          <Conversa
            abertura={abertura}
            sugestoesIniciais={sugestoes}
            perguntar={perguntar}
            consultando={consultando}
            onSessaoMorta={onSessaoMorta}
            perguntaInicial={primeira}
            onPerguntaFeita={() => setPrimeira("")}
          />
        </div>
      ) : (
        <div className="relative mt-5">
          <p className="text-sm font-medium text-white/80">Pergunte, por exemplo:</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {sugestoes.slice(0, 4).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => {
                  if (onEscolher) return onEscolher(s);
                  setPrimeira(s);
                  setAberta(true);
                }}
                className="rounded-full bg-white/15 px-4 py-2 text-left text-[15px] font-medium hover:bg-white/25"
              >
                {s}
              </button>
            ))}
            <button
              type="button"
              onClick={() => (onEscolher ? onEscolher("") : setAberta(true))}
              className="rounded-full bg-white px-4 py-2 text-[15px] font-semibold text-roxo hover:bg-white/90"
            >
              Escrever outra pergunta
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
