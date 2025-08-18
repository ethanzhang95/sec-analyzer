import os
import requests
import json

class SECFetchHTM:
    """
    A class to search and download SEC filings using sec-api.
    """
    BASE_API_URL = "https://api.sec-api.io"
    SEC_BASE_URL = "https://www.sec.gov"
    def __init__(self, api_key: str, download_folder: str = "./10k10q"):
        self.api_key = api_key
        self.headers = headers = {
            "Content-Type": "application/json",
            "Authorization": self.api_key,
            "User-Agent": "Ethan Zhang (ezhockey95@gmail.com)"
        }
        self.download_folder = download_folder
        os.makedirs(self.download_folder, exist_ok=True)

    def search_filings(self, ticker: str, form_type: str, start_date: str, end_date: str,
                       from_index: str = "0", size: str = "1", sort_order: str = "desc") -> dict:
        """
        Searches for filings matching the provided parameters.
        Returns the JSON response.
        """
        payload = {
            "query": f"ticker:{ticker} AND formType:\"{form_type}\" AND filedAt:[{start_date} TO {end_date}]",
            "from": from_index,
            "size": size,
            "sort": [{ "filedAt": { "order": sort_order } }]
        }
        response = requests.post(self.BASE_API_URL, json=payload, headers=self.headers)
        print("here")
        print(response)
        response.raise_for_status()
        return response.json()

    def download_filing(self, filing_url: str, filename: str) -> str:
        """
        Downloads the filing from the given URL and saves it as filename.
        Returns the full file path.
        """
        # Ensure the filing URL is complete
        if not filing_url.startswith("http"):
            filing_url = self.SEC_BASE_URL + filing_url

        # Set headers to mimic a browser request (SEC requires a valid User-Agent)
        response = requests.get(filing_url, headers=self.headers)
        response.raise_for_status()

        file_path = os.path.join(self.download_folder, filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path

    def get_latest_filing(self, ticker: str, form_type: str, start_date: str, end_date: str) -> str:
        """
        Searches for the most recent filing matching the parameters and downloads it.
        Returns the file path of the downloaded filing.
        """
        data = self.search_filings(ticker, form_type, start_date, end_date)
        filings = data.get("filings", [])
        if not filings:
            raise Exception("No filings found for the query.")

        # Use the first (most recent) filing
        filing = filings[0]
        filing_url = filing.get("linkToFilingDetails")
        if not filing_url:
            raise Exception("Filing URL not found in the response.")

        # Create a filename based on the ticker, form type, and filing date
        filing_date = filing.get("filedAt", "unknown_date")
        # Sanitize filing_date if needed (e.g., remove ":" characters)
        safe_date = filing_date.replace(":", "-")
        filename = f"{ticker}_{form_type}_{safe_date}.htm"

        print(f"Downloading filing from: {filing_url}")
        file_path = self.download_filing(filing_url, filename)
        print(f"Filing downloaded successfully and saved as {file_path}")
        return file_path
    
    def get_filing_list(self, ticker: str, form_type: str, start_date: str, end_date: str) -> list:
        """
        Searches for all filings within the specified date range (start_date to end_date)
        and downloads each filing. Returns a list of file paths to the downloaded filings.
        """
        all_file_paths = []
        from_index = 0
        batch_size = 100  # How many filings to fetch per call (adjust as needed)

        while True:
            # Fetch up to batch_size filings starting from from_index
            data = self.search_filings(
                ticker=ticker,
                form_type=form_type,
                start_date=start_date,
                end_date=end_date,
                from_index=str(from_index),
                size=str(batch_size),
                sort_order="desc"
            )

            filings = data.get("filings", [])
            if not filings:
                # No more filings in this batch, stop the loop
                break

            for filing in filings:
                filing_url = filing.get("linkToFilingDetails")
                if not filing_url:
                    # If there's no link, skip this filing
                    continue

                # Create a meaningful filename based on ticker, form type, and filing date
                filing_date = filing.get("filedAt", "unknown_date")
                safe_date = filing_date.replace(":", "-")  # sanitize if needed
                filename = f"{ticker}_{form_type}_{safe_date}.htm"

                # Download and save the filing locally
                file_path = self.download_filing(filing_url, filename)
                all_file_paths.append(file_path)

            # If the current batch is smaller than batch_size, we've hit the end
            if len(filings) < batch_size:
                break
            
            # Otherwise, move on to the next batch
            from_index += batch_size

        return all_file_paths


# Example usage:
if __name__ == "__main__":
    # Replace with your actual API key
    API_KEY = "43019e4aeceac67f586eaed6ba508aeeaee599e43bd47e90d12f269f1a0663e5"
    
    # Instantiate the downloader
    downloader = SECFetchHTM(api_key=API_KEY, download_folder="./10k10q")
    
    # Example parameters: Download the most recent 10-K filing for NVDA in 2022.
    ticker = "AAPL"
    form_type = "10-Q"
    start_date = "2022-01-01"
    end_date = "2022-12-31"
    
    #going to need to implement 10-Q
    try:
        temp = downloader.search_filings(ticker, form_type, start_date, end_date)
        print(temp)
        print("----------")
        #file_path = downloader.get_latest_filing(ticker, form_type, start_date, end_date)
        file_paths = downloader.get_filing_list(ticker, form_type, start_date, end_date)
        print(file_paths)
    except Exception as e:
        print("An error occurred:", e)
