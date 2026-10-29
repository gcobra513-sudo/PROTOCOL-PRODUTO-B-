/**
 * Etapa 3 — dados pessoais e endereço.
 *
 * O CPF vem travado da etapa 1: mudar o CPF aqui invalidaria os documentos já
 * conferidos contra ele na etapa 6. Quem errou o CPF volta à etapa 1 — e o
 * indicador de progresso deixa voltar.
 *
 * ENDEREÇO: ainda não sabemos se o PJe exige endereço completo para
 * distribuir (pergunta 23 em PERGUNTAS_JURIDICO.md — o manual do TRF1 mostra
 * abas de Endereços e Meios de contato na aba Partes). Pedimos: pedir e não
 * usar é barato, usar e não ter é caro, e pedir de novo a 15 mil pessoas é
 * inviável.
 */
import { Aviso, Campo, Cartao } from "../componentes/ui";
import type { DadosPessoais } from "../lib/tipos";
import { formatarCpf } from "../lib/validacao";

export function E3Pessoais({
  dados,
  onChange,
}: {
  dados: DadosPessoais;
  onChange: (campo: keyof DadosPessoais, valor: string) => void;
}) {
  return (
    <Cartao
      titulo="Seus dados"
      explicacao="Se algo já vier preenchido, é o que o sindicato tem no cadastro — só
        confira."
    >
      <Campo
        rotulo="Nome completo"
        obrigatorio
        autoComplete="name"
        valor={dados.nome}
        onChange={(v) => onChange("nome", v)}
      />

      <Campo
        rotulo="CPF"
        valor={formatarCpf(dados.cpf)}
        onChange={() => undefined}
        readOnly
        ajuda="Informado na entrada. Para corrigir, volte à etapa 1."
        className="bg-papel text-tinta/70"
      />

      <div className="grid gap-5 sm:grid-cols-2">
        <Campo
          rotulo="Matrícula (SIAPE)"
          valor={dados.matricula}
          onChange={(v) => onChange("matricula", v)}
          inputMode="numeric"
        />
        <Campo
          rotulo="RG"
          valor={dados.rg}
          onChange={(v) => onChange("rg", v)}
        />
      </div>

      <Campo
        rotulo="Data de nascimento"
        obrigatorio
        type="date"
        valor={dados.dataNascimento}
        onChange={(v) => onChange("dataNascimento", v)}
        ajuda="A lei dá prioridade na tramitação a quem tem 60 anos ou mais.
               Sem a data, não temos como pedir essa prioridade para você."
      />

      <div className="grid gap-5 sm:grid-cols-2">
        <Campo
          rotulo="E-mail"
          obrigatorio
          type="email"
          autoComplete="email"
          valor={dados.email}
          onChange={(v) => onChange("email", v)}
          ajuda="É por aqui que avisamos o que foi recebido."
        />
        <Campo
          rotulo="Telefone"
          obrigatorio
          type="tel"
          autoComplete="tel"
          placeholder="(00) 00000-0000"
          valor={dados.telefone}
          onChange={(v) => onChange("telefone", v)}
        />
      </div>

      <h3 className="pt-2 text-sm font-medium text-tinta">Endereço</h3>
      <div className="grid gap-5 sm:grid-cols-3">
        <Campo
          rotulo="CEP"
          obrigatorio
          inputMode="numeric"
          autoComplete="postal-code"
          valor={dados.cep}
          onChange={(v) => onChange("cep", v)}
        />
        <div className="sm:col-span-2">
          <Campo
            rotulo="Logradouro"
            obrigatorio
            autoComplete="street-address"
            valor={dados.logradouro}
            onChange={(v) => onChange("logradouro", v)}
          />
        </div>
      </div>
      <div className="grid gap-5 sm:grid-cols-3">
        <Campo
          rotulo="Número"
          obrigatorio
          valor={dados.numero}
          onChange={(v) => onChange("numero", v)}
        />
        <Campo
          rotulo="Complemento"
          valor={dados.complemento}
          onChange={(v) => onChange("complemento", v)}
        />
        <Campo
          rotulo="Bairro"
          obrigatorio
          valor={dados.bairro}
          onChange={(v) => onChange("bairro", v)}
        />
      </div>
      <div className="grid gap-5 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <Campo
            rotulo="Município"
            obrigatorio
            valor={dados.municipio}
            onChange={(v) => onChange("municipio", v)}
          />
        </div>
        <Campo
          rotulo="UF"
          obrigatorio
          maxLength={2}
          valor={dados.uf}
          onChange={(v) => onChange("uf", v.toUpperCase().slice(0, 2))}
        />
      </div>

      <Aviso tom="neutro">
        Pedimos o endereço porque os tribunais conferem isso em ações
        apresentadas em grande número. Se acabar não sendo necessário, nada é
        perdido — mas pedir de novo depois, a milhares de pessoas, seria.
      </Aviso>
    </Cartao>
  );
}
