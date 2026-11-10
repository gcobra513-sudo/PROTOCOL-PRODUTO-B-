/**
 * O painel do sindicato: o que ele diz e o que ele se recusa a dizer.
 *
 * O teste que importa é o do ACIONÁVEL. O maior gargalo da base pode ser um
 * tema afetado no STJ — e nenhuma decisão de diretoria o destrava. Apontar
 * esse como "o que resolver primeiro" manda o sindicato trabalhar no que não
 * depende dele.
 */
import { describe, expect, it } from "vitest";

import type { Gargalo } from "./envio";
import type * as api from "./envio";
import {
  fracao,
  pessoas,
  presosNoTribunal,
  primeiroAcionavel,
  resumoDoApagamento,
  frasesDaMudanca,
  resumoDasMudancas,
} from "./painel";

function g(quem: string, o_que: string, n: number): Gargalo {
  return { quem, titulo: "", explicacao: "", o_que, pessoas: n, exemplos: [] };
}

describe("o que o sindicato resolve primeiro", () => {
  it("escolhe o maior que depende do sindicato, não o maior da lista", () => {
    const lista = [
      g("TRIBUNAL", "o julgamento do STJ, Tema 1.302", 4000),
      g("CONFERENCIA", "a homologação da GIFA por advogado", 1204),
      g("VOCE", "os comprovantes de contribuição", 900),
      g("CONFERENCIA", "o rol de substituídos", 300),
    ];
    const alvo = primeiroAcionavel(lista);
    expect(alvo?.o_que).toContain("homologação");
    expect(alvo?.pessoas).toBe(1204);
  });

  it("devolve nulo quando nada depende do sindicato", () => {
    expect(primeiroAcionavel([g("TRIBUNAL", "o julgamento", 10)])).toBeNull();
    expect(primeiroAcionavel([])).toBeNull();
  });

  it("conta quem está parado no tribunal", () => {
    expect(
      presosNoTribunal([
        g("CONFERENCIA", "homologar", 5),
        g("TRIBUNAL", "o julgamento do Tema 1.302", 4000),
        g("TRIBUNAL", "o julgamento do Tema 1.410", 12),
      ]),
    ).toBe(4000);
    expect(presosNoTribunal([g("VOCE", "comprovantes", 3)])).toBe(0);
    expect(presosNoTribunal([])).toBe(0);
  });
});

describe("os números como o diretor lê", () => {
  it("plural certo", () => {
    expect(pessoas(1)).toBe("1 pessoa");
    expect(pessoas(0)).toBe("0 pessoas");
    expect(pessoas(12)).toBe("12 pessoas");
  });

  it("fração sempre com denominador", () => {
    // "3 participam" não diz nada: 3 de 4 e 3 de 4.000 são opostos.
    expect(fracao(3, 10)).toBe("3 de 10 (30%)");
    expect(fracao(0, 4812)).toBe("0 de 4812 (0%)");
  });

  it("sem base não inventa percentual", () => {
    expect(fracao(0, 0)).toBe("—");
  });
});

