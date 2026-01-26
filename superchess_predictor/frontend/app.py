import requests
import streamlit as st

API_URL = "http://localhost:8000/analyze"

st.set_page_config(page_title="Superchess Predictor", layout="wide")
st.title("♟️ Superchess Predictor UI")

DEFAULT_FEN = "r1b2rk1/pp1nqppp/2p2n2/b3p3/2BP4/P1N1PN2/1PQB1PPP/R4RK1 w - - 2 12"

with st.sidebar:
    st.header("Position Input")
    fen_input = st.text_area("FEN", value=DEFAULT_FEN, height=80)
    engine_path_input = st.text_input("Engine path", value="")

if st.button("🔮 Analyze via API"):
    if not fen_input.strip():
        st.error("FEN is required")
    else:
        with st.spinner("Calling backend API..."):
            try:
                resp = requests.post(
                    API_URL,
                    json={"fen": fen_input, "engine_path": engine_path_input or None},
                    timeout=60,
                )
                resp.raise_for_status()
            except requests.RequestException as exc:  # pylint: disable=broad-except
                st.error(f"API request failed: {exc}")
            else:
                data = resp.json()
                st.session_state["prediction_data"] = data

prediction_data = st.session_state.get("prediction_data")
if prediction_data:
    st.success("Prediction ready.")
    players = prediction_data.get("players", [])
    moves = prediction_data.get("moves", [])

    if not players or not moves:
        st.warning("No data returned from API.")
    else:
        player_choice = st.radio("Choose player:", players, horizontal=True)
        top_moves = sorted(
            moves,
            key=lambda mv: -mv.get("probabilities", {}).get(player_choice, 0.0),
        )[:5]

        st.subheader(f"Top 5 moves for {player_choice}")
        for mv in top_moves:
            prob = mv.get("probabilities", {}).get(player_choice, 0.0) * 100
            tags = ", ".join(mv.get("tags") or []) or "—"
            cp = mv.get("score_cp")
            cp_text = f" ({cp} cp)" if cp is not None else ""
            st.markdown(
                f"- **{mv['san']}** ({mv['uci']}) — {prob:.1f}%{cp_text}<br/>"
                f"  <span style='font-size:0.9em;color:#666;'>Tags: {tags}</span>",
                unsafe_allow_html=True,
            )

        st.markdown("#### Engine Candidates & Tags")
        candidate_rows = []
        for mv in moves:
            tag_flags = mv.get("tag_flags") or {}
            true_flags = [tag for tag, active in tag_flags.items() if active]
            candidate_rows.append(
                {
                    "Move": mv.get("san"),
                    "UCI": mv.get("uci"),
                    "Score (cp)": mv.get("score_cp"),
                    "Primary Tags": ", ".join(mv.get("tags") or []) or "—",
                    "Tag Flags": ", ".join(true_flags) if true_flags else "—",
                }
            )
        st.dataframe(candidate_rows, hide_index=True, use_container_width=True)

        with st.expander("Probabilities for all players", expanded=False):
            for mv in moves:
                prob_line = ", ".join(
                    f"{player}: {mv.get('probabilities', {}).get(player, 0.0) * 100:.1f}%"
                    for player in players
                )
                st.write(f"{mv['san']} ({mv['uci']}): {prob_line}")
else:
    st.info("Enter a FEN and run the analysis to view predictions.")
