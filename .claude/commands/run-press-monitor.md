---
description: Lance PressMonitor — détecte les nouvelles mentions Argos/Omnividens dans data/comm/press_mentions.yaml et notifie Discord.
---

# /run-press-monitor

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.press_monitor import PressMonitor

result = await run_agent(PressMonitor())
print(result.status, result.output_summary)
```

## Format `data/comm/press_mentions.yaml`

```yaml
mentions:
  - id: 2026-05-23-bleeping
    source: BleepingComputer
    url: https://www.bleepingcomputer.com/...
    title: "Argos lance son scan supply chain"
    sentiment: positive
    status: new
```

Le bot passe à `status: ack` les entrées notifiées (idempotent : un run
suivant ne re-notifie pas les mêmes mentions).
