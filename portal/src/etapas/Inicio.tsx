/**
 * A primeira tela. Ela existe para a pessoa saber onde está e por que vale
 * a pena seguir.
 *
 * O QUE ELA PROMETE É O QUE O PRODUTO ENTREGA: você manda os seus
 * documentos, a gente lê, e te diz de quais ações você faz parte e o que
 * pode ser feito em cada uma. Nem mais — não prometemos dinheiro, nem
 * parecer — nem menos.
 *
 * E quem fala aqui é o SINDICATO. Se existe escritório na relação, foi o
 * sindicato que o contratou; isso é contrato, não é assunto desta tela.
 */
import { Aviso, Botao, Cartao } from "../componentes/ui";

const PASSOS = [
  {
    titulo: "Você entra sem senha",
    texto:
      "Digita o CPF e recebe um código de seis dígitos no e-mail que o " +
      "sindicato tem em cadastro. Sem senha para criar, nem para esquecer.",
  },
  {
    titulo: "Conta quem é e desde quando é filiado",
    texto:
      "É a data de filiação que diz de quais ações você faz parte. Os " +
      "comprovantes de contribuição confirmam.",
  },
  {
    titulo: "Anexa o que tem",
    texto:
      "Comprovantes de contribuição, e — se você tiver — a sentença e a " +
      "certidão de trânsito em julgado. Quem não tem também recebe resposta.",
  },
  {
    titulo: "Recebe a resposta",
    texto:
      "De quais ações você participa, por qual período, e o que pode ser " +
      "feito em cada uma: executar, se já há sentença; entrar com ação, se " +
      "ainda não.",
  },
];

export function Inicio({
  entidade,
  onComecar,
  onVerPrivacidade,
}: {
  entidade?: string;
  onComecar: () => void;
  onVerPrivacidade: () => void;
}) {
  return (
    <Cartao
      titulo={
        entidade
          ? `Seus direitos, organizados — ${entidade}`
          : "Seus direitos, organizados"
      }
      explicacao={
        <>
          Você manda os seus documentos, a gente lê, e te diz{" "}
          <strong>de quais ações você faz parte</strong> e o que pode ser
          feito em cada uma. Leva poucos minutos.
        </>
      }
    >
      <ol className="space-y-4">
        {PASSOS.map((p, i) => (
          <li key={p.titulo} className="flex gap-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-borda text-sm text-tinta/70">
              {i + 1}
            </span>
            <div>
              <p className="text-[15px] font-medium text-tinta">{p.titulo}</p>
              <p className="mt-0.5 text-[15px] leading-relaxed text-tinta/75">
                {p.texto}
              </p>
            </div>
          </li>
        ))}
      </ol>

      <Botao tipo="principal" onClick={onComecar}>
        Começar
      </Botao>

      <Aviso tom="neutro">
        <strong>O que isto não é:</strong> não é parecer e não promete
        dinheiro. Nada é apresentado em juízo com base neste cadastro — o que
        a gente faz é organizar o que você tem e mostrar o que dá para fazer.{" "}
        <button
          type="button"
          onClick={onVerPrivacidade}
          className="underline hover:text-tinta"
        >
          Como tratamos os seus dados
        </button>
        .
      </Aviso>
    </Cartao>
  );
}
