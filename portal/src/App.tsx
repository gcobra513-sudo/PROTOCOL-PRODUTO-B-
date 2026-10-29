/**
 * O formulário em sete etapas.
 *
 * REGRAS DE NAVEGAÇÃO, e por quê:
 *
 * - "Próximo" só habilita quando a etapa está completa. A alternativa — deixar
 *   avançar e reclamar no fim — produz o abandono que a especificação quer
 *   evitar, e faz a pessoa descobrir seis erros de uma vez;
 * - o indicador de progresso deixa VOLTAR, nunca pular adiante. A etapa 6
 *   precisa do CPF validado na 1 para procurar o CPF dentro do documento;
 * - o rascunho é salvo a cada mudança. Perder o preenchimento no meio é a
 *   principal causa de abandono.
 */
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Send, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Toaster, toast } from "sonner";

import { Privacidade } from "./componentes/Privacidade";
import { Progresso } from "./componentes/Progresso";
import { Aviso, Botao, cn } from "./componentes/ui";
import { E0Inicio } from "./etapas/E0Inicio";
import { E1Entrar } from "./etapas/E1Entrar";
import { E2OQueVemPorAi } from "./etapas/E2OQueVemPorAi";
import { E3Pessoais } from "./etapas/E3Pessoais";
import { E4Funcional } from "./etapas/E4Funcional";
import { E5Processo } from "./etapas/E5Processo";
import { MeusProcessos } from "./paginas/MeusProcessos";
import { Painel } from "./paginas/Painel";
import { E6Documentos } from "./etapas/E6Documentos";
import { E7Declaracoes } from "./etapas/E7Declaracoes";
import * as arquivosEmMemoria from "./lib/arquivos";
import * as armazem from "./lib/armazenamento";
import * as api from "./lib/envio";
import {
  DOCUMENTOS,
  RASCUNHO_VAZIO,
  type DocumentoEnviado,
  type Rascunho,
  type TipoDocumento,
} from "./lib/tipos";
import { conferirCpf, conferirProcesso, destinoDoNumero } from "./lib/validacao";

const ETAPAS = [
  "Entrar",
  "O que pedimos",
  "Seus dados",
  "Situação",
  "Processo",
  "Documentos",
  "Confirmar",
];

