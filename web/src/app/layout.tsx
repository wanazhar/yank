import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ConnectBootstrap } from "@/components/connect-bootstrap";
import { Nav } from "@/components/nav";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Yank Connect",
  description: "Paste a URL, pick a format, download to your device.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Yank", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#0c0d14",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${sans.variable} ${mono.variable}`}>
      <body className="min-h-dvh font-sans">
        <div className="mx-auto flex min-h-dvh max-w-lg flex-col px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-[max(0.5rem,env(safe-area-inset-top))]">
          <header className="glass-chrome glass-header mb-5 flex items-center justify-between gap-3 px-3 py-2.5">
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-semibold tracking-tight text-foreground">
                yank
              </span>
              <span className="font-mono text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground/90">
                connect
              </span>
            </div>
            <Nav />
          </header>
          <main className="relative z-[1] flex-1 animate-fade-in">
            <ConnectBootstrap>{children}</ConnectBootstrap>
          </main>
        </div>
      </body>
    </html>
  );
}
