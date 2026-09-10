import json, pathlib

C = []
def _lines(s):
    t = s.strip("\n")
    return [ln + "\n" for ln in t.split("\n")[:-1]] + [t.split("\n")[-1]]
def md(s): C.append({"cell_type": "markdown", "metadata": {}, "source": _lines(s)})
def code(s): C.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": _lines(s)})

md("""
# Boggle — estate portfolio tracker

Tracks the three-way distribution of an inherited Fidelity brokerage account (Transfer on Death)
against date-of-death basis. Beneficiary names and the account number are redacted.

- **Holdings** — 555 positions from the Feb 2026 statement. 183 assigned outright per the
  distribution CSV; the remaining 372 split 40/40/20 A / B / C as fractional shares.
- **Basis** — date of death 2025-12-07 (Sunday). Treas. Reg. §20.2031-2(b): mean of the high–low
  means on 12/05 and 12/08. Mutual funds §20.2031-8(b): last NAV on or before the DOD.
- **Prices** — Yahoo Finance chart API, stdlib only, cached in `data/quotes_cache.json`.
  Yahoo history is split-adjusted to today's share count, so quantities are scaled by the
  post-2/28 split factor `F_after_feb` and both price series are in the same terms.

Run locally:

```
uv run --with pandas --with matplotlib --with openpyxl --with jupyterlab jupyter lab
```

or open it on Binder from the badge in the README. On Binder, run the cells top to bottom;
quotes are fetched live and cached for the session only.
""")

code("""
from pathlib import Path
import pandas as pd, numpy as np
import quotes

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")

BASE = Path.cwd()
DATA = BASE / "data"
RECIPIENTS = ["A", "H", "E"]
DOD = pd.Timestamp("2025-12-07")
""")

md("## Load")

code("""
h = pd.read_csv(DATA / "holdings.csv")
p = pd.read_csv(DATA / "dod_prices.csv")

# one row per (symbol, recipient) with non-zero shares
long = h.melt(
    id_vars=["Seq", "Section", "Symbol", "Description", "Quantity 2/28/26", "Method"],
    value_vars=[f"{r} Shares" for r in RECIPIENTS],
    var_name="Recipient", value_name="Shares_0228",
)
long["Recipient"] = long["Recipient"].str.replace(" Shares", "", regex=False)
long = long[long["Shares_0228"] > 0].copy()

cols = ["Symbol", "Yahoo", "Yahoo Type", "Yahoo Exchange", "DOD Price", "F_after_feb", "Splits since DOD", "Method", "Flag"]
df = long.merge(p[cols].rename(columns={"Method": "Price method", "Flag": "Price flag"}), on="Symbol", how="left")
df["F_after_feb"] = df["F_after_feb"].fillna(1.0)
df["Shares"] = df["Shares_0228"] * df["F_after_feb"]          # today's share count
df["DOD Value"] = df["Shares"] * df["DOD Price"]

print(f"{len(df)} position-rows, {df.Symbol.nunique()} symbols, {df.Recipient.nunique()} recipients")
df.head()
""")

md("## Live quotes")

code("""
syms = sorted(df.loc[df["Yahoo"].notna(), "Yahoo"].unique())
q = quotes.get_quotes(syms, max_age_minutes=20)      # max_age_minutes=0 forces a refresh

px = pd.DataFrame(
    [{"Yahoo": s, "Price": r.get("price"), "Quote time": r.get("time"), "Quote error": r.get("error")}
     for s, r in q.items()]
)
df = df.drop(columns=[c for c in ("Price", "Quote time", "Quote error") if c in df], errors="ignore").merge(px, on="Yahoo", how="left")
df["Value"] = df["Shares"] * df["Price"]
df["Gain"] = df["Value"] - df["DOD Value"]
df["Gain %"] = np.where(df["DOD Value"] > 0, df["Gain"] / df["DOD Value"], np.nan)

missing = df[df["Price"].isna()]
print(f"{df['Price'].notna().sum()} of {len(df)} rows priced; {missing.Symbol.nunique()} symbols unpriced")
if len(missing):
    display(missing.groupby("Symbol")[["Shares", "DOD Value"]].sum().join(
        p.set_index("Symbol")[["Method", "Flag"]]).sort_values("DOD Value", ascending=False))
""")

