from __future__ import annotations

from typing import Any, Optional

from .cache import EngineCache
from .engine_session import EngineSession
from .legacy_patch import patch_legacy_for_fast


class FastTaggerSession:
    def __init__(self, engine_path: str):
        self.engine_path = engine_path
        self.cache = EngineCache()
        self._session = EngineSession(engine_path)

    def __enter__(self) -> "FastTaggerSession":
        self._session.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._session.__exit__(exc_type, exc, tb)

    def tag_position(
        self,
        fen: str,
        move_uci: str,
        *,
        depth: int = 14,
        multipv: int = 6,
        cp_threshold: int = 100,
        small_drop_cp: int = 30,
        use_new: Optional[bool] = None,
    ) -> Any:
        from rule_tagger2.core.facade import tag_position as tag_position_impl

        with patch_legacy_for_fast(self._session, self.cache):
            return tag_position_impl(
                self.engine_path,
                fen,
                move_uci,
                depth=depth,
                multipv=multipv,
                cp_threshold=cp_threshold,
                small_drop_cp=small_drop_cp,
                use_new=use_new,
            )


def tag_position_fast(
    engine_path: str,
    fen: str,
    move_uci: str,
    *,
    depth: int = 14,
    multipv: int = 6,
    cp_threshold: int = 100,
    small_drop_cp: int = 30,
    use_new: Optional[bool] = None,
) -> Any:
    with FastTaggerSession(engine_path) as session:
        return session.tag_position(
            fen,
            move_uci,
            depth=depth,
            multipv=multipv,
            cp_threshold=cp_threshold,
            small_drop_cp=small_drop_cp,
            use_new=use_new,
        )
