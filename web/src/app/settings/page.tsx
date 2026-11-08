"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchConfig, patchConfig } from "@/lib/api";
import type { AppConfig } from "@/lib/types";

export default function SettingsPage() {
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchConfig()
      .then(setCfg)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  if (!cfg) {
    return <p className="text-sm text-muted-foreground">{error || "Loading…"}</p>;
  }

  function set<K extends keyof AppConfig>(key: K, value: AppConfig[K]) {
    setCfg((prev) => (prev ? { ...prev, [key]: value } : prev));
    setSaved(false);
  }

  async function onSave() {
    if (!cfg) return;
    try {
      const next = await patchConfig(cfg);
      setCfg(next);
      setSaved(true);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Shared with the TUI via ~/.config/yank/config.toml.</p>
      </div>

      <div className="panel space-y-3 p-4 text-sm">
        <label className="block space-y-1">
          <span className="text-xs text-muted-foreground">Format preference</span>
          <select
            className="field h-9 w-full rounded-lg px-2"
            value={cfg.format_preference}
            onChange={(e) => set("format_preference", e.target.value)}
          >
            <option value="best">Best</option>
            <option value="best_video_audio">Best video + audio</option>
            <option value="audio_only">Audio only</option>
          </select>
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-muted-foreground">Max concurrent</span>
          <Input
            type="number"
            min={1}
            max={8}
            value={cfg.max_concurrent}
            onChange={(e) => set("max_concurrent", parseInt(e.target.value, 10) || 1)}
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-muted-foreground">Filename template</span>
          <Input
            value={cfg.filename_template}
            onChange={(e) => set("filename_template", e.target.value)}
            className="font-mono text-xs"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-muted-foreground">Default subtitle language</span>
          <Input value={cfg.default_subtitle_lang} onChange={(e) => set("default_subtitle_lang", e.target.value)} />
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-muted-foreground">Proxy</span>
          <Input value={cfg.proxy} onChange={(e) => set("proxy", e.target.value)} className="font-mono text-xs" />
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-muted-foreground">Playlist items</span>
          <Input value={cfg.playlist_items} onChange={(e) => set("playlist_items", e.target.value)} />
        </label>
        <label className="block space-y-1">
          <span className="text-xs text-muted-foreground">SponsorBlock remove</span>
          <Input value={cfg.sponsorblock_remove} onChange={(e) => set("sponsorblock_remove", e.target.value)} />
        </label>
        <div className="flex flex-wrap gap-3">
          {(
            [
              ["embed_metadata", "Embed metadata"],
              ["embed_subtitles", "Embed subtitles"],
              ["download_thumbnail", "Thumbnail"],
              ["download_playlist", "Expand playlists"],
              ["split_chapters", "Split chapters"],
              ["audio_normalize", "Normalize audio"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 text-muted-foreground">
              <input
                type="checkbox"
                className="accent-primary"
                checked={Boolean(cfg[key])}
                onChange={(e) => set(key, e.target.checked)}
              />
              {label}
            </label>
          ))}
        </div>
        <Button onClick={() => void onSave()}>Save settings</Button>
        {saved ? <p className="text-xs text-emerald-400">Saved.</p> : null}
        {error ? <p className="text-xs text-red-300">{error}</p> : null}
      </div>
    </div>
  );
}
