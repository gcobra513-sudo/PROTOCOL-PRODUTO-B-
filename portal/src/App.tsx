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
import { useCallback, useEffect, useMemo, useState } from "react";

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
import { MeusProcessos } from "./paginas/MeusProcessos";
import { MinhasAcoes } from "./paginas/MinhasAcoes";
import { Painel } from "./paginas/Painel";
import * as arquivos from "./lib/arquivos";
import * as armazenamento from "./lib/armazenamento";
import * as api from "./lib/envio";
import { baixar, reciboJson } from "./lib/exportar";
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
function pendencias(r: Rascunho, etapa: number, temToken: boolean): string[] {
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
    return tiposFaltando(r.documentos).map((tipo) => {
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
const AREAS: { tela: api.Tela; rotulo: string }[] = [
  { tela: "cadastro", rotulo: "Meu cadastro" },
  { tela: "acoes", rotulo: "Minhas ações" },
  { tela: "processos", rotulo: "Meus processos" },
];

function linkDaArea(tela: api.Tela, apelido: string): string {
  const q = new URLSearchParams();
  if (apelido) q.set("entidade", apelido);
  if (tela !== "cadastro") q.set("tela", tela);
  const busca = q.toString();
  return busca ? `?${busca}` : "./";
}

export function App() {
  const apelido = useMemo(() => api.entidadeDoLink(), []);
  const tela = useMemo(() => api.telaDoLink(), []);
  const [entidade, setEntidade] = useState<string | undefined>(undefined);
  const [avisoDemo, setAvisoDemo] = useState("");
  const [comecou, setComecou] = useState(false);
  const [etapa, setEtapa] = useState(0);
  const [token, setToken] = useState("");
  const [rascunho, setRascunho] = useState<Rascunho>(RASCUNHO_VAZIO);
  const [recibo, setRecibo] = useState<api.Recibo | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const [verPrivacidade, setVerPrivacidade] = useState(false);

  // O NOME da entidade vem do SERVIDOR, do apelido que está no link. O
  // apelido não serve como nome: uma página que se apresenta como sendo de
  // uma entidade sem ter confirmado com o servidor é uma página que mente.
  useEffect(() => {
    if (!apelido) return;
    void api.verEntidade(apelido).then((e) => {
      if (!e) return;
      setEntidade(e.nome);
      if (e.demonstracao) setAvisoDemo(e.aviso_demonstracao ?? "");
    });
  }, [apelido]);

  useEffect(() => {
    const salvo = armazenamento.carregar();
    if (salvo && salvo.versao === RASCUNHO_VAZIO.versao) {
      setRascunho(salvo);
      setEtapa(salvo.etapa);
      setComecou(true);
    }
  }, []);

  useEffect(() => {
    if (comecou) armazenamento.salvar({ ...rascunho, etapa });
  }, [rascunho, etapa, comecou]);

  const mudar = useCallback(
    <S extends keyof Rascunho>(secao: S, campo: string, valor: unknown) => {
      setRascunho((r) => ({
        ...r,
        [secao]: { ...(r[secao] as object), [campo]: valor },
      }));
    },
    [],
  );

  const falta = pendencias(rascunho, etapa, Boolean(token));
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

  return (
    <div className="min-h-screen bg-papel">
      <header className="border-b border-borda bg-carta">
        <div className="mx-auto max-w-3xl px-4 py-4 sm:px-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-alerta">
            Protótipo — não é o portal oficial
          </p>
          <p className="mt-0.5 text-lg font-semibold text-tinta">
            {entidade ?? "Seus direitos, organizados"}
          </p>
          {api.servidorLigado() ? (
            <nav className="mt-2 flex flex-wrap gap-4 text-sm">
              {AREAS.map((a) => (
                <a
                  key={a.tela}
                  href={linkDaArea(a.tela, apelido)}
                  aria-current={a.tela === tela ? "page" : undefined}
                  className={
                    a.tela === tela
                      ? "font-semibold text-tinta"
                      : "text-acento underline"
                  }
                >
                  {a.rotulo}
                </a>
              ))}
            </nav>
          ) : null}
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        {avisoDemo ? (
          <Aviso tom="alerta">
            <strong>Demonstração.</strong> {avisoDemo}
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
          <MinhasAcoes entidade={apelido} />
        ) : tela === "processos" ? (
          <MeusProcessos entidade={apelido} />
        ) : tela === "painel" ? (
          <Painel entidade={apelido} />
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
                href={linkDaArea("acoes", apelido)}
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

            {etapa === 0 ? (
              <Entrar
                cpf={rascunho.identificacao.cpf}
                onCpf={(v) => {
                  mudar("identificacao", "cpf", v);
                  setToken("");
                }}
                entidade={apelido}
                temToken={Boolean(token)}
                onToken={setToken}
              />
            ) : null}

            {etapa === 1 ? (
              <Voce
                dados={rascunho.identificacao}
                onChange={(c, v) => mudar("identificacao", c, v)}
                cpfTravado={Boolean(token)}
              />
            ) : null}

            {etapa === 2 ? (
              <Carreira
                carreira={rascunho.carreira}
                filiacao={rascunho.filiacao}
                onCarreira={(campo, valor) => mudar("carreira", campo, valor)}
                onFiliacao={(campo, valor) => mudar("filiacao", campo, valor)}
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

        <footer className="pt-4 text-sm">
          <button
            type="button"
            onClick={() => setVerPrivacidade(true)}
            className="text-acento underline"
          >
            Como tratamos os seus dados
          </button>
        </footer>
      </main>

      {verPrivacidade ? (
        <Privacidade onFechar={() => setVerPrivacidade(false)} />
      ) : null}
    </div>
  );
}
