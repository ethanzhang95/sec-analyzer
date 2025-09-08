# sec_resolver.py
from __future__ import annotations
import os, json, time, sys, re
import requests

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

def _normalize_variants(ticker: str) -> list[str]:
    """Generate common variants for class tickers (dot, hyphen, none)."""
    t = ticker.strip().upper()
    if not t:
        return []
    variants = {t}
    if "." in t:
        variants.add(t.replace(".", "-"))   # BRK.A -> BRK-A
        variants.add(t.replace(".", ""))    # BRK.A -> BRKA
    if "-" in t:
        variants.add(t.replace("-", "."))   # BRK-A -> BRK.A
        variants.add(t.replace("-", ""))    # BRK-A -> BRKA
    return list(variants)

class TickerResolver:
    def __init__(self, user_agent: str):
        if not user_agent or "@" not in user_agent:
            raise ValueError("Provide a meaningful User-Agent (e.g., 'Your Name (you@email)')")
        self.ua = user_agent
        # maps: ticker_variant -> {"cik": "000...", "title": "Company Name", "canonical": "TICKER"}
        self._map: dict[str, dict] = {}

    def load(self, *, cache_path: str = ".cache_company_tickers.json", force_refresh: bool = False) -> None:
        data = None
        if (not force_refresh) and os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                data = json.load(f)
        else:
            resp = requests.get(SEC_TICKERS_URL, headers={"User-Agent": self.ua}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            with open(cache_path, "w") as f:
                json.dump(data, f)
            time.sleep(0.5)  # be polite to sec.gov

        # Build mapping with variants
        mapping: dict[str, dict] = {}
        for entry in data.values():
            cik = str(entry["cik_str"]).zfill(10)
            ticker = entry["ticker"].upper()
            title = entry.get("title", "")
            rec = {"cik": cik, "title": title, "canonical": ticker}
            mapping[ticker] = rec
            # add common variants
            for v in _normalize_variants(ticker):
                mapping.setdefault(v, rec)
        self._map = mapping

    def cik_for(self, ticker_or_cik: str | None) -> str | None:
        """Return 10-digit CIK for a ticker or numeric CIK input."""
        if not ticker_or_cik:
            return None
        s = ticker_or_cik.strip().upper()
        if s.isdigit():
            return s.zfill(10)
        # try exact + variants
        for variant in [s, *_normalize_variants(s)]:
            rec = self._map.get(variant)
            if rec:
                return rec["cik"]
        return None

    def info_for(self, ticker_or_cik: str | None) -> dict | None:
        """Return dict with cik/title/canonical (useful for printing)."""
        if not ticker_or_cik:
            return None
        s = ticker_or_cik.strip().upper()
        if s.isdigit():
            # If it's a CIK, try to find any ticker record with same CIK for title
            cik = s.zfill(10)
            for rec in self._map.values():
                if rec["cik"] == cik:
                    return rec
            return {"cik": cik, "title": "(unknown)", "canonical": "(unknown)"}
        for variant in [s, *_normalize_variants(s)]:
            rec = self._map.get(variant)
            if rec:
                return rec
        return None

def main():
    user_agent = os.getenv("EDGAR_IDENTITY", "").strip()
    if not user_agent:
        print("Tip: set EDGAR_IDENTITY env var to your email UA.")
        user_agent = input("Enter User-Agent (e.g., 'Ethan Zhang (ezhockey95@gmail.com)'): ").strip() # put your name and email here

    resolver = TickerResolver(user_agent=user_agent)
    print(f"Loading SEC ticker map from {SEC_TICKERS_URL} ...")
    resolver.load()
    print("Loaded tickers → CIK mapping.\n")

    args = sys.argv[1:] or ["AAPL","GOOG","GOOGL","MSFT","BRK.A","BRK.B","XOM","META","NFLX","TSLA","SPY"]
    for t in args:
        info = resolver.info_for(t)
        if info:
            print(f"{t:>6} → {info['cik']}  | canonical: {info['canonical']:<8} | {info['title']}")
        else:
            print(f"{t:>6} → NOT FOUND")

if __name__ == "__main__":
    main()
