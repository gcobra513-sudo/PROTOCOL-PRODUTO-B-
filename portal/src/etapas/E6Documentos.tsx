/**
 * Etapa 6 — documentos, com recusa na hora.
 *
 * Três cuidados que a especificação exige:
 *
 * 1. **o arquivo precisa ser legível por computador.** Foto de procuração é
 *    só uma imagem, e o sistema precisa LER o nome do advogado nela. Se não
 *    conseguir, recusa e explica. Recusar na hora incomoda; descobrir no fim
 *    é pior, porque não há mais tempo de pedir de novo;
 * 2. **o documento é da pessoa certa?** Procura o CPF dentro do texto. Pega
 *    quem sobe sem perceber o documento do cônjuge;
 * 3. **cada arquivo é renomeado** pelo tipo. Com 15 mil pastas,
 *    "Documento (1).pdf" é inútil.
 *
 * E uma coisa boa de privacidade: a conferência é feita AQUI, no navegador.
 * O documento não sai do dispositivo da pessoa para ser verificado.
 */
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  FileDown,
  Loader2,
  Upload,
} from "lucide-react";
import { useState } from "react";

import { Aviso, Botao, Cartao, cn } from "../componentes/ui";
import * as arquivosEmMemoria from "../lib/arquivos";
import { ler } from "../lib/leitura";
import { abrirParaImprimir } from "../lib/procuracao";
import {
  DOCUMENTOS,
  NOME_DE_ARQUIVO,
  type DocumentoEnviado,
  type Rascunho,
  type TipoDocumento,
} from "../lib/tipos";