md("## Summary by recipient")

code("""
def summarize(frame, by):
    g = frame.groupby(by, dropna=False).agg(
        Positions=("Symbol", "nunique"),
        DOD=("DOD Value", "sum"),
        Now=("Value", "sum"),
        Gain=("Gain", "sum"),
    )
    g["Gain %"] = np.where(g["DOD"] > 0, g["Gain"] / g["DOD"], np.nan)
    return g.sort_values("Now", ascending=False)

s = summarize(df, "Recipient")
s.loc["TOTAL"] = [df.Symbol.nunique(), df["DOD Value"].sum(), df["Value"].sum(), df["Gain"].sum(),
                  df["Gain"].sum() / df["DOD Value"].sum()]
s.style.format({"DOD": "${:,.0f}", "Now": "${:,.0f}", "Gain": "${:,.0f}", "Gain %": "{:.2%}"})
""")

md("## By asset class")

code("""
summarize(df, ["Recipient", "Section"]).style.format(
    {"DOD": "${:,.0f}", "Now": "${:,.0f}", "Gain": "${:,.0f}", "Gain %": "{:.2%}"})
""")

md("## Movers since date of death — whole account")

code("""
acct = df.groupby(["Symbol", "Description"], as_index=False).agg(
    Shares=("Shares", "sum"), DOD_px=("DOD Price", "first"), Price=("Price", "first"),
    DOD=("DOD Value", "sum"), Now=("Value", "sum"), Gain=("Gain", "sum"))
acct["Gain %"] = np.where(acct["DOD"] > 0, acct["Gain"] / acct["DOD"], np.nan)
acct = acct.dropna(subset=["Gain"])

fmt = {"DOD_px": "${:,.2f}", "Price": "${:,.2f}", "DOD": "${:,.0f}", "Now": "${:,.0f}",
       "Gain": "${:,.0f}", "Gain %": "{:.1%}"}
print("Top 15 by dollar gain")
display(acct.nlargest(15, "Gain").style.format(fmt).hide(axis="index"))
print("Bottom 15 by dollar gain")
display(acct.nsmallest(15, "Gain").style.format(fmt).hide(axis="index"))
""")

md("## Concentration")

code("""
top = acct.nlargest(25, "Now").copy()
top["Share of account"] = top["Now"] / acct["Now"].sum()
print(f"top 25 of {len(acct)} positions = {top['Share of account'].sum():.1%} of account value")
top.style.format({**fmt, "Share of account": "{:.2%}"}).hide(axis="index")
""")

md("## Charts")

code("""
import matplotlib.pyplot as plt
plt.rcParams.update({"figure.dpi": 120, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))

r = summarize(df, "Recipient")
x = np.arange(len(r))
ax[0].bar(x - 0.2, r["DOD"], 0.4, label="At date of death", color="#9aa5b1")
ax[0].bar(x + 0.2, r["Now"], 0.4, label="Current", color="#3d6b9c")
ax[0].set_xticks(x); ax[0].set_xticklabels(r.index)
ax[0].set_ylabel("USD"); ax[0].legend(frameon=False)
ax[0].yaxis.set_major_formatter(lambda v, _: f"${v/1000:,.0f}k")
ax[0].set_title("Value by recipient", loc="left")

sec = df.groupby("Section")["Value"].sum().sort_values()
ax[1].barh(sec.index, sec.values, color="#3d6b9c")
ax[1].xaxis.set_major_formatter(lambda v, _: f"${v/1000:,.0f}k")
ax[1].set_title("Current value by asset class", loc="left")

fig.tight_layout()
""")

code("""
fig, ax = plt.subplots(figsize=(11, 3.6))
m = acct.nlargest(12, "Gain").iloc[::-1]
n = acct.nsmallest(12, "Gain")
b = pd.concat([n, m])
ax.barh(b["Symbol"], b["Gain"], color=np.where(b["Gain"] >= 0, "#2e7d5b", "#a4373a"))
ax.axvline(0, color="#333", lw=0.8)
ax.xaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
ax.set_title("Largest gains and losses since 2025-12-07 (whole account)", loc="left")
fig.tight_layout()
""")