/** O que falta para a etapa estar completa. Lista vazia = pode avançar. */
function pendencias(
  r: Rascunho,
  etapa: number,
  exigirAcesso = false,
): string[] {
  const falta: string[] = [];
  const exigir = (valor: string, nome: string) => {
    if (!valor.trim()) falta.push(nome);
  };

  if (etapa === 0) {
    const falhas = conferirCpf(r.pessoais.cpf);
    // Com servidor, o acesso confirmado é parte de estar completo. Sem isso
    // a pessoa preencheria as sete etapas para descobrir no fim que não
    // entrou.
    if (!falhas.length && exigirAcesso) return ["confirmar o acesso"];
    return falhas;
  }
  if (etapa === 1) return [];

  if (etapa === 2) {
    const p = r.pessoais;
    exigir(p.nome, "nome completo");
    exigir(p.email, "e-mail");
    exigir(p.telefone, "telefone");
    exigir(p.dataNascimento, "data de nascimento");
    exigir(p.cep, "CEP");
    exigir(p.logradouro, "logradouro");
    exigir(p.numero, "número");
    exigir(p.bairro, "bairro");
    exigir(p.municipio, "município");
    exigir(p.uf, "UF");
    if (!p.email.includes("@")) falta.push("um e-mail válido");
    return falta;
  }

  if (etapa === 3) {
    const f = r.funcional;
    exigir(f.cargo, "cargo");
    exigir(f.situacao, "situação atual");
    exigir(f.dataIngresso, "data de ingresso");
    if (
      (f.situacao === "aposentado" || f.situacao === "pensionista") &&
      !f.dataAposentadoria
    ) {
      falta.push("a data da aposentadoria ou do início da pensão");
    }
    return falta;
  }

  if (etapa === 4) {
    // "não sei" e "não tenho" são respostas COMPLETAS, de propósito.
    if (!r.processo.temProcesso) return ["responder se você tem sentença"];
    const doAcompanhamento = r.processo.acompanhar
      .filter((n) => n)
      .flatMap((n) => conferirProcesso(n));
    if (r.processo.temProcesso !== "sim") return doAcompanhamento;
    // A trava, e não é zelo: o servidor RECUSA número fora do TRF1 no campo
    // da sentença, porque a execução corre no juízo que decidiu (CPC, art.
    // 516, II). Sem isto a pessoa preenche, é avisada, envia e é reprovada —
    // descobrindo no fim o que dava para saber aqui. A tela oferece mover o
    // número para acompanhamento; esta linha é o que torna a oferta efetiva.
    if (destinoDoNumero(r.processo.numero) === "acompanhar") {
      return [
        "mover o processo de outro tribunal para acompanhamento, ou corrigir " +
          "o número da sentença",
        ...doAcompanhamento,
      ];
    }
    return [...conferirProcesso(r.processo.numero), ...doAcompanhamento];
  }

  if (etapa === 5) {
    for (const spec of DOCUMENTOS) {
      if (!spec.obrigatorio) continue;
      // O motor exige sentença e certidão de trânsito SÓ de quem declarou
      // "sim" para ter processo — está no contrato compartilhado. Exigi-las
      // de quem não sabe o número, ou de quem não tem sentença, travaria o
      // cadastro num documento que a pessoa não tem como apresentar.
      if (spec.soComProcesso && r.processo.temProcesso !== "sim") continue;
      if (!r.documentos.some((d) => d.tipo === spec.tipo)) {
        falta.push(spec.rotulo.toLowerCase());
      } else if (exigirAcesso && !arquivosEmMemoria.tem(spec.tipo)) {
        // Recarregar a página mantém o que foi digitado e perde os anexos,
        // de propósito (ver `lib/arquivos.ts`). Melhor dizer "reanexe" aqui
        // que estourar no envio.
        falta.push(`reanexar ${spec.rotulo.toLowerCase()}`);
      }
    }
    return falta;
  }

  const d = r.declaracoes;
  if (!d.jaExecutou) falta.push("a 1ª pergunta");
  if (!d.jaRecebeu) falta.push("a 2ª pergunta");
  if (!d.outroAdvogado) falta.push("a 3ª pergunta");
  if (!d.cienciaEIniciativa) falta.push("a declaração final");
  return falta;
}

