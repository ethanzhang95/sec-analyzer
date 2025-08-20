'use client';
import { useEffect, useState } from 'react';

type WorkerResponse = {
  ok: boolean;
  answer: string | null;
  citations: string[] | null;
  error?: string | null;
};

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';

export default function Home() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<WorkerResponse | null>(null);
  const [health, setHealth] = useState<string>('checking…');

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BASE}/queries/health`, { cache: 'no-store' });
        const t = await r.text();
        setHealth(r.ok ? t : `bad (${r.status})`);
      } catch (e: any) {
        setHealth('unreachable');
      }
    })();
  }, []);

  async function ask() {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const res = await fetch(`${BASE}/queries`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });

      // handle non-JSON errors gracefully
      let json: WorkerResponse | { error?: string };
      try {
        json = await res.json();
      } catch {
        throw new Error(`API returned ${res.status}, and the body wasn’t JSON`);
      }

      if (!res.ok || !(json as WorkerResponse).ok) {
        throw new Error((json as any)?.error || `API error (${res.status})`);
      }
      setData(json as WorkerResponse);
    } catch (e: any) {
      setError(e?.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      ask();
    }
  }

  return (
    <main className="mx-auto max-w-3xl p-6 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">SEC Filing Q&A</h1>
        <span className="text-sm text-gray-600">
          API health: <b>{health}</b>
        </span>
      </header>

      <div className="space-y-3">
        <label className="block text-sm font-medium">Prompt</label>
        <textarea
          className="w-full rounded border p-3"
          rows={4}
          placeholder="e.g., What is Apple's net income for FY 2022?"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="flex gap-3">
          <button
            onClick={ask}
            disabled={loading || !prompt.trim()}
            className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
          >
            {loading ? 'Asking…' : 'Ask (⌘/Ctrl+Enter)'}
          </button>
          <a
            href={`${BASE}/swagger-ui/index.html`}
            target="_blank"
            className="rounded border px-3 py-2 hover:bg-gray-50"
          >
            Open API Docs
          </a>
        </div>
      </div>

      {error && <p className="text-red-600">Error: {error}</p>}

      {data?.answer && (
        <section className="rounded-xl border p-4 space-y-2">
          <h2 className="text-lg font-medium">Answer</h2>
          <p className="whitespace-pre-wrap">{data.answer}</p>

          {!!data.citations?.length && (
            <>
              <h3 className="pt-2 text-base font-medium">Citations</h3>
              <ul className="list-disc pl-5 text-sm">
                {data.citations.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </main>
  );
}
