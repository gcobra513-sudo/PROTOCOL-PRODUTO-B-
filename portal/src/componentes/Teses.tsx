/**
 * AS NOVIDADES NOS TRIBUNAIS, e AS TESES ACOMPANHADAS.
 *
 * É o que o escritório e a diretoria querem saber primeiro de manhã: o
 * tribunal julgou alguma coisa que alcança a nossa gente? Quantas pessoas?
 * As frases das novidades vêm prontas do servidor; a lista de teses mostra
 * cada tema e cada ação da carreira, com a situação, a fonte, e quantas
 * pessoas da base seriam alcançadas.
 *
 * O NÚMERO É UMA SIMULAÇÃO, e a tela diz isso duas vezes: no cabeçalho e em
 * cada linha ("poderiam", não "podem"). Para o filiado nada muda antes de um
 * advogado conferir a tese.
 */
import { ChevronDown, Landmark, Megaphone, Scale } from "lucide-react";
import { useState } from "react";

import type { NovidadeNosTribunais, Tese } from "../lib/envio";
import { alcanceEmPalavras, rotuloDaSituacaoDaTese, saudacao } from "../lib/teses";
import { Cartao } from "./ui";

function dia(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

/** O "bom dia": o que os tribunais decidiram, e quem isso alcança. Sem
 *  novidade, não aparece — um quadro dizendo "nada de novo" todo dia ensina
 *  a pessoa a não olhar para ele. */
export function Novidades({ novidades }: { novidades: NovidadeNosTribunais[] }) {
  if (!novidades.length) return null;
  return (
    <section
      aria-label="Novidades nos tribunais"
      className="rounded-2xl border-2 border-bom/30 bg-bom/10 p-5 sm:p-6"
    >
      <div className="flex items-start gap-4">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-bom text-white">
          <Megaphone className="h-6 w-6" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-bold text-tinta">
            {saudacao(new Date())}. {novidades.length === 1 ? "Há uma novidade" : `Há ${novidades.length} novidades`} nos tribunais.
          </h2>
          <ul className="mt-3 space-y-3">
            {novidades.map((n) => (
              <li key={`${n.entidade ?? ""}-${n.id}-${n.evento}`} className="rounded-lg bg-carta p-4 text-[16px] leading-relaxed text-tinta shadow-cartao">
                {n.frase}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-tinta/70">
            Os números são uma simulação: quantas pessoas teriam o caminho aberto se a tese for
            conferida por advogado. Nada muda para o filiado antes disso.
          </p>
        </div>
      </div>
    </section>
  );
}

export function Teses({ teses, de }: { teses: Tese[]; de?: string }) {
  const [aberta, setAberta] = useState("");
  if (!teses.length) return null;
  return (
    <Cartao
      titulo={de ? `Teses acompanhadas — ${de}` : "Teses acompanhadas"}
      explicacao="Os temas dos tribunais e as ações coletivas da carreira deste sindicato. Em cada um: a situação, a fonte, e quantas pessoas da base seriam alcançadas. O alcance é uma simulação até um advogado conferir a tese."
    >
      <div className="space-y-2">
        {teses.map((t) => (
          <div key={t.id} className="rounded-lg border border-borda bg-carta">
            <button
              type="button"
              aria-expanded={aberta === t.id}
              onClick={() => setAberta((a) => (a === t.id ? "" : t.id))}
              className="flex w-full flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 text-left hover:bg-lilas/40"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-lilas text-acento">
                {t.tipo === "acao" ? (
                  <Scale className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <Landmark className="h-5 w-5" aria-hidden="true" />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[16px] font-semibold text-tinta">{t.rotulo}</span>
                <span className="block text-sm text-tinta/70">{alcanceEmPalavras(t)}</span>
              </span>
              {rotuloDaSituacaoDaTese(t) ? (
                <span className="rounded-full border border-borda bg-papel px-3 py-1 text-[13px] font-semibold text-tinta/80">
                  {rotuloDaSituacaoDaTese(t)}
                  {/* No tema afetado a data é a da AFETAÇÃO, não a de um
                      julgamento marcado. */}
                  {t.data ? (t.situacao === "afetado" ? ` · afetado em ${dia(t.data)}` : ` em ${dia(t.data)}`) : ""}
                </span>
              ) : null}
              <span
                className={
                  "rounded-full border px-3 py-1 text-[13px] font-semibold " +
                  (t.conferida
                    ? "border-bom/40 bg-bom/10 text-bom"
                    : "border-borda bg-papel text-tinta/70")
                }
              >
                {t.conferida ? "Conferida por advogado" : "Ainda não conferida"}
              </span>
              <ChevronDown
                className={"h-5 w-5 shrink-0 text-acento transition-transform " + (aberta === t.id ? "rotate-180" : "")}
                aria-hidden="true"
              />
            </button>
            {aberta === t.id ? (
              <div className="space-y-3 border-t border-borda px-4 py-4 text-[15px] leading-relaxed text-tinta/85">
                {t.questao ? (
                  <p>
                    <strong className="text-tinta">A questão:</strong> {t.questao}
                  </p>
                ) : null}
                {t.tese ? (
                  <p>
                    <strong className="text-tinta">A tese:</strong> {t.tese}
                  </p>
                ) : t.tipo === "tema" ? (
                  <p>Ainda não há tese fixada.</p>
                ) : null}
                <div className="grid gap-2 sm:grid-cols-3">
                  {[
                    [t.conferida ? "podem" : "poderiam", t.poderiam],
                    ["dependem de conferência", t.dependem],
                    ["ficam de fora", t.fora],
                  ].map(([rotulo, n]) => (
                    <div key={String(rotulo)} className="rounded-lg bg-papel p-3">
                      <p className="text-2xl font-bold text-tinta">{n}</p>
                      <p className="text-sm text-tinta/70">{rotulo}</p>
                    </div>
                  ))}
                </div>
                {t.fonte ? (
                  <p className="text-sm text-tinta/60">
                    Fonte:{" "}
                    {/^https:\/\//.test(t.fonte) ? (
                      <a href={t.fonte} target="_blank" rel="noopener noreferrer" className="underline">
                        {t.fonte}
                      </a>
                    ) : (
                      t.fonte
                    )}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </Cartao>
  );
}
