"""Boggle — all the machinery behind the plain-language report.

`report.ipynb` calls these functions and shows nothing else. The technical notebook
(`portfolio.ipynb`) works with the DataFrames directly.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import quotes

DATA = Path(__file__).resolve().parent / "data"
DOD = pd.Timestamp("2025-12-07")
DOD_LABEL = "7 December 2025"
RECIPIENTS = ["A", "H", "E"]
SHARE = {"A": "40%", "H": "40%", "E": "20%"}
PAL = {"A": "#3d6b9c", "H": "#c07c3a", "E": "#2e7d5b"}
STYLE = {
    "A": dict(lw=2.2, ls="-"),
    "H": dict(lw=1.5, ls=(0, (5, 2))),
    "E": dict(lw=2.2, ls="-"),
}

# ---------------------------------------------------------------- formatting

def usd(v, _=None):
    if pd.isna(v):
        return "—"
    return ("-" if v < 0 else "") + f"${abs(v):,.0f}"


def usd_k(v, _=None):
    if pd.isna(v):
        return "—"
    return ("-" if v < 0 else "") + f"${abs(v)/1000:,.0f}k"


def _style():
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.dpi": 130, "font.size": 9.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.22, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.titlesize": 11.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.titlepad": 27,
    })
    return plt


def _subtitle(ax, text):
    ax.annotate(text, xy=(0, 1), xycoords="axes fraction", xytext=(0, 7),
                textcoords="offset points", fontsize=8.8, color="#555", va="bottom")


# ---------------------------------------------------------------- data

def load() -> pd.DataFrame:
    """Positions, one row per beneficiary per holding, with date-of-death value."""
    h = pd.read_csv(DATA / "holdings.csv")
    p = pd.read_csv(DATA / "dod_prices.csv")

    long = h.melt(
        id_vars=["Seq", "Section", "Symbol", "Description", "Quantity 2/28/26", "Method"],
        value_vars=[f"{r} Shares" for r in RECIPIENTS],
        var_name="Recipient", value_name="Shares_0228",
    )
    long["Recipient"] = long["Recipient"].str.replace(" Shares", "", regex=False)
    long = long[long["Shares_0228"] > 0].copy()

    cols = ["Symbol", "Yahoo", "Yahoo Type", "Yahoo Exchange", "DOD Price",
            "F_after_feb", "Splits since DOD", "Method", "Flag"]
    df = long.merge(p[cols].rename(columns={"Method": "Price method", "Flag": "Price flag"}),
                    on="Symbol", how="left")
    df["F_after_feb"] = df["F_after_feb"].fillna(1.0)
    df["Shares"] = df["Shares_0228"] * df["F_after_feb"]
    df["DOD Value"] = df["Shares"] * df["DOD Price"]
    return df


def add_prices(df: pd.DataFrame, max_age_minutes: int = 20) -> pd.DataFrame:
    """Attach today's price and the gain since the date of death."""
    syms = sorted(df.loc[df["Yahoo"].notna(), "Yahoo"].unique())
    q = quotes.get_quotes(syms, max_age_minutes=max_age_minutes, verbose=False)
    px = pd.DataFrame([{"Yahoo": s, "Price": r.get("price"), "Quote time": r.get("time")}
                       for s, r in q.items()])
    df = df.drop(columns=[c for c in ("Price", "Quote time") if c in df]).merge(px, on="Yahoo", how="left")
    df["Value"] = df["Shares"] * df["Price"]
    df["Gain"] = df["Value"] - df["DOD Value"]
    return df


def weekly(df: pd.DataFrame, start: str = "2025-12-05") -> pd.DataFrame:
    """Week-by-week value of each share, plus a Total column."""
    syms = sorted(df.loc[df["Yahoo"].notna(), "Yahoo"].unique())
    hist = quotes.get_history(syms, start=start, interval="1wk", verbose=False)

    prices = pd.DataFrame(hist).rename_axis("Date").sort_index()
    prices.index = pd.to_datetime(prices.index)
    prices = prices[prices.index >= DOD - pd.Timedelta(days=3)].ffill()

    shares = df.pivot_table(index="Recipient", columns="Yahoo", values="Shares", aggfunc="sum").fillna(0.0)
    common = [c for c in prices.columns if c in shares.columns]
    V = pd.DataFrame({r: prices[common].mul(shares.loc[r, common], axis=1).sum(axis=1) for r in shares.index})
    V["Total"] = V.sum(axis=1)
    return V


# ---------------------------------------------------------------- headline

