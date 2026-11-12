/**
 * O ensaio de navegador: Chromium de verdade contra o portal construído.
 *
 * POR QUE ESTE ARQUIVO EXISTE, e por que em JavaScript. Até 02/11/2026 o
 * `servidor/LEIAME.md` mandava rodar `ferramentas/ensaio_portal.py` e
 * descrevia em detalhe o que ele fazia. O arquivo NUNCA EXISTIU. Estava
 * escrito, então passava por verificado — a mesma doença que a auditoria
 * achou sete vezes nos comentários do código, um andar acima.
 *
 * O buraco que a descrição nomeava é real e nenhuma outra suíte o cobre:
 * **o navegador mandando um nome de campo que o servidor não espera.** Os
 * testes do servidor provam o que ele ACEITA; os do portal provam o que a
 * tela DIZ; nenhum dos dois roda React num navegador contra o servidor.
 *
 * Em JavaScript porque o Playwright instalado nesta máquina é o de Node, e
 * o Chromium que ele conhece é o de `/opt/pw-browsers`. Instalar o
 * Playwright de Python traria um segundo navegador e uma segunda versão
 * para manter. Quem orquestra é `ferramentas/ensaio_portal.py`: ele sobe o
 * servidor, semeia os dados, chama este arquivo e CONFERE O DISCO depois.
 *
 * Fala com o orquestrador por JSON: a configuração vem em argv[2], o
 * resultado sai em stdout entre marcadores. Erro de console e exceção de
 * página DERRUBAM o ensaio: num React, "funcionou mas gritou no console" é
 * um defeito que a pessoa vê como tela em branco meia hora depois.
 */
// CommonJS, e não ESM, por um motivo medido: nesta máquina o Playwright é
// um pacote GLOBAL, e `require("playwright")` o resolve de qualquer
// diretório enquanto `import` devolve ERR_MODULE_NOT_FOUND. Trocar isto por
// ESM exige instalar o Playwright no repositório — um segundo navegador e
// uma segunda versão para manter.
const { chromium } = require("playwright");
const fs = require("node:fs/promises");

const cfg = JSON.parse(process.argv[2]);
const passos = [];
let pagina = null;

function marco(texto) {
  passos.push(texto);
  if (cfg.verboso) console.error(`    · ${texto}`);
}

async function registrarFalha(erro) {
  const diagnostico = { erro: String(erro && erro.message ? erro.message : erro) };
  if (pagina && !pagina.isClosed()) {
    try {
      const tiro = `${cfg.saida}/falhou.png`;
      await pagina.screenshot({ path: tiro, fullPage: true });
      diagnostico.imagem = tiro;
      const html = `${cfg.saida}/falhou.html`;
      await fs.writeFile(html, await pagina.content(), "utf-8");
      diagnostico.html = html;
      diagnostico.visivel = (await pagina.innerText("body")).slice(0, 1200);
    } catch (e) {
      diagnostico.diagnosticoFalhou = String(e);
    }
  }
  return diagnostico;
}

/** Entra pelo portão: pede o código, LÊ O CÓDIGO DA TELA e confere.
 *
 *  Ler da tela é de propósito: em modo ensaio o servidor devolve
 *  `codigo_do_ensaio` no corpo, e a tela o mostra. Pegar o código
 *  interceptando a resposta HTTP seria mais fácil e testaria menos — o
 *  caminho que a pessoa percorre inclui a tela mostrar o código. */
async function entrar(p, cpf, rotuloCpf, rotuloCodigo) {
  await p.getByLabel(rotuloCpf, { exact: false }).first().fill(cpf);
  await p.getByRole("button", { name: /c.digo/i }).first().click();
  const codigo = await p.locator("code").first().innerText({ timeout: 15000 });
  if (!/^\d{6}$/.test(codigo.trim())) {
    throw new Error(`a tela não mostrou um código de 6 dígitos: ${codigo}`);
  }
  await p.getByLabel(rotuloCodigo, { exact: false }).first().fill(codigo.trim());
  await p.getByRole("button", { name: /^Entrar$/ }).first().click();
  return codigo.trim();
}

async function proxima(p) {
  const botao = p.getByRole("button", { name: /Continuar|Avan.ar|Pr.xim/i }).first();
  await botao.click();
}

