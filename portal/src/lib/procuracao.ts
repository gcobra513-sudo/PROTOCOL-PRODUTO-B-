/**
 * O modelo de procuração, gerado com os dados que a pessoa já preencheu.
 *
 * POR QUE OFERECER MODELO, e não só pedir "mande a sua procuração"
 *
 * Receber 15 mil procurações com redações diferentes significa 15 mil
 * documentos para conferir um a um, cada um com um problema distinto. Com
 * modelo, a conferência é de assinatura e data.
 *
 * E principalmente: duas cláusulas costumam FALTAR nas procurações genéricas,
 * e as duas travam o processo depois —
 *
 *   * **poderes para executar**: "promover execução / cumprimento de
 *     sentença, receber e dar quitação, levantar valores". Procuração só para
 *     "defesa de direitos" pode não bastar numa execução, e a falha aparece
 *     quando o juiz manda regularizar — com o prazo já correndo;
 *   * **poderes para substabelecer**: sem isso não há como repassar a
 *     atuação, e cada troca de advogado trava o caso.
 *
 * DUAS COISAS QUE ESTE ARQUIVO NÃO DECIDE, de propósito:
 *
 * 1. **Para quem a procuração é dada.** Há dois caminhos — direto ao advogado
 *    do escritório (um documento só, mas 15 mil procurações nominais, e troca
 *    de advogado refaz tudo) ou ao sindicato, que substabelece (mais
 *    flexível, e provavelmente o que já existe). É decisão jurídica pendente
 *    — pergunta 14 de PERGUNTAS_JURIDICO.md —, então o modelo pede o caminho
 *    como parâmetro em vez de escolher.
 * 2. **Quem é o outorgado.** Nome, OAB e endereço do escritório saem como
 *    campos a preencher. Inventar nome de advogado ou número de OAB num
 *    documento que vai ser assinado por milhares de pessoas é inaceitável.
 */
import type { Rascunho } from "./tipos";

export type CaminhoProcuracao = "direto_ao_advogado" | "ao_sindicato";

/** Marcadores que o escritório precisa substituir antes de usar. */
export const A_PREENCHER = [
  "[NOME COMPLETO DO ADVOGADO]",
  "[OAB/UF Nº]",
  "[ENDEREÇO PROFISSIONAL]",
  "[NOME DA ENTIDADE SINDICAL]",
  "[CNPJ DA ENTIDADE]",
] as const;

const CLAUSULA_EXECUTAR =
  "promover execução e cumprimento de sentença, inclusive contra a Fazenda " +
  "Pública; requerer e acompanhar liquidação; apresentar e impugnar cálculos; " +
  "requerer expedição de requisições de pagamento, precatório ou requisição " +
  "de pequeno valor; receber e dar quitação; levantar e movimentar valores " +
  "depositados, inclusive em conta judicial";

const CLAUSULA_SUBSTABELECER =
  "substabelecer esta procuração, com ou sem reserva de iguais poderes, a " +
  "outros advogados ou sociedades de advogados";

function hoje(): string {
  const d = new Date();
  const meses = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
  ];
  return `${d.getDate()} de ${meses[d.getMonth()]} de ${d.getFullYear()}`;
}

function enderecoDe(r: Rascunho): string {
  const p = r.pessoais;
  const partes = [
    [p.logradouro, p.numero].filter(Boolean).join(", "),
    p.complemento,
    p.bairro,
    [p.municipio, p.uf].filter(Boolean).join("/"),
    p.cep ? `CEP ${p.cep}` : "",
  ].filter(Boolean);
  return partes.join(", ") || "[ENDEREÇO]";
}