export function E6Documentos({
  rascunho,
  enviados,
  onEnviado,
  onRemover,
}: {
  rascunho: Rascunho;
  enviados: DocumentoEnviado[];
  onEnviado: (d: DocumentoEnviado) => void;
  onRemover: (tipo: TipoDocumento) => void;
}) {
  const cpf = rascunho.pessoais.cpf;
  const [lendo, setLendo] = useState<TipoDocumento | null>(null);
  const [recusado, setRecusado] = useState<Record<string, string>>({});

  async function receber(tipo: TipoDocumento, arquivo: File) {
    setLendo(tipo);
    setRecusado((r) => ({ ...r, [tipo]: "" }));
    try {
      const resultado = await ler(arquivo, cpf);
      if (!resultado.legivel) {
        setRecusado((r) => ({ ...r, [tipo]: resultado.motivoRecusa }));
        return;     // NÃO registra: documento ilegível não entra
      }
      // Os bytes ficam na memória da aba, nunca no rascunho salvo. Ver
      // `lib/arquivos.ts` para o motivo.
      arquivosEmMemoria.guardar(tipo, arquivo);
      onEnviado({
        tipo,
        nomeOriginal: arquivo.name,
        // Do contrato compartilhado, não inventado aqui.
        nomeFinal: NOME_DE_ARQUIVO[tipo],
        tamanho: arquivo.size,
        sha256: resultado.sha256,
        legivel: true,
        cpfEncontrado: resultado.cpfEncontrado,
        motivoRecusa: "",
      });
    } finally {
      setLendo(null);
    }
  }

  return (
    <Cartao
      titulo="Seus documentos"
      explicacao={
        <>
          Prefira <strong>PDF</strong>. Conferimos cada arquivo na hora, aqui
          no seu aparelho — nada é enviado nesta etapa.
        </>
      }
    >
      {DOCUMENTOS.map((spec) => {
        // O asterisco tem de dizer a verdade. Sentença e certidão de trânsito
        // só são exigidas de quem declarou ter processo ("sim") — está no
        // contrato compartilhado. Mostramos o campo de qualquer forma, porque
        // quem não sabe o NÚMERO pode ter o documento em mãos; o que não se
        // pode é marcar como obrigatório algo que a pessoa não tem como
        // apresentar. Asterisco mentindo trava o cadastro sem explicar.
        const exigidoAgora =
          spec.obrigatorio &&
          !(spec.soComProcesso && rascunho.processo.temProcesso !== "sim");
        const enviado = enviados.find((e) => e.tipo === spec.tipo);
        const erro = recusado[spec.tipo];
        const estaLendo = lendo === spec.tipo;
        return (
          <div
            key={spec.tipo}
            className={cn(
              "rounded-md border p-4",
              enviado ? "border-bom/40 bg-bom/5" : "border-borda bg-carta",
            )}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[15px] font-medium text-tinta">
                  {spec.rotulo}
                  {exigidoAgora ? (
                    <>
                      <span className="ml-1 text-alerta" aria-hidden="true">
                        *
                      </span>
                      <span className="sr-only"> (obrigatório)</span>
                    </>
                  ) : (
                    <span className="ml-2 text-sm font-normal text-tinta/60">
                      (se tiver)
                    </span>
                  )}
                </p>
                <p className="text-sm text-tinta/60">{spec.porque}</p>
                {spec.tipo === "procuracao" ? (
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    <Botao
                      tipo="secundario"
                      tamanho="pequeno"
                      onClick={() =>
                        abrirParaImprimir(rascunho, "direto_ao_advogado")
                      }
                    >
                      <FileDown className="h-4 w-4" aria-hidden="true" />
                      Baixar modelo de procuração
                    </Botao>
                  </div>
                ) : null}
              </div>

              {enviado ? (
                <Botao
                  tipo="discreto"
                  tamanho="pequeno"
                  onClick={() => {
                    arquivosEmMemoria.esquecer(spec.tipo);
                    onRemover(spec.tipo);
                  }}
                >
                  Trocar arquivo
                </Botao>
              ) : (
                <label
                  className={cn(
                    "inline-flex h-9 cursor-pointer items-center gap-2 rounded-md",
                    "border border-borda bg-carta px-3 text-sm text-tinta",
                    "hover:bg-papel",
                    estaLendo && "cursor-wait opacity-60",
                  )}
                >
                  {estaLendo ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Upload className="h-4 w-4" aria-hidden="true" />
                  )}
                  {estaLendo ? "Conferindo…" : "Escolher arquivo"}
                  <input
                    type="file"
                    accept="application/pdf,.pdf,image/*"
                    className="sr-only"
                    // Identifica o campo pelo TIPO do contrato, não pela
                    // posição. O ensaio geral escolhia por índice e quebrou
                    // quando o campo de um documento já anexado sai do DOM:
                    // os índices andam, e o ensaio anexa no campo errado ou
                    // não acha nenhum.
                    data-tipo={spec.tipo}
                    disabled={estaLendo}
                    onChange={(e) => {
                      const a = e.target.files?.[0];
                      if (a) void receber(spec.tipo, a);
                      e.target.value = "";
                    }}
                  />
                </label>
              )}
            </div>

            <AnimatePresence initial={false}>
              {erro ? (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="pt-3">
                    <Aviso tom="alerta">
                      <span className="flex items-start gap-2">
                        <AlertTriangle
                          className="mt-0.5 h-4 w-4 shrink-0"
                          aria-hidden="true"
                        />
                        <span>{erro}</span>
                      </span>
                    </Aviso>
                  </div>
                </motion.div>
              ) : null}

              {enviado ? (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="space-y-2 pt-3 text-sm">
                    <p className="flex items-start gap-2 text-bom">
                      <CheckCircle2
                        className="mt-0.5 h-4 w-4 shrink-0"
                        aria-hidden="true"
                      />
                      <span>
                        Lido com sucesso. Será guardado como{" "}
                        <code className="rounded bg-carta px-1">
                          {enviado.nomeFinal}
                        </code>
                        .
                      </span>
                    </p>
                    {enviado.cpfEncontrado ? (
                      <p className="pl-6 text-tinta/60">
                        Encontramos o seu CPF dentro do documento.
                      </p>
                    ) : (
                      <p className="pl-6 text-alerta">
                        Não encontramos o seu CPF dentro deste documento.
                        Confira se é o documento certo — pode ser de outra
                        pessoa. Se você tem certeza de que está correto, siga
                        em frente: o escritório confere.
                      </p>
                    )}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        );
      })}

      <Aviso tom="neutro">
        <strong>Sobre a procuração:</strong> use o modelo acima se puder. Ele
        já traz duas cláusulas que costumam faltar e que travam o processo
        depois — os poderes para <em>executar</em> (receber, dar quitação,
        levantar valores) e para <em>substabelecer</em>. Procuração só para
        “defesa de direitos” pode não bastar numa execução, e a falha aparece
        quando o juiz manda regularizar, com o prazo já correndo.
      </Aviso>

      <Aviso tom="neutro">
        <strong>Por que recusamos foto:</strong> a petição precisa citar o que
        está escrito no documento, e numa foto o texto não existe para o
        computador — é só um desenho. Se você só tem papel, escaneie em PDF
        com a opção de reconhecer texto ativada.
      </Aviso>
    </Cartao>
  );
}
