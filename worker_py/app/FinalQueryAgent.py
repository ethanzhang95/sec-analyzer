# FinalQueryAgent.py

import os, re
from datetime import datetime

from llama_index.core import VectorStoreIndex, get_response_synthesizer, StorageContext, load_index_from_storage
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from llama_index.llms.openai import OpenAI
from llama_index.core.evaluation import FaithfulnessEvaluator
from llama_index.core import PromptTemplate
from llama_index.core.response_synthesizers import Refine
from llama_index.core.postprocessor import LLMRerank
from llama_index.core.query_pipeline import QueryPipeline
from llama_index.core.query_pipeline.components import FnComponent
from llama_index.core.prompts import PromptTemplate
from llama_index.core.llms import ChatMessage
from llama_index.core.settings import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.response_synthesizers import TreeSummarize

class FinalQueryAgent:
    def __init__(self, persist_dir: str, strategy: str, storage = None, index = None):
        """
        Initialize the query agent with the storage persistence directory and strategy (index ID).
        """
        self.persist_dir = persist_dir
        self.strategy = strategy
        # Build storage context from persisted index
        #self.storage_context = StorageContext.from_defaults(persist_dir=self.persist_dir)  #load this once in InitialQueryAgent.py
        self.storage_context = storage
        self.index = index
        Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-large")
        # Create an LLM handle with the updated model settings
        self.llm = OpenAI(model="gpt-4-turbo", temperature=1) #set temperature to 1
        self.citation = []

    def input_mapper_fn(self, query_str: str):
        return {"query_str": query_str}

    def extract_filters_from_query(self, query: str) -> MetadataFilters:
        filters = []
        # Match specific section (Item 1A, Item 7, etc.)
        section_match = re.search(r'item\s*(\d+[a-zA-Z]?)', query, re.IGNORECASE)
        if section_match:
            filters.append(MetadataFilter(
                key="section",
                value=f"Item {section_match.group(1).upper()}",
                operator=FilterOperator.EQ
            ))
        # Match form type (10-K or 10-Q)
        form_match = re.search(r'\b(10-[KQ])\b', query, re.IGNORECASE)
        if form_match:
            filters.append(MetadataFilter(
                key="form_type",
                value=form_match.group(1).upper(),
                operator=FilterOperator.EQ
            ))
        # Match filing year
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match:
            filters.append(MetadataFilter(
                key="filing_date",
                value=f"{year_match.group(1)}-01-01",
                operator=FilterOperator.GTE
            ))
        return MetadataFilters(filters=filters)


    
    def build_pipeline_query(self, prompt_str: str, query_str: str):
        """
        Builds and runs the query pipeline:
          - Loads the prebuilt index from storage.
          - Detects the form type from the query.
          - Creates separate retrievers for narrative and table documents using updated filters.
          - Sets up prompt rewriting, LLM-based reranking, node merging with citation printing, and summarization.
          - Runs the query and evaluates the response.
        """
        try:
            # Load the prebuilt index using the given strategy (index ID)
            #index = load_index_from_storage(self.storage_context, index_id=self.strategy)
            index = self.index
            self.citation = []
            # Helper function to detect form type from the query.
            def detect_form_type(query: str) -> str:
                        q = query.lower()         
                        if "annual" in q or "fiscal year" in q or "year ending" in q:  ####
                            return "10-K"
                        elif re.search(r'q[1-4]|quarter|quarterly|march|june|september|december|10q|10-q', q):
                            print("QQQQQ")
                            print(q)
                            print("WHYYYY")
                            return "10-Q"
                        else:
                            return "10-K"  # fallback to 10-K
 

            form_type = "10-K"
            print(f"Form type to retrieve similarity from: {form_type}")

            # Define filters using the detected form type
            filters_table = MetadataFilters(filters=[
                MetadataFilter(key="type", value="table", operator=FilterOperator.EQ),
                #MetadataFilter(key="form_type", value=[form_type], operator=FilterOperator.IN)
            ])
            filters_narrative = MetadataFilters(filters=[
                MetadataFilter(key="type", value="narrative", operator=FilterOperator.EQ),
                #MetadataFilter(key="form_type", value=[form_type], operator=FilterOperator.EQ)
            ])

            retriever_narrative = index.as_retriever(similarity_top_k=10, filters=filters_narrative)
            retriever_table = index.as_retriever(similarity_top_k=10, filters=filters_table)

            # Set up LLM-based rerankers
            reranker_narrative = LLMRerank(llm=self.llm, top_n=5)
            reranker_table = LLMRerank(llm=self.llm, top_n=5)

            # Use the Refine summarizer
            #summarizer = Refine(llm=self.llm) 
            #try this

    
   

            # 2) Pass the PromptTemplate to Refine
           # summarizer = Refine(
           #     llm=self.llm
           # )
            
            summarizer = TreeSummarize(llm=self.llm)
 


            # Prompt rewriting template and component
            template = PromptTemplate("{query_str}.")
            def apply_prompt(query_str):
                prompt_text = template.format(query_str=query_str)
                return [ChatMessage(role="user", content=prompt_text)]
            prompt_tmpl = FnComponent(fn=apply_prompt, output_keys=["messages"])

            # Input mapper component
            input_mapper = FnComponent(fn=lambda query_str: {"query_str": query_str}, output_keys=["query_str"])

            # Define a merge component that prints citation details and merges nodes
            def capture_nodes(nodes1, nodes2):
                merged = nodes1 + nodes2
                print("\n🔍 Merged Nodes:")
                for i, node in enumerate(merged):
                    content_preview = node.node.get_content()[:200] if hasattr(node, "node") else node.text[:200]
                    print(f"[{i}] {content_preview}...\n")
                    print(f"--- Citation {i+1} ---")
                    if node.metadata.get('type') == 'table':
                        print("node.text: ")
                        print(node.text)
                        citation = (f"Table cited from: {node.metadata.get('filename', '')} "
                                    f"{node.metadata.get('form_type', '')} "
                                    f"{node.metadata.get('section', '')} "
                                    f"footnote: {node.metadata.get('footnote', '')}")
                        #save citation here, output in the final response
                        print("\n📊 " + citation + "\n")
                        self.citation.append(citation)
                    elif node.metadata.get('type') == 'narrative':
                        citation = (f"Text cited from: {node.metadata.get('filename', '')} "
                                    f"{node.metadata.get('form_type', '')} "
                                    f"{node.metadata.get('section', '')}")
                        print(citation)
                return merged

            merge_reranked = FnComponent(fn=capture_nodes, output_keys=["nodes"])

            # Build the query pipeline
            print("Starting the RAG Query Pipeline...")
            p = QueryPipeline(verbose=True)
            p.add_modules({
                "input": input_mapper,
                "llm": self.llm,
                "prompt_tmpl": prompt_tmpl,
                "retriever_narrative": retriever_narrative,
                "retriever_table": retriever_table,
                "merge_reranked": merge_reranked,
                "summarizer": summarizer,
                "reranker_narrative": reranker_narrative,
                "reranker_table": reranker_table
            })
            '''
            p.add_link("input", "prompt_tmpl")

            # 2) user query (from prompt_tmpl) --> table retriever
            p.add_link("prompt_tmpl", "retriever_table", dest_key="query_str")

            # 3) user query + table nodes --> table re-ranker
            p.add_link("prompt_tmpl", "reranker_table", dest_key="query_str")
            p.add_link("retriever_table", "reranker_table", dest_key="nodes")

            # 4) final summarizer sees user query + re-ranked table nodes
            p.add_link("prompt_tmpl", "summarizer", dest_key="query_str")
            p.add_link("reranker_table", "summarizer", dest_key="nodes")
            '''

            # Link modules to form the processing graph
            
            p.add_link("input", "prompt_tmpl")
            p.add_link("prompt_tmpl", "llm", dest_key="messages")
            p.add_link("llm", "retriever_narrative")
            p.add_link("llm", "retriever_table")

            p.add_link("retriever_narrative", "reranker_narrative", dest_key="nodes")
            p.add_link("llm", "reranker_narrative", dest_key="query_str")
            p.add_link("retriever_table", "reranker_table", dest_key="nodes")
            p.add_link("llm", "reranker_table", dest_key="query_str")

            p.add_link("reranker_narrative", "merge_reranked", dest_key="nodes1")
            p.add_link("reranker_table", "merge_reranked", dest_key="nodes2")
            p.add_link("merge_reranked", "summarizer", dest_key="nodes")
            p.add_link("llm", "summarizer", dest_key="query_str")
            

            print("Summarizer input keys:", summarizer.as_query_component().input_keys)
            print("Pipeline input keys:", p.input_keys)

            # Run the pipeline
            response = p.run(query_str=query_str)

            evaluator = FaithfulnessEvaluator(llm=self.llm)
            eval_result = evaluator.evaluate_response(response=response)
            return response, eval_result.passing, self.citation

        except Exception as e:
            print("Error in build_pipeline_query:", e)
            return None, None
    
    #Note: try to save citations and have response in the final response
    def run(self, prompt_str: str, query_str: str):
        """
        Run the complete query pipeline with the given prompt and query strings.
        """
        '''
        topic_instruction = ". Now here are more instructions: Use only the retrieved information that is tabular data in markdown format. Carefully compare rows and columns in order to answer the questions. "
        "Your response should have numeric values that were extracted from the tables. If you dont have the numbers, please say so with the statement: I don't have the data and thats it in your response."
        og_query_str = query_str
        query_str = "You are a financial analyst. Here is the query: " + query_str + " " + topic_instruction + " In addition, please please please make sure to include metrics from the 10k or 10q reports for every company that is mentioned in the query. An important keyword is COMPARE, it means you give numbers for both companies not just one."
        return self.build_pipeline_query(prompt_str, query_str, og_query_str)
        '''
        
        topic_instruction = (
            "Instructions: You are a financial analyst. Please Carefully compare rows and columns in order to answer the questions. Use only the retrieved information from 10K or 10Q form that maybe in multiple tabular data in markdown format. The response shall present numeric values that were extracted from the tabular table. If the data isn't sufficient, say so"
        )
        
        '''topic_instruction = (
            "Here are instructions: "
            "Use only the retrieved information that is tabular data in markdown format. "
            "Carefully compare rows and columns in order to answer the questions. "
            "Your response should have numeric values that were extracted from the tables. "
            "If you don't have the numbers, please say so. "
        )'''

        query_str = (
            "You need to answer this question: " + query_str + " "
            + topic_instruction
        )

        return self.build_pipeline_query(prompt_str, query_str)

# -------------------------------
# Example Usage
# -------------------------------
'''
if __name__ == "__main__":
    strategy = "10k10q"
    persist_dir = "./store" + strategy
    topic = ("find the debt-to-equity ratio and return on equity for APPLE for the fiscal year ended 2018 and provide an analysis of what these metrics suggest about the financial health of the companies. "
             "This is best figured from the Item 8. financial statements in the 10-K form")
    agent = FinalQueryAgent(persist_dir, strategy)
    response, passing = agent.run(topic, topic)
    print("\n---------Final Response to the question:-----\n")
    print(response)
    print("Evaluation Passing:", passing)
'''
