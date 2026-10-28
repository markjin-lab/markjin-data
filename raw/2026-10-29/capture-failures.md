# capture-failures — 2026-10-29 round1

## Baseline mode
- improve/sources.yaml not merged to main; no fetch_primary / public scrapers
- FRED permanently off; zero FRED requests this round
- EIA / 海关 / raw agency: not requested

## arXiv #110
- all_valid: True
- invalid: []

## X pagination (public; tokens private only)
- early-stop (schedule): 0
- page_cap with next_token left for R2: A02, A03, A04, A05, B02, B04, B08, B09, B10, B11, B12, B13, B14, B16, B17
- empty first page (ok): B01

## Other
- none blocking