md("""
## Weekly history since the date of death

Weekly closes per symbol from 2025-12-05 forward, valued at each beneficiary's share count.
Yahoo closes are split-adjusted to today's share count, the same basis as the DOD prices, so the
series is continuous across any split.
""")

code("""
hist = quotes.get_history(syms, start="2025-12-05", interval="1wk", max_age_hours=12)

H = (pd.DataFrame(hist)                       # index: date string, columns: Yahoo symbol
       .rename_axis("Date").sort_index())
H.index = pd.to_datetime(H.index)
H = H[H.index >= DOD - pd.Timedelta(days=3)]
H = H.ffill()                                  # carry the last close over non-trading gaps

# shares per (recipient, symbol) -> weekly value matrix per recipient
shares = df.pivot_table(index="Recipient", columns="Yahoo", values="Shares", aggfunc="sum").fillna(0.0)
common = [c for c in H.columns if c in shares.columns]
V = pd.DataFrame({r: H[common].mul(shares.loc[r, common], axis=1).sum(axis=1) for r in shares.index})
V["Total"] = V.sum(axis=1)

print(f"{len(H)} weekly points, {len(common)} symbols with history "
      f"({H.index.min():%Y-%m-%d} to {H.index.max():%Y-%m-%d})")
V.tail(6).style.format("${:,.0f}")
""")

code("""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams.update({"figure.dpi": 130, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25,
                     "grid.linewidth": 0.6, "axes.axisbelow": True})
PAL = {"A": "#3d6b9c", "H": "#c07c3a", "E": "#2e7d5b"}
usd_k = lambda v, _=None: ("-" if v < 0 else "") + f"${abs(v)/1000:,.0f}k"

# A and B hold equal 40% shares, so their curves coincide: B is drawn dashed to keep both visible.
STYLE = {"A": dict(lw=2.0, ls="-"),
         "H": dict(lw=1.4, ls=(0, (5, 2))),
         "E": dict(lw=2.0, ls="-")}

fig, ax = plt.subplots(figsize=(11, 4.4))
for r in RECIPIENTS:
    if r in V:
        ax.plot(V.index, V[r], color=PAL[r], label=r, **STYLE[r])

lo, hi = V[RECIPIENTS].min().min(), V[RECIPIENTS].max().max()
pad = (hi - lo) * 0.10
ax.set_ylim(lo - pad, hi + pad)

# end-of-series labels, nudged apart where A and B coincide
ends = sorted(((V[r].iloc[-1], r) for r in RECIPIENTS if r in V), reverse=True)
for k, (val, r) in enumerate(ends):
    dy = 0
    if k and abs(val - ends[k - 1][0]) < (hi - lo) * 0.03:
        dy = -11
    ax.annotate(f"{r[-1]}  ${val/1000:,.0f}k", (V.index[-1], val), xytext=(8, dy),
                textcoords="offset points", va="center", fontsize=8.5,
                color=PAL[r], fontweight="bold")

ax.axvline(DOD, color="#888", lw=1, ls="--")
ax.annotate("date of death", (DOD, ax.get_ylim()[0]), xytext=(5, 8), textcoords="offset points",
            fontsize=8, color="#888", style="italic")
ax.yaxis.set_major_formatter(lambda v, _: f"${v/1000:,.0f}k")
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
ax.set_title("Portfolio value by beneficiary, weekly", loc="left", fontsize=11, fontweight="bold")
ax.set_xlim(V.index.min() - pd.Timedelta(days=4), V.index.max() + pd.Timedelta(days=32))
ax.legend(frameon=False, loc="center left", fontsize=8.5)
fig.tight_layout()
""")

code("""
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))

idx = V[["Total"]].div(V["Total"].iloc[0]) * 100
ax[0].plot(idx.index, idx["Total"], lw=2, color="#3d6b9c")
ax[0].axhline(100, color="#666", lw=1, ls="--")
ax[0].fill_between(idx.index, 100, idx["Total"], where=idx["Total"] >= 100, color="#2e7d5b", alpha=0.15)
ax[0].fill_between(idx.index, 100, idx["Total"], where=idx["Total"] < 100, color="#a4373a", alpha=0.15)
ax[0].xaxis.set_major_locator(mdates.MonthLocator(interval=2)); ax[0].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
ax[0].set_title(f"Indexed to 100 at DOD  (now {idx['Total'].iloc[-1]:.1f})", loc="left")

wk = V["Total"].diff().dropna()
ax[1].bar(wk.index, wk.values, width=5.5, color=np.where(wk.values >= 0, "#2e7d5b", "#a4373a"))
ax[1].axhline(0, color="#333", lw=0.8)
ax[1].yaxis.set_major_formatter(usd_k)
ax[1].xaxis.set_major_locator(mdates.MonthLocator(interval=2)); ax[1].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
ax[1].set_title("Weekly change, whole account", loc="left")

fig.tight_layout()
""")

