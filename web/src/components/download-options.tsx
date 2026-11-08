"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchConfig } from "@/lib/api";
import { defaultOptions, type AppConfig, type DownloadOptionsIn } from "@/lib/types";
import { ChevronDown } from "lucide-react";

type Props = {
  value: DownloadOptionsIn;
  onChange: (v: DownloadOptionsIn) => void;
  subtitleLangs?: string[];
  extractAudio: boolean;
  onExtractAudio: (v: boolean) => void;
  audioFormat: string;
  onAudioFormat: (v: string) => void;
  scheduleMinutes: string;
  onScheduleMinutes: (v: string) => void;
  queueOnly: boolean;
  onQueueOnly: (v: boolean) => void;
};

export function DownloadOptions(props: Props) {
  const [open, setOpen] = useState(false);
  const [cfg, setCfg] = useState<AppConfig | null>(null);

  useEffect(() => {
    void fetchConfig().then(setCfg).catch(() => setCfg(null));
  }, []);

  const opts = props.value;

  function set<K extends keyof DownloadOptionsIn>(key: K, val: DownloadOptionsIn[K]) {
    props.onChange({ ...opts, [key]: val });
  }

  function loadDefaults() {
    props.onChange(defaultOptions(cfg));
  }

  return (
    <div className="panel overflow-hidden">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium"
        onClick={() => setOpen((v) => !v)}
      >
        Options
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div className="space-y-3 border-t border-white/[0.06] px-4 py-3 text-sm">
          <div className="flex flex-wrap gap-3">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="accent-primary"
                checked={props.extractAudio}
                onChange={(e) => props.onExtractAudio(e.target.checked)}
              />
              Audio only
            </label>
            {props.extractAudio ? (
              <select
                className="field rounded-lg px-2 py-1 text-xs"
                value={props.audioFormat}
                onChange={(e) => props.onAudioFormat(e.target.value)}
              >
                {["mp3", "m4a", "opus", "flac"].map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            ) : null}
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="accent-primary"
                checked={props.queueOnly}
                onChange={(e) => props.onQueueOnly(e.target.checked)}
              />
              Queue only
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-xs text-muted-foreground">Schedule (minutes)</span>
            <Input
              type="number"
              min={0}
              step={1}
              value={props.scheduleMinutes}
              onChange={(e) => props.onScheduleMinutes(e.target.value)}
              className="h-9"
            />
          </label>

          <div className="grid gap-2 sm:grid-cols-2">
            {(
              [
                ["download_thumbnail", "Thumbnail"],
                ["embed_metadata", "Embed metadata"],
                ["embed_subtitles", "Embed subtitles"],
                ["write_subtitles_file", "Subtitle file"],
                ["audio_normalize", "Normalize audio"],
                ["split_chapters", "Split chapters"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="flex items-center gap-2 text-muted-foreground">
                <input
                  type="checkbox"
                  className="accent-primary"
                  checked={Boolean(opts[key])}
                  onChange={(e) => set(key, e.target.checked)}
                />
                {label}
              </label>
            ))}
          </div>

          <label className="block space-y-1">
            <span className="text-xs text-muted-foreground">Filename template</span>
            <Input
              value={opts.filename_template || ""}
              onChange={(e) => set("filename_template", e.target.value)}
              className="h-9 font-mono text-xs"
            />
          </label>

          {props.subtitleLangs && props.subtitleLangs.length > 0 ? (
            <label className="block space-y-1">
              <span className="text-xs text-muted-foreground">Subtitle language</span>
              <select
                className="field h-9 w-full rounded-lg px-2 text-sm"
                value={opts.subtitle_langs?.[0] || "en"}
                onChange={(e) => set("subtitle_langs", [e.target.value])}
              >
                {props.subtitleLangs.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {(
            [
              ["custom_format", "Custom format"],
              ["proxy", "Proxy"],
              ["playlist_items", "Playlist items"],
              ["sponsorblock_remove", "SponsorBlock"],
              ["download_sections", "Sections"],
              ["meta_title", "Meta title"],
              ["meta_artist", "Meta artist"],
              ["tag", "Tag"],
              ["note", "Note"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="block space-y-1">
              <span className="text-xs text-muted-foreground">{label}</span>
              <Input
                value={(opts[key] as string) || ""}
                onChange={(e) => set(key, e.target.value)}
                className="h-9 font-mono text-xs"
              />
            </label>
          ))}

          <Button type="button" variant="ghost" size="sm" onClick={loadDefaults}>
            Reset to settings defaults
          </Button>
        </div>
      ) : null}
    </div>
  );
}
