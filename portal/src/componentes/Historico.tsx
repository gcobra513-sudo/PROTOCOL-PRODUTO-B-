/**
 * O HISTÓRICO DE UM CASO, passo a passo: quem encaminhou, quando o
 * escritório recebeu, o que pediu, que documento abriu, quem foi avisado.
 *
 * É a custódia posta na tela. As frases vêm prontas do servidor — a tela não
 * interpreta o que aconteceu, só mostra na ordem.
 */
function quando(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso ?? "");
  if (!m) return "";
  // A hora vem em UTC; mostrada no fuso de quem lê.
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return `${m[3]}/${m[2]}/${m[1]}`;
  return d.toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function Historico({ passos }: { passos: { quando: string; o_que: string }[] }) {
  if (!passos.length) return null;
  return (
    <div>
      <p className="text-sm font-semibold uppercase tracking-wide text-tinta/60">Histórico do caso</p>
      <ol className="mt-2 space-y-0">
        {passos.map((p, i) => (
          <li key={`${p.quando}-${i}`} className="relative flex gap-3 pb-3 last:pb-0">
            {/* A linha que liga um passo ao seguinte. */}
            {i < passos.length - 1 ? (
              <span aria-hidden="true" className="absolute left-[7px] top-4 h-full w-0.5 bg-acento/20" />
            ) : null}
            <span aria-hidden="true" className="relative mt-1.5 h-4 w-4 shrink-0 rounded-full border-2 border-acento bg-carta" />
            <span className="text-[15px] leading-relaxed text-tinta">
              {p.o_que}
              <span className="block text-sm text-tinta/60">{quando(p.quando)}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
