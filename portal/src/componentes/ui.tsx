/**
 * Componentes de interface, no estilo shadcn/ui: Tailwind + cva, sem
 * biblioteca de componentes por cima.
 *
 * Duas regras que valem para tudo aqui, e não são estética:
 *
 * 1. **Todo campo tem rótulo ligado por `htmlFor`/`id`.** Quem usa leitor de
 *    tela depende disso, e parte dos 15 mil filiados é aposentada — leitor de
 *    tela e zoom grande não são exceção nesse público.
 * 2. **Erro é texto, não cor.** Vermelho sozinho não é mensagem para quem não
 *    distingue vermelho e verde. O erro aparece escrito, e `aria-invalid` +
 *    `aria-describedby` ligam o campo à explicação.
 */
import { cva, type VariantProps } from "class-variance-authority";
import { clsx } from "clsx";
import type { ReactNode } from "react";
import { twMerge } from "tailwind-merge";

export function cn(...entradas: (string | undefined | false | null)[]) {
  return twMerge(clsx(entradas));
}

// --------------------------------------------------------------------------
const botao = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-medium " +
    "transition-colors focus-visible:outline focus-visible:outline-2 " +
    "focus-visible:outline-offset-2 focus-visible:outline-acento " +
    "disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      tipo: {
        principal: "bg-acento text-carta hover:bg-acento/90",
        secundario:
          "border border-borda bg-carta text-tinta hover:bg-papel",
        discreto: "text-tinta/70 hover:text-tinta hover:bg-papel",
      },
      tamanho: {
        normal: "h-11 px-5 text-[15px]",
        pequeno: "h-9 px-3 text-sm",
      },
    },
    defaultVariants: { tipo: "principal", tamanho: "normal" },
  },
);

export function Botao({
  tipo,
  tamanho,
  className,
  ...resto
}: React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof botao>) {
  return <button className={cn(botao({ tipo, tamanho }), className)} {...resto} />;
}

// --------------------------------------------------------------------------
export function Cartao({
  titulo,
  explicacao,
  children,
}: {
  titulo: string;
  explicacao?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-borda bg-carta p-5 sm:p-7">
      <h2 className="text-xl font-semibold text-tinta">{titulo}</h2>
      {explicacao ? (
        <p className="mt-2 text-[15px] leading-relaxed text-tinta/70">
          {explicacao}
        </p>
      ) : null}
      <div className="mt-6 space-y-5">{children}</div>
    </section>
  );
}

// --------------------------------------------------------------------------
let contador = 0;
function idUnico(prefixo: string) {
  contador += 1;
  return `${prefixo}-${contador}`;
}

export function Campo({
  rotulo,
  valor,
  onChange,
  problemas = [],
  ajuda,
  obrigatorio,
  ...resto
}: {
  rotulo: string;
  valor: string;
  onChange: (v: string) => void;
  problemas?: string[];
  ajuda?: string;
  obrigatorio?: boolean;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const id = resto.id ?? idUnico("campo");
  const idAjuda = `${id}-ajuda`;
  const temErro = problemas.length > 0;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-tinta">
        {rotulo}
        {obrigatorio ? (
          <span className="ml-1 text-alerta" aria-hidden="true">
            *
          </span>
        ) : null}
        {obrigatorio ? <span className="sr-only"> (obrigatório)</span> : null}
      </label>
      <input
        {...resto}
        id={id}
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={temErro || undefined}
        aria-describedby={temErro || ajuda ? idAjuda : undefined}
        className={cn(
          "mt-1.5 h-11 w-full rounded-md border bg-carta px-3 text-[15px]",
          "text-tinta placeholder:text-tinta/40",
          "focus:outline focus:outline-2 focus:outline-offset-0 focus:outline-acento",
          temErro ? "border-alerta" : "border-borda",
          resto.className,
        )}
      />
      {temErro ? (
        <ul id={idAjuda} className="mt-1.5 space-y-1">
          {problemas.map((p) => (
            <li key={p} className="text-sm text-alerta">
              {p}
            </li>
          ))}
        </ul>
      ) : ajuda ? (
        <p id={idAjuda} className="mt-1.5 text-sm text-tinta/60">
          {ajuda}
        </p>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
export function Escolha<T extends string>({
  rotulo,
  explicacao,
  valor,
  onChange,
  opcoes,
  obrigatorio,
}: {
  rotulo: string;
  explicacao?: string;
  valor: T | "";
  onChange: (v: T) => void;
  opcoes: { valor: T; rotulo: string; detalhe?: string }[];
  obrigatorio?: boolean;
}) {
  const nome = idUnico("escolha");
  return (
    <fieldset>
      <legend className="text-sm font-medium text-tinta">
        {rotulo}
        {obrigatorio ? (
          <span className="ml-1 text-alerta" aria-hidden="true">
            *
          </span>
        ) : null}
      </legend>
      {explicacao ? (
        <p className="mt-1 text-sm text-tinta/60">{explicacao}</p>
      ) : null}
      <div className="mt-2.5 space-y-2">
        {opcoes.map((o) => (
          <label
            key={o.valor}
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-md border p-3",
              "transition-colors hover:bg-papel",
              valor === o.valor
                ? "border-acento bg-acento/5"
                : "border-borda bg-carta",
            )}
          >
            <input
              type="radio"
              name={nome}
              value={o.valor}
              checked={valor === o.valor}
              onChange={() => onChange(o.valor)}
              className="mt-0.5 h-4 w-4 accent-acento"
            />
            <span>
              <span className="block text-[15px] text-tinta">{o.rotulo}</span>
              {o.detalhe ? (
                <span className="block text-sm text-tinta/60">{o.detalhe}</span>
              ) : null}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

// --------------------------------------------------------------------------
export function Caixa({
  rotulo,
  marcado,
  onChange,
  detalhe,
}: {
  rotulo: ReactNode;
  marcado: boolean;
  onChange: (v: boolean) => void;
  detalhe?: ReactNode;
}) {
  const id = idUnico("caixa");
  return (
    <div className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        checked={marcado}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 accent-acento"
      />
      <label htmlFor={id} className="text-[15px] leading-relaxed text-tinta">
        {rotulo}
        {detalhe ? (
          <span className="mt-1 block text-sm text-tinta/60">{detalhe}</span>
        ) : null}
      </label>
    </div>
  );
}

// --------------------------------------------------------------------------
export function Aviso({
  tom,
  children,
}: {
  tom: "alerta" | "bom" | "neutro";
  children: ReactNode;
}) {
  const cores = {
    alerta: "border-alerta/40 bg-alerta/5 text-alerta",
    bom: "border-bom/40 bg-bom/5 text-bom",
    neutro: "border-borda bg-papel text-tinta/80",
  } as const;
  return (
    <div
      role={tom === "alerta" ? "alert" : undefined}
      className={cn(
        "rounded-md border p-3.5 text-[15px] leading-relaxed",
        cores[tom],
      )}
    >
      {children}
    </div>
  );
}
