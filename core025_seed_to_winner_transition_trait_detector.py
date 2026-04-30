
# BUILD: core025_seed_to_straight_trait_miner__2026-04-30_v1_UPLOAD_FIXED

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter, defaultdict
from itertools import product
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


BUILD_LABEL = "core025_seed_to_straight_trait_miner__2026-04-30_v1_UPLOAD_FIXED"
CORE_MEMBERS = {"0025", "0225", "0255"}


# =========================
# CORE HELPERS
# =========================

def norm_digits_4(value) -> Optional[str]:
    digs = re.findall(r"\d", str(value))
    if len(digs) < 4:
        return None
    return "".join(digs[:4]).zfill(4)


def box_key_4(value) -> Optional[str]:
    r = norm_digits_4(value)
    return "".join(sorted(r)) if r else None


def core_member(value) -> Optional[str]:
    b = box_key_4(value)
    return b if b in CORE_MEMBERS else None


def digit_sum(r4: str) -> int:
    return sum(int(x) for x in r4)


def parity_pattern(r4: str) -> str:
    return "".join("E" if int(x) % 2 == 0 else "O" for x in r4)


def highlow_pattern(r4: str) -> str:
    return "".join("H" if int(x) >= 5 else "L" for x in r4)


def repeat_shape(r4: str) -> str:
    counts = sorted(Counter(r4).values(), reverse=True)
    if counts == [1, 1, 1, 1]:
        return "all_unique"
    if counts == [2, 1, 1]:
        return "one_pair"
    if counts == [2, 2]:
        return "two_pair"
    if counts == [3, 1]:
        return "triple"
    if counts == [4]:
        return "quad"
    return "other"


def double_digit_for_member(member: str) -> str:
    if member == "0025":
        return "0"
    if member == "0225":
        return "2"
    if member == "0255":
        return "5"
    return ""


def double_positions(r4: str) -> str:
    counts = Counter(r4)
    doubles = [d for d, c in counts.items() if c == 2]
    if not doubles:
        return ""
    d = doubles[0]
    positions = [str(i + 1) for i, x in enumerate(r4) if x == d]
    return "-".join(positions)


def find_col(df: pd.DataFrame, candidates: List[str], required: bool = True) -> Optional[str]:
    norm = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): c for c in df.columns}
    for cand in candidates:
        key = re.sub(r"[^a-z0-9]+", "", cand.lower())
        if key in norm:
            return norm[key]
    for cand in candidates:
        key = re.sub(r"[^a-z0-9]+", "", cand.lower())
        for nk, orig in norm.items():
            if key and key in nk:
                return orig
    if required:
        raise ValueError(f"Could not find required column. Tried {candidates}. Found columns: {list(df.columns)}")
    return None


def load_any_table(uploaded) -> pd.DataFrame:
    raw = uploaded.getvalue()
    name = uploaded.name.lower()

    if name.endswith(".csv"):
        try:
            return pd.read_csv(io.BytesIO(raw), dtype=str)
        except Exception:
            return pd.read_csv(io.BytesIO(raw), sep=None, engine="python", dtype=str)

    if name.endswith(".txt") or name.endswith(".tsv"):
        # First try tabular raw history: date<TAB>state<TAB>game<TAB>result
        try:
            df = pd.read_csv(io.BytesIO(raw), sep="\t", header=None, dtype=str)
            if df.shape[1] >= 4:
                df = df.iloc[:, :4]
                df.columns = ["Date", "State", "Game", "Result"]
                return df
        except Exception:
            pass

        # Try auto sep with header.
        try:
            df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python", dtype=str)
            if not df.empty:
                return df
        except Exception:
            pass

        # Fallback line parser.
        text = raw.decode("utf-8", errors="ignore")
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = re.split(r"\t+", line)
            if len(parts) >= 4:
                rows.append(parts[:4])
                continue
            # Try date state game result using multiple spaces.
            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 4:
                rows.append(parts[:4])
        if rows:
            return pd.DataFrame(rows, columns=["Date", "State", "Game", "Result"])

    raise ValueError("Unsupported or unreadable file format. Use .csv, .txt, or .tsv.")


