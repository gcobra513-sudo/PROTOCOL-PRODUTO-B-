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
  resumoDaFilaDeLeitura,
  camposDaLeitura,
  faltaNaLeitura,
  fatosDaLeitura,
  rotuloDoDispositivo,
  filtrarPessoas,
  situacaoDaPessoa,
  resumoDaPlanilha,
  resumoDoAcesso,
  resumoDoEnvioDoRol,
  resumoDoRolVigente,
  atalhoDoGargalo,
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

describe("a fila de leitura humana", () => {
  it("com documentos esperando, aparece e diz quantos e de quantas pessoas", () => {
    const r = resumoDaFilaDeLeitura({ documentos: 7, pessoas: 3, ilegiveis: 0, sem_banco: false });
    expect(r.mostra).toBe(true);
    expect(r.frase).toContain("7 documentos");
    expect(r.frase).toContain("3 pessoas");
  });

  it("singular certo, porque 1 documento de 1 pessoa é o caso do primeiro dia", () => {
    const r = resumoDaFilaDeLeitura({ documentos: 1, pessoas: 1, ilegiveis: 0, sem_banco: false });
    expect(r.frase).toContain("1 documento ");
    expect(r.frase).toContain("1 pessoa");
    expect(r.frase).not.toContain("1 documentos");
  });

  it("NÃO promete o que o produto ainda não faz", () => {
    // Não existe tela para REGISTRAR a leitura feita por uma pessoa. Uma
    // frase como "clique para ler" ou "em análise" prometeria um fluxo que
    // não há — a fila tem entrada e contador, e ainda não tem saída.
    const f = resumoDaFilaDeLeitura({ documentos: 2, pessoas: 1, ilegiveis: 0, sem_banco: false })
      .frase.toLowerCase();
    expect(f).not.toContain("em análise");
    expect(f).not.toContain("clique");
    expect(f).toContain("incompleta");
  });

  it("fila vazia não ocupa a tela", () => {
    expect(
      resumoDaFilaDeLeitura({ documentos: 0, pessoas: 0, ilegiveis: 0, sem_banco: false }).mostra,
    ).toBe(false);
  });

  it("sem banco, diz que não sabe — zero afirmaria que não há nada esperando", () => {
    const r = resumoDaFilaDeLeitura({ documentos: 0, pessoas: 0, ilegiveis: 0, sem_banco: true });
    expect(r.mostra).toBe(true);
    expect(r.frase.toLowerCase()).toContain("não dá para saber");
  });
});

describe("o formulário de leitura, por tipo de documento", () => {
  it("pede só o que o motor usa, e muda com o tipo", () => {
    expect(camposDaLeitura("sentenca")).toEqual(["dispositivo", "numero_processo"]);
    expect(camposDaLeitura("certidao_transito")).toEqual(["transito_em_julgado"]);
    expect(camposDaLeitura("contribuicao")).toEqual(["periodo_inicio", "periodo_fim"]);
    // Tipo que não conhecemos: não inventa campo — só registra que foi lido.
    expect(camposDaLeitura("ficha_financeira")).toEqual([]);
  });

  it("não deixa registrar sentença sem dizer o que ela decidiu", () => {
    expect(faltaNaLeitura("sentenca", {})).toContain("o que a sentença decidiu");
    expect(faltaNaLeitura("sentenca", { dispositivo: "procedente" })).toEqual([]);
    // o número do processo é opcional: nem toda página fotografada o traz
    expect(faltaNaLeitura("sentenca", { dispositivo: "improcedente",
                                        numero_processo: "" })).toEqual([]);
  });

  it("certidão exige a data, e comprovante exige período na ordem certa", () => {
    expect(faltaNaLeitura("certidao_transito", {})).toHaveLength(1);
    expect(faltaNaLeitura("certidao_transito",
                          { transito_em_julgado: "2019-08-22" })).toEqual([]);
    expect(faltaNaLeitura("contribuicao", { periodo_inicio: "2010-01" })).toHaveLength(1);
    expect(faltaNaLeitura("contribuicao",
                          { periodo_inicio: "2012-01", periodo_fim: "2010-01" }),
    ).toContain("o período termina antes de começar");
    expect(faltaNaLeitura("contribuicao",
                          { periodo_inicio: "2010-01", periodo_fim: "2012-12" }),
    ).toEqual([]);
  });

  it("só manda os campos do tipo, e nunca campo vazio", () => {
    // Campo vazio mandado vira "" no servidor, e um fato vazio é pior que
    // fato nenhum: parece que alguém leu e não havia nada.
    expect(fatosDaLeitura("sentenca", { dispositivo: "procedente",
                                        numero_processo: "  ",
                                        transito_em_julgado: "2019-01-01" }),
    ).toEqual({ dispositivo: "procedente" });
  });

  it("o dispositivo aparece em português de gente", () => {
    expect(rotuloDoDispositivo("parcialmente_procedente")).toBe(
      "Parcialmente procedente",
    );
    expect(rotuloDoDispositivo("extinto")).toContain("Extinto");
  });

  it("a fila diz quando há documento que nem uma pessoa conseguiu ler", () => {
    const r = resumoDaFilaDeLeitura({ documentos: 0, pessoas: 0, ilegiveis: 2,
                                      sem_banco: false });
    expect(r.mostra).toBe(true);
    expect(r.frase).toContain("2 documentos");
    expect(r.frase.toLowerCase()).toContain("pedir de novo");
  });
});

