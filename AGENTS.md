# TARS — Instructions de développement

## Projet

TARS est un assistant vocal de type Jarvis, développé en **Python + PySide6 + QML**, avec pour objectif de fonctionner **100 % en local**.

L'application doit être conçue pour rester utilisable sans connexion Internet après l'installation des modèles nécessaires.

## Langue

* La langue par défaut de l'application est le **français**.
* L'anglais doit également être supporté.
* La langue doit pouvoir être modifiée depuis l'interface.
* La langue utilisée par le TTS doit être configurable facilement dans la configuration de l'application.
* La voix française est la configuration initiale de Pocket TTS.

## IA locales

TARS utilise actuellement trois modèles locaux :

* **TTS** : Pocket TTS de Kyutai
* **STT** : Parakeet TDT 0.6B v3
* **Decision LLM** : Needle2, utilisé pour déterminer quel agent contacter

Chaque IA possède son propre provider dans `providers/`.

Structure attendue :

```text
providers/
├── tts/
│   ├── adapter.py
│   └── pocket_tts.py
├── stt/
│   ├── adapter.py
│   └── parakeet.py
└── llm/
    ├── adapter.py
    └── needle.py
```

### Règle impérative concernant les providers

Les autres parties de l'application **ne doivent jamais importer ou appeler directement** :

* `pocket_tts.py`
* `parakeet.py`
* `needle.py`

Seul le fichier `adapter.py` correspondant peut appeler son modèle.

Le reste de l'application doit uniquement communiquer avec les `adapter.py`.

Les adapters doivent rester **très courts et simples**. Leur unique responsabilité est d'appeler le modèle correspondant et d'exposer une interface stable au reste de l'application.

Cette architecture doit permettre de remplacer facilement un modèle ou un provider sans modifier le reste de l'application.

## Fonctionnement hors ligne

TARS doit pouvoir fonctionner sans Wi-Fi après installation des modèles.

Depuis l'interface, lorsque la connexion Internet est disponible, l'utilisateur doit pouvoir :

1. télécharger/installer les modèles nécessaires ;
2. vérifier leur présence ;
3. utiliser ensuite TARS sans connexion Internet.

Le code ne doit donc pas supposer qu'une connexion Internet est disponible au démarrage ou pendant l'utilisation normale.

## Interface

* Utiliser **PySide6 + QML** pour l'interface.
* Respecter l'architecture existante du projet.
* Pour toute aide concernant PySide6/QML, consulter le skill correspondant dans le dossier `skills`.
* Pour la rédaction ou modification du README, consulter le skill `Markdown README` dans le dossier `skills`.

## Règles générales

* Respecter l'architecture existante avant d'introduire une nouvelle structure.
* Privilégier des composants simples, modulaires et facilement remplaçables.
* Ne pas dupliquer la logique des providers ailleurs dans le projet.
* Ne pas ajouter de dépendance inutile.
* Vérifier que les fonctionnalités continuent de fonctionner en mode hors ligne.
* Avant de terminer une tâche, vérifier les erreurs et les fonctionnalités concernées.
* Garder l'application légère, donc penser à faire des optimisation si possible à ce niveau.
* Concernant Git, tu as l'INTERDICTION d'utiliser quelconque commande Git.
