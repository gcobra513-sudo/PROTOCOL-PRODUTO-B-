/**
 * Rascunho salvo no navegador.
 *
 * A especificação chama isto de principal causa de abandono: a pessoa junta
 * seis documentos, preenche vinte campos, fecha a aba sem querer e perde
 * tudo. Com 15 mil pessoas, mesmo 5% de abandono são 750 cadastros a
 * recuperar à mão.
 *
 * LIMITES, ditos de frente:
 *
 * - é `localStorage`: fica NESTE navegador, neste dispositivo. Não sincroniza
 *   e não sai do aparelho. O servidor já existe, e o rascunho continua NÃO
 *   indo para ele de propósito: só o envio final sai, e até lá a pessoa está
 *   corrigindo o que escreveu — mandar rascunho a cada tecla guardaria
 *   versões que ninguém pediu de um cadastro que ainda não existe;
 * - pode falhar. Aba privada, armazenamento bloqueado, cota cheia — qualquer
 *   acesso pode lançar. Então TODA leitura e escrita vai em try/catch, e o
 *   formulário tem de funcionar sem nada salvo;
 * - **não guarda o conteúdo dos documentos.** Só o registro de que foram
 *   enviados, o nome e o hash. Guardar PDF de identidade e procuração no
 *   navegador seria acumular documento de 15 mil pessoas em máquina que não
 *   controlamos.
 */
import { RASCUNHO_VAZIO, type Rascunho } from "./tipos";

const CHAVE = "sindilote.portal.rascunho.v1";

export function salvar(r: Rascunho): boolean {
  try {
    const paraSalvar: Rascunho = {
      ...r,
      atualizadoEm: new Date().toISOString(),
      // Os documentos ficam só como registro; o arquivo em si não entra.
      documentos: r.documentos.map((d) => ({ ...d })),
    };
    localStorage.setItem(CHAVE, JSON.stringify(paraSalvar));
    return true;
  } catch {
    // Aba privada ou cota cheia. Não é erro do usuário e não para o
    // formulário — só significa que não dá para voltar depois.
    return false;
  }
}

export function soDigitos(v: string): string {
  return (v ?? "").replace(/\D/g, "");
}

/** O rascunho guardado, SE for desta pessoa. Chamada só depois que o portão
 *  conferiu o CPF.
 *
 *  O RASCUNHO É DE UMA PESSOA, E O NAVEGADOR PODE NÃO SER. O sindicato
 *  atende vários filiados do mesmo computador da sede, e a versão anterior
 *  restaurava o rascunho ao abrir a página, antes de qualquer identificação:
 *  quem sentava depois de alguém que não terminou caía DENTRO do cadastro
 *  dela, com nome, CPF e e-mail na tela (medido no navegador, 12/11/2026).
 *
 *  QUANDO NÃO É DELA, APAGA. Não basta não mostrar: o que ficasse guardado
 *  ficaria para o próximo que soubesse onde olhar. O custo é a dona, se
 *  voltar depois de outra pessoa ter usado o computador, começar do zero —
 *  e entre ela redigitar e o cadastro dela ficar exposto, redigitar.
 *
 *  Sem CPF não apaga nem devolve: é a tela ANTES do portão, e apagar ali
 *  faria a dona perder o rascunho só por abrir a página.
 */
export function carregarDe(cpf: string): Rascunho | null {
  const digitos = soDigitos(cpf);
  if (digitos.length !== 11) return null;
  const salvo = carregar();
  if (!salvo) return null;
  if (soDigitos(salvo.identificacao.cpf) !== digitos) {
    apagar();
    return null;
  }
  return salvo;
}

/** O formulário de quem acabou de se identificar e não tem rascunho: vazio,
 *  só com o CPF. É também o que se usa quando alguém troca o CPF na mesma
 *  aba — o que estava na memória era de OUTRA pessoa. */
export function limpoPara(cpf: string): Rascunho {
  return {
    ...RASCUNHO_VAZIO,
    identificacao: { ...RASCUNHO_VAZIO.identificacao, cpf },
  };
}

/** Lê o que está guardado, SEM perguntar de quem é. Não é para a tela:
 *  quem mostra rascunho usa `carregarDe`. */
function carregar(): Rascunho | null {
  try {
    const bruto = localStorage.getItem(CHAVE);
    if (!bruto) return null;
    const lido = JSON.parse(bruto) as Partial<Rascunho>;
    // Versão diferente começa limpo. A 1 era o cadastro do Produto A, com
    // procuração e endereço: ler aquilo como se fosse uma conta do B
    // produziria um rascunho meio preenchido com campos que não existem
    // mais, e a pessoa descobriria no envio.
    if (lido.versao !== RASCUNHO_VAZIO.versao) return null;
    return {
      ...RASCUNHO_VAZIO,
      ...lido,
      identificacao: {
        ...RASCUNHO_VAZIO.identificacao,
        ...(lido.identificacao ?? {}),
      },
      carreira: { ...RASCUNHO_VAZIO.carreira, ...(lido.carreira ?? {}) },
      filiacao: { ...RASCUNHO_VAZIO.filiacao, ...(lido.filiacao ?? {}) },
      judicial: { ...RASCUNHO_VAZIO.judicial, ...(lido.judicial ?? {}) },
      // Os BYTES nunca foram salvos — só a ficha. Recarregar a página perde
      // os anexos de propósito, e a tela diz isso.
      documentos: [],
    };
  } catch {
    return null;
  }
}

export function apagar(): void {
  try {
    localStorage.removeItem(CHAVE);
  } catch {
    /* nada a fazer, e não é problema do usuário */
  }
}

export function disponivel(): boolean {
  try {
    const t = "__sindilote_teste__";
    localStorage.setItem(t, "1");
    localStorage.removeItem(t);
    return true;
  } catch {
    return false;
  }
}
