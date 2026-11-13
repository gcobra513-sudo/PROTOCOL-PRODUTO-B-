/**
 * A conta do filiado, de ponta a ponta.
 *
 * SEIS ETAPAS, e a contagem importa: o cadastro do Produto A tinha sete e
 * pedia procuração, identidade e endereço. O Produto B não distribui
 * processo — responde uma pergunta —, e cada campo que ele deixou de pedir é
 * uma pessoa a mais que termina o cadastro.
 *
 * A ETAPA QUE MAIS VALE É A DA FILIAÇÃO. É dela que sai "de quais ações você
 * faz parte", e por isso ela explica por que pergunta em vez de só pedir.
 *
 * O QUE NÃO SE GUARDA NO NAVEGADOR: os bytes dos documentos. O rascunho
 * sobrevive a fechar a aba e é legível por quem usar aquele computador
 * depois — e no computador da sede do sindicato isso é vazamento marcado
 * para a semana que vem. Perder os anexos ao recarregar é o preço, e a tela
 * diz isso.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AcessosDaDemo } from "./componentes/AcessosDaDemo";
import { Casca } from "./componentes/Casca";
import { Privacidade } from "./componentes/Privacidade";
import { Progresso } from "./componentes/Progresso";
import { Aviso, Botao } from "./componentes/ui";
import { Carreira } from "./etapas/Carreira";
import { Confirmar } from "./etapas/Confirmar";
import { Documentos, tiposFaltando } from "./etapas/Documentos";
import { Entrar } from "./etapas/Entrar";
import { Inicio } from "./etapas/Inicio";
import { Processos } from "./etapas/Processos";
import { Voce } from "./etapas/Voce";
import { Atendimento } from "./paginas/Atendimento";
import { Landing } from "./paginas/Landing";
import { MeusProcessos } from "./paginas/MeusProcessos";
import { MinhaArea } from "./paginas/MinhaArea";
import { MinhasAcoes } from "./paginas/MinhasAcoes";
import { Painel } from "./paginas/Painel";
import * as arquivos from "./lib/arquivos";
import { camposDoSindicato, jaTemos, preencher } from "./lib/conhecido";
import * as armazenamento from "./lib/armazenamento";
import { acessosDaDemonstracao, type AcessoDaDemo } from "./lib/demonstracao";
import { enderecoDaArea } from "./lib/entrada";
import * as api from "./lib/envio";
import { baixar, reciboJson } from "./lib/exportar";
import { cliqueQueNavega, paradoDemais } from "./lib/sessao";
import {
  DOCUMENTOS,
  RASCUNHO_VAZIO,
  type DocumentoEnviado,
  type Rascunho,
} from "./lib/tipos";
import { conferirCpf, conferirProcesso } from "./lib/validacao";
import { conferirCompetencia } from "./etapas/Carreira";

const ETAPAS = [
  "Entrar",
  "Você",
  "Carreira e filiação",
  "Processos",
  "Documentos",
  "Conferir",
];

/** O que falta para sair desta etapa. Lista vazia = pode seguir.
 *
 *  A LISTA É O TEXTO QUE A PESSOA LÊ, não um código de erro. "preencher o
 *  campo obrigatório" não diz qual; aqui cada pendência é uma frase. */