/** Uma aba nova, com os gritos do console vigiados.
 *
 *  CONTEXTO POR FASE, de propósito: o filiado e o gestor são duas pessoas
 *  em dois navegadores. Reusar o contexto levaria o token do filiado no
 *  armazenamento local para a tela do gestor, e o ensaio passaria a medir
 *  um estado que ninguém tem. */
async function abrirAba(navegador, gritos, rotulo) {
  const contexto = await navegador.newContext({
    viewport: { width: 1280, height: 1000 },
  });
  const p = await contexto.newPage();
  pagina = p;
  p.on("console", (m) => {
    if (m.type() === "error") gritos.push(`${rotulo}: ${m.text()}`);
  });
  p.on("pageerror", (e) => gritos.push(`${rotulo} pageerror: ${e.message}`));
  return { contexto, p };
}

/** Tudo o que a tela mostra: o texto e o que está dentro dos campos. */
async function oQueATelaMostra(p) {
  const texto = await p.innerText("body");
  const campos = await p.locator("input, textarea, select").evaluateAll(
    (els) => els.map((e) => e.value || "").join("\n"));
  return `${texto}\n${campos}`;
}

/** O COMPUTADOR DA SEDE: duas pessoas, UM navegador.
 *
 *  O sindicato atende vários filiados do mesmo computador. A primeira
 *  começa o cadastro e vai embora sem enviar; a segunda senta em seguida.
 *  O rascunho existe para a PRIMEIRA não perder o que digitou — e não pode
 *  ser o jeito de a segunda ler o nome, o CPF e o e-mail dela.
 *
 *  Um contexto só, de propósito: é o oposto de `abrirAba`. O que se mede é
 *  exatamente o que fica no navegador entre uma pessoa e outra. */
async function faseSede(navegador, gritos, resultado) {
  const contexto = await navegador.newContext({
    viewport: { width: 1280, height: 1000 },
  });
  const abrir = async (rotulo) => {
    const p = await contexto.newPage();
    pagina = p;
    p.on("console", (m) => {
      if (m.type() === "error") gritos.push(`${rotulo}: ${m.text()}`);
    });
    p.on("pageerror", (e) => gritos.push(`${rotulo} pageerror: ${e.message}`));
    await p.goto(`${cfg.web}/?entidade=${cfg.entidade}`, { waitUntil: "networkidle" });
    return p;
  };
  const dela = [cfg.sede.primeira.nome, cfg.sede.primeira.cpf,
                cfg.sede.primeira.cpf.replace(/\D/g, ""),
                cfg.sede.primeira.email];
  const aparece = (tela) => dela.filter((d) => tela.includes(d));
  try {
    // 1. A primeira pessoa começa, preenche e FECHA A ABA sem enviar.
    let p = await abrir("sede: primeira");
    await p.getByRole("button", { name: /^Começar$/ }).click();
    await entrar(p, cfg.sede.primeira.cpf, "CPF", "Código recebido");
    await p.getByText(/Acesso confirmado/).waitFor({ timeout: 15000 });
    await proxima(p);
    await p.getByLabel("Nome completo").fill(cfg.sede.primeira.nome);
    await p.getByLabel("E-mail").fill(cfg.sede.primeira.email);
    await p.waitForTimeout(300);
    await p.close();
    marco("sede: a primeira pessoa preencheu e fechou a aba sem enviar");

    // 2. A SEGUNDA senta no mesmo computador e abre o portal.
    p = await abrir("sede: segunda");
    let viu = aparece(await oQueATelaMostra(p));
    const comecar = p.getByRole("button", { name: /^Começar$/ });
    if (await comecar.count()) {
      await comecar.click();
      await p.waitForTimeout(300);
      viu = viu.concat(aparece(await oQueATelaMostra(p)));
    }
    resultado.sede = { vazouAntesDoPortao: [...new Set(viu)] };
    marco(`sede: antes do portão a segunda viu ${resultado.sede.vazouAntesDoPortao.length} dado(s) da primeira`);

    // Se o portão nem aparece, ela já está DENTRO do cadastro da primeira:
    // registra e para aqui — não há "entrar" para ensaiar.
    const portao = p.getByRole("button", { name: /c.digo/i }).first();
    resultado.sede.caiuDentroDoCadastro =
      !(await portao.isVisible({ timeout: 3000 }).catch(() => false));
    if (resultado.sede.caiuDentroDoCadastro) {
      marco("sede: a segunda pessoa caiu DENTRO do cadastro da primeira, sem portão");
      return;
    }

    // 3. A segunda ENTRA, com o CPF dela. O que era da primeira tem de
    //    sumir da tela E do navegador.
    await entrar(p, cfg.sede.segunda.cpf, "CPF", "Código recebido");
    await p.getByText(/Acesso confirmado/).waitFor({ timeout: 15000 });
    await proxima(p);
    await p.getByLabel("Nome completo").waitFor({ timeout: 15000 });
    resultado.sede.vazouDepoisDoPortao = aparece(await oQueATelaMostra(p));
    const guardado = await p.evaluate(() => JSON.stringify(
      Object.fromEntries(Object.entries(localStorage))));
    resultado.sede.ficouNoNavegador = aparece(guardado);
    await p.close();
    marco("sede: a segunda entrou com o CPF dela");
  } finally {
    await contexto.close();
  }
}

