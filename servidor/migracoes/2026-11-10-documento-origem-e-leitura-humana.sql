-- =====================================================================
-- `documento` ganha duas colunas: de onde veio, e a leitura por uma pessoa.
--
-- PARA RODAR NUM BANCO QUE JÁ EXISTE (`CREATE TABLE IF NOT EXISTS` não
-- altera tabela existente).
--
--   origem          'cadastro' ou 'sindicato'. O reenvio de um filiado
--                   substitui o que ELE tinha mandado, e só isso.
--   leitura_humana  '' | 'lido' | 'ilegivel', para o documento que a
--                   máquina não lê.
--
-- O DEFAULT DE `origem` É 'cadastro', e para linha antiga isso pode estar
-- errado: o que veio de `ingerir_documentos.py` devia ser 'sindicato'. Não
-- há SQL que saiba a diferença. Depois desta migração, RODE DE NOVO a
-- ingestão dos documentos do sindicato — ela regrava a origem certa — ANTES
-- de qualquer reenvio de filiado, senão o reenvio apaga o que o sindicato
-- entregou. Está na tabela de reprojeções do LEIA.md.
-- =====================================================================
BEGIN;

ALTER TABLE documento
    ADD COLUMN IF NOT EXISTS origem text NOT NULL DEFAULT 'cadastro';
ALTER TABLE documento
    ADD COLUMN IF NOT EXISTS leitura_humana text NOT NULL DEFAULT '';

ALTER TABLE documento DROP CONSTRAINT IF EXISTS documento_origem_check;
ALTER TABLE documento
    ADD CONSTRAINT documento_origem_check
    CHECK (origem IN ('cadastro', 'sindicato'));
ALTER TABLE documento DROP CONSTRAINT IF EXISTS documento_leitura_humana_check;
ALTER TABLE documento
    ADD CONSTRAINT documento_leitura_humana_check
    CHECK (leitura_humana IN ('', 'lido', 'ilegivel'));

COMMIT;
