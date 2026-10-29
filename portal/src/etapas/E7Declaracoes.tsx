/**
 * Etapa 7 — quatro perguntas e a declaração.
 *
 * POR QUE A PRIMEIRA PERGUNTA É A MAIS IMPORTANTE DO PORTAL
 *
 * "Você já entrou com execução sobre este mesmo assunto?" ataca o maior risco
 * do projeto: protocolar duas vezes a ação da mesma pessoa. Isso geraria dois
 * processos, e o erro só apareceria semanas depois.
 *
 * As três formas de descobrir isso automaticamente foram testadas e **todas
 * as três estão fechadas**: a base pública do CNJ não permite busca por CPF;
 * a consulta ao sistema do tribunal é vedada por norma; a consulta pública
 * tem CAPTCHA. Não existe jeito técnico de saber.
 *
 * Mas dá para PERGUNTAR. A resposta não é prova — e por isso "não sei" é
 * opção legítima — mas é a informação mais barata que existe.
 *
 * A quarta não é pergunta, é declaração, e protege o escritório: há orientação
 * do CNJ de que o juiz pode exigir demonstração de que o autor sabia da ação
 * e quis entrar com ela. Ter isso de 15 mil pessoas desde o começo resolve
 * antes de virar problema.
 */
import { Aviso, Cartao, Caixa, Escolha } from "../componentes/ui";
import type { Declaracoes, Resposta } from "../lib/tipos";

const OPCOES: { valor: Resposta; rotulo: string }[] = [
  { valor: "nao", rotulo: "Não" },
  { valor: "sim", rotulo: "Sim" },
  { valor: "nao_sei", rotulo: "Não sei" },
];

export function E7Declaracoes({
  dados,
  onChange,
}: {
  dados: Declaracoes;
  onChange: (campo: keyof Declaracoes, valor: Resposta | boolean) => void;
}) {
  const algumSim =
    dados.jaExecutou === "sim" ||
    dados.jaRecebeu === "sim" ||
    dados.outroAdvogado === "sim";
  const algumNaoSei =
    dados.jaExecutou === "nao_sei" ||
    dados.jaRecebeu === "nao_sei" ||
    dados.outroAdvogado === "nao_sei";

  return (
    <Cartao
      titulo="Quatro perguntas, e a sua confirmação"
      explicacao="Estas respostas valem tanto quanto os documentos. Responder “não sei”
        é melhor que adivinhar."
    >
      <Escolha<Resposta>
        rotulo="Você já entrou com ação de execução sobre este mesmo assunto?"
        explicacao="Por conta própria, por outro advogado, ou pelo sindicato."
        obrigatorio
        valor={dados.jaExecutou}
        onChange={(v) => onChange("jaExecutou", v)}
        opcoes={OPCOES}
      />

      <Escolha<Resposta>
        rotulo="Você já fez acordo ou recebeu valores sobre isso?"
        obrigatorio
        valor={dados.jaRecebeu}
        onChange={(v) => onChange("jaRecebeu", v)}
        opcoes={OPCOES}
      />

      <Escolha<Resposta>
        rotulo="Outro advogado já cuida ou cuidou desta cobrança?"
        obrigatorio
        valor={dados.outroAdvogado}
        onChange={(v) => onChange("outroAdvogado", v)}
        opcoes={OPCOES}
      />

      {algumSim ? (
        <Aviso tom="alerta">
          Você respondeu “sim” a alguma das perguntas. Isso{" "}
          <strong>não impede</strong> o seu cadastro — mas o escritório vai
          analisar o seu caso antes de entrar com qualquer ação, para não
          protocolar algo em duplicidade. Alguém pode entrar em contato.
        </Aviso>
      ) : null}

      {algumNaoSei && !algumSim ? (
        <Aviso tom="neutro">
          Respondeu “não sei”, e isso está certo — é melhor que adivinhar. O
          escritório vai conferir antes de entrar com a ação.
        </Aviso>
      ) : null}

      <div className="rounded-md border border-borda bg-papel p-4">
        <Caixa
          marcado={dados.cienciaEIniciativa}
          onChange={(v) => onChange("cienciaEIniciativa", v)}
          rotulo={
            <strong>
              Declaro que tomei conhecimento desta ação e que é da minha
              vontade entrar com ela.
            </strong>
          }
          detalhe="Também declaro que as informações e os documentos que enviei são
            verdadeiros, e que avisarei o escritório se algo mudar."
        />
      </div>

      <div className="rounded-md border border-borda bg-papel p-4">
        <Caixa
          marcado={dados.querAviso}
          onChange={(v) => onChange("querAviso", v)}
          rotulo={
            <strong>
              Quero receber aviso por e-mail quando houver movimentação nos
              meus processos.
            </strong>
          }
          detalhe="Opcional, e dá para mudar depois. Sem isso a gente não te
            escreve — você ainda pode entrar e consultar quando quiser."
        />
      </div>

      <Aviso tom="neutro">
        <strong>O que acontece depois:</strong> você recebe um e-mail com a
        lista do que foi recebido, e pode corrigir ou completar enquanto o
        lote não fechar. Ninguém acerta tudo na primeira tentativa.
      </Aviso>
    </Cartao>
  );
}
