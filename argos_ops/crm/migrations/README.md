# Migrations CRM Argos Ops

Migrations SQL versionnées, appliquées dans l'ordre lexicographique. Chaque
migration est une transaction (`BEGIN; ... COMMIT;`) idempotente
(`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).

## Appliquer en local

```bash
psql "$DATABASE_URL" -f argos_ops/crm/migrations/0001_init.sql
```

## Appliquer en prod (serveur SecHunter)

```bash
# Depuis le serveur 204.168.171.71, dans le container postgres existant :
docker exec -i sechunter-postgres-1 psql -U argos_ops -d argos_ops \
  < argos_ops/crm/migrations/0001_init.sql
```

## Liste des migrations

| Fichier | Description | Date |
|---------|-------------|------|
| `0001_init.sql` | Schéma CRM initial + KB vectorielle (P3) | 2026-05-07 |
| `0002_p7_stripe.sql` | Colonnes Stripe sur companies (P7 FinanceBot) | 2026-05-12 |
| `0003_agent_run_io.sql` | Colonnes `inputs`/`outputs` JSONB sur agent_runs (cockpit Travail IN→OUT) | 2026-06-08 |
