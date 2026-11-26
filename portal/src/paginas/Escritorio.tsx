/**
 * A ÁREA DO ESCRITÓRIO que o sindicato contratou.
 *
 * O escritório recebia o filiado por e-mail e WhatsApp: documento solto,
 * sem saber quem o sindicato tinha encaminhado nem por qual ação. Aqui ele
 * vê a fila — SÓ quem lhe foi encaminhado —, abre os documentos de cada
 * pessoa e diz em que pé está. O que ele marca aparece para o filiado e
 * para o sindicato, e é isso que tira o telefone do meio.
 *
 * O que esta tela NÃO faz: o trabalho de dentro do escritório. Ela termina
 * em "documentação completa".
 */
import { useEffect, useState } from "react";

import { Aviso, Botao, Cartao } from "../componentes/ui";
import * as api from "../lib/envio";
import { ordemDeTrabalho, rotuloDaSituacao, tomDaSituacao } from "../lib/escritorio";
import { formatarCpf } from "../lib/validacao";
import { Portao } from "./Portao";

const CORES = {
  bom: "border-bom/40 bg-bom/10 text-bom",
  neutro: "border-borda bg-papel text-tinta/80",
  alerta: "border-alerta/40 bg-alerta/10 text-alerta",
} as const;

function dia(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

function Caso({
  caso,
  possiveis,
  ocupado,
  onAbrir,
  onSituar,
}: {
  caso: api.CasoDoEscritorio;
  possiveis: { tipo: string; rotulo: string }[];
  ocupado: boolean;
  onAbrir: (arquivo: string) => void;
  onSituar: (situacao: string, faltam?: string[]) => void;
}) {
  const [escolhendo, setEscolhendo] = useState(false);
  const [faltam, setFaltam] = useState<string[]>(caso.faltam);
  const rotulo = (tipo: string) => possiveis.find((p) => p.tipo === tipo)?.rotulo ?? tipo;

  return (
    <div className="rounded-lg border border-borda bg-carta p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[17px] font-semibold text-tinta">{caso.nome}</p>
          <p className="text-[15px] text-tinta/70">
            CPF {formatarCpf(caso.cpf)}
            {caso.email ? ` · ${caso.email}` : ""}
            {caso.telefone ? ` · ${caso.telefone}` : ""}
          </p>
          <p className="mt-1 text-[15px] text-tinta/70">
            {caso.rotulo} · encaminhado pelo sindicato em {dia(caso.encaminhado_em)}
          </p>
        </div>
        <span
          className={`inline-block shrink-0 rounded-full border px-3 py-1 text-[13px] font-semibold ${CORES[tomDaSituacao(caso.situacao)]}`}
        >
          {rotuloDaSituacao(caso.situacao)}
        </span>
      </div>

      <div className="mt-4">
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
                Abrir {d.rotulo}
              </Botao>
            ))}
          </div>
        ) : (
          <p className="mt-1 text-[15px] text-tinta/70">Nenhum documento enviado ainda.</p>
        )}
      </div>

      {caso.situacao === "PENDENTE" && caso.faltam.length ? (
        <p className="mt-3 text-[15px] text-tinta">
          Você marcou que falta: <strong>{caso.faltam.map(rotulo).join(", ")}</strong>. A pessoa
          vê isso na área dela.
        </p>
      ) : null}

      {escolhendo ? (
        <div className="mt-4 rounded-lg bg-lilas p-4">
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
        <div className="mt-4 flex flex-wrap gap-3">
          {caso.situacao === "ENCAMINHADO" ? (
            <Botao tamanho="pequeno" disabled={ocupado} onClick={() => onSituar("RECEBIDO")}>
              Confirmar recebimento
            </Botao>
          ) : null}
          {caso.situacao !== "COMPLETO" ? (
            <Botao
              tipo={caso.situacao === "ENCAMINHADO" ? "secundario" : "principal"}
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

  const casos = ordemDeTrabalho(dados.casos);
  const quantos = (s: string) => casos.filter((c) => c.situacao === s).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-tinta sm:text-3xl">{dados.escritorio.nome}</h1>
        <p className="mt-1 text-[17px] text-tinta/70">
          Os filiados que o sindicato encaminhou a este escritório. Só eles.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {(["ENCAMINHADO", "RECEBIDO", "PENDENTE", "COMPLETO"] as const).map((s) => (
          <div key={s} className="rounded-xl bg-carta p-4 shadow-cartao">
            <p className="text-3xl font-bold text-tinta">{quantos(s)}</p>
            <p className="text-[15px] text-tinta/70">{rotuloDaSituacao(s)}</p>
          </div>
        ))}
      </div>

      {erro ? <Aviso tom="alerta">{erro}</Aviso> : null}

      <Cartao
        titulo="Casos encaminhados"
        explicacao="O que ainda não foi aberto vem primeiro. O que você marcar aqui aparece para o filiado e para o sindicato."
      >
        {casos.length === 0 ? (
          <Aviso tom="neutro">O sindicato ainda não encaminhou nenhum caso a este escritório.</Aviso>
        ) : (
          casos.map((c) => (
            <Caso
              key={`${c.cpf}-${c.acao}`}
              caso={c}
              possiveis={dados.documentos_possiveis}
              ocupado={ocupado}
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
              onSituar={(situacao, faltam) =>
                void fazer(async () => {
                  await api.situarCaso(entidade, token, c.cpf, c.acao, situacao, faltam ?? []);
                  setVersao((v) => v + 1);
                })
              }
            />
          ))
        )}
      </Cartao>
    </div>
  );
}
