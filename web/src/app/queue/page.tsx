"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MediaPlayer } from "@/components/media-player";
import {
  fetchQueue,
  saveDownloadToDevice,
  queueClearFinished,
  queueItemCancel,
  queueItemPause,
  queueItemStart,
  queuePauseAll,
  queueRetryFailed,
  queueStartAll,
  type QueueItem,
} from "@/lib/api";
import { Download, Play } from "lucide-react";

function statusVariant(status: string): "default" | "success" | "warn" | "muted" {
  if (status === "completed") return "success";
  if (status === "error" || status === "cancelled") return "warn";
  if (status === "downloading") return "default";
  return "muted";
}

export default function QueuePage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [summary, setSummary] = useState<{ size: number; active: number; average_percent: number } | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const data = await fetchQueue(search);
      setItems(data.items);
      setSummary(data.summary ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load queue");
    }
  }, [search]);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => void reload(), 2000);
    return () => window.clearInterval(id);
  }, [reload]);

  async function act(fn: () => Promise<unknown>) {
    try {
      await fn();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Queue</h1>
        {summary ? (
          <p className="text-sm text-muted-foreground">
            {summary.size} items · {summary.active} active · {summary.average_percent.toFixed(0)}% avg
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">Pause, cancel, and bulk actions like the TUI.</p>
        )}
      </div>

      <Input
        placeholder="Search queue"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="h-9"
      />

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => void act(queueStartAll)}>
          Start all
        </Button>
        <Button size="sm" variant="outline" onClick={() => void act(queuePauseAll)}>
          Pause all
        </Button>
        <Button size="sm" variant="ghost" onClick={() => void act(queueClearFinished)}>
          Clear finished
        </Button>
        <Button size="sm" variant="ghost" onClick={() => void act(queueRetryFailed)}>
          Retry failed
        </Button>
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      ) : null}

      {items.length === 0 ? (
        <div className="panel px-4 py-10 text-center text-sm text-muted-foreground">Nothing queued.</div>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => {
            const pct = item.progress?.percent ?? 0;
            return (
              <li key={item.id} className="panel space-y-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="line-clamp-2 text-sm font-medium leading-snug">{item.title}</p>
                  <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                </div>
                {item.error ? <p className="text-xs text-red-300">{item.error}</p> : null}

                {item.progress && item.status === "downloading" ? (
                  <div className="space-y-1.5">
                    <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                      <div
                        className="h-full rounded-full bg-primary transition-[width] duration-300"
                        style={{ width: `${Math.min(100, pct)}%` }}
                      />
                    </div>
                    <p className="font-mono text-[11px] text-muted-foreground">
                      {pct.toFixed(1)}% · {item.progress.speed_display} · ETA {item.progress.eta_display}
                    </p>
                  </div>
                ) : null}

                {item.status === "completed" &&
                item.streamable &&
                (item.media_kind === "video" || item.media_kind === "audio") ? (
                  <div className="space-y-1.5">
                    <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                      <Play className="h-3 w-3" aria-hidden />
                      Stream on this device
                    </p>
                    <MediaPlayer
                      itemId={item.id}
                      mediaKind={item.media_kind}
                      title={item.title}
                    />
                    <p className="text-[10px] leading-snug text-muted-foreground">
                      Playback uses your phone or browser — the file stays in Connect staging until you save.
                    </p>
                  </div>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  {item.status !== "downloading" && item.status !== "completed" ? (
                    <Button size="sm" variant="outline" onClick={() => void act(() => queueItemStart(item.id))}>
                      Start
                    </Button>
                  ) : null}
                  {item.status === "downloading" ? (
                    <Button size="sm" variant="outline" onClick={() => void act(() => queueItemPause(item.id))}>
                      Pause
                    </Button>
                  ) : null}
                  {item.status !== "completed" && item.status !== "cancelled" ? (
                    <Button size="sm" variant="ghost" onClick={() => void act(() => queueItemCancel(item.id))}>
                      Cancel
                    </Button>
                  ) : null}
                  {item.downloadable ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        void act(() =>
                          saveDownloadToDevice(
                            item.id,
                            item.filename || item.progress?.filename || item.title,
                          ),
                        )
                      }
                    >
                      <Download className="h-3.5 w-3.5" />
                      Save to device
                    </Button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
