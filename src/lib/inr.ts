/**
 * Indian money units (owner directive): amounts read the way people
 * say them — lakhs and crores — with the exact rupee figure kept
 * alongside (pillar 1: the display never replaces the fact).
 */

const CRORE = 1e7;
const LAKH = 1e5;

export interface InrDisplay {
  /** "₹2.03 கோடி" / "₹2.03 crore"; the exact figure below one lakh. */
  primary: string;
  /** The exact rupee figure when primary is a rounded unit, else null. */
  exact: string | null;
}

export function formatInrCompact(
  amount: number,
  locale: string,
): InrDisplay {
  const tag = locale === "ta" ? "ta-IN" : "en-IN";
  const exact = new Intl.NumberFormat(tag, {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);

  const inUnit = (value: number, unitTa: string, unitEn: string) => {
    const n = new Intl.NumberFormat(tag, {
      maximumFractionDigits: 2,
    }).format(Math.round(value * 100) / 100);
    return `₹${n} ${locale === "ta" ? unitTa : unitEn}`;
  };

  if (amount >= CRORE) {
    return { primary: inUnit(amount / CRORE, "கோடி", "crore"), exact };
  }
  if (amount >= LAKH) {
    return { primary: inUnit(amount / LAKH, "லட்சம்", "lakh"), exact };
  }
  return { primary: exact, exact: null };
}
