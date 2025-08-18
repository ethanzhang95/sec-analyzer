# QueryCoordinatorAgent.py

import os
import json
from typing import List, Dict
import requests
import openai
import datetime
import threading

# Import your previously defined agents
from FilingParserAgent import FilingParserAgent
from FinalQueryAgent import FinalQueryAgent
from htmDownloader import SECFetchHTM  # our downloader class

# Import the LLM from llama_index (same as used in FinalQueryAgent)
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.core.prompts import PromptTemplate
from llama_index.core import StorageContext, load_index_from_storage, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.settings import Settings

class QueryCoordinatorAgent:
    """
    Agent that processes the initial user query, uses an LLM to extract a list of companies (CIKs/tickers and names),
    downloads the corresponding SEC filings via SECFilingRetriever (which now uses SECFetchHTM), 
    invokes FilingParserAgent to parse them, and finally calls the FinalQueryAgent to produce the answer.
    """
    def __init__(self,
                 sec_api_key: str,
                 edgar_identity: str,
                 download_folder: str = "./10k10q",
                 persist_dir: str = "./store10k10q",
                 openai_api_key: str = None):
        self.sec_api_key = sec_api_key
        self.edgar_identity = edgar_identity
        self.download_folder = download_folder
        self.persist_dir = persist_dir
        self.formToFile = {}
        
        if openai_api_key:
            openai.api_key = openai_api_key
        # Instantiate the final query agent (assumes index already built or will be built by parsing)
        #fetcher for SEC API
        self.htmDownloader = SECFetchHTM(api_key=sec_api_key, download_folder=download_folder)
        # Create an LLM instance similar to what FinalQueryAgent uses.
        self.llm = LlamaOpenAI(model="gpt-4-turbo", temperature=0)
        # ---- CENTRALIZE INDEX LOADING/CREATION HERE ----
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-large")
        self.embed_model = Settings.embed_model
        self.lock = threading.Lock()
        try:
            # Attempt to load an existing index
            self.storage_context = StorageContext.from_defaults(persist_dir=self.persist_dir)
            self.index = load_index_from_storage(self.storage_context, index_id="10k10q")
            print("Loaded existing index from storage.")
        except Exception as e:
            # If it doesn't exist, create a new one
            print("No existing index found, creating a new one. Error details:", e)
            self.index = VectorStoreIndex([], embed_model=self.embed_model, persist_dir=self.persist_dir)
            self.index.set_index_id("10k10q")
            self.storage_context = self.index.storage_context
            self.storage_context.persist(self.persist_dir)
            
        self.final_query_agent = FinalQueryAgent(persist_dir=self.persist_dir, strategy="10k10q", storage = self.storage_context, index = self.index)

    def get_companies_from_query(self, query: str) -> List[Dict]:
        """
        Use the LLM to extract a list of companies from the user query, along with their corresponding 
        tickers (or CIKs) and optionally the filing date range.
        Expected output: a JSON list of objects with "company_name", "ticker" (or "cik"), and "filing_date_range".
        """
        prompt_str = (
            "You are an assistant specialized in financial filings. Given the following query, "
            "extract a list of companies mentioned along with their corresponding ticker symbols, CIK, form type, "
            "and the filing indicator (e.g. a fiscal year or quarter like '2003' or '2003 Q2') that identifies the report. "
            "Return the result as a JSON list where each entry has 'company_name', 'ticker', 'CIK', 'formType', and 'filing_date_range'. "
            "Return only valid JSON, with no additional text. No header that says json or anything, follow exactly the format of the example. An example output would be: "
            "[{\"company_name\": \"Apple Inc.\", \"ticker\": \"AAPL\", \"CIK\": \"0000320193\", \"formType\": \"10-K\", \"filing_date_range\": \"2003\"}]. "
            "[{\"company_name\": \"Apple Inc.\", \"ticker\": \"AAPL\", \"CIK\": \"0000320193\", \"formType\": \"10-Q\", \"filing_date_range\": \"2003 Q2\"}]. "
            f"Query: {query}\n\n"
            "Remember: 'filing_date_range' should refer to the fiscal period that the report covers. "
            "For Quarterly Reports, the filing_date_range should include the quarter, for example Q2, at the end of the string. Look at the example"
            "One more thing, if you need multiple reports from the same company, create separate JSON entries for each report, just giving a different filing_data_range"
            "The final rule is: if you are going to pull 10k, then don't pull 10q, and vice versa."
        )
        prompt_template = PromptTemplate(prompt_str)

        response = self.llm.predict(prompt_template)
        
        try:
            companies = json.loads(response) #potentially here, will need to change the filing data to work for 10k and 10q
            return companies
        except Exception as e:
            print("Error parsing company list:", e)
            return []

    #Usually, q1 reports are filed march to june, q2 reports are filed june to sept, q3 reports are filed sept to dec, and q4 reports are filed jan to march
    
    
    def determine_filing_quarter_from_data(self, period: str):
        '''
        Given a filing dae string in ISO format, determine the filing quarter based on defined filing windows for large companies
        '''
        #returns "Q1", "Q2", or "Q3" if the data falls within one of these windows: otherwise, return None
        try:
            dt = datetime.datetime.strptime(period, "%Y-%m-%d")
            month = dt.month
            if 1 <= month <= 3:
                return "Q1"
            elif 4 <= month <= 6:
                return "Q2"
            elif 7 <= month <= 9:
                return "Q3"
            elif 10 <= month <= 12:
                return "Q4"
        except Exception as e:
            print(f"Error determining quarter from period '{period}': {e}")
            return None
                
    def process_filings(self, companies: List[Dict]) -> None:
        """
        For each company in the provided list, download the relevant filing, parse it,
        and update the embedding index.
        """
        for company in companies:
            print("form to file right here")
            print(self.formToFile)
            ticker = company.get("ticker")
            print("currently on: " + ticker)
            form_type = company.get("formType")
            filing_indicator = company.get("filing_date_range") #format: "2003 Q2" or "2003"
            form_type = form_type
            if not (ticker and form_type and filing_indicator):
                print("Incomplete company info:", company)
                exit(1)
            
            #check if form is already processed and embedded
            if (ticker, form_type, filing_indicator) in self.formToFile:
                #we already have this embedded, skip
                continue
            else:
                #process 10q report
                if form_type.upper() == "10-Q": #process the date to get the quarter -> 3 reports, 1 2 3 become the quarter 1 2 3
                    parts = filing_indicator.strip().split()
                    if len(parts) == 2:
                        target_year, target_quarter = parts[0], parts[1].upper()
                    else:
                        target_year, target_quarter = filing_indicator.strip(), None
                        
                #process 10k report
                else:
                    target_year, target_quarter = filing_indicator.strip(), None
                    
                #build a broad historical range: from (target year - 1) to (target year + 1)
                try:
                    ty = int(target_year)
                except Exception:
                    print(f"Invalid target year: {target_year} for {ticker}")
                    exit(1)
                
                #this can potentially be tweaked, lets tweak this
                start_date = f"{ty}-02-01"
                end_date = f"{ty+1}-02-28"
                
                #fetch all filings for this company and form type within the broad range
                filings_list = self.htmDownloader.get_filing_list(ticker, form_type, start_date, end_date)
                if not filings_list:
                    print(f"No filings found for {ticker} between {start_date} and {end_date}")
                    continue
                
                print("filings list right here")
                print(filings_list)
                
                #this is the string referring to the form we are actually looking for
                correct_filing = None 
                
                #should be all 10-Q reports in the filings_list
                #at this point, just process all the 10-Q reports
                if form_type.upper() == "10-Q":
                    #at this point, just process all the 10Q reports
                    self.formToFile[(ticker, form_type, filing_indicator)] = filings_list
                    for filing in filings_list:
                        parser_agent = FilingParserAgent(
                            file_path=filing,
                            identity=self.edgar_identity,
                            persist_dir=self.persist_dir,
                            storage_context=self.storage_context,
                            index = self.index
                        )
                        parser_agent.parse_10k_financial_tables()
                        parser_agent.build_index()
                    
                elif form_type.upper() == "10-K":
                    #get the most recent, because year is already specified
                    correct_filing = filings_list[0]
                    self.formToFile[(ticker, form_type, filing_indicator)] = filings_list[0]
                    for filing in filings_list:
                        if filing != correct_filing:
                            os.remove(filing)
                    if correct_filing == None:
                        print("No correct filing error")
                        exit(1)
                    file_path = correct_filing
                    '''------------'''
                #htm files have been saved to 10k10q folder, now need to called FilingParserAgent
                    print("embedding" + ticker)
                    parser_agent = FilingParserAgent(
                        file_path=file_path,
                        identity=self.edgar_identity,
                        persist_dir=self.persist_dir,
                        storage_context=self.storage_context,
                        index = self.index
                    )
                    parser_agent.parse_10k_financial_tables()
                    parser_agent.build_index()
            #persist changes once
        print("Finished processing filings for companies.")

    '''
    def run(self, initial_query: str):
        """
        Main method that:
          1. Uses the LLM to extract companies (with tickers) from the initial query.
          2. Downloads the corresponding filings.
          3. Processes the filings (parsing and indexing).
          4. Runs the final query using FinalQueryAgent.
        """
        companies = self.get_companies_from_query(initial_query)
        print("Companies extracted:", companies)
        self.process_filings(companies)
        response, passing, citation = self.final_query_agent.run(prompt_str=initial_query, query_str=initial_query)
        #if passing is false, run again
        count = 0
        while passing == False and count < 2:
            response, passing, citation = self.final_query_agent.run(prompt_str=initial_query, query_str=initial_query)
            count += 1
        print("Final Query Response:", response)
        print("Citation:", citation)
        return response, passing
    '''
    '''
    def run(self, initial_query: str):
        # 1. Identify companies in user query
        companies = self.get_companies_from_query(initial_query)
        
        # 2. Download and parse the needed filings
        self.process_filings(companies)
        
        # 3. Run the final query
        #    final_query_agent.run() returns: (response_obj, passing_bool, citation_list)
        response_obj, passing, citation_list = self.final_query_agent.run(
            prompt_str=initial_query, 
            query_str=initial_query
        )

        # Retry logic if passing=False
        count = 0
        while passing is False and count < 2:
            response_obj, passing, citation_list = self.final_query_agent.run(
                prompt_str=initial_query, 
                query_str=initial_query
            )
            count += 1
        
        # NOTE: "response_obj" is a LlamaIndex "Response" object,
        #       so we want "response_obj.response" for the final answer text.

        # EXACT LITERAL PRINT:
        print(f"Final Query Response: {response_obj.response}")
        print(f"Citation: {citation_list}")

        # Return them if needed
        return response_obj.response, citation_list
    '''
    def run(self, initial_query: str):
        try:
            companies = self.get_companies_from_query(initial_query)
            self.process_filings(companies)
            
            response_obj, passing, citation_list = self.final_query_agent.run(
                prompt_str=initial_query, 
                query_str=initial_query
            )
            
            # If you have logic that might fail again:
            count = 0
            while passing is False and count < 2:
                response_obj, passing, citation_list = self.final_query_agent.run(
                    prompt_str=initial_query, 
                    query_str=initial_query
                )
                count += 1

            # Print or return the results
            print(f"Final Query Response: {response_obj.response}")
            print(f"Citation: {citation_list}")
            return response_obj.response, citation_list

        except Exception as e:
            # Handle the exception gracefully here
            print("An error occurred:", e)
            # Possibly log it or return some default / user-friendly message
            return "Sorry, something went wrong. Please try again later.", []



