-- A FORMA DO BANCO, numa impressão digital: colunas, padrões, chaves,
-- restrições e o isolamento por linha (ligado e forçado) de cada tabela.
--
-- Rode no banco de produção e num banco recém-criado por
-- `banco.criar_esquema`. Impressões iguais: a produção tem a forma que o
-- código espera. Diferentes: falta migração — ou sobra coluna.
SELECT md5(string_agg(linha, E'\n' ORDER BY linha)) AS impressao, count(*) AS linhas FROM (
  SELECT 'col|' || table_name || '|' || column_name || '|' || data_type || '|' || is_nullable || '|' || coalesce(column_default, '') AS linha
    FROM information_schema.columns WHERE table_schema = 'public'
  UNION ALL
  SELECT 'con|' || rel.relname::text || '|' || con.conname::text || '|' || con.contype::text || '|' || pg_get_constraintdef(con.oid)
    FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid
   WHERE rel.relnamespace = 'public'::regnamespace
  UNION ALL
  SELECT 'rls|' || relname::text || '|' || relrowsecurity::text || '|' || relforcerowsecurity::text
    FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'
) t;
