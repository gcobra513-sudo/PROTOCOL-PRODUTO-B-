# Plano — `oportunidade` persistida

Spec: `docs/superpowers/specs/2026-11-02-oportunidade-persistida-design.md`

Cada tarefa: teste primeiro, ver falhar pelo motivo certo, implementar,
suíte inteira. Verificar cada guarda nova com MUTANTE — foi o que achou dois
testes meus que não testavam nada na entrega anterior.

| # | Tarefa | Teste que prova |
|---|---|---|
| 1 | Migração do esquema | a chave primária inclui a assinatura; `catalogo_versao` não existe mais |
| 2 | `Catalogo.digest` medido | editar um byte do TOML muda o digest; a assinatura declarada não muda |
| 3 | `banco.registrar_oportunidades` | grava; é idempotente; RECUSA conteúdo mudado com assinatura igual |
| 4 | `oportunidades_de` e `mudancas` | a transição entre duas assinaturas aparece; não atravessa entidade |
| 5 | `ferramentas/reavaliar_oportunidades.py` | reavalia a base, não imprime CPF, sai 1 quando recusa |
| 6 | tarefa `reavaliar` no agendador | entra em `TAREFAS`, roda a ferramenta, respeita `atendivel` |
| 7 | o painel mostra o que mudou | a contagem e a lista chegam no JSON e na tela |

## Travas que não se quebram nesta entrega

- **nada nominal sai sem homologação humana** — nenhuma rota nova manda
  e-mail;
- **um sindicato nunca vê o dado de outro** — toda tabela nova entra na
  política de RLS, e há teste de travessia;
- **a dúvida nunca vira permissão** — conteúdo mudado sem versão nova é
  RECUSA, não aviso;
- **nunca afirmar o que não dá para justificar** — a linha guardada diz de
  qual catálogo saiu, medido e declarado.
