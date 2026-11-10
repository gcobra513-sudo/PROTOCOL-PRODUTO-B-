/**
 * Os documentos. Um obrigatório, dois opcionais, e a diferença importa.
 *
 *   contribuição   OBRIGATÓRIA, e aceita VÁRIOS. É o que prova desde quando
 *                  você é filiado, e portanto de quais ações você faz parte.
 *                  Um comprovante por ano é o caso normal
 *   sentença       só se você tiver. Decide se o caminho é EXECUTAR
 *   certidão       só se você tiver. Confirma que a sentença é definitiva
 *
 * NÃO SE PEDE PROCURAÇÃO, IDENTIDADE NEM COMPROVANTE DE RESIDÊNCIA. São
 * documentos para litigar, e exigi-los de quem só quer saber se tem direito
 * derruba a conclusão do cadastro sem melhorar resposta nenhuma.
 *
 * O ARQUIVO É OLHADO AQUI, NO APARELHO DA PESSOA, antes de sair.
 *
 * SCANNER E FOTO ENTRAM. Esta tela recusava os dois — "sem texto não há o
 * que ler" —, e a base deste produto é de aposentados com papel físico. A
 * regra mudou em 10/11/2026: o que a máquina não lê é aceito, e a pessoa é
 * AVISADA de que aquele documento vai ser lido por gente e por isso a
 * resposta demora mais. Avisar na hora continua sendo o ponto; o que deixou
 * de existir é a recusa.
 *
 * A foto (JPG, PNG) vira PDF aqui mesmo, com `lib/foto.ts`, sem sair do
 * aparelho: o servidor continua recebendo só PDF.
 */
import { useState } from "react";

import { Aviso, Cartao } from "../componentes/ui";
import * as arquivos from "../lib/arquivos";
import { ehImagemAceita, fotoParaPdf } from "../lib/foto";
import { ler } from "../lib/leitura";
import {
  DOCUMENTOS,
  type DocumentoEnviado,
  type EspecDocumento,
  type TipoDocumento,
} from "../lib/tipos";