/** O texto do instrumento. Separado do HTML para poder ser testado. */
export function textoDaProcuracao(
  r: Rascunho,
  caminho: CaminhoProcuracao,
): string {
  const p = r.pessoais;
  const outorgante =
    `${p.nome || "[NOME DO OUTORGANTE]"}, portador(a) do CPF nº ` +
    `${p.cpf || "[CPF]"}${p.rg ? `, RG nº ${p.rg}` : ""}, ` +
    `residente e domiciliado(a) em ${enderecoDe(r)}`;

  const outorgado =
    caminho === "direto_ao_advogado"
      ? "[NOME COMPLETO DO ADVOGADO], inscrito(a) na [OAB/UF Nº], com " +
        "escritório em [ENDEREÇO PROFISSIONAL]"
      : "[NOME DA ENTIDADE SINDICAL], inscrita no CNPJ sob o nº " +
        "[CNPJ DA ENTIDADE], por seus advogados constituídos";

  const finalidade =
    "para o fim específico de promover, em nome do(a) outorgante, a execução " +
    "do título judicial de que é titular, bem como para representá-lo(a) nos " +
    "processos e procedimentos decorrentes";

  return [
    "PROCURAÇÃO",
    "",
    `OUTORGANTE: ${outorgante}.`,
    "",
    `OUTORGADO: ${outorgado}.`,
    "",
    `PODERES: pelo presente instrumento, o(a) outorgante nomeia e constitui ` +
      `o(a) outorgado(a) seu(sua) bastante procurador(a), ${finalidade}, ` +
      `conferindo-lhe os poderes da cláusula “ad judicia et extra”, em ` +
      `qualquer juízo, instância ou tribunal, e ainda, EXPRESSAMENTE, os ` +
      `poderes para ${CLAUSULA_EXECUTAR}, e para ${CLAUSULA_SUBSTABELECER}.`,
    "",
    `${r.pessoais.municipio || "[CIDADE]"}, ${hoje()}.`,
    "",
    "",
    "_______________________________________________",
    p.nome || "[NOME DO OUTORGANTE]",
    `CPF ${p.cpf || "[CPF]"}`,
  ].join("\n");
}

/** Documento para imprimir ou salvar em PDF. Abre em aba nova. */
export function abrirParaImprimir(
  r: Rascunho,
  caminho: CaminhoProcuracao,
): void {
  const texto = textoDaProcuracao(r, caminho);
  const corpo = texto
    .split("\n")
    .map((linha) =>
      linha === "PROCURAÇÃO"
        ? `<h1>${linha}</h1>`
        : linha.trim() === ""
          ? "<p class='vazia'></p>"
          : `<p>${linha.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</p>`,
    )
    .join("\n");

  const html = `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Procuração — ${r.pessoais.nome || "modelo"}</title>
<style>
  @page { size: A4; margin: 3cm 2.5cm; }
  body { font: 12pt/1.7 Georgia, "Times New Roman", serif; color: #111;
         max-width: 17cm; margin: 2cm auto; padding: 0 1cm; }
  h1 { font-size: 14pt; text-align: center; letter-spacing: .12em;
       margin: 0 0 1.5cm; }
  p { margin: 0 0 .35cm; text-align: justify; }
  p.vazia { margin: 0 0 .7cm; }
  .aviso { border: 1pt solid #b4341f; color: #b4341f; padding: .4cm;
           margin-bottom: 1cm; font-family: system-ui, sans-serif;
           font-size: 9pt; line-height: 1.5; text-align: left; }
  @media print { .aviso, .naoimprimir { display: none } }
  .naoimprimir { font-family: system-ui, sans-serif; font-size: 10pt;
                 text-align: center; margin-top: 1.5cm; }
  button { font: inherit; padding: .4em 1.2em; cursor: pointer; }
</style></head><body>
<div class="aviso">
  <strong>MODELO — confira antes de assinar.</strong> Os trechos entre
  colchetes precisam ser preenchidos pelo escritório. Este aviso não aparece
  na impressão.
</div>
${corpo}
<div class="naoimprimir">
  <button onclick="window.print()">Imprimir ou salvar em PDF</button>
</div>
</body></html>`;

  const janela = window.open("", "_blank");
  if (!janela) {
    // Bloqueador de pop-up. Cai para download, que sempre funciona.
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "procuracao-modelo.html";
    a.click();
    URL.revokeObjectURL(url);
    return;
  }
  janela.document.write(html);
  janela.document.close();
}
