/**
 * O ATENDIMENTO: a conversa em que o filiado pergunta o que perguntaria por
 * telefone — em que processo estou, mudou alguma coisa, meus documentos
 * chegaram, o que falta.
 *
 * NÃO É UMA PESSOA E NÃO É UMA IA GENERATIVA, e a tela diz isso antes de
 * qualquer pergunta. Quem responde é o servidor, com o que já está no
 * cadastro dela; a pergunta não leva CPF e não fica guardada.
 */
import { Bot, SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Aviso, Botao, Cartao, cn } from "../componentes/ui";
import * as api from "../lib/envio";
import { Portao } from "./Portao";

interface Fala {
  de: "voce" | "atendimento";
  texto: string[];
}

const ABERTURA: Fala = {
  de: "atendimento",
  texto: [
    "Olá. Sou o atendimento automático do portal: respondo na hora, com o que está no seu cadastro.",
    "Não sou uma pessoa e não dou parecer. Escolha uma pergunta abaixo, ou escreva a sua.",
  ],
};

const SUGESTOES_INICIAIS = [
  "Em quais processos eu estou?",
  "Mudou alguma coisa nos meus processos?",
  "Meus documentos chegaram?",
  "O que falta eu fazer?",
];

export function Atendimento({ entidade }: { entidade: string }) {
  const [token, setToken] = useState("");
  const [falas, setFalas] = useState<Fala[]>([ABERTURA]);
  const [sugestoes, setSugestoes] = useState<string[]>(SUGESTOES_INICIAIS);
  const [texto, setTexto] = useState("");
  const [esperando, setEsperando] = useState(false);
  const [erro, setErro] = useState("");
  const fim = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: "nearest" });
  }, [falas]);

  if (!token) {
    return (
      <Portao
        entidade={entidade}
        titulo="Atendimento"
        explicacao="Pergunte pelos seus processos, pelos seus documentos e pelo que falta. Para responder sobre você, precisamos confirmar que é você."
        onToken={setToken}
      />
    );
  }

  async function perguntar(pergunta: string) {
    const limpa = pergunta.trim();
    if (!limpa || esperando) return;
    setErro("");
    setTexto("");
    setFalas((f) => [...f, { de: "voce", texto: [limpa] }]);
    setEsperando(true);
    try {
      const r = await api.perguntar(token, limpa);
      setFalas((f) => [...f, { de: "atendimento", texto: r.resposta }]);
      if (r.sugestoes.length) setSugestoes(r.sugestoes);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "o atendimento não respondeu");
    } finally {
      setEsperando(false);
    }
  }

  return (
    <Cartao
      titulo="Atendimento"
      explicacao="Automático: responde com o que está no seu cadastro. A sua pergunta não fica guardada."
    >
      <div
        role="log"
        aria-live="polite"
        aria-label="Conversa com o atendimento"
        className="max-h-[28rem] space-y-3 overflow-y-auto rounded-xl bg-papel p-4"
      >
        {falas.map((f, i) => (
          <div
            key={i}
            className={cn("flex gap-2", f.de === "voce" ? "justify-end" : "justify-start")}
          >
            {f.de === "atendimento" ? (
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
                {f.de === "voce" ? "Você: " : "Atendimento: "}
              </span>
              {f.texto.map((t, j) => (
                <p key={j}>{t}</p>
              ))}
            </div>
          </div>
        ))}
        {esperando ? (
          <p className="pl-10 text-sm text-tinta/60">Consultando o seu cadastro…</p>
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
        <label htmlFor="pergunta-do-atendimento" className="sr-only">
          Sua pergunta
        </label>
        <input
          id="pergunta-do-atendimento"
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
    </Cartao>
  );
}
