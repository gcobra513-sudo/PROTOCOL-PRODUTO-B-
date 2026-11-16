/**
 * A CONVERSA COM O PROTO: as falas, as perguntas prontas e a caixa de texto.
 *
 * É a mesma para o filiado e para o gestor — o que muda é a quem a pergunta
 * vai (`perguntar`) e o que ele diz ao se apresentar. Um componente só,
 * para que o Proto se comporte igual nos dois lugares.
 */
import { Bot, SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { RespostaDoAtendimento } from "../lib/envio";
import { sessaoMorreu } from "../lib/sessao";
import { Aviso, Botao, cn } from "./ui";

interface Fala {
  de: "voce" | "proto";
  texto: string[];
}

export function Conversa({
  abertura,
  sugestoesIniciais,
  perguntar: enviar,
  consultando,
  onSessaoMorta,
  perguntaInicial = "",
  onPerguntaFeita,
}: {
  /** Como o Proto se apresenta. */
  abertura: string[];
  sugestoesIniciais: string[];
  perguntar: (pergunta: string) => Promise<RespostaDoAtendimento>;
  /** O que aparece enquanto a resposta não chega. */
  consultando: string;
  onSessaoMorta: () => void;
  /** Pergunta que já veio escolhida de outra tela: é feita ao abrir. */
  perguntaInicial?: string;
  onPerguntaFeita?: () => void;
}) {
  const [falas, setFalas] = useState<Fala[]>([{ de: "proto", texto: abertura }]);
  const [sugestoes, setSugestoes] = useState<string[]>(sugestoesIniciais);
  const [texto, setTexto] = useState("");
  const [esperando, setEsperando] = useState(false);
  const [erro, setErro] = useState("");
  const fim = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: "nearest" });
  }, [falas]);

  async function perguntar(pergunta: string) {
    const limpa = pergunta.trim();
    if (!limpa || esperando) return;
    setErro("");
    setTexto("");
    setFalas((f) => [...f, { de: "voce", texto: [limpa] }]);
    setEsperando(true);
    try {
      const r = await enviar(limpa);
      setFalas((f) => [...f, { de: "proto", texto: r.resposta }]);
      if (r.sugestoes.length) setSugestoes(r.sugestoes);
    } catch (e) {
      if (sessaoMorreu(e)) onSessaoMorta();
      else setErro(e instanceof Error ? e.message : "o Proto não respondeu");
    } finally {
      setEsperando(false);
    }
  }

  // A PERGUNTA QUE VEIO DE OUTRA TELA, feita uma vez só: quem clicou numa
  // pergunta quer a resposta, não a mesma pergunta para clicar de novo.
  useEffect(() => {
    if (!perguntaInicial) return;
    onPerguntaFeita?.();
    void perguntar(perguntaInicial);
  }, [perguntaInicial]);

  return (
    <>
      <div
        role="log"
        aria-live="polite"
        aria-label="Conversa com o Proto"
        className="max-h-[28rem] space-y-3 overflow-y-auto rounded-xl bg-papel p-4"
      >
        {falas.map((f, i) => (
          <div
            key={i}
            className={cn("flex gap-2", f.de === "voce" ? "justify-end" : "justify-start")}
          >
            {f.de === "proto" ? (
              <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-roxo text-white">
                <Bot className="h-4 w-4" aria-hidden="true" />
              </span>
            ) : null}
            <div
              className={cn(
                "max-w-[85%] space-y-2 rounded-xl px-4 py-3 text-[15px] leading-relaxed",
                f.de === "voce"
                  ? "bg-azul text-white"
                  : "bg-carta text-tinta shadow-cartao",
              )}
            >
              <span className="sr-only">
                {f.de === "voce" ? "Você: " : "Proto: "}
              </span>
              {f.texto.map((t, j) => (
                <p key={j}>{t}</p>
              ))}
            </div>
          </div>
        ))}
        {esperando ? (
          <p className="pl-10 text-sm text-tinta/60">{consultando}</p>
        ) : null}
        <div ref={fim} />
      </div>

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}

      <div className="flex flex-wrap gap-2">
        {sugestoes.map((s) => (
          <button
            key={s}
            type="button"
            disabled={esperando}
            onClick={() => void perguntar(s)}
            className="rounded-full bg-lilas px-3.5 py-2 text-sm font-medium text-acento hover:bg-lilas/70 disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void perguntar(texto);
        }}
      >
        <label htmlFor="pergunta-ao-proto" className="sr-only">
          Sua pergunta
        </label>
        <input
          id="pergunta-ao-proto"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          maxLength={500}
          placeholder="Escreva a sua pergunta"
          autoComplete="off"
          className="h-12 min-w-0 flex-1 rounded-lg border border-borda bg-carta px-3.5 text-[15px] text-tinta placeholder:text-tinta/40"
        />
        <Botao type="submit" disabled={esperando || !texto.trim()}>
          <SendHorizontal className="h-4 w-4" aria-hidden="true" />
          Perguntar
        </Botao>
      </form>
    </>
  );
}
