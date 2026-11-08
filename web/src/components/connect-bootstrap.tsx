"use client";

import { useEffect, useState } from "react";
import { bootstrapPairFromUrl, ensureSession } from "@/lib/api";

export function ConnectBootstrap({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    bootstrapPairFromUrl();
    void (async () => {
      const ok = await ensureSession();
      setAuthed(ok);
      setReady(true);
    })();
  }, []);

  if (!ready) {
    return (
      <div className="panel flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary shadow-glow" />
        <span className="relative z-[1]">Connecting</span>
      </div>
    );
  }

  if (!authed) {
    return (
      <div className="panel space-y-3 p-5">
        <p className="relative z-[1] text-sm font-medium">Sign in via magic link</p>
        <p className="relative z-[1] text-pretty text-sm leading-relaxed text-muted-foreground">
          Open the link from <code className="rounded-lg bg-white/10 px-1.5 py-0.5 font-mono text-xs">yank connect</code> on
          this phone. No API token. Tailscale HTTPS can sign you in automatically.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
