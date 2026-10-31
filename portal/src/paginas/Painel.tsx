/**
 * O painel do gestor do sindicato.
 *
 * A MANCHETE VEM PRIMEIRO, E EM NÚMERO GRANDE: "Você não consegue falar com
 * 1.930 dos seus 4.812 filiados." É a primeira frase do produto, sai do
 * arquivo que o próprio sindicato mandou, e é informação que ele não tem
 * hoje. Um painel que abrisse com dez caixinhas de contagem enterraria isso.
 *
 * E a falta é NOMINAL. "Faltam 1.930 e-mails" não diz a quem ligar; a lista
 * diz. Contagem agregada é para saber o tamanho do problema, não para
 * resolvê-lo.
 *
 * DUAS METADES, E ELAS RESPONDEM PERGUNTAS DE SEMANAS DIFERENTES:
 *
 *   completude   o estado da BASE: quem você não alcança, que campo falta.
 *                É a pergunta da primeira semana;
 *   panorama     o que RESOLVER PRIMEIRO: qual decisão destrava mais gente.
 *                É a pergunta da terceira, e nada no produto a respondia.
 *
 * O panorama carrega separado de propósito: se ele falhar, o painel que já
 * existia continua abrindo. Meia tela é melhor que nenhuma, e um painel que
 * some inteiro por causa da metade nova é regressão.
 *
 * SEM MARCA DE ESCRITÓRIO. Quem fala com o filiado é o sindicato: avisar
 * milhares de pessoas que elas podem processar a União, com a marca de um
 * escritório, é a figura que o Provimento 205/2021 do CFOAB descreve como
 * captação por estímulo ao litígio. Ver PRODUTO_SINDICATOS.md, §4.
 */
import { useEffect, useState } from "react";

import { Aviso, Cartao } from "../componentes/ui";
import * as api from "../lib/envio";
import { fracao, pessoas, presosNoTribunal, primeiroAcionavel } from "../lib/painel";
import { Portao } from "./Portao";

function Numero({
  rotulo,
  valor,
  tom = "normal",
}: {
  rotulo: string;
  valor: number;
  tom?: "normal" | "atencao";
}) {
  return (
    <div className="rounded-md border border-borda bg-papel p-4">
      <p
        className={
          tom === "atencao"
            ? "text-2xl font-semibold text-acento"
            : "text-2xl font-semibold text-tinta"
        }
      >
        {valor}
      </p>
      <p className="mt-1 text-sm text-tinta/70">{rotulo}</p>
    </div>
  );
}

