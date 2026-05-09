---
description: Répond à une question support Tier 1 via RAG sur KB Argos (anti-hallucination strict)
---

# /run-support-tier1

Slash command **interactive** pour répondre à une question produit en
s'appuyant sur la KB Argos. Sortie : soit une réponse factuelle avec
citations `[KB#N: doc§index]`, soit `ESCALADE: <raison>` si la KB ne
couvre pas le sujet.

Usage typique :

- Test rapide d'une question avant de l'inclure dans `/check-emails`
- Validation manuelle qu'une question prospect a une réponse
- Debug du seuil de distance RAG (cf. skill `kb-rag`)

## Procédure

### 1. Demander la question

Si l'utilisateur n'a pas fourni de question dans la commande, demande-la
en une phrase.

### 2. Lancer le RAG

Exécute (utilise le skill `kb-rag`) :

```python
import asyncio, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from argos_ops.crm.db import session_scope, dispose_engine
from argos_ops.rag.search import search_kb, build_support_prompt

async def main():
    async with session_scope() as s:
        result = await search_kb(s, query="<QUESTION>", top_k=5)
    print(build_support_prompt(result))
    print(f"\\n# RAG meta: hits={len(result.hits)} top_dist={result.top_distance}")
    await dispose_engine()

asyncio.run(main())
```

(Adapte `<QUESTION>` à la vraie question.)

### 3. Lire le prompt produit

Le prompt sortant contient :
- La question
- Les 5 chunks top-K (avec `doc_path§index` + distance)
- Les règles anti-hallucination

### 4. Répondre

**Toi (Claude Code)** rédige la réponse en suivant strictement les règles
du prompt :

- Si les extraits couvrent la question → réponse factuelle courte avec
  citations `[KB#N: doc§index]` à chaque claim
- Sinon → `ESCALADE: <raison courte>` (ex : « Question hors KB Argos —
  requiert un humain »)

### 5. Décision suivante

- **Réponse fournie** : présente-la au fondateur. S'il la valide pour
  envoyer à un prospect, copie-la dans `/check-emails`
- **Escalade** : recommande au fondateur de répondre manuellement OU
  d'enrichir la KB si c'est une question fréquente non couverte (à noter
  dans `data/kb/faq.md` ou un nouveau fichier KB)

## Notes

- Cette commande **ne logge pas dans `agent_runs`** (pas une exécution
  d'agent — c'est une utility interactive)
- Cette commande **ne touche pas à la DB** sauf en lecture (recherche RAG)
- Distance threshold default = 0.85. Si tu observes des faux négatifs
  (escalade alors qu'il y avait une bonne réponse), abaisse à 0.7 et
  re-teste

## Voir aussi

- Skill : [`.claude/skills/kb-rag/`](../skills/kb-rag/)
- Code : [`argos_ops/rag/search.py`](../../argos_ops/rag/search.py)
- Eval : [`scripts/eval_kb_rag.py`](../../scripts/eval_kb_rag.py)
- Décisions : [D-017](../../docs/DECISIONS.md) (local-first)
