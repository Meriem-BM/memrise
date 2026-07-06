import Image from "next/image";

// Mark exported transparent from the source art (intrinsic ~179x160).
const RATIO = 179 / 160;

/** Memrise mark. `size` is the rendered height in px. */
export function Logo({ size = 24, className }: { size?: number; className?: string }) {
  return (
    <Image
      src="/logo.png"
      alt=""
      width={Math.round(size * RATIO)}
      height={size}
      priority
      unoptimized
      className={className}
    />
  );
}