/** O que o sindicato resolve primeiro. É esta a parte que vale a reunião. */
function OQueResolverPrimeiro({ p }: { p: api.Panorama }) {
  const alvo = primeiroAcionavel(p.gargalos);
  const noTribunal = presosNoTribunal(p.gargalos);
  return (
    <Cartao
      titulo="O que resolver primeiro"
      explicacao={p.manchete}
    >
      {alvo ? (
        <div className="rounded-md border border-acento/40 bg-acento/5 p-5">
          <p className="text-sm font-semibold uppercase tracking-wide text-acento">
            Depende do sindicato
          </p>
          <p className="mt-2 text-[17px] leading-relaxed text-tinta">
            <strong>{alvo.o_que}</strong> destrava {pessoas(alvo.pessoas)}.
          </p>
          {alvo.exemplos.length ? (
            <p className="mt-2 text-sm text-tinta/70">
              Por exemplo: {alvo.exemplos.slice(0, 3).join("; ")}
              {alvo.pessoas > 3 ? ", entre outros" : ""}.
            </p>
          ) : null}
        </div>
      ) : (
        <Aviso tom="neutro">
          Não há nada parado esperando decisão do sindicato agora.
        </Aviso>
      )}

      {/* OS DOIS NÚMEROS. A base é o que o sindicato mandou; os cadastrados
          são de quem já temos documento. Mostrar só o segundo era o que
          fazia um sindicato de 4.812 filiados ver um painel de 200. */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-md border border-borda bg-papel p-4">
          <p className="text-2xl font-semibold text-tinta">{p.pessoas}</p>
          <p className="mt-1 text-sm text-tinta/70">
            pessoas na base (planilha + portal)
          </p>
        </div>
        <div className="rounded-md border border-borda bg-papel p-4">
          <p className="text-2xl font-semibold text-tinta">{p.cadastrados}</p>
          <p className="mt-1 text-sm text-tinta/70">
            já mandaram documento pelo portal
          </p>
        </div>
      </div>

      {noTribunal > 0 ? (
        <Aviso tom="neutro">
          <strong>{pessoas(noTribunal)}</strong> dependem de um tribunal
          julgar. Não é com o sindicato nem com elas — e cobrar andamento não
          antecipa.
        </Aviso>
      ) : null}

      {p.gargalos.length ? (
        <div>
          <p className="text-[15px] font-medium text-tinta">
            Tudo o que está parado, e quem destrava
          </p>
          <p className="mt-1 text-sm text-tinta/70">
            Do que segura mais gente para o que segura menos.
          </p>
          <div className="mt-2 space-y-1">
            {p.gargalos.map((g) => (
              <div
                key={`${g.quem}-${g.o_que}`}
                className="flex items-baseline justify-between gap-4 border-b border-borda py-1.5 text-[15px]"
              >
                <span className="text-tinta/80">
                  {g.o_que}
                  <span className="ml-2 text-[13px] text-tinta/50">
                    {g.titulo}
                  </span>
                </span>
                <span className="shrink-0 font-medium text-tinta">
                  {g.pessoas}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {p.por_acao.length ? (
        <div>
          <p className="text-[15px] font-medium text-tinta">
            Quem a sua base alcança, por ação
          </p>
          <div className="mt-2 space-y-2">
            {p.por_acao.map((a) => (
              <div
                key={a.acao}
                className="rounded-md border border-borda bg-papel p-3"
              >
                <p className="text-[15px] text-tinta">{a.rotulo}</p>
                <p className="mt-1 text-sm text-tinta/70">
                  Faz parte: {fracao(a.participam, p.pessoas)} · ainda a
                  conferir: {a.indeterminados} · fora: {a.nao_participam}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* O limite vem do servidor e fica na tela. Um diretor que supõe que
          os documentos foram lidos confia numa coluna que ninguém conferiu. */}
      <Aviso tom="alerta">{p.limite}</Aviso>
    </Cartao>
  );
}

export function Painel({ entidade }: { entidade: string }) {
  const [token, setToken] = useState("");
  const [dados, setDados] = useState<api.PainelDoGestor | null>(null);
  const [panorama, setPanorama] = useState<api.Panorama | null>(null);
  const [erroPanorama, setErroPanorama] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!token) return;
    void api
      .verPanorama(entidade, token)
      .then(setPanorama)
      .catch((e) =>
        setErroPanorama(
          e instanceof Error ? e.message : "não foi possível apurar",
        ),
      );
  }, [token, entidade]);

  useEffect(() => {
    if (!token) return;
    void api
      .verCompletude(entidade, token)
      .then(setDados)
      .catch((e) =>
        setErro(e instanceof Error ? e.message : "não foi possível abrir"),
      );
  }, [entidade, token]);

  if (!token) {
    return (
      <Portao
        entidade={entidade}
        titulo="Painel do sindicato"
        explicacao="Para gestores. O código vai para o e-mail cadastrado — não há senha."
        onToken={setToken}
      />
    );
  }

  if (erro) {
    return (
      <Cartao titulo="Painel do sindicato">
        <Aviso tom="alerta">{erro}</Aviso>
      </Cartao>
    );
  }

  if (!dados) {
    return (
      <Cartao titulo="Painel do sindicato">
        <Aviso tom="neutro">Carregando…</Aviso>
      </Cartao>
    );
  }

  const r = dados.retrato;
  const faltas = Object.entries(r.falta_por_campo);

  return (
    <div className="space-y-6">
      {panorama ? <OQueResolverPrimeiro p={panorama} /> : null}
      {erroPanorama ? (
        <Aviso tom="alerta">
          Não foi possível apurar o que resolver primeiro: {erroPanorama}. O
          retrato da base abaixo continua valendo.
        </Aviso>
      ) : null}

    <Cartao titulo={dados.nome || "Painel do sindicato"}>
      {/* A manchete, antes de tudo. */}
      <div className="rounded-md border border-acento/40 bg-acento/5 p-5">
        <p className="text-[17px] leading-relaxed text-tinta">
          {dados.manchete}
        </p>
      </div>

      {!dados.tem_acervo ? (
        <Aviso tom="alerta">
          <p>
            <strong>Você ainda não enviou a sua base de filiados.</strong>
          </p>
          <p className="mt-2">
            Os números abaixo contam só quem se cadastrou pelo portal. Com a
            sua planilha — do jeito que ela estiver — o painel passa a mostrar
            a base inteira, e quem falta.
          </p>
        </Aviso>
      ) : null}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Numero rotulo="filiados no acervo" valor={r.total} />
        <Numero
          rotulo="você não alcança"
          valor={r.inalcancaveis}
          tom="atencao"
        />
        <Numero rotulo="cadastrados no portal" valor={r.cadastrados} />
        <Numero rotulo="sem cadastro" valor={r.sem_cadastro} />
        <Numero rotulo="acompanhando processo" valor={r.acompanhando} />
        <Numero rotulo="querem aviso por e-mail" valor={r.querem_aviso} />
      </div>

      {r.fora_do_acervo > 0 ? (
        <Aviso tom="neutro">
          <strong>{r.fora_do_acervo}</strong> pessoa(s) se cadastraram pelo
          portal e não constam da sua planilha. Provavelmente filiados novos —
          vale conferir antes da próxima exportação.
        </Aviso>
      ) : null}

      {r.divergentes > 0 ? (
        <Aviso tom="alerta">
          <strong>{r.divergentes}</strong> linha(s) da sua planilha têm o mesmo
          CPF com dados diferentes. A gente não escolhe qual vale — a ordem na
          planilha não decide isso. Essa decisão é do sindicato.
        </Aviso>
      ) : null}

      {faltas.length ? (
        <div>
          <p className="text-[15px] font-medium text-tinta">O que falta</p>
          <div className="mt-2 space-y-1">
            {faltas.map(([campo, quantos]) => (
              <div
                key={campo}
                className="flex items-baseline justify-between border-b border-borda py-1 text-[15px]"
              >
                <span className="text-tinta/80">{campo}</span>
                <span className="font-medium text-tinta">{quantos}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {dados.inalcancaveis.length ? (
        <div>
          <p className="text-[15px] font-medium text-tinta">
            Quem você não alcança, e por quê
          </p>
          <p className="mt-1 text-sm text-tinta/70">
            Contagem não diz a quem ligar. Esta lista diz.
          </p>
          <div className="mt-2 space-y-1">
            {dados.inalcancaveis.slice(0, 50).map((p) => (
              <div key={p.chave} className="border-b border-borda py-1 text-sm">
                <span className="text-tinta">
                  {p.nome || "(sem nome no acervo)"}
                </span>
                <span className="ml-2 text-tinta/70">{p.motivo}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <Aviso tom="neutro">
        A movimentação dos processos é atualizada sozinha, com cerca de um dia
        de atraso — é o que a base pública do CNJ entrega.{" "}
        <strong>Não é intimação e não serve para contar prazo.</strong>
      </Aviso>
    </Cartao>
    </div>
  );
}
