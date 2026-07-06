/**
 * Source dots (D-025): one dot per outlet that covered the story. No
 * denominator — the registry will grow (national outlets to come), so a
 * fraction would mislead. Which outlets, and which tracked outlets did
 * not cover it, live on the story page. Never a rating (pillar 2).
 */
const CAP = 12;

export function SourceDots({
  count,
  label,
}: {
  count: number;
  label: string;
}) {
  const shown = Math.min(count, CAP);
  return (
    <span
      className="inline-flex items-center gap-[3px]"
      role="img"
      aria-label={label}
    >
      {Array.from({ length: shown }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className="size-[7px] rounded-full bg-primary"
        />
      ))}
      {count > CAP ? (
        <span className="text-[10px] font-bold text-primary">+{count - CAP}</span>
      ) : null}
    </span>
  );
}
