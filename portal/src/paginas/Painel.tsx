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

import { MailX, UserCheck, UserX, Users } from "lucide-react";

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
  resumoDoEnvioDoRol,
  resumoDoRolVigente,
  resumoDoAcesso,
  resumoDasMudancas,
  resumoDoApagamento,
  rotuloDoDispositivo,
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
}: {
  entidade: string;
  token: string;
  doc: api.DocumentoNaFila;
  dispositivos: string[];
  onFeito: () => void;
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
    <div className="space-y-4 rounded-lg border border-borda bg-carta p-4">
      <div>
        <p className="text-[15px] font-medium text-tinta">{doc.nome}</p>
        <p className="mt-0.5 text-sm text-tinta/70">{doc.rotulo}</p>
      </div>
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
}: {
  entidade: string;
  token: string;
  onMudou: () => void;
}) {
  const [fila, setFila] = useState<api.Conferencia | null>(null);
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
      {fila.pendentes.map((doc) => (
        <DocumentoParaLer
          key={doc.id}
          entidade={entidade}
          token={token}
          doc={doc}
          dispositivos={fila.dispositivos}
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


/** Quantas linhas a tela mostra de uma vez. A base pode ter milhares; a
 *  busca e o filtro acham quem se procura, e a planilha leva todo mundo. */
const LINHAS_NA_TELA = 50;

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
}: {
  entidade: string;
  token: string;
  /** Sobe quando a base muda (planilha gravada, leitura registrada). */
  versao: number;
}) {
  const [lista, setLista] = useState<api.PessoaNaLista[] | null>(null);
  const [texto, setTexto] = useState("");
  const [dono, setDono] = useState("");
  const [erro, setErro] = useState("");
  const [baixando, setBaixando] = useState(false);

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
  const filtradas = filtrarPessoas(lista, { texto, dono });
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
      <Campo
        rotulo="Procurar pelo nome"
        valor={texto}
        onChange={setTexto}
        placeholder="Ex.: maria"
      />
      <div className="flex flex-wrap gap-2">
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
        {filtradas.length > LINHAS_NA_TELA
          ? ` — mostrando as primeiras ${LINHAS_NA_TELA}. A planilha traz todas.`
          : "."}
      </p>

      <div className="space-y-1">
        {filtradas.slice(0, LINHAS_NA_TELA).map((p) => (
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

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}
      <div>
        <Botao
          tipo="secundario"
          disabled={baixando}
          onClick={() => void baixar()}
        >
          {baixando ? "Preparando…" : "Baixar a planilha da base"}
        </Botao>
        <p className="mt-2 text-sm text-tinta/60">
          A planilha traz o CPF inteiro de cada pessoa, para você casar com
          os seus registros. Fica registrado quem baixou.
        </p>
      </div>
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

export function Painel({ entidade }: { entidade: string }) {
  const [token, setToken] = useState("");
  const [dados, setDados] = useState<api.PainelDoGestor | null>(null);
  const [panorama, setPanorama] = useState<api.Panorama | null>(null);
  const [erroPanorama, setErroPanorama] = useState("");
  const [erro, setErro] = useState("");
  // Sobe a cada leitura registrada: a fila mudou, e a contagem do panorama
  // tem de mudar junto — número parado ao lado de uma fila que anda parece
  // defeito mesmo quando não é.
  const [versaoDaFila, setVersaoDaFila] = useState(0);

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
      {/* OS NÚMEROS DA BASE, antes de tudo: é a primeira coisa que a
          diretoria quer saber, e eles já vinham no retrato — só estavam
          três cartões abaixo. Os mesmos valores, do mesmo lugar. */}
      <div className="grid gap-4 md:grid-cols-3">
        <Destaque
          cor="roxo"
          icone={<Users className="h-5 w-5" aria-hidden="true" />}
          valor={r.total}
          rotulo="filiados no acervo"
        />
        <Destaque
          cor="azul"
          icone={<MailX className="h-5 w-5" aria-hidden="true" />}
          valor={r.inalcancaveis}
          rotulo="você não alcança"
        />
        <div className="grid gap-4">
          <Mini
            cor="azul"
            icone={<UserCheck className="h-5 w-5" aria-hidden="true" />}
            valor={r.cadastrados}
            rotulo="cadastrados no portal"
          />
          <Mini
            cor="claro"
            icone={<UserX className="h-5 w-5" aria-hidden="true" />}
            valor={r.sem_cadastro}
            rotulo="sem cadastro"
          />
        </div>
      </div>
      {panorama ? <MudouDeVeredicto p={panorama} /> : null}
      {panorama && resumoDaFilaDeLeitura(panorama.aguardando_leitura).mostra ? (
        // A FILA DE LEITURA HUMANA, à vista. Sem isto o servidor contava e
        // tela nenhuma mostrava — o mesmo erro de entregar pela metade que
        // já custou uma revisão neste repositório.
        <Aviso tom="neutro">
          {resumoDaFilaDeLeitura(panorama.aguardando_leitura).frase}
        </Aviso>
      ) : null}
      <FilaDeConferencia
        entidade={entidade}
        token={token}
        onMudou={() => setVersaoDaFila((v) => v + 1)}
      />
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

      <NomePorNome entidade={entidade} token={token} versao={versaoDaFila} />

      <EnviarBase
        entidade={entidade}
        token={token}
        onMudou={() => setVersaoDaFila((v) => v + 1)}
      />

      <RolDeSubstituidos
        entidade={entidade}
        token={token}
        onMudou={() => setVersaoDaFila((v) => v + 1)}
      />

      <ApagarAPedido
        entidade={entidade}
        token={token}
        jaApagados={dados.apagados_a_pedido}
      />
    </div>
  );
}
