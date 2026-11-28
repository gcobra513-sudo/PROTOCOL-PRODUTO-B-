/**
 * O PAINEL DO ESCRITÓRIO que o sindicato contratou.
 *
 * O escritório recebia o filiado por e-mail e WhatsApp: documento solto,
 * sem saber quem o sindicato tinha encaminhado nem por qual ação. Aqui ele
 * tem o que o gestor do sindicato tem do lado dele — os números no topo, a
 * fila que se filtra e se procura, a planilha — e, em cada caso, os
 * documentos da pessoa e o que ele marca. O que ele marca aparece para o
 * filiado e para o sindicato, e é isso que tira o telefone do meio.
 *
 * A PRIMEIRA VERSÃO era uma pilha de dezoito cartões abertos, um por caso:
 * cinco telas de rolagem para achar uma pessoa. Agora cada caso é uma
 * linha, e abre quando se toca.
 *
 * O que esta tela NÃO faz: o trabalho de dentro do escritório. Ela termina
 * em "documentação completa".
 */
import {
  Building2,
  CheckCheck,
  Landmark,
  Megaphone,
  Scale,
  ChevronDown,
  Clock,
  Download,
  FileQuestion,
  FileText,
  Inbox,
  Mail,
  Phone,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Historico } from "../componentes/Historico";
import { ProtoNoTopo } from "../componentes/ProtoNoTopo";
import { Aviso, Botao, Campo, Cartao, Destaque, Mini } from "../componentes/ui";
import * as api from "../lib/envio";
import { haQuanto, rotuloDaSituacaoDaTese, saudacao, tesesJuntas, type TeseJunta } from "../lib/teses";
import {
  csvDosCasos,
  diasNaFila,
  filtrarCasos,
  ordemDeTrabalho,
  rotuloDaSituacao,
  tomDaSituacao,
} from "../lib/escritorio";
import { formatarCpf } from "../lib/validacao";
import { Portao } from "./Portao";

const CORES = {
  bom: "border-bom/40 bg-bom/10 text-bom",
  neutro: "border-borda bg-papel text-tinta/80",
  alerta: "border-alerta/40 bg-alerta/10 text-alerta",
} as const;

const PERGUNTAS = [
  "Teve novidade nos tribunais?",
  "Quantos casos eu tenho?",
  "O que eu abro primeiro?",
  "De quem falta documento?",
  "Quem está com a documentação completa?",
];

const ABERTURA = [
  "Olá. Sou o Proto, o assistente automático do portal.",
  "Aqui eu respondo sobre os casos que o sindicato encaminhou a este escritório: quantos são, por onde começar, de quem falta documento — ou como está o caso de uma pessoa, é só escrever o nome.",
];

function Selo({ situacao }: { situacao: string }) {
  return (
    <span
      className={`inline-block shrink-0 rounded-full border px-3 py-1 text-[13px] font-semibold ${CORES[tomDaSituacao(situacao)]}`}
    >
      {rotuloDaSituacao(situacao)}
    </span>
  );
}

