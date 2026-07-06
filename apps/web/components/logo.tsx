/** Memrise mark: nested rounded squares — episodes distilled into a canonical memory. Monochrome. */
export function Logo({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      className={className}
      aria-hidden
    >
      <rect
        x="9"
        y="9"
        width="30"
        height="30"
        rx="9"
        stroke="currentColor"
        strokeOpacity={0.25}
        strokeWidth={2.5}
      />
      <rect
        x="14"
        y="14"
        width="20"
        height="20"
        rx="6.5"
        stroke="currentColor"
        strokeOpacity={0.5}
        strokeWidth={2.5}
      />
      <rect x="19.5" y="19.5" width="9" height="9" rx="3" fill="currentColor" />
    </svg>
  );
}