function pendencias(
  r: Rascunho,
  etapa: number,
  temToken: boolean,
  jaTemos: string[] = [],
): string[] {
  if (etapa === 0) {
    return temToken ? [] : ["entrar com o código que chegou no seu e-mail"];
  }

  if (etapa === 1) {
    const falta: string[] = [];
    if (!r.identificacao.nome.trim()) falta.push("o seu nome");
    if (conferirCpf(r.identificacao.cpf).length) falta.push("um CPF válido");
    if (!r.identificacao.email.includes("@")) falta.push("um e-mail válido");
    return falta;
  }

  if (etapa === 2) {
    const falta: string[] = [];
    if (!r.carreira.cargo.trim()) falta.push("o seu cargo");
    if (!r.carreira.situacao) falta.push("a sua situação hoje");
    if (!r.filiacao.desde.trim()) {
      falta.push("desde quando você é filiado");
    } else {
      falta.push(...conferirCompetencia(r.filiacao.desde));
    }
    if (r.filiacao.ate.trim()) {
      falta.push(...conferirCompetencia(r.filiacao.ate));
      if (
        !conferirCompetencia(r.filiacao.desde).length &&
        !conferirCompetencia(r.filiacao.ate).length &&
        r.filiacao.ate < r.filiacao.desde
      ) {
        falta.push("corrigir as datas: a filiação termina antes de começar");
      }
    }
    return falta;
  }

  if (etapa === 3) {
    // Etapa opcional por desenho: "não sei" é resposta completa, e quem
    // responde isso é justamente quem mais precisa do produto.
    if (!r.judicial.temProcesso) return ["responder se você tem processo"];
    if (r.judicial.temProcesso !== "sim") return [];
    return r.judicial.numeros
      .filter((n) => n.trim())
      .flatMap((n) => conferirProcesso(n));
  }

  if (etapa === 4) {
    return tiposFaltando(r.documentos, jaTemos).map((tipo) => {
      const espec = DOCUMENTOS.find((d) => d.tipo === tipo);
      return `anexar: ${espec?.rotulo ?? tipo}`;
    });
  }

  if (etapa === 5 && !r.confirmou) {
    return ["marcar a declaração final"];
  }
  return [];
}

/** Os links entre as áreas. Sem eles, cada uma só se alcança digitando o
 *  endereço — e ninguém digita. */