function Anexo({
  doc,
  onRemover,
}: {
  doc: DocumentoEnviado;
  onRemover: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-borda bg-papel px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm text-tinta">{doc.nomeOriginal}</p>
        <p className="mt-0.5 text-xs text-tinta/60">
          {(doc.tamanho / 1024).toFixed(0)} kB
          {doc.cpfEncontrado ? " · seu CPF aparece no documento" : ""}
        </p>
        {!doc.temTexto ? (
          // DITO NA HORA, e sem tom de erro: o documento ENTROU. O que muda
          // para a pessoa é o tempo — e quem espera sem saber por quê liga.
          <p className="mt-1 text-xs text-tinta/75">
            Recebemos como imagem. Uma pessoa vai ler este documento, então a
            resposta sobre ele demora mais.
          </p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onRemover}
        className="shrink-0 text-sm text-tinta/70 underline hover:text-tinta"
      >
        remover
      </button>
    </div>
  );
}

function Pedido({
  espec,
  enviados,
  cpf,
  onEnviado,
  onRemover,
}: {
  espec: EspecDocumento;
  enviados: DocumentoEnviado[];
  cpf: string;
  onEnviado: (d: DocumentoEnviado) => void;
  onRemover: (chave: number) => void;
}) {
  const [lendo, setLendo] = useState(false);
  const [recusa, setRecusa] = useState("");
  const meus = enviados.filter((d) => d.tipo === espec.tipo);
  const podeMais = espec.multiplos || meus.length === 0;

  async function receber(lista: FileList | null) {
    if (!lista?.length) return;
    setLendo(true);
    setRecusa("");
    try {
      for (const original of Array.from(lista)) {
        // A FOTO VIRA PDF ANTES DE QUALQUER OUTRA COISA, e o que segue
        // adiante — conferência, guarda, envio — é o PDF. O nome que a
        // pessoa vê continua sendo o do arquivo que ela escolheu.
        let arquivo = original;
        if (ehImagemAceita(original)) {
          try {
            arquivo = await fotoParaPdf(original);
          } catch {
            setRecusa(
              "não conseguimos abrir esta imagem. Tente tirar a foto de " +
                "novo, ou envie o documento em PDF.",
            );
            continue;
          }
        }
        const r = await ler(arquivo, cpf);
        if (!r.legivel) {
          // SÓ O QUE NINGUÉM LÊ fica de fora: arquivo que não abre. Scanner
          // e foto entram, marcados, e uma pessoa lê.
          setRecusa(r.motivoRecusa);
          continue;
        }
        onEnviado({
          chave: arquivos.guardar(arquivo),
          tipo: espec.tipo,
          nomeOriginal: original.name,
          nomeFinal: "",
          tamanho: arquivo.size,
          sha256: r.sha256,
          temTexto: r.temTexto,
          cpfEncontrado: r.cpfEncontrado,
        });
        if (!espec.multiplos) break;
      }
    } finally {
      setLendo(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-borda bg-carta p-4">
      <div>
        <p className="text-[15px] font-medium text-tinta">
          {espec.rotulo}
          {espec.obrigatorio ? (
            <span className="ml-2 text-xs font-normal text-alerta">
              obrigatório
            </span>
          ) : null}
        </p>
        <p className="mt-1 text-sm text-tinta/70">{espec.ajuda}</p>
      </div>

      {meus.map((d) => (
        <Anexo key={d.chave} doc={d} onRemover={() => onRemover(d.chave)} />
      ))}

      {podeMais ? (
        <label className="inline-block cursor-pointer">
          <input
            type="file"
            accept="application/pdf,image/jpeg,image/png"
            multiple={espec.multiplos}
            className="hidden"
            onChange={(e) => void receber(e.target.files)}
          />
          <span className="inline-flex h-10 items-center rounded-md border border-borda bg-carta px-4 text-[15px] text-tinta hover:bg-papel">
            {lendo
              ? "Conferindo…"
              : meus.length
                ? "Anexar mais um"
                : "Escolher arquivo"}
          </span>
        </label>
      ) : null}

      {recusa ? <Aviso tom="alerta">{recusa}</Aviso> : null}
    </div>
  );
}

export function Documentos({
  cpf,
  enviados,
  onEnviado,
  onRemover,
}: {
  cpf: string;
  enviados: DocumentoEnviado[];
  onEnviado: (d: DocumentoEnviado) => void;
  onRemover: (chave: number) => void;
}) {
  const obrigatorios = DOCUMENTOS.filter((d) => d.obrigatorio);
  const opcionais = DOCUMENTOS.filter((d) => !d.obrigatorio);

  return (
    <Cartao
      titulo="Seus documentos"
      explicacao={
        <>
          Pode ser <strong>PDF ou foto</strong> — inclusive foto tirada
          agora, com o celular. Cada arquivo é olhado{" "}
          <strong>aqui, no seu aparelho</strong>, antes de sair. Documento
          escaneado ou fotografado é lido por uma pessoa, e por isso a
          resposta sobre ele demora mais.
        </>
      }
    >
      {obrigatorios.map((espec) => (
        <Pedido
          key={espec.tipo}
          espec={espec}
          enviados={enviados}
          cpf={cpf}
          onEnviado={onEnviado}
          onRemover={onRemover}
        />
      ))}

      <div className="space-y-3 border-t border-borda pt-6">
        <div>
          <p className="text-[15px] font-medium text-tinta">
            Se você tiver, anexe também
          </p>
          <p className="mt-1 text-sm text-tinta/70">
            Não tem? Siga assim mesmo. Quem não tem sentença ainda recebe
            resposta — a dela é sobre entrar com ação, não sobre executar.
          </p>
        </div>
        {opcionais.map((espec) => (
          <Pedido
            key={espec.tipo}
            espec={espec}
            enviados={enviados}
            cpf={cpf}
            onEnviado={onEnviado}
            onRemover={onRemover}
          />
        ))}
      </div>

      <Aviso tom="neutro">
        Os arquivos ficam só na memória desta aba até você confirmar.{" "}
        <strong>Se recarregar a página, precisa anexar de novo</strong> — o
        que você digitou continua salvo. É assim de propósito: guardar
        documento no navegador é guardar num lugar que ninguém controla.
      </Aviso>
    </Cartao>
  );
}

/** O que ainda falta anexar.
 *
 *  `jaTemos` são os tipos que o SINDICATO já mandou. Sem contá-los, a pessoa
 *  ficava travada nesta etapa pedindo um comprovante que o sindicato já tinha
 *  entregado — e pedir de novo o que já foi dado é o que faz alguém concluir
 *  que o sistema não funciona. */
export function tiposFaltando(
  enviados: DocumentoEnviado[],
  jaTemos: string[] = [],
): TipoDocumento[] {
  const tem = new Set<string>([
    ...enviados.map((d) => d.tipo),
    ...jaTemos,
  ]);
  return DOCUMENTOS.filter((d) => d.obrigatorio && !tem.has(d.tipo)).map(
    (d) => d.tipo,
  );
}
