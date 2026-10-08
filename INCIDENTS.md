# Documentation d'Incidents & Post-Mortem — ChocoBot

## 1. Dispositif de Supervision
- **Journalisation applicative :** Module `logging` enregistrant l'activité et les erreurs dans `app.log`.
- **Suivi d'erreurs (APM) :** Sentry SDK sur FastAPI pour la capture automatique des exceptions.
- **Alerting :** Notification automatique par e-mail lors de l'apparition d'une nouvelle issue Sentry.

---

## 2. Post-Mortem : Incident #01 — Indisponibilité de l'API LLM & Latence

### Diagnostic
- **Alerte :** Mail Sentry + déclenchement d'une issue `RuntimeError: Panne simulée : 503 service unavailable`.
- **Cause racine :** Échec d'appel au service d'inférence (Ollama) et sur-latence réseau.

### Résolution
1. **Pression absorbée par le Cache FAQ :** Maintien du service sur les questions courantes sans solliciter le LLM.
2. **Encapsulation défensive :** Capture de l'exception avec `sentry_sdk.capture_exception()`.
3. **Mode dégradé (Fallback UX) :** Renvoi d'un message d'indisponibilité temporaire au client au lieu d'une erreur HTTP 500.
4. **Monitoring actif :** Intégration du test de connexion Ollama sur l'endpoint `/health`.

---

## 3. Post-Mortem : Incident #02 — Reconstitution et gestion des données corrompues

### Fiche de l'incident
- **Sévérité :** Faible à Moyenne.
- **Type d'erreur :** Payload JSON malformé / Invalidation de schéma Pydantic sur `/profile`.

### Diagnostic & Cause Racine
Envoi de requêtes HTTP POST contenant des types de données invalides ou des champs requis manquants. Faute de traitement spécifique des logs, ces erreurs de validation passaient silencieusement en HTTP 422 sans alerte de sécurité ou d'intégrité.

### Résolution
1. **Interception globale :** Ajout d'un `@app.exception_handler(RequestValidationError)` dans `app.py`.
2. **Alerting Sentry :** Envoi systématique d'une alerte Sentry via `sentry_sdk.capture_message()` lors d'un rejet de payload.
3. **Réponse normalisée :** Renvoi d'un code HTTP 400 explicite pour guider le client sans exposer la structure interne de la base de données.