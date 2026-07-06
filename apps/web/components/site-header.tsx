import Link from "next/link";

import { Logo } from "@/components/logo";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-black/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-2.5 px-6 py-4">
        <Link href="/" className="flex items-center gap-2.5 text-white">
          <Logo size={20} className="shrink-0" />
          <span className="text-xl font-semibold tracking-tight">Memrise</span>
        </Link>
      </div>
    </header>
  );
}
