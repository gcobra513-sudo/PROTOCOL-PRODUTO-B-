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
import { useEffect, useState, type MouseEvent } from "react";

import { BadgeCheck, MailX, UserCheck, UserX, Users } from "lucide-react";

import {
  Aviso,
  Botao,
  Caixa,
  Campo,
  Cartao,
  Destaque,
  Escolha,
  Mini,
} from "../componentes/ui";
import * as api from "../lib/envio";
import {
  ABAS_DO_PAINEL,
  linhasPorVez,
  pendenciasAVista,
  ABERTURA_DO_PROTO_DO_GESTOR,
  PERGUNTAS_DO_GESTOR_AO_PROTO,
  abaDaAncora,
  destinoDoQuadro,
  type AbaDoPainel,
  type FiltroDoPortal,
  type QuadroDoTopo,
  camposDaLeitura,
  faltaNaLeitura,
  fatosDaLeitura,
  filtrarPessoas,
  rotuloDoDono,
  situacaoDaPessoa,
  frasesDaMudanca,
  fracao,
  pessoas,
  presosNoTribunal,
  primeiroAcionavel,
  resumoDaFilaDeLeitura,
  resumoDaPlanilha,
  atalhoDoGargalo,
  resumoDoEnvioDaFicha,
  resumoDoEnvioDoRol,
  resumoDoRolVigente,
  resumoDoAcesso,
  resumoDasMudancas,
  resumoDoApagamento,
  rotuloDoDispositivo,
} from "../lib/painel";
import { conferirCpf, formatarCpf } from "../lib/validacao";
import { resumoDoEscritorio, rotuloDaSituacao } from "../lib/escritorio";
import { sessaoMorreu } from "../lib/sessao";
import { Conversa } from "../componentes/Conversa";
import { Historico } from "../componentes/Historico";
import { Novidades, Teses } from "../componentes/Teses";
import { ProtoNoTopo } from "../componentes/ProtoNoTopo";
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
  const [todas, setTodas] = useState(false);
  const pendencias = pendenciasAVista(p.gargalos, todas);
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
          {atalhoDoGargalo(alvo) ? (
            <a
              href={atalhoDoGargalo(alvo)?.ancora}
              className="mt-3 inline-block text-[15px] font-medium text-acento underline"
            >
              {atalhoDoGargalo(alvo)?.rotulo}
            </a>
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
            {pendencias.visiveis.map((g) => (
              <div
                key={`${g.quem}-${g.o_que}`}
                className="flex items-baseline justify-between gap-4 border-b border-borda py-1.5 text-[15px]"
              >
                <span className="text-tinta/80">
                  {g.o_que}
                  <span className="ml-2 text-[13px] text-tinta/50">
                    {g.titulo}
                  </span>
                  {atalhoDoGargalo(g) ? (
                    <a
                      href={atalhoDoGargalo(g)?.ancora}
                      className="ml-2 text-[13px] font-medium text-acento underline"
                    >
                      {atalhoDoGargalo(g)?.rotulo}
                    </a>
                  ) : null}
                </span>
                <span className="shrink-0 font-medium text-tinta">
                  {g.pessoas}
                </span>
              </div>
            ))}
          </div>
          {pendencias.guardadas > 0 ? (
            <div className="mt-3">
              <Botao
                tipo="secundario"
                tamanho="pequeno"
                onClick={() => setTodas(true)}
              >
                Ver as outras {pendencias.guardadas}
              </Botao>
            </div>
          ) : null}
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
      {/* NEUTRO: é um limite do que a tela afirma, não um erro. Em
          vermelho, quem assistia achava que algo tinha quebrado. */}
      <Aviso tom="neutro">{p.limite}</Aviso>
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


/** Um documento da fila: abrir, ler, registrar.
 *
 * O GESTOR ABRE ANTES DE REGISTRAR, e a tela é desenhada para isso: o botão
 * de abrir vem primeiro e os campos depois. Um formulário que deixasse
 * registrar sem nunca ter aberto convidaria a preencher de memória.
 *
 * DUAS SAÍDAS, porque são duas: "li, e diz isto" e "não dá para ler". Sem a
 * segunda, a foto tremida ficaria na fila para sempre.
 */
function DocumentoParaLer({
  entidade,
  token,
  doc,
  dispositivos,
  onFeito,
  aberto,
  onAbrir,
}: {
  entidade: string;
  token: string;
  doc: api.DocumentoNaFila;
  dispositivos: string[];
  onFeito: () => void;
  /** Só um documento fica aberto por vez; os outros mostram só o nome. */
  aberto: boolean;
  onAbrir: () => void;
}) {
  const [valores, setValores] = useState<Record<string, string>>({});
  const [observacao, setObservacao] = useState("");
  const [indo, setIndo] = useState(false);
  const [erro, setErro] = useState("");
  const campos = camposDaLeitura(doc.tipo);
  const falta = faltaNaLeitura(doc.tipo, valores);
  const mudar = (campo: string) => (v: string) =>
    setValores((atual) => ({ ...atual, [campo]: v }));

  async function abrir() {
    setErro("");
    // A ABA É ABERTA ANTES DO PEDIDO, ainda dentro do clique: aberta depois
    // de esperar a rede, o navegador a trata como pop-up e bloqueia.
    const aba = window.open("", "_blank");
    try {
      const blob = await api.abrirDocumento(entidade, token, doc.id);
      const endereco = URL.createObjectURL(blob);
      if (aba) aba.location.href = endereco;
      else window.location.href = endereco;
      // O endereço só vale nesta sessão do navegador; soltá-lo depois de um
      // tempo devolve a memória sem fechar o documento na cara do gestor.
      setTimeout(() => URL.revokeObjectURL(endereco), 10 * 60 * 1000);
    } catch (e) {
      aba?.close();
      setErro(e instanceof Error ? e.message : "não foi possível abrir");
    }
  }

  async function registrar(resultado: "lido" | "ilegivel") {
    setIndo(true);
    setErro("");
    try {
      await api.registrarLeitura(entidade, token, doc.id, {
        resultado,
        fatos: resultado === "lido" ? fatosDaLeitura(doc.tipo, valores) : {},
        observacao,
      });
      onFeito();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível registrar");
    } finally {
      setIndo(false);
    }
  }

  return (
    <div className="rounded-lg border border-borda bg-carta p-4">
      {/* UM ABERTO POR VEZ. Cada documento traz um formulário inteiro, e
          três deles abertos eram mais de três telas de rolagem no celular.
          Fechado, o formulário continua montado — só escondido —, para que
          o que já foi digitado não se perca ao abrir outro. */}
      <button
        type="button"
        aria-expanded={aberto}
        onClick={onAbrir}
        className="flex w-full items-start justify-between gap-3 text-left"
      >
        <span>
          <span className="block text-[15px] font-medium text-tinta">{doc.nome}</span>
          <span className="mt-0.5 block text-sm text-tinta/70">{doc.rotulo}</span>
        </span>
        <span className="shrink-0 text-sm font-medium text-acento underline">
          {aberto ? "Aberto" : "Abrir para ler"}
        </span>
      </button>
      <div hidden={!aberto} className="mt-4 space-y-4">
      <Botao tipo="secundario" tamanho="pequeno" onClick={() => void abrir()}>
        Abrir o documento
      </Botao>

      {campos.includes("dispositivo") ? (
        <Escolha
          rotulo="O que a sentença decidiu"
          obrigatorio
          valor={valores.dispositivo ?? ""}
          onChange={mudar("dispositivo")}
          opcoes={dispositivos.map((d) => ({
            valor: d,
            rotulo: rotuloDoDispositivo(d),
          }))}
        />
      ) : null}
      {campos.includes("numero_processo") ? (
        <Campo
          rotulo="Número do processo (se aparecer)"
          valor={valores.numero_processo ?? ""}
          onChange={mudar("numero_processo")}
          inputMode="numeric"
        />
      ) : null}
      {campos.includes("transito_em_julgado") ? (
        <Campo
          rotulo="Data do trânsito em julgado"
          obrigatorio
          type="date"
          valor={valores.transito_em_julgado ?? ""}
          onChange={mudar("transito_em_julgado")}
        />
      ) : null}
      {campos.includes("periodo_inicio") ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo
            rotulo="O comprovante cobre de"
            obrigatorio
            type="month"
            valor={valores.periodo_inicio ?? ""}
            onChange={mudar("periodo_inicio")}
          />
          <Campo
            rotulo="até"
            obrigatorio
            type="month"
            valor={valores.periodo_fim ?? ""}
            onChange={mudar("periodo_fim")}
          />
        </div>
      ) : null}
      <Campo
        rotulo="Observação (opcional)"
        valor={observacao}
        onChange={setObservacao}
        maxLength={300}
        ajuda="Ex.: página 3; ou por que não deu para ler."
      />

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}
      <div className="flex flex-wrap gap-3">
        <Botao
          tamanho="pequeno"
          disabled={indo || falta.length > 0}
          onClick={() => void registrar("lido")}
        >
          {indo ? "Registrando…" : "Registrar o que li"}
        </Botao>
        <Botao
          tipo="secundario"
          tamanho="pequeno"
          disabled={indo}
          onClick={() => void registrar("ilegivel")}
        >
          Não dá para ler
        </Botao>
      </div>
      {falta.length ? (
        <p className="text-sm text-tinta/60">Falta: {falta.join("; ")}.</p>
      ) : null}
      </div>
    </div>
  );
}