def prepare_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    date_col = find_col(df, ["Date", "Draw Date", "draw_date"], required=False)
    state_col = find_col(df, ["State", "Jurisdiction"], required=False)
    game_col = find_col(df, ["Game", "Stream", "GameName"], required=False)
    result_col = find_col(df, ["Result", "Results", "Number", "Winning Number"], required=True)

    if date_col is None:
        df["Date"] = pd.RangeIndex(start=0, stop=len(df), step=1)
        date_col = "Date"
    if state_col is None:
        df["State"] = "Unknown"
        state_col = "State"
    if game_col is None:
        df["Game"] = "Unknown"
        game_col = "Game"

    out = pd.DataFrame({
        "Date": df[date_col],
        "State": df[state_col].astype(str).str.strip(),
        "Game": df[game_col].astype(str).str.strip(),
        "Result": df[result_col].map(norm_digits_4),
    })
    out = out.dropna(subset=["Result"]).copy()

    parsed_dates = pd.to_datetime(out["Date"], errors="coerce")
    out["DateParsed"] = parsed_dates
    if parsed_dates.notna().any():
        out = out.sort_values(["State", "Game", "DateParsed"]).reset_index(drop=True)
    else:
        out = out.reset_index(drop=True)
        out["DateParsed"] = pd.RangeIndex(start=0, stop=len(out), step=1)

    out["StreamKey"] = out["State"] + " | " + out["Game"]
    out["Member"] = out["Result"].map(core_member)
    out["Sum"] = out["Result"].map(digit_sum)
    out["Parity"] = out["Result"].map(parity_pattern)
    out["HighLow"] = out["Result"].map(highlow_pattern)
    out["RepeatShape"] = out["Result"].map(repeat_shape)
    return out