describe("a lista nome por nome", () => {
  const P = (nome: string, extra: Partial<api.PessoaNaLista> = {}): api.PessoaNaLista => ({
    nome, cpf: "***.444.777-**", cadastrou: true, pode: false,
    depende_de: [], acoes: [], oportunidades: [], ...extra,
  });
  const BASE = [
    P("JOSÉ DA SILVA (EXEMPLO)", { depende_de: ["VOCE", "TRIBUNAL"] }),
    P("MARIA JOÃO (EXEMPLO)", { depende_de: ["CONFERENCIA"] }),
    P("ANA PAULA (EXEMPLO)", { pode: true }),
  ];

  it("busca pelo nome sem exigir acento nem maiúscula", () => {
    // O gestor digita "jose" e "joao". Exigir o acento é fazer a busca
    // falhar para quem escreve como todo mundo escreve.
    expect(filtrarPessoas(BASE, { texto: "jose", dono: "" }).map((p) => p.nome))
      .toEqual(["JOSÉ DA SILVA (EXEMPLO)"]);
    expect(filtrarPessoas(BASE, { texto: "JOAO", dono: "" })).toHaveLength(1);
  });

  it("filtra por de quem depende — e quem depende de dois aparece nos dois", () => {
    expect(filtrarPessoas(BASE, { texto: "", dono: "VOCE" })).toHaveLength(1);
    expect(filtrarPessoas(BASE, { texto: "", dono: "TRIBUNAL" })).toHaveLength(1);
    expect(filtrarPessoas(BASE, { texto: "", dono: "CONFERENCIA" })[0]!.nome)
      .toContain("MARIA");
  });

  it("\"quem já pode\" é filtro próprio, não um dono", () => {
    expect(filtrarPessoas(BASE, { texto: "", dono: "PODE" }).map((p) => p.nome))
      .toEqual(["ANA PAULA (EXEMPLO)"]);
  });

  it("sem filtro, devolve todo mundo", () => {
    expect(filtrarPessoas(BASE, { texto: "  ", dono: "" })).toHaveLength(3);
  });

  it("a situação de cada um cabe numa linha, com as palavras do painel", () => {
    expect(situacaoDaPessoa(BASE[2]!)).toContain("pode");
    const s = situacaoDaPessoa(BASE[0]!);
    expect(s).toContain("depende do filiado");
    expect(s).toContain("depende do tribunal");
    // Quem não tem pendência nem pode: não se inventa estado.
    expect(situacaoDaPessoa(P("X"))).toBe("sem ação que a alcance");
  });
});

describe("a prévia da planilha, antes de o gestor confirmar", () => {
  const PREVIA: api.PreviaDaPlanilha = {
    sha256: "abc", arquivo: "base.xlsx", manchete: "", linhas: 12,
    pessoas: 10, alcancaveis: 7, inalcancaveis: 3, divergentes: 2,
    colunas_ausentes: ["telefone"], apagados_a_pedido: 1, gravado: false,
  };

  it("diz quantas pessoas, e quantas o sindicato NÃO alcança", () => {
    const linhas = resumoDaPlanilha(PREVIA).join("\n");
    expect(linhas).toContain("10 pessoas");
    expect(linhas).toContain("3");
    expect(linhas.toLowerCase()).toContain("não consegue falar");
  });

  it("avisa de quem pediu apagamento — quantos, nunca quem", () => {
    const linhas = resumoDaPlanilha(PREVIA).join("\n");
    expect(linhas).toContain("1 pessoa");
    expect(linhas.toLowerCase()).toContain("apagamento");
    expect(linhas.toLowerCase()).toContain("tire");
  });

  it("não fala do que não aconteceu", () => {
    // Linha "0 pediram apagamento" em toda prévia vira ruído que ninguém lê
    // no dia em que o número não for zero.
    const limpa = resumoDaPlanilha({ ...PREVIA, apagados_a_pedido: 0,
                                     divergentes: 0, colunas_ausentes: [] });
    expect(limpa.join("\n").toLowerCase()).not.toContain("apagamento");
    expect(limpa.join("\n").toLowerCase()).not.toContain("divergen");
  });
});

