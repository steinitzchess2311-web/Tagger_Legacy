# 文件：rule_tagger2/api_single_move.py

from typing import List, Dict, Any

def tag_single_move(fen: str, move_uci: str, engine_meta: Dict[str, Any] | None = None) -> List[str]:
    """
    统一入口：给定 fen + 一步 UCI，返回这一手的风格标签列表。
    现在先返回一个假标签，后面再换成真的。
    """
    engine_meta = engine_meta or {}

    # TODO: 以后在这里调用你真正的 rule_tagger 流水线
    # 比如：
    # result = analyze_position_and_move(
    #     fen=fen,
    #     move_uci=move_uci,
    #     engine_info=engine_meta,
    # )
    # tags = result.tags

    # 目前先用调试用的假标签，目的是把整条管线连通
    tags = ["_DEBUG_dummy_tag"]

    return tags