def build_transitions(hist: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stream, g in hist.groupby("StreamKey", sort=False):
        g = g.sort_values("DateParsed").reset_index(drop=True)
        for i in range(1, len(g)):
            seed = g.loc[i - 1, "Result"]
            winner = g.loc[i, "Result"]
            win_member = core_member(winner)
            if win_member not in CORE_MEMBERS:
                continue
            rows.append({
                "StreamKey": stream,
                "Date": g.loc[i, "Date"],
                "Seed": seed,
                "Winner": winner,
                "WinMember": win_member,
                "DoubleDigit": double_digit_for_member(win_member),
                "DoublePositions": double_positions(winner),
                "SeedSum": digit_sum(seed),
                "WinnerSum": digit_sum(winner),
                "SeedParity": parity_pattern(seed),
                "WinnerParity": parity_pattern(winner),
                "SeedHighLow": highlow_pattern(seed),
                "WinnerHighLow": highlow_pattern(winner),
                "SeedRepeatShape": repeat_shape(seed),
                "WinnerRepeatShape": repeat_shape(winner),
            })
    return pd.DataFrame(rows)


def summarize_counts(df: pd.DataFrame, group_cols: List[str], target_col: str, min_n: int = 1) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby(group_cols + [target_col]).size().reset_index(name="Hits")
    totals = df.groupby(group_cols).size().reset_index(name="Total")
    out = g.merge(totals, on=group_cols, how="left")
    out["RatePct"] = (out["Hits"] / out["Total"] * 100).round(2)
    out = out[out["Total"] >= min_n].sort_values(group_cols + ["Hits"], ascending=[True] * len(group_cols) + [False])
    return out.reset_index(drop=True)


def positional_seed_to_winner(trans: pd.DataFrame, min_n: int = 1) -> pd.DataFrame:
    rows = []
    for _, r in trans.iterrows():
        seed = r["Seed"]
        win = r["Winner"]
        for si in range(4):
            for wi in range(4):
                rows.append({
                    "SeedPos": f"S{si+1}",
                    "SeedDigit": seed[si],
                    "WinnerPos": f"W{wi+1}",
                    "WinnerDigit": win[wi],
                    "WinMember": r["WinMember"],
                    "DoubleDigit": r["DoubleDigit"],
                    "DoublePositions": r["DoublePositions"],
                    "SeedSum": r["SeedSum"],
                    "SeedParity": r["SeedParity"],
                    "SeedHighLow": r["SeedHighLow"],
                })
    raw = pd.DataFrame(rows)
    return summarize_counts(raw, ["SeedPos", "SeedDigit", "WinnerPos"], "WinnerDigit", min_n=min_n)


def same_position_map(trans: pd.DataFrame, min_n: int = 1) -> pd.DataFrame:
    rows = []
    for _, r in trans.iterrows():
        seed = r["Seed"]
        win = r["Winner"]
        for i in range(4):
            rows.append({
                "Position": f"P{i+1}",
                "SeedDigitAtPosition": seed[i],
                "WinnerDigitAtSamePosition": win[i],
                "WinMember": r["WinMember"],
                "DoubleDigit": r["DoubleDigit"],
            })
    raw = pd.DataFrame(rows)
    return summarize_counts(raw, ["Position", "SeedDigitAtPosition"], "WinnerDigitAtSamePosition", min_n=min_n)


def seed_trait_to_member(trans: pd.DataFrame, min_n: int = 1) -> pd.DataFrame:
    frames = []
    trait_specs = [
        ("SeedSum", "SeedSum"),
        ("SeedParity", "SeedParity"),
        ("SeedHighLow", "SeedHighLow"),
        ("SeedRepeatShape", "SeedRepeatShape"),
    ]
    for label, col in trait_specs:
        tmp = summarize_counts(trans, [col], "WinMember", min_n=min_n)
        if not tmp.empty:
            tmp.insert(0, "Trait", label)
            tmp = tmp.rename(columns={col: "TraitValue"})
            frames.append(tmp)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def seed_position_to_member(trans: pd.DataFrame, min_n: int = 1) -> pd.DataFrame:
    rows = []
    for _, r in trans.iterrows():
        seed = r["Seed"]
        for i, d in enumerate(seed):
            rows.append({
                "SeedPos": f"S{i+1}",
                "SeedDigit": d,
                "WinMember": r["WinMember"],
            })
    raw = pd.DataFrame(rows)
    return summarize_counts(raw, ["SeedPos", "SeedDigit"], "WinMember", min_n=min_n)


def double_digit_summary(trans: pd.DataFrame) -> pd.DataFrame:
    if trans.empty:
        return pd.DataFrame()
    out = trans.groupby(["WinMember", "DoubleDigit"]).size().reset_index(name="Hits")
    out["MemberExpectedDouble"] = out["WinMember"].map(double_digit_for_member)
    out["IsExpected"] = out["DoubleDigit"].eq(out["MemberExpectedDouble"])
    return out.sort_values("Hits", ascending=False).reset_index(drop=True)


def double_position_summary(trans: pd.DataFrame, min_n: int = 1) -> pd.DataFrame:
    return summarize_counts(trans, ["WinMember", "DoubleDigit"], "DoublePositions", min_n=min_n)


def seed_to_double_position(trans: pd.DataFrame, min_n: int = 1) -> pd.DataFrame:
    frames = []
    for col in ["SeedSum", "SeedParity", "SeedHighLow", "SeedRepeatShape"]:
        tmp = summarize_counts(trans, [col, "WinMember"], "DoublePositions", min_n=min_n)
        if not tmp.empty:
            tmp.insert(0, "Trait", col)
            tmp = tmp.rename(columns={col: "TraitValue"})
            frames.append(tmp)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def stream_member_bias(trans: pd.DataFrame, min_n: int = 1) -> pd.DataFrame:
    return summarize_counts(trans, ["StreamKey"], "WinMember", min_n=min_n)


def make_zip(reports: Dict[str, pd.DataFrame]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, df in reports.items():
            zf.writestr(name, df.to_csv(index=False))
    bio.seek(0)
    return bio.getvalue()


# =========================
# STREAMLIT UI
# =========================

st.set_page_config(page_title="Core025 Seed → Straight Trait Miner", layout="wide")
st.title("Core025 Seed → Straight Trait Miner")
st.caption(f"BUILD: {BUILD_LABEL}")

st.info(
    "Upload the same full history file used by your Core025 app. "
    "This miner keeps only transitions where the next result is a Core025 member, then mines seed-position, double-digit, member, sum, parity, and positional straight traits."
)

uploaded = st.file_uploader("Upload FULL HISTORY (.txt/.csv/.tsv)", type=["txt", "csv", "tsv"])

min_n = st.sidebar.slider("Minimum sample size for rule tables", 1, 20, 2)
show_rows = st.sidebar.slider("Preview rows per report", 10, 200, 50)

if not uploaded:
    st.warning("Upload FULL HISTORY to begin.")
    st.stop()

try:
    raw = load_any_table(uploaded)
    hist = prepare_history(raw)
    trans = build_transitions(hist)
except Exception as e:
    st.error(f"Failed to parse/mine file: {e}")
    st.stop()

st.success(f"Loaded {len(hist):,} result rows. Found {len(trans):,} Core025 member-hit transitions.")

if trans.empty:
    st.error("No Core025 member-hit transitions found. Check whether the Result column is being parsed correctly.")
    st.stop()

reports = {
    "core025_member_hit_transitions.csv": trans,
    "seed_position_to_winner_position_digit.csv": positional_seed_to_winner(trans, min_n=min_n),
    "same_position_seed_digit_to_winner_digit.csv": same_position_map(trans, min_n=min_n),
    "seed_position_digit_to_member.csv": seed_position_to_member(trans, min_n=min_n),
    "seed_trait_to_member.csv": seed_trait_to_member(trans, min_n=min_n),
    "double_digit_summary.csv": double_digit_summary(trans),
    "double_position_summary.csv": double_position_summary(trans, min_n=min_n),
    "seed_trait_to_double_position.csv": seed_to_double_position(trans, min_n=min_n),
    "stream_to_member_bias.csv": stream_member_bias(trans, min_n=min_n),
}

c1, c2, c3, c4 = st.columns(4)
c1.metric("Core025 transitions", len(trans))
c2.metric("0025 hits", int((trans["WinMember"] == "0025").sum()))
c3.metric("0225 hits", int((trans["WinMember"] == "0225").sum()))
c4.metric("0255 hits", int((trans["WinMember"] == "0255").sum()))

st.download_button(
    "Download ALL trait-mining reports ZIP",
    make_zip(reports),
    "core025_seed_to_straight_trait_reports__2026-04-30_v1.zip",
    "application/zip",
    use_container_width=True,
)

tabs = st.tabs([
    "Transitions",
    "Seed Position → Winner Position",
    "Same Position",
    "Member Rules",
    "Double Digit + Position",
    "Stream Bias",
])

with tabs[0]:
    st.subheader("Core025 Member-Hit Transitions")
    st.dataframe(trans.head(show_rows), use_container_width=True, hide_index=True)
    st.download_button(
        "Download transitions CSV",
        trans.to_csv(index=False).encode(),
        "core025_member_hit_transitions.csv",
        "text/csv",
        use_container_width=True,
    )

with tabs[1]:
    st.subheader("Seed Position/Digit → Winner Position/Digit")
    df = reports["seed_position_to_winner_position_digit.csv"]
    st.dataframe(df.head(show_rows), use_container_width=True, hide_index=True)
    st.caption("Example: S1 seed digit 8 → W3 winner digit 2. Use high-rate rows as positional reorder rules.")

with tabs[2]:
    st.subheader("Same-Position Seed Digit → Same-Position Winner Digit")
    df = reports["same_position_seed_digit_to_winner_digit.csv"]
    st.dataframe(df.head(show_rows), use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("Seed Traits → Winning Member")
    st.markdown("### Seed position/digit → member")
    st.dataframe(reports["seed_position_digit_to_member.csv"].head(show_rows), use_container_width=True, hide_index=True)
    st.markdown("### Sum / parity / high-low / repeat shape → member")
    st.dataframe(reports["seed_trait_to_member.csv"].head(show_rows), use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("Double Digit + Double Position")
    st.markdown("### Double digit summary")
    st.dataframe(reports["double_digit_summary.csv"], use_container_width=True, hide_index=True)
    st.markdown("### Double positions by member")
    st.dataframe(reports["double_position_summary.csv"].head(show_rows), use_container_width=True, hide_index=True)
    st.markdown("### Seed trait → double position")
    st.dataframe(reports["seed_trait_to_double_position.csv"].head(show_rows), use_container_width=True, hide_index=True)

with tabs[5]:
    st.subheader("Stream → Member Bias")
    st.dataframe(reports["stream_to_member_bias.csv"].head(show_rows), use_container_width=True, hide_index=True)