export function App() {
  const apelido = useMemo(() => api.entidadeDoLink(), []);
  // A ÁREA É ESTADO, não endereço lido uma vez: trocar de área não recarrega
  // a página. Recarregava — e a sessão, que só existe na memória, ia embora
  // a cada clique no menu.
  const [tela, setTela] = useState<api.Tela>(() => api.telaDoLink());
  useEffect(() => {
    const voltou = () => setTela(api.telaDoLink());
    window.addEventListener("popstate", voltou);
    return () => window.removeEventListener("popstate", voltou);
  }, []);
  const irPara = useCallback(
    (qual: api.Tela) => {
      window.history.pushState({}, "", enderecoDaArea(qual, apelido));
      setTela(qual);
      window.scrollTo(0, 0);
    },
    [apelido],
  );
  // A pergunta escolhida na Minha área, levada ao Proto. Vale uma vez.
  const [perguntaAoProto, setPerguntaAoProto] = useState("");
  const [entidade, setEntidade] = useState<string | undefined>(undefined);
  const [avisoDemo, setAvisoDemo] = useState("");
  const [acessosDemo, setAcessosDemo] = useState<AcessoDaDemo[]>([]);
  const [comecou, setComecou] = useState(false);
  const [etapa, setEtapa] = useState(0);
  const [token, setToken] = useState("");
  const [rascunho, setRascunho] = useState<Rascunho>(RASCUNHO_VAZIO);
  const [recibo, setRecibo] = useState<api.Recibo | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const [verPrivacidade, setVerPrivacidade] = useState(false);
  const [conhecido, setConhecido] = useState<api.MeuCadastro | null>(null);
  // Por que a pessoa foi posta para fora, quando não foi ela que saiu.
  const [avisoDeSaida, setAvisoDeSaida] = useState("");

  // O NOME da entidade vem do SERVIDOR, do apelido que está no link. O
  // apelido não serve como nome: uma página que se apresenta como sendo de
  // uma entidade sem ter confirmado com o servidor é uma página que mente.
  useEffect(() => {
    if (!apelido) return;
    void api.verEntidade(apelido).then((e) => {
      if (!e) return;
      setEntidade(e.nome);
      if (e.demonstracao) setAvisoDemo(e.aviso_demonstracao ?? "");
      setAcessosDemo(acessosDaDemonstracao(e));
    });
  }, [apelido]);

  // O RASCUNHO NÃO É RESTAURADO AO ABRIR A PÁGINA. Era, e no computador da
  // sede isso punha a segunda pessoa dentro do cadastro da primeira, sem
  // portão (medido em 12/11/2026). Ele volta DEPOIS que o portão confere o
  // CPF, e só se for daquele CPF — ver o efeito do `token`, abaixo.
  //
  // E SÓ É GRAVADO DEPOIS DISSO. `dono` é o CPF para o qual a decisão de
  // restaurar já foi tomada: gravar antes escreveria o formulário ainda
  // vazio por cima do rascunho que a dona veio buscar.
  const [dono, setDono] = useState("");
  useEffect(() => {
    if (comecou && dono && dono === armazenamento.soDigitos(rascunho.identificacao.cpf)) {
      armazenamento.salvar({ ...rascunho, etapa });
    }
  }, [rascunho, etapa, comecou, dono]);

  const mudar = useCallback(
    <S extends keyof Rascunho>(secao: S, campo: string, valor: unknown) => {
      setRascunho((r) => ({
        ...r,
        [secao]: { ...(r[secao] as object), [campo]: valor },
      }));
    },
    [],
  );

  // ASSIM QUE A PESSOA ENTRA, buscamos o que o sindicato já mandou. Ela
  // recebeu o link no grupo do WhatsApp e abriu: encontrar 17 campos em
  // branco — 10 deles já enviados pelo sindicato — é o que faz a aposentada
  // desistir no meio.
  //
  // Falha aqui NÃO trava o cadastro: a tela volta a ser a de antes, em
  // branco, e ela preenche. Pior que não preencher é não deixar entrar.
  useEffect(() => {
    if (!token) return;
    // O PORTÃO ACABOU DE CONFERIR ESTE CPF. Só agora o rascunho guardado
    // pode voltar — e, se era de outra pessoa, `carregarDe` o apaga. A
    // etapa NÃO é restaurada: a pessoa está na tela do portão lendo "acesso
    // confirmado", e ser jogada para a etapa 4 sem aviso é pior que clicar
    // em Continuar e encontrar os campos preenchidos.
    const cpf = rascunho.identificacao.cpf;
    const salvo = armazenamento.carregarDe(cpf);
    if (salvo) {
      setRascunho({
        ...salvo,
        identificacao: { ...salvo.identificacao, cpf },
      });
    }
    setDono(armazenamento.soDigitos(cpf));
    if (!api.servidorLigado()) return;
    void api
      .meuCadastro(token)
      .then((d) => {
        setConhecido(d);
        if (d.conhecido) setRascunho((r) => preencher(r, d.campos));
      })
      .catch(() => setConhecido(null));
  }, [token]);

  // QUEM ENTROU POR OUTRA ÁREA é a mesma pessoa no cadastro. O CPF do portão
  // passa a ser o do formulário — e se o que estava na memória era de outro
  // CPF, não vai junto.
  const entrou = useCallback((novo: string, cpf: string) => {
    setAvisoDeSaida("");
    setRascunho((r) => {
      if (armazenamento.soDigitos(r.identificacao.cpf) === armazenamento.soDigitos(cpf)) {
        return r;
      }
      arquivos.esquecerTudo();
      return armazenamento.limpoPara(cpf);
    });
    setToken(novo);
  }, []);

  // SAIR. Encerra no servidor e esquece TUDO o que está na memória desta
  // página — o formulário, os anexos, o recibo. O rascunho guardado no
  // navegador fica: ele só volta para quem passar pelo portão com o mesmo
  // CPF (T23), e apagá-lo é outro botão, que diz que apaga.
  const encerrar = useCallback(
    (aviso = "") => {
      if (token) void api.sair(token);
      arquivos.esquecerTudo();
      setRascunho(RASCUNHO_VAZIO);
      setConhecido(null);
      setRecibo(null);
      setToken("");
      setDono("");
      setEtapa(0);
      setComecou(false);
      setErro("");
      setAvisoDeSaida(aviso);
    },
    [token],
  );
  const sessaoMorta = useCallback(
    () => encerrar("A sua sessão terminou. Entre de novo para continuar."),
    [encerrar],
  );

  // A TELA PARADA SE FECHA SOZINHA. A sessão vale em todas as áreas, e uma
  // tela esquecida aberta no computador da sede é a sessão de alguém na mão
  // do próximo. Durante o envio não conta: subir os documentos numa
  // conexão lenta é ficar parado sem ter ido embora.
  const ultimaAtividade = useRef(Date.now());
  useEffect(() => {
    if (!token) return;
    const marcar = () => {
      ultimaAtividade.current = Date.now();
    };
    marcar();
    const sinais = ["pointerdown", "keydown", "scroll", "touchstart"] as const;
    for (const s of sinais) window.addEventListener(s, marcar, { passive: true });
    const relogio = window.setInterval(() => {
      if (enviando) marcar();
      else if (paradoDemais(ultimaAtividade.current, Date.now())) {
        encerrar(
          "Você ficou um tempo sem mexer e, por segurança, a sessão foi " +
            "encerrada. Entre de novo para continuar: o que você preencheu " +
            "volta, mas os documentos anexados precisam ser escolhidos de novo.",
        );
      }
    }, 15_000);
    return () => {
      for (const s of sinais) window.removeEventListener(s, marcar);
      window.clearInterval(relogio);
    };
  }, [token, enviando, encerrar]);

  const doSindicato = useMemo(
    () => camposDoSindicato(conhecido?.campos ?? {}),
    [conhecido],
  );

  const falta = pendencias(
    rascunho, etapa, Boolean(token), conhecido?.documentos ?? [],
  );
  const ultima = etapa === ETAPAS.length - 1;

  async function enviar() {
    setErro("");
    setEnviando(true);
    try {
      setRecibo(await api.enviarCadastro(token, rascunho, arquivos.mapa()));
      armazenamento.apagar();
      arquivos.esquecerTudo();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "o envio não completou");
    } finally {
      setEnviando(false);
    }
  }

  // SEM SINDICATO NO LINK, a pessoa chegou pela porta da frente: é a página
  // de entrada, que pergunta de qual sindicato ela é. O cadastro sem
  // sindicato não leva a lugar nenhum — não há a quem pedir o código.
  if (!apelido && tela === "cadastro") {
    return (
      <>
        <Landing onPrivacidade={() => setVerPrivacidade(true)} />
        {verPrivacidade ? (
          <Privacidade onFechar={() => setVerPrivacidade(false)} />
        ) : null}
      </>
    );
  }

  return (
    <Casca
      entidade={entidade}
      tela={tela}
      comServidor={api.servidorLigado()}
      link={(qual) => enderecoDaArea(qual, apelido)}
      onIr={irPara}
      temSessao={Boolean(token)}
      onSair={() => encerrar()}
      onPrivacidade={() => setVerPrivacidade(true)}
    >
      <div
        className={
          tela === "painel"
            ? "mx-auto max-w-5xl space-y-6"
            : "mx-auto max-w-3xl space-y-6"
        }
      >
        {avisoDemo ? (
          <Aviso tom="alerta">
            <strong>Demonstração.</strong> {avisoDemo}
            {/* Quem já entrou não precisa mais da lista. */}
            {!token ? (
              <AcessosDaDemo acessos={acessosDemo} apelido={apelido} />
            ) : null}
          </Aviso>
        ) : null}

        {avisoDeSaida ? <Aviso tom="neutro">{avisoDeSaida}</Aviso> : null}

        {/* O QUE MUDA A CONVERSA: ela não está preenchendo, está conferindo.
            E se já temos documento dela, a tela diz — pedir de novo o que o
            sindicato já mandou é o que faz a pessoa achar que não funciona. */}
        {conhecido?.conhecido && !recibo && tela === "cadastro" ? (
          <Aviso tom="bom">
            {/* O texto do servidor já explica tudo. Repetir a mesma ideia
                em duas frases coladas faz a pessoa parar de ler. */}
            <p>{conhecido.aviso}</p>
            {conhecido.documentos.length ? (
              <p className="mt-2">
                Já temos: {jaTemos(conhecido.documentos).join(", ")}. Você não
                precisa enviar de novo.
              </p>
            ) : null}
          </Aviso>
        ) : null}

        {tela !== "cadastro" && !api.servidorLigado() ? (
          <Aviso tom="alerta">
            <strong>Esta área precisa do servidor do sindicato.</strong> Esta
            página está em modo de demonstração, sem servidor: ela confere
            tudo no seu aparelho e não consulta nada. Peça ao sindicato o
            endereço do portal.
          </Aviso>
        ) : tela === "acoes" ? (
          // `key={token}`: outra sessão é outra pessoa, e a área recomeça do
          // zero. Sem isso, o que a anterior viu ficaria na memória da área
          // e piscaria na tela da próxima até a consulta nova voltar.
          <MinhasAcoes key={token} entidade={apelido} token={token}
                       onToken={entrou} onSessaoMorta={sessaoMorta} />
        ) : tela === "processos" ? (
          <MeusProcessos key={token} entidade={apelido} token={token}
                         onToken={entrou} onSessaoMorta={sessaoMorta} />
        ) : tela === "area" ? (
          <MinhaArea key={token} entidade={apelido} token={token}
                     onToken={entrou} onSessaoMorta={sessaoMorta}
                     onIr={irPara}
                     onPerguntar={(p) => {
                       setPerguntaAoProto(p);
                       irPara("atendimento");
                     }} />
        ) : tela === "atendimento" ? (
          <Atendimento key={token} entidade={apelido} token={token}
                       onToken={entrou} onSessaoMorta={sessaoMorta}
                       perguntaInicial={perguntaAoProto}
                       onPerguntaFeita={() => setPerguntaAoProto("")} />
        ) : tela === "painel" ? (
          <Painel key={token} entidade={apelido} token={token}
                  onToken={entrou} onSessaoMorta={sessaoMorta}
                  onSair={() => encerrar()} />
        ) : recibo ? (
          <div className="space-y-5">
            <Aviso tom="bom">
              <span className="block font-medium">Cadastro enviado.</span>
              <span className="mt-1 block text-sm">
                Guarde o número do protocolo.
              </span>
            </Aviso>
            <div className="rounded-lg border border-borda bg-carta p-5">
              <p className="text-sm text-tinta/60">Protocolo</p>
              <p className="mt-1 select-all font-mono text-2xl font-semibold text-tinta">
                {recibo.protocolo}
              </p>
              <p className="mt-3 text-sm text-tinta/70">
                Recebido em {recibo.recebido_em}. Documentos:{" "}
                {Object.keys(recibo.arquivos).length}.
              </p>
            </div>
            {recibo.aguardando_leitura?.length ? (
              // O SERVIDOR é quem diz, não o navegador: é ele que guarda a
              // marca. Dito no recibo para a pessoa não ficar esperando uma
              // resposta sem saber por que ela demora.
              <Aviso tom="neutro">
                {recibo.aguardando_leitura.length === 1
                  ? "1 dos seus documentos chegou como imagem"
                  : `${recibo.aguardando_leitura.length} dos seus documentos chegaram como imagem`}
                . Eles foram recebidos e vão ser lidos por uma pessoa — a
                resposta sobre eles demora mais que a dos outros.
              </Aviso>
            ) : null}
            <div className="rounded-lg border border-borda bg-papel p-5">
              <p className="font-medium text-tinta">O que acontece agora</p>
              <p className="mt-2 text-[15px] leading-relaxed text-tinta/75">
                A gente lê os seus documentos e cruza com as ações coletivas
                da sua categoria. Em seguida você vai poder ver, aqui mesmo,
                de quais ações faz parte e o que pode ser feito em cada uma.
              </p>
            </div>
            {api.servidorLigado() ? (
              <a
                href={enderecoDaArea("acoes", apelido)}
                onClick={(e) => {
                  // POR DENTRO DA PÁGINA: a sessão que enviou o cadastro
                  // continua valendo para ler, e recarregar a jogaria fora.
                  if (cliqueQueNavega(e)) {
                    e.preventDefault();
                    irPara("acoes");
                  }
                }}
                className="block rounded-md border border-borda bg-carta p-4 text-[15px] font-medium text-tinta underline"
              >
                Ver de quais ações eu faço parte
              </a>
            ) : null}
            <Botao
              tipo="secundario"
              onClick={() =>
                baixar(
                  `recibo-${recibo.protocolo}.json`,
                  reciboJson(rascunho),
                  "application/json",
                )
              }
            >
              Baixar o meu recibo
            </Botao>
          </div>
        ) : !comecou ? (
          <Inicio
            entidade={entidade}
            onComecar={() => setComecou(true)}
            onVerPrivacidade={() => setVerPrivacidade(true)}
          />
        ) : (
          <>
            <Progresso
              etapas={ETAPAS}
              atual={etapa}
              onVoltarPara={(i) => setEtapa(i)}
            />

            {/* SAIR, PARA QUEM ESTÁ NUM COMPUTADOR QUE NÃO É SEU. O rascunho
                fica guardado neste navegador até o envio — é o que evita
                perder tudo ao fechar a aba sem querer. No computador da
                sede, quem vai embora sem terminar precisa de um jeito de
                não deixar nada para trás. */}
            {dono ? (
              <p className="text-sm text-tinta/70">
                Usando um computador que não é seu?{" "}
                <button
                  type="button"
                  className="text-acento underline"
                  onClick={() => {
                    armazenamento.apagar();
                    encerrar();
                  }}
                >
                  Sair e apagar o que preenchi neste computador
                </button>
              </p>
            ) : null}

            {etapa === 0 ? (
              <Entrar
                cpf={rascunho.identificacao.cpf}
                onCpf={(v) => {
                  // TROCOU O CPF DEPOIS DE ALGUÉM TER ENTRADO: é outra
                  // pessoa na mesma aba. O que está na memória — nome,
                  // processos, anexos — era da anterior, e não vai junto.
                  if (token) {
                    setRascunho(armazenamento.limpoPara(v));
                    arquivos.esquecerTudo();
                    setConhecido(null);
                  } else {
                    mudar("identificacao", "cpf", v);
                  }
                  setToken("");
                  setDono("");
                }}
                entidade={apelido}
                temToken={Boolean(token)}
                onToken={(novo) => {
                  setAvisoDeSaida("");
                  setToken(novo);
                }}
              />
            ) : null}

            {etapa === 1 ? (
              <Voce
                dados={rascunho.identificacao}
                onChange={(c, v) => mudar("identificacao", c, v)}
                cpfTravado={Boolean(token)}
              doSindicato={doSindicato}
              />
            ) : null}

            {etapa === 2 ? (
              <Carreira
                carreira={rascunho.carreira}
                filiacao={rascunho.filiacao}
                onCarreira={(campo, valor) => mudar("carreira", campo, valor)}
                onFiliacao={(campo, valor) => mudar("filiacao", campo, valor)}
              doSindicato={doSindicato}
              />
            ) : null}

            {etapa === 3 ? (
              <Processos
                dados={rascunho.judicial}
                onChange={(c, v) => mudar("judicial", c, v)}
              />
            ) : null}

            {etapa === 4 ? (
              <Documentos
                cpf={rascunho.identificacao.cpf}
                enviados={rascunho.documentos}
                onEnviado={(d: DocumentoEnviado) =>
                  setRascunho((r) => ({ ...r, documentos: [...r.documentos, d] }))
                }
                onRemover={(chave: number) => {
                  arquivos.esquecer(chave);
                  setRascunho((r) => ({
                    ...r,
                    documentos: r.documentos.filter((d) => d.chave !== chave),
                  }));
                }}
              />
            ) : null}

            {etapa === 5 ? (
              <Confirmar
                rascunho={rascunho}
                onConfirmar={(v) => setRascunho((r) => ({ ...r, confirmou: v }))}
                onQuerAviso={(v) => setRascunho((r) => ({ ...r, querAviso: v }))}
              />
            ) : null}

            {falta.length ? (
              <Aviso tom="neutro">
                Para seguir, falta: {falta.join("; ")}.
              </Aviso>
            ) : null}

            {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}

            <div className="flex items-center justify-between gap-3">
              <Botao
                tipo="secundario"
                disabled={etapa === 0}
                onClick={() => setEtapa((e) => Math.max(0, e - 1))}
              >
                Voltar
              </Botao>
              <Botao
                tipo="principal"
                disabled={falta.length > 0 || enviando}
                onClick={() =>
                  ultima ? void enviar() : setEtapa((e) => e + 1)
                }
              >
                {ultima ? (enviando ? "Enviando…" : "Enviar") : "Continuar"}
              </Botao>
            </div>
          </>
        )}

      </div>

      {verPrivacidade ? (
        <Privacidade onFechar={() => setVerPrivacidade(false)} />
      ) : null}
    </Casca>
  );
}
