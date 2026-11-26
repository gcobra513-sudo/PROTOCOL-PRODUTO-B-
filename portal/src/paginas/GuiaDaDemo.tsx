/**
 * O GUIA DA DEMONSTRAÇÃO: por onde começar, com que acesso entrar e o que
 * dizer em cada tela.
 *
 * Existe porque a demonstração, sozinha, não se explicava. O botão "Ver a
 * demonstração" caía no começo do cadastro do filiado — um formulário —, e
 * quem ia apresentar numa reunião precisava saber de cor em que ordem abrir
 * as telas e qual CPF fictício entra em qual. Aqui isso está escrito, na
 * ordem da conversa com uma diretoria (`lib/demonstracao.ts`).
 *
 * SÓ EXISTE SE O SERVIDOR DISSER QUE HÁ DEMONSTRAÇÃO. Num servidor de
 * verdade esta página diz que não há nada para mostrar, e não lista acesso
 * nenhum: os CPFs vêm do servidor, nunca daqui.
 */
import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";

import { acessosDaDemonstracao, roteiroDaDemonstracao, type Parada } from "../lib/demonstracao";
import * as api from "../lib/envio";
import { Abertura, BotaoClaro, Moldura, Secao } from "./Publica";

export const DEMONSTRACAO = "demo-sindicato";
export const GUIA = "?pagina=demonstracao";

