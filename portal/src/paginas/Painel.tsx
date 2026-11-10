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

import { Aviso, Botao, Campo, Cartao } from "../componentes/ui";
import * as api from "../lib/envio";
import {
  frasesDaMudanca,
  fracao,
  pessoas,
  presosNoTribunal,
  primeiroAcionavel,
  resumoDaFilaDeLeitura,
  resumoDasMudancas,
  resumoDoApagamento,
} from "../lib/painel";
import { conferirCpf, formatarCpf } from "../lib/validacao";
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


/** Apagamento a pedido do titular (LGPD art. 18, VI).
 *
 * POR QUE ESTA TELA EXISTE: a spec dizia "o sindicato apaga pelo painel", e
 * a primeira entrega não tinha tela nenhuma — só a rota e uma ferramenta de
 * linha de comando. Recurso que só `curl` alcança não chega a quem ele
 * serve, e passava por pronto na contagem.
 *
 * TRÊS DECISÕES DE DESENHO, E AS TRÊS SÃO SOBRE O QUE NÃO SE DESFAZ:
 *
 * 1. Fica RECOLHIDA. Não é o trabalho do painel, é a exceção dele, e um
 *    formulário de apagar sempre aberto ao lado do retrato da base é um
 *    clique errado esperando acontecer.
 * 2. CONFIRMAÇÃO EM DUAS ETAPAS, repetindo em palavras o que vai acontecer.
 *    Não há desfazer: o diário é redigido, o disco é apagado. A confirmação
 *    é a única chance.
 * 3. O RESULTADO É O DO SERVIDOR, inclusive quando ele diz que sobrou coisa.
 *    `resumoDoApagamento` carrega essa regra, e o teste dela é o que impede
 *    esta tela de pintar de verde um apagamento que não terminou.
 */
/** O mesmo teto que o servidor aplica (`apagamento.TETO_DO_TEXTO`).
 *
 *  O servidor RECUSA com 400 em vez de cortar, porque o registro de um
 *  apagamento precisa guardar exatamente o que o gestor escreveu. Repetir o
 *  número aqui evita que ele descubra o limite levando um erro depois de
 *  escrever — e se os dois divergirem, quem manda é o servidor: a tela erra
 *  para o lado de deixar digitar menos. */
const TETO_DO_TEXTO = 500;