describe("o resumo de um apagamento a pedido", () => {
  const SAIDA: api.ResultadoDoApagamento = {
    marcador: "32b87ccc2dda",
    banco: { pessoa: 1, documento: 3 },
    portao: 2,
    diario: 1,
    arquivos: 4,
    rol: 1,
    acervo: 1,
    logs: 1,
    email_conhecido: true,
    vestigios: [],
  };

  it("sem vestígio, diz que terminou", () => {
    const r = resumoDoApagamento(SAIDA);
    expect(r.terminou).toBe(true);
    expect(r.frase.toLowerCase()).toContain("nada sobrou");
  });

  it("COM vestígio, NÃO lê como apagado — e manda repetir", () => {
    // A regra inteira do recurso está aqui. O servidor devolve 200 com a
    // lista cheia de propósito: é a resposta honesta de que sobrou coisa.
    // Uma tela que pintasse isso de verde desfaria a honestidade do
    // servidor na última polegada.
    const r = resumoDoApagamento({
      ...SAIDA,
      vestigios: ["banco: pessoa", "disco: entrega/"],
    });
    expect(r.terminou).toBe(false);
    expect(r.frase).toContain("2");
    expect(r.frase.toLowerCase()).toContain("repetir");
    expect(r.frase.toLowerCase()).not.toContain("nada sobrou");
  });

  it("lista o que saiu de cada lugar, em português de gente", () => {
    const linhas = resumoDoApagamento(SAIDA).linhas.join("\n");
    expect(linhas).toContain("documento");
    expect(linhas).toContain("4");
    expect(linhas).not.toContain("tombstone");
    expect(linhas).not.toContain("vestigios");
  });

  it("não mostra lugar de onde não saiu nada", () => {
    // Dez linhas com zero esconderiam a única que não é zero.
    const linhas = resumoDoApagamento({
      ...SAIDA,
      banco: {},
      portao: 0,
      diario: 0,
      arquivos: 0,
      rol: 1,
      acervo: 0,
      logs: 0,
    }).linhas;
    expect(linhas).toHaveLength(1);
    // E a linha fala a língua do gestor: "rol" é palavra nossa.
    expect(linhas[0]).toContain("planilha de filiados");
    expect(linhas[0]).not.toContain("rol");
  });

  it("NUNCA traz o marcador para a tela", () => {
    // O marcador é HMAC do CPF. Serve ao operador no log, não ao gestor na
    // tela — e um identificador estável por pessoa numa tela é mais um
    // lugar com dado pessoal.
    const r = resumoDoApagamento(SAIDA);
    const tudo = [r.frase, ...r.linhas, r.nota ?? ""].join(" ");
    expect(tudo).not.toContain("32b87ccc2dda");
  });

  it("diz quando o sindicato não tinha e-mail desta pessoa", () => {
    // O gestor precisa avisar o titular de que foi atendido. Sem e-mail em
    // cadastro, esse aviso tem de sair por outro caminho.
    const sem = resumoDoApagamento({ ...SAIDA, email_conhecido: false });
    expect(sem.nota?.toLowerCase()).toContain("e-mail");
    // E quando havia e-mail, NÃO há nota: um aviso que aparece sempre não
    // é aviso, é moldura.
    expect(resumoDoApagamento(SAIDA).nota).toBeUndefined();
  });
});

describe("o que mudou de veredicto", () => {
  const GRUPO: api.MudancaDeVeredicto = {
    referencia: "GIFA-2006",
    trilha: "executar",
    de: "FALTA",
    para: "PODE",
    pessoas: 12,
    exemplos: ["FULANA DE TAL (EXEMPLO)", "BELTRANO DE TAL (EXEMPLO)"],
  };
  const MUDOU: api.Mudancas = {
    catalogo: "auditor-fiscal-receita-federal@2",
    total: 12,
    sem_banco: false,
    grupos: [GRUPO],
  };

  it("destravar lê como destravar, e travar como travar", () => {
    // A MESMA TELA MOSTRA OS DOIS SENTIDOS, e confundi-los é o pior erro
    // possível aqui: dizer "agora pode" a quem deixou de poder faria o
    // sindicato ligar para a pessoa com a notícia errada.
    expect(frasesDaMudanca(GRUPO).toLowerCase()).toContain("passou a poder");
    const travou = { ...GRUPO, de: "PODE", para: "FALTA" };
    expect(frasesDaMudanca(travou).toLowerCase()).toContain("deixou de poder");
    expect(frasesDaMudanca(travou).toLowerCase()).not.toContain(
      "passou a poder",
    );
  });

  it("diz quantas pessoas, com plural certo", () => {
    expect(frasesDaMudanca(GRUPO)).toContain("12 pessoas");
    expect(frasesDaMudanca({ ...GRUPO, pessoas: 1 })).toContain("1 pessoa");
  });

  it("sem banco, NÃO diz que nada mudou", () => {
    // A diferença entre "nada mudou" e "não dá para saber". Um painel que
    // tranquiliza sem base é pior que um painel que não diz nada.
    const r = resumoDasMudancas({ ...MUDOU, total: 0, sem_banco: true,
                                  grupos: [] });
    expect(r.mostra).toBe(true);
    expect(r.frase.toLowerCase()).not.toContain("nada mudou");
    expect(r.frase.toLowerCase()).toContain("não");
  });

  it("com banco e nada mudou, não ocupa a tela", () => {
    const r = resumoDasMudancas({ ...MUDOU, total: 0, grupos: [] });
    expect(r.mostra).toBe(false);
  });

  it("com mudança, aparece e diz de qual catálogo", () => {
    const r = resumoDasMudancas(MUDOU);
    expect(r.mostra).toBe(true);
    expect(r.frase).toContain("12");
    expect(r.catalogo).toContain("auditor-fiscal-receita-federal@2");
  });
});
