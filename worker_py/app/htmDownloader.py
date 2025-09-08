# htmDownloader.py
from __future__ import annotations

import os
import re
import json
import logging
from typing import Dict, List, Iterable, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SECFetchHTM:
    """
    Search & download SEC filings using sec-api.io, with retries, caching, and safe filenames.

    Backward-compatible public methods:
      - search_filings(ticker, form_type, start_date, end_date, from_index="0", size="1", sort_order="desc") -> dict
      - get_latest_filing(ticker, form_type, start_date, end_date) -> str (local file path)
      - get_filing_list(ticker, form_type, start_date, end_date) -> list[str] (local file paths)
      - download_filing(filing_url, filename) -> str (local file path)
    """

    BASE_API_URL = "https://api.sec-api.io"
    SEC_BASE_URL = "https://www.sec.gov"

    _ALLOWED_FORMS = {"10-K", "10-Q"}

    def __init__(
        self,
        api_key: str,
        download_folder: str = "./10k10q",
        *,
        user_agent="Ethan Zhang (ezhockey95@gmail.com)", # replace with your name and email
        timeout: float = 30.0,
        retries: int = 3,
        backoff_factor: float = 0.8,
        verbose: bool = False,
        session: Optional[requests.Session] = None,
    ) -> None:
        """
        :param api_key: sec-api.io API key
        :param download_folder: local folder for downloads
        :param user_agent: SEC requires a meaningful UA; override with your email
        :param timeout: request timeout (seconds)
        :param retries: retry attempts for transient errors
        :param backoff_factor: exponential backoff base
        :param verbose: if True, sets logger to DEBUG
        :param session: optional pre-configured requests.Session
        """
        self.api_key = api_key
        self.download_folder = download_folder
        self.timeout = timeout

        os.makedirs(self.download_folder, exist_ok=True)

        # Logging
        self.log = logging.getLogger(self.__class__.name if hasattr(self.__class__, "name") else "SECFetchHTM")
        if verbose:
            logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
        else:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

        # HTTP session with retry policy
        self.session = session or requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": self.api_key,
            "User-Agent": user_agent,
        })

        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            backoff_factor=backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)


    def search_filings(self, ticker: str, form_type: str, start_date: str, end_date: str,
                    from_index: str = "0", size: str = "1", sort_order: str = "desc") -> dict:
        """
        Now accepts ticker OR CIK in the 'ticker' parameter.
        If numeric → query by cik:, else → ticker:
        """
        ident = str(ticker).strip()
        if ident.isdigit():
            q_id = f"cik:{int(ident)}"
        else:
            q_id = f"ticker:{ident.upper()}"

        payload = {
            "query": f'{q_id} AND formType:"{form_type}" AND filedAt:[{start_date} TO {end_date}]',
            "from": from_index,
            "size": size,
            "sort": [{ "filedAt": { "order": sort_order } }]
        }
        resp = self.session.post(self.BASE_API_URL, json=payload, timeout=self.timeout)
        self._raise_for_status(resp)
        return resp.json()

    def download_filing(self, filing_url: str, filename: str) -> str:
        """
        Download a filing (HTML) and save to `download_folder/filename`.
        Returns the local file path. Uses caching if file already exists.
        """
        url = filing_url if filing_url.startswith("http") else self.SEC_BASE_URL + filing_url
        file_path = os.path.join(self.download_folder, self._safe_filename(filename))

        # Cache: if file exists and is non-empty, skip network
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            self.log.debug("Cache hit: %s", file_path)
            return file_path

        self.log.debug("GET %s -> %s", url, file_path)
        resp = self.session.get(url, timeout=self.timeout)
        self._raise_for_status(resp)

        with open(file_path, "wb") as f:
            f.write(resp.content)

        return file_path

    def get_latest_filing(
        self, ticker: str, form_type: str, start_date: str, end_date: str
    ) -> str:
        """
        Find the most recent filing matching the query and download it.
        Returns the local file path.
        """
        data = self.search_filings(ticker, form_type, start_date, end_date, from_index="0", size="1", sort_order="desc")
        filing = self._first_filing_or_raise(data)

        filing_url = filing.get("linkToFilingDetails")
        if not filing_url:
            raise RuntimeError("Filing URL not found in search response.")

        filing_date = filing.get("filedAt", "unknown_date")
        filename = self._default_filename(ticker, form_type, filing_date)
        return self.download_filing(filing_url, filename)

    def get_filing_list(
        self, ticker: str, form_type: str, start_date: str, end_date: str, *, batch_size: int = 100
    ) -> List[str]:
        """
        Download all filings in the window. Returns paths of downloaded files.
        """
        paths: List[str] = []
        for filing in self.iter_filings(ticker, form_type, start_date, end_date, batch_size=batch_size):
            filing_url = filing.get("linkToFilingDetails")
            if not filing_url:
                continue
            filing_date = filing.get("filedAt", "unknown_date")
            filename = self._default_filename(ticker, form_type, filing_date)
            path = self.download_filing(filing_url, filename)
            paths.append(path)
        return paths


    def iter_filings(
        self, ticker: str, form_type: str, start_date: str, end_date: str, *, batch_size: int = 100
    ) -> Iterable[Dict]:
        """
        Generator that yields filing dicts across all pages.
        Useful if you prefer to control downloading or enrich metadata.
        """
        t = self._normalize_ticker(ticker)
        f = self._validate_form(form_type)

        from_index = 0
        while True:
            data = self.search_filings(
                ticker=t,
                form_type=f,
                start_date=start_date,
                end_date=end_date,
                from_index=str(from_index),
                size=str(batch_size),
                sort_order="desc",
            )
            filings = data.get("filings", []) or []
            if not filings:
                break
            for filing in filings:
                yield filing
            if len(filings) < batch_size:
                break
            from_index += batch_size

    def _default_filename(self, ticker: str, form_type: str, filed_at: str) -> str:
        # Example: "AAPL_10-Q_2024-02-01T00-00-00Z.htm"
        safe_date = re.sub(r"[^0-9T:\-Z]", "-", str(filed_at)).replace(":", "-")
        base = f"{self._normalize_ticker(ticker)}_{form_type}_{safe_date}.htm"
        return self._safe_filename(base)

    @staticmethod
    def _safe_filename(name: str) -> str:
        # Keep alnum, dash, underscore, dot; replace others with _
        name = re.sub(r"[^\w\-.]+", "_", name.strip())
        # Normalize multiple underscores/dashes
        name = re.sub(r"_{2,}", "_", name)
        return name[:255]  # filesystem-friendly

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        if not ticker or not isinstance(ticker, str):
            raise ValueError("ticker must be a non-empty string")
        return ticker.upper().strip()

    def _validate_form(self, form_type: str) -> str:
        if not form_type or form_type.upper() not in self._ALLOWED_FORMS:
            raise ValueError(f"form_type must be one of {sorted(self._ALLOWED_FORMS)}")
        return form_type.upper()

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Try to include API error details in exception for easier debugging
            detail = ""
            try:
                body = resp.json()
                detail = f" | body={json.dumps(body)[:500]}"
            except Exception:
                pass
            raise requests.HTTPError(f"{e} (status={resp.status_code}){detail}") from None


# Example usage
if __name__ == "__main__":
    import os

    API_KEY = os.getenv("SEC_API_KEY", "")
    if not API_KEY:
        raise SystemExit("Set SEC_API_KEY in your environment")

    downloader = SECFetchHTM(
        api_key=API_KEY,
        download_folder=os.getenv("DOWNLOAD_FOLDER", "./10k10q"),
        user_agent=os.getenv("EDGAR_IDENTITY", "ethan@example.com"),
        verbose=True,
    )

    ticker = "AAPL"
    form_type = "10-Q"
    start_date = "2022-01-01"
    end_date = "2022-12-31"

    # Show first page of search results
    data = downloader.search_filings(ticker, form_type, start_date, end_date, size="5")
    print(json.dumps(data, indent=2)[:1500])

    # Download all matches (cached if already present)
    paths = downloader.get_filing_list(ticker, form_type, start_date, end_date, batch_size=50)
    print(paths[:5])
