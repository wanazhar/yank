"use client";

import { streamUrl } from "@/lib/api";
import { useMemo } from "react";

type Props = {
  itemId: string;
  mediaKind: "video" | "audio";
  title: string;
};

export function MediaPlayer({ itemId, mediaKind, title }: Props) {
  const src = useMemo(() => streamUrl(itemId), [itemId]);

  if (mediaKind === "audio") {
    return (
      <audio
        key={src}
        controls
        preload="metadata"
        className="w-full rounded-lg"
        aria-label={`Play ${title}`}
      >
        <source src={src} />
      </audio>
    );
  }

  return (
    <video
      key={src}
      controls
      playsInline
      preload="metadata"
      className="max-h-52 w-full rounded-lg bg-black/40"
      aria-label={`Play ${title}`}
    >
      <source src={src} />
    </video>
  );
}
