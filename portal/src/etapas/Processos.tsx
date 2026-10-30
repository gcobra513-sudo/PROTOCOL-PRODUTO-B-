/**
 * Processos que você já tem. Etapa inteiramente OPCIONAL.
 *
 * "Não sei" é resposta completa aqui, e quem responde isso é justamente
 * quem mais precisa do produto: a pessoa que não faz ideia do que corre em
 * nome dela. Obrigar a preencher produziria número chutado, que é pior que
 * campo vazio — porque ninguém sabe que está errado.
 *
 * E aceita QUALQUER TRIBUNAL. Acompanhar não é protocolar: a sentença de
 * alguém pode ser de tribunal estadual, e recusá-la seria pôr a nossa
 * suposição acima do fato dela.
 */
import { Aviso, Botao, Campo, Cartao, Escolha } from "../componentes/ui";
import type { Judicial, Resposta } from "../lib/tipos";
import { conferirProcesso, formatarProcesso } from "../lib/validacao";

export function Processos({
  dados,
  onChange,
}: {
  dados: Judicial;
  onChange: <C extends keyof Judicial>(campo: C, valor: Judicial[C]) => void;
}) {
  const numeros = dados.numeros ?? [];

  const trocar = (i: number, v: string) =>
    onChange(
      "numeros",
      numeros.map((n, j) => (j === i ? formatarProcesso(v) : n)),
    );

  return (
    <Cartao
      titulo="Processos que você já tem"
      explicacao="Se você sabe o número, a gente passa a acompanhar e te avisa
        quando andar. Se não sabe, siga — isso não trava nada."
    >
      <Escolha<Resposta>
        rotulo="Você tem algum processo sobre isso?"
        obrigatorio
        valor={dados.temProcesso}
        onChange={(v) => onChange("temProcesso", v)}
        opcoes={[
          { valor: "sim", rotulo: "Tenho, e sei o número" },
          {
            valor: "nao_sei",
            rotulo: "Acho que tenho, mas não sei o número",
            detalhe: "Marque sem medo. A gente procura depois.",
          },
          { valor: "nao", rotulo: "Não tenho nenhum" },
        ]}
      />

      {dados.temProcesso === "sim" ? (
        <div className="space-y-3">
          {numeros.map((numero, i) => (
            <div key={i} className="flex items-end gap-2">
              <div className="flex-1">
                <Campo
                  rotulo={`Processo ${i + 1}`}
                  inputMode="numeric"
                  placeholder="0000000-00.0000.0.00.0000"
                  valor={formatarProcesso(numero)}
                  onChange={(v) => trocar(i, v)}
                  problemas={numero ? conferirProcesso(numero) : []}
                />
              </div>
              <Botao
                tipo="secundario"
                onClick={() =>
                  onChange("numeros", numeros.filter((_, j) => j !== i))
                }
              >
                Remover
              </Botao>
            </div>
          ))}
          <Botao
            tipo="secundario"
            onClick={() => onChange("numeros", [...numeros, ""])}
          >
            {numeros.length ? "Acrescentar outro" : "Informar um número"}
          </Botao>
          <Aviso tom="neutro">
            Qualquer tribunal do país serve. O número está na sentença, em
            qualquer intimação que você recebeu, ou com quem cuidou da ação.
          </Aviso>
        </div>
      ) : null}

      <div className="space-y-4 border-t border-borda pt-6">
        <Escolha<Resposta>
          rotulo="Você já executou alguma sentença sobre isso?"
          valor={dados.jaExecutou}
          onChange={(v) => onChange("jaExecutou", v)}
          opcoes={[
            { valor: "nao", rotulo: "Não" },
            { valor: "sim", rotulo: "Sim, já executei" },
            { valor: "nao_sei", rotulo: "Não sei" },
          ]}
        />
        <Escolha<Resposta>
          rotulo="Você já tem ação própria sobre o mesmo assunto?"
          valor={dados.temAcaoPropria}
          onChange={(v) => onChange("temAcaoPropria", v)}
          opcoes={[
            { valor: "nao", rotulo: "Não" },
            { valor: "sim", rotulo: "Sim" },
            { valor: "nao_sei", rotulo: "Não sei" },
          ]}
        />
      </div>

      <Aviso tom="neutro">
        O que a gente mostra depois é a <strong>movimentação</strong> que o
        tribunal registrou, com cerca de um dia de atraso.{" "}
        <strong>Não é intimação e não serve para contar prazo.</strong>
      </Aviso>
    </Cartao>
  );
}