def headline(df: pd.DataFrame, V: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("Recipient").agg(DOD=("DOD Value", "sum"), Now=("Value", "sum"))
    g["Change"] = g["Now"] - g["DOD"]
    g["Change %"] = g["Change"] / g["DOD"]
    g.insert(0, "Share of the account", [SHARE[r] for r in g.index])
    g.loc["Everyone together"] = ["100%", g["DOD"].sum(), g["Now"].sum(),
                                  g["Change"].sum(), g["Change"].sum() / g["DOD"].sum()]
    out = g.rename(columns={"DOD": f"Worth on {DOD_LABEL}", "Now": "Worth today",
                            "Change": "Change since then", "Change %": "Change %"})
    out.index.name = None
    return out.style.format({f"Worth on {DOD_LABEL}": usd, "Worth today": usd,
                             "Change since then": usd, "Change %": "{:+.1%}"})


def sentence(df: pd.DataFrame) -> str:
    d, n = df["DOD Value"].sum(), df["Value"].sum()
    ch = n - d
    word = "more" if ch >= 0 else "less"
    return (f"The whole account was worth about {usd(d)} on {DOD_LABEL}. "
            f"Today it is worth about {usd(n)} — {usd(abs(ch))} {word}, a change of {ch/d:+.1%}.")


# ---------------------------------------------------------------- charts

def chart_value(V: pd.DataFrame):
    plt = _style()
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(11, 4.6))
    for r in RECIPIENTS:
        if r in V:
            ax.plot(V.index, V[r], color=PAL[r], label=f"{r}  ({SHARE[r]})", **STYLE[r])

    lo, hi = V[RECIPIENTS].min().min(), V[RECIPIENTS].max().max()
    pad = (hi - lo) * 0.12
    ax.set_ylim(lo - pad, hi + pad)

    ends = sorted(((V[r].iloc[-1], r) for r in RECIPIENTS if r in V), reverse=True)
    for k, (val, r) in enumerate(ends):
        dy = -12 if k and abs(val - ends[k - 1][0]) < (hi - lo) * 0.03 else 0
        ax.annotate(f"{usd_k(val)}", (V.index[-1], val), xytext=(9, dy),
                    textcoords="offset points", va="center", fontsize=9,
                    color=PAL[r], fontweight="bold")

    ax.axvline(DOD, color="#999", lw=1, ls="--")
    ax.annotate(DOD_LABEL, (DOD, ax.get_ylim()[0]), xytext=(6, 9), textcoords="offset points",
                fontsize=8.5, color="#888", style="italic")
    ax.yaxis.set_major_formatter(usd_k)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_title("What each share has been worth, week by week")
    _subtitle(ax, "Two of the shares are the same size, so their lines sit on top of each other — "
                  "the dashed line is the second one.")
    ax.set_xlim(V.index.min() - pd.Timedelta(days=4), V.index.max() + pd.Timedelta(days=34))
    ax.legend(frameon=False, loc="center left", fontsize=9)
    fig.tight_layout()
    return fig


def chart_indexed(V: pd.DataFrame):
    plt = _style()
    import matplotlib.dates as mdates

    idx = V["Total"] / V["Total"].iloc[0] * 100
    fig, ax = plt.subplots(figsize=(11, 3.9))
    ax.plot(idx.index, idx, lw=2.2, color="#3d6b9c")
    ax.axhline(100, color="#999", lw=1, ls="--")
    ax.fill_between(idx.index, 100, idx, where=idx >= 100, color="#2e7d5b", alpha=0.15)
    ax.fill_between(idx.index, 100, idx, where=idx < 100, color="#a4373a", alpha=0.15)
    ax.annotate(f"{idx.iloc[-1]:.1f}", (idx.index[-1], idx.iloc[-1]), xytext=(9, 0),
                textcoords="offset points", va="center", fontweight="bold", color="#3d6b9c")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_xlim(idx.index.min() - pd.Timedelta(days=4), idx.index.max() + pd.Timedelta(days=26))
    ax.set_title("The same picture, as a score out of 100")
    _subtitle(ax, f"100 is what the account was worth on {DOD_LABEL}. Above the line is up; below is down. "
                  f"Today it reads {idx.iloc[-1]:.1f}.")
    fig.tight_layout()
    return fig


def chart_weekly_change(V: pd.DataFrame):
    plt = _style()
    import matplotlib.dates as mdates

    wk = V["Total"].diff().dropna()
    up, dn = (wk >= 0).sum(), (wk < 0).sum()
    fig, ax = plt.subplots(figsize=(11, 3.9))
    ax.bar(wk.index, wk.values, width=5.5, color=np.where(wk.values >= 0, "#2e7d5b", "#a4373a"))
    ax.axhline(0, color="#444", lw=0.9)
    ax.yaxis.set_major_formatter(usd_k)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_title("Good weeks and bad weeks")
    _subtitle(ax, f"Each bar is one week's change for the whole account. "
                  f"{up} weeks up, {dn} weeks down. Best week {usd(wk.max())}, worst {usd(wk.min())}.")
    fig.tight_layout()
    return fig