/** A DONA DO RASCUNHO VOLTA: fechou a aba sem querer, abre de novo no mesmo
 *  navegador, passa pelo portão — e encontra o que tinha digitado. É para
 *  isso que o rascunho existe, e a correção do vazamento não pode custar
 *  isso. */
async function faseVolta(navegador, gritos, resultado) {
  const contexto = await navegador.newContext({
    viewport: { width: 1280, height: 1000 },
  });
  try {
    for (const vez of ["primeira vez", "de volta"]) {
      const p = await contexto.newPage();
      pagina = p;
      await p.goto(`${cfg.web}/?entidade=${cfg.entidade}`, { waitUntil: "networkidle" });
      await p.getByRole("button", { name: /^Começar$/ }).click();
      await entrar(p, cfg.sede.primeira.cpf, "CPF", "Código recebido");
      await p.getByText(/Acesso confirmado/).waitFor({ timeout: 15000 });
      await proxima(p);
      const nome = p.getByLabel("Nome completo");
      await nome.waitFor({ timeout: 15000 });
      if (vez === "primeira vez") {
        await nome.fill(cfg.sede.primeira.nome);
        await p.waitForTimeout(300);
        await p.close();
      } else {
        resultado.volta = { nomeRecuperado: await nome.inputValue() };
        // E ELA VAI EMBORA DIREITO: o botão de sair não deixa nada dela no
        // navegador, nem na tela.
        await p.getByRole("button", { name: /Sair e apagar/ }).click();
        await p.getByRole("button", { name: /^Começar$/ }).waitFor({ timeout: 15000 });
        const guardado = await p.evaluate(() => JSON.stringify(
          Object.fromEntries(Object.entries(localStorage))));
        const tela = await oQueATelaMostra(p);
        resultado.volta.sobrouAoSair = [cfg.sede.primeira.nome,
          cfg.sede.primeira.cpf.replace(/\D/g, "")]
          .filter((d) => guardado.includes(d) || tela.includes(d));
        await p.close();
      }
    }
    marco(`volta: a dona reencontrou "${resultado.volta.nomeRecuperado}", e saiu apagando`);
  } finally {
    await contexto.close();
  }
}