describe("o que a planilha muda em quem consegue entrar (T26)", () => {
  const ACESSO: api.AcessoPelaPlanilha = {
    novos: 40, novos_aguardando: 4, novos_por_dominio: 6,
    trocas_aguardando: 3,
    trocas_recusadas: 1, sem_email: 5, divergentes: 2, fora_da_planilha: 7,
  };

  it("e-mail repetido em gente nova: NÃO entrou, e diz o que fazer", () => {
    // O gestor precisa saber duas coisas: que essas pessoas não entram
    // ainda, e que basta um e-mail só de cada uma para entrarem na hora.
    const linhas = resumoDoAcesso(ACESSO, true).join("\n").toLowerCase();
    expect(linhas).toContain("4 pessoas");
    expect(linhas).toContain("outra pessoa");
    expect(linhas).toContain("não entram");
    expect(linhas).toContain("só dela");
  });

  it("antes de gravar fala no futuro; depois, no que aconteceu", () => {
    expect(resumoDoAcesso(ACESSO, false).join("\n")).toContain("vão poder entrar");
    expect(resumoDoAcesso(ACESSO, true).join("\n")).toContain("já podem entrar");
  });

  it("a troca de e-mail NÃO é anunciada como feita", () => {
    // O erro caro: o gestor lê "3 e-mails atualizados", avisa os filiados, e
    // o código continua indo para o endereço antigo. A frase tem de dizer
    // que NÃO vale ainda, e para onde o código vai enquanto isso.
    const linhas = resumoDoAcesso(ACESSO, true).join("\n").toLowerCase();
    expect(linhas).toContain("3 pessoas");
    expect(linhas).toContain("não vale");
    expect(linhas).toContain("e-mail de antes");
    expect(linhas).not.toContain("atualizad");
  });

  it("domínio concentrado: NÃO entraram, sem ensinar o limite", () => {
    // O gestor precisa saber que essas pessoas esperam e por quê. O número
    // do limite fica fora da tela: é a única coisa que só serve a quem
    // quer ficar logo abaixo dele.
    const linhas = resumoDoAcesso(ACESSO, true).join("\n").toLowerCase();
    expect(linhas).toContain("6 pessoas");
    expect(linhas).toContain("domínio");
    expect(linhas).toContain("não entram");
    expect(linhas).not.toMatch(/mais de \d|até \d|limite de \d/);
  });

  it("diz ao gestor que a pessoa é AVISADA do pedido de troca", () => {
    // O gestor precisa saber que o filiado vai receber um e-mail: é ele
    // quem atende o telefone quando alguém perguntar "que troca é essa?".
    const linhas = resumoDoAcesso(ACESSO, true).join("\n").toLowerCase();
    expect(linhas).toContain("é avisada");
  });

  it("quem sumiu da planilha continua entrando, e isso é dito", () => {
    const linhas = resumoDoAcesso(ACESSO, true).join("\n").toLowerCase();
    expect(linhas).toContain("7 pessoas");
    expect(linhas).toContain("continuam");
  });

  it("recusada, sem e-mail e divergente têm cada um a sua frase", () => {
    const linhas = resumoDoAcesso(ACESSO, false).join("\n").toLowerCase();
    expect(linhas).toContain("recusad");
    expect(linhas).toContain("5 pessoas");
    expect(linhas).toContain("dois e-mails");
  });

  it("não fala do que não aconteceu, e aguenta servidor antigo", () => {
    const nada = { novos: 0, novos_aguardando: 0, novos_por_dominio: 0,
                   trocas_aguardando: 0,
                   trocas_recusadas: 0,
                   sem_email: 0, divergentes: 0, fora_da_planilha: 0 };
    expect(resumoDoAcesso(nada, true)).toEqual([]);
    expect(resumoDoAcesso(undefined, true)).toEqual([]);
  });

  it("não chama ninguém de escritório (Regra Zero)", () => {
    expect(resumoDoAcesso(ACESSO, false).join("\n").toLowerCase())
      .not.toContain("escritório");
  });
});

