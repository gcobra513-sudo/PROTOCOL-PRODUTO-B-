/**
 * Etapa 4 — situação funcional.
 *
 * O portal NÃO pergunta "você tem direito?". Quem decide elegibilidade é o
 * jurídico, com base nestes dados. Perguntar à pessoa produziria resposta
 * errada — ela não tem como saber — e criaria expectativa indevida, que é
 * pior que dado faltando.
 */
import { Cartao, Campo, Escolha } from "../componentes/ui";
import type { Funcional, SituacaoFuncional } from "../lib/tipos";

export function E4Funcional({
  dados,
  onChange,
}: {
  dados: Funcional;
  onChange: (campo: keyof Funcional, valor: string) => void;
}) {
  const aposentadoOuPensionista =
    dados.situacao === "aposentado" || dados.situacao === "pensionista";
  return (
    <Cartao
      titulo="Sua situação funcional"
      explicacao="São os dados que o escritório usa para analisar o seu caso. Não
        perguntamos se você tem direito — isso é o jurídico que avalia."
    >
      <Campo
        rotulo="Cargo"
        obrigatorio
        valor={dados.cargo}
        onChange={(v) => onChange("cargo", v)}
        placeholder="Auditor-Fiscal da Receita Federal do Brasil"
      />

      <Escolha<SituacaoFuncional>
        rotulo="Situação atual"
        obrigatorio
        valor={dados.situacao}
        onChange={(v) => onChange("situacao", v)}
        opcoes={[
          { valor: "ativo", rotulo: "Na ativa" },
          { valor: "aposentado", rotulo: "Aposentado" },
          {
            valor: "pensionista",
            rotulo: "Pensionista",
            detalhe: "recebo pensão por morte de servidor",
          },
        ]}
      />

      <Campo
        rotulo="Unidade onde trabalha ou trabalhou"
        valor={dados.unidade}
        onChange={(v) => onChange("unidade", v)}
      />

      <div className="grid gap-5 sm:grid-cols-2">
        <Campo
          rotulo="Data de ingresso"
          obrigatorio
          type="date"
          valor={dados.dataIngresso}
          onChange={(v) => onChange("dataIngresso", v)}
        />
        {aposentadoOuPensionista ? (
          <Campo
            rotulo={
              dados.situacao === "pensionista"
                ? "Data de início da pensão"
                : "Data da aposentadoria"
            }
            obrigatorio
            type="date"
            valor={dados.dataAposentadoria}
            onChange={(v) => onChange("dataAposentadoria", v)}
          />
        ) : null}
      </div>
    </Cartao>
  );
}