/** O cadastro do filiado, do início ao protocolo na tela. */
async function faseCadastro(navegador, gritos, resultado) {
  const { contexto, p } = await abrirAba(navegador, gritos, "cadastro");
  try {
    await p.goto(`${cfg.web}/?entidade=${cfg.entidade}`, { waitUntil: "networkidle" });
    marco("portal abriu");

    // A TELA DE INÍCIO vem antes do portão, e é parte do caminho: ela é o
    // que diz à pessoa o que vai acontecer. Pular direto para o portão
    // ensaiaria um percurso que ninguém faz.
    await p.getByRole("button", { name: /^Começar$/ }).click();
    marco("tela de início: Começar");

    await entrar(p, cfg.filiado.cpf, "CPF", "Código recebido");
    // O portão CONFIRMA e não avança sozinho: quem avança é a pessoa, pelo
    // mesmo "Continuar" de todas as etapas.
    await p.getByText(/Acesso confirmado/).waitFor({ timeout: 15000 });
    await proxima(p);
    await p.getByLabel("Nome completo").waitFor({ timeout: 15000 });
    marco("entrou pelo portão e caiu na etapa Você");

    await p.getByLabel("Nome completo").fill(cfg.filiado.nome);
    await p.getByLabel("E-mail").fill(cfg.filiado.email);
    await proxima(p);
    marco("etapa Você preenchida");

    await p.getByLabel("Seu cargo").fill(cfg.filiado.cargo);
    await p.getByRole("radio", { name: /Aposentado/ }).first().check();
    await p.getByLabel("Filiado desde").fill(cfg.filiado.filiadoDesde);
    await p.getByRole("checkbox", { name: /Ainda sou filiado/ }).first().check();
    await proxima(p);
    marco("etapa Carreira preenchida");

    await p.getByRole("radio", { name: /Não tenho nenhum/ }).first().check();
    await proxima(p);
    marco("etapa Processos respondida");

    for (const [rotulo, arquivos] of cfg.documentos) {
      // O CARTÃO É O DIV MAIS INTERNO QUE TEM AS DUAS COISAS: o rótulo e um
      // campo de arquivo. Filtrar só pelo texto pega qualquer ancestral —
      // inclusive o `body` — e `.last()` sozinho pega o `<p>` do título, que
      // não contém campo nenhum. Prender ao nome da classe CSS resolveria e
      // amarraria o ensaio ao estilo: o rótulo vem do contrato, a classe não.
      const cartao = p
        .locator("div")
        .filter({ hasText: rotulo })
        .filter({ has: p.locator('input[type="file"]') })
        .last();
      await cartao.locator('input[type="file"]').first().setInputFiles(arquivos);
      // O PDF é lido NO NAVEGADOR (pdf.js) antes de poder seguir. Esperar o
      // anexo aparecer é esperar a leitura terminar, e é o que a pessoa vê.
      for (const caminho of arquivos) {
        const nome = caminho.split("/").pop();
        await cartao.getByText(nome, { exact: false })
          .first().waitFor({ timeout: 60000 });
      }
    }
    await p.getByText(/Conferindo/).waitFor({ state: "detached", timeout: 60000 })
      .catch(() => {});
    await proxima(p);
    marco(`etapa Documentos: ${cfg.documentos.flatMap((d) => d[1]).length} PDF(s) anexados`);

    for (const caixa of await p.getByRole("checkbox").all()) {
      if (await caixa.isVisible()) await caixa.check();
    }
    await p.getByRole("button", { name: /Enviar|Confirmar e enviar/i }).first().click();
    marco("cadastro enviado");

    const protocolo = await p.locator("text=/PRT-[A-Z0-9-]+/").first()
      .innerText({ timeout: 30000 });
    resultado.protocolo = (protocolo.match(/PRT-[A-Z0-9-]+/) || [""])[0];
    if (!resultado.protocolo) throw new Error("não achei o protocolo na tela");
    marco(`protocolo lido na tela: ${resultado.protocolo}`);

    // O RECIBO TEM DE DIZER que parte chegou como imagem. Quem espera uma
    // resposta sem saber por que ela demora liga para o sindicato.
    const tela = await p.innerText("body");
    resultado.avisouImagem = /chegaram como imagem/.test(tela);
    if (resultado.avisouImagem) marco("o recibo avisou: 2 documentos como imagem");
  } finally {
    await contexto.close();
  }
}

/** O gestor LÊ o que a máquina não leu, e registra. A fila tem saída.
 *
 *  A foto e a sentença de scanner do cadastro estão na fila. O gestor abre
 *  a sentença — e o que se confere é que o NAVEGADOR conseguiu buscar o
 *  arquivo, com a sessão no cabeçalho: é a costura que nenhum teste de
 *  servidor exercita. Depois registra as duas leituras.
 */
