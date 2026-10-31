-- =====================================================================
-- O ESQUEMA. Três camadas, e o isolamento imposto pelo banco.
--
-- Ver BANCO.md para o desenho inteiro. O essencial:
--
--   CAMADA 1  recebimento      o que chegou, como chegou. Não se edita.
--   CAMADA 2  pessoa_afirmacao toda afirmação, com procedência
--             pessoa           o valor vigente, derivado
--   CAMADA 3  processo, vinculo, movimento, oportunidade
--
-- TODA TABELA TEM `entidade` E TODA TABELA TEM POLÍTICA. Não porque o
-- servidor não filtre, mas porque o erro provável num produto
-- multi-entidade é um WHERE esquecido numa tela escrita daqui a seis meses
-- por outra pessoa. Consulta sem filtro devolve ZERO linhas, não as linhas
-- do sindicato vizinho.
--
-- FORCE, não só ENABLE: sem o FORCE o DONO da tabela ignora a política.
-- =====================================================================

-- O PAPEL DA APLICAÇÃO, e ele existe por um motivo que custou um teste
-- vermelho para aparecer: **superusuário ignora RLS por completo**,
-- inclusive com FORCE. E a URL que a Supabase entrega por padrão conecta
-- como `postgres`, que é privilegiado. Quem rodasse as migrações e a
-- aplicação com a mesma URL teria políticas perfeitas e proteção nenhuma.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'protocol_app') THEN
        CREATE ROLE protocol_app NOLOGIN NOBYPASSRLS;
    END IF;
END $$;


-- ---------------------------------------------------------------------
-- CAMADA 1 — RECEBIMENTO
--
-- Uma linha por coisa que chegou. Quando o cadastro de alguém sair errado,
-- a pergunta é "o que exatamente nos mandaram?" — e sem esta camada a
-- resposta é "não sei, já tratamos".
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recebimento (
    id          bigserial PRIMARY KEY,
    entidade    text NOT NULL,
    tipo        text NOT NULL CHECK (tipo IN ('acervo', 'cadastro')),
    recebido_em timestamptz NOT NULL DEFAULT now(),
    origem      text NOT NULL DEFAULT '',
    payload     jsonb NOT NULL,
    -- Impressão digital do que chegou, para provar que não mudou.
    sha256      text NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS recebimento_por_entidade
    ON recebimento (entidade, recebido_em DESC);


-- ---------------------------------------------------------------------
-- CAMADA 2 — FATOS, COM PROCEDÊNCIA
--
-- A decisão de desenho que mais importa, e ela vem de uma regra do produto:
-- quando o sindicato e o filiado discordam, NINGUÉM DECIDE SOZINHO.
--
-- Isso é impossível numa tabela larga: gravar o segundo valor apaga o
-- primeiro, e a divergência some junto. Por isso são duas tabelas — uma que
-- guarda toda afirmação já feita, e outra com o valor vigente.
-- ---------------------------------------------------------------------
-- A CHAVE É O RECEBIMENTO, NÃO O RELÓGIO. Era
-- `(entidade, cpf, campo, fonte, afirmado_em)`, e dois envios da mesma pessoa
-- no mesmo segundo colidiam: o segundo era descartado em silêncio, e com ele
-- ia embora a afirmação que fazia a divergência existir. Um envio é um
-- recebimento; é ele que distingue.
CREATE TABLE IF NOT EXISTS pessoa_afirmacao (
    id             bigserial PRIMARY KEY,
    entidade       text NOT NULL,
    cpf            text NOT NULL,
    campo          text NOT NULL,
    valor          text NOT NULL DEFAULT '',
    fonte          text NOT NULL CHECK (fonte IN ('acervo', 'cadastro')),
    recebimento_id bigint REFERENCES recebimento (id) ON DELETE SET NULL,
    afirmado_em    timestamptz NOT NULL DEFAULT now(),
    -- NULLS NOT DISTINCT para que a afirmação sem recebimento também não
    -- duplique: com o padrão do SQL, NULL nunca colide com NULL e a
    -- reprojeção criaria uma linha nova a cada execução.
    UNIQUE NULLS NOT DISTINCT (entidade, cpf, campo, fonte, recebimento_id)
);

CREATE TABLE IF NOT EXISTS pessoa (
    entidade        text NOT NULL,
    cpf             text NOT NULL,
    nome            text NOT NULL DEFAULT '',
    email           text NOT NULL DEFAULT '',
    cargo           text NOT NULL DEFAULT '',
    situacao        text NOT NULL DEFAULT '',
    data_nascimento text NOT NULL DEFAULT '',
    -- Alcançável = CPF que fecha E e-mail que serve. É a manchete do painel,
    -- e por isso é coluna e não conta feita na hora.
    alcancavel      boolean NOT NULL DEFAULT false,
    -- Verdadeiro quando acervo e cadastro discordam em algum campo. O valor
    -- vigente continua sendo o do ACERVO até o sindicato homologar: a ordem
    -- de chegada não decide qual versão da verdade entra na base.
    tem_divergencia boolean NOT NULL DEFAULT false,
    atualizado_em   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entidade, cpf)
);


