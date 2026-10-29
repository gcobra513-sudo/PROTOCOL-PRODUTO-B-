# Produto B — A base viva do sindicato

> Separado do Produto A em 28/10/2026. O A é o peticionamento em massa, para o
> escritório. Este é o produto para sindicatos e cooperativas.
>
> Reescrito em 29/10/2026. A versão anterior punha a OAB dos escritórios
> parceiros como fonte principal da base e tratava a organização dos dados
> como pré-requisito chato do diferencial. As duas coisas estavam erradas, e o
> histórico do git guarda a versão antiga.

---

## 1. O que é

Um webapp com **dois lados da mesma base**, e a base nasce da organização de
um acervo que hoje está jogado.

**A base se enche por duas bocas:**

1. **O que o sindicato já tem.** Exportação de folha, planilha de secretaria,
   sistema antigo, lista que ninguém atualizou desde 2014. Chega como estiver.
   Nós normalizamos, conferimos e dizemos o que falta — **nominalmente**.
2. **O que o filiado entrega.** Ele entra na plataforma — convocado pelo
   sindicato ou porque acabou de se filiar — completa o que falta, manda os
   documentos que tem e informa os processos de que já participa.

**E ela devolve para os dois lados:**

- **Para o filiado:** a área dele. Vê o que consta a seu respeito, completa o
  que falta, informa o número do processo e **acompanha a movimentação**.
- **Para o gerente do sindicato:** um painel que se atualiza sozinho.

**O diferencial aparece para os dois.** Cruzando o que a base diz de cada
pessoa com os entendimentos firmados nos tribunais superiores, a plataforma
indica o que aquela pessoa pode fazer: **ajuizar** ação nova, quando não há
título; **executar**, quando já existe processo com sentença.

Numa frase: *o sindicato entrega um acervo bagunçado e recebe de volta uma
base viva, que diz nome por nome quem pode fazer o quê e o que andou.*

---

## 2. A ordem das entregas, e por que ela é esta

| Entrega | Depende de resposta do jurídico? |
|---|---|
| 1. Organização do acervo | **não** |
| 2. Painel de completude para o gerente | **não** |
| 3. Área do filiado + acompanhamento por número | **não** |
| 4. Indicação de direito (ajuizar / executar) | **sim, e está bloqueada** |

A organização é a primeira entrega **porque é a única que não depende de
ninguém** e porque é ela que vende. O primeiro número que o gerente vê não é
"quem tem direito" — é o estado da base dele:

> *"Você tem 4.812 filiados cadastrados. Não consegue falar com 1.930 deles."*

Isso é medível no primeiro dia, a partir do arquivo que ele mesmo mandou, e é
informação que ele não tem hoje.

A entrega 4 usa o mesmo painel, com uma coluna a mais. Ela está bloqueada em
**conteúdo, não em código**: o motor de elegibilidade já existe
(`src/sindilote/elegibilidade.py`, oito perguntas, dúvida nunca resolvendo a
favor) e o catálogo de títulos já tem formato
(`config/titulos.MODELO.toml`). Falta o que só o jurídico fornece:

- **os entendimentos, por número** — tema repetitivo ou recurso;
- **os critérios objetivos** de enquadramento: cargo, período, situação
  funcional, data de aposentadoria, rol de substituídos.

Sem esses dois o motor roda e devolve `INDETERMINADO` para todo mundo. É o
comportamento certo e vale zero de produto. **Nenhuma linha de código resolve
isso.**

---

## 3. O que a aquisição de dados permite, medido

Não existe fonte pública que devolva os processos de uma pessoa a partir do
CPF ou do nome. Conferido por requisição em 29/10/2026:

| Fonte | Chave que aceita | Veredito |
|---|---|---|
| DataJud (CNJ) | nº do processo, classe, órgão | **não busca por CPF nem nome** |
| PJe automatizado | — | reservado ao MNI, art. 29 §3º Res. CNJ 185/2013 |
| Consulta pública do tribunal | nome/CPF em alguns | captcha; vários removeram a busca por nome |
| DJEN / Comunica | OAB + UF, nº do processo | a chave é a OAB, e recusa requisição de fora do Brasil |
| Agregador comercial (Escavador, Judit, Jusbrasil) | **CPF** | existe, é pago, e a cobertura é parcial |

**Decisão:** o MVP não compra agregador. O CPF é chave de busca **dentro da
base que montamos**, e a base se enche pelo número que o próprio filiado
informa e pelos processos que nós protocolamos.

O caminho da OAB dos escritórios parceiros está **fora de escopo** — ele
dependia de contrato e de máquina no Brasil, e o que ele acrescentava era o
texto da intimação, não a movimentação.

### O que o DataJud entrega (`docs/achados_datajud.md`)

- **65 tribunais**, e o alias sai do próprio número CNJ. Acompanhar não é
  privilégio do TRF1;
- **o STF não está lá.** STJ está. Isso limita o que a entrega 4 pode
  prometer;
- **22 a 43 s por consulta**, defasagem de ~1 dia. A tela não consulta ao
  vivo: quem consulta é o coletor, em segundo plano;
- **não tem parte, não tem peça.** O vínculo CPF↔processo é sempre nosso.

---

## 4. Regras de desenho que não são negociáveis

**O e-mail do portão vem do sindicato, nunca de quem digita.** O filiado pode
**propor** correção; quem **homologa** é o sindicato. Se o filiado pudesse
trocar o próprio e-mail, o código de acesso viraria enfeite — ver `rol.py`.

