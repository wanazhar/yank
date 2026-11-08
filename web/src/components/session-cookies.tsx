"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { clearSessionCookies, fetchSession, uploadSessionCookies } from "@/lib/api";
import { ChevronDown } from "lucide-react";

export function SessionCookies() {
  const [open, setOpen] = useState(false);
  const [set, setSet] = useState(false);
  const [text, setText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchSession();
      setSet(Boolean((s.cookies as { set?: boolean } | undefined)?.set));
    } catch {
      setSet(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSave() {
    setBusy(true);
    setStatus(null);
    try {
      await uploadSessionCookies(text);
      setText("");
      setSet(true);
      setStatus("Saved for this Connect session only.");
      void refresh();
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function onClear() {
    setBusy(true);
    setStatus(null);
    try {
      await clearSessionCookies();
      setSet(false);
      setStatus("Cleared.");
      void refresh();
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Clear failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel overflow-hidden">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm"
        onClick={() => setOpen((v) => !v)}
      >
        <span>
          YouTube session cookies{" "}
          <span className="font-mono text-xs text-muted-foreground">
            {set ? "· active" : "· optional"}
          </span>
        </span>
        <ChevronDown className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div className="space-y-3 border-t border-white/[0.06] px-4 py-3 text-sm text-muted-foreground">
          <p className="text-pretty leading-relaxed">
            Your phone browser does not let this app read YouTube&apos;s cookies automatically (that
            would let any site steal logins). You can paste a{" "}
            <span className="text-foreground">Netscape cookies.txt</span> export from a browser
            where you&apos;re signed in. It stays in server RAM for your session only and is wiped
            on <code className="font-mono text-xs">yank connect stop</code>.
          </p>
          <p className="text-pretty text-xs leading-relaxed">
            On Android: Firefox + &quot;Export Cookies&quot; extensions work well. On iOS, exporting
            is harder — using the desktop TUI&apos;s browser cookies on the server is usually easier.
          </p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            placeholder="# Netscape HTTP Cookie File&#10;.youtube.com	TRUE	/	TRUE	..."
            className="field w-full resize-y rounded-lg px-3 py-2 font-mono text-xs text-foreground placeholder:text-muted-foreground/70"
            spellCheck={false}
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" disabled={busy || !text.trim()} onClick={() => void onSave()}>
              Use for my downloads
            </Button>
            <Button type="button" size="sm" variant="outline" disabled={busy || !set} onClick={() => void onClear()}>
              Clear
            </Button>
          </div>
          {status ? <p className="text-xs text-foreground">{status}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
