// lens + trendline mark, no fill so it sits directly on the header bg
export function Logo({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle cx="10" cy="10" r="6.25" className="stroke-logo-mark" strokeWidth="1.75" />
      <line x1="14.42" y1="14.42" x2="19.5" y2="19.5" className="stroke-logo-mark" strokeWidth="1.75" strokeLinecap="round" />
      <polyline
        points="4.5,13 11,11.5 16,4"
        className="stroke-logo-line"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="4" r="1.5" className="fill-logo-line" />
    </svg>
  );
}