code("""
# Cumulative gain by beneficiary, and drawdown from the running peak
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))

for r in RECIPIENTS:
    if r in V:
        ax[0].plot(V.index, V[r] - V[r].iloc[0], lw=1.8, color=PAL[r], label=r)
ax[0].axhline(0, color="#666", lw=1, ls="--")
ax[0].yaxis.set_major_formatter(usd_k)
ax[0].xaxis.set_major_locator(mdates.MonthLocator(interval=2)); ax[0].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
ax[0].set_title("Cumulative gain since DOD", loc="left"); ax[0].legend(frameon=False)

dd = V["Total"] / V["Total"].cummax() - 1
ax[1].fill_between(dd.index, dd.values, 0, color="#a4373a", alpha=0.3)
ax[1].plot(dd.index, dd.values, lw=1.2, color="#a4373a")
ax[1].yaxis.set_major_formatter(lambda v, _: f"{v:.1%}")
ax[1].xaxis.set_major_locator(mdates.MonthLocator(interval=2)); ax[1].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
ax[1].set_title(f"Drawdown from peak  (worst {dd.min():.1%})", loc="left")

fig.tight_layout()
""")

code("""
# Weekly table: value, change, cumulative since DOD
tbl = pd.DataFrame({
    "Total": V["Total"],
    "Δ week": V["Total"].diff(),
    "Δ since DOD": V["Total"] - V["Total"].iloc[0],
    "% since DOD": V["Total"] / V["Total"].iloc[0] - 1,
})
tbl.index = tbl.index.strftime("%Y-%m-%d")
tbl.tail(16).style.format({"Total": "${:,.0f}", "Δ week": "${:,.0f}",
                           "Δ since DOD": "${:,.0f}", "% since DOD": "{:+.2%}"})
""")

md("## Export snapshot")

code("""
stamp = pd.Timestamp.now().strftime("%Y-%m-%d")
out = BASE / f"snapshot_{stamp}.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as w:
    summarize(df, "Recipient").to_excel(w, sheet_name="By recipient")
    summarize(df, ["Recipient", "Section"]).to_excel(w, sheet_name="By asset class")
    acct.sort_values("Now", ascending=False).to_excel(w, sheet_name="Positions", index=False)
    df.sort_values(["Recipient", "Value"], ascending=[True, False]).to_excel(w, sheet_name="Detail", index=False)\n    V.to_excel(w, sheet_name="Weekly")
print("wrote", out)
""")

md("""
## Notes and limits

- The 40/40/20 fractional split is an **estimate**. Fidelity's TOD form assigns fractional shares
  that cannot be distributed to the beneficiary with the largest percentage; Beneficiaries A and B hold
  equal 40% shares and the form states no tie rule. Replace `data/holdings.csv` with Fidelity's
  executed distribution when it is available.
- Quantities at the date of death are assumed equal to the 2/28/2026 statement quantities. The
  February statement shows no trades in this account; December–January activity is not in the record.
- Unpriced: `756CNT929` (Reckitt escrow, no market), `TGNA` (delisted, Nexstar acquisition),
  `TCCPY` (not on Yahoo), `AVB` (no Yahoo bars at the DOD). These carry no value in the totals.
- `data/dod_prices.csv` holds the full audit trail: high, low and mean for each of 12/05 and 12/08,
  the method applied, and every split event since the DOD. Regenerate it with `dod_prices.py`.
- Prices are Yahoo consolidated quotes, not exchange-of-listing prints. For the estate return,
  Fidelity's date-of-death valuation letter controls.
""")

nb = {
    "cells": C,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
pathlib.Path("portfolio.ipynb").write_text(json.dumps(nb, indent=1))
print("cells:", len(C))
