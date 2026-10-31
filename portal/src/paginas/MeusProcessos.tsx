/**
 * A tela que mata o telefonema.
 *
 * A frase central DEVE ser "nada novo desde 14 de outubro" — quem liga para
 * o sindicato liga para ouvir isso, e em nove de cada dez vezes é essa a
 * resposta.
 *
 * AGORA ELA ESTÁ AQUI. A tela sabia a data do último MOVIMENTO, não a da
 * última COLETA — e "nada novo" só é verdade em relação à segunda. Com o
 * agendador registrando cada execução, a API passou a expor `conferido_em`,
 * e a frase que importa pode finalmente ser dita.
 *
 * E quando NUNCA conferimos, a tela diz isso em vez de calar: silêncio aqui
 * seria lido como "não mudou nada", que é o oposto da verdade.
 *
 * E ela diz o limite na própria tela, não no rodapé: movimentação não é
 * intimação. Esconder isso pouparia uma linha e criaria a chance de alguém
 * perder prazo confiando em nós.
 */
import { useEffect, useState } from "react";

import { Aviso, Cartao } from "../componentes/ui";
import { Portao } from "./Portao";
import * as api from "../lib/envio";
import { formatarProcesso } from "../lib/validacao";

function soData(iso: string): string {
  // "2026-07-10T13:31:55.000Z" -> "10/07/2026". Sem Intl para não depender
  // do locale do aparelho: o mesmo processo tem de ler igual em todo lugar.
  const [ano, mes, dia] = (iso.slice(0, 10) || "").split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : iso;
}

export function MeusProcessos({ entidade }: { entidade: string }) {
  const [token, setToken] = useState("");
  const [dados, setDados] = useState<api.MeusProcessos | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!token) return;
    void api
      .meusProcessos(token)
      .then(setDados)
      .catch((e) =>
        setErro(e instanceof Error ? e.message : "não foi possível consultar"),
      );
  }, [token]);

  if (!token) {
    return (
      <Portao
        entidade={entidade}
        titulo="Meus processos"
        explicacao="Veja o que andou nos processos que você informou. Sem senha: o código vai para o e-mail que o seu sindicato tem em cadastro."
        onToken={setToken}
      />
    );
  }

  if (erro) {
    return (
      <Cartao titulo="Meus processos">
        <Aviso tom="alerta">{erro}</Aviso>
      </Cartao>
    );
  }

  if (!dados) {
    return (
      <Cartao titulo="Meus processos">
        <Aviso tom="neutro">Carregando…</Aviso>
      </Cartao>
    );
  }

  if (dados.processos.length === 0) {
    return (
      <Cartao titulo="Meus processos">
        <Aviso tom="neutro">
          <p>
            <strong>Você ainda não informou nenhum processo.</strong>
          </p>
          <p className="mt-2">
            Para a gente acompanhar, informe o número no cadastro — está na sua
            sentença, em qualquer intimação que você recebeu, ou com o advogado
            que cuidou da ação.
          </p>
        </Aviso>
      </Cartao>
    );
  }

  return (
    <Cartao
      titulo="Meus processos"
      explicacao={
        dados.conferido_em
          ? `A gente confere sozinho. Última conferência: ${soData(dados.conferido_em)}.`
          : "A gente confere a movimentação sozinho. Você não precisa ligar para perguntar se andou."
      }
    >
      {!dados.conferido_em ? (
        <Aviso tom="alerta">
          <strong>Ainda não conferimos o tribunal.</strong> O que está abaixo
          é o que já tínhamos. Enquanto não houver uma conferência, a
          ausência de novidade aqui não quer dizer que nada mudou.
        </Aviso>
      ) : null}
      <div className="space-y-3">
        {dados.processos.map((p) => (
          <div
            key={p.numero}
            className="rounded-md border border-borda bg-papel p-4"
          >
            <p className="font-mono text-[15px] text-tinta">
              {formatarProcesso(p.numero)}
            </p>
            {p.tribunal ? (
              <p className="mt-1 text-sm text-tinta/60">{p.tribunal}</p>
            ) : null}

            {p.ultimo_movimento ? (
              <p className="mt-3 text-[15px] text-tinta">
                Último andamento em{" "}
                <strong>{soData(p.ultimo_movimento.data)}</strong>:{" "}
                {p.ultimo_movimento.nome}
                {p.ultimo_movimento.grau !== "?"
                  ? ` (${p.ultimo_movimento.grau})`
                  : ""}
              </p>
            ) : (
              <p className="mt-3 text-[15px] text-tinta/70">
                Ainda não temos movimentação deste processo. Pode ser que ele
                tenha sido protocolado nos últimos dias — a base do CNJ tem
                cerca de um dia de atraso.
              </p>
            )}
          </div>
        ))}
      </div>

      {/* O limite na tela, não no rodapé. */}
      <Aviso tom="alerta">{dados.limite}</Aviso>
    </Cartao>
  );
}

