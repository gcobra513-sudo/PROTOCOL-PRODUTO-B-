-- =====================================================================
-- A ORIGEM DO VEREDICTO: a assinatura DECLARADA e o digest MEDIDO.
--
-- PARA RODAR NUM BANCO QUE JÁ EXISTE. `esquema.sql` já traz a forma nova,
-- e `CREATE TABLE IF NOT EXISTS` NÃO altera tabela existente — então um
-- banco em produção ficaria com a forma velha e o erro só apareceria na
-- primeira escrita. É o que o cabeçalho de `banco.TABELAS` registra ter
-- acontecido antes com `documento` e `achado`.
--
-- POR QUE A MUDANÇA:
--
--   `catalogo_versao integer` saiu porque o INTEIRO é a hipótese de um
--   contrato só: um sindicato com duas carreiras tem DUAS versões de
--   catálogo, e o motor já devolvia "slug@2 outro@1" em
--   `Catalogo.assinatura`. A coluna não conseguia guardar o que o próprio
--   motor produzia.
--
--   `catalogo_digest` entra porque a assinatura é uma DECLARAÇÃO. Subir a
--   `versao` do TOML é disciplina de quem edita, e o comentário da própria
--   `versao` registra o dia em que a disciplina falhou: "ninguém conferia,
--   e nada casava". Veredicto guardado citando uma versão que o conteúdo
--   não tem é prova FALSA — pior que prova nenhuma, porque ninguém
--   desconfia dela.
--
--   A ASSINATURA ENTRA NA CHAVE PRIMÁRIA: reavaliar sob catálogo novo
--   INSERE em vez de sobrescrever. Tem de ser assim porque o veredicto
--   antigo NÃO é recalculável — o catálogo que o produziu pode já ter sido
--   editado em disco. É o mesmo argumento do diário append-only.
--
-- SEGURO PORQUE A TABELA ESTÁ VAZIA. Medido em 02/11/2026: 0 linhas no
-- banco de São Paulo e 0 no de teste. Ninguém escrevia nela — era a
-- segunda metade do T11. Num banco COM linhas, isto perderia a versão
-- antiga: ali a migração seria outra, preenchendo `catalogo_assinatura`
-- a partir de `catalogo_versao` antes de dropar.
-- =====================================================================
BEGIN;

ALTER TABLE oportunidade DROP COLUMN IF EXISTS catalogo_versao;

ALTER TABLE oportunidade
    ADD COLUMN IF NOT EXISTS catalogo_assinatura text NOT NULL DEFAULT '';
ALTER TABLE oportunidade
    ADD COLUMN IF NOT EXISTS catalogo_digest text NOT NULL DEFAULT '';

ALTER TABLE oportunidade DROP CONSTRAINT IF EXISTS oportunidade_pkey;
ALTER TABLE oportunidade
    ADD PRIMARY KEY (entidade, cpf, trilha, referencia, catalogo_assinatura);

-- O DEFAULT DA ASSINATURA SAI. Gravar veredicto sem dizer de onde saiu é
-- exatamente o que esta migração existe para impedir, e um default vazio
-- deixaria a omissão passar em silêncio. O do digest fica, porque linha
-- antiga pode não ter sido medida — e hoje não há linha antiga.
ALTER TABLE oportunidade ALTER COLUMN catalogo_assinatura DROP DEFAULT;

COMMIT;
