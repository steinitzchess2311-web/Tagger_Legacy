from __future__ import annotations

from typing import Optional

import chess.engine


class EngineSession:
    def __init__(self, engine_path: str):
        self.engine_path = engine_path
        self.engine: Optional[chess.engine.SimpleEngine] = None

    def __enter__(self) -> "EngineSession":
        self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.engine is not None:
            try:
                self.engine.quit()
            except Exception:
                pass
            self.engine = None
