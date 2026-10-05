import type { ReadingCard } from "./readingModel";

export type ReadingBasis = {
  facts: string[];
  reading?: string;
  takeaway?: string;
};

// Explain supplied content only; never calculate a chart or infer a missing rule.
export function getReadingBasis(card: ReadingCard): ReadingBasis | null {
  const explanation = card.basis_explanation;
  if (explanation) {
    const facts = [...new Set(explanation.facts.map((fact) => fact.trim()).filter(Boolean))];
    const reading = explanation.reading.trim();
    if (facts.length && reading) {
      return {
        facts,
        reading,
        takeaway: card.user_takeaway.trim() || undefined,
      };
    }
  }
  const basis = card.basis_line.trim();
  // Older/other-provider responses can show their supplied basis without a
  // fabricated bridge from that basis to the result text.
  return basis ? { facts: [basis] } : null;
}