function CartaoDaParada({ numero, parada }: { numero: number; parada: Parada }) {
  const [copiado, setCopiado] = useState(false);
  async function copiar() {
    try {
      await navigator.clipboard.writeText(parada.cpf);
      setCopiado(true);
    } catch {
      // Sem permissão de área de transferência: o CPF está escrito ao lado.
      setCopiado(false);
    }
  }
  return (
    <li className="rounded-xl bg-carta p-6 shadow-cartao sm:p-8">
      <div className="flex items-start gap-4">
        <span
          aria-hidden="true"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-acento text-lg font-bold text-carta"
        >
          {numero}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-xl font-bold text-tinta">{parada.titulo}</h3>
          <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-[15px] text-tinta/75">
            <span>
              Entre como <strong className="text-tinta">{parada.quem}</strong>, com o CPF de exemplo
            </span>
            <code className="rounded bg-papel px-2 py-1 text-base font-semibold text-tinta">
              {parada.cpf}
            </code>
            <button
              type="button"
              onClick={() => void copiar()}
              className="rounded border border-tinta/20 px-2 py-1 text-sm hover:bg-papel"
            >
              {copiado ? "Copiado" : "Copiar"}
            </button>
          </p>

          <h4 className="mt-5 text-sm font-semibold uppercase tracking-wide text-tinta/60">
            O que mostrar
          </h4>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-[15px] leading-relaxed text-tinta/80">
            {parada.mostrar.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ol>

          <h4 className="mt-5 text-sm font-semibold uppercase tracking-wide text-tinta/60">
            O que dizer
          </h4>
          <p className="mt-2 rounded-lg bg-lilas px-4 py-3 text-[16px] leading-relaxed text-tinta">
            {parada.falar}
          </p>

          {/* EM OUTRA ABA: o guia fica aberto ao lado, e quem apresenta
              volta a ele sem perder a tela que estava mostrando. */}
          <a
            href={parada.link}
            target="_blank"
            rel="noreferrer"
            className="mt-6 inline-flex h-12 items-center gap-2 rounded-lg bg-acento px-5 text-[15px] font-semibold text-carta hover:bg-acento/90"
          >
            {parada.botao} <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </a>
        </div>
      </div>
    </li>
  );
}

export function GuiaDaDemo({ onPrivacidade }: { onPrivacidade: () => void }) {
  const [paradas, setParadas] = useState<Parada[] | null>(null);

  useEffect(() => {
    if (!api.servidorLigado()) {
      setParadas([]);
      return;
    }
    void api
      .verEntidade(DEMONSTRACAO)
      .then((e) => setParadas(roteiroDaDemonstracao(acessosDaDemonstracao(e), DEMONSTRACAO)))
      .catch(() => setParadas([]));
  }, []);

  return (
    <Moldura atual="demonstracao" onPrivacidade={onPrivacidade}>
      <Abertura
        sobre="Demonstração"
        titulo="Guia da demonstração"
        acoes={<BotaoClaro href="#roteiro">Começar pelo passo 1</BotaoClaro>}
      >
        Um sindicato de mentira, com filiados fictícios, para ver o portal
        funcionando. Abaixo está a ordem para apresentar, o acesso de cada
        tela e o que dizer em cada uma.
      </Abertura>

      <Secao id="antes" titulo="Antes de começar">
        <ul className="grid gap-4 md:grid-cols-3">
          <li className="rounded-xl bg-carta p-6 text-[15px] leading-relaxed text-tinta/80 shadow-cartao">
            <strong className="block text-tinta">Tudo aqui é fictício.</strong>
            Nomes, CPFs, e-mails, documentos, a carreira e a ação são de
            exemplo. Não envie documento de verdade nesta página.
          </li>
          <li className="rounded-xl bg-carta p-6 text-[15px] leading-relaxed text-tinta/80 shadow-cartao">
            <strong className="block text-tinta">Entre com um toque.</strong>
            Na demonstração cada perfil tem um botão “Entrar como”, e cada um
            cai na própria área. No portal de verdade a pessoa entra com o
            CPF e um código que chega no e-mail cadastrado pelo sindicato.
          </li>
          <li className="rounded-xl bg-carta p-6 text-[15px] leading-relaxed text-tinta/80 shadow-cartao">
            <strong className="block text-tinta">Abra o link um minuto antes.</strong>
            Depois de um tempo parada, a demonstração demora cerca de um
            minuto para acordar, e recomeça do zero.
          </li>
        </ul>
      </Secao>

      <Secao id="roteiro" titulo="O roteiro, na ordem">
        {paradas === null ? (
          <p className="text-tinta/70">Carregando…</p>
        ) : paradas.length === 0 ? (
          <p className="rounded-xl bg-carta p-6 text-[15px] text-tinta/80 shadow-cartao">
            Este endereço não tem uma demonstração para mostrar.
          </p>
        ) : (
          <ol className="space-y-5">
            {paradas.map((p, i) => (
              <CartaoDaParada key={p.id} numero={i + 1} parada={p} />
            ))}
          </ol>
        )}
      </Secao>

      {paradas && paradas.length > 0 ? (
        <Secao id="perguntas" titulo="O que vão perguntar, e a resposta">
          <dl className="space-y-4">
            <div className="rounded-xl bg-carta p-6 shadow-cartao">
              <dt className="text-[17px] font-semibold text-tinta">
                “Essa ação existe?”
              </dt>
              <dd className="mt-2 text-[15px] leading-relaxed text-tinta/80">
                Não. A carreira e a ação da demonstração são inventadas, e a
                tela diz isso no nome. No portal de verdade, uma ação só
                aparece como conferida depois que um advogado confere e
                assina. Antes disso o portal mostra a pendência e não diz
                que alguém pode.
              </dd>
            </div>
            <div className="rounded-xl bg-carta p-6 shadow-cartao">
              <dt className="text-[17px] font-semibold text-tinta">
                “E o valor que cada um tem a receber?”
              </dt>
              <dd className="mt-2 text-[15px] leading-relaxed text-tinta/80">
                O portal mostra uma apuração preliminar e bruta quando tem
                as duas coisas: a ficha financeira do filiado, enviada pelo
                sindicato, e a verba conferida por advogado. É o percentual
                da verba sobre a base de cada mês, sem correção, juros nem
                imposto, e isso vem escrito junto do número. Sem a ficha,
                ele diz o que falta e não estima.
              </dd>
            </div>
            <div className="rounded-xl bg-carta p-6 shadow-cartao">
              <dt className="text-[17px] font-semibold text-tinta">
                “O Proto é uma inteligência artificial?”
              </dt>
              <dd className="mt-2 text-[15px] leading-relaxed text-tinta/80">
                Não. Ele responde sobre uma lista fechada de assuntos, só com
                o que está no cadastro, e diz quando não sabe. Nenhum dado de
                filiado é enviado a serviço de fora.
              </dd>
            </div>
            <div className="rounded-xl bg-carta p-6 shadow-cartao">
              <dt className="text-[17px] font-semibold text-tinta">
                “O que o sindicato precisa para começar?”
              </dt>
              <dd className="mt-2 text-[15px] leading-relaxed text-tinta/80">
                A planilha de filiados que já tem, do jeito que está.
              </dd>
            </div>
          </dl>
        </Secao>
      ) : null}
    </Moldura>
  );
}