async function faseConferencia(navegador, gritos, resultado) {
  const { contexto, p: g } = await abrirAba(navegador, gritos, "conferencia");
  try {
    await g.goto(`${cfg.web}/?entidade=${cfg.entidade}&tela=painel`,
                 { waitUntil: "networkidle" });
    await entrar(g, cfg.gestor.cpf, "Seu CPF",
                 "Código que chegou no seu e-mail");
    await g.getByRole("heading", { name: "Documentos para ler" })
      .waitFor({ timeout: 20000 });
    marco("o gestor vê a fila de leitura");

    const cartao = (rotulo) => g
      .locator("div")
      .filter({ hasText: rotulo })
      .filter({ has: g.getByRole("button", { name: "Abrir o documento" }) })
      .last();

    // ABRIR. O arquivo vem por `fetch` com Authorization — CORS, sessão e
    // tipo do conteúdo, de uma vez.
    const sentenca = cartao("Sentença, se você tiver");
    const [resposta] = await Promise.all([
      g.waitForResponse((r) => r.url().includes("/arquivo"), { timeout: 20000 }),
      sentenca.getByRole("button", { name: "Abrir o documento" }).click(),
    ]);
    const tipo = resposta.headers()["content-type"] || "";
    if (resposta.status() !== 200 || !tipo.startsWith("application/pdf")) {
      throw new Error(`o documento não abriu: ${resposta.status()} ${tipo}`);
    }
    resultado.conferencia = { abriu: true, registradas: 0 };
    marco("o gestor abriu a sentença de scanner");
    for (const aba of contexto.pages()) {
      if (aba !== g) await aba.close().catch(() => {});
    }

    await sentenca.getByRole("radio", { name: /^Procedente$/ }).check();
    await sentenca.getByRole("button", { name: "Registrar o que li" }).click();
    await g.getByText("Sentença, se você tiver").waitFor({ state: "detached", timeout: 20000 });
    resultado.conferencia.registradas += 1;
    marco("leitura da sentença registrada: procedente");

    const foto = cartao("Comprovantes de contribuição ao sindicato");
    await foto.getByLabel("O comprovante cobre de").fill("2022-01");
    await foto.getByLabel("até").fill("2022-12");
    await foto.getByRole("button", { name: "Registrar o que li" }).click();
    await g.getByRole("heading", { name: "Documentos para ler" })
      .waitFor({ state: "detached", timeout: 20000 });
    resultado.conferencia.registradas += 1;
    marco("leitura do comprovante fotografado registrada — a fila esvaziou");

    // O SINDICATO MANDA A LISTA. Uma planilha .xlsx de verdade, em duas
    // etapas: conferir, e só então gravar. A pessoa nova tem de aparecer
    // na lista sem recarregar a página.
    const entrada = g.getByLabel(/A planilha de filiados/);
    await entrada.setInputFiles(cfg.planilha.caminho);
    await g.getByRole("button", { name: "Conferir a planilha" }).click();
    await g.getByText("Confira antes de gravar.").waitFor({ timeout: 20000 });
    if ((await g.innerText("body")).includes(cfg.planilha.nome)) {
      throw new Error("a pessoa da planilha apareceu na base ANTES da confirmação");
    }
    await g.getByRole("button", { name: "Confirmar e gravar a planilha" }).click();
    await g.getByText(/Planilha gravada/).waitFor({ timeout: 20000 });
    await g.getByText(cfg.planilha.nome).first().waitFor({ timeout: 20000 });
    resultado.planilha = { gravou: true };
    marco("o gestor enviou a planilha .xlsx: conferiu, confirmou, e a base cresceu");

    // O QUE A PLANILHA MUDOU EM QUEM ENTRA, como o gestor LEU. A planilha
    // traz uma pessoa nova e uma que já entrava, com outro e-mail: a tela
    // tem de dizer que a primeira já pode entrar e que a troca da segunda
    // NÃO vale. Quem confere o texto é o Python, do lado de fora.
    await g.getByText("Quem consegue entrar no portal").waitFor({ timeout: 20000 });
    resultado.planilha.acesso = await g.innerText("body");

    // E A PESSOA NOVA ENTRA DE VERDADE. Outro navegador, sem nada do
    // gestor: alguém que só existe na planilha pede o código e passa pelo
    // portão. É isto que "a planilha liga o acesso" quer dizer — o resto é
    // contagem numa tela.
    const nova = await abrirAba(navegador, gritos, "nova pela planilha");
    try {
      await nova.p.goto(`${cfg.web}/?entidade=${cfg.entidade}`, { waitUntil: "networkidle" });
      await nova.p.getByRole("button", { name: /^Começar$/ }).click();
      await entrar(nova.p, cfg.planilha.cpf, "CPF", "Código recebido");
      await nova.p.getByText(/Acesso confirmado/).waitFor({ timeout: 15000 });
      resultado.planilha.novaEntrou = true;
      marco("quem veio só pela planilha entrou pelo portão");
    } finally {
      await nova.contexto.close();
      pagina = g;
    }

    // NOME POR NOME, e a planilha. O gestor vê a pessoa na lista — com o
    // CPF mascarado — e baixa a base. O que se confere do lado de fora é o
    // ARQUIVO que o navegador recebeu: é ele que o sindicato leva embora.
    await g.getByRole("heading", { name: "Nome por nome" }).waitFor({ timeout: 20000 });
    const lista = await g.innerText("body");
    resultado.lista = {
      viuNome: lista.includes(cfg.filiado.nome),
      cpfInteiroNaTela: lista.includes(cfg.filiado.cpf) ||
        lista.includes(cfg.filiado.cpf.replace(/\D/g, "")),
    };
    const [baixado] = await Promise.all([
      g.waitForEvent("download", { timeout: 20000 }),
      g.getByRole("button", { name: "Baixar a planilha da base" }).click(),
    ]);
    resultado.lista.planilha = await fs.readFile(await baixado.path(), "utf-8");
    resultado.lista.nomeDoArquivo = baixado.suggestedFilename();
    marco(`o gestor baixou ${resultado.lista.nomeDoArquivo}`);
  } finally {
    await contexto.close();
  }
}

