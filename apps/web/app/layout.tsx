import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/site-header";
import { QueryProvider } from "@/providers/query-provider";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-inter",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "Memrise Inspector",
  description: "Inspect the living memory of the Memrise framework",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
        <QueryProvider>
          <div className="relative flex min-h-screen flex-col selection:bg-white/30">
            <SiteHeader />
            <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-10">{children}</main>
            <footer className="mx-auto w-full max-w-7xl px-6 py-8 text-xs text-faint">
              <span className="font-mono">memrise</span> · inspector for a living memory system
            </footer>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
