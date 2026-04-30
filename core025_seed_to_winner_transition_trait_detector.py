# BUILD: core025_permutation_separator_miner__2026-04-30_v2_FULL

import streamlit as st
import pandas as pd
from collections import Counter
import itertools

st.set_page_config(layout="wide")

CORE_MEMBERS = {"0025", "0225", "0255"}

# =========================
# HELPERS
# =========================

def digits(x):
    return [int(d) for d in str(x).zfill(4)]

def box(x):
    return "".join(sorted(str(x).zfill(4)))

def member(x):
    b = box(x)
    return b if b in CORE_MEMBERS else None

def sum_digits(x):
    return sum(digits(x))

def root(x):
    s = sum_digits(x)
    return s % 9 if s % 9 != 0 else 9

def parity(x):
    return "".join("E" if d % 2 == 0 else "O" for d in digits(x))

def highlow(x):
    return "".join("H" if d >= 5 else "L" for d in digits(x))

def spread(x):
    d = digits(x)
    return max(d) - min(d)

def mirror_pairs():
    return {(0,5),(1,6),(2,7),(3,8),(4,9)}

def has_mirror(x):
    d = digits(x)
    for a,b in mirror_pairs():
        if a in d and b in d:
            return True
    return False

def get_pairs(x):
    d = digits(x)
    return set(tuple(sorted(p)) for p in itertools.combinations(d,2))

def get_triplets(x):
    d = digits(x)
    return set(tuple(sorted(t)) for t in itertools.combinations(d,3))

# =========================
# LOAD
# =========================

st.title("Core025 Permutation Separator Miner v2")

file = st.file_uploader("Upload FULL HISTORY")

if not file:
    st.stop()

df = pd.read_csv(file)
df["Result"] = df["Result"].astype(str).str.zfill(4)

df["Seed"] = df["Result"].shift(1)
df = df.dropna()

df["Member"] = df["Result"].apply(member)
df = df[df["Member"].notna()]

# =========================
# TRAITS
# =========================

def build_traits(seed):
    return {
        "sum": sum_digits(seed),
        "root": root(seed),
        "parity": parity(seed),
        "highlow": highlow(seed),
        "spread": spread(seed),
        "has_mirror": has_mirror(seed),
        "pairs": get_pairs(seed),
        "triplets": get_triplets(seed),
        "contains_0": "0" in seed,
        "contains_2": "2" in seed,
        "contains_5": "5" in seed,
    }

df["Traits"] = df["Seed"].apply(build_traits)

# =========================
# BASE FREQUENCY
# =========================

perm_counts = df["Result"].value_counts()
total = len(df)

base_freq = (perm_counts / total).to_dict()

# =========================
# MINING
# =========================

results = []

for perm in perm_counts.index:

    perm_df = df[df["Result"] == perm]
    perm_hits = len(perm_df)

    # --- SINGLE TRAITS ---
    for trait in ["sum","root","parity","highlow","spread","has_mirror",
                  "contains_0","contains_2","contains_5"]:

        grouped = df.groupby(df["Traits"].apply(lambda x: x[trait]))

        for val, sub in grouped:
            total_occ = len(sub)
            if total_occ < 10:
                continue

            hits = len(sub[sub["Result"] == perm])

            lift = (hits/total_occ) / base_freq[perm] if base_freq[perm] > 0 else 0

            results.append({
                "perm": perm,
                "trait": trait,
                "value": val,
                "hits": hits,
                "total": total_occ,
                "rate": hits/total_occ,
                "lift": lift
            })

    # --- PAIRS ---
    all_pairs = set(p for row in df["Traits"] for p in row["pairs"])

    for pair in all_pairs:
        sub = df[df["Traits"].apply(lambda x: pair in x["pairs"])]
        total_occ = len(sub)

        if total_occ < 10:
            continue

        hits = len(sub[sub["Result"] == perm])

        lift = (hits/total_occ) / base_freq[perm]

        results.append({
            "perm": perm,
            "trait": "pair",
            "value": pair,
            "hits": hits,
            "total": total_occ,
            "rate": hits/total_occ,
            "lift": lift
        })

    # --- TRIPLETS ---
    all_trip = set(t for row in df["Traits"] for t in row["triplets"])

    for trip in all_trip:
        sub = df[df["Traits"].apply(lambda x: trip in x["triplets"])]
        total_occ = len(sub)

        if total_occ < 10:
            continue

        hits = len(sub[sub["Result"] == perm])

        lift = (hits/total_occ) / base_freq[perm]

        results.append({
            "perm": perm,
            "trait": "triplet",
            "value": trip,
            "hits": hits,
            "total": total_occ,
            "rate": hits/total_occ,
            "lift": lift
        })

# =========================
# FINAL TABLE
# =========================

res_df = pd.DataFrame(results)

# Separation score vs other permutations
res_df["score"] = res_df["lift"] * res_df["rate"]

res_df = res_df.sort_values(["perm","score"], ascending=False)

st.dataframe(res_df.head(500))

st.download_button(
    "Download Full Separator Report",
    res_df.to_csv(index=False),
    "core025_permutation_separator_report_v2.csv"
)
