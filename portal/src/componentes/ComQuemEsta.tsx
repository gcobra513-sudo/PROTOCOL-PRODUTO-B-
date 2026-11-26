/**
 * COM QUEM ESTÁ O SEU CASO — o que o filiado perguntava por telefone.
 *
 * O sindicato encaminha o filiado a um escritório contratado, e até aqui
 * isso acontecia por fora: a pessoa não sabia a quem tinha sido
 * encaminhada, nem se o documento tinha chegado. Este cartão é a resposta
 * inteira: o nome do escritório, a situação, e o que ELA precisa fazer —
 * quase sempre, nada.
 */
import type { Encaminhamento } from "../lib/envio";
import { fraseParaOFiliado, rotuloDaSituacao, tomDaSituacao } from "../lib/escritorio";
import { Cartao } from "./ui";

const CORES = {
  bom: "border-bom/40 bg-bom/10 text-bom",
  neutro: "border-borda bg-papel text-tinta/80",
  alerta: "border-alerta/40 bg-alerta/10 text-alerta",
} as const;

export function ComQuemEsta({ casos }: { casos: Encaminhamento[] }) {
  // Situação que a tela não conhece não aparece: frase inventada sobre o
  // caso de alguém é pior que frase nenhuma.
  const visiveis = casos.filter((c) => fraseParaOFiliado(c));
  if (!visiveis.length) return null;
  return (
    <Cartao
      titulo="Com quem está o seu caso"
      explicacao="O seu sindicato encaminha cada caso ao escritório que cuida daquela ação. Aqui você acompanha, sem precisar ligar."
    >
      {visiveis.map((c) => (
        <div key={c.acao} className="rounded-md border border-borda bg-papel p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm text-tinta/70">{c.rotulo}</p>
              <p className="text-[17px] font-semibold text-tinta">{c.escritorio}</p>
            </div>
            <span
              className={`inline-block shrink-0 rounded-full border px-3 py-1 text-[13px] font-semibold ${CORES[tomDaSituacao(c.situacao)]}`}
            >
              {rotuloDaSituacao(c.situacao)}
            </span>
          </div>
          <p className="mt-3 text-[16px] leading-relaxed text-tinta">{fraseParaOFiliado(c)}</p>
          {c.contato ? (
            <p className="mt-2 text-[15px] text-tinta/70">
              Contato do escritório: <strong className="text-tinta">{c.contato}</strong>
            </p>
          ) : null}
        </div>
      ))}
    </Cartao>
  );
}