export default function App() {
  const [rascunho, setRascunho] = useState<Rascunho>(RASCUNHO_VAZIO);
  const [etapa, setEtapa] = useState(0);
  const [recuperado, setRecuperado] = useState(false);
  // A pessoa já saiu da página inicial? Quem tem rascunho salvo já saiu.
  const [comecou, setComecou] = useState(false);
  const [token, setToken] = useState("");
  const [recibo, setRecibo] = useState<api.Recibo | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [verPrivacidade, setVerPrivacidade] = useState(false);
  const rascunhoLigado = useMemo(() => armazem.disponivel(), []);

  const comServidor = useMemo(() => api.servidorLigado(), []);
  const apelido = useMemo(() => api.entidadeDoLink(), []);
  // Qual tela o link pede. Três telas, um só aplicativo: o cadastro
  // (?entidade=...), a consulta do filiado (&consulta) e o painel do gestor
  // (&painel). Sem roteador porque não há navegação entre elas — cada uma é
  // um endereço que alguém recebe pronto, e o portão de cada uma é o mesmo.
  const tela = useMemo(() => api.telaDoLink(), []);

  // O NOME da entidade vem do SERVIDOR, a partir do apelido que está no link
  // (?entidade=...). O apelido não serve como nome: "sind-ensaio" é
  // identificador, e escrevê-lo no cabeçalho de uma página que a pessoa
  // associa ao próprio sindicato é mostrar chave de banco como texto para
  // gente ler. Foi exatamente isso que o ensaio geral pegou.
  //
  // E o nome não está embutido no código porque a pessoa chega por um link do
  // próprio sindicato: uma página que se apresenta como sendo de uma entidade
  // sem ela ter mandado o link é problema nosso, não dela. Sem servidor ou
  // sem apelido, a página não cita ninguém — que é a resposta certa.
  const [entidade, setEntidade] = useState<string | undefined>(undefined);
  const [avisoDemo, setAvisoDemo] = useState("");
  useEffect(() => {
    if (!apelido) return;
    let vivo = true;
    void api.verEntidade(apelido).then((e) => {
      if (!vivo || !e) return;
      if (e.nome) setEntidade(e.nome);
      // Quem chega pelo link não tem como adivinhar que o servidor é de
      // teste — e poderia enviar identidade e procuração de verdade para um
      // disco que se apaga a cada reinício.
      if (e.demonstracao) setAvisoDemo(e.aviso_demonstracao ?? "");
    });
    return () => {
      vivo = false;
    };
  }, [apelido]);

  // Recupera o rascunho uma vez, na abertura.
  useEffect(() => {
    const salvo = armazem.carregar();
    if (salvo) {
      setRascunho(salvo);
      setEtapa(Math.min(salvo.etapa, ETAPAS.length - 1));
      setRecuperado(true);
      setComecou(true);
    }
  }, []);

  // Salva a cada mudança. Nunca guarda o conteúdo dos documentos.
  useEffect(() => {
    if (!comecou) return;
    if (rascunho === RASCUNHO_VAZIO) return;
    armazem.salvar({ ...rascunho, etapa });
  }, [comecou, rascunho, etapa]);

  const mudar = useCallback(
    <S extends keyof Rascunho>(secao: S, campo: string, valor: unknown) => {
      setRascunho((r) => ({
        ...r,
        [secao]: { ...(r[secao] as object), [campo]: valor },
      }));
    },
    [],
  );

  const falta = pendencias(
    rascunho,
    etapa,
    comServidor && (etapa === 0 ? !token : true),
  );
  const podeAvancar = falta.length === 0;
  const ultima = etapa === ETAPAS.length - 1;

  async function enviar() {
    setEnviando(true);
    try {
      const r = await api.enviarCadastro(token, rascunho, arquivosEmMemoria.mapa());
      setRecibo(r);
      // O token vale um envio. Guardar o rascunho depois disso só serviria
      // para a pessoa reabrir um cadastro que já foi entregue.
      armazem.apagar();
      arquivosEmMemoria.esquecerTudo();
      setToken("");
      toast.success(`Cadastro enviado — protocolo ${r.protocolo}`, {
        duration: 12000,
      });
    } catch (e) {
      const problemas =
        e instanceof api.ErroDoServidor && e.problemas.length
          ? e.problemas.join("; ")
          : "";
      toast.error(e instanceof Error ? e.message : String(e), {
        description: problemas || undefined,
        duration: 14000,
      });
    } finally {
      setEnviando(false);
    }
  }

  function avancar() {
    if (!podeAvancar) return;
    if (ultima) {
      if (comServidor && token) {
        void enviar();
        return;
      }
      // O envio depende do servidor do portal, que ainda não existe. A tela
      // diz isso em vez de simular sucesso: tela que finge que enviou é pior
      // que tela que avisa que ainda não envia.
      toast.info("Cadastro completo neste aparelho", {
        description:
          "O envio para o escritório depende do servidor do portal, que " +
          "ainda não está ligado. Nada foi transmitido.",
        duration: 8000,
      });
      return;
    }
    setEtapa((e) => e + 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="min-h-dvh bg-papel">
      <Toaster position="top-center" />
      {verPrivacidade ? (
        <Privacidade onFechar={() => setVerPrivacidade(false)} />
      ) : null}
      <header className="border-b border-borda bg-carta">
        <div className="mx-auto max-w-3xl px-4 py-4 sm:px-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-alerta">
            Protótipo — não é o portal oficial
          </p>
          {/* `p`, não `h1`: o título da PÁGINA é o da etapa (ou o da página
              inicial). Dois `h1` fazem o leitor de tela anunciar dois títulos
              principais e a pessoa não sabe onde está. Este é o nome do
              serviço, que é faixa, não cabeçalho. */}
          <p className="mt-0.5 text-lg font-semibold text-tinta">
            {tela === "painel"
              ? "Painel do sindicato"
              : tela === "consulta"
                ? "Acompanhamento de processos"
                : "Cadastro para execução de sentença"}
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        {avisoDemo ? (
          <Aviso tom="alerta">
            <strong>Demonstração.</strong> {avisoDemo}
          </Aviso>
        ) : null}
        {tela === "painel" ? (
          <Painel entidade={apelido} />
        ) : tela === "consulta" ? (
          <MeusProcessos entidade={apelido} />
        ) : recibo ? (
          <div className="space-y-5">
            <Aviso tom="bom">
              <span className="block font-medium">Cadastro enviado.</span>
              <span className="mt-1 block text-sm">
                Guarde o número do protocolo. É por ele que o escritório
                localiza o seu cadastro.
              </span>
            </Aviso>
            <div className="rounded-lg border border-borda bg-carta p-5">
              <p className="text-sm text-tinta/60">Protocolo</p>
              <p className="mt-1 select-all font-mono text-2xl font-semibold text-tinta">
                {recibo.protocolo}
              </p>
              <p className="mt-3 text-sm text-tinta/70">
                Recebido em {recibo.recebido_em}. Documentos enviados:{" "}
                {Object.keys(recibo.arquivos).length}.
              </p>
              {recibo.substituiu_protocolo ? (
                <p className="mt-2 text-sm text-tinta/70">
                  Este envio substituiu o cadastro anterior (
                  {recibo.substituiu_protocolo}), que foi guardado.
                </p>
              ) : null}
            </div>
            <div className="rounded-lg border border-borda bg-papel p-5">
              <p className="font-medium text-tinta">O que acontece agora</p>
              <p className="mt-2 text-[15px] leading-relaxed text-tinta/75">
                O escritório analisa os documentos e decide o que é possível
                pedir. Essa avaliação é dele, e pode levar alguns dias. Se
                faltar algum documento, você será procurado pelo contato que
                informou.
              </p>
            </div>
            <Botao
              tipo="secundario"
              onClick={() => {
                setRecibo(null);
                setRascunho(RASCUNHO_VAZIO);
                setEtapa(0);
                setComecou(false);
              }}
            >
              Cadastrar outra pessoa
            </Botao>
          </div>
        ) : !comecou ? (
          <E0Inicio
            entidade={entidade}
            onComecar={() => {
              setComecou(true);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
            onVerPrivacidade={() => setVerPrivacidade(true)}
          />
        ) : (
          <>
        <Progresso
          etapas={ETAPAS}
          atual={etapa}
          onVoltarPara={(i) => {
            setEtapa(i);
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />

        {recibo ? null : recuperado && etapa > 0 ? (
          <Aviso tom="bom">
            <span className="flex flex-wrap items-center justify-between gap-2">
              <span>Recuperamos o que você já havia preenchido.</span>
              <Botao
                tipo="discreto"
                tamanho="pequeno"
                onClick={() => {
                  armazem.apagar();
                  setRascunho(RASCUNHO_VAZIO);
                  setEtapa(0);
                  setRecuperado(false);
                  setComecou(false);
                  setToken("");
                  arquivosEmMemoria.esquecerTudo();
                  toast.success("Começamos de novo.");
                }}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                Começar de novo
              </Botao>
            </span>
          </Aviso>
        ) : null}

        <AnimatePresence mode="wait">
          <motion.div
            key={etapa}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }}
            transition={{ duration: 0.18 }}
          >
            {etapa === 0 ? (
              <E1Entrar
                cpf={rascunho.pessoais.cpf}
                onCpf={(v) => {
                  mudar("pessoais", "cpf", v);
                  setToken("");
                }}
                entidade={apelido}
                temToken={Boolean(token)}
                onToken={setToken}
              />
            ) : null}
            {etapa === 1 ? (
              <E2OQueVemPorAi
                rascunhoLigado={rascunhoLigado}
                onVerPrivacidade={() => setVerPrivacidade(true)}
              />
            ) : null}
            {etapa === 2 ? (
              <E3Pessoais
                dados={rascunho.pessoais}
                onChange={(c, v) => mudar("pessoais", c, v)}
              />
            ) : null}
            {etapa === 3 ? (
              <E4Funcional
                dados={rascunho.funcional}
                onChange={(c, v) => mudar("funcional", c, v)}
              />
            ) : null}
            {etapa === 4 ? (
              <E5Processo
                dados={rascunho.processo}
                onChange={(c, v) => mudar("processo", c, v)}
              />
            ) : null}
            {etapa === 5 ? (
              <E6Documentos
                rascunho={rascunho}
                enviados={rascunho.documentos}
                onEnviado={(d: DocumentoEnviado) =>
                  setRascunho((r) => ({
                    ...r,
                    documentos: [
                      ...r.documentos.filter((x) => x.tipo !== d.tipo),
                      d,
                    ],
                  }))
                }
                onRemover={(tipo: TipoDocumento) =>
                  setRascunho((r) => ({
                    ...r,
                    documentos: r.documentos.filter((x) => x.tipo !== tipo),
                  }))
                }
              />
            ) : null}
            {etapa === 6 ? (
              <E7Declaracoes
                dados={rascunho.declaracoes}
                onChange={(c, v) => mudar("declaracoes", c, v)}
              />
            ) : null}
          </motion.div>
        </AnimatePresence>

        {/* O que falta, escrito. Botão cinza sem explicação é armadilha. */}
        {!podeAvancar && falta.length ? (
          <p className="text-sm text-tinta/70" role="status">
            Para continuar, falta: <strong>{falta.join(", ")}</strong>.
          </p>
        ) : null}

        <div
          className={cn(
            "flex items-center justify-between gap-3 border-t border-borda pt-5",
            (!comecou || recibo) && "hidden",
          )}
        >
          <Botao
            tipo="secundario"
            disabled={etapa === 0}
            onClick={() => {
              setEtapa((e) => Math.max(0, e - 1));
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Voltar
          </Botao>

          <Botao disabled={!podeAvancar || enviando} onClick={avancar}>
            {ultima
              ? enviando
                ? "Enviando…"
                : comServidor && token
                  ? "Enviar ao escritório"
                  : "Concluir"
              : "Próximo"}
            {ultima ? (
              <Send className="h-4 w-4" aria-hidden="true" />
            ) : (
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            )}
          </Botao>
        </div>

          </>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pb-4">
          <button
            type="button"
            onClick={() => setVerPrivacidade(true)}
            className="text-sm text-acento underline underline-offset-2
              hover:no-underline focus-visible:outline focus-visible:outline-2
              focus-visible:outline-acento"
          >
            Como tratamos os seus dados
          </button>
          <p className="text-xs leading-relaxed text-tinta/50">
            {comServidor
              ? "Os seus documentos são conferidos neste aparelho e enviados ao escritório somente quando você confirma."
              : "Protótipo para avaliação. Os dados ficam apenas neste navegador e nada é transmitido."}{" "}
            As cores e o nome não são a identidade visual de nenhuma entidade.
          </p>
        </div>
      </main>
    </div>
  );
}
