"""Notifications outbound vers les canaux du fondateur — Discord uniquement au launch.

Cf. D-017 : tous les webhooks sortants sont initiés par les agents tournant
sur l'ordi du fondateur. Les webhooks **entrants** (chat widget P8 etc.)
arrivent sur le serveur SecHunter et sont absorbés par la queue Redis.
"""