-- O DOCUMENTO e o que se leu dele.
--
-- `documento` guarda o METADADO, nunca os bytes: o PDF fica no disco ou no
-- object storage, e o banco guarda a impressão digital. Pôr PDF em coluna
-- faz o banco inchar, o backup demorar e a consulta arrastar — e nenhuma
-- dessas três coisas melhora o produto.
CREATE TABLE IF NOT EXISTS documento (
    entidade    text NOT NULL,
    cpf         text NOT NULL,
    tipo        text NOT NULL,         -- sentenca, certidao_transito, fichas...
    sha256      text NOT NULL,
    paginas     integer NOT NULL DEFAULT 0,
    caracteres  integer NOT NULL DEFAULT 0,
    tem_texto   boolean NOT NULL DEFAULT false,
    recebido_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entidade, cpf, tipo, sha256)
);

-- CADA ACHADO GUARDA O TRECHO DE ONDE SAIU, e essa coluna é a razão de o
-- produto poder afirmar o que afirma: um humano confere a extração lendo uma
-- linha, sem abrir o PDF. Extração sem trecho é palpite com cara de dado.
CREATE TABLE IF NOT EXISTS achado (
    entidade    text NOT NULL,
    cpf         text NOT NULL,
    documento   text NOT NULL,         -- o sha256 do documento de origem
    tipo        text NOT NULL,         -- numero_processo, transito_em_julgado...
    valor       text NOT NULL,
    confianca   text NOT NULL CHECK (confianca IN ('CERTO','PROVAVEL','SUSPEITO')),
    trecho      text NOT NULL,
    posicao     integer NOT NULL DEFAULT 0,
    metodo      text NOT NULL DEFAULT '',
    -- Humano conferiu? Só o CERTO dispensa; PROVAVEL e SUSPEITO esperam aqui.
    conferido   boolean NOT NULL DEFAULT false,
    extraido_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entidade, cpf, documento, tipo, valor, posicao)
);
CREATE INDEX IF NOT EXISTS achado_a_conferir
    ON achado (entidade, conferido) WHERE NOT conferido;


-- ---------------------------------------------------------------------
-- CAMADA 3 — CONSULTA
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processo (
    entidade text NOT NULL,
    numero   text NOT NULL,
    tribunal text NOT NULL DEFAULT '',
    PRIMARY KEY (entidade, numero)
);

CREATE TABLE IF NOT EXISTS vinculo (
    entidade text NOT NULL,
    cpf      text NOT NULL,
    numero   text NOT NULL,
    fonte    text NOT NULL DEFAULT 'declarado',
    PRIMARY KEY (entidade, cpf, numero)
);

CREATE TABLE IF NOT EXISTS movimento (
    entidade text NOT NULL,
    numero   text NOT NULL,
    grau     text NOT NULL,
    data     text NOT NULL,
    nome     text NOT NULL,
    visto_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entidade, numero, grau, data, nome)
);

