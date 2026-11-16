-- =====================================================================
-- O esquema endurecido (auditoria de segurança de 31/10/2026, itens de
-- banco h4-2 a h4-8).
--
-- PARA RODAR NUM BANCO QUE JÁ EXISTE (`CREATE TABLE IF NOT EXISTS` não
-- altera tabela existente). São DUAS etapas, nesta ordem:
--
--   1. este arquivo — as três mudanças de FORMA:
--      - `recebimento` ganha UNIQUE (entidade, id);
--      - a chave estrangeira de `pessoa_afirmacao` passa a levar a entidade
--        junto, para uma linha de um sindicato não poder apontar para o
--        recebimento de outro;
--      - o mesmo recebimento (entidade + impressão digital) não entra duas
--        vezes.
--   2. reaplicar `esquema.sql` — as políticas (que passam a usar NULLIF) e
--      as permissões (a sequência deixa de ser legível) são refeitas por
--      ele a cada aplicação, e não são repetidas aqui para não haver duas
--      cópias.
--
-- ANTES, CONFIRA QUE NÃO HÁ REPETIÇÃO — com repetição o índice único não
-- nasce, e a migração inteira é desfeita (está numa transação):
--
--   SELECT entidade, sha256, count(*) FROM recebimento
--    WHERE sha256 <> '' GROUP BY 1, 2 HAVING count(*) > 1;
--
-- Tem de vir vazio. Se não vier, a base tem recebimento duplicado, e isso
-- se resolve olhando — não apagando por SQL.
-- =====================================================================
BEGIN;

ALTER TABLE recebimento
    DROP CONSTRAINT IF EXISTS recebimento_entidade_id_unico;
ALTER TABLE recebimento
    ADD CONSTRAINT recebimento_entidade_id_unico UNIQUE (entidade, id);

-- O nome antigo é o que o Postgres deu sozinho à chave escrita na coluna.
ALTER TABLE pessoa_afirmacao
    DROP CONSTRAINT IF EXISTS pessoa_afirmacao_recebimento_id_fkey;
ALTER TABLE pessoa_afirmacao
    DROP CONSTRAINT IF EXISTS pessoa_afirmacao_recebimento_fk;
ALTER TABLE pessoa_afirmacao
    ADD CONSTRAINT pessoa_afirmacao_recebimento_fk
    FOREIGN KEY (entidade, recebimento_id)
    REFERENCES recebimento (entidade, id)
    ON DELETE SET NULL (recebimento_id);

CREATE UNIQUE INDEX IF NOT EXISTS recebimento_sem_repetir
    ON recebimento (entidade, sha256) WHERE sha256 <> '';

COMMIT;
