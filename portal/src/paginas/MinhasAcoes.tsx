/**
 * A tela que o cadastro promete.
 *
 * O último passo do cadastro diz, com estas palavras: "a gente lê os seus
 * documentos e mostra de quais ações você faz parte e o que pode ser feito em
 * cada uma". Até o checkpoint 7c o motor calculava isso e ninguém via.
 *
 * A ORDEM DOS BLOCOS É A DECISÃO DE DESENHO, e ela é o contrário da ordem em
 * que o motor pensa:
 *
 *   1. PENDÊNCIAS, separadas por quem destrava. Vem primeiro porque é a
 *      única parte sobre a qual a pessoa pode AGIR hoje — e porque é o que
 *      corta o telefonema. "Depende do tribunal" é resposta completa;
 *   2. DE QUAIS AÇÕES VOCÊ FAZ PARTE, com o período. O período não é detalhe
 *      técnico: é a pessoa poder conferir a nossa conta dos anos dela antes
 *      de qualquer valor existir;
 *   3. O QUE CABE EM CADA UMA, nas duas trilhas.
 *
 * E O QUE ESTA TELA NÃO FAZ: não promete dinheiro, não esconde "não cabe", e
 * não chama de erro o estado em que não há nada homologado. Hoje o catálogo
 * tem `homologado = "N"` em tudo, então a tela mostra muita conferência
 * pendente — e isso é o retrato certo, não defeito de tela.
 */
import { useEffect, useState } from "react";

import { Aviso, Cartao } from "../componentes/ui";
import { Portao } from "./Portao";
import * as api from "../lib/envio";
import {
  comoFrase,
  explicacaoDaTrilha,
  periodo,
  resumo,
  rotuloDaTrilha,
  rotuloDoEstado,
  rotuloDoVeredicto,
  semPrefixo,
  tomDoEstado,
  tomDoVeredicto,
  type Tom,
} from "../lib/veredicto";

const CORES: Record<Tom, string> = {
  bom: "border-bom/40 bg-bom/10 text-bom",
  neutro: "border-borda bg-papel text-tinta/80",
  alerta: "border-alerta/40 bg-alerta/10 text-alerta",
};

function Selo({ tom, children }: { tom: Tom; children: React.ReactNode }) {
  return (
    <span
      className={`inline-block shrink-0 rounded-full border px-3 py-1 text-[13px] font-semibold ${CORES[tom]}`}
    >
      {children}
    </span>
  );
}

/** As pendências, por quem destrava. É o bloco que existe para a pessoa não
 *  precisar ligar: cada grupo diz de quem é e o que esperar. */
