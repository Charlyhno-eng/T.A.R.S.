# T.A.R.S.

Assistant vocal personnel, base légère pour construire un assistant de type Jarvis. Application Python 3.12 avec PySide6 et interface QML.

## État de l’application

- Conversation vocale : capture au maintien du contrôle central, transcription locale avec Parakeet TDT 0.6B v3, réponse via GLM 5.3 Flash (API Z.AI), synthèse locale avec Pocket TTS.
- Français et anglais sont disponibles. La langue est mémorisée ; les modèles locaux se téléchargent depuis l’interface et fonctionnent ensuite hors ligne. GLM requiert une connexion et une clé API.
- L’interface affiche l’état d’écoute, de traitement et de parole, avec tête robot animée. Les réglages permettent de choisir la langue et gérer la clé API.

## Technologies et organisation

- Dépendances Python gérées par `uv` dans `pyproject.toml` ; UI en QML sous `src/ui`.
- `src/core` contient contrôleur, services audio, réglages et orchestration ; `src/providers/{stt,tts,llm}` contient les fournisseurs et leurs adaptateurs.
- Tests dans `tests/`. Lancement : `uv run python src/app.py` ; vérifications : `uv run pytest`.
- Préférences dans `config/config.toml`, clé Z.AI dans `config/llm_api_key` (fichier local ignoré par Git). Ressources vocales dans `~/.tars`.

## Règles de travail

- Suivre les conventions existantes et limiter les changements au ticket.
- Garder ce fichier concis ; le mettre à jour lorsque l’architecture ou les capacités durables changent.