# -------------------------------
# Example Usage
# -------------------------------
if __name__ == "__main__":
    #ezhockey95 account
    #SEC_API_KEY = "43019e4aeceac67f586eaed6ba508aeeaee599e43bd47e90d12f269f1a0663e5"
    #ethanzhangva95 account
    #SEC_API_KEY = "e904e3262a9fbf4e3d9decc2afdc772632d1f972ca5fe42c584fb601a2880b97"
    #albert account
    SEC_API_KEY = "a3e5eb6ce44ba509fb776675af1ff9a73e2c29b3a100f3a0acc8b29404bc7e43"
    EDGAR_IDENTITY = "ezhockey95@gmail.com"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
   # initial_query = (
        #"Rivian's long-term debt for year ending December 31, 2024"
        #"What is the net income of Apple for the year 2022?"
        #"Give me NVDIA's cash and cash equivalents at end of period for the quarterly period ended April 28, 2024"
   # )
    
    coordinator = QueryCoordinatorAgent(
        sec_api_key=SEC_API_KEY,
        edgar_identity=EDGAR_IDENTITY,
        download_folder="./10k10q",
        persist_dir="./store10k10q",
        openai_api_key=OPENAI_API_KEY
    )
    while True:
        initial_query = input("Ask Chatbot a question: ")
        coordinator.run(initial_query)
    
    #test API request
    coordinator.run(initial_query)