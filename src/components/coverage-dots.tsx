/**
 * The coverage dot-row: Arivom's signature transparency visual (D-023).
 * One dot per tracked outlet; filled = that outlet covered the story.
 * Pure presentation — says which, never why, no bias labels (pillar 2).
 */
export function CoverageDots({
  covered,
  total,
  label,
}: {
  covered: number;
  total: number;
  label: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-[3px]"
      role="img"
      aria-label={label}
    >
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={`size-[7px] rounded-full ${
            i < covered ? "bg-primary" : "bg-border"
          }`}
        />
      ))}
      <span className="ms-1.5 text-[11px] font-semibold tabular-nums text-muted-foreground">
        {covered}/{total}
      </span>
    </span>
  );
}