**Divergência não se resolve sozinha.** Quando o acervo do sindicato e o
cadastro do filiado discordam num campo, o campo fica marcado como divergente
e aparece para o gerente decidir. É a mesma postura de
`elegibilidade.achado_de_repeticao`: a ordem na planilha não decide.

**Quem fala com o filiado é o sindicato, não o escritório.** O Provimento
205/2021 do CFOAB define captação de clientela como angariar clientes por
indução à contratação ou **estímulo ao litígio** (vedada pelo art. 34, IV do
Estatuto e art. 7º do Código de Ética). Avisar dez mil pessoas que elas podem
processar a União, com a marca de um escritório, é a figura que a norma
descreve. Informar o próprio filiado é atividade institucional do sindicato,
que tem legitimidade constitucional para defender direitos individuais da
categoria (CF, art. 8º, III). **Consequência: a plataforma usa a identidade da
entidade, não a do escritório.** Isso é conformidade, não estética.

**A máquina prepara; quem assina é gente.** A tela do filiado nunca diz "você
tem direito a executar". Diz que o caso parece se enquadrar, e que o sindicato
vai conferir. Nada nominal sai sem homologação humana — a mesma trava que
`titulos.toml` tem com `revisado = "S"`.

**Atualização é diária, não em tempo real.** O painel está atualizado com o
que os tribunais publicaram ontem, e se atualiza sozinho. Prometer tempo real
é prometer o que o DataJud não dá.

**Nunca publicar dado pessoal real.** Em demonstração, só cadastro
declaradamente fictício. Nome plausível com CPF de dígito válido numa página
pública passa a parecer pessoa real.

**Nunca pedir credencial, senha ou certificado a ninguém.** O portão é código
de 6 dígitos no e-mail do rol. Sem senha, por desenho.

---

## 5. Onde isso roda

A LGPD não exige armazenamento no Brasil, e não existe certificação de
datacenter a contratar. O que existe: **nuvem estrangeira é transferência
internacional**, e desde 23/08/2025 ela só é válida com as cláusulas-padrão da
ANPD (Res. CD/ANPD 19/2024).

A Render, onde a demonstração está hoje, **não tem região na América do Sul**
(Oregon, Ohio, Virginia, Frankfurt, Singapura). Para cadastro fictício é
indiferente; para sindicato real, não serve.

**Destino:** Postgres gerenciado em São Paulo (`sa-east-1`) e aplicação em
região brasileira.

**A trava:** o servidor recusa atender entidade que não seja `demo-` enquanto
o deploy não declarar região brasileira. É trava de código, não de
procedimento — procedimento se esquece. Mesmo desenho do `PREFIXO_DEMO` que
já existe em `servidor/app.py`.

**Dado sensível por construção:** constar do rol de um sindicato *é* filiação
sindical (LGPD, art. 11). Consequência não é hospedagem diferente — é
cifragem, retenção curta, isolamento entre entidades e **log de leitura**: num
produto de consulta o vazamento é um *read*, não um *write*.

---

## 6. O que já existe

| Parte | Estado |
|---|---|
| Portal do filiado (`portal/`) | funciona: sete etapas, confere documento no aparelho |
| Servidor de recebimento (`servidor/`) | funciona: valida, limita, grava diário append-only |
| Isolamento entre entidades (`servidor/entidades.py`) | funciona: contenção de caminho |
| Acompanhamento por número (DataJud) | a chave está integrada e conferida; o coletor não existe |
| Ingestão do acervo do sindicato | **não existe** |
| Painel de completude | **não existe** |
| Indicação de direito | **não existe, e está bloqueada no jurídico** |

---

## 7. O que falta decidir

1. **Os entendimentos, por número** — STJ, STF ou os dois. Medido: o STF não
   está no DataJud, e se for necessário é uma fonte a levantar.
2. **Os critérios objetivos de enquadramento.** Pergunta 5 de
   `PERGUNTAS_JURIDICO.md`, aberta desde antes da separação dos produtos.
3. **Uma exportação real de sindicato**, ainda que descaracterizada. Sem ver
   um arquivo de verdade, a ingestão é chute: formato, encoding, colunas e
   sujeira saem dele, não da nossa imaginação.
4. **Base legal LGPD por tratamento**, em três perguntas e não numa genérica:
   dado do filiado mostrado a ele; o sindicato vendo a própria base; o
   cruzamento contra teses — este último provavelmente em art. 11, onde
   legítimo interesse não está disponível.
5. **Modelo de cobrança.** Muda o que o pitch enfatiza.

6. **Retenção e apagamento do acervo.** `acervo.jsonl` é append-only e guarda
   uma CÓPIA INTEIRA da base a cada ingestão — nome, CPF, e-mail, endereço,
   cargo — de milhares de pessoas que nunca usaram o portal e nunca declararam
   nada. Filiação sindical é dado sensível, e um pedido de eliminação (LGPD,
   art. 18, VI) não se atende sem quebrar a propriedade append-only do
   arquivo. Cada reexportação multiplica as cópias.

   **Isto precisa de posição declarada antes da primeira ingestão real:**
   prazo de retenção, procedimento de reescrita, ou registro de tombstone.
   Hoje não há nenhuma das três, e o diário de cadastro não tem o mesmo
   problema porque só guarda quem entregou os próprios dados.
