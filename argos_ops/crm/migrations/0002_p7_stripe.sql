-- Argos Ops — Migration P7 (FinanceBot)
-- Ajoute les colonnes Stripe sur companies pour le pilotage MRR/dunning.
-- Idempotente : ré-application sans casser un schéma déjà migré.

BEGIN;

-- =============================================================================
-- Companies — colonnes Stripe (P7 FinanceBot)
-- =============================================================================
-- ID customer Stripe (unique, nullable — pas tous les leads ont une fiche
-- Stripe). Format ``cus_...``
ALTER TABLE companies ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT UNIQUE;

-- Statut canonique de l'abonnement (cf. Stripe Subscription.status)
-- 'trialing' | 'active' | 'past_due' | 'canceled' | 'unpaid' | 'incomplete'
-- NULL = pas de souscription Stripe associée à cette company
ALTER TABLE companies ADD COLUMN IF NOT EXISTS subscription_status TEXT;

-- MRR normalisé en EUR (mensuel équivalent). Pour un abonnement annuel
-- 1 200 €/an, ``mrr_eur`` vaut 100. Mis à jour par chaque run FinanceBot.
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mrr_eur NUMERIC(10, 2);

-- Date de la dernière synchro Stripe pour cette company (debug / observabilité)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS stripe_synced_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_companies_subscription_status ON companies(subscription_status);
CREATE INDEX IF NOT EXISTS idx_companies_stripe_customer_id ON companies(stripe_customer_id);

COMMIT;
