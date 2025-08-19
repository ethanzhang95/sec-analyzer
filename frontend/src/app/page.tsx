'use client';
import { useState } from 'react';

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState<string | null>(null);
  const [data, setData]     = useState<{ ok: boolean; answer?: string; citations?: string[] } | null>(null);

  async function ask() {
    setLoading(true); setError(null); setData(null);
    try {
      const res = await fetch(process.env.NEXT_PUBLIC_API_URL + "/queries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const json = await res.json();
      if (!res.ok || !json?.ok) throw new Error(json?.error || "API error");
      setData(json);
    } catch (e:any) {
      setError(e.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold mb-4">SEC Filing Q&A</h1>
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2"
          placeholder="e.g., What is Apple's net income for FY 2022?"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <button
          onClick={ask}
          disabled={loading || !prompt.trim()}
          className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
        >
          {loading ? "Asking..." : "Ask"}
        </button>
      </div>

      {error && <p className="mt-4 text-red-600">Error: {error}</p>}
      {data?.answer && (
        <section className="mt-6 space-y-3">
          <h2 className="text-lg font-medium">Answer</h2>
          <p className="whitespace-pre-wrap">{data.answer}</p>
          {!!data.citations?.length && (
            <>
              <h3 className="text-base font-medium mt-4">Citations</h3>
              <ul className="list-disc pl-5 space-y-1">
                {data.citations.map((c,i) => <li key={i}>{c}</li>)}
              </ul>
            </>
          )}
        </section>
      )}
    </main>
  );
}