/** A fila de leitura humana, com SAÍDA.
 *
 * Scanner e foto entram no cadastro e a máquina não os lê. QUEM LÊ É O
 * SINDICATO, por aqui (decisão de 10/11/2026). O que o gestor registra vira
 * fato, com o marcador dele como autor — e muda a resposta do filiado.
 *
 * O QUE ESTA TELA DIZ ANTES DOS CAMPOS: que o que se registra vira dado do
 * filiado e fica com autor. Não é aviso de rodapé; é o que separa conferir
 * de preencher formulário.
 */
function FilaDeConferencia({
  entidade,
  token,
  onMudou,
  onQuantos,
}: {
  entidade: string;
  token: string;
  onMudou: () => void;
  /** Quantos documentos há para ler: é o selo da aba. */
  onQuantos: (n: number) => void;
}) {
  const [fila, setFila] = useState<api.Conferencia | null>(null);
  const [abertoNaFila, setAbertoNaFila] = useState("");
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    void api
      .verConferencia(entidade, token)
      .then(setFila)
      .catch((e) =>
        setErro(e instanceof Error ? e.message : "não foi possível abrir"),
      );
  }, [entidade, token, versao]);

  const quantos = fila ? fila.pendentes.length + fila.ilegiveis.length : 0;
  // SÓ DEPOIS DE SABER. Avisar "zero" enquanto a fila ainda carrega fazia o
  // painel escrever "nenhum documento esperando leitura" por um instante,
  // ao lado da fila que acabava de chegar — o ensaio pegou os dois juntos.
  useEffect(() => {
    if (fila) onQuantos(quantos);
  }, [fila, quantos, onQuantos]);

  if (erro) return null; // sem banco o painel já diz que não sabe da fila
  if (!fila || (!fila.pendentes.length && !fila.ilegiveis.length)) return null;

  return (
    <Cartao
      titulo="Documentos para ler"
      explicacao={
        <>
          Estes documentos chegaram como imagem — foto ou scanner — e a
          máquina não consegue ler. Abra, leia e registre.{" "}
          <strong>
            O que você registrar vira dado do filiado e fica com o seu nome
            como autor.
          </strong>
        </>
      }
    >
      {fila.pendentes.map((doc, i) => (
        <DocumentoParaLer
          key={doc.id}
          entidade={entidade}
          token={token}
          doc={doc}
          dispositivos={fila.dispositivos}
          // O escolhido; ou, se ele já saiu da fila, o primeiro.
          aberto={
            fila.pendentes.some((d) => d.id === abertoNaFila)
              ? doc.id === abertoNaFila
              : i === 0
          }
          onAbrir={() => setAbertoNaFila(doc.id)}
          onFeito={() => {
            setVersao((v) => v + 1);
            onMudou();
          }}
        />
      ))}
      {fila.ilegiveis.length ? (
        <div>
          <p className="text-[15px] font-medium text-tinta">
            Não deu para ler — peça de novo
          </p>
          <div className="mt-2 space-y-1">
            {fila.ilegiveis.map((doc) => (
              <div key={doc.id} className="border-b border-borda py-1 text-sm">
                <span className="text-tinta">{doc.nome}</span>
                <span className="ml-2 text-tinta/70">{doc.rotulo}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </Cartao>
  );
}


/** Quantas linhas a tela mostra de cada vez — `linhasPorVez` decide pela
 *  largura. A base pode ter milhares; a busca e o filtro acham quem se
 *  procura, e a planilha leva todo mundo. */
const LINHAS_POR_VEZ =
  typeof window === "undefined" ? 15 : linhasPorVez(window.innerWidth);

/** A base, NOME POR NOME.
 *
 * A frase do produto é "nós dizemos, nome por nome" — e o painel mostrava
 * totais e três nomes de exemplo. Esta é a lista: cada pessoa, o que ela já
 * pode, e de quem depende o resto.
 *
 * O CPF AQUI VEM MASCARADO. O inteiro sai só na PLANILHA, que o gestor pede
 * de propósito, vem como arquivo e fica registrada — porque é por ele que o
 * sindicato casa esta lista com os registros dele.
 */
function NomePorNome({
  entidade,
  token,
  versao,
  portal,
  onPortal,
  dono,
  onDono,
}: {
  entidade: string;
  token: string;
  /** Sobe quando a base muda (planilha gravada, leitura registrada). */
  versao: number;
  /** A situação escolhida ("PODE", ou de quem depende). Mora no `Painel`
   *  pela mesma razão do filtro do portal: o quadro "já podem" a escolhe. */
  dono: string;
  onDono: (d: string) => void;
  /** Quem entrou no portal / quem falta. Mora no `Painel` porque os quadros
   *  do topo também o escolhem. */
  portal: FiltroDoPortal;
  onPortal: (f: FiltroDoPortal) => void;
}) {
  const [lista, setLista] = useState<api.PessoaNaLista[] | null>(null);
  const [texto, setTexto] = useState("");
  const setDono = onDono;
  const [erro, setErro] = useState("");
  const [baixando, setBaixando] = useState(false);
  const [mostrando, setMostrando] = useState(LINHAS_POR_VEZ);
  // Mudou a busca ou o filtro: a lista é outra, e recomeça do começo.
  useEffect(() => setMostrando(LINHAS_POR_VEZ), [texto, dono, portal]);

  useEffect(() => {
    void api
      .verPessoas(entidade, token)
      .then(setLista)
      .catch((e) =>
        setErro(e instanceof Error ? e.message : "não foi possível abrir"),
      );
  }, [entidade, token, versao]);

  async function baixar() {
    setBaixando(true);
    setErro("");
    try {
      const blob = await api.exportarPessoas(entidade, token);
      const endereco = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = endereco;
      a.download = `base-${entidade}.csv`;
      a.click();
      URL.revokeObjectURL(endereco);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível exportar");
    } finally {
      setBaixando(false);
    }
  }

  if (!lista) {
    return erro ? <Aviso tom="alerta">{erro}</Aviso> : null;
  }
  const filtradas = filtrarPessoas(lista, { texto, dono, portal });
  const doPortal: [FiltroDoPortal, string][] = [
    ["", "Todos"],
    ["entrou", "Já entrou no portal"],
    ["falta", "Ainda não entrou"],
  ];
  const filtros: [string, string][] = [
    ["", "Todos"],
    ["PODE", "Já pode"],
    ["VOCE", rotuloDoDono("VOCE")],
    ["CONFERENCIA", rotuloDoDono("CONFERENCIA")],
    ["TRIBUNAL", rotuloDoDono("TRIBUNAL")],
  ];

  return (
    <Cartao
      titulo="Nome por nome"
      explicacao="Cada pessoa da base: o que ela já pode, e de quem depende o resto."
    >
      {/* A PLANILHA NO TOPO: é com ela que o sindicato sai daqui e liga
          para as pessoas. Ficava depois de cinquenta nomes. */}
      <div className="rounded-lg bg-lilas p-4">
        <Botao disabled={baixando} onClick={() => void baixar()}>
          {baixando ? "Preparando…" : "Baixar a planilha da base"}
        </Botao>
        <p className="mt-2 text-sm text-tinta/70">
          Abre no Excel. Traz cada pessoa com o CPF inteiro, o e-mail e o
          telefone que constam — para você entrar em contato. Fica
          registrado quem baixou.
        </p>
      </div>
      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}

      <Campo
        rotulo="Procurar pelo nome"
        valor={texto}
        onChange={setTexto}
        placeholder="Ex.: maria"
      />
      <div>
        <p className="text-sm font-medium text-tinta">No portal</p>
        <div className="mt-1 flex flex-wrap gap-2">
          {doPortal.map(([valor, rotulo]) => (
            <Botao
              key={valor || "todos"}
              tipo={portal === valor ? "principal" : "secundario"}
              tamanho="pequeno"
              aria-pressed={portal === valor}
              onClick={() => onPortal(valor)}
            >
              {rotulo}
            </Botao>
          ))}
        </div>
      </div>
      <p className="text-sm font-medium text-tinta">Situação</p>
      <div className="-mt-3 flex flex-wrap gap-2">
        {filtros.map(([valor, rotulo]) => (
          <Botao
            key={valor || "todos"}
            tipo={dono === valor ? "principal" : "secundario"}
            tamanho="pequeno"
            aria-pressed={dono === valor}
            onClick={() => setDono(valor)}
          >
            {rotulo}
          </Botao>
        ))}
      </div>

      <p className="text-sm text-tinta/70">
        {pessoas(filtradas.length)}
        {filtradas.length !== lista.length
          ? ` de ${lista.length} na base`
          : " na base"}
        {filtradas.length > mostrando
          ? ` — mostrando as primeiras ${mostrando}. A planilha traz todas.`
          : "."}
      </p>

      <div className="space-y-1">
        {filtradas.slice(0, mostrando).map((p) => (
          <div
            key={`${p.cpf}-${p.nome}`}
            className="border-b border-borda py-2 text-sm"
          >
            <p className="text-tinta">
              {p.nome}
              <span className="ml-2 text-tinta/50">{p.cpf}</span>
              {!p.cadastrou ? (
                <span className="ml-2 text-tinta/60">
                  · ainda não entrou no portal
                </span>
              ) : null}
            </p>
            <p className="mt-0.5 text-tinta/70">{situacaoDaPessoa(p)}</p>
          </div>
        ))}
      </div>

      {filtradas.length > mostrando ? (
        <Botao
          tipo="secundario"
          onClick={() => setMostrando((n) => n + LINHAS_POR_VEZ)}
        >
          Mostrar mais {Math.min(LINHAS_POR_VEZ, filtradas.length - mostrando)}
        </Botao>
      ) : null}
    </Cartao>
  );
}


/** O sindicato ENTREGA a base: a planilha de filiados e os documentos.
 *
 * "O sindicato manda a lista de filiados" é a primeira frase do produto, e
 * não havia por onde: a planilha e os documentos só entravam por linha de
 * comando, rodada por nós.
 *
 * AS DUAS ENTREGAS SÃO EM DUAS ETAPAS, e a primeira não grava nada. O
 * gestor escolhe o arquivo, o servidor LÊ e devolve o que ele traz, e só o
 * segundo clique grava — levando a impressão digital do que foi conferido.
 * A planilha é a base inteira do sindicato: a confirmação é a única
 * conferência que ela recebe.
 */
function EnviarBase({
  entidade,
  token,
  onMudou,
}: {
  entidade: string;
  token: string;
  onMudou: () => void;
}) {
  const [planilha, setPlanilha] = useState<File | null>(null);
  const [previa, setPrevia] = useState<api.PreviaDaPlanilha | null>(null);
  const [docs, setDocs] = useState<File[]>([]);
  const [previaDocs, setPreviaDocs] =
    useState<api.PreviaDosDocumentos | null>(null);
  const [indo, setIndo] = useState("");
  const [erro, setErro] = useState("");

  async function fazer(qual: string, acao: () => Promise<void>) {
    setIndo(qual);
    setErro("");
    try {
      await acao();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível enviar");
    } finally {
      setIndo("");
    }
  }

  const conferirPlanilha = () =>
    fazer("planilha", async () => {
      if (planilha) setPrevia(await api.enviarPlanilha(entidade, token, planilha));
    });
  const gravarPlanilha = () =>
    fazer("planilha", async () => {
      if (!planilha || !previa) return;
      setPrevia(
        await api.enviarPlanilha(entidade, token, planilha, previa.sha256),
      );
      onMudou();
    });
  const conferirDocs = () =>
    fazer("docs", async () => {
      if (docs.length) {
        setPreviaDocs(
          await api.enviarDocumentosDoSindicato(entidade, token, docs),
        );
      }
    });
  const gravarDocs = () =>
    fazer("docs", async () => {
      if (!docs.length || !previaDocs) return;
      setPreviaDocs(
        await api.enviarDocumentosDoSindicato(
          entidade, token, docs, previaDocs.sha256,
        ),
      );
      onMudou();
    });

  return (
    <Cartao
      titulo="Enviar a base do sindicato"
      explicacao="Primeiro a planilha de filiados; depois, se tiver, as sentenças e certidões que o sindicato já guarda. Nada é gravado antes de você conferir."
    >
      <div className="space-y-3 rounded-lg border border-borda bg-carta p-4">
        <label className="block text-[15px] font-medium text-tinta">
          A planilha de filiados (Excel .xlsx ou CSV)
          <input
            type="file"
            accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="mt-2 block text-sm font-normal"
            onChange={(e) => {
              setPlanilha(e.target.files?.[0] ?? null);
              setPrevia(null);
            }}
          />
        </label>
        {previa ? (
          <div className="space-y-2">
            {previa.gravado ? (
              <Aviso tom="bom">
                Planilha gravada: {pessoas(previa.pessoas)} na base.
              </Aviso>
            ) : (
              <Aviso tom="neutro">
                <strong>Confira antes de gravar.</strong> Nada foi gravado
                ainda.
              </Aviso>
            )}
            {resumoDaPlanilha(previa).map((linha) => (
              <p key={linha} className="text-sm text-tinta/80">
                {linha}
              </p>
            ))}
            {/* QUEM CONSEGUE ENTRAR, separado do que entrou na base: são
                duas coisas, e a segunda tem uma regra que a primeira não
                tem — a planilha não troca o e-mail de quem já entra. */}
            {resumoDoAcesso(previa.acesso, previa.gravado).length ? (
              <div className="space-y-2 border-t border-borda pt-2">
                <p className="text-sm font-medium text-tinta">
                  Quem consegue entrar no portal
                </p>
                {resumoDoAcesso(previa.acesso, previa.gravado).map((linha) => (
                  <p key={linha} className="text-sm text-tinta/80">
                    {linha}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-3">
          {!previa ? (
            <Botao
              tamanho="pequeno"
              disabled={!planilha || indo === "planilha"}
              onClick={() => void conferirPlanilha()}
            >
              {indo === "planilha" ? "Lendo…" : "Conferir a planilha"}
            </Botao>
          ) : !previa.gravado ? (
            <Botao
              tamanho="pequeno"
              disabled={indo === "planilha"}
              onClick={() => void gravarPlanilha()}
            >
              {indo === "planilha" ? "Gravando…" : "Confirmar e gravar a planilha"}
            </Botao>
          ) : null}
        </div>
      </div>

      <div className="space-y-3 rounded-lg border border-borda bg-carta p-4">
        <label className="block text-[15px] font-medium text-tinta">
          Documentos que o sindicato já tem (PDFs, ou um .zip)
          <input
            type="file"
            multiple
            accept="application/pdf,.pdf,.zip,application/zip"
            className="mt-2 block text-sm font-normal"
            onChange={(e) => {
              setDocs(Array.from(e.target.files ?? []));
              setPreviaDocs(null);
            }}
          />
        </label>
        <p className="text-sm text-tinta/60">
          Cada arquivo encontra o dono pelo CPF — no nome do arquivo ou no
          texto do documento. O que não encontrar volta numa lista, com o
          motivo.
        </p>
        {previaDocs ? (
          <div className="space-y-2">
            <Aviso tom={previaDocs.gravado ? "bom" : "neutro"}>
              {previaDocs.gravado ? "Gravado: " : "Confira antes de gravar: "}
              {previaDocs.casaram} de {previaDocs.arquivos} documento(s)
              encontraram o dono, de {pessoas(previaDocs.pessoas)}.
            </Aviso>
            {previaDocs.sobraram.length ? (
              <div>
                <p className="text-sm font-medium text-tinta">
                  Não encontraram dono ({previaDocs.sobraram_total}):
                </p>
                {previaDocs.sobraram.map((x) => (
                  <p key={x.arquivo} className="text-sm text-tinta/75">
                    {x.arquivo} — {x.motivo}
                  </p>
                ))}
              </div>
            ) : null}
            {previaDocs.avisos.map((a) => (
              <p key={a} className="text-sm text-tinta/75">
                Atenção: {a}
              </p>
            ))}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-3">
          {!previaDocs ? (
            <Botao
              tamanho="pequeno"
              disabled={!docs.length || indo === "docs"}
              onClick={() => void conferirDocs()}
            >
              {indo === "docs" ? "Lendo…" : "Conferir os documentos"}
            </Botao>
          ) : !previaDocs.gravado && previaDocs.casaram > 0 ? (
            <Botao
              tamanho="pequeno"
              disabled={indo === "docs"}
              onClick={() => void gravarDocs()}
            >
              {indo === "docs" ? "Gravando…" : "Confirmar e gravar os documentos"}
            </Botao>
          ) : null}
        </div>
      </div>

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}
    </Cartao>
  );
}

/** O ROL DE SUBSTITUÍDOS de cada ação coletiva.
 *
 *  É o que faltava para o sistema responder: ele pergunta se a pessoa
 *  consta do rol da ação, e ninguém respondia. Quem tem a lista é o
 *  sindicato, que ajuizou.
 *
 *  A CAIXA "É O ROL INTEIRO" COMEÇA DESMARCADA, e isso é a decisão desta
 *  tela: marcada, quem não está na lista passa a aparecer como FORA do rol,
 *  que é resposta com consequência. Tem de ser um ato, não um padrão.
 */
function RolDeSubstituidos({
  entidade,
  token,
  onMudou,
}: {
  entidade: string;
  token: string;
  onMudou: () => void;
}) {
  const [acoes, setAcoes] = useState<api.AcaoComRol[] | null>(null);
  const [acao, setAcao] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [completo, setCompleto] = useState(false);
  const [previa, setPrevia] = useState<api.PreviaDoRol | null>(null);
  const [indo, setIndo] = useState(false);
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    void api
      .verRois(entidade, token)
      .then((lista) => {
        setAcoes(lista);
        setAcao((atual) => atual || (lista[0]?.acao ?? ""));
      })
      .catch((e) =>
        setErro(e instanceof Error ? e.message : "não foi possível abrir"),
      );
  }, [entidade, token, versao]);

  async function fazer(passo: () => Promise<void>) {
    setIndo(true);
    setErro("");
    try {
      await passo();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível enviar");
    } finally {
      setIndo(false);
    }
  }

  const conferir = () =>
    fazer(async () => {
      if (arquivo && acao) {
        setPrevia(await api.enviarRol(entidade, token, acao, arquivo, completo));
      }
    });
  const gravar = () =>
    fazer(async () => {
      if (!arquivo || !previa) return;
      setPrevia(
        await api.enviarRol(
          entidade, token, acao, arquivo, completo, previa.sha256,
        ),
      );
      setVersao((v) => v + 1);
      onMudou();
    });
  const retirar = (qual: string) =>
    fazer(async () => {
      await api.retirarRol(entidade, token, qual);
      setPrevia(null);
      setVersao((v) => v + 1);
      onMudou();
    });

  if (acoes !== null && acoes.length === 0) return null;

  return (
    <Cartao
      titulo="Rol de substituídos"
      explicacao="A lista de quem o sindicato substituiu em cada ação coletiva. Sem ela, não dá para dizer quem pode executar. Nada é gravado antes de você conferir."
    >
      {(acoes ?? []).map((a) => (
        <div key={a.acao} className="rounded-lg border border-borda bg-carta p-4">
          <p className="text-[15px] font-medium text-tinta">{a.rotulo}</p>
          {a.rol ? (
            <div className="mt-2 space-y-1">
              {resumoDoRolVigente(a.rol).map((linha) => (
                <p key={linha} className="text-sm text-tinta/80">
                  {linha}
                </p>
              ))}
              <Botao
                tipo="discreto"
                tamanho="pequeno"
                disabled={indo}
                onClick={() => void retirar(a.acao)}
              >
                Retirar este rol
              </Botao>
            </div>
          ) : (
            <p className="mt-1 text-sm text-tinta/70">
              O rol desta ação ainda não foi enviado.
            </p>
          )}
        </div>
      ))}

      <div className="space-y-3 rounded-lg border border-borda bg-carta p-4">
        {(acoes ?? []).length > 1 ? (
          <label className="block text-[15px] font-medium text-tinta">
            De qual ação é este rol
            <select
              value={acao}
              onChange={(e) => {
                setAcao(e.target.value);
                setPrevia(null);
              }}
              className="mt-2 block h-11 w-full rounded-lg border border-borda bg-carta px-3 text-[15px] font-normal"
            >
              {(acoes ?? []).map((a) => (
                <option key={a.acao} value={a.acao}>
                  {a.rotulo}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <label className="block text-[15px] font-medium text-tinta">
          O arquivo do rol (planilha com coluna de CPF, ou PDF com texto)
          <input
            type="file"
            accept=".xlsx,.csv,.pdf,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="mt-2 block text-sm font-normal"
            onChange={(e) => {
              setArquivo(e.target.files?.[0] ?? null);
              setPrevia(null);
            }}
          />
        </label>
        <p className="text-sm text-tinta/60">
          Cada pessoa é reconhecida pelo CPF. Rol só com nome não entra:
          casar por nome seria adivinhar.
        </p>
        <Caixa
          rotulo="Esta lista é o rol inteiro desta ação"
          marcado={completo}
          onChange={(v) => {
            setCompleto(v);
            setPrevia(null);
          }}
          detalhe="Marque só se for a lista completa. Marcado, quem é da sua base e não está nela passa a aparecer como fora do rol. Desmarcado, quem não está na lista fica sem resposta."
        />
        {previa ? (
          <div className="space-y-2">
            {previa.gravado ? (
              <Aviso tom="bom">Rol gravado para {previa.rotulo}.</Aviso>
            ) : (
              <Aviso tom="neutro">
                <strong>Confira antes de gravar.</strong> Nada foi gravado
                ainda.
              </Aviso>
            )}
            {resumoDoEnvioDoRol(previa).map((linha) => (
              <p key={linha} className="text-sm text-tinta/80">
                {linha}
              </p>
            ))}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-3">
          {!previa ? (
            <Botao
              tamanho="pequeno"
              disabled={!arquivo || !acao || indo}
              onClick={() => void conferir()}
            >
              {indo ? "Lendo…" : "Conferir o rol"}
            </Botao>
          ) : !previa.gravado ? (
            <Botao
              tamanho="pequeno"
              disabled={indo}
              onClick={() => void gravar()}
            >
              {indo ? "Gravando…" : "Confirmar e gravar o rol"}
            </Botao>
          ) : null}
        </div>
      </div>

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}
    </Cartao>
  );
}

/** A FICHA FINANCEIRA: a base de cálculo de cada filiado, mês a mês.
 *
 *  É o que o painel cobra como "a base de cálculo (ficha financeira)", e
 *  não havia onde entregá-la. As mesmas duas etapas da planilha e do rol.
 *  É REMUNERAÇÃO: a tela mostra contagens, nunca valor. */
function FichaFinanceira({
  entidade,
  token,
  onMudou,
}: {
  entidade: string;
  token: string;
  onMudou: () => void;
}) {
  const [recebidas, setRecebidas] = useState<api.FichasRecebidas | null>(null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [previa, setPrevia] = useState<api.PreviaDaFicha | null>(null);
  const [indo, setIndo] = useState(false);
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    void api
      .verFichas(entidade, token)
      .then(setRecebidas)
      .catch(() => setRecebidas(null));
  }, [entidade, token, versao]);

  async function fazer(passo: () => Promise<void>) {
    setIndo(true);
    setErro("");
    try {
      await passo();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível enviar");
    } finally {
      setIndo(false);
    }
  }
  const conferir = () =>
    fazer(async () => {
      if (arquivo) setPrevia(await api.enviarFicha(entidade, token, arquivo));
    });
  const gravar = () =>
    fazer(async () => {
      if (!arquivo || !previa) return;
      setPrevia(await api.enviarFicha(entidade, token, arquivo, previa.sha256));
      setVersao((v) => v + 1);
      onMudou();
    });

  return (
    <Cartao
      titulo="Ficha financeira"
      explicacao="A base de cálculo de cada filiado, mês a mês. Sem ela não há do que tirar o percentual da verba, e o portal não mostra valor. Nada é gravado antes de você conferir."
    >
      {recebidas ? (
        <p className="text-[15px] text-tinta/80">
          {recebidas.pessoas > 0
            ? `Já recebemos a ficha de ${pessoas(recebidas.pessoas)}. ` +
              `${recebidas.sem_ficha > 0 ? `${pessoas(recebidas.sem_ficha)} da base ainda ${recebidas.sem_ficha === 1 ? "está" : "estão"} sem ficha.` : "Toda a base tem ficha."}`
            : "Nenhuma ficha foi enviada ainda."}
        </p>
      ) : null}
      <div className="space-y-3 rounded-lg border border-borda bg-carta p-4">
        <label className="block text-[15px] font-medium text-tinta">
          A planilha da ficha (Excel ou CSV)
          <input
            type="file"
            accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="mt-2 block text-sm font-normal"
            onChange={(e) => {
              setArquivo(e.target.files?.[0] ?? null);
              setPrevia(null);
            }}
          />
        </label>
        <p className="text-sm text-tinta/60">
          Três colunas: CPF, Competência (o mês, como 03/2004) e Base (o
          valor sobre o qual a verba incide). Uma linha por pessoa e por mês.
          Mês que não vier não é contado como zero: a conta só sai com todos.
        </p>
        {previa ? (
          <div className="space-y-2">
            {previa.gravado ? (
              <Aviso tom="bom">Ficha financeira gravada.</Aviso>
            ) : (
              <Aviso tom="neutro">
                <strong>Confira antes de gravar.</strong> Nada foi gravado
                ainda.
              </Aviso>
            )}
            {resumoDoEnvioDaFicha(previa).map((linha) => (
              <p key={linha} className="text-sm text-tinta/80">
                {linha}
              </p>
            ))}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-3">
          {!previa ? (
            <Botao tamanho="pequeno" disabled={!arquivo || indo} onClick={() => void conferir()}>
              {indo ? "Lendo…" : "Conferir a ficha"}
            </Botao>
          ) : !previa.gravado && previa.pessoas > 0 ? (
            <Botao tamanho="pequeno" disabled={indo} onClick={() => void gravar()}>
              {indo ? "Gravando…" : "Confirmar e gravar a ficha"}
            </Botao>
          ) : null}
        </div>
      </div>
      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}
    </Cartao>
  );
}

/** OS ESCRITÓRIOS que o sindicato contratou, e a triagem.
 *
 *  O sindicato terceiriza o jurídico, e o que ele faz é encaminhar: esta
 *  pessoa, por esta ação, a este escritório. Aqui isso é um botão — e o
 *  retorno, que antes não existia, é a contagem de cada escritório, com os
 *  casos PARADOS na frente. */
function Escritorios({
  entidade,
  token,
}: {
  entidade: string;
  token: string;
}) {
  const [visao, setVisao] = useState<api.VisaoDosEscritorios | null>(null);
  const [casos, setCasos] = useState<api.CasoDoSindicato[]>([]);
  const [abertoEm, setAbertoEm] = useState("");
  const [casoAberto, setCasoAberto] = useState("");
  const [feito, setFeito] = useState("");
  const [erro, setErro] = useState("");
  const [indo, setIndo] = useState(false);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    void api
      .verEscritorios(entidade, token)
      .then(setVisao)
      .catch(() => setVisao(null));
    // Os casos, com o histórico: a custódia que o sindicato lê.
    void api
      .verCasosDosEscritorios(entidade, token)
      .then((r) => setCasos(r.casos))
      .catch(() => setCasos([]));
  }, [entidade, token, versao]);

  // Sindicato sem escritório cadastrado não vê um cartão vazio.
  if (!visao || visao.escritorios.length === 0) return null;
  const nomeDe = (id: string | null) =>
    visao.escritorios.find((e) => e.id === id)?.nome ?? "";

  async function encaminhar(acao: api.AcaoATriar) {
    if (!acao.escritorio) return;
    setIndo(true);
    setErro("");
    setFeito("");
    try {
      const r = await api.encaminharAoEscritorio(entidade, token, acao.acao, acao.escritorio);
      setFeito(
        `${pessoas(r.encaminhados)} ${r.encaminhados === 1 ? "encaminhada" : "encaminhadas"} a ${nomeDe(acao.escritorio)}. ` +
          (r.avisados > 0
            ? "O escritório foi avisado por e-mail."
            : "O aviso por e-mail ao escritório não saiu: avise por outro meio."),
      );
      setVersao((v) => v + 1);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "não foi possível encaminhar");
    } finally {
      setIndo(false);
    }
  }

  return (
    <Cartao
      titulo="Escritórios"
      explicacao="Os escritórios que o sindicato contratou. Você encaminha os filiados de cada ação, e acompanha aqui o que cada escritório já recebeu."
    >
      {visao.acoes.map((a) => (
        <div key={a.acao} className="rounded-lg bg-lilas p-4">
          <p className="text-[15px] font-medium text-tinta">{a.rotulo}</p>
          {a.escritorio ? (
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <p className="min-w-0 basis-full text-[15px] text-tinta/80 sm:flex-1 sm:basis-0">
                {a.a_encaminhar > 0
                  ? `${pessoas(a.a_encaminhar)} já ${a.a_encaminhar === 1 ? "se cadastrou" : "se cadastraram"} e ainda não ${a.a_encaminhar === 1 ? "foi encaminhada" : "foram encaminhadas"}. Quem cuida desta ação: ${nomeDe(a.escritorio)}.`
                  : `Todos os que já se cadastraram estão com ${nomeDe(a.escritorio)}.`}
              </p>
              {a.a_encaminhar > 0 ? (
                <Botao tamanho="pequeno" disabled={indo} onClick={() => void encaminhar(a)}>
                  {indo ? "Encaminhando…" : `Encaminhar ${a.a_encaminhar}`}
                </Botao>
              ) : null}
            </div>
          ) : (
            <p className="mt-1 text-[15px] text-tinta/70">
              Nenhum escritório está cadastrado como responsável por esta ação.
            </p>
          )}
        </div>
      ))}
      {feito ? <Aviso tom="bom">{feito}</Aviso> : null}
      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}

      {visao.escritorios.map((e) => (
        <div key={e.id} className="rounded-lg border border-borda bg-carta p-4">
          <p className="text-[16px] font-semibold text-tinta">{e.nome}</p>
          {resumoDoEscritorio(e).map((linha, i) => (
            <p
              key={linha}
              className={
                i === 0 && e.parados > 0
                  ? "mt-1 text-[15px] font-medium text-alerta"
                  : "mt-1 text-[15px] text-tinta/80"
              }
            >
              {linha}
            </p>
          ))}
          {e.casos > 0 ? (
            <div className="mt-3">
              <Botao
                tipo="secundario"
                tamanho="pequeno"
                aria-expanded={abertoEm === e.id}
                onClick={() => setAbertoEm((a) => (a === e.id ? "" : e.id))}
              >
                {abertoEm === e.id ? "Fechar os casos" : "Ver os casos e o histórico"}
              </Botao>
            </div>
          ) : null}
          {/* A CUSTÓDIA: cada caso, com quem recebeu, o que foi pedido e
              que documento foi aberto. É o que por e-mail não existia. */}
          {abertoEm === e.id ? (
            <div className="mt-3 space-y-2">
              {casos
                .filter((c) => c.escritorio_id === e.id)
                .map((c) => {
                  const chave = `${c.cpf}-${c.rotulo}-${c.encaminhado_em}`;
                  return (
                    <div key={chave} className="rounded-lg border border-borda bg-papel">
                      <button
                        type="button"
                        aria-expanded={casoAberto === chave}
                        onClick={() => setCasoAberto((a) => (a === chave ? "" : chave))}
                        className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-left hover:bg-lilas/40"
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[15px] font-semibold text-tinta">{c.nome}</span>
                          <span className="block text-sm text-tinta/65">{c.cpf} · {c.rotulo}</span>
                        </span>
                        <span className="rounded-full border border-borda bg-carta px-3 py-1 text-[13px] font-semibold text-tinta/80">
                          {rotuloDaSituacao(c.situacao)}
                          {c.faltam_em_palavras.length ? `: ${c.faltam_em_palavras.join(", ")}` : ""}
                        </span>
                      </button>
                      {casoAberto === chave ? (
                        <div className="border-t border-borda px-4 py-3">
                          <Historico passos={c.historico} />
                        </div>
                      ) : null}
                    </div>
                  );
                })}
            </div>
          ) : null}
        </div>
      ))}
    </Cartao>
  );
}

export function Painel({
  entidade,
  token,
  onToken,
  onSessaoMorta,
  onSair,
}: {
  entidade: string;
  /** A sessão é do `App`, e vale em todas as áreas: vazio = ninguém entrou. */
  token: string;
  onToken: (token: string, cpf: string) => void;
  /** O servidor não aceita mais esta sessão: a tela volta ao portão. */
  onSessaoMorta: () => void;
  /** Sair, para entrar com outro CPF — quem não é gestor chega até aqui. */
  onSair: () => void;
}) {
  const [dados, setDados] = useState<api.PainelDoGestor | null>(null);
  const [panorama, setPanorama] = useState<api.Panorama | null>(null);
  const [erroPanorama, setErroPanorama] = useState("");
  const [erro, setErro] = useState("");
  // Sobe a cada leitura registrada: a fila mudou, e a contagem do panorama
  // tem de mudar junto — número parado ao lado de uma fila que anda parece
  // defeito mesmo quando não é.
  const [versaoDaFila, setVersaoDaFila] = useState(0);
  const [aba, setAba] = useState<AbaDoPainel>("resumo");
  const [portal, setPortal] = useState<FiltroDoPortal>("");
  const [dono, setDono] = useState("");
  // Quantos documentos a fila tem NA TELA: é o número do selo da aba.
  const [filaNaTela, setFilaNaTela] = useState<number | null>(null);
  const [teses, setTeses] = useState<{
    teses: api.Tese[];
    novidades: api.NovidadeNosTribunais[];
  } | null>(null);
  useEffect(() => {
    if (!token) return;
    // Carrega à parte, como o panorama: se falhar, o painel continua.
    void api.verTeses(entidade, token).then(setTeses).catch(() => setTeses(null));
  }, [entidade, token]);
  const [todosForaDeAlcance, setTodosForaDeAlcance] = useState(false);

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
  }, [token, entidade, versaoDaFila]);

  useEffect(() => {
    if (!token) return;
    void api
      .verCompletude(entidade, token)
      .then(setDados)
      .catch((e) => {
        if (sessaoMorreu(e)) onSessaoMorta();
        else setErro(e instanceof Error ? e.message : "não foi possível abrir");
      });
  }, [entidade, token]);

  if (!token) {
    return (
      <Portao
        entidade={entidade}
        titulo="Painel do sindicato"
        explicacao="Para gestores. O código vai para o e-mail cadastrado — não há senha."
        onToken={onToken}
      />
    );
  }

  if (erro) {
    return (
      <Cartao titulo="Painel do sindicato">
        <Aviso tom="alerta">{erro}</Aviso>
        {/* A SESSÃO É UMA SÓ PARA TODAS AS ÁREAS. Quem entrou como filiado
            e abriu o painel chega aqui com a sessão dele — e precisa de um
            jeito de entrar com o CPF de gestor sem fechar a página. */}
        <Botao tipo="secundario" onClick={onSair}>
          Sair e entrar com outro CPF
        </Botao>
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
  const filaDeLeitura = panorama
    ? resumoDaFilaDeLeitura(panorama.aguardando_leitura)
    : null;

  /** Abre uma aba e, se houver, rola até um ponto dela. O ponto só existe
   *  depois de a aba aparecer — por isso a rolagem espera o desenho. */
  function irPara(qual: AbaDoPainel, ancora = "") {
    setAba(qual);
    window.requestAnimationFrame(() => {
      const alvo = ancora
        ? document.getElementById(ancora)
        : document.getElementById("abas-do-painel");
      alvo?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
  function abrirQuadro(q: QuadroDoTopo) {
    const d = destinoDoQuadro(q);
    setPortal(d.portal);
    setDono(d.dono);
    irPara(d.aba, d.ancora);
  }
  /** O atalho de uma pendência ("Enviar o rol") mora em outra aba. */
  function seguirAtalho(e: MouseEvent) {
    const link = (e.target as HTMLElement).closest("a[href^='#']");
    const ancora = link?.getAttribute("href") ?? "";
    const destino = abaDaAncora(ancora);
    if (!destino) return;
    e.preventDefault();
    irPara(destino, ancora.slice(1));
  }

  // NO TELEFONE, O QUE FICA ACIMA DAS ABAS SÓ APARECE NO RESUMO. Medido em
  // 28/11/2026 num iPhone: quem tocava em "Filiados" via a mesma tela e meia
  // de assistente, números e novidades antes de chegar à lista.
  const soNoResumo = aba === "resumo" ? "" : "hidden lg:block";

  return (
    // `flex` e não `space-y`: é o que deixa as abas subirem para o topo no
    // telefone (`order-first`) sem mudar a ordem no computador.
    <div className="flex flex-col gap-6 [&>*]:min-w-0">
      {/* O PROTO, NO TOPO: era a quinta aba, e a diretoria não chegava
          até ela. A aba continua, para a conversa longa. */}
      <div className={soNoResumo}>
      <ProtoNoTopo
        para="Estou aqui para ajudar a diretoria: digo quantos filiados há na base, com quantos você não consegue falar e o que resolver primeiro. Respondo na hora, com o que está neste painel."
        abertura={ABERTURA_DO_PROTO_DO_GESTOR}
        sugestoes={PERGUNTAS_DO_GESTOR_AO_PROTO}
        perguntar={(p) => api.perguntarComoGestor(entidade, token, p)}
        consultando="Consultando o painel…"
        onSessaoMorta={onSessaoMorta}
      />
      </div>

      {/* OS NÚMEROS DA BASE, antes de tudo — e cada um ABRE a lista do que
          conta. Número que não vira nomes obriga o gestor a procurar por
          conta própria quem são aquelas pessoas. */}
      <div className={"grid-cols-2 gap-3 md:grid-cols-3 md:gap-4 " + (aba === "resumo" ? "grid" : "hidden lg:grid")}>
        <Destaque
          cor="roxo"
          icone={<Users className="h-5 w-5" aria-hidden="true" />}
          valor={r.total}
          rotulo="filiados no acervo"
          onClick={() => abrirQuadro("acervo")}
        />
        <Destaque
          cor="azul"
          icone={<MailX className="h-5 w-5" aria-hidden="true" />}
          valor={r.inalcancaveis}
          rotulo="você não alcança"
          onClick={() => abrirQuadro("inalcancaveis")}
        />
        {/* No celular os dois pequenos ficam lado a lado, na linha de baixo:
            os quatro números cabem numa tela só. */}
        <div className="col-span-2 grid grid-cols-2 gap-3 md:col-span-1 md:grid-cols-1 md:gap-4">
          <Mini
            cor="azul"
            icone={<UserCheck className="h-5 w-5" aria-hidden="true" />}
            valor={r.cadastrados}
            rotulo="cadastrados no portal"
            onClick={() => abrirQuadro("cadastrados")}
          />
          <Mini
            cor="claro"
            icone={<UserX className="h-5 w-5" aria-hidden="true" />}
            valor={r.sem_cadastro}
            rotulo="sem cadastro"
            onClick={() => abrirQuadro("sem_cadastro")}
          />
        </div>
      </div>

      {/* AS NOVIDADES NOS TRIBUNAIS, para a diretoria também: o que foi
          julgado e quantos filiados alcança. */}
      <div className={soNoResumo + " empty:hidden"}>
        <Novidades novidades={teses?.novidades ?? []} />
      </div>

      {/* QUEM JÁ PODE, À VISTA. Os quatro quadros acima são sobre o
          cadastro; este é o resultado, e ficava dentro da aba Filiados,
          atrás de um filtro. Só aparece com o panorama carregado: zero
          antes da resposta chegar seria afirmar que ninguém pode. */}
      {panorama ? (
        <button
          type="button"
          onClick={() => abrirQuadro("podem")}
          className={"w-full flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-bom/30 bg-bom/10 px-5 py-4 text-left hover:bg-bom/15 " + (aba === "resumo" ? "flex" : "hidden lg:flex")}
        >
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-bom text-white">
            <BadgeCheck className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="text-3xl font-bold text-tinta">{panorama.aptos}</span>
          <span className="min-w-0 flex-1 text-[16px] text-tinta">
            <strong>
              {panorama.aptos === 1 ? "filiado já pode" : "filiados já podem"}
            </strong>{" "}
            <span className="text-tinta/70">
              {panorama.aptos
                ? "— têm tudo pronto para um advogado conferir e assinar."
                : "— veja abaixo o que resolver primeiro para isso mudar."}
            </span>
          </span>
          <span className="text-[15px] font-semibold text-acento underline">Ver quem são</span>
        </button>
      ) : null}

      {/* AS ABAS. O painel era uma página só com dez telas de rolagem
          (medido), e o envio da base ficava no fim. As quatro continuam
          montadas — a escondida só não aparece —, para que um arquivo já
          escolhido não se perca ao trocar de aba. */}
      <div
        id="abas-do-painel"
        role="tablist"
        aria-label="Áreas do painel"
        className="order-first grid scroll-mt-4 grid-cols-3 gap-2 rounded-xl bg-carta p-2 shadow-cartao md:flex md:flex-wrap lg:order-none"
      >
        {ABAS_DO_PAINEL.map((a) => (
          <button
            key={a.id}
            type="button"
            role="tab"
            id={`aba-${a.id}`}
            aria-selected={aba === a.id}
            aria-controls={`painel-${a.id}`}
            aria-label={a.rotulo}
            onClick={() => setAba(a.id)}
            className={
              // No iPhone menor (320 pontos) "Documentos" com o contador não
              // cabia em um terço da largura a 15 pontos.
              "rounded-lg px-1 py-3 text-[14px] font-medium transition min-[380px]:px-2 min-[380px]:text-[15px] md:px-4 md:text-base " +
              (aba === a.id
                ? "bg-roxo text-white"
                : "text-tinta hover:bg-lilas")
            }
          >
            <span className="md:hidden">{a.curto}</span>
            <span className="hidden md:inline">{a.rotulo}</span>
            {a.id === "documentos" && (filaNaTela ?? 0) > 0 ? (
              <span className="ml-1 rounded-full bg-alerta px-1.5 py-0.5 text-[13px] text-carta min-[380px]:px-2 min-[380px]:text-sm md:ml-2">
                {filaNaTela}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {/* ------------------------------------------------------- RESUMO */}
      <div
        id="painel-resumo"
        role="tabpanel"
        aria-labelledby="aba-resumo"
        hidden={aba !== "resumo"}
        className="space-y-6"
        onClick={seguirAtalho}
      >
      {panorama ? <MudouDeVeredicto p={panorama} /> : null}
      {filaDeLeitura?.mostra ? (
        // A FILA DE LEITURA HUMANA, à vista. Sem isto o servidor contava e
        // tela nenhuma mostrava — o mesmo erro de entregar pela metade que
        // já custou uma revisão neste repositório.
        <Aviso tom="neutro">
          {filaDeLeitura.frase}{" "}
          <button
            type="button"
            className="underline"
            onClick={() => irPara("documentos")}
          >
            Abrir os documentos para ler
          </button>
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
          <p className="mt-2">
            <button
              type="button"
              className="underline"
              onClick={() => irPara("envios")}
            >
              Enviar a base agora
            </button>
          </p>
        </Aviso>
      ) : null}

      <div className="grid grid-cols-2 gap-3">
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

      <Aviso tom="neutro">
        A movimentação dos processos é atualizada sozinha, com cerca de um dia
        de atraso — é o que a base pública do CNJ entrega.{" "}
        <strong>Não é intimação e não serve para contar prazo.</strong>
      </Aviso>
    </Cartao>
      {/* AS TESES ACOMPANHADAS, no fim do resumo: é o que explica de onde
          vêm as pendências de "conferência por advogado" acima. */}
      <Teses teses={teses?.teses ?? []} />
      </div>

      {/* ----------------------------------------------------- FILIADOS */}
      <div
        id="painel-filiados"
        role="tabpanel"
        aria-labelledby="aba-filiados"
        hidden={aba !== "filiados"}
        className="space-y-6"
      >
        <NomePorNome
          entidade={entidade}
          token={token}
          versao={versaoDaFila}
          portal={portal}
          onPortal={setPortal}
          dono={dono}
          onDono={setDono}
        />

        {dados.inalcancaveis.length ? (
          <div id="nao-alcanca" className="scroll-mt-4">
            <Cartao
              titulo="Quem você não alcança, e por quê"
              explicacao="Contagem não diz a quem ligar. Esta lista diz."
            >
              <div className="space-y-1">
                {dados.inalcancaveis
                  .slice(0, todosForaDeAlcance ? 50 : 5)
                  .map((p) => (
                  <div
                    key={p.chave}
                    className="border-b border-borda py-1 text-sm"
                  >
                    <span className="text-tinta">
                      {p.nome || "(sem nome no acervo)"}
                    </span>
                    <span className="ml-2 text-tinta/70">{p.motivo}</span>
                  </div>
                ))}
              </div>
              {!todosForaDeAlcance && dados.inalcancaveis.length > 5 ? (
                <Botao
                  tipo="secundario"
                  tamanho="pequeno"
                  onClick={() => setTodosForaDeAlcance(true)}
                >
                  Ver os outros {Math.min(dados.inalcancaveis.length, 50) - 5}
                </Botao>
              ) : null}
            </Cartao>
          </div>
        ) : null}
      </div>

      {/* --------------------------------------------------- DOCUMENTOS */}
      <div
        id="painel-documentos"
        role="tabpanel"
        aria-labelledby="aba-documentos"
        hidden={aba !== "documentos"}
        className="space-y-6"
      >
        <FilaDeConferencia
          entidade={entidade}
          token={token}
          onMudou={() => setVersaoDaFila((v) => v + 1)}
          onQuantos={setFilaNaTela}
        />
        {filaNaTela === 0 ? (
          <Cartao titulo="Documentos para ler">
            <Aviso tom="bom">
              Nenhum documento esperando leitura agora.
            </Aviso>
          </Cartao>
        ) : null}
      </div>

      {/* ------------------------------------------------------- ENVIOS */}
      <div
        id="painel-envios"
        role="tabpanel"
        aria-labelledby="aba-envios"
        hidden={aba !== "envios"}
        className="space-y-6"
      >
        <div id="escritorios" className="scroll-mt-4">
          <Escritorios entidade={entidade} token={token} />
        </div>

        <EnviarBase
          entidade={entidade}
          token={token}
          onMudou={() => setVersaoDaFila((v) => v + 1)}
        />

        {/* O `id` é o destino do atalho "Enviar o rol" das pendências. */}
        <div id="rol-de-substituidos" className="scroll-mt-4">
          <RolDeSubstituidos
            entidade={entidade}
            token={token}
            onMudou={() => setVersaoDaFila((v) => v + 1)}
          />
        </div>

        <div id="ficha-financeira" className="scroll-mt-4">
          <FichaFinanceira
            entidade={entidade}
            token={token}
            onMudou={() => setVersaoDaFila((v) => v + 1)}
          />
        </div>

        <ApagarAPedido
          entidade={entidade}
          token={token}
          jaApagados={dados.apagados_a_pedido}
        />
      </div>

      {/* -------------------------------------------------------- PROTO */}
      <div
        id="painel-proto"
        role="tabpanel"
        aria-labelledby="aba-proto"
        hidden={aba !== "proto"}
        className="space-y-6"
      >
        <Cartao
          titulo="Pergunte ao Proto"
          explicacao="O assistente automático do portal: responde com o que está neste painel. A sua pergunta não fica guardada."
        >
          <Conversa
            abertura={ABERTURA_DO_PROTO_DO_GESTOR}
            sugestoesIniciais={PERGUNTAS_DO_GESTOR_AO_PROTO}
            perguntar={(p) => api.perguntarComoGestor(entidade, token, p)}
            consultando="Consultando o painel…"
            onSessaoMorta={onSessaoMorta}
          />
        </Cartao>
      </div>
    </div>
  );
}