def chart_gain_and_dip(V: pd.DataFrame):
    plt = _style()
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.0))
    for r in RECIPIENTS:
        if r in V:
            ax[0].plot(V.index, V[r] - V[r].iloc[0], color=PAL[r], label=r, **STYLE[r])
    ax[0].axhline(0, color="#999", lw=1, ls="--")
    ax[0].yaxis.set_major_formatter(usd_k)
    ax[0].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax[0].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax[0].set_title("Money made or lost since then")
    _subtitle(ax[0], "Starting from zero on the date of death.")
    ax[0].legend(frameon=False, fontsize=8.5)

    dd = V["Total"] / V["Total"].cummax() - 1
    ax[1].fill_between(dd.index, dd.values, 0, color="#a4373a", alpha=0.28)
    ax[1].plot(dd.index, dd.values, lw=1.3, color="#a4373a")
    ax[1].yaxis.set_major_formatter(lambda v, _: f"{v:.1%}")
    ax[1].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax[1].xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax[1].set_title("How far below its best")
    _subtitle(ax[1], f"Worst dip so far: {dd.min():.1%} below the highest point reached.")
    fig.tight_layout()
    return fig


def chart_mix(df: pd.DataFrame):
    plt = _style()
    NAMES = {
        "Exchange Traded Products": "Index funds (ETFs)",
        "Stock Funds": "Stock mutual funds",
        "Bond Funds": "Bond funds",
        "Stocks": "Individual company shares",
        "Short-term Funds": "Cash",
        "Other": "Real-estate trusts",
    }
    s = df.groupby("Section")["Value"].sum().rename(index=NAMES).sort_values()
    total = s.sum()
    fig, ax = plt.subplots(figsize=(11, 3.6))
    bars = ax.barh(s.index, s.values, color="#3d6b9c", height=0.62)
    for b, v in zip(bars, s.values):
        ax.annotate(f"{usd_k(v)}  ({v/total:.0%})", (v, b.get_y() + b.get_height() / 2),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=8.5, color="#333")
    ax.set_xlim(0, s.max() * 1.28)
    ax.xaxis.set_major_formatter(usd_k)
    ax.set_title("What the money is invested in")
    _subtitle(ax, "The whole account, today, grouped by kind of investment.")
    fig.tight_layout()
    return fig


def chart_movers(df: pd.DataFrame, n: int = 10):
    plt = _style()
    a = (df[df["Price"].notna()]
           .groupby(["Symbol", "Description"], as_index=False)
           .agg(Gain=("Gain", "sum")))
    a["Name"] = a["Description"].str.split(r"\(| ADR| ADS| SPON| UNSP| COM ", regex=True).str[0].str.title().str.strip()
    a["Label"] = a["Name"].str.slice(0, 30) + "  (" + a["Symbol"] + ")"
    b = pd.concat([a.nsmallest(n, "Gain"), a.nlargest(n, "Gain").iloc[::-1]])
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.barh(b["Label"], b["Gain"], color=np.where(b["Gain"] >= 0, "#2e7d5b", "#a4373a"), height=0.68)
    ax.axvline(0, color="#444", lw=0.9)
    ax.xaxis.set_major_formatter(usd)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_title(f"The {n} biggest winners and {n} biggest losers")
    _subtitle(ax, "Whole account, in dollars gained or lost since the date of death.")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------- tables

def biggest_holdings(df: pd.DataFrame, n: int = 15):
    a = (df[df["Price"].notna()]
           .groupby(["Symbol", "Description"], as_index=False)
           .agg(Now=("Value", "sum"), DOD=("DOD Value", "sum")))
    a["Change"] = a["Now"] - a["DOD"]
    a["Share of account"] = a["Now"] / a["Now"].sum()
    a["Investment"] = a["Description"].str.slice(0, 46).str.title()
    top = a.nlargest(n, "Now")[["Investment", "Symbol", "Now", "Change", "Share of account"]]
    return (top.rename(columns={"Now": "Worth today", "Change": "Change since the date of death"})
               .style.format({"Worth today": usd, "Change since the date of death": usd,
                              "Share of account": "{:.1%}"}).hide(axis="index"))


def recent_weeks(V: pd.DataFrame, n: int = 10):
    t = pd.DataFrame({
        "Whole account": V["Total"],
        "Change that week": V["Total"].diff(),
        "Change since the start": V["Total"] - V["Total"].iloc[0],
    })
    t.index = t.index.strftime("%d %b %Y")
    t.index.name = "Week ending"
    return t.tail(n).style.format({"Whole account": usd, "Change that week": usd,
                                   "Change since the start": usd})


def not_counted(df: pd.DataFrame):
    m = df[df["Price"].isna()]
    if m.empty:
        return None
    g = (m.groupby(["Symbol", "Description"], as_index=False)
           .agg(Shares=("Shares", "sum")))
    g["Investment"] = g["Description"].str.slice(0, 46).str.title()
    return g[["Investment", "Symbol", "Shares"]].style.format({"Shares": "{:,.3f}"}).hide(axis="index")
