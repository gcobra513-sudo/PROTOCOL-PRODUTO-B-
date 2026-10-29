/**
 * Termo de privacidade e canal para direitos do titular.
 *
 * TRÊS DECISÕES QUE NÃO SÃO DE REDAÇÃO, SÃO DE SUBSTÂNCIA:
 *
 * 1. **A base legal não é consentimento, e isso muda a tela.** O tratamento
 *    aqui existe para instruir e propor ação judicial — é exercício regular
 *    de direitos em processo (LGPD, art. 7º, VI) e execução de contrato com o
 *    escritório. Pedir "aceito os termos" num checkbox sugeriria que a pessoa
 *    pode retirar o consentimento e apagar tudo no meio de um processo
 *    judicial, o que não é verdade. Então aqui há INFORMAÇÃO clara e
 *    acessível, não uma caixa de aceite que cria promessa falsa.
 *
 *    A declaração de ciência e iniciativa da etapa 7 é outra coisa: é sobre a
 *    ação, não sobre dados.
 *
 * 2. **Não inventamos o controlador.** Quem é o controlador, o encarregado e
 *    o canal de contato depende de como o escritório e o sindicato se
 *    organizarem — e provavelmente há operação conjunta. Os campos saem
 *    marcados como pendentes, e um teste reprova se o portal subir para
 *    produção com eles em branco.
 *
 * 3. **O que está escrito aqui é o que o sistema faz de verdade.** Cada linha
 *    abaixo corresponde a comportamento que existe no código — inclusive o
 *    fato de que, nesta versão, os documentos são lidos no navegador e não
 *    saem do aparelho da pessoa. Termo que descreve um sistema que não existe
 *    é pior que termo nenhum.
 */
import { X } from "lucide-react";

import { Aviso, Botao } from "./ui";

/** Preencher antes de usar com gente de verdade. */
export const CONTROLADOR = {
  nome: "[RAZÃO SOCIAL DO ESCRITÓRIO]",
  cnpj: "[CNPJ]",
  encarregado: "[NOME DO ENCARREGADO DE DADOS]",
  canal: "[E-MAIL PARA DIREITOS DO TITULAR]",
  sindicato: "[NOME DA ENTIDADE SINDICAL]",
};

export function temPendencia(): boolean {
  return Object.values(CONTROLADOR).some((v) => v.startsWith("["));
}

export function Privacidade({ onFechar }: { onFechar: () => void }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="privacidade-titulo"
      className="fixed inset-0 z-50 overflow-y-auto bg-tinta/40 p-4 sm:p-8"
    >
      <div className="mx-auto max-w-2xl rounded-lg border border-borda bg-carta">
        <div className="flex items-start justify-between gap-4 border-b border-borda p-5">
          <h2
            id="privacidade-titulo"
            className="text-lg font-semibold text-tinta"
          >
            Como tratamos os seus dados
          </h2>
          <Botao tipo="discreto" tamanho="pequeno" onClick={onFechar}>
            <X className="h-4 w-4" aria-hidden="true" />
            Fechar
          </Botao>
        </div>

        <div className="space-y-5 p-5 text-[15px] leading-relaxed text-tinta/85">
          {temPendencia() ? (
            <Aviso tom="alerta">
              <strong>Protótipo:</strong> a identificação do responsável e o
              canal de contato ainda não foram preenchidos. Antes de usar com
              pessoas de verdade, isso é obrigatório.
            </Aviso>
          ) : null}

          <section>
            <h3 className="font-semibold text-tinta">Quem é o responsável</h3>
            <p className="mt-1">
              {CONTROLADOR.nome}, CNPJ {CONTROLADOR.cnpj}, em conjunto com{" "}
              {CONTROLADOR.sindicato} no que se refere à relação com os
              filiados. Encarregado de dados: {CONTROLADOR.encarregado}.
            </p>
          </section>

          <section>
            <h3 className="font-semibold text-tinta">Por que pedimos</h3>
            <p className="mt-1">
              Para analisar se existe título a executar, montar a petição e
              apresentá-la em juízo. A base legal é o{" "}
              <strong>exercício regular de direitos em processo judicial</strong>{" "}
              e a <strong>execução do contrato</strong> com o escritório — não
              é consentimento. Isso tem uma consequência prática que você deve
              saber: <strong>uma vez que a ação for apresentada, não é
              possível apagar os dados que já constam do processo</strong>,
              porque eles passam a integrar os autos.
            </p>
          </section>

          <section>
            <h3 className="font-semibold text-tinta">O que pedimos</h3>
            <ul className="mt-1 space-y-1">
              <li>• identificação: nome, CPF, RG, matrícula</li>
              <li>• contato: e-mail, telefone, endereço</li>
              <li>• situação funcional: cargo, datas, unidade</li>
              <li>• o número do seu processo</li>
              <li>
                • documentos: procuração, identidade, comprovante de
                residência, sentença, certidão de trânsito e, se tiver, fichas
                financeiras
              </li>
            </ul>
            <p className="mt-2">
              Não pedimos dado de saúde, de origem racial, de religião, de
              opinião política nem biométrico.
            </p>
          </section>

          <section>
            <h3 className="font-semibold text-tinta">
              O que acontece nesta versão do portal
            </h3>
            <p className="mt-1">
              Nesta versão, <strong>nada é transmitido</strong>. O que você
              preenche fica salvo apenas neste navegador, neste aparelho. Os
              documentos são lidos <strong>aqui mesmo</strong> para conferir se
              o texto é legível e se o seu CPF aparece neles — eles não saem do
              seu aparelho para isso.
            </p>
            <p className="mt-2">
              Quando o envio ao escritório for ligado, este texto será
              atualizado antes, e você verá a mudança.
            </p>
          </section>

          <section>
            <h3 className="font-semibold text-tinta">Com quem compartilhamos</h3>
            <p className="mt-1">
              Com o Poder Judiciário, no que a petição exigir — e isso é
              público, porque o processo é público, salvo sigilo. Com a entidade
              sindical, para conferir a filiação. Não vendemos nem cedemos
              dados para publicidade.
            </p>
          </section>

          <section>
            <h3 className="font-semibold text-tinta">Por quanto tempo</h3>
            <p className="mt-1">
              Enquanto o processo durar, e depois pelo prazo em que o
              escritório é obrigado a guardar documentos de clientes. Se você
              desistir antes de a ação ser apresentada, os documentos são
              descartados.
            </p>
          </section>

          <section>
            <h3 className="font-semibold text-tinta">Seus direitos</h3>
            <p className="mt-1">
              Você pode pedir confirmação do tratamento, acesso, correção,
              portabilidade e informação sobre compartilhamentos, e pode se
              opor ao tratamento. Pode também pedir eliminação —{" "}
              <strong>com o limite acima</strong>: o que já está nos autos de
              um processo não pode ser retirado pelo escritório.
            </p>
            <p className="mt-2">
              Para exercer qualquer um deles:{" "}
              <strong>{CONTROLADOR.canal}</strong>.
            </p>
          </section>

          <p className="border-t border-borda pt-4 text-sm text-tinta/60">
            Se algo aqui não corresponder ao que o sistema faz, é defeito
            nosso. Avise pelo canal acima.
          </p>
        </div>
      </div>
    </div>
  );
}
