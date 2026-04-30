import pandas as pd
from collections import Counter, defaultdict

# =========================
# LOAD DATA
# =========================
df = pd.read_csv("your_history_file.csv")  # <-- CHANGE PATH
df["Result"] = df["Result"].astype(str).str.zfill(4)

# =========================
# HELPERS
# =========================
def get_digits(num):
    return [int(d) for d in num]

def get_member(num):
    counts = Counter(num)
    if counts == Counter({'0':2,'0':2,'2':1,'5':1}): return "0025"
    if counts == Counter({'2':2,'0':1,'5':1}): return "0225"
    if counts == Counter({'5':2,'0':1,'2':1}): return "0255"
    return None

# =========================
# BUILD SEED → WINNER PAIRS
# =========================
df["Seed"] = df["Result"].shift(1)
df = df.dropna().copy()

df["SeedDigits"] = df["Seed"].apply(get_digits)
df["WinDigits"] = df["Result"].apply(get_digits)

df["SeedMember"] = df["Seed"].apply(get_member)
df["WinMember"] = df["Result"].apply(get_member)

# Keep only Core025 transitions
df = df[df["WinMember"].notna()]

# =========================
# 1. POSITIONAL MAPPING
# =========================
pos_map = defaultdict(lambda: defaultdict(int))

for _, row in df.iterrows():
    s = row["SeedDigits"]
    w = row["WinDigits"]
    for i in range(4):
        for j in range(4):
            pos_map[f"S{i+1}->{j+1}"][(s[i], w[j])] += 1

pos_df = []
for k, v in pos_map.items():
    for pair, count in v.items():
        pos_df.append([k, pair[0], pair[1], count])

pos_df = pd.DataFrame(pos_df, columns=["Mapping","SeedDigit","WinDigit","Count"])

# =========================
# 2. DOUBLE DIGIT ANALYSIS
# =========================
double_counts = Counter()
double_positions = defaultdict(Counter)

for _, row in df.iterrows():
    digits = row["Result"]
    c = Counter(digits)
    for d, cnt in c.items():
        if cnt == 2:
            double_counts[d] += 1
            positions = [i for i, x in enumerate(digits) if x == d]
            double_positions[d][tuple(positions)] += 1

double_df = pd.DataFrame(double_counts.items(), columns=["Digit","DoubleCount"])

# =========================
# 3. MEMBER TRANSITIONS
# =========================
transition = pd.crosstab(df["SeedMember"], df["WinMember"])

# =========================
# 4. SUM + PARITY ANALYSIS
# =========================
df["Sum"] = df["Result"].apply(lambda x: sum(map(int, x)))
df["Parity"] = df["Result"].apply(lambda x: "".join(["E" if int(d)%2==0 else "O" for d in x]))

sum_member = pd.crosstab(df["Sum"], df["WinMember"])
parity_member = pd.crosstab(df["Parity"], df["WinMember"])

# =========================
# SAVE RESULTS
# =========================
pos_df.to_csv("positional_mapping.csv", index=False)
double_df.to_csv("double_digit_counts.csv", index=False)
transition.to_csv("member_transition.csv")
sum_member.to_csv("sum_to_member.csv")
parity_member.to_csv("parity_to_member.csv")

print("DONE — files exported")