describe("o rol de substituídos: o que o gestor lê antes de confirmar (T19)", () => {
  const PREVIA: api.PreviaDoRol = {
    acao: "GIFA-2006", rotulo: "GIFA (2006)", sha256: "abc", completo: true,
    declarado_completo: true,
    constam: 30, nao_constam: 12, sem_resposta: 0, fora_da_base: 400,
    invalidas: 2, gravado: false,
  };

  it("lista completa: diz quantos constam e quantos passam a ficar FORA", () => {
    const linhas = resumoDoEnvioDoRol(PREVIA).join("\n");
    expect(linhas).toContain("30 pessoas");
    expect(linhas).toContain("12 pessoas");
    expect(linhas.toLowerCase()).toContain("fora do rol");
  });

  it("lista parcial: quem não está nela NÃO é dito fora do rol", () => {
    // "Fora do rol" tem consequência. Numa lista que ninguém declarou
    // inteira, a ausência não responde nada — e a tela não pode sugerir.
    const linhas = resumoDoEnvioDoRol({
      ...PREVIA, completo: false, nao_constam: 0, sem_resposta: 12,
    }).join("\n").toLowerCase();
    expect(linhas).toContain("sem resposta");
    expect(linhas).not.toContain("fora do rol");
  });

  it("diz que o CPF de quem não é da base não fica guardado", () => {
    const linhas = resumoDoEnvioDoRol(PREVIA).join("\n").toLowerCase();
    expect(linhas).toContain("400");
    expect(linhas).toContain("não");
    expect(linhas).toContain("guardad");
  });

  it("avisa quando NINGUÉM da base está na lista: é sinal de arquivo errado", () => {
    const linhas = resumoDoEnvioDoRol({ ...PREVIA, constam: 0, nao_constam: 42 });
    expect((linhas[0] ?? "").toLowerCase()).toContain("ninguém");
    expect(linhas.join("\n").toLowerCase()).toContain("arquivo");
  });

  it("declarada completa com linha ilegível: diz que a declaração NÃO valeu", () => {
    // CPF que perdeu o zero no Excel vira linha ilegível. Enquanto houver
    // uma, ninguém é dado como fora — e o gestor tem de saber por quê, senão
    // marca a caixa, vê "sem resposta" e conclui que o sistema ignorou.
    const linhas = resumoDoEnvioDoRol({
      ...PREVIA, completo: false, declarado_completo: true,
      nao_constam: 0, sem_resposta: 12, invalidas: 3,
    }).join("\n").toLowerCase();
    expect(linhas).toContain("3 linha");
    expect(linhas).toContain("ninguém é dado como fora");
    expect(linhas).toContain("corrija");
    expect(linhas).not.toContain("não foi declarada completa");
  });

  it("não fala do que não aconteceu", () => {
    const limpa = resumoDoEnvioDoRol({ ...PREVIA, fora_da_base: 0, invalidas: 0 })
      .join("\n").toLowerCase();
    expect(limpa).not.toContain("guardad");
    expect(limpa).not.toContain("cpf válido");
  });

  it("o rol que vale: a data como se lê aqui, e quem ficou sem resposta", () => {
    const vigente: api.RolVigente = {
      enviado_em: "2026-11-12T14:03:00+00:00", arquivo: "rol-gifa.xlsx",
      completo: true, declarado_completo: true, constam: 30,
      nao_constam: 12, sem_resposta: 3, fora_da_base: 400, invalidas: 0,
    };
    const linhas = resumoDoRolVigente(vigente).join("\n");
    expect(linhas).toContain("12/11/2026");
    expect(linhas).toContain("rol-gifa.xlsx");
    expect(linhas).toContain("3 pessoas");
    expect(linhas.toLowerCase()).toContain("de novo");
    const semSobra = resumoDoRolVigente({ ...vigente, sem_resposta: 0 }).join("\n");
    expect(semSobra.toLowerCase()).not.toContain("de novo");
  });
});

describe("a pendência leva ao lugar onde se resolve", () => {
  it("a do rol aponta para o cartão do rol", () => {
    const atalho = atalhoDoGargalo({ ...g("CONFERENCIA", "o rol de substituídos de GIFA", 12),
                                     onde: "rol-de-substituidos" });
    expect(atalho?.ancora).toBe("#rol-de-substituidos");
    expect(atalho?.rotulo.toLowerCase()).toContain("rol");
  });

  it("não adivinha pela frase: sem `onde`, não há atalho", () => {
    // A palavra "rol" na frase não basta. Quem diz onde se resolve é o
    // servidor, na origem — a tela que deduzisse erraria calada.
    expect(atalhoDoGargalo(g("CONFERENCIA", "o rol de substituídos de GIFA", 12))).toBeNull();
    expect(atalhoDoGargalo({ ...g("TRIBUNAL", "o julgamento", 3), onde: "" })).toBeNull();
  });

  it("lugar que a tela não conhece não vira link quebrado", () => {
    expect(atalhoDoGargalo({ ...g("CONFERENCIA", "x", 1), onde: "lugar-novo" })).toBeNull();
  });
});