function ApagarAPedido({
  entidade,
  token,
  jaApagados,
}: {
  entidade: string;
  token: string;
  jaApagados: number;
}) {
  const [aberto, setAberto] = useState(false);
  const [cpf, setCpf] = useState("");
  const [motivo, setMotivo] = useState("");
  const [pedidoPor, setPedidoPor] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [indo, setIndo] = useState(false);
  const [erro, setErro] = useState("");
  const [saida, setSaida] = useState<api.ResultadoDoApagamento | null>(null);

  const problemas = cpf ? conferirCpf(cpf) : [];
  const podeSeguir =
    cpf !== "" && problemas.length === 0 && pedidoPor.trim() !== "";

  function limpar() {
    setCpf("");
    setMotivo("");
    setPedidoPor("");
    setConfirmando(false);
    setErro("");
  }

  async function apagar() {
    setIndo(true);
    setErro("");
    try {
      const r = await api.apagarFiliado(entidade, token, {
        cpf,
        motivo,
        pedidoPor,
      });
      setSaida(r);
      limpar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível concluir");
      setConfirmando(false);
    } finally {
      setIndo(false);
    }
  }

  const resumo = saida ? resumoDoApagamento(saida) : null;

  return (
    <Cartao
      titulo="Pedido de apagamento de um filiado"
      explicacao={
        <>
          Quando um filiado pede, por escrito, que o sindicato apague os dados
          dele (LGPD, art. 18, VI). <strong>Não há desfazer.</strong>{" "}
          {jaApagados > 0
            ? `${pessoas(jaApagados)} da sua planilha já pediram, e por isso ` +
              "não aparecem nas contagens acima."
            : ""}
        </>
      }
    >
      {resumo ? (
        <div className="space-y-3">
          <Aviso tom={resumo.terminou ? "bom" : "alerta"}>
            {resumo.frase}
          </Aviso>
          {resumo.linhas.length ? (
            <div>
              <p className="text-[15px] font-medium text-tinta">O que saiu</p>
              <div className="mt-2 space-y-1">
                {resumo.linhas.map((linha) => (
                  <div
                    key={linha}
                    className="border-b border-borda py-1 text-sm text-tinta/80"
                  >
                    {linha}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-tinta/70">
              Não havia nada desta pessoa nesta entidade. O pedido fica
              registrado de todo modo, e a próxima planilha que você mandar
              não vai recriá-la.
            </p>
          )}
          {resumo.nota ? <Aviso tom="neutro">{resumo.nota}</Aviso> : null}
          <Botao
            tipo="secundario"
            onClick={() => {
              setSaida(null);
              setAberto(false);
            }}
          >
            Fechar
          </Botao>
        </div>
      ) : !aberto ? (
        <Botao tipo="secundario" onClick={() => setAberto(true)}>
          Atender um pedido de apagamento
        </Botao>
      ) : confirmando ? (
        <div className="space-y-4">
          <Aviso tom="alerta">
            <strong>Confirme antes de seguir. Isto não se desfaz.</strong>
            <br />
            Vamos apagar, desta entidade: os documentos que a pessoa enviou, o
            conteúdo do envio dela no diário, a linha dela na planilha de
            filiados, e o que estiver no banco de consulta. O código de acesso
            dela deixa de valer na hora.
            <br />
            <br />
            Fica registrado que <strong>{pedidoPor}</strong> pediu este
            apagamento, e fica a marca que impede a próxima planilha de
            recriar esta pessoa. A marca não guarda o CPF em claro.
          </Aviso>
          <p className="text-[15px] text-tinta">
            CPF: <strong>{formatarCpf(cpf)}</strong>
          </p>
          <div className="flex flex-wrap gap-3">
            <Botao onClick={() => void apagar()} disabled={indo}>
              {indo ? "Apagando…" : "Apagar definitivamente"}
            </Botao>
            <Botao
              tipo="secundario"
              onClick={() => setConfirmando(false)}
              disabled={indo}
            >
              Voltar
            </Botao>
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <Campo
            rotulo="CPF de quem pediu"
            valor={cpf}
            onChange={setCpf}
            problemas={problemas}
            obrigatorio
            inputMode="numeric"
            ajuda="O CPF do filiado que pediu o apagamento."
          />
          <Campo
            rotulo="Quem no sindicato está atendendo"
            valor={pedidoPor}
            onChange={setPedidoPor}
            obrigatorio
            maxLength={TETO_DO_TEXTO}
            ajuda="Nome ou e-mail. Fica no registro de quem mandou apagar — sem isto, não apagamos."
          />
          <Campo
            rotulo="Motivo (opcional)"
            valor={motivo}
            onChange={setMotivo}
            maxLength={TETO_DO_TEXTO}
            ajuda="Ex.: pedido do titular por e-mail em 02/11/2026."
          />
          {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}
          <div className="flex flex-wrap gap-3">
            <Botao
              onClick={() => setConfirmando(true)}
              disabled={!podeSeguir}
            >
              Conferir e confirmar
            </Botao>
            <Botao
              tipo="secundario"
              onClick={() => {
                limpar();
                setAberto(false);
              }}
            >
              Cancelar
            </Botao>
          </div>
        </div>
      )}
    </Cartao>
  );
}


/** O que mudou de veredicto desde o catálogo anterior.
 *
 * É A NOTÍCIA, e vem ANTES do "o que resolver primeiro" quando existe: que
 * doze pessoas passaram a poder ajuizar é mais acionável que a lista de
 * gargalos, e o gargalo continua lá embaixo.
 *
 * NADA FOI AVISADO A NINGUÉM, e a tela diz isso em voz alta. Quem fala com
 * o filiado é o sindicato, e a decisão de avisar é dele — com advogado, não
 * com agendador. Uma tela que mostrasse a mudança sem dizer isso deixaria o
 * gestor supondo que o filiado já sabe.
 */
function MudouDeVeredicto({ p }: { p: api.Panorama }) {
  const r = resumoDasMudancas(p.mudancas);
  if (!r.mostra) return null;
  const semBanco = p.mudancas.sem_banco;
  return (
    <Cartao titulo="O que mudou desde a última avaliação">
      <Aviso tom={semBanco ? "alerta" : "bom"}>{r.frase}</Aviso>
      {p.mudancas.grupos.map((g) => (
        <div key={`${g.referencia}-${g.de}-${g.para}-${g.trilha}`}>
          <p className="text-[15px] font-medium text-tinta">
            {frasesDaMudanca(g)}
          </p>
          {g.exemplos.length ? (
            <p className="mt-1 text-sm text-tinta/70">
              {g.exemplos.join(" · ")}
              {g.pessoas > g.exemplos.length
                ? ` … e ${pessoas(g.pessoas - g.exemplos.length)}`
                : ""}
            </p>
          ) : null}
        </div>
      ))}
      {r.catalogo ? (
        <p className="text-sm text-tinta/60">
          Catálogo de agora: <code>{r.catalogo}</code>. É ele que a resposta
          guardada cita — por isso dá para dizer o que mudou, e não só como
          está hoje.
        </p>
      ) : null}
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
      {panorama ? <MudouDeVeredicto p={panorama} /> : null}
      {panorama && resumoDaFilaDeLeitura(panorama.aguardando_leitura).mostra ? (
        // A FILA DE LEITURA HUMANA, à vista. Sem isto o servidor contava e
        // tela nenhuma mostrava — o mesmo erro de entregar pela metade que
        // já custou uma revisão neste repositório.
        <Aviso tom="neutro">
          {resumoDaFilaDeLeitura(panorama.aguardando_leitura).frase}
        </Aviso>
      ) : null}
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

      <ApagarAPedido
        entidade={entidade}
        token={token}
        jaApagados={dados.apagados_a_pedido}
      />
    </div>
  );
}
