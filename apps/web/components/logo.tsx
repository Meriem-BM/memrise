import Image from "next/image";

const RATIO = 587 / 96;

/** Memrise wordmark. `size` is the rendered height in px. */
export function Logo({ size = 22, className }: { size?: number; className?: string }) {
  return (
    <Image
      src="/logo.png"
      alt="Memrise"
      width={Math.round(size * RATIO)}
      height={size}
      priority
      unoptimized
      className={className}
    />
  );
}
