"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DownloadOptions } from "@/components/download-options";
import { SessionCookies } from "@/components/session-cookies";
import { Input } from "@/components/ui/input";
import {
  enqueueBatch,
  enqueueDownload,
  extractFormats,
  fetchConfig,
  type PlaylistExtract,
  type VideoMeta,
} from "@/lib/api";
import { defaultOptions, type DownloadOptionsIn } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ArrowRight, Link2 } from "lucide-react";
import { useRouter } from "next/navigation";

function isPlaylist(x: VideoMeta | PlaylistExtract): x is PlaylistExtract {
  return "playlist" in x && x.playlist === true;
}

export default function HomePage() {
  const router = useRouter();
  const [batch, setBatch] = useState(false);
  const [playlist, setPlaylist] = useState(false);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [meta, setMeta] = useState<VideoMeta | null>(null);
  const [playlistUrls, setPlaylistUrls] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [extractAudio, setExtractAudio] = useState(false);
  const [audioFormat, setAudioFormat] = useState("mp3");
  const [queueOnly, setQueueOnly] = useState(false);
  const [scheduleMinutes, setScheduleMinutes] = useState("0");
  const [options, setOptions] = useState<DownloadOptionsIn>({});
  const [enqueuing, setEnqueuing] = useState(false);

  useEffect(() => {
    void fetchConfig()
      .then((cfg) => {
        setAudioFormat(cfg.audio_format);
        setPlaylist(cfg.download_playlist);
        setOptions(defaultOptions(cfg));
        if (cfg.format_preference === "audio_only") setExtractAudio(true);
      })
      .catch(() => undefined);
  }, []);

  async function onExtract(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMeta(null);
    setPlaylistUrls([]);
    setLoading(true);
    try {
      const data = await extractFormats(url.trim(), playlist);
      if (isPlaylist(data)) {
        setPlaylistUrls(data.entries.map((e) => e.url));
        return;
      }
      setMeta(data);
      setSelected(data.suggested_format_id ?? data.formats[0]?.format_id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch formats");
    } finally {
      setLoading(false);
    }
  }

  async function onDownload() {
    setEnqueuing(true);
    setError(null);
    const sched = parseFloat(scheduleMinutes) || 0;
    const payload = {
      format_id: selected || "",
      extract_audio: extractAudio,
      audio_format: audioFormat,
      auto_start: !queueOnly,
      schedule_minutes: sched,
      options,
    };

    try {
      if (playlistUrls.length > 0) {
        await enqueueBatch(playlistUrls, payload);
      } else if (batch) {
        const urls = url
          .split(/\n/)
          .map((u) => u.trim())
          .filter(Boolean);
        await enqueueBatch(urls, payload);
      } else if (meta && selected) {
        await enqueueDownload({ url: meta.url, ...payload });
      } else {
        throw new Error("Nothing to download");
      }
      router.push("/queue/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enqueue failed");
      setEnqueuing(false);
    }
  }

  const canDownload = playlistUrls.length > 0 || (meta && selected) || (batch && url.trim());

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-balance text-2xl font-semibold tracking-tight">Paste a link</h1>
        <p className="text-sm text-muted-foreground">Same flow as the TUI: URL → formats → options → queue.</p>
      </div>

      <SessionCookies />

      <div className="flex flex-wrap gap-3 text-sm">
        <label className="flex items-center gap-2 text-muted-foreground">
          <input type="checkbox" className="accent-primary" checked={batch} onChange={(e) => setBatch(e.target.checked)} />
          Batch (one URL per line)
        </label>
        <label className="flex items-center gap-2 text-muted-foreground">
          <input
            type="checkbox"
            className="accent-primary"
            checked={playlist}
            onChange={(e) => setPlaylist(e.target.checked)}
          />
          Playlist
        </label>
      </div>

      <form className="space-y-3" onSubmit={onExtract}>
        <div className="relative">
          <Link2
            className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-muted-foreground"
            aria-hidden
          />
          {batch ? (
            <textarea
              placeholder="https://&#10;https://"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              rows={4}
              className="field w-full rounded-lg py-2 pl-10 pr-3 font-mono text-sm"
            />
          ) : (
            <Input
              placeholder="https://"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="pl-10"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
            />
          )}
        </div>
        <Button type="submit" className="w-full" size="lg" disabled={loading || !url.trim()}>
          {loading ? "Fetching…" : playlist ? "Resolve playlist" : batch ? "Resolve batch" : "Formats"}
          {!loading ? <ArrowRight className="h-4 w-4 opacity-80" /> : null}
        </Button>
        {error ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        ) : null}
      </form>

      {playlistUrls.length > 0 ? (
        <section className="panel space-y-3 p-4">
          <p className="text-sm font-medium">{playlistUrls.length} entries queued for download</p>
          <DownloadOptions
            value={options}
            onChange={setOptions}
            extractAudio={extractAudio}
            onExtractAudio={setExtractAudio}
            audioFormat={audioFormat}
            onAudioFormat={setAudioFormat}
            scheduleMinutes={scheduleMinutes}
            onScheduleMinutes={setScheduleMinutes}
            queueOnly={queueOnly}
            onQueueOnly={setQueueOnly}
          />
          <Button className="w-full" size="lg" disabled={enqueuing} onClick={() => void onDownload()}>
            {enqueuing ? "Starting…" : queueOnly ? "Add all to queue" : "Download all"}
          </Button>
        </section>
      ) : null}

      {meta ? (
        <section className="panel space-y-4 p-4 animate-fade-in">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <h2 className="truncate text-base font-medium leading-snug">{meta.title}</h2>
              <div className="flex flex-wrap gap-2">
                <Badge variant="muted">{meta.platform}</Badge>
                {meta.uploader ? <span className="text-xs text-muted-foreground">{meta.uploader}</span> : null}
                {meta.duration != null ? (
                  <span className="font-mono text-xs text-muted-foreground">
                    {Math.floor(meta.duration / 60)}m
                  </span>
                ) : null}
              </div>
            </div>
            {meta.thumbnail ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={meta.thumbnail} alt="" className="h-14 w-24 shrink-0 rounded-md object-cover ring-1 ring-white/10" />
            ) : null}
          </div>

          <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
            {meta.formats.map((f) => {
              const on = selected === f.format_id;
              return (
                <button
                  key={f.format_id}
                  type="button"
                  onClick={() => setSelected(f.format_id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-md border px-3 py-2.5 text-left text-sm transition-colors",
                    on ? "border-primary/40 bg-primary/10" : "border-transparent bg-white/[0.02] hover:bg-white/[0.05]",
                  )}
                >
                  <span className="font-mono text-xs text-muted-foreground">{f.format_id}</span>
                  <span className="flex-1 truncate">{f.resolution || "—"}</span>
                  <span className="font-mono text-xs text-muted-foreground">{f.filesize_display}</span>
                  <Badge variant={on ? "default" : "muted"}>{f.kind || "av"}</Badge>
                </button>
              );
            })}
          </div>

          <DownloadOptions
            value={options}
            onChange={setOptions}
            subtitleLangs={meta.subtitle_langs}
            extractAudio={extractAudio}
            onExtractAudio={setExtractAudio}
            audioFormat={audioFormat}
            onAudioFormat={setAudioFormat}
            scheduleMinutes={scheduleMinutes}
            onScheduleMinutes={setScheduleMinutes}
            queueOnly={queueOnly}
            onQueueOnly={setQueueOnly}
          />

          <Button className="w-full" size="lg" disabled={!canDownload || enqueuing} onClick={() => void onDownload()}>
            {enqueuing ? "Starting…" : queueOnly ? "Add to queue" : "Download"}
          </Button>
        </section>
      ) : null}

      {batch && !meta && playlistUrls.length === 0 && url.trim() ? (
        <section className="panel space-y-3 p-4">
          <p className="text-sm text-muted-foreground">Batch ready — uses best format per URL from settings.</p>
          <DownloadOptions
            value={options}
            onChange={setOptions}
            extractAudio={extractAudio}
            onExtractAudio={setExtractAudio}
            audioFormat={audioFormat}
            onAudioFormat={setAudioFormat}
            scheduleMinutes={scheduleMinutes}
            onScheduleMinutes={setScheduleMinutes}
            queueOnly={queueOnly}
            onQueueOnly={setQueueOnly}
          />
          <Button className="w-full" size="lg" disabled={enqueuing} onClick={() => void onDownload()}>
            {enqueuing ? "Starting…" : queueOnly ? "Queue batch" : "Download batch"}
          </Button>
        </section>
      ) : null}
    </div>
  );
}
