/**
 * Etapa 5 — o processo de origem. A mais importante de todas.
 *
 * Cada filiado tem a SUA sentença, e é o número desse processo que diz onde a
 * execução vai ser protocolada (CPC, art. 516, II: executa-se no juízo que
 * decidiu). Sem ele, o caso não anda.
 *
 * TRÊS ESCOLHAS, NÃO DUAS. A primeira versão desta tela tinha só "informo o
 * número" ou "não sei" — e isso obrigava quem NÃO TEM sentença a dizer que
 * não sabe, enchendo a lista de busca do escritório de gente que não tem nada
 * a procurar. O contrato de dados do motor já previa os três estados; a tela
 * é que estava com dois.
 *
 * E as três coisas que esta tela faz e parecem detalhe:
 *
 * 1. **confere o dígito verificador na hora.** São 20 dígitos e as pessoas
 *    erram ao digitar. O dígito existe para isso, e usá-lo aqui economiza
 *    uma rodada de "confirme seu número" com milhares de pessoas;
 * 2. **avisa quando não é do TRF1** — mas AVISA, não recusa. A pessoa pode
 *    ter processo de outro tribunal e ainda assim ser o processo dela; recusar
 *    seria pôr a nossa suposição acima do fato dela;
 * 3. **"não sei" é resposta completa.** É muito melhor admitir que não sabe
 *    do que chutar. Número chutado é pior que campo vazio, porque ninguém
 *    sabe que está errado.
 */
import { Aviso, Botao, Campo, Cartao, Escolha } from "../componentes/ui";
import { CONTRATO, type ProcessoOrigem, type Resposta } from "../lib/tipos";
import {
  SEGMENTOS,
  conferirProcesso,
  decompor,
  destinoDoNumero,
  formatarProcesso,
} from "../lib/validacao";

