# worker_py/app/run_query.py
import os, json, sys, argparse, io
from pathlib import Path
from dotenv import load_dotenv
from contextlib import redirect_stdout

from InitialQueryAgent import QueryCoordinatorAgent

def main():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()

    SEC_API_KEY = os.getenv("SEC_API_KEY", "")
    EDGAR_IDENTITY = os.getenv("EDGAR_IDENTITY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    if not (SEC_API_KEY and EDGAR_IDENTITY and OPENAI_API_KEY):
        # Print ONLY JSON on stdout
        print(json.dumps({"ok": False, "error": "Missing required env vars"}))
        sys.exit(1)

    # Capture any prints from downstream code to avoid corrupting stdout JSON
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            agent = QueryCoordinatorAgent(
                sec_api_key=SEC_API_KEY,
                edgar_identity=EDGAR_IDENTITY,
                download_folder="./10k10q",
                persist_dir="./store10k10q",
                openai_api_key=OPENAI_API_KEY
            )
            answer, citations = agent.run(args.prompt)
    except Exception as e:
        # Send debug logs to stderr so API can still parse stdout JSON
        print(buf.getvalue(), file=sys.stderr)
        print(json.dumps({"ok": False, "error": f"Worker exception: {str(e)}"}))
        sys.exit(1)

    # Dump captured logs to stderr for visibility
    logs = buf.getvalue()
    if logs:
        print(logs, file=sys.stderr)

    # Print ONLY the JSON result on stdout
    print(json.dumps({
        "ok": True,
        "answer": getattr(answer, "response", answer),
        "citations": citations
    }))

if __name__ == "__main__":
    main()
