"""Argos Ops — flotte d'agents IA pour acquisition / conversion / support / admin.

Configure loguru avec un **filtre anti-fuite secrets** dès l'import du
package, pour que les patterns connus de credentials (webhook Discord,
clés API, tokens) soient redactés avant tout sink (stdout, fichier).
Cf. CLAUDE.md § Sécurité des secrets.
"""

from argos_ops.logging import install_secret_filter

install_secret_filter()

__version__ = "0.1.0"
