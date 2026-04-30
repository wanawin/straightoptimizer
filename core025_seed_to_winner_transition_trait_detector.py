
# BUILD: core025_exact_permutation_separator_miner__2026-04-30_v2_1_UPLOAD_PARSE_FIXED

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter
from itertools import combinations
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

BUILD_LABEL = "core025_exact_permutation_separator_miner__2026-04-30_v2_1_UPLOAD_PARSE_FIXED"
CORE_MEMBERS = {"0025", "0225", "0255"}
MIRROR_PAIRS = [(0,5), (1,6), (2,7), (3,8), (4,9)]


def norm_digits_4(value) -> Optional[str]:
    digs = re.findall(r"\d", str(value))
    if len(digs) < 4:
        return None
    return "".join(digs[:4]).zfill(4)


def box_key(value) -> Optional[str]:
    r = norm_digits_4(value)
    return "".join(sorted(r)) if r else None


def core_member(value) -> Optional[str]:
    b = box_key(value)
    return b if b in CORE_MEMBERS else None


def load_any_table(uploaded) -> pd.DataFrame:
    raw = uploaded.getvalue()
    name = uploaded.name.lower()

    if name.endswith(".csv"):
        try:
            return pd.read_csv(io.BytesIO(raw), dtype=str)
        except Exception:
            return pd.read_csv(io.BytesIO(raw), sep=None, engine="python", dtype=str)

    if name.endswith(".txt") or name.endswith(".tsv"):
        try:
            df = pd.read_csv(io.BytesIO(raw), sep="\t", header=None, dtype=str)
            if df.shape[1] >= 4:
                df = df.iloc[:, :4]
                df.columns = ["Date", "State", "Game", "Result"]
                return df
        except Exception:
            pass

        try:
            df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python", dtype=str)
            if not df.empty and df.shape[1] >= 4:
                return df
        except Exception:
            pass

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
            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 4:
                rows.append(parts[:4])
        if rows:
            return pd.DataFrame(rows, columns=["Date", "State", "Game", "Result"])

    raise ValueError("Unsupported or unreadable file. Upload .txt, .csv, or .tsv.")


def find_col(df: pd.DataFrame, candidates: List[str], required=True) -> Optional[str]:
    norm_map = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): c for c in df.columns}
    for cand in candidates:
        k = re.sub(r"[^a-z0-9]+", "", cand.lower())
        if k in norm_map:
            return norm_map[k]
    for cand in candidates:
        k = re.sub(r"[^a-z0-9]+", "", cand.lower())
        for nk, orig in norm_map.items():
            if k and k in nk:
                return orig
    if required:
        raise ValueError(f"Missing required column. Tried {candidates}. Found: {list(df.columns)}")
    return None


def prepare_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    date_col = find_col(df, ["Date", "Draw Date"], required=False)
    state_col = find_col(df, ["State", "Jurisdiction"], required=False)
    game_col = find_col(df, ["Game", "Stream"], required=False)
    result_col = find_col(df, ["Result", "Results", "Number", "Winning Number"], required=True)

    if date_col is None:
        df["Date"] = pd.RangeIndex(0, len(df))
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

    parsed = pd.to_datetime(out["Date"], errors="coerce")
    out["DateParsed"] = parsed
    if parsed.notna().any():
        out = out.sort_values(["State", "Game", "DateParsed"]).reset_index(drop=True)
    else:
        out["DateParsed"] = pd.RangeIndex(0, len(out))
        out = out.reset_index(drop=True)

    out["StreamKey"] = out["State"] + " | " + out["Game"]
    return out


def digits(s: str) -> List[int]:
    return [int(x) for x in str(s).zfill(4)]


def digit_sum(s: str) -> int:
    return sum(digits(s))


def root_sum(s: str) -> int:
    sm = digit_sum(s)
    return sm % 9 if sm % 9 != 0 else 9


def spread(s: str) -> int:
    d = digits(s)
    return max(d) - min(d)


def parity_pattern(s: str) -> str:
    return "".join("E" if d % 2 == 0 else "O" for d in digits(s))


def highlow_pattern(s: str) -> str:
    return "".join("H" if d >= 5 else "L" for d in digits(s))


def repeat_shape(s: str) -> str:
    vals = sorted(Counter(str(s).zfill(4)).values(), reverse=True)
    if vals == [1,1,1,1]:
        return "all_unique"
    if vals == [2,1,1]:
        return "one_pair"
    if vals == [2,2]:
        return "two_pair"
    if vals == [3,1]:
        return "triple"
    if vals == [4]:
        return "quad"
    return "other"


