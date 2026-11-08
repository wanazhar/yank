export type AppConfig = {
  format_preference: string;
  max_concurrent: number;
  filename_template: string;
  audio_format: string;
  subtitle_format: string;
  embed_metadata: boolean;
  embed_subtitles: boolean;
  default_subtitle_lang: string;
  download_thumbnail: boolean;
  download_playlist: boolean;
  proxy: string;
  rate_limit: string;
  playlist_items: string;
  sponsorblock_remove: string;
  split_chapters: boolean;
  audio_normalize: boolean;
  language: string;
};

export type DownloadOptionsIn = {
  filename_template?: string;
  download_thumbnail?: boolean;
  embed_metadata?: boolean;
  embed_subtitles?: boolean;
  write_subtitles_file?: boolean;
  subtitle_langs?: string[];
  custom_format?: string;
  proxy?: string;
  playlist_items?: string;
  sponsorblock_remove?: string;
  download_sections?: string;
  audio_normalize?: boolean;
  split_chapters?: boolean;
  meta_title?: string;
  meta_artist?: string;
  tag?: string;
  note?: string;
};

export const defaultOptions = (cfg: AppConfig | null): DownloadOptionsIn => ({
  filename_template: cfg?.filename_template,
  download_thumbnail: cfg?.download_thumbnail ?? false,
  embed_metadata: cfg?.embed_metadata ?? true,
  embed_subtitles: cfg?.embed_subtitles ?? false,
  write_subtitles_file: false,
  subtitle_langs: cfg ? [cfg.default_subtitle_lang] : ["en"],
  audio_normalize: cfg?.audio_normalize ?? false,
  split_chapters: cfg?.split_chapters ?? false,
  proxy: cfg?.proxy || "",
  playlist_items: cfg?.playlist_items || "",
  sponsorblock_remove: cfg?.sponsorblock_remove || "",
});