export function E5Processo({
  dados,
  onChange,
}: {
  dados: ProcessoOrigem;
  onChange: (campo: keyof ProcessoOrigem, valor: string | string[]) => void;
}) {
  const informou = dados.temProcesso === "sim";
  const problemas = informou ? conferirProcesso(dados.numero) : [];
  const avisos =
    informou && problemas.length === 0
      ? conferirProcesso(dados.numero, { exigirTrf1: true })
      : [];
  const partes = decompor(dados.numero);
  const integro = informou && problemas.length === 0 && partes !== null;

  // O número é íntegro mas não é do TRF1. Antes a tela apenas avisava e
  // deixava enviar — e o servidor recusava, com razão: a execução corre no
  // juízo que decidiu (CPC, art. 516, II). A pessoa descobria no fim o que
  // dava para saber no começo. Agora a tela diz para onde o número vai.
  const foraDoTrf1 = informou && destinoDoNumero(dados.numero) === "acompanhar";

  const acompanhar = dados.acompanhar ?? [];
  const maximo: number = CONTRATO.acompanhamento.maximo;

  const trocarAcompanhar = (indice: number, valor: string) =>
    onChange(
      "acompanhar",
      acompanhar.map((n, i) => (i === indice ? formatarProcesso(valor) : n)),
    );
  const removerAcompanhar = (indice: number) =>
    onChange("acompanhar", acompanhar.filter((_, i) => i !== indice));
  const acrescentarAcompanhar = (valor = "") =>
    onChange("acompanhar", [...acompanhar, valor]);

  return (
    <Cartao
      titulo="O número do seu processo"
      explicacao={
        <>
          É o processo da <strong>sua sentença</strong> — aquele que já foi
          julgado. É ele que define onde a execução vai ser apresentada.
        </>
      }
    >
      <Escolha<Resposta>
        rotulo="Você tem uma sentença a executar?"
        obrigatorio
        valor={dados.temProcesso}
        onChange={(v) => onChange("temProcesso", v)}
        opcoes={[
          {
            valor: "sim",
            rotulo: "Sim, e eu tenho o número do processo",
          },
          {
            valor: "nao_sei",
            rotulo: "Tenho, mas não sei o número",
            detalhe:
              "Marque sem medo. É muito melhor que chutar — o escritório " +
              "procura depois.",
          },
          {
            valor: "nao",
            rotulo: "Não tenho sentença nenhuma sobre isso",
            detalhe: "Melhor saber agora do que descobrir depois.",
          },
        ]}
      />

      {informou ? (
        <>
          <Campo
            rotulo="Número do processo"
            obrigatorio
            inputMode="numeric"
            placeholder="0000000-00.0000.0.00.0000"
            valor={formatarProcesso(dados.numero)}
            onChange={(v) => onChange("numero", formatarProcesso(v))}
            problemas={problemas}
            ajuda="20 dígitos. Pode colar com ou sem pontuação."
          />

          {integro && partes ? (
            <Aviso tom={avisos.length ? "alerta" : "bom"}>
              <p>
                Número íntegro. Pelo que ele informa: processo de{" "}
                <strong>
                  {SEGMENTOS[partes.segmento] ?? "segmento desconhecido"}
                </strong>
                , ano <strong>{partes.ano}</strong>.
              </p>
              {avisos.length ? (
                <ul className="mt-2 space-y-1">
                  {avisos.map((a) => (
                    <li key={a}>• {a}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1">
                  É da Justiça Federal da 1ª Região, como esperado.
                </p>
              )}
            </Aviso>
          ) : null}

          {foraDoTrf1 ? (
            <Aviso tom="alerta">
              <p>
                <strong>Este processo não é da Justiça Federal da 1ª Região.</strong>{" "}
                A execução de uma sentença corre no juízo que a julgou, e o
                escritório atua no TRF1 — então este número não serve como o
                processo da sua sentença aqui.
              </p>
              <p className="mt-2">
                Mas ele serve para <strong>acompanhamento</strong>: a gente
                avisa quando houver movimentação nele, em qualquer dos
                tribunais do país.
              </p>
              <div className="mt-3">
                <Botao
                  tipo="secundario"
                  onClick={() => {
                    acrescentarAcompanhar(dados.numero);
                    onChange("numero", "");
                    onChange("temProcesso", "nao_sei");
                  }}
                >
                  Mover para acompanhamento
                </Botao>
              </div>
            </Aviso>
          ) : null}

          <Aviso tom="neutro">
            O número está na sentença, em qualquer intimação que você recebeu,
            ou com o advogado que cuidou da ação. Se não achar agora, marque a
            segunda opção e siga — dá para corrigir depois.
          </Aviso>
        </>
      ) : null}

      {dados.temProcesso === "nao_sei" ? (
        <>
          <Campo
            rotulo="Alguma pista que ajude a encontrar?"
            valor={dados.observacao}
            onChange={(v) => onChange("observacao", v)}
            placeholder="Ex.: a ação foi pelo sindicato, por volta de 2015"
            ajuda="Opcional. Qualquer detalhe reduz o tempo de busca: ano,
              nome do advogado, vara, cidade."
          />
          <Aviso tom="neutro">
            Você entra numa lista para o escritório localizar o processo. Isso
            não impede você de concluir o cadastro.
          </Aviso>
        </>
      ) : null}

      <div className="space-y-3 border-t border-borda pt-6">
        <div>
          <p className="text-[15px] font-medium text-tinta">
            Outros processos que você quer acompanhar
          </p>
          <p className="mt-1 text-sm text-tinta/70">
            Qualquer processo em que você seja parte, de qualquer tribunal. A
            gente confere a movimentação e avisa você — você não precisa
            ligar para perguntar se andou.
          </p>
        </div>

        {acompanhar.map((numero, i) => (
          <div key={i} className="flex items-end gap-2">
            <div className="flex-1">
              <Campo
                rotulo={`Processo ${i + 1}`}
                inputMode="numeric"
                placeholder="0000000-00.0000.0.00.0000"
                valor={formatarProcesso(numero)}
                onChange={(v) => trocarAcompanhar(i, v)}
                problemas={numero ? conferirProcesso(numero) : []}
              />
            </div>
            <Botao tipo="secundario" onClick={() => removerAcompanhar(i)}>
              Remover
            </Botao>
          </div>
        ))}

        {acompanhar.length < maximo ? (
          <Botao tipo="secundario" onClick={() => acrescentarAcompanhar()}>
            {acompanhar.length ? "Acrescentar outro processo" : "Acrescentar processo"}
          </Botao>
        ) : (
          <Aviso tom="neutro">
            Chegou ao limite de {maximo} processos. Se você tem mais que isso,
            fale com o sindicato.
          </Aviso>
        )}

        <Aviso tom="neutro">
          O que a gente mostra é a <strong>movimentação</strong> registrada
          pelo tribunal, com cerca de um dia de atraso.{" "}
          <strong>Não é intimação e não serve para contar prazo.</strong>
        </Aviso>
      </div>

      {dados.temProcesso === "nao" ? (
        <Aviso tom="alerta">
          Sem uma sentença já julgada, não há o que executar — a execução
          cobra o que uma decisão determinou. <strong>Você pode concluir o
          cadastro</strong>, e o escritório vai avaliar se existe outro
          caminho para o seu caso. Mas é importante você saber disso agora.
        </Aviso>
      ) : null}
    </Cartao>
  );
}
