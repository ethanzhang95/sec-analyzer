# SEC Analyzer

A full-stack application that lets you query SEC filings (10-K, 10-Q) and get structured answers about company financials.  
Example:  
> *“What was Apple’s net income in 2022?”*  

The system retrieves filings directly from the SEC, parses **financial tables only** (ignoring narrative), and uses a retrieval-augmented generation (RAG) pipeline to generate precise numeric answers with citations.

---

## 📂 Project Structure
```
SECapp/
├── api/ # Spring Boot backend (Java/Gradle)
├── frontend/ # Next.js frontend (TypeScript/React)
├── worker_py/ # Python worker for SEC filings + RAG pipeline
├── 10k10q/ # Cached SEC filings
├── store10k10q/ # Persisted vector index
└── README.md
```
## ✨ Features
- Query **10-K / 10-Q filings** by company and year  
- Extract values from **financial tables** (cleaner answers)  
- Retrieval-augmented generation with **citations from SEC filings**  
- Full-stack architecture:  
  - **Frontend:** Next.js UI  
  - **Backend:** Spring Boot API layer  
  - **Worker:** Python + LlamaIndex RAG pipeline  

---

## 🚀 Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/sec-analyzer.git
cd sec-analyzer
```
### 2. Python Worker (RAG Pipeline)
```
cd worker_py
python3 -m venv .venv
source .venv/bin/activate   # Mac/Linux
# or .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```
Create a .env file in the root directory with
```
OPENAI_API_KEY=your_openai_api_key
SEC_API_KEY=your_sec_api_key
SEC_EMAIL=your_email_for_SEC_requests
```

Run a test query:
python3 app/run_query.py --prompt "What was Apple's net income in 2022?"
### 3. Spring Boot Backend
```
cd api
./gradlew bootRun # Mac/Linux
gradlew.bat bootRun # Windows
```
This starts the backend at http://localhost:8000

### 4. Next.js Frontend
```
cd frontend
npm install
npm run dev
```
This starts the frontend at http://localhost:3000

🛠️ Example Queries

"What was Apple’s net income in 2022?"

"Compare Microsoft’s and Google’s R&D spending in 2021."

"Show Tesla’s operating cash flow for 2020 and 2021."


📌 Roadmap

 Add multi-company comparison in frontend UI

 Improve form-type detection (10-K vs 10-Q)

 Containerize with Docker for one-command startup

 Deploy backend + worker to cloud (AWS/GCP/Azure)

 Enable MCP Server Functionality


 📄 License

MIT License.