/** O gestor apaga um filiado a pedido, pelo painel. */
async function fasePainel(navegador, gritos, resultado) {
  const { contexto: contextoDoGestor, p: g } =
    await abrirAba(navegador, gritos, "painel");
  {
      try {
        await g.goto(`${cfg.web}/?entidade=${cfg.entidade}&tela=painel`,
                     { waitUntil: "networkidle" });
        await entrar(g, cfg.gestor.cpf, "Seu CPF",
                     "Código que chegou no seu e-mail");
        await g.getByRole("button", { name: /Atender um pedido de apagamento/ })
          .waitFor({ timeout: 20000 });
        marco("o gestor entrou no painel");

        await g.getByRole("button", { name: /Atender um pedido de apagamento/ })
          .click();
        await g.getByLabel("CPF de quem pediu").fill(cfg.filiado.cpf);
        await g.getByLabel("Quem no sindicato está atendendo")
          .fill("gestor@exemplo.invalid");
        await g.getByLabel("Motivo (opcional)")
          .fill("pedido do titular, ensaio automatizado");
        await g.getByRole("button", { name: /Conferir e confirmar/ }).click();

        // A CONFIRMAÇÃO TEM DE DIZER QUE NÃO SE DESFAZ. É a única chance
        // que o gestor tem, e uma tela que a perdesse continuaria passando
        // em todos os testes de unidade.
        const aviso = await g.innerText("body");
        if (!/não se desfaz/i.test(aviso)) {
          throw new Error("a confirmação não avisa que o apagamento não se desfaz");
        }
        resultado.apagamento = { confirmacaoAvisa: true };
        marco("confirmação em duas etapas, avisando que não se desfaz");

        await g.getByRole("button", { name: /Apagar definitivamente/ }).click();
        await g.getByText(/nada sobrou|Ainda sobra/).waitFor({ timeout: 60000 });
        const dito = await g.innerText("body");
        resultado.apagamento.disse = /nada sobrou/.test(dito)
          ? "nada sobrou" : "ainda sobra";
        resultado.apagamento.tela = dito.slice(0, 600);
        marco(`o painel disse: ${resultado.apagamento.disse}`);
      } finally {
        await contextoDoGestor.close();
      }
  }
}

async function main() {
  const navegador = await chromium.launch();
  const gritos = [];
  const resultado = { passos, gritos, protocolo: "", apagamento: null };
  try {
    // UMA FASE POR CHAMADA, e a razão é a ordem da conferência. O
    // orquestrador confere o DISCO entre as duas: o cadastro grava, ele
    // confere o que chegou, e só então o painel apaga. Numa chamada só, a
    // conferência do cadastro rodaria depois do apagamento e encontraria
    // tudo vazio — foi o primeiro defeito que este ensaio pegou, e era meu.
    if (cfg.fase === "sede") {
      await faseSede(navegador, gritos, resultado);
    } else if (cfg.fase === "volta") {
      await faseVolta(navegador, gritos, resultado);
    } else if (cfg.fase === "cadastro") {
      await faseCadastro(navegador, gritos, resultado);
    } else if (cfg.fase === "conferencia") {
      await faseConferencia(navegador, gritos, resultado);
    } else if (cfg.fase === "painel") {
      await fasePainel(navegador, gritos, resultado);
    } else {
      throw new Error(`fase desconhecida: ${cfg.fase}`);
    }
  } catch (erro) {
    resultado.falha = await registrarFalha(erro);
  } finally {
    await navegador.close();
  }

  process.stdout.write(`\n<<<ENSAIO>>>${JSON.stringify(resultado)}<<<FIM>>>\n`);
  process.exit(resultado.falha ? 1 : 0);
}

main();
