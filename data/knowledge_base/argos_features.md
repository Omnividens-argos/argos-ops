# Argos — Catalogue des modules

> Référentiel exhaustif des 139 modules de scan d'Argos. **Source de vérité**
> pour SupportBot, OutboundBot, ContentBot et toute doc
> publique qui décrit la couverture du produit. Si un autre fichier KB ou
> une page publique cite un compte différent ou décrit un module
> différemment, **ce fichier prime** — créer une PR pour aligner.
>
> Source : interview fondateur en P3-M2 (2026-05-08), croisée avec dump
> automatisé de `MODULE_DESCRIPTIONS` (`sechunter/core/scan_profiles.py`)
> et de `_FREE_MODULES` (`sechunter/core/plans.py`). L'annexe
> machine-readable [`argos_modules.raw.json`](argos_modules.raw.json) est
> régénérable manuellement via la commande documentée en § 7.

---

## 1. Vue d'ensemble

### 1.1 Philosophie — DAST-first, 0 faux positif, IA-corrélation

Argos est un **scanner DAST + recon + cloud** avec un complément SAST fin.
Trois choix produits que la doc reflète partout :

1. **DAST-first.** L'axe principal est l'analyse en runtime depuis
   l'extérieur (« scanner qui teste l'appli sans accès au code »). Le SAST
   est un complément (14 modules sur 139, ~10 %) — wrappers fins autour de
   tree-sitter, ruff, semgrep, trufflehog, hadolint, checkov. Argos ne
   prétend pas remplacer Snyk ou SonarQube sur le SAST pur, et le dit.
2. **0 faux positif comme obsession.** Les modules ne crachent un finding
   que s'il y a une **preuve reproductible** : oracle out-of-band, baseline
   diff, time-based, signature ancrée, status-code whitelist. Pas de
   substring matching. Un an de travail dédié à tuer les FP — c'est ce qui
   justifie la phrase clinchante « 0 faux positif et 139 modules ».
