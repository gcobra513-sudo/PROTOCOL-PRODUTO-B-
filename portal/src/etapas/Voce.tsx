/**
 * Quem é você. A etapa mais curta, de propósito.
 *
 * O Produto B não pede endereço, RG nem matrícula. Esses campos existiam
 * para preencher formulário de distribuição de processo — e o B não
 * distribui nada: ele responde uma pergunta. Pedir dado que não se usa é
 * aumentar o que se guarda sem melhorar o que se entrega, e dado guardado
 * sem razão é só superfície a mais para vazar.
 */
import { Aviso, Campo, Cartao } from "../componentes/ui";
import type { Identificacao } from "../lib/tipos";
import { conferirCpf, formatarCpf } from "../lib/validacao";

export function Voce({
  dados,
  onChange,
  cpfTravado,
  doSindicato,
}: {
  dados: Identificacao;
  onChange: (campo: keyof Identificacao, valor: string) => void;
  cpfTravado: boolean;
  /** Campos que vieram do sindicato, como `identificacao.campo`. */
  doSindicato?: Set<string>;
}) {
  // DE ONDE VEIO O QUE JÁ ESTÁ PREENCHIDO. Sem isto, a pessoa vê o próprio
  // nome num campo que ela não digitou e não sabe por quê — e campo
  // preenchido sem explicação parece erro do sistema, não ajuda.
  const daBase = (campo: string, padrao?: string) =>
    doSindicato?.has(`identificacao.${campo}`)
      ? "Veio do seu sindicato. Corrija se estiver errado."
      : padrao;

  return (
    <Cartao
      titulo="Você"
      explicacao="Só o necessário para a gente te identificar e te avisar."
    >
      <Campo
        rotulo="Nome completo"
        obrigatorio
        valor={dados.nome}
        ajuda={daBase("nome")}
        onChange={(v) => onChange("nome", v)}
      />

      <Campo
        rotulo="CPF"
        obrigatorio
        inputMode="numeric"
        placeholder="000.000.000-00"
        valor={formatarCpf(dados.cpf)}
        onChange={(v) => onChange("cpf", formatarCpf(v))}
        problemas={dados.cpf ? conferirCpf(dados.cpf) : []}
        ajuda={
          cpfTravado
            ? "É o CPF com que você entrou, e por isso não muda aqui."
            : undefined
        }
      />

      <Campo
        rotulo="E-mail"
        obrigatorio
        valor={dados.email}
        onChange={(v) => onChange("email", v.trim())}
        ajuda={daBase(
          "email",
          "É para cá que vão os avisos. O código de acesso continua indo " +
            "para o e-mail que o sindicato tem em cadastro.",
        )}
      />

      <Campo
        rotulo="Telefone"
        inputMode="tel"
        valor={dados.telefone}
        ajuda={daBase("telefone")}
        onChange={(v) => onChange("telefone", v)}
      />

      <Campo
        rotulo="Data de nascimento"
        placeholder="AAAA-MM-DD"
        valor={dados.dataNascimento}
        ajuda={daBase("dataNascimento")}
        onChange={(v) => onChange("dataNascimento", v.trim())}
      />

      <Aviso tom="neutro">
        Não pedimos endereço, RG nem matrícula.{" "}
        <strong>Dado que a gente não usa é dado que a gente não guarda.</strong>
      </Aviso>
    </Cartao>
  );
}
