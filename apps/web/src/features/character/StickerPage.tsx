import type { Locale } from "../../shared/copy";

import { DokkaebiPicker } from "./DokkaebiPicker";
import { DokkaebiSticker } from "./DokkaebiSticker";
import {
  dokkaebiAssetBase,
  getDokkaebiAssetUrl,
  type DokkaebiExpression,
} from "./dokkaebiCatalog";

type StickerPageProps = {
  locale: Locale;
  expression: DokkaebiExpression;
  onExpressionChange: (expression: DokkaebiExpression) => void;
  onNavigateToService: () => void;
};

export function StickerPage({
  locale,
  expression,
  onExpressionChange,
  onNavigateToService,
}: StickerPageProps) {
  const isKorean = locale === "ko";

  return (
    <main className="sticker-page">
      <header className="sticker-page-header">
        <button
          className="sticker-back"
          type="button"
          onClick={onNavigateToService}
          aria-label={isKorean ? "이전으로" : "Go back"}
        >
          ←
        </button>
      </header>

      <section className="sticker-intro">
        <h1>{isKorean ? "표정 선택" : "Choose a face"}</h1>
      </section>

      <section
        className="sticker-preview"
        aria-label={isKorean ? "선택한 표정" : "Selected expression"}
      >
        <DokkaebiSticker expression={expression} locale={locale} size={180} />
      </section>

      <DokkaebiPicker
        expression={expression}
        onChange={onExpressionChange}
        locale={locale}
      />

      <div className="sticker-actions">
        <button
          className="sticker-primary"
          type="button"
          onClick={onNavigateToService}
        >
          {isKorean ? "선택 완료" : "Done"}
        </button>
        <a
          className="sticker-download"
          href={getDokkaebiAssetUrl(expression)}
          download={`dokkaebi-${expression}.png`}
        >
          {isKorean ? "이미지 저장" : "Save image"}
        </a>
        <a
          className="sticker-pack-download"
          href={`${dokkaebiAssetBase}dokkaebi-emoticons.zip`}
          download="dokkaebi-emoticons.zip"
        >
          {isKorean ? "전체 ZIP 저장" : "Save all (ZIP)"}
        </a>
      </div>
    </main>
  );
}
