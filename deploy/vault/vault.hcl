# Vault — mode serveur, stockage fichier (DAT §4.1 : jamais -dev hors dev).
ui = true

# mlock empêche l'écriture des secrets (KEK) sur le disque via le swap.
# Le garder ACTIF est la posture sûre. Il exige :
#   - la capacité IPC_LOCK (déjà accordée dans docker-compose.yml), ET
#   - une limite memlock suffisante (relevée via `ulimits` dans le compose).
#
# REPLI DÉVELOPPEMENT UNIQUEMENT : si votre hôte ne peut pas verrouiller la
# mémoire (Docker Desktop / WSL2 / rootless), passez cette valeur à `true`.
# En contrepartie, désactivez le swap sur l'hôte OU réservez ce mode au dev :
# en production, mlock doit rester actif (le secret des KEK en dépend).
disable_mlock = false

storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true   # TLS terminé au reverse proxy edge ; réseau interne uniquement
}

# Adresse d'API annoncée (lève l'avertissement « no api_addr value specified »).
api_addr = "http://vault:8200"

# Scellé au démarrage : descellement par quorum via `make unseal` (docs/runbook-vault.md).
