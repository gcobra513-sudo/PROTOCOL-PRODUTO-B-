-- AS POLÍTICAS DE ISOLAMENTO e as permissões do papel `protocol_app`, numa
-- impressão digital. Mesma regra de `conferir_forma.sql`: tem de dar igual
-- na produção e num banco recém-criado.
SELECT md5(string_agg(linha, E'\n' ORDER BY linha)) AS impressao, count(*) AS linhas,
       count(*) FILTER (WHERE linha LIKE 'pol|%') AS politicas,
       count(*) FILTER (WHERE linha LIKE 'per|%') AS permissoes FROM (
  SELECT 'pol|' || tablename || '|' || policyname || '|' || cmd || '|' || array_to_string(roles, ',') || '|' || coalesce(qual, '') || '|' || coalesce(with_check, '') AS linha
    FROM pg_policies WHERE schemaname = 'public'
  UNION ALL
  SELECT 'per|' || table_name || '|' || privilege_type
    FROM information_schema.role_table_grants
   WHERE table_schema = 'public' AND grantee = 'protocol_app'
) t;
