# FilingParserAgent.py
'''

'''

# FilingParserAgent.py

import os
import re
import csv
import chardet
import pandas as pd
from bs4 import BeautifulSoup
from edgar import set_identity

from llama_index.core import Document, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.schema import TextNode

import threading

from llama_index.core.settings import Settings

# Define financial keywords used to identify financial tables.
FINANCIAL_KEYWORDS = [
    "net income", "total assets", "revenue", "cash flow", "balance sheet",
    "statement of operations", "comprehensive income", "stockholders’ equity",
    "earnings per share", "operating income", "liabilities", "expenses", "shares purchased", "average price",
    "number of shares", "tax rate", "gross margin", "cash equivalents", "depreciation", "amortization"
]

class FilingParserAgent:
    def __init__(self, file_path, identity, download_folder="./10k10q", persist_dir="./store10k10q", storage_context=None, index=None):
        """
        Initialize the agent with the path to a filing, EDGAR identity, and optional folders.
        """
        self.file_path = file_path
        print(f"Processing file: {self.file_path}")
        self.download_folder = download_folder
        self.persist_dir = persist_dir
        # Set the EDGAR identity
        set_identity(identity)
        # Placeholders for parsed sections and documents
        self.sections = {}
        self.narrative_documents = []
        self.table_documents = []
          # You may pass additional parameters if needed.
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-large")
        self.embed_model = Settings.embed_model
        self.storage_context = storage_context
        self.index = index

    # -------------------------------
    # Parsing Utilities
    # -------------------------------
    def parse_table(self, table):
        rows = []
        for row in table.find_all('tr'):
            cols = row.find_all(['td', 'th'])
            current_row = []
            for col in cols:
                # The fix: join stripped strings without extra spaces
                text = ''.join(col.stripped_strings).replace('\xa0', ' ').strip()
                current_row.append(text)
            rows.append(current_row)
        return rows

    def is_financial_table(self, table_data):
        return True
        if not table_data:
            return False
        flat_text = ' '.join(' '.join(row).lower() for row in table_data)
        return any(keyword in flat_text for keyword in FINANCIAL_KEYWORDS)

    #not being called, remove later
    def extract_metadata_from_header(self, raw_text):
        metadata = {}
        form_type_match = re.search(r"SUBMISSION TYPE:\s*(\S+)", raw_text)
        date_match = re.search(r"FILED AS OF DATE:\s*(\d+)", raw_text)
        cik_match = re.search(r"CENTRAL INDEX KEY:\s*(\d+)", raw_text)
        if form_type_match:
            metadata['form_type'] = form_type_match.group(1)
        if date_match:
            metadata['filing_date'] = date_match.group(1)
        if cik_match:
            metadata['cik'] = cik_match.group(1)
        return metadata

    def to_markdown_from_table(self, table):
        """
        Convert a list-of-lists table to a markdown-formatted string.
        Handles ragged rows and empty cells.
        """
        # Remove completely empty rows
        table = [row for row in table if any(str(cell).strip() for cell in row)]
        if not table:
            return "⚠️ Table is empty or malformed."
        max_cols = max(len(row) for row in table)
        normalized = []
        for row in table:
            cleaned = [str(cell).strip() if str(cell).strip() else ' ' for cell in row]
            # Pad row to max_cols
            cleaned += [' '] * (max_cols - len(cleaned))
            normalized.append(cleaned[:max_cols])
        header = normalized[0]
        md = "| " + " | ".join(header) + " |\n"
        md += "| " + " | ".join(["---"] * max_cols) + " |\n"
        for row in normalized[1:]:
            md += "| " + " | ".join(row) + " |\n"
        return md
    #fix method call here, maybe use static method, etc.
    def table_to_text(self, table, note=""):
        """Turn structured table into a readable text chunk."""
        import pandas as pd
        if isinstance(table, pd.DataFrame):
            table_str = table.to_string(index=False)
        elif isinstance(table, dict):  # convert dict to string
            table_str = "\n".join([", ".join(map(str, row)) for row in table.get("rows", [])])
        else:
            table_str = str(table)

        table_str = self.to_markdown_from_table(table)
        return f"{table_str}" 

    # -------------------------------
    # Main Parsing Functionality
    # -------------------------------
    def parse_10k_financial_tables(self):
        """
        Parses the 10-K/10-Q filing (HTML file) into sections,
        extracting narrative text and financial tables.
        """
        with open(self.file_path, "rb") as f:
            raw = f.read()
        print("FILE PATH")
        print(self.file_path)
        print("FILE")
        print(raw[:100])
        encoding = chardet.detect(raw)["encoding"] or "utf-8"
        html = raw.decode(encoding, errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        # New item pattern capturing trailing text (similar to bp.py)
        item_pattern = re.compile(r"Item[\s\xa0]+(\d+[A-Z]?)\s*[\.\-:–—]?\s*(.*)", re.IGNORECASE)
        top_level_elements = soup.find_all(['div', 'p', 'span', 'table', 'font', 'b', 'strong', 'h1', 'h2', 'h3', 'h4'])

        sections = {}
        current_item_key = None
        buffer = []

        text = soup.get_text()
        form_type = re.search(r"Form\s+(10-K|10-Q)", text)
        filing_date = re.search(r"FILED AS OF DATE:\s*(\d{8})", text)
        cik = re.search(r"CENTRAL INDEX KEY:\s*(\d+)", text)
        note_pattern = re.compile(r"Note\s+(\d+)", re.IGNORECASE)

        def flush_section():
            nonlocal sections, current_item_key, buffer, form_type, filing_date, cik
            if current_item_key and buffer:
                section_html = ''.join(str(tag) for tag in buffer)
                section_soup = BeautifulSoup(section_html, "html.parser")
                tables_by_note = []
                elements = section_soup.find_all(['p', 'div', 'span', 'b', 'strong'])
                current_note = None
                current_note_buffer = []

                def flush_note_block(note_number, note_buffer):
                    nonlocal tables_by_note
                    if not note_buffer:
                        return
                    note_html = ''.join(str(tag) for tag in note_buffer)
                    note_soup = BeautifulSoup(note_html, "html.parser")
                    for table in note_soup.find_all("table"):
                        parsed = self.parse_table(table)
                        if self.is_financial_table(parsed):
                            tables_by_note.append({
                                "note_number": note_number,
                                "parsed": parsed,
                                "html": str(table)
                            })
                        table.decompose()

                for el in elements:
                    el_text = el.get_text(" ", strip=True)
                    match_note = note_pattern.match(el_text)
                    if match_note:
                        flush_note_block(current_note, current_note_buffer)
                        current_note = int(match_note.group(1))
                        current_note_buffer = [el]
                    else:
                        current_note_buffer.append(el)
                flush_note_block(current_note, current_note_buffer)

                clean_text = section_soup.get_text(separator="\n").strip()
                sections[current_item_key] = {
                    "form_type": form_type.group(1) if form_type else None,
                    "filing_date": filing_date.group(1) if filing_date else None,
                    "cik": cik.group(1) if cik else None,
                    "filename": self.file_path,
                    "section": current_item_key,
                    "html": section_html,
                    "text": clean_text,
                    "tables": [t["parsed"] for t in tables_by_note],
                    "tables_html": [t["html"] for t in tables_by_note],
                    "tables_by_note": tables_by_note
                }

        for tag in top_level_elements:
            tag_text = tag.get_text(" ", strip=True)
            match_item = item_pattern.match(tag_text)
            if match_item:
                flush_section()
                # Use the entire cleaned tag text as the section key
                item_number = match_item.group(1).upper()
                current_item_key = cleaned = re.sub(r'\s+', ' ', tag_text).strip()
                buffer = [tag]
            else:
                buffer.append(tag)
        flush_section()

        # Now, assign any tables not linked to a section.
        all_text = soup.get_text(separator="\n")
        text_pos = 0
        table_list = soup.find_all('table')
        section_positions = []
        for key, data in sections.items():
            start = all_text.find(data['text'], text_pos)
            if start >= 0:
                section_positions.append((start, key))
                text_pos = start + len(data['text'])
        text_pos = 0
        for table in table_list:
            table_text = table.get_text(separator="\n")
            table_start = all_text.find(table_text, text_pos)
            text_pos = table_start + len(table_text)
            section_for_table = None
            for pos, sec in section_positions:
                if pos < table_start:
                    section_for_table = sec
                else:
                    break
            if section_for_table in sections:
                parsed = self.parse_table(table)
                if self.is_financial_table(parsed):
                    sections[section_for_table]["tables"].append(parsed)
                    sections[section_for_table]["tables_html"].append(str(table))

        self.sections = sections
        return sections

    # -------------------------------
    # Document & Index Building
    # -------------------------------
    def build_documents(self):
        """
        Builds narrative and table documents from the parsed filing sections.
        """
        self.narrative_documents = []
        self.table_documents = []
        for section_key, meta in self.sections.items():
            doc_text = meta["text"]
            metadata = {
                "section": section_key,
                "form_type": meta["form_type"],
                "filing_date": meta["filing_date"],
                "cik": meta["cik"],
                "filename": meta["filename"],
                "type": "narrative",
            }
            self.narrative_documents.append(Document(text=doc_text, metadata=metadata))
            for table_entry in meta.get("tables_by_note", []):
                table_text = self.table_to_text(table_entry["parsed"], table_entry.get("note", ""))
                table_metadata = metadata.copy()
                table_metadata["type"] = "table"
                table_metadata["footnote"] = table_entry["note_number"]
                self.table_documents.append(Document(text=table_text, metadata=table_metadata))
        print(f"Built {len(self.narrative_documents)} narrative documents and {len(self.table_documents)} table documents.")
        return self.narrative_documents, self.table_documents

    def build_index(self, chunk_size=2048, chunk_overlap=0, index_id="10k10q"):
        """
        Builds the embedding index from the narrative and table documents and persists it.
        """
        self.build_documents() #this will be handled in InitialQueryAgent.py
        parser_sentence = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        # Use SentenceSplitter for both narrative and table documents
        #commented out nodes_narrative
        #nodes_narrative = parser_sentence.get_nodes_from_documents(self.narrative_documents)
        nodes_table = parser_sentence.get_nodes_from_documents(self.table_documents)
        #print("nodes_table")
        #print(nodes_table)
        #all_nodes = nodes_narrative + nodes_table
        all_nodes = nodes_table
        #this part will be handled in InitialQueryAgent.py

        if self.storage_context != None:
            print("filing index reached")
            self.index.insert_nodes(all_nodes)
            self.index.storage_context.persist(persist_dir=self.persist_dir)
            
        print("Index built and persisted to:", self.persist_dir)
        
# -------------------------------
# Example Usage
# -------------------------------
'''
if __name__ == "__main__":
    file_path = "/Users/ethanzhang/Documents/UVA/Second Year/Beachpoint/BP/10k10q/a10-k20189292018.htm"
    identity = "ezhockey95@gmail.com"
    
    agent = FilingParserAgent(file_path, identity)
    agent.parse_10k_financial_tables()      # Parse the filing into sections
    agent.build_index()                     # Build and persist the embedding index
'''