function Linha({
  caso,
  comSindicato,
  possiveis,
  aberto,
  ocupado,
  onAlternar,
  onAbrir,
  onSituar,
}: {
  caso: api.CasoDoEscritorio;
  /** Com mais de um sindicato, a linha diz de qual é o caso. */
  comSindicato: boolean;
  possiveis: { tipo: string; rotulo: string }[];
  aberto: boolean;
  ocupado: boolean;
  onAlternar: () => void;
  onAbrir: (arquivo: string) => void;
  onSituar: (situacao: string, faltam?: string[]) => void;
}) {
  const [escolhendo, setEscolhendo] = useState(false);
  const [faltam, setFaltam] = useState<string[]>(caso.faltam);
  const rotulo = (tipo: string) => possiveis.find((p) => p.tipo === tipo)?.rotulo ?? tipo;
  const dias = diasNaFila(caso.encaminhado_em, new Date());
  const esperando = caso.situacao === "ENCAMINHADO";

  return (
    <div className="rounded-lg border border-borda bg-carta">
      <button
        type="button"
        aria-expanded={aberto}
        onClick={onAlternar}
        className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-left hover:bg-lilas/40"
      >
        {/* NO TELEFONE O NOME OCUPA A LINHA INTEIRA; os detalhes vão para a
            de baixo. Lado a lado, o nome virava "JOSE DE EX…". */}
        <span className="min-w-0 basis-full sm:flex-1 sm:basis-0">
          <span className="block text-[16px] font-semibold text-tinta sm:truncate">{caso.nome}</span>
          <span className="block text-sm text-tinta/65">
            CPF {formatarCpf(caso.cpf)} · {caso.rotulo}
          </span>
          {comSindicato && caso.sindicato ? (
            <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-ceu px-2.5 py-0.5 text-[13px] font-medium text-tinta">
              <Building2 className="h-3.5 w-3.5" aria-hidden="true" /> {caso.sindicato}
            </span>
          ) : null}
        </span>
        <span className="flex items-center gap-1 text-sm text-tinta/70">
          <FileText className="h-4 w-4" aria-hidden="true" />
          {caso.documentos.length} {caso.documentos.length === 1 ? "documento" : "documentos"}
        </span>
        {dias !== null ? (
          <span
            className={
              "flex items-center gap-1 text-sm " +
              (esperando && dias > 7 ? "font-semibold text-alerta" : "text-tinta/70")
            }
          >
            <Clock className="h-4 w-4" aria-hidden="true" />
            {dias === 0 ? "hoje" : dias === 1 ? "há 1 dia" : `há ${dias} dias`}
          </span>
        ) : null}
        <Selo situacao={caso.situacao} />
        <ChevronDown
          className={"ml-auto h-5 w-5 shrink-0 text-acento transition-transform sm:ml-0 " + (aberto ? "rotate-180" : "")}
          aria-hidden="true"
        />
      </button>

      {aberto ? (
        <div className="space-y-4 border-t border-borda px-4 py-4">
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-[15px] text-tinta/80">
            {caso.email ? (
              <span className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-acento" aria-hidden="true" /> {caso.email}
              </span>
            ) : null}
            {caso.telefone ? (
              <span className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-acento" aria-hidden="true" /> {caso.telefone}
              </span>
            ) : null}
          </div>

          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-tinta/60">
              Documentos que a pessoa enviou
            </p>
            {caso.documentos.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {caso.documentos.map((d) => (
                  <Botao
                    key={d.arquivo}
                    tipo="secundario"
                    tamanho="pequeno"
                    disabled={ocupado}
                    onClick={() => onAbrir(d.arquivo)}
                  >
                    <FileText className="mr-2 h-4 w-4" aria-hidden="true" />
                    {d.rotulo}
                  </Botao>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-[15px] text-tinta/70">Nenhum documento enviado ainda.</p>
            )}
            <p className="mt-2 text-sm text-tinta/60">Cada documento aberto fica registrado.</p>
          </div>

          <Historico passos={caso.historico ?? []} />

          {caso.situacao === "PENDENTE" && caso.faltam.length ? (
            <Aviso tom="neutro">
              Você avisou que falta: <strong>{caso.faltam.map(rotulo).join(", ")}</strong>. A
              pessoa vê isso na área dela.
            </Aviso>
          ) : null}

          {escolhendo ? (
            <div className="rounded-lg bg-lilas p-4">
              <p className="text-[15px] font-medium text-tinta">Qual documento falta?</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {possiveis.map((p) => (
                  <label key={p.tipo} className="flex items-center gap-2 text-[15px] text-tinta">
                    <input
                      type="checkbox"
                      className="h-5 w-5"
                      checked={faltam.includes(p.tipo)}
                      onChange={(e) =>
                        setFaltam((antes) =>
                          e.target.checked ? [...antes, p.tipo] : antes.filter((t) => t !== p.tipo),
                        )
                      }
                    />
                    {p.rotulo}
                  </label>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-3">
                <Botao
                  tamanho="pequeno"
                  disabled={ocupado || faltam.length === 0}
                  onClick={() => {
                    onSituar("PENDENTE", faltam);
                    setEscolhendo(false);
                  }}
                >
                  Avisar o filiado
                </Botao>
                <Botao tipo="discreto" tamanho="pequeno" onClick={() => setEscolhendo(false)}>
                  Cancelar
                </Botao>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              {esperando ? (
                <Botao tamanho="pequeno" disabled={ocupado} onClick={() => onSituar("RECEBIDO")}>
                  Confirmar recebimento
                </Botao>
              ) : null}
              {caso.situacao !== "COMPLETO" ? (
                <Botao
                  tipo={esperando ? "secundario" : "principal"}
                  tamanho="pequeno"
                  disabled={ocupado}
                  onClick={() => onSituar("COMPLETO")}
                >
                  Documentação completa
                </Botao>
              ) : null}
              <Botao tipo="secundario" tamanho="pequeno" disabled={ocupado} onClick={() => setEscolhendo(true)}>
                Falta documento
              </Botao>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

/** Quem uma tese alcança num sindicato: os nomes de quem já é caso deste
 *  escritório, e a contagem de quem ainda não lhe foi encaminhado. */
function PessoasDaTese({
  entidade,
  token,
  tese,
}: {
  entidade: string;
  token: string;
  tese: string;
}) {
  const [dados, setDados] = useState<api.PessoasDaTese | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    void api
      .verPessoasDaTese(entidade, token, tese)
      .then(setDados)
      .catch((e) => setErro(e instanceof Error ? e.message : "não foi possível abrir"));
  }, [entidade, token, tese]);
  if (erro) return <p className="mt-2 text-sm text-alerta">{erro}</p>;
  if (!dados) return <p className="mt-2 text-sm text-tinta/60">Carregando…</p>;
  return (
    <div className="mt-3 space-y-2">
      {/* QUEM JÁ PODERIA vem primeiro: é por eles que se começa. */}
      {[...dados.pessoas]
        .sort((a, b) => Number(b.como === "poderiam") - Number(a.como === "poderiam"))
        .map((p) => (
        <div key={p.cpf} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg bg-carta px-3 py-2">
          <span className="min-w-0 basis-full sm:flex-1 sm:basis-0">
            <span className="block text-[15px] font-medium text-tinta sm:truncate">{p.nome}</span>
            <span className="block text-sm text-tinta/60">CPF {formatarCpf(p.cpf)}</span>
          </span>
          <span
            className={
              "rounded-full border px-3 py-0.5 text-[13px] font-semibold " +
              (p.como === "poderiam" ? CORES.bom : CORES.neutro)
            }
          >
            {p.como === "poderiam" ? "Poderia" : "Depende de conferência"}
          </span>
        </div>
      ))}
      {dados.pessoas.length === 0 ? (
        <p className="text-sm text-tinta/70">Nenhum caso seu é alcançado ainda.</p>
      ) : null}
      {dados.nao_encaminhadas > 0 ? (
        <p className="rounded-lg bg-ambar px-3 py-2 text-sm text-tinta">
          <strong>+ {dados.nao_encaminhadas}</strong>{" "}
          {dados.nao_encaminhadas === 1 ? "filiado alcançado" : "filiados alcançados"} ainda não{" "}
          {dados.nao_encaminhadas === 1 ? "foi encaminhado" : "foram encaminhados"} a você. Peça ao
          sindicato.
        </p>
      ) : null}
    </div>
  );
}

/** Uma tese, numa linha: o que é, em que pé está, e o NÚMERO. Aberta, a
 *  divisão por sindicato — e, de cada um, as pessoas. */
function LinhaDaTese({
  tese,
  token,
  aberta,
  onAlternar,
}: {
  tese: TeseJunta;
  token: string;
  aberta: boolean;
  onAlternar: () => void;
}) {
  const [vendo, setVendo] = useState("");
  const quando = haQuanto(tese.data, new Date());
  const pendente = tese.tipo === "tema" && tese.situacao === "afetado";
  return (
    <div className="rounded-xl border border-borda bg-carta">
      <button
        type="button"
        aria-expanded={aberta}
        onClick={onAlternar}
        className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 px-4 py-4 text-left hover:bg-lilas/40"
      >
        <span className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-lilas text-acento sm:flex">
          {tese.tipo === "acao" ? (
            <Scale className="h-5 w-5" aria-hidden="true" />
          ) : (
            <Landmark className="h-5 w-5" aria-hidden="true" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[17px] font-semibold text-tinta">{tese.rotulo}</span>
          <span className="mt-1 flex flex-wrap gap-2">
            {rotuloDaSituacaoDaTese(tese) ? (
              <span className="rounded-full bg-papel px-2.5 py-0.5 text-[13px] font-medium text-tinta/80">
                {rotuloDaSituacaoDaTese(tese)}
                {quando && !pendente ? ` ${quando}` : ""}
              </span>
            ) : null}
            <span
              className={
                "rounded-full border px-2.5 py-0.5 text-[13px] font-medium " +
                (tese.conferida ? CORES.bom : CORES.neutro)
              }
            >
              {tese.conferida ? "Conferida" : "A conferir"}
            </span>
          </span>
        </span>
        <span className="text-right">
          <span className="block text-3xl font-bold leading-none text-tinta">
            {pendente ? tese.dependem : tese.poderiam}
          </span>
          <span className="text-sm text-tinta/65">
            {pendente ? "na carreira" : tese.conferida ? "podem" : "poderiam"}
          </span>
        </span>
        <ChevronDown
          className={"h-5 w-5 shrink-0 text-acento transition-transform " + (aberta ? "rotate-180" : "")}
          aria-hidden="true"
        />
      </button>

      {aberta ? (
        <div className="space-y-3 border-t border-borda px-4 py-4">
          {tese.porSindicato.map((x) => (
            <div key={x.entidade} className="rounded-lg bg-papel p-3">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <span className="flex min-w-0 basis-full items-center gap-2 text-[15px] font-semibold text-tinta sm:flex-1 sm:basis-0">
                  <Building2 className="h-4 w-4 shrink-0 text-acento" aria-hidden="true" />
                  {x.nome}
                </span>
                <span className="flex-1 text-[15px] text-tinta/80 sm:flex-none">
                  {pendente ? (
                    <>
                      <strong className="text-tinta">{x.dependem}</strong> na carreira
                    </>
                  ) : (
                    <>
                      <strong className="text-tinta">{x.poderiam}</strong>{" "}
                      {tese.conferida ? "podem" : "poderiam"} ·{" "}
                      <strong className="text-tinta">{x.dependem}</strong> dependem
                    </>
                  )}
                </span>
                <Botao
                  tipo="secundario"
                  tamanho="pequeno"
                  aria-expanded={vendo === x.entidade}
                  onClick={() => setVendo((v) => (v === x.entidade ? "" : x.entidade))}
                >
                  {vendo === x.entidade ? "Fechar" : "Ver pessoas"}
                </Botao>
              </div>
              {vendo === x.entidade ? (
                <PessoasDaTese entidade={x.entidade} token={token} tese={tese.id} />
              ) : null}
            </div>
          ))}
          <details className="text-[15px] text-tinta/80">
            <summary className="cursor-pointer font-medium text-acento underline">
              A questão, a tese e a fonte
            </summary>
            <div className="mt-2 space-y-2 leading-relaxed">
              {tese.questao ? <p><strong className="text-tinta">Questão:</strong> {tese.questao}</p> : null}
              {tese.tese ? (
                <p><strong className="text-tinta">Tese:</strong> {tese.tese}</p>
              ) : tese.tipo === "tema" ? (
                <p>Ainda não há tese fixada.</p>
              ) : null}
              {tese.fonte ? <p className="text-sm text-tinta/60">Fonte: {tese.fonte}</p> : null}
            </div>
          </details>
          {!tese.conferida && !pendente ? (
            <p className="text-sm text-tinta/60">
              Simulação: vale depois que um advogado conferir a tese.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function Escritorio({
  entidade,
  token,
  secao,
  onIr,
  onToken,
  onSessaoMorta,
}: {
  entidade: string;
  token: string;
  /** Qual das quatro telas do escritório: início, tribunais, casos ou
   *  sindicatos. Moram no menu lateral. */
  secao: api.Tela;
  onIr: (tela: api.Tela) => void;
  onToken: (token: string, cpf: string) => void;
  onSessaoMorta: () => void;
}) {
  const [dados, setDados] = useState<api.VisaoUnicaDoEscritorio | null>(null);
  const [sindicato, setSindicato] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [versao, setVersao] = useState(0);
  const [texto, setTexto] = useState("");
  const [situacao, setSituacao] = useState("");
  const [aberto, setAberto] = useState("");
  const [teseAberta, setTeseAberta] = useState("");
  const [mostrando, setMostrando] = useState(10);

  useEffect(() => {
    if (!token) return;
    void api
      .visaoUnicaDoEscritorio(token)
      .then(setDados)
      .catch((e) => {
        if (e instanceof api.ErroDoServidor && e.status === 401) onSessaoMorta();
        else setErro(e instanceof Error ? e.message : "não foi possível abrir");
      });
  }, [entidade, token, versao]);
  useEffect(() => setMostrando(10), [texto, situacao, sindicato]);

  if (!token) {
    return (
      <Portao
        entidade={entidade}
        titulo="Área do escritório"
        explicacao="Para os escritórios contratados pelo sindicato. O código vai para o e-mail que o sindicato cadastrou — não há senha."
        onToken={onToken}
      />
    );
  }
  if (erro && !dados) {
    return (
      <Cartao titulo="Área do escritório">
        <Aviso tom="alerta">{erro}</Aviso>
      </Cartao>
    );
  }
  if (!dados) {
    return (
      <Cartao titulo="Área do escritório">
        <Aviso tom="neutro">Carregando…</Aviso>
      </Cartao>
    );
  }

  async function fazer(passo: () => Promise<void>) {
    setOcupado(true);
    setErro("");
    try {
      await passo();
    } catch (e) {
      if (e instanceof api.ErroDoServidor && e.status === 401) onSessaoMorta();
      else setErro(e instanceof Error ? e.message : "não foi possível concluir");
    } finally {
      setOcupado(false);
    }
  }

  const varios = dados.sindicatos.length > 1;
  const nome =
    dados.sindicatos.find((x) => x.entidade === entidade)?.escritorio ??
    dados.sindicatos[0]?.escritorio ??
    "Escritório";
  const todos = ordemDeTrabalho(
    sindicato ? dados.casos.filter((c) => c.entidade === sindicato) : dados.casos,
  );
  const quantos = (s: string) => dados.casos.filter((c) => c.situacao === s).length;
  const filtrados = filtrarCasos(todos, { texto, situacao });
  const teses = tesesJuntas(dados.sindicatos);
  // UMA NOVIDADE POR TEMA, e não uma por sindicato: o julgamento é um só.
  const recentes = teses.filter((t) =>
    (dados.novidades ?? []).some((n) => n.id === t.id),
  );
  const parados = dados.casos.filter(
    (c) => c.situacao === "ENCAMINHADO" && (diasNaFila(c.encaminhado_em, new Date()) ?? 0) > 7,
  ).length;

  const verCasos = (s: string, deQual = "") => () => {
    setSituacao(s);
    setSindicato(deQual);
    onIr("casos");
  };
  const verTese = (id: string) => () => {
    setTeseAberta(id);
    onIr("tribunais");
  };

  function baixar() {
    const blob = new Blob([csvDosCasos(filtrados, dados!.documentos_possiveis)], {
      type: "text/csv;charset=utf-8",
    });
    const endereco = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = endereco;
    a.download = `casos-do-escritorio${sindicato ? `-${sindicato}` : ""}.csv`;
    a.click();
    URL.revokeObjectURL(endereco);
  }

  const titulo = (grande: string, pequeno: string) => (
    <div>
      <p className="text-sm font-semibold uppercase tracking-widest text-acento">{nome}</p>
      <h1 className="text-2xl font-bold text-tinta sm:text-3xl">{grande}</h1>
      {pequeno ? <p className="mt-1 text-[16px] text-tinta/65">{pequeno}</p> : null}
    </div>
  );

  // ------------------------------------------------------------ TRIBUNAIS
  if (secao === "tribunais") {
    return (
      <div className="space-y-5">
        {titulo("Tribunais", "O que foi julgado, e quantas pessoas alcança. Toque para ver por sindicato.")}
        {teses.length === 0 ? (
          <Aviso tom="neutro">Nenhuma tese acompanhada para os seus sindicatos ainda.</Aviso>
        ) : (
          <div className="space-y-3">
            {teses.map((t) => (
              <LinhaDaTese
                key={t.id}
                tese={t}
                token={token}
                aberta={teseAberta === t.id}
                onAlternar={() => setTeseAberta((a) => (a === t.id ? "" : t.id))}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  // ----------------------------------------------------------- SINDICATOS
  if (secao === "sindicatos") {
    return (
      <div className="space-y-5">
        {titulo("Meus sindicatos", "Quem contratou este escritório.")}
        <div className="grid gap-4 md:grid-cols-2">
          {dados.sindicatos.map((x) => {
            const dele = dados.casos.filter((c) => c.entidade === x.entidade);
            const paradosDele = dele.filter(
              (c) => c.situacao === "ENCAMINHADO" && (diasNaFila(c.encaminhado_em, new Date()) ?? 0) > 7,
            ).length;
            return (
              <div key={x.entidade} className="rounded-xl bg-carta p-5 shadow-cartao">
                <p className="flex items-center gap-2 text-lg font-semibold text-tinta">
                  <Building2 className="h-5 w-5 shrink-0 text-acento" aria-hidden="true" />
                  {x.nome}
                </p>
                <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                  {[
                    [x.casos, "casos"],
                    [x.aguardando, "aguardando você"],
                    [x.pendentes, "falta documento"],
                  ].map(([n, r]) => (
                    <div key={String(r)} className="rounded-lg bg-papel p-3">
                      <p className="text-2xl font-bold text-tinta">{n}</p>
                      <p className="text-[13px] text-tinta/65">{r}</p>
                    </div>
                  ))}
                </div>
                {paradosDele > 0 ? (
                  <p className="mt-3 text-sm font-semibold text-alerta">
                    {paradosDele} {paradosDele === 1 ? "parado" : "parados"} há mais de 7 dias
                  </p>
                ) : null}
                <div className="mt-4">
                  <Botao tamanho="pequeno" onClick={verCasos("", x.entidade)}>
                    Ver os casos
                  </Botao>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- CASOS
  if (secao === "casos") {
    const filtros: [string, string][] = [
      ["", "Todos"],
      ["ENCAMINHADO", "Aguardando"],
      ["RECEBIDO", "Recebidos"],
      ["PENDENTE", "Falta documento"],
      ["COMPLETO", "Completos"],
    ];
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          {titulo("Casos", "O que ainda não foi aberto vem primeiro.")}
          <Botao tipo="secundario" tamanho="pequeno" disabled={filtrados.length === 0} onClick={baixar}>
            <Download className="mr-2 h-4 w-4" aria-hidden="true" />
            Baixar planilha
          </Botao>
        </div>

        {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}

        <div className="space-y-3 rounded-xl bg-carta p-4 shadow-cartao">
          <Campo
            rotulo="Procurar pelo nome ou pelo CPF"
            valor={texto}
            onChange={setTexto}
            placeholder="Ex.: maria"
            autoComplete="off"
          />
          <div className="flex flex-wrap gap-2" role="group" aria-label="Situação">
            {filtros.map(([valor, rotulo]) => (
              <Botao
                key={valor || "todos"}
                tamanho="pequeno"
                tipo={situacao === valor ? "principal" : "secundario"}
                aria-pressed={situacao === valor}
                onClick={() => setSituacao(valor)}
              >
                {rotulo}
              </Botao>
            ))}
          </div>
          {varios ? (
            <div className="flex flex-wrap gap-2" role="group" aria-label="Sindicato">
              {[{ entidade: "", nome: "Todos os sindicatos" }, ...dados.sindicatos].map((x) => (
                <Botao
                  key={x.entidade || "todos"}
                  tamanho="pequeno"
                  tipo={sindicato === x.entidade ? "principal" : "secundario"}
                  aria-pressed={sindicato === x.entidade}
                  onClick={() => setSindicato(x.entidade)}
                >
                  {x.nome}
                </Botao>
              ))}
            </div>
          ) : null}
        </div>

        {dados.casos.length === 0 ? (
          <Aviso tom="neutro">Nenhum sindicato encaminhou caso a este escritório ainda.</Aviso>
        ) : (
          <>
            <p className="text-sm text-tinta/70">
              {filtrados.length} {filtrados.length === 1 ? "caso" : "casos"}
            </p>
            <div className="space-y-2">
              {filtrados.slice(0, mostrando).map((c) => {
                const chave = `${c.entidade ?? ""}-${c.cpf}-${c.acao}`;
                // O CASO É DO SINDICATO DELE: é ao portal daquele
                // sindicato que se pede o documento e se marca a situação.
                const dono = c.entidade ?? entidade;
                return (
                  <Linha
                    key={chave}
                    caso={c}
                    comSindicato={varios}
                    possiveis={dados.documentos_possiveis}
                    aberto={aberto === chave}
                    ocupado={ocupado}
                    onAlternar={() => setAberto((a) => (a === chave ? "" : chave))}
                    onAbrir={(arquivo) =>
                      void fazer(async () => {
                        // A ABA É ABERTA ANTES DO PEDIDO: aberta depois, o
                        // navegador a trata como janela não pedida e bloqueia.
                        const aba = window.open("", "_blank");
                        try {
                          const endereco = await api.abrirDocumentoDoCaso(dono, token, c.cpf, arquivo);
                          if (aba) aba.location.href = endereco;
                          else window.location.assign(endereco);
                        } catch (e) {
                          aba?.close();
                          throw e;
                        }
                      })
                    }
                    onSituar={(nova, faltam) =>
                      void fazer(async () => {
                        await api.situarCaso(dono, token, c.cpf, c.acao, nova, faltam ?? []);
                        setVersao((v) => v + 1);
                      })
                    }
                  />
                );
              })}
            </div>
            {filtrados.length > mostrando ? (
              <Botao tipo="secundario" onClick={() => setMostrando((m) => m + 10)}>
                Mostrar mais {Math.min(10, filtrados.length - mostrando)}
              </Botao>
            ) : null}
          </>
        )}
      </div>
    );
  }

  // --------------------------------------------------------------- INÍCIO
  return (
    <div className="space-y-6">
      {titulo(`${saudacao(new Date())}.`, "")}

      {/* A NOTÍCIA DO DIA, para bater o olho: o tema, quando, e o NÚMERO.
          O resto está a um toque, em Tribunais. */}
      {recentes.length ? (
        <section aria-label="Novidades nos tribunais">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-tinta">
            <Megaphone className="h-5 w-5 text-bom" aria-hidden="true" />
            {recentes.length === 1 ? "1 novidade" : `${recentes.length} novidades`} nos tribunais
          </h2>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {recentes.map((t) => {
              const pendente = t.situacao === "afetado";
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={verTese(t.id)}
                  className="flex items-center gap-4 rounded-xl border-2 border-bom/30 bg-bom/10 p-4 text-left transition hover:bg-bom/15"
                >
                  <span className="text-center">
                    <span className="block text-4xl font-bold leading-none text-tinta">
                      {pendente ? t.dependem : t.poderiam}
                    </span>
                    <span className="text-[13px] text-tinta/70">{pendente ? "na carreira" : "poderiam"}</span>
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[16px] font-semibold text-tinta">{t.rotulo}</span>
                    <span className="block text-sm text-tinta/75">
                      {rotuloDaSituacaoDaTese(t)} {pendente ? "" : haQuanto(t.data, new Date())} ·{" "}
                      {t.porSindicato.length} {t.porSindicato.length === 1 ? "sindicato" : "sindicatos"}
                    </span>
                  </span>
                  <ChevronDown className="h-5 w-5 -rotate-90 text-acento" aria-hidden="true" />
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* OS CASOS, em quatro números — cada um abre a lista do que conta. */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4">
        <Destaque
          cor="roxo"
          icone={<Inbox className="h-5 w-5" aria-hidden="true" />}
          valor={quantos("ENCAMINHADO")}
          rotulo="aguardando você confirmar"
          onClick={verCasos("ENCAMINHADO")}
        />
        <Destaque
          cor="azul"
          icone={<FileQuestion className="h-5 w-5" aria-hidden="true" />}
          valor={quantos("PENDENTE")}
          rotulo="com documento faltando"
          onClick={verCasos("PENDENTE")}
        />
        <div className="col-span-2 grid grid-cols-2 gap-3 md:col-span-1 md:grid-cols-1 md:gap-4">
          <Mini
            cor="azul"
            icone={<FileText className="h-5 w-5" aria-hidden="true" />}
            valor={quantos("RECEBIDO")}
            rotulo="em conferência"
            onClick={verCasos("RECEBIDO")}
          />
          <Mini
            cor="claro"
            icone={<CheckCheck className="h-5 w-5" aria-hidden="true" />}
            valor={quantos("COMPLETO")}
            rotulo="documentação completa"
            onClick={verCasos("COMPLETO")}
          />
        </div>
      </div>

      {parados > 0 ? (
        <button
          type="button"
          onClick={verCasos("ENCAMINHADO")}
          className="flex w-full items-center gap-3 rounded-xl border border-alerta/30 bg-alerta/10 px-4 py-3 text-left text-[16px] text-tinta hover:bg-alerta/15"
        >
          <Clock className="h-5 w-5 shrink-0 text-alerta" aria-hidden="true" />
          <span className="flex-1">
            <strong>{parados}</strong> {parados === 1 ? "caso parado" : "casos parados"} há mais de 7 dias
          </span>
          <span className="text-sm font-semibold text-acento underline">Ver</span>
        </button>
      ) : null}

      <ProtoNoTopo
        para="Pergunte sobre os tribunais, a sua fila ou o caso de uma pessoa."
        abertura={ABERTURA}
        sugestoes={PERGUNTAS}
        perguntar={(p) => api.perguntarComoEscritorioEmTodos(token, p)}
        consultando="Olhando a sua fila…"
        onSessaoMorta={onSessaoMorta}
      />
    </div>
  );
}
