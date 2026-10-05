import type { Locale } from "../../shared/copy";

import { getDokkaebiAssetUrl, getDokkaebiLabel, type DokkaebiExpression } from "./dokkaebiCatalog";
import "./dokkaebi.css";

type DokkaebiStickerProps = {
  expression: DokkaebiExpression;
  size?: number;
  locale?: Locale;
  decorative?: boolean;
  className?: string;
  loading?: "eager" | "lazy";
};

export function DokkaebiSticker({
  expression,
  size = 80,
  locale = "ko",
  decorative = false,
  className = "",
  loading = "eager",
}: DokkaebiStickerProps) {
  const label = getDokkaebiLabel(expression, locale);

  return (
    <img
      className={`dokkaebi-sticker ${className}`.trim()}
      src={getDokkaebiAssetUrl(expression)}
      alt={decorative ? "" : locale === "ko" ? `${label} 표정의 도깨비` : `Dokkaebi: ${label}`}
      aria-hidden={decorative || undefined}
      width={size}
      height={size}
      decoding="async"
      loading={loading}
      draggable={false}
    />
  );
}
