"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchHistory, historyClear, historyToggleFavorite, type HistoryEntry } from "@/lib/api";
import Link from "next/link";

export default function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const data = await fetchHistory(q, status);
      setEntries(data.entries);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    }
  }

  useEffect(() => {
    void load();
  }, [q, status]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">History</h1>
          <p className="text-sm text-muted-foreground">Search, favorites, and re-download like the TUI.</p>
        </div>
        <Button size="sm" variant="ghost" onClick={() => void historyClear().then(load)}>
          Clear
        </Button>
      </div>

      <div className="flex gap-2">
        <Input placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} className="h-9" />
        <select
          className="field h-9 rounded-lg px-2 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      ) : null}

      {entries.length === 0 ? (
        <div className="panel px-4 py-10 text-center text-sm text-muted-foreground">No history yet.</div>
      ) : (
        <ul className="space-y-2">
          {entries.map((e, index) => (
            <li key={`${e.date}-${index}`} className="panel space-y-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <p className="line-clamp-2 text-sm font-medium">{e.title}</p>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => void historyToggleFavorite(index).then(load)}
                  >
                    {e.favorite ? "★" : "☆"}
                  </Button>
                  <Badge variant={e.status === "success" ? "success" : "warn"}>{e.status}</Badge>
                </div>
              </div>
              <p className="font-mono text-[10px] text-muted-foreground">
                {new Date(e.date).toLocaleString()}
                {e.format_id ? ` · ${e.format_id}` : ""}
                {e.filesize ? ` · ${(e.filesize / 1e6).toFixed(1)} MB` : ""}
              </p>
              {e.error ? <p className="text-xs text-red-300">{e.error}</p> : null}
              {e.note ? <p className="text-xs text-muted-foreground">{e.note}</p> : null}
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/?redownload=${encodeURIComponent(e.url)}`}
                  className="text-xs text-primary underline-offset-2 hover:underline"
                >
                  Download again
                </Link>
                <a href={e.url} className="truncate font-mono text-xs text-muted-foreground underline-offset-2 hover:underline">
                  {e.url}
                </a>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
