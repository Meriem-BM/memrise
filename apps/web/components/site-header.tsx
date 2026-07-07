import Link from "next/link";

import { Logo } from "@/components/logo";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-2.5 px-6 py-4">
        <Link href="/" className="flex items-center text-white" aria-label="Memrise home">
          <Logo size={22} className="shrink-0" />
        </Link>
      </div>
    </header>
  );
}
