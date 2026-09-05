from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class TTSAdapter(ABC):
    """
    Interface commune pour les providers Text-To-Speech de T.A.R.S.
    """

    @abstractmethod
    def speak(self, text: str) -> Path:
        """
        Génère une réponse vocale et retourne le chemin du fichier audio.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """
        Libère les ressources du provider.
        """
        raise NotImplementedError