-- O TRABALHO DE FUNDO: quando rodou, como foi, e quem está rodando agora.
--
-- Existe por uma razão só, e não é organização: **agendador que morre calado
-- é pior que agendador nenhum**. Sem este registro, o produto continua
-- prometendo aviso na tela de cadastro, a pessoa continua marcando o opt-in,
-- e ninguém recebe nada — até o primeiro telefonema perguntando por uma
-- sentença de três meses atrás.
--
-- `arrendado_ate` é a trava entre instâncias. De BANCO e não de memória:
-- duas instâncias do servidor não compartilham memória, e é justamente com
-- duas que o problema aparece. E ela EXPIRA, para que um processo morto no
-- meio não trave o trabalho para sempre.
CREATE TABLE IF NOT EXISTS execucao (
    entidade      text NOT NULL,
    tarefa        text NOT NULL,
    arrendado_ate timestamptz,
    -- A ÚLTIMA BOA é coluna própria, e não a última linha: contar a
    -- tentativa como sucesso faria o painel dizer "rodou hoje" enquanto
    -- ninguém é avisado há semanas.
    ultima_boa    timestamptz,
    ultima_em     timestamptz,
    ultima_ok     boolean,
    ultimo_detalhe text NOT NULL DEFAULT '',
    PRIMARY KEY (entidade, tarefa)
);


-- O QUE JÁ FOI AVISADO A CADA PESSOA.
--
-- Por PESSOA e não por processo: numa ação coletiva o mesmo processo alcança
-- milhares, e cada uma tem o seu estado — quem se cadastrou ontem não pode
-- receber o histórico de 2006 porque alguém já foi avisado dele.
--
-- A chave primária é o que impede o aviso repetido, e ela é a defesa de
-- verdade: o trabalho roda todo dia, e avisar duas vezes o mesmo andamento
-- faz a pessoa desligar o aviso — e aí ela volta a ligar.
CREATE TABLE IF NOT EXISTS aviso_enviado (
    entidade   text NOT NULL,
    cpf        text NOT NULL,
    -- numero|grau|data|nome: o DataJud não dá identificador estável.
    chave      text NOT NULL,
    -- `enviado`: a pessoa recebeu e-mail sobre este andamento.
    -- `estreia`: NÃO recebeu, e não vai receber — é histórico de um processo
    --            visto pela primeira vez. Marcar a estreia como "enviado"
    --            seria mentir no log de um aviso que nunca saiu, e é
    --            justamente neste log que alguém vai procurar quando a
    --            pessoa disser "não fui avisada".
    motivo     text NOT NULL DEFAULT 'enviado'
               CHECK (motivo IN ('enviado', 'estreia')),
    enviado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entidade, cpf, chave)
);


-- O VEREDICTO DO MOTOR, e `catalogo_versao` é o que torna o produto
-- auditável: quando o STJ julgar o Tema 1.302, a gente reavalia e quem
-- estava FALTA vira PODE — com a prova de por que mudou. Sem este campo, o
-- veredicto de ontem é inexplicável hoje.
CREATE TABLE IF NOT EXISTS oportunidade (
    entidade        text NOT NULL,
    cpf             text NOT NULL,
    trilha          text NOT NULL CHECK (trilha IN ('executar', 'ajuizar')),
    referencia      text NOT NULL,
    veredicto       text NOT NULL CHECK (veredicto IN ('PODE', 'NAO_PODE', 'FALTA')),
    motivos         jsonb NOT NULL DEFAULT '[]'::jsonb,
    falta           jsonb NOT NULL DEFAULT '[]'::jsonb,
    catalogo_versao integer NOT NULL,
    avaliado_em     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entidade, cpf, trilha, referencia)
);


-- ---------------------------------------------------------------------
-- AUDITORIA E APAGAMENTO
-- ---------------------------------------------------------------------