def bucket(value: int, cuts: List[int]) -> str:
    prev = None
    for c in cuts:
        if value <= c:
            if prev is None:
                return f"<= {c}"
            return f"{prev+1}-{c}"
        prev = c
    return f"> {cuts[-1]}"


def mirror_traits(seed: str) -> Dict[str, object]:
    ds = set(digits(seed))
    present = []
    for a, b in MIRROR_PAIRS:
        if a in ds and b in ds:
            present.append(f"{a}{b}")
    return {"mirror_count": len(present), "has_mirror": int(bool(present)), "mirror_pairs": "|".join(present) if present else "none"}


def adjacent_pairs(seed: str) -> List[str]:
    s = str(seed).zfill(4)
    return [s[i:i+2] for i in range(3)]


def ordered_pairs_any(seed: str) -> List[str]:
    s = str(seed).zfill(4)
    return [s[i] + s[j] for i, j in combinations(range(4), 2)]


def unordered_pairs_any(seed: str) -> List[str]:
    s = str(seed).zfill(4)
    return ["".join(sorted(s[i] + s[j])) for i, j in combinations(range(4), 2)]


def unordered_triplets_any(seed: str) -> List[str]:
    s = str(seed).zfill(4)
    return ["".join(sorted("".join(s[i] for i in comb))) for comb in combinations(range(4), 3)]


def double_positions(winner: str) -> str:
    c = Counter(winner)
    doubles = [d for d, n in c.items() if n == 2]
    if not doubles:
        return "none"
    d = doubles[0]
    return "-".join(str(i+1) for i, x in enumerate(winner) if x == d)


def member_double_digit(member: str) -> str:
    return {"0025": "0", "0225": "2", "0255": "5"}.get(member, "")


def build_single_traits(seed: str) -> Dict[str, str]:
    s = str(seed).zfill(4)
    d = digits(s)
    mt = mirror_traits(s)
    traits = {
        "seed_sum": str(digit_sum(s)),
        "seed_sum_bucket": bucket(digit_sum(s), [6, 10, 14, 18, 22, 26, 30]),
        "seed_root": str(root_sum(s)),
        "seed_spread": str(spread(s)),
        "seed_spread_bucket": bucket(spread(s), [2, 4, 6, 8]),
        "seed_parity": parity_pattern(s),
        "seed_highlow": highlow_pattern(s),
        "seed_repeat_shape": repeat_shape(s),
        "seed_even_count": str(sum(1 for x in d if x % 2 == 0)),
        "seed_high_count": str(sum(1 for x in d if x >= 5)),
        "core_digit_count": str(sum(1 for ch in s if ch in "025")),
        "has0": str(int("0" in s)),
        "has2": str(int("2" in s)),
        "has5": str(int("5" in s)),
        "has9": str(int("9" in s)),
        "first_digit": s[0],
        "last_digit": s[-1],
        "first_pair": s[:2],
        "last_pair": s[2:],
        "mirror_count": str(mt["mirror_count"]),
        "has_mirror": str(mt["has_mirror"]),
        "mirror_pairs": str(mt["mirror_pairs"]),
    }
    for i, ch in enumerate(s):
        traits[f"S{i+1}"] = ch
        traits[f"S{i+1}_is_core"] = str(int(ch in "025"))
    return traits


def build_trait_tokens(seed: str) -> List[str]:
    tokens = []
    single = build_single_traits(seed)
    tokens.extend([f"{k}={v}" for k, v in single.items()])
    for p in adjacent_pairs(seed):
        tokens.append(f"adj_pair={p}")
        tokens.append(f"touching_unordered_pair={''.join(sorted(p))}")
    for p in ordered_pairs_any(seed):
        tokens.append(f"ordered_pair_any={p}")
    for p in unordered_pairs_any(seed):
        tokens.append(f"unordered_pair_any={p}")
    for t in unordered_triplets_any(seed):
        tokens.append(f"unordered_triplet_any={t}")
    s = str(seed).zfill(4)
    for i, j in combinations(range(4), 2):
        tokens.append(f"S{i+1}{j+1}={s[i]}{s[j]}")
        tokens.append(f"S{i+1}{j+1}_unordered={''.join(sorted(s[i]+s[j]))}")
    return sorted(set(tokens))


