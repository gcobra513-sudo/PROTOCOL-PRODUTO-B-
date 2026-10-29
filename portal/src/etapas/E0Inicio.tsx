/**
 * A página inicial. O que a pessoa vê antes de começar.
 *
 * O QUE ESTA PÁGINA NÃO DIZ, E POR QUÊ
 *
 * Não diz "descubra se você tem direito" nem "veja quanto você vai receber".
 * As duas frases parecem boas e são as mais perigosas que existem aqui:
 *
 * 1. **"se você tem direito"** é parecer jurídico. Em outubro de 2026 a OAB-SP
 *    ajuizou ação civil pública contra uma legaltech alegando exercício
 *    ilegal da advocacia justamente por analisar casos concretos, recomendar
 *    estratégia e produzir peças em escala. Uma página que oferece análise a
 *    pessoa física é a versão mais exposta dessa conduta.
 * 2. **"quanto você vai receber"** é liquidação, depende dos termos do
 *    título, de índices e do marco prescricional. Não calculamos isso, e
 *    prometer número cria expectativa que ninguém vai honrar.
 *
 * O que ela diz é o que é verdade: o sindicato contratou um escritório, o
 * escritório precisa de documentos, e este é o caminho organizado para
 * entregá-los. A decisão sobre o caso é do advogado, e a página fala isso.
 *
 * E o nome do sindicato vem de fora (`entidade`), não embutido: a pessoa
 * chega por um link do próprio sindicato. Página que se apresenta como sendo
 * de uma entidade sem autorização dela é outro problema.
 */
import { motion } from "framer-motion";
import { ArrowRight, Clock, FileCheck2, Lock, ShieldCheck } from "lucide-react";

import { Botao } from "../componentes/ui";

const PASSOS = [
  {
    titulo: "Você conta a sua situação",
    texto:
      "Cargo, se está na ativa ou aposentado, e o número do processo da sua " +
      "sentença. Se não souber o número, pode dizer que não sabe.",
  },
  {
    titulo: "Você envia os documentos",
    texto:
      "Procuração, identidade, comprovante de residência e a sentença. " +
      "Conferimos cada arquivo na hora e avisamos se algum não der para ler.",
  },
  {
    titulo: "O escritório analisa",
    texto:
      "Com os documentos organizados, o advogado avalia o seu caso e decide " +
      "o que é possível pedir. Essa decisão é dele, não nossa.",
  },
];

export function E0Inicio({
  entidade,
  onComecar,
  onVerPrivacidade,
}: {
  entidade?: string;
  onComecar: () => void;
  onVerPrivacidade: () => void;
}) {
  return (
    <div className="space-y-10">
      <motion.section
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
      >
        {entidade ? (
          <p className="text-sm font-medium text-acento">{entidade}</p>
        ) : null}
        <h1 className="mt-1 text-[28px] font-semibold leading-tight text-tinta sm:text-4xl">
          Envie os seus documentos para a execução da sua sentença
        </h1>
        <p className="mt-4 max-w-2xl text-[17px] leading-relaxed text-tinta/75">
          Se você já tem uma sentença julgada a seu favor, o passo seguinte é
          cobrar o que ela determinou. Para isso o escritório precisa dos seus
          documentos — organizados, legíveis e completos.
        </p>
        <p className="mt-3 max-w-2xl text-[17px] leading-relaxed text-tinta/75">
          Esta página é o caminho para entregá-los sem idas e vindas.
        </p>

        <div className="mt-7 flex flex-wrap items-center gap-4">
          <Botao onClick={onComecar} className="h-12 px-7 text-base">
            Comece aqui
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Botao>
          <span className="flex items-center gap-1.5 text-sm text-tinta/60">
            <Clock className="h-4 w-4" aria-hidden="true" />
            cerca de 15 minutos
          </span>
        </div>
      </motion.section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-tinta/50">
          Como funciona
        </h2>
        <ol className="mt-4 space-y-4">
          {PASSOS.map((p, i) => (
            <motion.li
              key={p.titulo}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: 0.06 * (i + 1) }}
              className="flex gap-4 rounded-lg border border-borda bg-carta p-4 sm:p-5"
            >
              <span
                aria-hidden="true"
                className="flex h-8 w-8 shrink-0 items-center justify-center
                  rounded-full bg-acento/10 text-sm font-semibold text-acento"
              >
                {i + 1}
              </span>
              <span>
                <span className="block font-medium text-tinta">{p.titulo}</span>
                <span className="mt-1 block text-[15px] leading-relaxed text-tinta/70">
                  {p.texto}
                </span>
              </span>
            </motion.li>
          ))}
        </ol>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          {
            Icone: FileCheck2,
            titulo: "Conferimos na hora",
            texto:
              "CPF, número do processo e legibilidade dos arquivos. Errar " +
              "aqui é barato; descobrir depois é caro.",
          },
          {
            Icone: Lock,
            titulo: "Seus documentos não saem do aparelho",
            texto:
              "A conferência de legibilidade é feita no seu próprio " +
              "navegador, antes de qualquer envio.",
          },
          {
            Icone: ShieldCheck,
            titulo: "Pode parar e voltar",
            texto:
              "O preenchimento fica salvo. Se faltar um documento, você " +
              "busca e continua depois.",
          },
        ].map(({ Icone, titulo, texto }) => (
          <div key={titulo} className="rounded-lg border border-borda bg-carta p-4">
            <Icone className="h-5 w-5 text-acento" aria-hidden="true" />
            <p className="mt-2.5 font-medium text-tinta">{titulo}</p>
            <p className="mt-1 text-sm leading-relaxed text-tinta/70">{texto}</p>
          </div>
        ))}
      </section>

      <section className="rounded-lg border border-borda bg-papel p-5">
        <h2 className="font-medium text-tinta">O que esta página não faz</h2>
        <ul className="mt-2.5 space-y-2 text-[15px] leading-relaxed text-tinta/75">
          <li>
            • <strong>Não diz se você tem direito.</strong> Quem avalia isso é
            o advogado, com os documentos na mão. Qualquer resposta nossa seria
            chute — e chute sobre direito cria expectativa que não se sustenta.
          </li>
          <li>
            • <strong>Não calcula valores.</strong> Quanto a sentença vale
            depende do que ela determinou, de índices e de prazos. Essa conta é
            feita no processo, não aqui.
          </li>
          <li>
            • <strong>Não é um processo.</strong> Preencher esta página não
            apresenta ação nenhuma em juízo. Isso é feito pelo advogado, depois.
          </li>
        </ul>
        <p className="mt-4 text-sm text-tinta/60">
          Antes de começar, vale ler{" "}
          <button
            type="button"
            onClick={onVerPrivacidade}
            className="text-acento underline underline-offset-2 hover:no-underline"
          >
            como tratamos os seus dados
          </button>
          .
        </p>
      </section>
    </div>
  );
}
