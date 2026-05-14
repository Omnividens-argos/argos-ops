---
description: Drafte les réponses aux emails inbound non répondus (humain-in-the-loop)
---

# /check-emails

Slash command **interactive** lancée par le fondateur quand il a quelques
minutes pour traiter la boîte. Pas de cron — c'est l'humain qui ouvre la
session quand il est prêt.

Pré-requis : EmailBot a déjà ingéré les emails (cron `*/15` lancée par
`/run-email-bot`). Si tu doutes, lance d'abord `/run-email-bot` pour avoir
l'inbox à jour.

## Procédure

### 1. Lister les emails non répondus

Requête SQL canonique sur la base `argos_ops` :

```sql
SELECT i_in.id, i_in.lead_id, l.email, i_in.subject, i_in.body, i_in.occurred_at
FROM interactions i_in
JOIN leads l ON l.id = i_in.lead_id
WHERE i_in.channel = 'email'
  AND i_in.direction = 'in'
  AND NOT EXISTS (
    SELECT 1 FROM interactions i_out
    WHERE i_out.lead_id = i_in.lead_id
      AND i_out.channel = 'email'
      AND i_out.direction = 'out'
      AND i_out.occurred_at > i_in.occurred_at
  )
ORDER BY i_in.occurred_at DESC
LIMIT 20;
```

(Tu peux passer par `psql` ou écrire un petit script Python — pas de
préférence.)

### 2. Pour chaque email, classifier et drafter

Pour chaque ligne :

a. **Classifier** — invoque le skill `email-classifier` avec subject + body
   (le skill retourne `category`, `confidence`, `suggested_priority`,
   `suggested_response_skeleton`)

b. **Charger contexte produit** — invoque le skill `kb-rag` (P6) :

   ```python
   from argos_ops.crm.db import session_scope
   from argos_ops.rag.search import search_kb, build_support_prompt

   async with session_scope() as session:
       result = await search_kb(session, query=email.subject + " " + email.body[:500])
   ```

   Si `result.is_empty` → escalade (réponds manuellement, ne drafte pas).
   Sinon → utilise `build_support_prompt(result)` comme contexte pour
   rédiger ta réponse, en respectant les citations `[KB#N: doc§index]`.

c. **Drafter** — rédige une réponse en respectant strictement
   `data/kb/tone_of_voice.md` (DAST-first, anti-FUD, vouvoiement jamais).
   Cite des modules / prix / features uniquement s'ils sont confirmés dans
   la KB — pas d'invention.

d. **Soumettre à l'agent-juge (P14)** — invoque le skill `claude-judge`
   avec : `draft` + `original_query=email.body` + `rag_chunks` (issus du
   `kb-rag` étape b) + `channel='email'` + `agent_name='SupportBot'`.

   Parse la sortie JSON via :

   ```python
   from argos_ops.judge import parse_judge_json, apply_thresholds

   report = parse_judge_json(judge_output_text)
   verdict = apply_thresholds(report)  # auto_send / queued / killed
   ```

   - `verdict='killed'` → ne propose pas l'envoi. Affiche les
     `factual_issues / tone_issues / legal_issues`. Demande au fondateur
     soit de reformuler, soit de skipper.
   - `verdict='queued'` → flag les issues au fondateur, demande
     **validation renforcée** (le fondateur doit explicitement OK le
     wording avant envoi).
   - `verdict='auto_send'` → continue la procédure standard ci-dessous.

   Le verdict du juge est **toujours** stocké dans `interactions.judge_score`
   + `interactions.judge_verdict` à l'étape 3, même si le fondateur
   override (pour audit + calibration P14.1).

e. **Soumettre au fondateur** — affiche : sujet + draft + catégorie +
   confidence + `(judge_score / verdict)`. Demande validation explicite
   (`"envoyer"`, `"corriger : ..."`, `"skip"`, `"escalade"`)

### 3. Sur validation

Utilise le skill `zimbra-ops` pour appeler `send_email(...)` avec :
- `to=lead.email`
- `subject=f"Re: {original_subject}"` (préfixer si pas déjà préfixé)
- `body_text=la_draft_validee`
- `in_reply_to=message_id_original` + `references=[...]` pour threader
- `from_name=settings.email_reply_name`

Puis insère l'interaction via `argos_ops.judge.save_judge_verdict(...)`
qui appelle `add_interaction` avec `judge_score=report.global_score` +
`judge_verdict=verdict` (auto_send / queued / killed). Si le fondateur a
overridé un `queued` en envoi → garde le verdict du juge (« le juge
disait queued mais l'humain a validé » est une info de calibration
précieuse).

### 4. Garde-fous

- Si `is_noreply(from_email)` → ne propose pas de réponse, marque skip
- Si la classification = `spam` avec confidence > 0.8 → propose de marquer
  lu sans réponse, demande validation
- Si la classification = `sav` → crée d'abord un `ticket` avant la réponse
  (`priority='P1'` si bloquant, sinon `'P2'`)
- Si l'email mentionne un sujet hors KB → demande au fondateur de répondre
  manuellement (n'invente pas)

## Notes

- Cette commande tourne **dans une session Claude Code interactive**, pas
  via cron. C'est volontaire : l'envoi d'email engage la marque, on ne le
  laisse pas passer en auto. L'agent-juge (P14, skill `claude-judge`) note
  chaque draft mais ne décide pas seul — le fondateur valide en dernier
  recours, même sur verdict `auto_send`
- Convention de ton : court, concret, factuel, pas de faux enthousiasme.
  Cf. `data/kb/tone_of_voice.md`
- Limite par session : pas de hard limit, mais reste raisonnable (10-15 emails
  par session pour garder l'humain alerte sur la validation)

## Voir aussi

- Code agent : [`argos_ops/agents/email_bot.py`](../../argos_ops/agents/email_bot.py)
- Skill plomberie : [`.claude/skills/zimbra-ops/`](../skills/zimbra-ops/)
- Skill classification : [`.claude/skills/email-classifier/`](../skills/email-classifier/)
- KB : [`data/kb/tone_of_voice.md`](../../data/kb/tone_of_voice.md), [`data/kb/argos_features.md`](../../data/kb/argos_features.md), [`data/kb/pricing.md`](../../data/kb/pricing.md), [`data/kb/faq.md`](../../data/kb/faq.md)
