import base64
from pathlib import Path
from typing import Optional

import chess
import chess.svg
import streamlit as st
from streamlit.components.v1 import html as st_html

from codex_utils import DEFAULT_ENGINE_PATH
from core.engine_utils import fetch_engine_moves
from core.file_utils import load_player_summaries
from core.predictor import compute_move_probability
from core.tagger_utils import tag_moves

st.set_page_config(page_title="Superchess Codex UI", layout="wide")
st.title("♟️ Superchess Codex Interface")

DEFAULT_FEN = "r1b2rk1/pp1nqppp/2p2n2/b3p3/2BP4/P1N1PN2/1PQB1PPP/R4RK1 w - - 2 12"

with st.sidebar:
    st.header("Position Input")
    fen_input = st.text_area("FEN", value=DEFAULT_FEN, height=80)
    engine_path_input = st.text_input("Engine path", value="")
    st.caption("Prediction uses only the FEN. No move input required.")

st.session_state.setdefault("prediction_payload", None)
st.session_state.setdefault("prediction_error", None)
st.session_state.setdefault("board_svg", None)
st.session_state.setdefault("board_fen", None)


def _render_board_svg(svg: str) -> None:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    st_html(
        f'<img src="data:image/svg+xml;base64,{encoded}" style="width:100%;max-width:520px;" />',
        height=520,
    )


board: Optional[chess.Board] = None
try:
    board = chess.Board(fen_input)
except ValueError as exc:
    st.error(f"Invalid FEN: {exc}")
else:
    svg_board = chess.svg.board(board, size=520)
    st.session_state["board_svg"] = svg_board
    st.session_state["board_fen"] = fen_input

st.subheader("Current Position")
current_svg = st.session_state.get("board_svg")
if current_svg:
    _render_board_svg(current_svg)
    st.caption(f"FEN: {st.session_state.get('board_fen', fen_input)}")
else:
    st.info("Enter a valid FEN in the sidebar to display the board.")

st.markdown("---")
st.header("🔮 Style Prediction System")
prediction_error = st.session_state.get("prediction_error")
if prediction_error:
    st.error(prediction_error)

run_prediction = st.button("🔮 Run Style Prediction (Top 7 Moves)")

if run_prediction:
    if board is None:
        st.session_state["prediction_payload"] = None
        st.session_state["prediction_error"] = "Please provide a valid FEN before running prediction."
    else:
        engine_path = engine_path_input or DEFAULT_ENGINE_PATH
        if not engine_path or not Path(engine_path).exists():
            st.session_state["prediction_payload"] = None
            st.session_state["prediction_error"] = "Valid engine path required to run prediction."
        else:
            with st.spinner("Running engine analysis and tagging moves..."):
                try:
                    top_moves = fetch_engine_moves(fen_input, engine_path=engine_path, top_n=7)
                except Exception as exc:  # pylint: disable=broad-except
                    st.session_state["prediction_payload"] = None
                    st.session_state["prediction_error"] = f"Engine analysis failed: {exc}"
                else:
                    try:
                        tagged = tag_moves(fen_input, top_moves, engine_path=engine_path)
                    except Exception as exc:  # pylint: disable=broad-except
                        st.session_state["prediction_payload"] = None
                        st.session_state["prediction_error"] = f"Move tagging failed: {exc}"
                    else:
                        player_summaries = load_player_summaries("reports")
                        if not player_summaries:
                            st.session_state["prediction_payload"] = None
                            st.session_state["prediction_error"] = "No universal summaries found in reports/."
                        else:
                            st.session_state["prediction_payload"] = {
                                "tagged": tagged,
                                "moves": top_moves,
                                "players": player_summaries,
                            }
                            st.session_state["prediction_error"] = None

prediction_payload = st.session_state.get("prediction_payload")
prediction_error = st.session_state.get("prediction_error")

if prediction_payload and not prediction_error:
    st.success("Prediction ready. Select a player to view likely moves.")
    player_keys = list(prediction_payload["players"].keys())
    if not player_keys:
        st.warning("No player summaries available.")
    else:
        player_choice = st.radio(
            "Choose player:",
            player_keys,
            horizontal=True,
            key="prediction_player_choice",
        )

        player_summary = prediction_payload["players"][player_choice]
        tagged_moves = prediction_payload["tagged"]
        probabilities = compute_move_probability(
            tagged_moves, player_summary["tag_distribution"]
        )

        st.caption(
            f"{player_choice}: {player_summary['meta']['games']} games, "
            f"{player_summary['meta']['moves']} moves aggregated."
        )

        if probabilities.size == 0:
            st.warning("No moves available for prediction.")
        else:
            sorted_entries = sorted(
                zip(tagged_moves, probabilities),
                key=lambda item: float(item[1]),
                reverse=True,
            )[:5]

            for mv, prob in sorted_entries:
                tags = ", ".join(mv["tags"]) if mv["tags"] else "—"
                cp = mv.get("score_cp")
                cp_text = f" | Score: {cp} cp" if cp is not None else ""
                st.markdown(
                    f"- **{mv['move']}** ({mv['uci']}) — {prob * 100:.1f}%{cp_text}<br/>"
                    f"  <span style='font-size:0.9em;color:#666;'>Tags: {tags}</span>",
                    unsafe_allow_html=True,
                )

            with st.expander("View all candidate moves", expanded=False):
                for mv, prob in zip(tagged_moves, probabilities):
                    tags = ", ".join(mv["tags"]) if mv["tags"] else "—"
                    cp = mv.get("score_cp")
                    cp_text = f" ({cp} cp)" if cp is not None else ""
                    st.write(f"{mv['move']} {cp_text} — {prob * 100:.2f}% | {tags}")
else:
    st.info("Run the style prediction to view player-specific recommendations.")
