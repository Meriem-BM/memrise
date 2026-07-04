import { Circle } from "lucide-react";
import Link from "next/link";

import { ClientOnly } from "@/components/client-only";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-black/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-2.5 px-6 py-4">
        <Link href="/" className="flex items-center gap-2.5">
          <ClientOnly
            fallback={
              <span
                className="inline-block size-[18px] shrink-0 rounded-full bg-white"
                aria-hidden
              />
            }
          >
            <Circle size={18} className="fill-white text-white" />
          </ClientOnly>
          <span className="text-xl font-semibold tracking-tight">Memrise</span>
        </Link>
      </div>
    </header>
  );
}
