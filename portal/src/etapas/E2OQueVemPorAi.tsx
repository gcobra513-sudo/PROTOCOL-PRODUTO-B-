/**
 * Etapa 2 — o que vai ser pedido, antes de começar.
 *
 * Parece tela de enfeite e é das mais úteis: a pessoa junta os documentos
 * ANTES de começar, em vez de abandonar no meio por não ter um papel em mãos.
 * Com estimativa honesta de tempo — "cerca de 15 minutos, se você já tiver os
 * documentos" —, porque estimativa otimista gera desistência quando estoura.
 */
import { Clock, FileText, Save } from "lucide-react";

import { Aviso, Cartao } from "../componentes/ui";
import { DOCUMENTOS } from "../lib/tipos";

export function E2OQueVemPorAi({
  rascunhoLigado,
  onVerPrivacidade,
}: {
  rascunhoLigado: boolean;
  onVerPrivacidade: () => void;
}) {
  return (
    <Cartao
      titulo="O que vamos pedir"
      explicacao="Dê uma olhada antes de começar. Separar os documentos agora evita
        ter que parar no meio."
    >
      <Aviso tom="neutro">
        <span className="flex items-start gap-2">
          <Clock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            Cerca de <strong>15 minutos</strong>, se você já tiver os
            documentos em mãos.
          </span>
        </span>
      </Aviso>

      <div>
        <h3 className="text-sm font-medium text-tinta">
          Informações que vamos pedir
        </h3>
        <ul className="mt-2 space-y-1.5 text-[15px] text-tinta/80">
          <li>• Seus dados pessoais e endereço</li>
          <li>• Cargo, situação (ativo, aposentado ou pensionista) e datas</li>
          <li>
            • <strong>O número do seu processo</strong> — o da sua sentença. É
            a informação mais importante de todas.
          </li>
        </ul>
      </div>

      <div>
        <h3 className="text-sm font-medium text-tinta">Documentos</h3>
        <ul className="mt-2 space-y-2">
          {DOCUMENTOS.map((d) => (
            <li key={d.tipo} className="flex items-start gap-2">
              <FileText
                className="mt-1 h-4 w-4 shrink-0 text-tinta/40"
                aria-hidden="true"
              />
              <span className="text-[15px] text-tinta/80">
                <strong className="text-tinta">{d.rotulo}</strong>
                {d.obrigatorio ? "" : " (se tiver)"} — {d.porque}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-tinta/60">
          Prefira <strong>PDF</strong>. Foto de celular normalmente não serve,
          porque o sistema precisa <em>ler</em> o texto do documento — e
          avisamos na hora se não der.
        </p>
      </div>

      <Aviso tom="neutro">
        Antes de começar, vale saber{" "}
        <button
          type="button"
          onClick={onVerPrivacidade}
          className="text-acento underline underline-offset-2 hover:no-underline"
        >
          como tratamos os seus dados
        </button>{" "}
        — inclusive um ponto importante: depois que a ação for apresentada, o
        que já está no processo não pode ser apagado.
      </Aviso>

      <Aviso tom={rascunhoLigado ? "bom" : "alerta"}>
        <span className="flex items-start gap-2">
          <Save className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {rascunhoLigado ? (
            <span>
              Seu preenchimento é salvo <strong>neste navegador</strong> a cada
              passo. Pode fechar e voltar depois, no mesmo aparelho.
            </span>
          ) : (
            <span>
              <strong>Atenção:</strong> o seu navegador está bloqueando o
              armazenamento, então <strong>não</strong> vamos conseguir salvar
              o preenchimento. Se fechar a aba, perde o que preencheu. Tente
              sair do modo de navegação privada.
            </span>
          )}
        </span>
      </Aviso>
    </Cartao>
  );
}
