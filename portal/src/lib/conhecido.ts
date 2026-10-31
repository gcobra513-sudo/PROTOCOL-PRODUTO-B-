/**
 * O que o sindicato já sabe sobre quem está entrando.
 *
 * A PESSOA RECEBE O LINK NO GRUPO DO SINDICATO E ABRE. Até aqui ela
 * encontrava 17 campos em branco — e **10 deles o sindicato já tinha
 * mandado**. Cada campo desses é gente que abandona o cadastro no meio, e a
 * abandonada é sempre a mesma: a aposentada, no celular.
 *
 * AS DUAS REGRAS DESTE PREENCHIMENTO:
 *
 * 1. **só preenche o que está vazio.** Se a pessoa já digitou alguma coisa,
 *    o que o sindicato mandou NÃO sobrescreve: ela está corrigindo, e
 *    apagar a correção dela no meio da digitação é o pior momento possível;
 * 2. **nada é escondido.** O campo preenchido continua editável e marcado
 *    como vindo do sindicato. Trazer o dado e travá-lo faria a pessoa
 *    desistir quando ele estivesse errado — e é justamente o errado que
 *    precisamos descobrir.
 */
import type { CamposConhecidos } from "./envio";
import type { Rascunho } from "./tipos";

/** Em quais campos do rascunho o dado do sindicato encaixa. Um lugar só:
 *  espalhar isto pelas telas faria um campo novo ser esquecido numa delas. */
const ONDE: Record<string, [keyof Rascunho, string]> = {
  nome_completo: ["identificacao", "nome"],
  cpf: ["identificacao", "cpf"],
  email: ["identificacao", "email"],
  telefone: ["identificacao", "telefone"],
  data_nascimento: ["identificacao", "dataNascimento"],
  cargo: ["carreira", "cargo"],
  situacao: ["carreira", "situacao"],
  unidade: ["carreira", "unidade"],
  data_ingresso: ["carreira", "dataIngresso"],
  data_aposentadoria: ["carreira", "dataAposentadoria"],
  filiado_desde: ["filiacao", "desde"],
  filiado_ate: ["filiacao", "ate"],
};

/** Quais campos do rascunho vieram do sindicato — para a tela poder dizer
 *  "conferido com o seu sindicato" em vez de deixar a pessoa adivinhar de
 *  onde saiu aquilo. */
export function camposDoSindicato(conhecidos: CamposConhecidos): Set<string> {
  const marcados = new Set<string>();
  for (const [campo, valor] of Object.entries(conhecidos ?? {})) {
    const onde = ONDE[campo];
    if (onde && String(valor ?? "").trim()) marcados.add(`${onde[0]}.${onde[1]}`);
  }
  return marcados;
}

/** O rascunho com o que o sindicato mandou, SEM apagar o que a pessoa já
 *  tiver digitado. */
export function preencher(
  rascunho: Rascunho,
  conhecidos: CamposConhecidos,
): Rascunho {
  const novo: Rascunho = {
    ...rascunho,
    identificacao: { ...rascunho.identificacao },
    carreira: { ...rascunho.carreira },
    filiacao: { ...rascunho.filiacao },
  };
  for (const [campo, valor] of Object.entries(conhecidos ?? {})) {
    const onde = ONDE[campo];
    const texto = String(valor ?? "").trim();
    if (!onde || !texto) continue;
    const [secao, chave] = onde;
    const alvo = novo[secao] as unknown as Record<string, unknown>;
    // VAZIO É O ÚNICO LUGAR ONDE ESCREVEMOS. O que a pessoa digitou é
    // correção, e correção não se desfaz.
    if (!String(alvo[chave] ?? "").trim()) alvo[chave] = texto;
  }
  return novo;
}

/** Os documentos que já temos, no rótulo que a pessoa entende. */
export function jaTemos(documentos: string[]): string[] {
  const rotulos: Record<string, string> = {
    contribuicao: "comprovante de contribuição",
    sentenca: "sentença",
    certidao_transito: "certidão de trânsito em julgado",
    outro: "outro documento",
  };
  return (documentos ?? []).map((d) => rotulos[d] ?? d);
}