function Pendencias({ grupos }: { grupos: api.GrupoDePendencia[] }) {
  const comItens = grupos.filter((g) => g.itens.length > 0);
  if (comItens.length === 0) return null;
  // O TEXTO MUDA QUANDO NÃO HÁ NADA SEU. Dizia sempre "você só precisa agir
  // no primeiro grupo" — e quando o grupo "depende de você" está vazio, o
  // primeiro grupo é o do sindicato. A frase mandava a pessoa providenciar o
  // que não é dela, que é o oposto do que esta tela existe para fazer.
  const seu = grupos.find((g) => g.quem === "VOCE")?.itens.length ?? 0;
  return (
    <Cartao
      titulo="O que ainda falta, e de quem é"
      explicacao={
        seu > 0
          ? "Separado por quem resolve. Você só precisa agir no primeiro grupo."
          : "Separado por quem resolve. Nada aqui depende de você agora — não é preciso fazer nada nem ligar."
      }
    >
      {comItens.map((g) => (
        <div
          key={g.quem}
          className="rounded-md border border-borda bg-papel p-4"
        >
          <p className="font-semibold text-tinta">{g.titulo}</p>
          <p className="mt-1 text-[14px] leading-relaxed text-tinta/70">
            {g.explicacao}
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-[15px] text-tinta">
            {g.itens.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </Cartao>
  );
}

function Acoes({ acoes }: { acoes: api.AcaoDoFiliado[] }) {
  return (
    <Cartao
      titulo="De quais ações você faz parte"
      explicacao="Uma ação coletiva alcança uma carreira, num período. O que decide é o cruzamento do seu tempo de filiação com o período dela — por isso os comprovantes de contribuição valem tanto."
    >
      {acoes.length === 0 ? (
        <Aviso tom="neutro">
          Ainda não há ação cadastrada para a sua categoria. Isso não quer
          dizer que você não tenha direito a nada — quer dizer que não há o
          que cruzar com os seus dados hoje.
        </Aviso>
      ) : (
        acoes.map((a) => {
          const faixa = periodo(a.inicio, a.fim, a.meses);
          return (
            <div
              key={a.id}
              className="rounded-md border border-borda bg-papel p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <p className="font-semibold text-tinta">{a.rotulo}</p>
                <Selo tom={tomDoEstado(a.estado)}>
                  {rotuloDoEstado(a.estado)}
                </Selo>
              </div>
              {faixa ? (
                <p className="mt-2 text-[15px] text-tinta">
                  Você entra <strong>{faixa}</strong>.{" "}
                  <span className="text-tinta/70">
                    Filiação parcial é participação parcial: conta só o que
                    você viveu.
                  </span>
                </p>
              ) : null}
              {a.motivos.length > 0 ? (
                <ul className="mt-2 space-y-1 text-[14px] leading-relaxed text-tinta/70">
                  {a.motivos.map((m) => (
                    <li key={m}>{comoFrase(semPrefixo(m, a.rotulo))}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })
      )}
    </Cartao>
  );
}

function Trilha({
  trilha,
  oportunidades,
}: {
  trilha: string;
  oportunidades: api.OportunidadeDoFiliado[];
}) {
  if (oportunidades.length === 0) return null;
  return (
    <Cartao titulo={rotuloDaTrilha(trilha)} explicacao={explicacaoDaTrilha(trilha)}>
      {oportunidades.map((o) => {
        const faixa = periodo(o.periodo_inicio, o.periodo_fim, o.meses);
        return (
          <div
            key={`${o.trilha}-${o.referencia}`}
            className="rounded-md border border-borda bg-papel p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <p className="font-semibold text-tinta">
                {/* O rótulo do motor já vem prefixado com a trilha, e aqui
                    isso repetiria o título do cartão. */}
                {o.rotulo.replace(/^(Executar|Ajuizar):\s*/, "")}
              </p>
              <Selo tom={tomDoVeredicto(o.veredicto)}>
                {rotuloDoVeredicto(o.veredicto)}
              </Selo>
            </div>
            {faixa ? (
              <p className="mt-2 text-[15px] text-tinta">
                Período considerado: <strong>{faixa}</strong>.
              </p>
            ) : null}
            {o.motivos.length > 0 ? (
              <ul className="mt-2 space-y-1 text-[14px] leading-relaxed text-tinta/70">
                {o.motivos.map((m) => (
                  <li key={m}>{comoFrase(semPrefixo(m, o.rotulo))}</li>
                ))}
              </ul>
            ) : null}
            {o.notas.length > 0 ? (
              <ul className="mt-2 space-y-1 text-[14px] leading-relaxed text-tinta/60">
                {o.notas.map((n) => (
                  <li key={n}>{comoFrase(semPrefixo(n, o.rotulo))}</li>
                ))}
              </ul>
            ) : null}
            {/* A fonte fica na tela, não no rodapé: quem quiser conferir o
                que dizemos tem de poder ir ao texto do tribunal. */}
            {o.fonte && /^https?:\/\//.test(o.fonte) ? (
              <p className="mt-3 text-[14px]">
                <a
                  href={o.fonte}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-tinta underline"
                >
                  Ver a fonte desta informação
                </a>
              </p>
            ) : null}
          </div>
        );
      })}
    </Cartao>
  );
}

export function MinhasAcoes({ entidade }: { entidade: string }) {
  const [token, setToken] = useState("");
  const [dados, setDados] = useState<api.MinhasAcoes | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!token) return;
    void api
      .minhasAcoes(token)
      .then(setDados)
      .catch((e) =>
        setErro(e instanceof Error ? e.message : "não foi possível consultar"),
      );
  }, [token]);

  if (!token) {
    return (
      <Portao
        entidade={entidade}
        titulo="Minhas ações"
        explicacao="Veja de quais ações você faz parte e o que cabe em cada uma. Sem senha: o código vai para o e-mail que o seu sindicato tem em cadastro."
        onToken={setToken}
      />
    );
  }

  if (erro) {
    return (
      <Cartao titulo="Minhas ações">
        <Aviso tom="alerta">{erro}</Aviso>
      </Cartao>
    );
  }

  if (!dados) {
    return (
      <Cartao titulo="Minhas ações">
        <Aviso tom="neutro">Carregando…</Aviso>
      </Cartao>
    );
  }

  const doFiliado =
    dados.pendencias.find((g) => g.quem === "VOCE")?.itens.length ?? 0;

  return (
    <div className="space-y-6">
      <Cartao
        titulo={dados.filiado ? `Olá, ${dados.filiado}` : "Minhas ações"}
        explicacao={resumo(dados.acoes, doFiliado)}
      >
        {/* O limite vem do servidor e aparece na tela, não no rodapé: a
            pessoa que lê "não é parecer" é a que não cria expectativa. */}
        <Aviso tom="alerta">{dados.aviso}</Aviso>
        {dados.categorias.length > 0 ? (
          <p className="text-[14px] text-tinta/60">
            Categoria considerada: {dados.categorias.join(", ")}.
          </p>
        ) : null}
      </Cartao>

      <Pendencias grupos={dados.pendencias} />
      <Acoes acoes={dados.acoes} />
      <Trilha
        trilha="executar"
        oportunidades={dados.oportunidades.filter(
          (o) => o.trilha === "executar",
        )}
      />
      <Trilha
        trilha="ajuizar"
        oportunidades={dados.oportunidades.filter(
          (o) => o.trilha === "ajuizar",
        )}
      />
    </div>
  );
}
