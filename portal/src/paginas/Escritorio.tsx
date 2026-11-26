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
  CheckCheck,
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

import { ProtoNoTopo } from "../componentes/ProtoNoTopo";
import { Aviso, Botao, Campo, Cartao, Destaque, Mini } from "../componentes/ui";
import * as api from "../lib/envio";
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
  possiveis,
  aberto,
  ocupado,
  onAlternar,
  onAbrir,
  onSituar,
}: {
  caso: api.CasoDoEscritorio;
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
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[16px] font-semibold text-tinta">{caso.nome}</span>
          <span className="block text-sm text-tinta/65">
            CPF {formatarCpf(caso.cpf)} · {caso.rotulo}
          </span>
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
          className={"h-5 w-5 shrink-0 text-acento transition-transform " + (aberto ? "rotate-180" : "")}
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

export function Escritorio({
  entidade,
  token,
  onToken,
  onSessaoMorta,
}: {
  entidade: string;
  token: string;
  onToken: (token: string, cpf: string) => void;
  onSessaoMorta: () => void;
}) {
  const [dados, setDados] = useState<api.CasosDoEscritorio | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [versao, setVersao] = useState(0);
  const [texto, setTexto] = useState("");
  const [situacao, setSituacao] = useState("");
  const [aberto, setAberto] = useState("");
  const [mostrando, setMostrando] = useState(10);

  useEffect(() => {
    if (!token) return;
    void api
      .casosDoEscritorio(entidade, token)
      .then(setDados)
      .catch((e) => {
        if (e instanceof api.ErroDoServidor && e.status === 401) onSessaoMorta();
        else setErro(e instanceof Error ? e.message : "não foi possível abrir");
      });
  }, [entidade, token, versao]);
  useEffect(() => setMostrando(10), [texto, situacao]);

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

  const todos = ordemDeTrabalho(dados.casos);
  const quantos = (s: string) => todos.filter((c) => c.situacao === s).length;
  const filtrados = filtrarCasos(todos, { texto, situacao });
  const filtrar = (s: string) => () => {
    setSituacao(s);
    document.getElementById("fila-do-escritorio")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  function baixar() {
    const blob = new Blob([csvDosCasos(filtrados, dados!.documentos_possiveis)], {
      type: "text/csv;charset=utf-8",
    });
    const endereco = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = endereco;
    a.download = `casos-${dados!.escritorio.id}.csv`;
    a.click();
    URL.revokeObjectURL(endereco);
  }

  const filtros: [string, string][] = [
    ["", "Todos"],
    ["ENCAMINHADO", rotuloDaSituacao("ENCAMINHADO")],
    ["RECEBIDO", rotuloDaSituacao("RECEBIDO")],
    ["PENDENTE", rotuloDaSituacao("PENDENTE")],
    ["COMPLETO", rotuloDaSituacao("COMPLETO")],
  ];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold uppercase tracking-widest text-acento">
          Painel do escritório
        </p>
        <h1 className="text-2xl font-bold text-tinta sm:text-3xl">{dados.escritorio.nome}</h1>
        <p className="mt-1 text-[17px] text-tinta/70">
          Os filiados que o sindicato encaminhou a este escritório, e os documentos de cada um.
        </p>
      </div>

      <ProtoNoTopo
        para="Estou aqui para ajudar o escritório: digo quantos casos chegaram, por onde começar e de quem falta documento. Respondo na hora."
        abertura={ABERTURA}
        sugestoes={PERGUNTAS}
        perguntar={(p) => api.perguntarComoEscritorio(entidade, token, p)}
        consultando="Olhando a sua fila…"
        onSessaoMorta={onSessaoMorta}
      />

      {/* OS NÚMEROS, e cada um ABRE a lista do que conta — como no painel
          do sindicato. */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 md:gap-4">
        <Destaque
          cor="roxo"
          icone={<Inbox className="h-5 w-5" aria-hidden="true" />}
          valor={quantos("ENCAMINHADO")}
          rotulo="aguardando você confirmar"
          onClick={filtrar("ENCAMINHADO")}
        />
        <Destaque
          cor="azul"
          icone={<FileQuestion className="h-5 w-5" aria-hidden="true" />}
          valor={quantos("PENDENTE")}
          rotulo="com documento faltando"
          onClick={filtrar("PENDENTE")}
        />
        <div className="col-span-2 grid grid-cols-2 gap-3 md:col-span-1 md:grid-cols-1 md:gap-4">
          <Mini
            cor="azul"
            icone={<FileText className="h-5 w-5" aria-hidden="true" />}
            valor={quantos("RECEBIDO")}
            rotulo="em conferência"
            onClick={filtrar("RECEBIDO")}
          />
          <Mini
            cor="claro"
            icone={<CheckCheck className="h-5 w-5" aria-hidden="true" />}
            valor={quantos("COMPLETO")}
            rotulo="documentação completa"
            onClick={filtrar("COMPLETO")}
          />
        </div>
      </div>

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}

      <div id="fila-do-escritorio" className="scroll-mt-4">
        <Cartao
          titulo="Casos encaminhados"
          explicacao="O que ainda não foi aberto vem primeiro, do mais antigo para o mais novo. Toque num caso para ver os documentos. O que você marcar aparece para o filiado e para o sindicato."
        >
          <div className="rounded-lg bg-lilas p-4">
            <Botao tipo="secundario" disabled={filtrados.length === 0} onClick={baixar}>
              <Download className="mr-2 h-4 w-4" aria-hidden="true" />
              Baixar a planilha destes casos
            </Botao>
            <p className="mt-2 text-sm text-tinta/75">
              Abre no Excel: nome, CPF, contato, ação, situação e o que falta de cada pessoa.
            </p>
          </div>

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

          {todos.length === 0 ? (
            <Aviso tom="neutro">O sindicato ainda não encaminhou nenhum caso a este escritório.</Aviso>
          ) : (
            <>
              <p className="text-sm text-tinta/70">
                {filtrados.length === todos.length
                  ? `${todos.length} ${todos.length === 1 ? "caso" : "casos"}.`
                  : `${filtrados.length} de ${todos.length} casos.`}
              </p>
              <div className="space-y-2">
                {filtrados.slice(0, mostrando).map((c) => {
                  const chave = `${c.cpf}-${c.acao}`;
                  return (
                    <Linha
                      key={chave}
                      caso={c}
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
                            const endereco = await api.abrirDocumentoDoCaso(entidade, token, c.cpf, arquivo);
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
                          await api.situarCaso(entidade, token, c.cpf, c.acao, nova, faltam ?? []);
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
        </Cartao>
      </div>
    </div>
  );
}
