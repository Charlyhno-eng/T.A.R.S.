from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable


logger = logging.getLogger("TARS.Needle")


class NeedleProvider:
    """Technical local access to the Needle 2 tool-calling engine."""

    ENGINE_FILE_NAMES = {
        "darwin": "libneedle.dylib",
        "win32": "libneedle.dll",
    }

    DEFAULT_ROUTES = (
        "greeting",
        "wellbeing",
        "identity",
        "thanks",
        "help",
        "time",
        "date",
        "acknowledge",
        "unknown",
    )

    def __init__(
        self,
        data_directory: Path,
        agent_definitions: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self._data_directory = data_directory
        self._agent_definitions = agent_definitions
        self._agent: Any | None = None
        self._invalid_envelope_reported = False

    @property
    def model_available(self) -> bool:
        return self._engine_path.is_file()

    @property
    def _engine_path(self) -> Path:
        name = self.ENGINE_FILE_NAMES.get(sys.platform, "libneedle.so")
        return self._data_directory / name

    def download(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        if on_status:
            on_status("Téléchargement de Needle 2...")
        os.environ["NEEDLE_TELEMETRY"] = "0"
        try:
            from needle.agent import fetch
        except ImportError as exc:
            raise RuntimeError(
                "La dépendance Needle 2 est absente. Exécutez "
                "'pip install -r requirements.txt' puis relancez T.A.R.S."
            ) from exc
        self._data_directory.mkdir(parents=True, exist_ok=True)
        fetch.fetch_library(dest_dir=str(self._data_directory), generation=2)

    def load(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        if self._agent is not None:
            return
        if not self.model_available:
            raise RuntimeError("Le moteur local de Needle 2 est introuvable.")
        if on_status:
            on_status("Chargement local de Needle 2...")
        os.environ["NEEDLE_TELEMETRY"] = "0"
        try:
            import needle
        except ImportError as exc:
            raise RuntimeError(
                "La dépendance Needle 2 est absente. Exécutez "
                "'pip install -r requirements.txt' puis relancez T.A.R.S."
            ) from exc
        os.environ["NEEDLE2_LIB_PATH"] = str(self._engine_path)
        self._agent = needle.Needle(tools=self._tools())

    def select_route(self, text: str) -> str:
        if self._agent is None:
            raise RuntimeError("Needle 2 n'est pas initialisé.")
        self._agent.reset()
        try:
            result = self._agent.complete(text, max_new_tokens=1024)
        except RuntimeError as exc:
            if "unparseable envelope" not in str(exc):
                raise
            result = self._recover_response() or self._retry_response(text)
        calls = result.get("function_calls") or []
        arguments = calls[0].get("arguments") if calls else {}
        available_routes = {*self.DEFAULT_ROUTES, *self._agent_identifiers}
        route = str((arguments or {}).get("intent", "unknown"))
        if route not in available_routes:
            route = "unknown"
        return route

    def shutdown(self) -> None:
        if self._agent is not None:
            self._agent.close()
        self._agent = None

    def _retry_response(self, text: str) -> dict[str, object]:
        if not self._invalid_envelope_reported:
            logger.warning("Needle 2 returned an invalid response envelope; retrying.")
            self._invalid_envelope_reported = True
        self.shutdown()
        self.load()
        assert self._agent is not None
        try:
            return self._agent.complete(text, max_new_tokens=1024)
        except RuntimeError as exc:
            if "unparseable envelope" not in str(exc):
                raise
            logger.warning("Needle 2 retry returned an invalid response envelope.")
            return {}

    def _recover_response(self) -> dict[str, object]:
        if self._agent is None:
            return {}
        raw = self._agent._buffer.value.decode("utf-8", "replace")
        match = re.search(r',\s*"reasoning"\s*:', raw)
        if match is None:
            return {}
        try:
            result = json.loads(raw[:match.start()] + "}")
        except json.JSONDecodeError:
            return {}
        if not result.get("function_calls"):
            return {}
        logger.info("Needle 2 decision recovered from its reasoning envelope.")
        return result

    @property
    def _agent_identifiers(self) -> tuple[str, ...]:
        return tuple(identifier for identifier, _ in self._agent_definitions)

    def _tools(self) -> list[dict[str, object]]:
        agent_routes = "\n".join(
            f"- {identifier}: {description}"
            for identifier, description in self._agent_definitions
        )
        return [
            {
                "name": "select_response",
                "description": (
                    "Classify a French or English user message so T.A.R.S. "
                    "can give a short local reply or call a local agent. "
                    "Choose an agent route when the user explicitly asks to "
                    "call or contact that agent."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "description": (
                                "Response route or local agent identifier. "
                                f"Available local agents:\n{agent_routes}"
                            ),
                            "enum": [
                                *self.DEFAULT_ROUTES,
                                *self._agent_identifiers,
                            ],
                        }
                    },
                    "required": ["intent"],
                },
            }
        ]