def build_core_transitions(hist: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for stream, g in hist.groupby("StreamKey", sort=False):
        g = g.sort_values("DateParsed").reset_index(drop=True)
        for i in range(1, len(g)):
            seed = g.loc[i-1, "Result"]
            winner = g.loc[i, "Result"]
            mem = core_member(winner)
            if mem not in CORE_MEMBERS:
                continue
            rows.append({
                "StreamKey": stream,
                "Date": g.loc[i, "Date"],
                "Seed": seed,
                "WinnerPermutation": winner,
                "WinMember": mem,
                "DoubleDigit": member_double_digit(mem),
                "DoublePositions": double_positions(winner),
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out["TraitTokens"] = out["Seed"].map(build_trait_tokens)
    return out


def mine_single_trait_separators(trans: pd.DataFrame, min_trait_total: int, min_hits: int) -> pd.DataFrame:
    total_events = len(trans)
    perm_counts = trans["WinnerPermutation"].value_counts().to_dict()
    token_total = Counter()
    token_perm = Counter()
    for _, r in trans.iterrows():
        perm = r["WinnerPermutation"]
        for tok in r["TraitTokens"]:
            token_total[tok] += 1
            token_perm[(tok, perm)] += 1
    rows = []
    for (tok, perm), hits in token_perm.items():
        total = token_total[tok]
        if total < min_trait_total or hits < min_hits:
            continue
        baseline = perm_counts[perm] / total_events if total_events else 0
        rate = hits / total if total else 0
        lift = rate / baseline if baseline else 0
        separation = rate - ((perm_counts[perm] - hits) / max(total_events - total, 1))
        rows.append({
            "TargetPermutation": perm, "TraitStack": tok, "StackSize": 1,
            "Hits": hits, "TraitTotal": total,
            "ConfidencePct": round(rate * 100, 2), "BaselinePct": round(baseline * 100, 2),
            "Lift": round(lift, 3), "CompetingHitsWithTrait": total - hits,
            "SeparationScore": round(separation, 4),
            "RuleScore": round(hits * lift * max(separation, 0.001), 4),
        })
    return pd.DataFrame(rows).sort_values(["RuleScore", "Hits", "Lift"], ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def mine_stacked_trait_separators(trans: pd.DataFrame, min_stack_total: int, min_hits: int, max_tokens_per_event: int = 45) -> pd.DataFrame:
    total_events = len(trans)
    perm_counts = trans["WinnerPermutation"].value_counts().to_dict()
    stack_total = Counter()
    stack_perm = Counter()
    allowed_prefixes = (
        "seed_sum_bucket=", "seed_root=", "seed_spread_bucket=", "seed_parity=", "seed_highlow=",
        "seed_repeat_shape=", "core_digit_count=", "has_mirror=", "mirror_count=", "mirror_pairs=",
        "has0=", "has2=", "has5=", "has9=", "S1=", "S2=", "S3=", "S4=",
        "adj_pair=", "touching_unordered_pair=", "ordered_pair_any=", "unordered_pair_any=",
        "unordered_triplet_any=", "S12=", "S13=", "S14=", "S23=", "S24=", "S34=",
        "S12_unordered=", "S13_unordered=", "S14_unordered=", "S23_unordered=", "S24_unordered=", "S34_unordered="
    )
    reduced_prefixes = (
        "seed_sum_bucket=", "seed_root=", "seed_spread_bucket=", "seed_parity=", "seed_highlow=",
        "core_digit_count=", "has_mirror=", "has0=", "has2=", "has5=", "S1=", "S2=", "S3=", "S4="
    )
    for _, r in trans.iterrows():
        perm = r["WinnerPermutation"]
        toks = [t for t in r["TraitTokens"] if t.startswith(allowed_prefixes)]
        toks = sorted(set(toks))[:max_tokens_per_event]
        for a, b in combinations(toks, 2):
            stack = f"{a} && {b}"
            stack_total[stack] += 1
            stack_perm[(stack, perm)] += 1
        reduced = [t for t in toks if t.startswith(reduced_prefixes)]
        reduced = sorted(set(reduced))[:20]
        for a, b, c in combinations(reduced, 3):
            stack = f"{a} && {b} && {c}"
            stack_total[stack] += 1
            stack_perm[(stack, perm)] += 1
    rows = []
    for (stack, perm), hits in stack_perm.items():
        total = stack_total[stack]
        if total < min_stack_total or hits < min_hits:
            continue
        baseline = perm_counts[perm] / total_events if total_events else 0
        rate = hits / total if total else 0
        lift = rate / baseline if baseline else 0
        separation = rate - ((perm_counts[perm] - hits) / max(total_events - total, 1))
        rows.append({
            "TargetPermutation": perm, "TraitStack": stack, "StackSize": stack.count("&&") + 1,
            "Hits": hits, "TraitTotal": total,
            "ConfidencePct": round(rate * 100, 2), "BaselinePct": round(baseline * 100, 2),
            "Lift": round(lift, 3), "CompetingHitsWithTrait": total - hits,
            "SeparationScore": round(separation, 4),
            "RuleScore": round(hits * lift * max(separation, 0.001), 4),
        })
    return pd.DataFrame(rows).sort_values(["RuleScore", "Hits", "Lift"], ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def summarize_permutation_frequency(trans: pd.DataFrame) -> pd.DataFrame:
    total = len(trans)
    out = trans.groupby(["WinMember", "WinnerPermutation"]).size().reset_index(name="Hits")
    out["PctOfAllCoreHits"] = (out["Hits"] / total * 100).round(2)
    out["PctWithinMember"] = out.groupby("WinMember")["Hits"].transform(lambda s: (s / s.sum() * 100).round(2))
    return out.sort_values(["WinMember", "Hits"], ascending=[True, False]).reset_index(drop=True)


def make_zip(reports: Dict[str, pd.DataFrame]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, df in reports.items():
            zf.writestr(name, df.to_csv(index=False))
    bio.seek(0)
    return bio.getvalue()


st.set_page_config(page_title="Core025 Exact Permutation Separator Miner", layout="wide")
st.title("Core025 Exact Permutation Separator Miner v2.1")
st.caption(f"BUILD: {BUILD_LABEL}")

uploaded = st.file_uploader("Upload FULL HISTORY (.txt/.csv/.tsv)", type=["txt", "csv", "tsv"])

with st.sidebar:
    min_trait_total = st.slider("Min single-trait total", 2, 50, 6)
    min_single_hits = st.slider("Min single-trait hits for target permutation", 1, 20, 2)
    min_stack_total = st.slider("Min stacked-trait total", 2, 50, 4)
    min_stack_hits = st.slider("Min stacked-trait hits for target permutation", 1, 20, 2)
    preview_rows = st.slider("Preview rows", 25, 1000, 200)

if not uploaded:
    st.warning("Upload FULL HISTORY to begin.")
    st.stop()

try:
    raw = load_any_table(uploaded)
    hist = prepare_history(raw)
    trans = build_core_transitions(hist)
except Exception as e:
    st.error(f"Parse/mining setup failed: {e}")
    st.stop()

if trans.empty:
    st.error("No Core025 member-hit transitions found after parsing. Check Result parsing.")
    st.stop()

st.success(f"Parsed {len(hist):,} result rows and found {len(trans):,} Core025 member-hit transitions.")

freq = summarize_permutation_frequency(trans)

with st.spinner("Mining single-trait separators..."):
    single_rules = mine_single_trait_separators(trans, min_trait_total=min_trait_total, min_hits=min_single_hits)

with st.spinner("Mining stacked 2-trait and 3-trait separators..."):
    stacked_rules = mine_stacked_trait_separators(trans, min_stack_total=min_stack_total, min_hits=min_stack_hits)

reports = {
    "core025_exact_permutation_transitions.csv": trans.drop(columns=["TraitTokens"]),
    "core025_exact_permutation_frequency.csv": freq,
    "core025_single_trait_permutation_separators.csv": single_rules,
    "core025_stacked_trait_permutation_separators.csv": stacked_rules,
}

c1, c2, c3 = st.columns(3)
c1.metric("Core025 transitions", len(trans))
c2.metric("Exact permutations found", trans["WinnerPermutation"].nunique())
c3.metric("Stacked rules mined", len(stacked_rules))

st.download_button(
    "Download ALL v2.1 Separator Reports ZIP",
    make_zip(reports),
    "core025_exact_permutation_separator_reports__2026-04-30_v2_1.zip",
    "application/zip",
    use_container_width=True,
)

tabs = st.tabs(["Permutation Frequency", "Single-Trait Separators", "Stacked Separators", "Transitions"])

with tabs[0]:
    st.subheader("Exact Permutation Frequency")
    st.dataframe(freq, use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Single-Trait → Exact Permutation Separators")
    st.caption("Use high Hits + high Lift + high SeparationScore. These are soft scoring boosts, not eliminators.")
    st.dataframe(single_rules.head(preview_rows), use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("Stacked 2-Trait / 3-Trait Separators")
    st.caption("This is the deeper layer: pair/triplet/position/mirror/sum/parity stacks by exact winning straight permutation.")
    st.dataframe(stacked_rules.head(preview_rows), use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("Core025 Member-Hit Transitions")
    st.dataframe(trans.drop(columns=["TraitTokens"]).head(preview_rows), use_container_width=True, hide_index=True)