-- Num produto de CONSULTA o vazamento é um `read`, não um `write`. Sem este
-- registro, "quem viu o dado de quem" é uma pergunta sem resposta — e é a
-- primeira que alguém faz depois de um incidente.
--
-- ESCRITA desde o checkpoint 9: `/api/minhas-acoes` e o painel do sindicato
-- registram cada leitura, com MARCADOR e nunca com o CPF em claro — um log
-- de auditoria cheio de CPF é um segundo banco de dado pessoal, com retenção
-- mais longa e menos cuidado que o primeiro.
--
-- E é por causa desta tabela que entidade REAL não é atendida sem banco: sem
-- onde registrar, "quem viu o dado de quem" volta a ser pergunta sem
-- resposta. A trava está em `app._entidade`.
--
-- SEM DELETE para a aplicação (ver os GRANTs abaixo): log que o próprio
-- sistema apaga não é log de auditoria.
CREATE TABLE IF NOT EXISTS leitura (
    entidade  text NOT NULL,
    quando    timestamptz NOT NULL DEFAULT now(),
    quem_hash text NOT NULL,
    o_que     text NOT NULL,
    alvo_hash text NOT NULL DEFAULT ''
);

-- O APAGAMENTO, e ele resolve um conflito real: filiação sindical é dado
-- sensível (LGPD art. 11) e a eliminação (art. 18, VI) tem de ser atendida —
-- mas a camada 1 é append-only.
--
-- A saída: apagar é permitido, e deixa um TOMBSTONE — quem foi apagado,
-- quando, a pedido de quem — sem o dado. O log deixa de ser imutável e passa
-- a ser AUDITÁVEL, que é o que a lei pede. "Append-only" passa a significar
-- "não se edita", não "não se apaga nunca".
CREATE TABLE IF NOT EXISTS tombstone (
    entidade   text NOT NULL,
    cpf_hash   text NOT NULL,
    apagado_em timestamptz NOT NULL DEFAULT now(),
    motivo     text NOT NULL DEFAULT '',
    pedido_por text NOT NULL DEFAULT '',
    PRIMARY KEY (entidade, cpf_hash, apagado_em)
);


-- =====================================================================
-- AS POLÍTICAS
-- =====================================================================
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'recebimento', 'pessoa_afirmacao', 'pessoa', 'documento', 'achado',
        'processo', 'vinculo', 'movimento', 'oportunidade', 'leitura',
        'aviso_enviado', 'execucao', 'tombstone'
    ]
    LOOP
        -- O log de leitura e o tombstone são só INSERT e SELECT: a aplicação
        -- não reescreve a própria auditoria. As demais são derivadas do
        -- recebimento e podem ser reconstruídas.
        -- REVOKE ANTES DO GRANT, sempre. Uma tabela que já existia de uma
        -- versão anterior do esquema manteria as permissões antigas, e o
        -- endurecimento não teria efeito nenhum — a auditoria continuaria
        -- reescrevível e ninguém perceberia.
        EXECUTE format('REVOKE ALL ON %I FROM protocol_app', t);

        IF t IN ('leitura', 'tombstone') THEN
            EXECUTE format('GRANT SELECT, INSERT ON %I TO protocol_app', t);
        ELSE
            EXECUTE format(
                'GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO protocol_app', t
            );
        END IF;

        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS por_entidade ON %I', t);
        -- USING filtra a LEITURA; WITH CHECK impede escrever linha marcada
        -- com outra entidade. Sem o WITH CHECK o vazamento seria para dentro.
        EXECUTE format(
            'CREATE POLICY por_entidade ON %I '
            'USING (entidade = current_setting(''app.entidade'', true)) '
            'WITH CHECK (entidade = current_setting(''app.entidade'', true))',
            t
        );
    END LOOP;

    -- TODA sequência do esquema precisa ser usável pelo papel, não só a do
    -- recebimento. A linha nomeava uma sequência só; quando `pessoa_afirmacao`
    -- ganhou chave serial, o INSERT passou a falhar com "permission denied
    -- for sequence" — erro que só aparece na primeira escrita, e que num
    -- esquema aplicado pelo superusuário ninguém vê até a aplicação rodar com
    -- o papel certo. Varrer o schema não esquece a próxima.
    FOR t IN
        SELECT sequencename FROM pg_sequences WHERE schemaname = 'public'
    LOOP
        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %I TO protocol_app', t);
    END LOOP;
END $$;
