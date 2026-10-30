/**
 * Carreira e filiação — a etapa que decide de quais ações a pessoa faz parte.
 *
 * Duas perguntas aqui valem mais que todo o resto do cadastro:
 *
 *   CARGO           define a CATEGORIA alcançada por cada ação coletiva
 *   DESDE QUANDO    define o PERÍODO, e é o cruzamento desse período contra
 *   É FILIADO       o período da ação que responde "de quais ações eu faço
 *                   parte"
 *
 * Por isso a tela explica por que pergunta, em vez de só pedir. Quem entende
 * para que serve o campo preenche com cuidado; quem não entende chuta.
 *
 * E "ainda sou filiado" é uma CAIXA, não um campo de data vazio. Campo vazio
 * é ambíguo — pode ser "não sei" —, e a diferença entre "ainda sou" e "não
 * sei" muda a resposta que a pessoa recebe.
 */
import { useState } from "react";

import { Aviso, Campo, Cartao, Caixa, Escolha } from "../componentes/ui";
import type {
  Carreira as DadosCarreira,
  Filiacao,
  SituacaoFuncional,
} from "../lib/tipos";

/** AAAA-MM com o mês válido. "1992-13" é erro de digitação, e aceitá-lo
 *  faria o cruzamento comparar contra um mês que não existe. */
export function conferirCompetencia(valor: string): string[] {
  if (!valor.trim()) return [];
  const m = /^(\d{4})-(\d{2})$/.exec(valor.trim());
  if (!m) return ["use o formato AAAA-MM, por exemplo 1992-05"];
  const mes = Number(m[2]);
  if (mes < 1 || mes > 12) return [`não existe o mês ${m[2]}`];
  const agora = new Date();
  const limite = `${agora.getFullYear()}-${String(agora.getMonth() + 1).padStart(2, "0")}`;
  if (valor.trim() > limite) return ["essa data está no futuro"];
  if (Number(m[1]) < 1930) return ["esse ano parece erro de digitação"];
  return [];
}

export function Carreira({
  carreira,
  filiacao,
  onCarreira,
  onFiliacao,
}: {
  carreira: DadosCarreira;
  filiacao: Filiacao;
  onCarreira: (campo: keyof DadosCarreira, valor: string) => void;
  onFiliacao: (campo: keyof Filiacao, valor: string) => void;
}) {
  // Estado próprio, e não `ate === ""`, porque desmarcar a caixa precisa
  // REVELAR o campo de data — e nesse instante ele ainda está vazio. Derivar
  // do valor faria a caixa desmarcar e nada aparecer.
  const [desfiliou, setDesfiliou] = useState(filiacao.ate.trim() !== "");
  const aindaFiliado = !desfiliou;
  const problemasDesde = conferirCompetencia(filiacao.desde);
  const problemasAte = aindaFiliado ? [] : conferirCompetencia(filiacao.ate);
  const invertido =
    !aindaFiliado &&
    filiacao.desde &&
    filiacao.ate &&
    problemasDesde.length === 0 &&
    problemasAte.length === 0 &&
    filiacao.ate < filiacao.desde;

  return (
    <Cartao
      titulo="Sua carreira e sua filiação"
      explicacao={
        <>
          São estas duas respostas que dizem <strong>de quais ações você faz
          parte</strong>. Uma ação coletiva alcança uma carreira, num período —
          e é o seu período de filiação que a gente compara com ele.
        </>
      }
    >
      <Campo
        rotulo="Seu cargo"
        obrigatorio
        valor={carreira.cargo}
        onChange={(v) => onCarreira("cargo", v)}
        placeholder="Ex.: Auditor-Fiscal da Receita Federal do Brasil"
        ajuda="Escreva como está no seu contracheque. A gente entende variações
          de grafia — não precisa acertar o hífen."
      />

      <Escolha<SituacaoFuncional>
        rotulo="Sua situação hoje"
        obrigatorio
        valor={carreira.situacao}
        onChange={(v) => onCarreira("situacao", v)}
        opcoes={[
          { valor: "ativo", rotulo: "Na ativa" },
          { valor: "aposentado", rotulo: "Aposentado" },
          { valor: "pensionista", rotulo: "Pensionista" },
        ]}
      />

      <div className="space-y-3 border-t border-borda pt-6">
        <div>
          <p className="text-[15px] font-medium text-tinta">
            Desde quando você é filiado ao sindicato?
          </p>
          <p className="mt-1 text-sm text-tinta/70">
            É a pergunta mais importante do cadastro. Se não lembrar o mês
            exato, os comprovantes de contribuição que você vai anexar na
            próxima etapa confirmam.
          </p>
        </div>

        <Campo
          rotulo="Filiado desde"
          obrigatorio
          placeholder="1992-05"
          valor={filiacao.desde}
          onChange={(v) => onFiliacao("desde", v.trim())}
          problemas={problemasDesde}
          ajuda="Ano e mês, assim: 1992-05"
        />

        <Caixa
          marcado={aindaFiliado}
          onChange={(marcado) => {
            setDesfiliou(!marcado);
            // Remarcar "ainda sou filiado" limpa a data de saída: deixá-la
            // lá faria o cadastro dizer duas coisas contraditórias.
            if (marcado) onFiliacao("ate", "");
          }}
          rotulo="Ainda sou filiado"
          detalhe="Se você se desfiliou, desmarque e informe quando foi."
        />

        {desfiliou ? (
          <Campo
            rotulo="Filiado até"
            placeholder="2018-06"
            valor={filiacao.ate}
            onChange={(v) => onFiliacao("ate", v.trim())}
            problemas={problemasAte}
          />
        ) : null}

        {invertido ? (
          <Aviso tom="alerta">
            A filiação termina ({filiacao.ate}) antes de começar
            ({filiacao.desde}). Confira as duas datas.
          </Aviso>
        ) : null}

        <Aviso tom="neutro">
          <strong>Por que isso importa:</strong> quem foi filiado só por parte
          do período de uma ação participa dela só por esse pedaço. A gente
          calcula essa conta para você — mas precisa das datas certas.
        </Aviso>
      </div>

      <div className="space-y-3 border-t border-borda pt-6">
        <p className="text-[15px] font-medium text-tinta">
          O resto ajuda, mas não é obrigatório
        </p>
        <Campo
          rotulo="Unidade onde trabalha ou trabalhou"
          valor={carreira.unidade}
          onChange={(v) => onCarreira("unidade", v)}
        />
        <Campo
          rotulo="Quando entrou no serviço público"
          placeholder="AAAA-MM-DD"
          valor={carreira.dataIngresso}
          onChange={(v) => onCarreira("dataIngresso", v.trim())}
        />
        {carreira.situacao === "aposentado" ? (
          <Campo
            rotulo="Quando se aposentou"
            placeholder="AAAA-MM-DD"
            valor={carreira.dataAposentadoria}
            onChange={(v) => onCarreira("dataAposentadoria", v.trim())}
          />
        ) : null}
      </div>
    </Cartao>
  );
}
