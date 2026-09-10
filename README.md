# Boggle

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/rbpasker/Boggle/HEAD?labpath=portfolio.ipynb)

Estate portfolio tracking for an inherited Fidelity brokerage account (Transfer on Death),
divided three ways: A 40% / B 40% / C 20%. Beneficiary names and the account number are redacted.

Values against date-of-death basis, live quotes from Yahoo Finance, 555 positions — more than any
hosted portfolio tracker will hold (TradingView caps at 20–150 holdings by plan; Sharesight's
unlimited tier is paid).

## Run

On Binder: click the badge. Everything is preinstalled from `requirements.txt`; run the cells
top to bottom.

Locally:

```
uv run --with pandas --with matplotlib --with openpyxl --with jupyterlab jupyter lab
```

Open `portfolio.ipynb`, Run All. Live quotes come from the Yahoo Finance chart API through
`quotes.py` (stdlib only, no key) and are cached 20 minutes in `data/quotes_cache.json`.
`quotes.get_quotes(syms, max_age_minutes=0)` forces a refresh.

## Files

| Path | What |
|---|---|
| `portfolio.ipynb` | The tracker: load, quote, value against DOD basis, summaries, charts, xlsx export |
| `quotes.py` | Yahoo quote + weekly-history fetcher, on-disk cache |
| `dod_prices.py` | PEP 723 script that (re)builds `data/dod_prices.csv` from Yahoo daily bars |
| `data/holdings.csv` | 555 positions, per-recipient share allocation, 2/28/2026 statement basis |
| `data/dod_prices.csv` | Date-of-death price per symbol with full audit trail (H/L per day, method, splits) |
| `snapshot_YYYY-MM-DD.xlsx` | Written by the last notebook cell (5 sheets incl. the weekly series) |
| `requirements.txt`, `runtime.txt` | Binder environment |
| `build_nb.py` | Regenerates `portfolio.ipynb` from source |

## What the notebook shows

Summary by beneficiary and by asset class; top and bottom movers; concentration (top 25 = 76% of
account value); and a weekly time series from the date of death forward — value by beneficiary,
indexed performance, weekly change, cumulative gain, and drawdown from the running peak.

## Basis

Date of death 2025-12-07, a Sunday. Treas. Reg. §20.2031-2(b): mean of the high–low means on the
nearest trading days either side, 12/05 and 12/08, weighted inversely by intervening trading days
(zero on each side, so equal weights). Mutual funds, §20.2031-8(b): last NAV on or before the DOD,
the 12/05 close.

Yahoo's historical prices are split-adjusted to today's share count. `dod_prices.csv` carries
`F_after_feb`, the product of split ratios after 2/28/2026; the notebook multiplies statement
quantities by it so shares and prices are in the same terms.

## Regenerating DOD prices

```
uv run dod_prices.py --csv data/holdings.csv --out data/dod_prices.csv
```

Optional: `--yahoo-out <file> --recipient Beneficiary A` writes a Yahoo Finance portfolio import CSV;
`--xlsx <file>` fills the DOD override column of the Excel distribution workbook.

## Known gaps

- The 40/40/20 fractional split is an estimate. Fidelity's TOD form gives fractional shares that
  cannot be distributed to the largest-percentage beneficiary and states no tie rule for two equal
  40% shares. Replace `data/holdings.csv` with the executed distribution when Fidelity provides it.
- DOD quantities are assumed equal to 2/28/2026 quantities; the February statement shows no trades,
  earlier activity is not in the record.
- Unpriced: 756CNT929 (Reckitt escrow), TGNA (delisted, Nexstar), TCCPY (not on Yahoo),
  AVB (no Yahoo bars at DOD).
- Yahoo consolidated quotes, not exchange-of-listing prints. Fidelity's date-of-death valuation
  letter controls for the estate return.
