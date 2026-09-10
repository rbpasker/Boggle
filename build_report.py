"""Builds report.ipynb — the plain-language version. Code cells are collapsed by default
(JupyterLab honours metadata.jupyter.source_hidden), so a reader sees prose and pictures."""
import json, pathlib

C = []
def _lines(s):
    t = s.strip("\n")
    parts = t.split("\n")
    return [ln + "\n" for ln in parts[:-1]] + [parts[-1]]

def md(s):
    C.append({"cell_type": "markdown", "metadata": {}, "source": _lines(s)})

def code(s, hide=True):
    C.append({
        "cell_type": "code", "execution_count": None, "outputs": [],
        "metadata": {"jupyter": {"source_hidden": bool(hide)}, "tags": ["hide-input"]},
        "source": _lines(s),
    })

md("""
# The inheritance, in plain English

This page tracks a brokerage account that was divided among three people. It shows what each
person's share was worth on the day the account holder died, what it is worth now, and how it has
moved in between.

**How to use it.** From the menu at the top choose **Run ▸ Restart Kernel and Run All Cells**, then
wait. It looks up today's price for about 550 investments, so give it two or three minutes. The
numbers and pictures below fill in as it goes.

**Three shares.** Two people receive 40% each — shown as **A** and **H** — and one receives 20%,
shown as **E**.

**The starting line.** Everything is measured from **7 December 2025**, the date of death. That is
the date the tax rules use to set the starting value of an inheritance, so it is the fair place to
measure gains and losses from. Anything that happened before that date belongs to the estate, not
to the three people.
""")

code("""
import boggle

positions = boggle.add_prices(boggle.load())
print("Prices loaded. Now fetching week-by-week history…")
V = boggle.weekly(positions)
print("Done.")
""", hide=False)

md("""
---

## The short answer
""")

code("""
print(boggle.sentence(positions))
""")

code("""
boggle.headline(positions, V)
""")

md("""
Read that table across: what each share was worth on the date of death, what it is worth today, and
the difference. "Change %" is the same difference expressed as a percentage, which is the fairest
way to compare shares of different sizes — all three should move by roughly the same percentage,
because all three own slices of the same investments.

---

## Week by week

Each point is one week. The lines start on the date of death and run to the present.
""")

code("""
boggle.chart_value(V);
""")

md("""
Because two of the shares are exactly the same size, their lines lie on top of one another. The
dashed line is the second of the two.

The next picture is the same information with the dollar amounts taken out. Everything starts at
100 on the date of death, so a reading of 105 means "up 5% since then". This makes the shape of the
movement easier to see than the dollar chart, where a big number can hide a small change.
""")

code("""
boggle.chart_indexed(V);
""")

md("""
---

## Good weeks and bad weeks

Markets do not move in a straight line. Green bars are weeks the account gained value; red bars are
weeks it lost value. A run of red bars is normal and does not mean anything has gone wrong.
""")

code("""
boggle.chart_weekly_change(V);
""")

md("""
The two pictures below say the same thing in two different ways. On the left, the money made or
lost by each share since the date of death, starting from zero. On the right, how far the account
has fallen below the best value it had reached — a way of seeing the size of the rough patches.
Zero means "at its highest point ever".
""")

code("""
boggle.chart_gain_and_dip(V);
""")

md("""
---

## What the money is actually in

The account is not a single investment. It holds several hundred, in a few broad groups:

- **Index funds (ETFs)** — baskets that hold hundreds of companies at once. Cheap and diversified.
- **Stock mutual funds** — similar baskets, run by a manager who picks the contents.
- **Individual company shares** — small stakes in specific companies.
- **Bond funds** — loans to governments and companies; steadier than shares, lower return.
- **Cash** — money waiting to be invested.
- **Real-estate trusts** — companies that own property and pass the rent through.
""")

code("""
boggle.chart_mix(positions);
""")

md("""
A small number of holdings account for most of the value. The rest are hundreds of very small
positions — often a fraction of a single share — left over from the way the account was managed.
""")

code("""
boggle.biggest_holdings(positions)
""")

md("""
---

## What went up and what went down

Individual investments move in different directions. These are the biggest movers in dollar terms
across the whole account, not per person. A large loss on this list is usually a large holding
moving a little, not a small holding collapsing.
""")

code("""
boggle.chart_movers(positions);
""")

md("""
---

## The last few weeks in numbers
""")

code("""
boggle.recent_weeks(V)
""")

md("""
---

## Things worth knowing

**These are estimates, not a statement.** The official numbers come from the brokerage. This page
is a reconstruction from a monthly statement plus public market prices, and it is useful for
watching the trend, not for filing anything.

**The split is an estimate too.** Most of the account could not be divided into whole shares, so
it was split 40/40/20 down to fractions. The brokerage's own rule for leftover fractions may
differ slightly. When the final distribution paperwork arrives, the underlying file can be
replaced and everything here recalculates.

**A few holdings have no price.** One is an escrow entitlement from a corporate merger with no
market value; another was in a company that was bought out and no longer trades. They are left out
of the totals rather than guessed at.

**Prices are delayed and unofficial.** They come from a free public source, are not exchange-official,
and can be fifteen or twenty minutes behind. Fine for a weekly picture; not for trading.
""")

code("""
nc = boggle.not_counted(positions)
nc if nc is not None else print("Every holding has a price today.")
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
pathlib.Path("report.ipynb").write_text(json.dumps(nb, indent=1))
print("report cells:", len(C))