3. **IA-corrélation comme couche post-scan, pas comme module.** L'agent IA
   à 5 rôles (Strategist / Analyst / Correlator / Enricher / Reporter)
   transforme N findings indépendants en kill chain narratif scénarisé.
   Détail complet en [§ 4](#4-couche-ia-correlation).

### 1.2 Compte exact — 139 modules sur 6 catégories

| Catégorie | Modules | Couvre |
|---|---:|---|
| **web** (DAST) | 49 | SQLi, XSS, SSRF, IDOR, CSRF, LFI/RCE, XXE, smuggling H1/H2, race condition, OAuth, SAML, account takeover, postMessage, websocket, web3 dApp |
| **network** | 31 | Ports TCP/UDP, TLS/SSL, SSH audit, default creds (SSH/FTP/MySQL/Redis/Mongo), SMB, SNMP, LDAP, FTP, RDP, VNC, Telnet, Kerberos, MQTT, NTP, NFS, IPMI, DNS rebinding, Docker API, K8s API, Jenkins, Prometheus/Grafana, Redis/Mongo/MS-SQL/Memcached/Elasticsearch unauth, Consul/etcd, IPv6, email |
| **recon** | 20 | DNS zone, subdomains, ASN, fingerprint, tech stack, WAF detect, robots/sitemap, screenshot, JS analysis, source maps, favicon hash, GitHub recon, git exposure, S3 enum, subdomain takeover, backup files, email harvest, HTTP methods |
| **sast** | 14 | Python, JS/TS, Java, C#, PHP, Go, Ruby, secrets, dependencies (CVE via OSV.dev), supply-chain, Docker (hadolint), IaC (checkov : Terraform, CloudFormation, K8s, Helm), license audit, SBOM |
| **api** | 13 | BOLA (IDOR), broken function auth, mass assignment, excessive data exposure, OpenAPI audit, rate limiting, GraphQL injection, gRPC audit, WebSocket API, SSRF via API, injection générique, versioning exposure, auth |
| **cloud** | 12 | IAM, IMDS metadata (AWS/GCP/Azure), secrets manager (Vault/KV/SM), misconfig (S3/GCS/Azure Blob), Cognito, Firebase, Lambda, Terraform state, container registry, CDN bypass (origin IP leak), DNS dangling (34 plateformes), network ACL |
| **Total** | **139** | |

L'IA-corrélation **n'est pas une 7ᵉ catégorie de modules** — c'est une
couche post-scan implémentée dans `sechunter/core/agent.py` (543 LOC) et
documentée en [§ 4](#4-couche-ia-correlation).

### 1.3 Gating Free vs payant — 41 / 139

Critère de gating documenté dans `sechunter/core/plans.py:74-77` :

> « Modules accessibles au plan Free : uniquement ceux dont la sévérité max
> atteignable est ≤ HIGH. Les modules à potentiel CRITICAL (sqli, rce,
> xxe, smuggling, deserialization, file_upload, IMDS, secrets…) sont
> explicitement exclus pour préserver la valeur Pro/Team/Pro Max. »

| Tier | Modules | Sévérité max affichée |
|---|---:|---|
| **Free** | 41 | HIGH (CRITICAL masqués) |
| **Pro / Team / Pro Max** | 139 (tous) | toutes |

**Répartition Free par catégorie :**

| Catégorie | Free | Total |
|---|---:|---:|
| web | 21 | 49 |
| recon | 12 | 20 |
| network | 8 | 31 |
| api | 0 | 13 |
| cloud | 0 | 12 |
| sast | 0 | 14 |

api / cloud / sast sont **entièrement gated Pro+**. Logique : ces trois
catégories produisent presque exclusivement des findings CRITICAL
(creds AWS, IDOR API, RCE supply-chain). Les laisser en Free dilue le
signal d'upgrade et risque de forwarder à un attaquant des findings
exploitables sur la cible scannée gratuitement.

L'application technique du gating est faite par le middleware
`sechunter/core/quota.py:64-78` (`check_modules_allowed`) qui lève HTTP
403 sur tentative de scan d'un module gated. Appelé depuis
`scan_service.py:43-54` dans `POST /scans`.

> **Note technique (état au 2026-05-08).** `_FREE_MODULES` côté code liste
> 42 entrées, mais `network.portscan_light` n'est pas enregistré dans le
> registry actif (alias mort ou module non `@register`-é). Le compte
> Free **réellement scannable est donc de 41**. Ce fichier reflète la
> réalité du registry, pas la promesse théorique. Si un module
> supplémentaire est enregistré ultérieurement côté SecHunter, regénérer
> `argos_modules.raw.json` (commande § 7) et mettre ce fichier à jour.

### 1.4 Comment lire ce fichier

- **Tu cherches un module précis ?** → § 2 catalogue exhaustif (Ctrl+F sur
  le nom canonique `category.module`, ex : `cloud.dns_dangling`)
- **Tu prépares un cold call et tu veux les arguments forts ?** → § 3
  zooms emblématiques (30 modules avec exemples de findings réels)
- **Un prospect demande comment marche la corrélation IA ?** → § 4
- **Un prospect demande si Argos fait X (BAS, EDR, mobile, SCA) ?** →
  § 5 antimatière (réponse cadrée pour les 8 trucs hors-scope)
- **SupportBot a besoin d'une donnée structurée ?** →
  [`argos_modules.raw.json`](argos_modules.raw.json) (annexe § 7)

---

## 2. Catalogue exhaustif (139 modules)

Tableau exhaustif généré depuis `MODULE_DESCRIPTIONS` (registry SecHunter)
au 2026-05-08, croisé avec `_FREE_MODULES`. **41 modules ✓ Free** sur 139,
répartition par catégorie ci-dessous.

> Description rendue en l'état du registry. Certaines entrées sont en
> anglais (anciens commentaires de code), d'autres en français — pas
> d'effort de traduction sur ce fichier au launch. Re-rédaction
> uniformisée en français possible en P19 (maintenance).

### 2.1 Web (DAST) — 49 modules (21 Free)

| Module | Ce qu'il trouve | Free |
|---|---|---|
| `web.access_control` | Broken Access Control (forced browsing, priv esc, method bypass) | ✓ |
| `web.account_takeover` | Account Takeover v2 — password reset poisoning, reset token quality, email change without confirmation, OAuth misconfiguration, account enumeration, MFA bypass. | — |
| `web.api_versioning` | Détection d'anciennes versions d'API accessibles. v2 avec baseline diff (rejet catch-all), pré-validation anti-bot, et signature API (JSON / OpenAPI markers) obligatoire. | — |
| `web.broken_auth` | Broken Authentication v2 — rate limiting, default credentials, account lockout, session cookie flags. Uses AttackSurface for login discovery and response_classifier for anti-bot filtering. | ✓ |
| `web.business_logic` | Business Logic Flaws (price manipulation, coupon stacking) | — |
| `web.cache_deception` | Cache deception multi-technique (25+ extensions, 15+ séparateurs, Content-Type mismatch, two-request confirmation authentifiée si auth_recipe disponible, baseline diff via BaselineManager). Pré-validation anti-bot et whitelist des paths publics par design. | — |
| `web.cache_poisoning` | Web Cache Poisoning & Cache Deception (unkeyed headers, path confusion) | — |
| `web.clickjacking` | Clickjacking (iframe, X-Frame-Options, frame-ancestors) | ✓ |
| `web.cookie_security` | Audit cookies v2 — Secure, HttpOnly, SameSite, __Host- / __Secure- prefixes. Whitelists analytics/consent cookies and filters anti-bot responses. | ✓ |
| `web.cors` | CORS Misconfiguration | ✓ |
| `web.crlf_injection` | CRLF Injection / HTTP Response Splitting (header injection) | ✓ |
| `web.csp_bypass` | CSP Bypass Analysis (unsafe-inline/eval, JSONP, grade A-F) | ✓ |
| `web.csrf` | Cross-Site Request Forgery (tokens, SameSite, Referer) | ✓ |
| `web.deserialization` | Insecure Deserialization (Java, PHP, Python, .NET) | — |
| `web.error_disclosure` | Détection de fuites d'information via pages d'erreur — v2 avec pré-validation anti-bot, baseline diff, whitelist endpoints publics, triggers dérivés de l'AttackSurface, catalogue de ~50 patterns. | ✓ |
| `web.file_upload` | File Upload Vulns (shell, extension/MIME bypass, SVG XSS) | — |
| `web.fuzzing` | Directory / File Fuzzing | ✓ |
| `web.graphql` | GraphQL Security (introspection, injection, batching, DoS) | — |
| `web.headers` | Security Headers (CSP, HSTS, X-Frame-Options...) | ✓ |
| `web.host_header` | Host Header Injection (reset poisoning, X-Forwarded-Host) | ✓ |
| `web.http2_smuggling` | HTTP/2 request smuggling — H2.CL desync, H2.TE desync, CRLF injection in H2 headers, Content-Length mismatch | — |
| `web.http_smuggling` | HTTP Request Smuggling (CL.TE, TE.CL, TE.TE, timing) | — |
| `web.idor` | Insecure Direct Object Reference | ✓ |
| `web.insecure_tls_redirect` | Audit redirection HTTP→HTTPS, HSTS (max-age, includeSubDomains, preload) et leak de cookies sur HTTP. v2 avec pré-validation anti-bot et parsing HSTS structuré. | ✓ |
| `web.jwt` | JWT Attacks (none algo, key confusion, expiry) | ✓ |
| `web.lfi_rfi` | Local / Remote File Inclusion | — |
| `web.misconfig` | Security Misconfiguration (debug mode, default creds, dir listing) | ✓ |
| `web.nosqli` | NoSQL Injection (MongoDB operators, auth bypass, $where blind) | — |
| `web.oauth_misconfig` | OAuth/OIDC misconfiguration v2 — PKCE, grant types, client registration, id_token signing, client auth, response_mode, client-id enumeration. | — |
| `web.open_redirect` | Open Redirect | ✓ |
| `web.parameter_pollution` | HTTP Parameter Pollution (duplicate params, WAF bypass) | ✓ |
| `web.password_policy` | Audit de la politique de mots de passe (longueur, autocomplete, cleartext). v2 avec pré-validation anti-bot et discovery via AttackSurface. | ✓ |
| `web.path_traversal` | Path traversal detection (facade for web.lfi_rfi v2) | — |
| `web.postmessage_xss` | Détection de DOM XSS via window.postMessage — oracle d'exécution actif dans un navigateur headless sur les pages de l'AttackSurface. | — |
| `web.prototype_pollution` | Prototype Pollution JS (GET, JSON, client/server-side) | — |
| `web.race_condition` | Race Condition / TOCTOU (double-submit, coupon abuse, double-spend) | — |
| `web.rce` | Remote Code Execution (command injection, SSTI) | — |
| `web.rce_command` | OS Command Injection detection (error-based, OOB blind, time-based) across all injection locations (query, body, header, cookie). | — |
| `web.rce_ssti` | Server-Side Template Injection (SSTI) detection via arithmetic evaluation oracle across all injection locations. | — |
| `web.saml_attacks` | SAML 2.0 weaknesses v2 — metadata exposure, signature stripping, XML signature wrapping, InResponseTo / Destination absent, assertion replay, XXE via SAMLResponse. | — |
| `web.session_fixation` | Session Fixation (URL session ID, no rotation, cookie flags, weak entropy) | ✓ |
| `web.sqli` | SQL Injection (blind + error-based) | — |
| `web.ssi_injection` | Server-Side Includes (SSI) Injection detection via directive evaluation oracle across all injection locations. | — |
| `web.ssrf` | Server-Side Request Forgery | — |
| `web.subdomain_routing` | Test d'accès cross-tenant via manipulation du Host header. v2 avec diff structurel baseline / candidat, pré-validation anti-bot, et confirmation DNS optionnelle. | ✓ |
| `web.web3_dapp` | Web3 / dApp frontend audit v2 — private-key leak, provider key exposure, localStorage anti-pattern, eth_sign, EIP-712 chainId, infinite approve, signature replay. | — |
| `web.websocket` | WebSocket Security (CSWSH, injection, missing auth, cleartext) | — |
| `web.xss` | Cross-Site Scripting (reflected, stored, DOM-based) | — |
| `web.xxe` | XML External Entity Injection | — |

### 2.2 Network — 31 modules (8 Free)

| Module | Ce qu'il trouve | Free |
|---|---|---|
| `network.consul_etcd` | Audit Consul + etcd — détection unauth access via /v1/agent/self + /version canoniques, KV stores avec sensitive keys regex anchored, ACL tokens listables, auth status etcd. | — |
| `network.default_creds` | Default Credentials (SSH, FTP, MySQL, Redis, MongoDB...) | — |
| `network.dns_rebinding` | DNS Rebinding (Host validation, CORS permissif, protections manquantes) | — |
| `network.docker_api` | Audit Docker Engine API — détection d'exposition sans auth/TLS sur 2375 (HTTP) et 2376 (TLS sans mTLS). Signature canonique via /_ping + /version + confirmation active /containers/json + /info pour escalation CRITICAL. | — |
| `network.elasticsearch_unauth` | Audit Elasticsearch / OpenSearch — détection d'accès sans authentification via GET / signature canonique, listage d'indices, bulk _search cross-index, disclosure de version et CVE mapping. | — |
| `network.email` | Email Security (SMTP open relay, SPF/DKIM/DMARC, STARTTLS) | ✓ |
| `network.ftp` | FTP Security (anonymous login, bounce attack, banner grabbing, cleartext) | — |
| `network.ipmi` | IPMI BMC audit UDP 623 — Get Channel Auth Caps strict, cipher 0 bypass (CRITICAL), RAKP hash disclosure CVE-2013-4786 (HIGH) | — |
| `network.ipv6` | IPv6 Security (dual-stack, IPv6-only services, firewall bypass) | ✓ |
| `network.jenkins_unauth` | Audit Jenkins — détection unauth access via signature X-Jenkins + parsing /api/json (useSecurity flag), confirmation RCE Groovy active, credentials store, users, nodes, environment. | — |
| `network.kerberos` | Audit Kerberos v5 — détection KDC, AS-REP Roasting sur comptes courants, chiffrement faible accepté, authentification anonyme. | — |
| `network.kubernetes_api` | Audit Kubernetes API — détection API server exposé, kubelet secure/read-only accessible, vérification anonymous-auth via /api/v1/namespaces avec parsing JSON strict. | — |
| `network.ldap` | LDAP Security Audit (anonymous bind, injection, user enum, rootDSE) | — |
| `network.memcached_unauth` | Audit Memcached — détection d'accès sans authentification (TCP), disclosure slabs/items, test d'amplification UDP (CVE-2018-1000115). | — |
| `network.mongodb_unauth` | Audit MongoDB — détection d'accès sans authentification via Wire Protocol OP_QUERY isMaster, listage des bases (listDatabases), disclosure de version et wire version. | — |
| `network.mqtt` | Audit MQTT — détection accès anonyme, wildcard subscribe '#' et '$SYS/#', cleartext 1883, credentials par défaut (3.1.1 et 5.0) | ✓ |
| `network.mssql` | Audit Microsoft SQL Server — détection TDS PRELOGIN, politique de chiffrement, disclosure de version, mode d'authentification (Mixed vs Windows), exposition du SQL Server Browser UDP. | — |
| `network.nfs` | Audit NFS — portmapper, versions (NFSv2/v3/v4), énumération des exports via MOUNT, détection d'exports world-readable. | — |
| `network.ntp` | Audit NTP UDP 123 — NTPv4 strict Q1, version disclosure via mode 6 readvar, monlist CVE-2013-5211 avec facteur d'amplification mesuré | ✓ |
| `network.portscan` | Port Scan (nmap + fallback TCP) | ✓ |
| `network.prometheus_grafana` | Audit Prometheus + Grafana + AlertManager + node_exporter + Pushgateway — détection unauth via signatures JSON/OpenMetrics canoniques, secrets YAML anchored regex, Grafana default creds. | — |
| `network.rdp` | Audit RDP — négociation X.224 pour détecter PROTOCOL_RDP (standard security, sans NLA), parsing spec MS-RDPBCGR strict | — |
| `network.redis_unauth` | Audit Redis — détection d'accès sans authentification via RESP, CONFIG writable (préparation RCE), exposition de données et disclosure de version/OS. | — |
| `network.service_cve` | Service Version + CVE Matching | — |
| `network.smb` | SMB/NetBIOS Enumeration | — |
| `network.snmp` | SNMP Community String Bruteforce | ✓ |
| `network.ssh_audit` | Audit SSH (ssh-audit wrapper) — algorithmes obsolètes, CVEs, version disclosure | ✓ |
| `network.ssl_audit` | SSL/TLS Audit (ciphers, certs, BEAST/POODLE/Heartbleed) | ✓ |
| `network.telnet` | Audit Telnet — port 23 cleartext, device fingerprint, default credentials | — |
| `network.vnc` | Audit VNC — validation banner RFB anchored, confirmation active de SecurityType None via ServerInit, test de passwords triviaux pour VNC Auth | — |
| `network.winrm` | Audit WinRM (WS-Management) — détection stricte, cleartext HTTP, Basic auth sur HTTP, accès non authentifié via SOAP Enumerate | — |

### 2.3 Recon — 20 modules (12 Free)

| Module | Ce qu'il trouve | Free |
|---|---|---|
| `recon.asn` | ASN / WHOIS Lookup | ✓ |
| `recon.backup_files` | Détection de fichiers sensibles exposés : backup, config, debug, IDE | ✓ |
| `recon.cloud_provider` | Détection cloud provider (AWS/GCP/Azure/Cloudflare/…) via headers + DNS — alimente SharedContext pour les modules cloud/* (INFO only) | ✓ |
| `recon.dns_zone` | DNS Zone Transfer | ✓ |
| `recon.email_harvest` | Récolte d'emails OSINT (mailto + scan HTML) avec classification anti-FP — toutes les findings en INFO | ✓ |
| `recon.favicon_hash` | Identification de technologies par hash MurmurHash3 du favicon (Shodan-compatible). Détecte Grafana, Jenkins, GitLab, Fortinet, Prometheus, Kubernetes Dashboard, etc. N'émet qu'un finding INFO — la présence d'un favicon ne prouve pas l'exposition publique non protégée du service (certains dashboards sont publics par design). | — |
| `recon.fingerprint` | Technology Fingerprinting | ✓ |
| `recon.git_exposure` | Détection de répertoires VCS exposés (.git, .svn, .hg, .bzr) | — |
| `recon.github_recon` | Découverte d'organisations GitHub/GitLab, repos publics, emails de développeurs — oracles stricts (regex ancrées, API JSON validée) | — |
| `recon.http_methods` | Détection des méthodes HTTP dangereuses (TRACE, TRACK, DEBUG, PUT, DELETE, CONNECT, PATCH) avec baseline diff pour filtrer les catch-all SPA, whitelist des contextes REST, et confirmation stricte du TRACE via écho d'un header canary. | ✓ |
| `recon.js_analysis` | Analyse JS : extraction d'endpoints, secrets (patterns ancrés), commentaires | — |
| `recon.portscan_light` | Port Scan Light (top ports rapide) | — |
| `recon.robots_sitemap` | Cartographie passive : robots.txt, sitemap.xml, .well-known/security.txt | ✓ |
| `recon.s3_enum` | Énumération de buckets cloud storage (AWS S3, DigitalOcean Spaces, GCS) par permutations du domaine — oracle XML strict | — |
| `recon.screenshot` | Screenshot de la cible | ✓ |
| `recon.source_map` | Détection de source maps JS exposées (code source, secrets) | — |
| `recon.subdomain` | Subdomain Enumeration | ✓ |
| `recon.subdomain_takeover` | Subdomain Takeover (CNAME dangling vers services cloud) | — |
| `recon.tech_stack_deep` | Fingerprinting approfondi : cookies de session, chemins d'assets JS, data-attributes HTML, headers spécifiques aux frameworks modernes. Complémentaire de ``recon.fingerprint`` (qui lit les signatures explicites type ``Server`` et ``X-Powered-By``). | ✓ |
| `recon.waf_detect` | WAF Detection | ✓ |

### 2.4 SAST — 14 modules (0 Free)

| Module | Ce qu'il trouve | Free |
|---|---|---|
| `sast.csharp_analyzer` | Analyse statique C#/.NET via tree-sitter AST : SqlCommand concat, BinaryFormatter, NetDataContractSerializer, LosFormatter, Html.Raw, Response.Write, MD5/SHA1/DES/RC2, Process.Start, DirectorySearcher, Random, ViewState MAC, secrets hardcodes. | — |
| `sast.dependency` | SCA — dependances vulnerables (CVE via OSV.dev) | — |
| `sast.docker` | Docker Security (USER root, secrets in layers, :latest) | — |
| `sast.go_analyzer` | Analyse statique Go via tree-sitter AST : imports crypto faible (md5/sha1/des/rc4/math-rand), SQL via fmt.Sprintf, exec.Command avec variable/shell, InsecureSkipVerify, SSLv3, unsafe.Pointer, secrets hardcodes. | — |
| `sast.iac` | IaC Security (Terraform, CloudFormation, Kubernetes) | — |
| `sast.java_analyzer` | Analyse statique Java via tree-sitter AST : Runtime.getRuntime, ObjectInputStream, XMLDecoder, XStream, JNDI lookup, XXE parsers, crypto faible (DES/ECB/MD5/SHA1), Random, Spring CSRF disable, path traversal, secrets hardcodes. | — |
| `sast.javascript` | Analyse Statique JS/TS (eval, DOM XSS, secrets, ReDoS) | — |
| `sast.license_audit` | License audit v2 : classification SPDX (permissive/weak/strong/network copyleft/proprietary), expressions composees, detection conflits projet vs dep, transitives node_modules | — |
| `sast.php_analyzer` | Analyse statique PHP via tree-sitter AST : SQLi (mysql_query / PDO / wpdb), command injection (system/shell_exec/backticks), code injection (eval/assert/preg_replace e/create_function), unserialize user input, LFI/RFI (include/require), XSS (echo superglobale), path traversal, SSRF (curl), crypto faible, mcrypt, extract, secrets hardcodes. | — |
| `sast.python` | Analyse Statique Python (secrets, vulns, deps) | — |
| `sast.ruby_analyzer` | Analyse statique Ruby/Rails via tree-sitter AST : SQLi (where/find_by_sql/execute interp), command injection (system/exec/backtick interp), eval/instance_eval/class_eval sur params, send(params), YAML/Marshal.load, permit! mass assignment, html_safe / ERB raw, redirect_to params, Digest::MD5/SHA1, secrets hardcodes. | — |
| `sast.sbom` | SBOM v2 : genere un Software Bill of Materials au format CycloneDX 1.5 JSON a partir des manifests/lockfiles de tous les ecosystemes supportes (PyPI/npm/RubyGems/Go/Cargo/Packagist/Maven/NuGet). 1 seul finding INFO de synthese par scan, SBOM complet en evidence. | — |
| `sast.secrets` | Secrets multi-langage (AWS, GCP, Azure, Stripe, GitHub) | — |
| `sast.supply_chain` | Supply chain v2 : typosquatting (Damerau-Levenshtein), scripts preinstall/postinstall suspects (pipe-to-shell, base64 decode, reverse shell), dependency confusion, lockfiles manquants, versions non pinnees, replace local go.mod, dep via URL/git/file:// | — |

### 2.5 API — 13 modules (0 Free)

| Module | Ce qu'il trouve | Free |
|---|---|---|
| `api.auth` | API Authentication Testing | — |
| `api.bola` | Broken Object Level Authorization (IDOR via IDs séquentiels et UUIDs) | — |
| `api.broken_function_auth` | API Broken Function Level Authorization v2 — admin-class endpoints reachable from lower-privilege or anonymous sessions, plus HTTP method-switching authorization bypass (OWASP API5:2023). | — |
| `api.excessive_data` | API Excessive Data Exposure v2 — structured JSON response analysis with precise sensitive-key regex, anti-bot/SPA filtering, and pagination-less bulk detection (OWASP API3:2023). | — |
| `api.graphql_injection` | API GraphQL security audit v2 — strict spec-GraphQL probe, introspection / field suggestion / batching / alias flood / depth DoS / GraphQL-over-GET / unauth-mutation, plus 4-oracle injection (error / boolean / time / OOB) on inline arguments, variables and directives across SQLi, NoSQLi, RCE-cmd, SSTI, LDAPi, XPathi (OWASP API8:2023 + API10:2023). | — |
| `api.grpc_audit` | API gRPC audit v2 — reflection, service enumeration, plaintext (h2c), invalid TLS certificate, unauthenticated method invocation, health-check exposure (OWASP API1 + API5 + API8 + API10). | — |
| `api.injection` | API injection detection v2 — SQLi / NoSQLi / Command / SSTI / LDAPi / XPathi across query, body, header and cookie with error-based, boolean-blind, time-based and OOB oracles (OWASP API8:2023 + API10:2023). | — |
| `api.mass_assignment` | Mass Assignment (champs non documentes : is_admin, role) | — |
| `api.openapi_audit` | OpenAPI/Swagger Audit (spec exposee, endpoints sans auth) | — |
| `api.rate_limiting` | Rate Limiting (brute force login, register, password reset, OTP) | — |
| `api.ssrf_via_api` | SSRF detection v2 on API endpoints accepting URL-like parameters — OOB DNS/HTTP, cloud metadata fingerprint, and baseline-diff response-based oracles (OWASP API7:2023, CWE-918). | — |
| `api.versioning_exposure` | API versioning exposure v2 — detects legacy API versions that coexist with the current one and that may miss security patches or have weaker authorization checks (OWASP API9:2023, CWE-1059). | — |
| `api.websocket_api` | API WebSocket audit v2 — missing authentication, CSWSH, cleartext transport, token-in-URL, permissive CORS on upgrade, message-level injection (4 oracles × 6 categories), sensitive-data leak in echoes, GraphQL subscription unauth (OWASP API1 + API2 + API3 + API8 + API10). | — |

### 2.6 Cloud — 12 modules (0 Free)

| Module | Ce qu'il trouve | Free |
|---|---|---|
| `cloud.cdn_bypass` | Detects CDN/WAF bypass vectors: origin IP leaked in response headers, origin subdomains reachable without the CDN, and proxy-header spoofing that flips backend behaviour. | — |
| `cloud.cognito_misconfig` | Detects unauthenticated AWS Cognito Identity Pools, public User Pool sign-up, and exposed Hosted UIs using strict JSON content signatures. | — |
| `cloud.container_registry` | Detects Docker Registry / OCI registries accessible without authentication via anchored JSON signatures on the v2 catalog and tags endpoints. | — |
| `cloud.dns_dangling` | Detects dangling CNAMEs pointing to deprovisioned cloud resources (AWS S3, Azure App Service, Heroku, GitHub Pages, Netlify, Vercel, Firebase, Shopify, …) that can lead to subdomain takeover. | — |
| `cloud.firebase_misconfig` | Detects publicly readable Firebase Realtime Database, Firestore collections, Storage buckets, and unrestricted Identity Toolkit sign-up via anchored JSON signatures. | — |
| `cloud.iam` | Cloud IAM Misconfig (policies permissives, credentials exposees) | — |
| `cloud.lambda_misconfig` | Detects serverless env-var leakage, stack traces and fingerprint headers on Lambda / Azure Functions / GCP Cloud Functions using anchored signatures and baseline-diff validation. | — |
| `cloud.metadata` | Cloud Metadata IMDS (AWS IMDSv1/v2, GCP, Azure IMDS) | — |
| `cloud.misconfig` | Cloud Misconfiguration (AWS S3, GCP, Azure) | — |
| `cloud.network_acl` | Audits exposed management services (SSH, RDP, databases, orchestration planes, message brokers, monitoring dashboards) with a protocol-level probe to avoid false positives on generic open ports. | — |
| `cloud.secrets_manager` | Detects exposed secret stores (HashiCorp Vault, Azure Key Vault, Kubernetes Secrets API, GCP Secret Manager, AWS SSM) via strict JSON signatures and response classification. | — |
| `cloud.terraform_state` | Detects exposed Terraform state / plan files, unauthenticated Consul KV backends and public HCP Terraform workspaces via anchored JSON signatures and baseline-diff validation. | — |
---

## 3. Zoom sur 25-30 modules emblématiques

Format de chaque zoom : **Oracle** (ce qui rend la détection fiable) /
**Finding canonique** (exemple anonymisé reproductible) / **Différenciant**
(positionnement vs Acunetix / Detectify / Burp / Intruder). 4-6 lignes max.
Pour la liste exhaustive des 139 modules avec descriptions courtes, voir
[§ 2](#2-catalogue-exhaustif-139-modules).

> Convention placeholders (cf. [`tone_of_voice.md` § 9](tone_of_voice.md#9-convention-placeholders-pour-les-exemples-publics)) :
> tous les domaines cités sont fictifs (`acme.fr`, `acme-corp.com`,
> `boutique.example.com`, `app.client.example`). Les clés / IDs /
> credentials sont remplacés par les fixtures de test publiques officielles
> (`AKIAIOSFODNN7EXAMPLE` pour AWS — clé démo officielle des AWS docs,
> universellement reconnue comme fictive).

### 3.1 Web (DAST) — 12 zooms

#### `web.sqli` — SQL Injection — CRITICAL / Pro+

- **Oracle** : blind boolean + time-based (sleep 5s) + error-based selon
  l'environnement. Pas de substring matching sur les messages SQL — le
  finding ne sort que si la différence de comportement entre payload
  positif et payload négatif est statistiquement reproductible.
- **Finding canonique** : SQLi blind time-based sur `acme.fr/products?id=` —
  le payload `1' AND SLEEP(5)--` ajoute systématiquement +5 s à la latence
  baseline (mesuré sur 5 itérations). CRITICAL 9.8.
- **Différenciant** : Acunetix flague souvent un FP sur les pages avec
  rate-limit naturel (latence variable). Argos calibre la baseline avant
  le payload et exige un delta net.

#### `web.xss` — Cross-Site Scripting — HIGH/CRITICAL / Pro+

- **Oracle** : Playwright headless avec canary `SECXSS-<uuid>` exécuté en
  DOM réel sur 5 contextes d'injection (`<script>`, `<img onerror>`,
  `<svg onload>`, `<body onload>`, JS context). Le finding ne sort que si
  le canary unique est présent dans le DOM rendu.
- **Finding canonique** : reflected XSS sur `acme.fr/?q=` —
  `?q=<img src=x onerror=alert(SECXSS-...)>` exécute le canary dans le
  DOM rendu de la page de résultats. HIGH 8.0 reflected/DOM,
  CRITICAL 9.0 stored.
- **Différenciant** : exécution DOM via `PlaywrightPool` au lieu de regex
  statique. Acunetix et Burp Suite ratent le DOM-based XSS moderne (qui
  ne reflète pas dans le HTML brut mais dans le DOM après hydration React /
  Vue / Svelte).

#### `web.ssrf` — Server-Side Request Forgery — CRITICAL / Pro+

- **Oracle** : triple — regex in-band (présence injectée + absence
  baseline) + OOB DNS/HTTP via `CallbackToken` + cloud metadata
  `169.254.169.254` / `metadata.google.internal` avec signature JSON
  ancrée. Bypass IP-encoding embarqué (decimal, hex, octal,
  IPv6-mapped).
- **Finding canonique** : SSRF avec leak IMDS sur
  `acme-corp.com/api/preview?url=` —
  `?url=http://169.254.169.254/latest/meta-data/iam/security-credentials/`
  retourne `{"Code":"Success", "AccessKeyId":"AKIAIOSFODNN7EXAMPLE",...}`.
  CRITICAL 9.1.
- **Différenciant** : calibration 3 paliers (Bug #35) — le finding ne
  sort qu'avec corrélation explicite entre payload positif et baseline
  négative. Évite les FP sur les URL-fetchers légitimes (proxy
  d'images, preview link, OG card generator).

#### `web.lfi_rfi` — Local/Remote File Inclusion — CRITICAL / Pro+

- **Oracle** : full-body match ancré sur indicateurs système
  (`/etc/passwd` → `root:x:0:0:`, `win.ini` → `[fonts]`) + erreurs PHP /
  Java + RFI via OOB callback. 20+ variantes de traversal :
  deep-slash, semicolon, URL-encoded, null byte, UTF-8 overlong,
  unicode fullwidth.
- **Finding canonique** : LFI sur `acme.fr/?file=` — payload
  `?file=../../../../etc/passwd` retourne un body contenant `root:x:0:0:`
  ancré. CRITICAL 9.1.
- **Différenciant** : Bug #46 fix `etc_hostname` — kill du FP « match
  n'importe quelle ligne courte ». La majorité des scanners flagguent
  un LFI dès qu'ils voient `:` dans la réponse — Argos exige la signature
  exacte de `/etc/passwd` ou `/etc/shadow`.

#### `web.rce` / `web.rce_command` / `web.rce_ssti` — Remote Code Execution — CRITICAL / Pro+

Trois modules complémentaires, un même chapeau « RCE » dans le rapport :

- **`web.rce_command`** — OS Command Injection. **Oracle** : OOB DNS via
  callback Burp Collaborator-like (le serveur cible doit résoudre un
  domaine unique injecté → preuve d'exécution serveur). Couvre query,
  body, header, cookie. Pas de FP possible — l'oracle OOB ne déclenche
  que si le payload est exécuté.
- **`web.rce_ssti`** — Server-Side Template Injection. **Oracle** :
  évaluation arithmétique (`{{7*7}}` retourne `49`). Bypass des moteurs
  Jinja2 / Twig / Velocity / FreeMarker.
- **`web.rce` legacy** — wrapper qui agrège command + SSTI pour les
  rapports historiques.
- **Finding canonique** : RCE via SSTI Jinja2 sur
  `acme.fr/preview?template=` — payload `{{config}}` retourne le dict
  Flask config. CRITICAL 9.8.
- **Différenciant** : la triade command + SSTI + deserialization couvre
  les 3 vecteurs RCE serveurs modernes — Detectify n'a pas SSTI au
  catalogue, Acunetix l'a mais sans oracle arithmétique propre.

#### `web.deserialization` — Insecure Deserialization — CRITICAL / Pro+

- **Oracle** : OOB DNS lookup déclenché par gadget chain — Java (Apache
  Commons Collections, Hibernate), PHP (Phar, magic methods), Python
  (désérialisation native legacy), .NET (BinaryFormatter, JSON.Net).
  Le payload force le serveur à résoudre un domaine unique injecté.
- **Finding canonique** : Java unsafe deserialization sur cookie de session
  `JSESSIONID` de `acme.fr` — payload Commons Collections déclenche le
  lookup OOB en ~80 ms. CRITICAL 9.8.
- **Différenciant** : peu de scanners DAST mainstream couvrent les 4
  écosystèmes. C'est typiquement réservé à Burp Suite Pro avec un plugin
  dédié. Argos l'a en module standard.

#### `web.xxe` — XML External Entity — CRITICAL / Pro+

- **Oracle** : OOB DNS via entité externe (`<!ENTITY xxe SYSTEM "http://...">`).
  Le serveur cible doit résoudre le domaine pour valider — pas de FP sur
  les serveurs qui parsent XML sans expansion d'entités.
- **Finding canonique** : XXE sur endpoint d'import
  `acme-corp.com/api/import` (POST `application/xml`) — payload OOB
  exfiltre `/etc/passwd` via paramètre externe. CRITICAL 9.8.
- **Différenciant** : la majorité des scanners cherchent du XXE sur les
  endpoints `Content-Type: application/xml` déclarés explicitement.
  Argos teste aussi les endpoints qui parsent XML sans le déclarer
  (typique des SOAP legacy).

#### `web.http2_smuggling` — HTTP/2 Request Smuggling — HIGH / Pro+

- **Oracle** : POST canary baseline avant et après le payload smuggling
  (H2.CL desync, H2.TE desync, CRLF dans headers H2). Distingue « le
  reverse-proxy ignore le header malicieux » (pas vulnérable) vs « le
  back-end est désynchronisé » (vulnérable). Quasi-zéro FP sur
  Cloudflare / CloudFront / Akamai.
- **Finding canonique** : H2.CL desync sur `acme.fr` derrière Cloudflare —
  la requête smugglée arrive au back-end avec un body tronqué et la
  prochaine requête légitime du pool est polluée. HIGH 8.1.
- **Différenciant** : tous les scanners DAST mainstream flagguent un
  HIGH générique sur n'importe quel site CDN dès qu'ils détectent du
  HTTP/2 — c'est le FP le plus fréquent du marché. La canary baseline
  d'Argos lève l'ambiguïté (cf. Bug #56 batch 13 post-v2).

#### `web.csrf` — Cross-Site Request Forgery — HIGH / **Free** ✓

- **Oracle** : parse HTML pour token + whitelist protections modernes
  (reCAPTCHA / hCaptcha / Turnstile / honeypot / double-submit) + test
  d'enforcement serveur (POST sans token ET POST avec token random
  doivent être rejetés). Délégation `SameSite` à `web.cookie_security`.
- **Finding canonique** : form de login sur `acme.fr/login` sans token
  CSRF — le serveur accepte un POST sans token ni Origin/Referer check.
  HIGH 8.0.
- **Différenciant** : Bug #19/#58 — détection des protections modernes
  (reCAPTCHA, Turnstile) → la plupart des scanners flagguent un FP sur
  les forms protégées par reCAPTCHA visible parce qu'ils ne reconnaissent
  pas la protection.

#### `web.race_condition` — Race Condition — HIGH/CRITICAL / Pro+

- **Oracle** : N requêtes concurrentes sur endpoints sensibles
  (`/coupon`, `/payment`, `/vote`, `/register`, `/checkout`) + check de
  variation de shape (status / unique bodies / unique lengths). Burst
  ≥ 50 % rate-limited = **inconclusive** (Bug #27/#50).
- **Finding canonique** : `acme-corp.com/api/redeem_coupon` avec
  10 POST concurrents → 6 succès au lieu de 1-2 (le coupon devrait être
  consommé après le premier succès). CRITICAL 9.1 paiement,
  HIGH 7.5 coupon, MEDIUM 5.3 vote.
- **Différenciant** : exigence de variation de shape dans les réponses
  → kill du FP « 15 réponses identiques flaggées HIGH ». Module rare
  sur le segment DAST mainstream — Acunetix et Detectify ne le
  couvrent pas.

#### `web.broken_auth` — Broken Authentication — HIGH / **Free** ✓

- **Oracle** : test de rate-limiting (10 tentatives/seconde acceptées →
  vulnérable), default credentials sur dictionnaire restreint, audit
  cookie (Secure / HttpOnly / SameSite / `__Host-`), pré-validation
  anti-bot via `response_classifier`.
- **Finding canonique** : `acme.fr/wp-login.php` accepte 10 tentatives
  par seconde sans rate-limit ni CAPTCHA — bruteforce credentials
  trivial via wordlist standard. HIGH 7.5.
- **Différenciant** : module Free, c'est délibéré. La sévérité reste
  ≤ HIGH (pas de prise de compte effective testée), mais le finding
  arrive immédiatement → premier signal de valeur pour un user Free qui
  hésite à monter en Pro.

#### `web.csp_bypass` — CSP Bypass Analysis — HIGH / **Free** ✓

- **Oracle** : parse de la directive `Content-Security-Policy`, détection
  des keywords dangereux (`'unsafe-inline'`, `'unsafe-eval'`), des
  endpoints JSONP exploités, des hosts wildcards trop permissifs
  (`*.cloudflare.com`). Grade A-F sortie pour le rapport.
- **Finding canonique** : `acme.fr` retourne `Content-Security-Policy:
  script-src 'self' 'unsafe-inline'` — bypass de toute protection XSS
  par injection de balise `<script>` inline. HIGH 7.1, grade D.
- **Différenciant** : grade A-F lisible immédiatement par un dev junior,
  alors qu'Acunetix sort un rapport CSP brut illisible. Le grade casse
  la friction « je sais que c'est mauvais mais je ne sais pas à quel
  point ».

### 3.2 Network — 4 zooms

#### `network.default_creds` — Default Credentials — CRITICAL / Pro+

- **Oracle** : tentative de connexion avec dictionnaire restreint
  (`admin/admin`, `root/root`, `mongo/`, `redis/`, etc.) sur SSH, FTP,
  MySQL, Redis, MongoDB, MS-SQL, Memcached, Elasticsearch, Consul, etcd.
  La preuve = connexion établie + listing au moins partiel.
- **Finding canonique** : MongoDB exposé sur `acme.fr:27017` sans auth —
  `db.adminCommand({listDatabases:1})` retourne 12 bases dont
  `prod-customers`. CRITICAL 9.8.
- **Différenciant** : le dictionnaire est volontairement court (10-20
  combos par service) pour éviter le bruit et passer sous les seuils
  fail2ban — c'est de l'audit, pas du bruteforce. Certains concurrents
  envoient 1000+ combos et se font ban en 10 secondes.

#### `network.ssl_audit` — TLS/SSL Hardening — CRITICAL / Pro+

- **Oracle** : wrapper `sslyze` (OpenSSL via `nassl` C, pas de
  réimplémentation Python crypto). Détection cert expiry via parse ASN.1,
  Heartbleed, ROBOT, ciphers faibles (RC4, DES, 3DES, MD5).
- **Finding canonique** : cert TLS de `acme.fr` expiré dans 30 jours
  (HIGH 6.5 si < 7 j, MEDIUM 5.3 < 30 j). Heartbleed détecté CRITICAL 9.8,
  ROBOT CRITICAL 9.1, ciphers RC4 acceptés HIGH 7.5.
- **Différenciant** : Bug #66 — délégation HSTS à
  `web.insecure_tls_redirect` (zéro triplication entre les modules).
  Pas de réimplémentation `testssl.sh` maison — on s'appuie sur le
  binaire `sslyze` upstream maintenu par Yahoo Sec.

#### `network.portscan` — Port Scan — HIGH/CRITICAL / Pro+

- **Oracle** : chaîne fallback `rustscan` (65 K ports/seconde) → `nmap -sV`
  → Python TCP brut. Mapping risque service intégré : CRITICAL pour
  Redis/Mongo/Elasticsearch sans auth, HIGH pour MySQL/PG/RDP/VNC/SMB.
  Threshold 20+ ports ouverts → finding « surface excessive ».
- **Finding canonique** : `acme.fr` répond sur le port `27017/tcp` avec
  `{ismaster:1}` MongoDB sans auth. CRITICAL 9.8.
- **Différenciant** vs `nmap` pur : `nmap` produit un dump brut, Argos
  contextualise avec une matrice service → risque (port ouvert sans
  auth = risque calibré, port ouvert avec auth = info uniquement). Un
  dev junior peut prioriser sans connaître la sécu réseau.

#### `network.kubernetes_api` — Kubernetes API exposé — CRITICAL / Pro+

- **Oracle** : signature JSON stricte. `/version` exige
  `gitVersion: v\d+\.\d+\.\d+`, `/api/v1/namespaces` exige
  `apiVersion:v1` + `items[].metadata`, kubelet `/pods` exige
  `PodList` canonical. Q1 filtering anti-bot/SPA/WordPress.
- **Finding canonique** : API server `acme-corp.com:6443` accepte une
  requête anonyme — `GET /api/v1/namespaces` retourne 200 + 5 namespaces
  dont `production`. CRITICAL 9.8 anonymous-auth, HIGH 7.5/8.1 sur
  kubelet.
- **Différenciant** : un probe k8s sur une cible non-k8s retourne
  souvent 200 HTML (page WordPress, SPA React) → la majorité des
  scanners flagguent un FP. Argos exige la signature canonique
  (apiVersion + items + ListMeta) avant de sortir un finding.

### 3.3 Recon — 3 zooms

#### `recon.source_map` — Source Maps exposées — HIGH / Pro+

- **Oracle** : pour chaque fichier JS minifié référencé (`<script src=`,
  imports webpack), tester `+ '.map'` et parser la sortie — extraction
  des `sources[]` et des `sourcesContent[]`. Signature ancrée sur le
  format JSON sourcemap v3.
- **Finding canonique** : `acme.fr/static/swiper-bundle.min.js.map`
  exposée — révèle l'arborescence du build webpack interne et le code
  source de 47 fichiers JS, dont des stratégies anti-fraude côté front.
  HIGH 7.5.
- **Différenciant** : module sous-coté qui produit énormément de valeur
  en démo. La plupart des stacks Vite / webpack / esbuild oublient de
  désactiver le sourcemap en prod par défaut → c'est trouvé sur ~30 %
  des cibles scannées en première passe.

#### `recon.git_exposure` — VCS Exposé — HIGH / Pro+

- **Oracle** : signature VCS stricte. `.git/HEAD` exige
  `^ref:\s+refs/heads/\S+` ou un SHA-1 40 chars ; `.git/config` exige
  `[core]` ; `.git/index` exige le magic `DIRC` ; `.git/packed-refs`
  exige `# pack-refs with:`. Q1 filtering anti-bot/SPA/WordPress en
  amont.
- **Finding canonique** : `acme-corp.com/.git/HEAD` exposé renvoie
  `ref: refs/heads/main` — repo dumpable via outils standards
  (`git-dumper`). HIGH 8.2 si ≥ 2 fichiers `.git/` accessibles,
  MEDIUM 6.1 si 1 seul.
- **Différenciant** : couvre aussi SVN (`.svn/entries`), Mercurial
  (`.hg/store`), Bazaar (`.bzr/`) — pas seulement Git. Et la signature
  ancrée tue les FP « page WordPress qui retourne du HTML sur
  `/.git/HEAD` ».

#### `recon.subdomain_takeover` — Subdomain Takeover bottom-up — HIGH / Pro+

- **Oracle** : match CNAME-only sur regex service dangling + absence
  d'A record + status 404/410/403 + body regex signature
  service-spécifique. Distinct de `cloud.dns_dangling` —
  `subdomain_takeover` scanne les **subdomains découverts par
  `recon.subdomain`** (énumération bottom-up), `cloud.dns_dangling`
  scanne les **CNAMEs détectés sur la target principale** (top-down).
- **Finding canonique** : `subdomain.acme-corp.com` →
  `takeover.github.io` + 404 + body « There isn't a GitHub Pages site
  here » → takeover GitHub Pages confirmé. HIGH 8.2.
- **Différenciant** : overlap partiel mais angles complémentaires avec
  `cloud.dns_dangling` — pas redondant. `recon.subdomain_takeover`
  trouve ce que les énumérateurs Amass / Subfinder lèvent comme
  candidats ; `cloud.dns_dangling` couvre les CNAMEs au niveau du
  domaine apex et des subdomains explicitement scannés.

### 3.4 SAST — 4 zooms

#### `sast.secrets` — Secrets multi-langage — CRITICAL / Pro+

- **Oracle** : règles trufflehog v3 + ruleset maison sur AWS, GCP,
  Azure, Stripe, GitHub, Slack, Discord, Twilio, OpenAI, Anthropic.
  Validation par regex ancrée + format check (entropie + checksum si
  applicable, ex : Stripe `sk_live_...`). Pas de FP sur les UUIDs ou
  hashs aléatoires.
- **Finding canonique** : AWS access key `AKIAIOSFODNN7EXAMPLE` hardcodée
  dans `config/legacy.py` (commit historique 2024-08, jamais retiré du
  repo). CRITICAL 9.0.
- **Différenciant** : plus précis que `git secrets` ou
  `detect-secrets` qui flagguent au moindre mot ressemblant à un secret.
  Argos check le format complet (longueur, entropie, checksum AWS).

#### `sast.dependency` — SCA — CVE via OSV.dev — CRITICAL / Pro+

- **Oracle** : parse `package.json`, `requirements.txt`, `pom.xml`,
  `go.mod`, `Cargo.toml`, `composer.json`, `Gemfile.lock` → résolution
  des versions exactes → query OSV.dev (Open Source Vulnerabilities,
  base de Google). Sortie : CVE + CVSS + version fixée + lien advisory.
- **Finding canonique** : `log4j-core 2.14.1` détecté dans `pom.xml`
  d'`acme-corp.com/api` — CVE-2021-44228 (Log4Shell), CVSS 10.0,
  fix `2.17.0`.
- **Différenciant** : OSV.dev couvre les écosystèmes mineurs (Maven,
  Packagist, RubyGems, Hex, Pub) que Snyk free tier ne couvre pas. Pas
  de licence policy enforcement ni de patch suggestion auto-PR — ça,
  c'est hors scope (cf. [§ 5 antimatière](#5-antimatière--ce-quargos-ne-fait-pas)).

#### `sast.iac` — Infrastructure-as-Code (Terraform / K8s / Helm / etc.) — HIGH/CRITICAL / Pro+

- **Oracle** : wrapper `checkov` CLI (`--directory <t> -o json`,
  1000+ règles Terraform / CloudFormation / K8s / Helm / Dockerfile /
  Serverless / ARM / Bicep / Ansible) + fallback 20+ regex critiques
  si le binaire est absent. Q5 downgrade dans paths `test/fixture`
  (kill du FP CI/CD).
- **Finding canonique** : Terraform Security Group ouvert dans
  `infra/network.tf` — `ingress { from_port = 0, cidr_blocks =
  ["0.0.0.0/0"] }` autorise tout l'internet sur tout port.
  HIGH/CRITICAL selon `CHECKOV_RULE_META`.
- **Différenciant** : pattern wrapper avec **graceful fallback**
  (timeout / OSError → catalogue regex local). Si checkov n'est pas
  installé sur le runner, Argos détecte quand même les 20 misconfigs
  les plus dangereux. Plus checks spéciaux Argos (S3 sans encryption,
  containers sans `resources.limits`).

#### `sast.docker` — Dockerfile / docker-compose Hardening — HIGH / Pro+

- **Oracle** : `hadolint` CLI JSON (80+ règles `DL*`/`SC*`) + fallback
  7 regex maison (`USER root`, `COPY .env`, `ARG <secret>`,
  `FROM image:latest`, `ADD <URL>`, `apt-get` sans cleanup,
  `ENV <secret>`). Suppression via `# nosec` / `# sechunter-ignore`.
- **Finding canonique** : Dockerfile de `acme.fr/Dockerfile` avec
  `USER root` sans drop ultérieur — container tourne avec privilèges
  inutiles, escalation triviale en cas de RCE applicative. HIGH 7.5.
- **Différenciant** : checks spéciaux Argos hors hadolint —
  `FROM image` sans tag = `:latest` implicite ; `EXPOSE` > 5 ports =
  surface excessive ; pas de `USER` = root par défaut. Plus 7 patterns
  docker-compose (`privileged: true`, `network_mode: host`,
  `docker.sock` mount, `cap_add: SYS_ADMIN`, `pid: host`).

### 3.5 API — 3 zooms

#### `api.bola` — Broken Object Level Authorization (IDOR) — CRITICAL / Pro+

- **Oracle** : énumération d'IDs séquentiels (`/orders/1`, `/orders/2`)
  ET d'UUIDs prédictibles (UUIDv1 timestamp-based) avec session valide
  utilisateur A. Si l'API retourne les données de l'utilisateur B sans
  401/403, finding confirmé. Pré-condition : `auth_recipe` configuré.
- **Finding canonique** : `GET acme-corp.com/api/v1/orders/{id}` retourne
  les commandes d'un autre `user_id` avec une session valide — IDOR
  exploitable, fuite RGPD massive si exploité. CRITICAL 9.1.
- **Différenciant** : la plupart des scanners DAST testent BOLA sur IDs
  numériques séquentiels uniquement. Argos teste aussi les UUIDv1
  prédictibles (chunk timestamp dans les 12 premiers caractères).

#### `api.openapi_audit` — Audit OpenAPI / Swagger — HIGH/CRITICAL / Pro+

- **Oracle** : 5 phases. (1) Discovery 13+ well-known paths + validation
  JSON `openapi/swagger/paths+info`. (2) Swagger UI 8 paths + markers
  HTML. (3) Ops sensibles `POST/PUT/PATCH/DELETE` sur `/admin/`,
  `/config/`, `/keys/`, `/secrets/` sans `security` requirement.
  (4) Schemas permissifs `additionalProperties: unrestricted` ou champs
  `role` / `is_admin` sans `enum` / `readOnly`. (5) Live reachability
  d'endpoints anonymes avec regex `"key":` dans la réponse.
- **Finding canonique** : `acme-corp.com/admin/users` (GET) retourne
  `[{"id":1, "password_hash":"...", "role":"admin"}]` sans auth —
  endpoint admin reachable anonymously, leak RGPD. CRITICAL 9.1.
- **Différenciant** : Q5 whitelist `/login/`, `/register/`, `/logout/`,
  `/health/`, `/status/`, `/docs/`, `/openapi.json`, `/.well-known/`
  → empêche le FP « endpoint public-by-design flaggé HIGH »
  (Bug #12/#23/#39).

#### `api.graphql_injection` — GraphQL Injection — MEDIUM/CRITICAL / Pro+

- **Oracle** : 4 oracles × 3 locations × 6 catégories. **Oracles** :
  OOB-blind (CallbackToken Log4Shell / curl / nslookup / `LOAD_FILE`),
  error-based regex ancrées (Q2 anti-substring), time-based double-fire
  4.5-8 s, boolean-blind `BaselineManager.diff` Jaccard ≥ 0.7
  (Q3 — 429/5xx = inconclusive). **Locations** : argument inline,
  variable GraphQL, directive `@skip`/`@include`. **Catégories** :
  sqli, nosqli, rce_cmd, rce_ssti, ldapi, xpathi.
- **Finding canonique** : SQLi boolean-blind sur
  `acme-corp.com/graphql` — query `user(id: $id)` avec payload
  `1 OR 1=1` produit body diff Jaccard ≥ 0.7 vs payload falsy.
  MEDIUM 6.5.
- **Différenciant** : whitelist Shopify Storefront via hostname +
  headers + co-occurrence ≥ 4 types canoniques (Bug #72/#73) +
  Q1 probe spec-GraphQL stricte avant tout test. **Aucun scanner DAST
  mainstream ne couvre 6 catégories × 3 locations × 4 oracles** sur
  GraphQL.

### 3.6 Cloud — 4 zooms

#### `cloud.metadata` — Cloud Metadata IMDS — CRITICAL / Pro+

- **Oracle** : exploitation de SSRF déjà détectée par `web.ssrf` ou
  paramètre URL réflexif → tentative d'accès à `169.254.169.254`
  (AWS IMDSv1), `metadata.google.internal` (GCP),
  `169.254.169.254/metadata` (Azure). Validation par signature de
  réponse anchored (champs `iam`, `instance-id`, `instance/zone`).
- **Finding canonique** : SSRF sur `acme-corp.com/api/preview?url=` →
  IMDSv1 AWS retourne le rôle IAM `prod-app-role` et les credentials
  `AKIAIOSFODNN7EXAMPLE` valides. CRITICAL 9.8.
- **Différenciant** : couverture des 3 cloud providers + IMDSv1 ET
  IMDSv2 (Azure exige le header `Metadata: true`, GCP le header
  `Metadata-Flavor: Google`). Acunetix a IMDS AWS uniquement.

#### `cloud.dns_dangling` — Subdomain Takeover via dangling CNAME — CRITICAL / Pro+

- **Oracle** : oracle NXDOMAIN multi-hop CNAME + signature body anchored
  + status-code whitelist sur **34 plateformes fingerprintées** : AWS S3,
  Heroku, Netlify, Vercel, Firebase, Shopify, Webflow, Tilda, Ghost,
  Surge, Fly.io, Statuspage, GitHub Pages, Azure App Service, etc.
  Combinaisons exotiques que Detectify et Acunetix ne couvrent pas
  toutes.
- **Finding canonique** : `legacy.acme-corp.com` →
  `bucket-prod.s3.amazonaws.com` (bucket S3 supprimé, oracle NXDOMAIN
  multi-hop confirme la déprovision) — un attaquant peut claim le bucket
  S3 et takeover le sous-domaine pour servir du contenu malicieux sous
  HTTPS valide. CRITICAL 9.8.
- **Différenciant** : la couverture 34 plateformes est inégalée sur le
  marché DAST mainstream. Detectify revendique ~28 plateformes, Acunetix
  ~15. Le différenciant n°1 d'Argos sur le segment subdomain takeover.

#### `cloud.iam` — IAM Misconfig (multi-cloud) — CRITICAL / Pro+

- **Oracle** : triple. (1) Parsing landing page via regex structurées
  (AWS `AKIA`/`ASIA` + secret, GCP `AIza` + JSON SA, Azure
  `client_secret`, GitHub PAT, Stripe live, Slack, PEM blocks).
  (2) Endpoints IAM-debug avec baseline probe randomisée
  `/__argos_probe_<nonce>` (catch-all detection) + signature stricte
  `/actuator/env` (`SPRING_ACTUATOR_ENV`), `/debug/vars`
  (`GO_DEBUG_VARS`), `/.env` (≥ 3 `KEY=VALUE`). (3) `AttackSurface`
  body scan complémentaire.
- **Finding canonique** : leak en clair sur la landing page de
  `acme-corp.com` — `<script> const AWS_KEY="AKIAIOSFODNN7EXAMPLE"...
  </script>`. CRITICAL 9.0.
- **Différenciant** : Bug #20 fix — soft-404 HTML ne matche plus comme
  `.env` (regex full-body ≥ 3 `KEY=VALUE` + Q1 anti-bot). Plus
  `is_placeholder()` Q5 qui rejette `YOUR_KEY` / `EXAMPLE` / `xxxxx`.
  Couvre AWS + GCP + Azure + GitHub + Stripe + Slack en un seul module.

#### `cloud.firebase_misconfig` — Firebase Open — HIGH/CRITICAL / Pro+

- **Oracle** : signature JSON stricte. RTDB `GET /.json` → 200 + JSON ≠
  `null` ; Firestore `GET /v1/projects/{pid}/databases/(default)/documents/`
  → 200 + `documents` ≥ 1 ; Storage
  `GET /v0/b/{pid}.appspot.com/o` → 200 + `items` ≥ 1 ; Auth signup
  `POST` weak password → 400 + error `WEAK_PASSWORD`
  (≠ `OPERATION_NOT_ALLOWED`).
- **Finding canonique** : RTDB public read sur
  `https://acme-projectid.firebaseio.com/.json` retourne la base
  utilisateurs complète (1 200 entrées avec emails et hashes). HIGH 7.5.
- **Différenciant** : project ID extrait depuis le hostname + parsing
  de `/__/firebase/init.json` + regex landing page +
  `is_placeholder()` Q5 sur `AIza` / `projectId`. Write probe
  `PUT`+`DELETE` uniquement si `aggressive=True` (anti-pollution data
  prod par défaut).

---

## 4. Couche IA-corrélation

L'IA-corrélation **n'est pas un module de scan**, c'est une **couche
post-scan** implémentée dans `sechunter/core/agent.py` (543 LOC) avec
4 prompts dédiés dans `core/prompts/`. Cinq rôles spécialisés se relaient
sur la même run pour transformer N findings indépendants en récit
d'attaque exploitable.

### 4.1 Architecture — les 5 rôles

| Rôle | Entrée | Sortie | Référence code |
|---|---|---|---|
| **Strategist** | URL + intel Phase 0 (WAF/CMS/stack/ports) | Stratégie d'attaque contextualisée (texte + JSON) | `prompts/strategist.txt` (93 lignes) |
| **Analyst** | Findings bruts par module | Findings normalisés et déduplicqués | `prompts/analyst.txt` |
| **Correlator** | Findings normalisés | Chaînes d'attaque (JSON dans `scan.agent_chain`) | `prompts/correlator.txt` |
| **Enricher** | Findings + chaînes | Remediation guidance par finding | `prompts/enricher.txt` |
| **Reporter** | Toute la matière | Markdown / PDF / HTML / JSON | `reporters/markdown.py:141` |

Tous les rôles consomment des tokens chez le **provider IA configuré par
le user (BYOK)** — voir [§ 4.7](#47-byok-multi-provider-ia--fallback-automatique).
Aucun appel sortant ne part vers une clé serveur Argos
(cf. [`DECISIONS.md` D-011](../../docs/DECISIONS.md#d-011)).

### 4.2 Strategist — Stratégie pré-scan adaptative

L'agent **Strategist** analyse WAF / CMS / stack et génère une stratégie
d'attaque contextualisée intégrée au rapport final pour donner au RSSI la
lecture experte de la cible. Phase 0 du scan détecte la stack
(Cloudflare, WordPress, Spring Boot, Lambda, etc.) → le Strategist
génère un JSON riche avec :

- **`waf_bypass_strategy`** — règles d'évasion adaptées au WAF détecté
- **`cms_specific_attacks`** — vecteurs d'attaque spécifiques au CMS
- **`excluded_vectors`** — vecteurs impossibles à exclure du scan
- **`modules_priority`** — ordre de priorisation des modules
- **`attack_vectors`** — vecteurs d'attaque pertinents pour la cible
- **`notes`** — synthèse texte libre (clé sauvegardée dans le rapport)

**Exemple de stratégie générée pour `acme.fr` derrière Cloudflare avec
WordPress :**

```json
{
  "waf_bypass_strategy": "Cloudflare présent : SQLi time-based blind (pas error-based), DOM XSS (Cloudflare ne filtre pas le DOM), payloads encodés double-URL",
  "cms_specific_attacks": [
    "Énumération users /wp-json/wp/v2/users",
    "Bruteforce XML-RPC /xmlrpc.php",
    "Scan plugins /wp-content/plugins/",
    "wp-cron.php SSRF"
  ],
  "excluded_vectors": [
    "SMB (port 445 fermé)",
    "FTP (port 21 fermé)",
    "RFI (Cloudflare bloque payloads directs)"
  ]
}
```

> **Note implémentation (figé — D-013).** Aujourd'hui le filtrage
> temps-réel des modules est piloté par l'intel Phase 0 brute
> (ports / CMS détectés via `_filter_modules_by_intel`,
> `orchestrator.py:538`) qui exclut déjà ~90 % des vecteurs impossibles
> avant le scan. La stratégie LLM enrichit le rapport pour audit. La
> **fusion programmatique** entre la stratégie LLM (clés
> `modules_priority` + `excluded_vectors`) et le pipeline de filtrage est
> sur la roadmap technique côté SecHunter (ticket
> `feat/strategist-prescriptive-routing`, ~30 LOC).

**Différenciant** : aucun scanner DAST mainstream (Acunetix, Detectify,
Burp, Intruder) ne livre une lecture experte LLM-driven dans le rapport.
L'argument cold call : « le rapport Argos contient la stratégie d'attaque
qu'un pentester senior aurait écrite après avoir étudié votre stack ».

### 4.3 Chaînes d'attaque (Correlator)

> **Définition canonique** (figée — [D-012](../../docs/DECISIONS.md#d-012-d%C3%A9finitions-canoniques-watch-et-cha%C3%AEnes-dattaque-kb)) : à la fin de chaque scan,
> l'agent IA reçoit la liste complète des findings et identifie les
> **séquences exploitables ensemble** au-delà des CVSS individuels.
> Chaque chaîne a : un score de criticité (souvent ≥ max des findings
> individuels), un PoC step-by-step reproductible, la liste des findings
> constitutifs linkés, une remédiation pointant le maillon faible
> (souvent le plus simple à corriger casse toute la chaîne).
> **Disponible Pro / Team / Pro Max.** Nécessite l'IA en mode
> corrélation (BYOK user).

**Format de sortie** : string JSON sérialisée (`json.dumps()`) stockée
dans `scan.agent_chain` (`models.py:226`). Pas de dataclass typée — le
prompt `correlator.txt` dicte le schéma. Format brut, **machine-readable
pour les bots / pipelines + lisible humain dans le rapport HTML**.

**Schéma canonique :**

```json
{
  "attack_chains": [{
    "name": "XSS Stocké → Vol Session Admin → Accès Panel",
    "severity": "CRITICAL",
    "combined_cvss": 9.3,
    "findings": ["F1", "F2", "F3"],
    "kill_chain_phase": "exploitation → credential_access → privilege_escalation",
    "steps": [
      "Étape 1 : injecter <script>...</script> dans le champ commentaire",
      "Étape 2 : admin visite la page de modération",
      "Étape 3 : cookie de session admin volé via fetch() vers OOB"
    ],
    "impact": "Compromission totale du panel admin",
    "likelihood": "HIGH",
    "mitre_tactics": ["Initial Access (TA0001)", "Credential Access (TA0006)"],
    "mitre_techniques": ["T1189", "T1539"],
    "prerequisites": "Compte utilisateur ou inscription ouverte",
    "combined_poc": "1. Crée commentaire avec XSS → 2. Admin visite → 3. Cookie volé → 4. Accès /admin"
  }],
  "overall_risk": {
    "score": 8.5,
    "assessment": "Risque élevé — multiples chemins d'exploitation",
    "priority_chain": "XSS Stocké → Vol Session Admin → Accès Panel"
  }
}
```

**Différenciant** : aucun scanner DAST mainstream ne corrèle les
findings en kill chain narratif scénarisé avec mapping MITRE ATT&CK
(tactics + techniques) et combined CVSS recalculé. Acunetix livre une
liste, Argos livre un **récit exploitable** que le RSSI peut donner
direct au dev pour priorisation.

### 4.4 Watch — Surveillance continue (Pro Max only)

> **Définition canonique** (figée — [D-012](../../docs/DECISIONS.md#d-012-d%C3%A9finitions-canoniques-watch-et-cha%C3%AEnes-dattaque-kb)) :
> re-scan automatique d'une cible à intervalle configurable
> (6 h / 24 h / hebdo) avec alerte sur les changements : nouveau finding
> ≥ sévérité minimale, finding RESOLVED qui réapparaît (régression),
> score de risque global qui se dégrade. Canaux : Slack webhook, email,
> push dashboard. Historique conservé en timeline
> (`/watch/<target>/timeline`).
> **Pro Max uniquement.**

**Implémentation** : `core/watcher.py` avec scheduler ARQ + diff
signature stable entre runs successifs. Un finding est considéré
« nouveau » si sa signature `(module, target, oracle_proof_hash)` n'était
pas dans le run précédent. Évite le bruit des findings identiques
re-détectés à chaque run.

**Cas d'usage type** : Sarah Head of Sec qui gère 15 services en prod et
veut être prévenue dès qu'un service prend une nouvelle vuln CRITICAL
sans avoir à relancer manuellement chaque semaine.

**Pourquoi Pro Max only** : consomme des ressources serveur (scans en
background, scheduler ARQ, queues persistantes) non absorbables sur Pro
39 €. Le cas d'usage = équipe sécu qui veut du monitoring continu =
profil Sarah / Pro Max naturel.

### 4.5 Risk score A-F déterministe

L'argument différenciant face aux scores opaques d'Acunetix : **Argos
publie sa formule** dans `core/risk_score.py:15-44, 79-159`. Un dev
junior peut la recalculer à la main pour chaque rapport.

**Constantes :**

```python
_SEVERITY_WEIGHT = {CRITICAL: 10.0, HIGH: 7.0, MEDIUM: 4.0, LOW: 1.5, INFO: 0.0}
_POC_MULTIPLIER = 2.0     # bonus par finding avec PoC > 10 chars
_CHAIN_MULTIPLIER = 3.0   # bonus par chaîne d'attaque détectée
_MAX_RAW = 100.0
```

**Formule (sommes, pas multiplications) :**

```
findings_score = Σ severity_weight pour chaque finding non-FP
poc_score      = (count findings avec poc > 10 chars) × 2.0   ← s'AJOUTE
chain_score    = (count chaînes d'attaque) × 3.0              ← s'AJOUTE
raw_score      = min(findings_score + poc_score + chain_score, 100.0)
normalized     = round(max(0, 10.0 - (raw_score / 100.0) × 10.0), 1)
```

**Table grade A-F** (mapping par seuil, **pas formule continue**) :

| Grade | Seuil `raw_score` | Score normalisé | Couleur |
|---|---|---|---|
| **A — Excellent** | ≤ 2.0 | 9.8 — 10.0 | vert |
| **B — Bon** | ≤ 8.0 | 9.2 — 9.8 | vert clair |
| **C — Moyen** | ≤ 20.0 | 8.0 — 9.2 | jaune |
| **D — Mauvais** | ≤ 40.0 | 6.0 — 8.0 | orange |
| **F — Critique** | > 40.0 | 0.0 — 6.0 | rouge |

**Exemple concret** : 1 CRITICAL + 2 HIGH + 3 MEDIUM + 2 PoC + 1 chaîne
d'attaque → `raw_score = 10 + 14 + 12 + 4 + 3 = 43.0` → **Grade F,
normalized 5.7/10**.

**Différenciant** : Acunetix publie un score sans formule. Un RSSI ne
peut pas le contester ni le défendre en audit. Le score Argos est
recalculable, donc défendable.

### 4.6 Compliance mapping triple framework

Triple mapping framework, sortie **factuelle** (figé —
[D-014](../../docs/DECISIONS.md#d-014--compliance-mapping-sortie-factuelle-count-par-exigence-pas-de-score--marketing)) :

| Framework | Version | Couverture |
|---|---|---|
| **OWASP Top 10** | 2021 | Clés `A01:2021` à `A10:2021` (10 catégories) |
| **PCI-DSS** | 4.0 | Refs : 1.2.1, 2.2.1, 3.4.1, 4.2.1, 6.2.4, 7.2.2, 8.3.1, 10.2.1, 10.3.1, 11.3.1 |
| **RGPD** | — | 5 articles : Art. 5(1)(f) (intégrité/confidentialité), Art. 25 (privacy by design), Art. 32 (sécurité du traitement — majoritaire), Art. 33 (notification violation), Art. 34 (communication aux personnes) |

Sortie : count de findings par exigence violée, avec liste des findings
liés. **Pas de score % de couverture** — c'est un parti pris
(cf. D-014).

**Exemple sortie JSON :**

```json
{
  "owasp": {
    "A03:2021": {"name": "Injection", "count": 2, "findings": ["F1", "F4"]},
    "A01:2021": {"name": "Broken Access Control", "count": 1, "findings": ["F7"]}
  },
  "pci_dss": {
    "6.2.4": {"name": "Prevent common software attacks", "count": 2, "findings": ["F1", "F4"]}
  },
  "rgpd": {
    "Art. 32": {"name": "Sécurité du traitement", "count": 3, "findings": ["F1", "F4", "F7"]}
  }
}
```

**Implémentation** : `core/compliance_mapper.py` (543 LOC, 143+ mappings
CWE → exigence). Le mapping est statique côté code, pas généré par LLM
(traçable et auditable).

**Différenciant** : « pas de score marketing creux. On vous donne la
matière brute pour votre rapport d'audit. » Argument vendeur fort pour
Sarah Head of Sec qui prépare une certif SOC2 / ISO 27001 — son
auditeur exigera le détail finding-par-exigence de toute façon. Argos le
livre directement, les concurrents qui sortent un score % obligent à
re-faire le travail à la main.

### 4.7 BYOK multi-provider IA + fallback automatique

Argos n'embarque **aucune clé IA serveur**. Tous les appels (Strategist,
Analyst, Correlator, Enricher, Reporter) sont faits avec **les clés API
que le user a configurées dans Settings**. Voir
[D-011](../../docs/DECISIONS.md#d-011--ia-fallback-auto-pro-max--byok-seul-pas-de-cl%C3%A9-serveur-argos).

**Providers supportés** (`sechunter/core/ai/fallback.py`) :

- **Anthropic** — Claude 4.X (recommandé pour Correlator, meilleur en
  raisonnement long-context)
- **OpenAI** — GPT-4 / GPT-5
- **Google** — Gemini 1.5 / 2.0
- **DeepSeek** — DeepSeek Coder / DeepSeek V3

**Stockage des clés** : chiffrement AES-256-GCM via
`sechunter/core/crypto_service.py`. Les clés ne sortent jamais de la DB
en clair, elles ne sont déchiffrées qu'au moment de l'appel HTTP.

**IA fallback auto (Pro Max only)** : bascule automatique entre les
clés configurées en cas de rate-limit (429) ou erreur 503. Pré-condition
documentée dans la KB : **configurer ≥ 2 providers** pour que le
fallback soit utile. Si tous les providers configurés échouent, le scan
continue en mode dégradé (findings sans corrélation IA / chaînes
d'attaque).

**Différenciant** : zero vendor lock-in IA. Argument enterprise
différenciant pour les fintech / santé / défense qui ont des contraintes
de souveraineté sur les providers IA (ex : Mistral / Anthropic Europe
obligatoire, OpenAI banni). Argos s'adapte au choix du client, pas
l'inverse.

---

## 5. Antimatière — ce qu'Argos ne fait PAS

Cadre vendeur autant que limites assumées : un prospect qui confond
scanner DAST et plateforme XDR/SIEM/SOAR doit être recadré rapidement
pour éviter le mismatch d'attentes. Ce qui suit est exhaustif (8
hors-scope vérifiés dans le code) et **canonique pour SupportBot
et OutboundBot**.

### 5.1 Pas de BAS / Breach Attack Simulation

**Ce que c'est** : simulation continue de scénarios attaquant interne
type SafeBreach, AttackIQ, Cymulate — l'outil joue des kill chains
adverses sur l'infra du client pour valider la détection EDR / SIEM.

**Pourquoi pas Argos** : Argos est un scanner **externe** DAST/SAST/cloud
qui cherche les vulns exploitables. La simulation adversariale interne
est un autre métier (exécution de payloads dans des environnements
contrôlés, intégration EDR, scoring MITRE ATT&CK temps réel).

**Vers quoi rediriger** : SafeBreach, AttackIQ, Cymulate (segment
enterprise). Pour les budgets PME, **Atomic Red Team** (open source) +
le SOC interne du client.

### 5.2 Pas d'EDR / runtime detection

**Ce que c'est** : agent installé sur les hosts (workstations, serveurs)
qui détecte en temps réel les comportements malicieux au runtime
(injection process, tampering registry, exfiltration). CrowdStrike,
SentinelOne, Defender XDR.

**Pourquoi pas Argos** : Argos ne touche pas aux hosts. Aucun agent à
installer, aucune télémétrie continue. C'est délibéré : Argos respecte
le périmètre du DAST + scan externe.

**Vers quoi rediriger** : CrowdStrike Falcon, SentinelOne, Microsoft
Defender for Endpoint. Pour open source / budget contraint :
**Wazuh** (gratuit, self-host).

### 5.3 Pas de SCA full écosystème (Snyk / Dependabot grade)

**Ce que c'est** : analyse exhaustive des dépendances avec licence
policy enforcement (Apache 2.0 OK, GPL refusé en prod), patch suggestion
auto-PR (« upgrade `express` 4.17.1 → 4.18.2 fixe CVE-2022-X »),
provenance check (sbom signé via Sigstore).

**Pourquoi pas Argos** : `sast.dependency` couvre les CVE via OSV.dev
(cf. [§ 3.4](#34-sast--4-zooms)) — c'est suffisant pour détecter les
vulns. Mais **pas de licence policy**, **pas de patch suggestion auto-PR**,
**pas de provenance check**. C'est un autre métier (DevSecOps tooling,
intégration CI/CD profonde, gestion de politiques par projet).

**Vers quoi rediriger** : **Snyk** (segment fintech / scaleup), **GitHub
Dependabot** (gratuit, intégré GitHub), **Renovate** (open source,
self-host).

### 5.4 Pas de Mobile (MASA / iOS / Android)

**Ce que c'est** : scan d'APK / IPA, runtime mobile (Frida, Objection),
testing OWASP MASVS (Mobile Application Security Verification Standard),
audit MASA (Mobile App Security Assessment).

**Pourquoi pas Argos** : pas dans le repo. Aucun module mobile, aucun
scan binaire APK/IPA, aucun runtime mobile. Choix produit délibéré : on
vise la cible web/cloud/network, pas le mobile.

**Vers quoi rediriger** : **NowSecure**, **Appknox**, **Ostorlab**.
Ou audit manuel via consultant **OWASP MASVS-certifié**.

### 5.5 Pas de honeypot / déception

**Ce que c'est** : déploiement de leurres (faux serveurs, faux
credentials, faux endpoints) pour piéger les attaquants et collecter
des IoC. Thinkst Canary, TrapX, Illusive.

**Pourquoi pas Argos** : Argos est offensif (cherche les vulns), pas
défensif (piège les attaquants). Métier complètement différent — la
déception demande une infra de leurres distribuée + corrélation alerting
SIEM.

**Vers quoi rediriger** : **Thinkst Canary** (commercial, propre et
focused) ou **OpenCanary** (open source, self-host).

### 5.6 Pas de pentest manuel humain

**Ce que c'est** : prestation de service où un pentester humain audite
manuellement la cible (recon avancée, chaînes d'attaque créatives,
business logic complexe non scannable, social engineering).

**Pourquoi pas Argos** : produit 100 % automatisé. Pas de service
conseil, pas d'équipe de pentesters humains à louer. **C'est délibéré
et c'est notre différenciation prix** : un pentest manuel coûte
5-50 k€ pour 5-10 jours homme, Argos couvre la partie automatisable
pour 39-249 €/mois.

**Vers quoi rediriger** : **YesWeHack** (BugBounty FR), **Synack**
(pentest as a service), **Cobalt** (pentest distributed), ou un
consultant indépendant sur LinkedIn (réseau pentest FR actif).

### 5.7 Pas de WAF tuning ni patching automatique

**Ce que c'est** : génération automatique de règles WAF (Cloudflare,
ModSecurity, AWS WAF) à partir des findings, push automatique vers le
WAF pour bloquer la vuln en attendant le patch dev. Patching virtuel.

**Pourquoi pas Argos** : Argos détecte, ne corrige pas. La remédiation
sort en suggestion textuelle dans le rapport (via l'Enricher,
[§ 4.1](#41-architecture--les-5-r%C3%B4les)) mais n'agit pas sur l'infra.
Pas d'intégration push WAF, pas de génération automatique de règles
ModSecurity.

**Vers quoi rediriger** : **Cloudflare WAF Managed Rules** (pour
patching virtuel sur les CVE connus), **AWS WAF Bot Control**, ou
travail interne avec l'équipe DevOps du client.

### 5.8 Pas de gestion d'incident / SOAR

**Ce que c'est** : Security Orchestration, Automation and Response —
workflow ticket sur incident détecté, orchestration playbook réponse
(isoler le host, rotater la clé, notifier l'équipe), SLA tracking,
post-mortem automatisé. Splunk SOAR, Cortex XSOAR, Tines.

**Pourquoi pas Argos** : pas de workflow ticket, pas d'orchestration
playbook, pas de SLA tracking. Argos sort des findings, c'est au SOC du
client de les prendre en charge.

**Vers quoi rediriger** : **Tines** (segment scaleup, no-code), **Cortex
XSOAR** (Palo Alto, segment enterprise), ou ticketing classique
**Linear** / **Jira** + intégration via webhook (Argos peut pousser
les findings vers un webhook custom — voir [§ 4.7](#47-byok-multi-provider-ia--fallback-automatique) pour les
intégrations Pro Max).

---

## 6. Roadmap

Argos évolue rapidement et la majorité des marqueurs roadmap sont
internes, donc **pas annonçables publiquement**. Position canonique
(figée) :

> « Argos évolue rapidement. Pour la roadmap détaillée et discuter d'un
> module spécifique à votre besoin, contactez-nous via
> [`contact@omnividens.fr`](mailto:contact@omnividens.fr) ou demandez un
> custom contact (≥ 5 000 €/mois) qui inclut un canal direct sur les
> priorités produit. »

**Mentions publiques limitées :**

- **Pricing v2 Team tier** — branche actuelle `feat/pricing-v2-team-tier`,
  livraison imminente (cf. [`pricing.md`](pricing.md) qui acte déjà la
  grille v2)
- **Argos Ops** — flotte d'agents IA pour acquisition / conversion /
  support / admin du SaaS lui-même (repo séparé
  [`Omnividens-argos/argos-ops`](https://github.com/Omnividens-argos/argos-ops)).
  **Pas un module de scan** — c'est une couche business interne. À
  mentionner uniquement si un prospect demande comment on gère le
  support 24/7 sans équipe humaine

**Anti-FUD inverse** : pas de sur-promesse roadmap → pas de déception →
pas de churn. La refonte v2 du produit est terminée (67/67 sessions +
16 batches post-v2). Tout ce qui est annoncé dans cette KB est
**déjà livré et scannable aujourd'hui**.

---

## 7. Annexe machine-readable

Pour SupportBot et tout pipeline qui a besoin d'une
sortie **structurée** sur les modules (« le module X est-il dans le tier
Free ? », « combien de modules dans la catégorie cloud ? »), le fichier
[`argos_modules.raw.json`](argos_modules.raw.json) est l'annexe
canonique.

### 7.1 Architecture RAG hybride pour SupportBot

| Question type | Source | Comment retrieve |
|---|---|---|
| « Décris-moi le module `web.sqli` » | `argos_features.md` | Sémantique pgvector (cf. [§ 3.1](#31-web-dast--12-zooms)) |
| « Le module `cloud.iam` est-il dans Free ? » | `argos_modules.raw.json` | Lookup structuré `{name, free}` |
| « Combien de modules dans la catégorie sast ? » | `argos_modules.raw.json` | Aggregation par `category` |
| « Quel est le différenciant `web.http2_smuggling` ? » | `argos_features.md` § 3.1 | Sémantique pgvector |
| « Liste tous les modules CRITICAL Pro+ » | `argos_modules.raw.json` | Filter `free == false` |

**Décision SupportBot (P6)** : retrieve sémantique sur les `.md` de la
KB pour les questions descriptives (le contexte vectoriel donne la
nuance), retrieve structuré sur le `.json` pour les questions
factuelles (le lookup direct évite l'hallucination sur des chiffres).

### 7.2 Schéma JSON

```json
[
  {
    "name": "web.sqli",
    "category": "web",
    "description": {
      "description": "SQL Injection (blind + error-based)",
      "category": "web",
      "target_types": ["url"]
    },
    "free": false
  },
  ...
]
```

Total : **139 entrées**. La clé `name` suit le format canonique
`category.module` (cf. [§ 2](#2-catalogue-exhaustif-139-modules)). Le
champ `free: true` apparaît sur **41 modules** (cf. note technique
[§ 1.3](#13-gating-free-vs-payant--41--139)).

### 7.3 Regénérer le JSON

Le fichier est un **dump manuel** depuis le registry SecHunter — il
n'existe pas de pipeline automatisé qui le tient à jour. Si SecHunter
ajoute / retire / renomme un module, il faut relancer la commande
ci-dessous depuis le repo SecHunter (`~/Desktop/the good guy/`) :

```bash
cd ~/Desktop/the\ good\ guy/
uv run python -c "
import json
from sechunter.core.scan_profiles import MODULE_DESCRIPTIONS
from sechunter.core.plans import _FREE_MODULES
out = []
for name, desc in MODULE_DESCRIPTIONS.items():
    cat = name.split('.')[0]
    out.append({'name': name, 'category': cat, 'description': desc, 'free': name in _FREE_MODULES})
with open('/c/Users/pauzzle/Desktop/argos-ops/data/knowledge_base/argos_modules.raw.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(f'wrote {len(out)} modules')
"
```

Après regénération : si le compte change, mettre à jour
[§ 1.2](#12-compte-exact--139-modules-sur-6-cat%C3%A9gories),
[§ 1.3](#13-gating-free-vs-payant--41--139),
[`pricing.md`](pricing.md) (4 occurrences `139` et `41`),
[`tone_of_voice.md`](tone_of_voice.md) (3 occurrences `139`).

### 7.4 État du fichier

| Champ | Valeur au 2026-05-08 |
|---|---|
| Total modules | 139 |
| Free | 41 (registry actif ; `_FREE_MODULES` théorique = 42, ghost `network.portscan_light`) |
| Catégories | 6 (web, network, recon, sast, api, cloud) |
| Source registry | `sechunter/core/scan_profiles.py` `MODULE_DESCRIPTIONS` |
| Source gating | `sechunter/core/plans.py` `_FREE_MODULES` |
| Dernière regen | 2026-05-08 (P3-M2) |
