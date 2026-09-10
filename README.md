# Boggle

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/rbpasker/Boggle/HEAD?labpath=report.ipynb)

Tracks an inherited Fidelity brokerage account (Transfer on Death) divided three ways —
**A** 40%, **H** 40%, **E** 20% — valued against date-of-death basis with live market prices.
555 positions. Beneficiary names and account identifiers are redacted.

## Two notebooks

**`report.ipynb`** — the plain-English version. Charts with written explanations, no visible code
(the code cells are collapsed). This is the one the Binder badge opens, and the one to send to
someone who does not read Python.

**`portfolio.ipynb`** — the working version. Same data, DataFrames exposed, tables and diagnostics.

Either way: **Run ▸ Restart Kernel and Run All Cells**, then wait two to three minutes while
~550 quotes and ~550 weekly histories are fetched.

## Run

On Binder: click the badge.

Locally:

```
uv run --with pandas --with matplotlib --with openpyxl --with jupyterlab jupyter lab
```

## What the report shows

The headline table (each share's value on the date of death, today, and the change), then week-by-week
value per beneficiary, the same series indexed to 100, weekly gains and losses, cumulative gain,
drawdown from the running peak, the asset-class mix, the largest holdings, and the biggest movers.

## Files

| Path | What |
|---|---|
| `report.ipynb` | Plain-language report — narrative plus charts, code hidden |
| `portfolio.ipynb` | Technical notebook — same data, working DataFrames |
| `boggle.py` | Everything behind the report: loading, valuation, charts, tables |
| `quotes.py` | Yahoo Finance quote and weekly-history fetcher, on-disk cache |
| `dod_prices.py` | PEP 723 script; rebuilds `data/dod_prices.csv` from Yahoo daily bars |
| `build_report.py`, `build_nb.py` | Regenerate the two notebooks from source |
| `data/holdings.csv` | 555 positions, per-beneficiary share allocation, 2/28/2026 statement basis |
| `data/dod_prices.csv` | Date-of-death price per symbol with full audit trail |
| `requirements.txt`, `runtime.txt` | Binder environment |

## Basis

Date of death 2025-12-07, a Sunday. Treas. Reg. §20.2031-2(b): the mean of the high–low means on
the nearest trading days either side, 12/05 and 12/08, weighted inversely by intervening trading
days — zero on each side, so equal weights. Mutual funds, §20.2031-8(b): the last NAV on or before
the date of death, the 12/05 close.

Yahoo's historical prices are split-adjusted to today's share count. `data/dod_prices.csv` carries
`F_after_feb`, the product of split ratios after 2/28/2026; share counts are multiplied by it so
quantities and prices stay in the same terms across any split.

## Regenerating date-of-death prices

```
uv run dod_prices.py --csv data/holdings.csv --out data/dod_prices.csv
```

## Known gaps

- The 40/40/20 fractional split is an estimate. Fidelity's TOD form assigns fractional shares that
  cannot be distributed to the largest-percentage beneficiary and states no tie rule for two equal
  40% shares. Replace `data/holdings.csv` with the executed distribution when it arrives.
- Date-of-death quantities are assumed equal to 2/28/2026 quantities; the February statement shows
  no trades, and earlier activity is not in the record.
- Four holdings carry no price and are excluded from totals: a Reckitt escrow entitlement, TGNA
  (delisted after the Nexstar acquisition), TCCPY (absent from Yahoo), and AVB (no bars at the DOD).
- Yahoo consolidated quotes, delayed and unofficial. Fidelity's date-of-death valuation letter
  controls for the estate return.
