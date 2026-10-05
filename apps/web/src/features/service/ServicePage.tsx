import { useEffect, useRef, useState } from "react";
import type { SajuPreviewResponse } from "../../shared/api/contracts";
import type { Locale } from "../../shared/copy";
import { useSajuInputForm } from "../shared/useSajuInputForm";
import type { DokkaebiExpression } from "../character/dokkaebiCatalog";
import { DokkaebiSticker } from "../character/DokkaebiSticker";
import { DokkaebiBirthForm } from "./experience/DokkaebiBirthForm";
import { DokkaebiLanding } from "./experience/DokkaebiLanding";
import { DokkaebiReading } from "./experience/DokkaebiReading";
import { DokkaebiWaiting } from "./experience/DokkaebiWaiting";
import {
  experienceCopy,
  type ReadingTopicKey,
} from "./experience/experienceCopy";
import "./experience/experience.css";

type ServicePageProps = {
  locale: Locale;
  onLocaleChange: (locale: Locale) => void;
  result: SajuPreviewResponse | null;
  onResultChange: (result: SajuPreviewResponse | null) => void;
  expression: DokkaebiExpression;
  onExpressionChange: (expression: DokkaebiExpression) => void;
  onChooseExpression: () => void;
};

export function ServicePage({
  locale,
  onLocaleChange,
  result,
  onResultChange,
  expression,
  onExpressionChange,
  onChooseExpression,
}: ServicePageProps) {
  const copy = experienceCopy[locale];
  const [stage, setStage] = useState<"welcome" | "birth" | "time">("welcome");
  const [topicKey, setTopicKey] = useState<ReadingTopicKey>("today");
  const mainRef = useRef<HTMLElement>(null);
  const form = useSajuInputForm({
    locale,
    debug: false,
    onSuccess: onResultChange,
    onErrorResult: () => onResultChange(null),
  });
  const screen = form.loading ? "waiting" : result ? "reading" : stage;

  useEffect(() => {
    if (mainRef.current?.closest("[hidden]")) return;
    window.scrollTo(0, 0);
    mainRef.current?.focus({ preventScroll: true });
  }, [screen]);

  function goHome() {
    if (form.loading) return;
    onResultChange(null);
    setStage("welcome");
  }
  function editInformation() {
    onResultChange(null);
    setStage("birth");
  }
  function goBack() {
    if (result) editInformation();
    else setStage(stage === "time" ? "birth" : "welcome");
  }

  return (
    <div className={`dk-experience dk-screen-${screen}`}>
      <header className="dk-header">
        <div className="dk-header-left">
          {screen !== "welcome" ? (
            <button
              className="dk-icon-button dk-back-button"
              disabled={form.loading}
              onClick={goBack}
              aria-label={result ? copy.edit : copy.back}
            >
              ←
            </button>
          ) : null}
          {screen !== "welcome" ? (
            <button
              className="dk-icon-button"
              disabled={form.loading}
              onClick={goHome}
              aria-label={copy.home}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="m3 10 9-7 9 7v10H3Z" />
                <path d="M9 20v-7h6v7" />
              </svg>
            </button>
          ) : null}
        </div>
        <div className="dk-header-actions">
          <button
            className="dk-icon-button dk-face-button"
            onClick={onChooseExpression}
            disabled={form.loading}
            aria-label={copy.faces}
          >
            <DokkaebiSticker expression={expression} decorative size={28} />
          </button>
          <label className="dk-locale">
            <span className="dk-sr-only">Language</span>
            <select
              value={locale}
              disabled={form.loading || Boolean(result)}
              title={result ? copy.resultLanguageNote : undefined}
              onChange={(event) => onLocaleChange(event.target.value as Locale)}
            >
              <option value="ko">KO</option>
              <option value="en">EN</option>
            </select>
          </label>
        </div>
      </header>
      <main className="dk-main" ref={mainRef} tabIndex={-1}>
        {screen === "waiting" ? (
          <DokkaebiWaiting locale={locale} topicKey={topicKey} />
        ) : result ? (
          <DokkaebiReading
            key={result.trace_id}
            locale={locale}
            result={result}
            detailPayload={form.lastSubmittedPayload}
            expression={expression}
            onExpressionChange={onExpressionChange}
            onEdit={editInformation}
            topicKey={topicKey}
            onTopicChange={setTopicKey}
          />
        ) : stage === "welcome" ? (
          <DokkaebiLanding
            locale={locale}
            expression={expression}
            onStart={(topic) => {
              setTopicKey(topic);
              setStage("birth");
            }}
          />
        ) : (
          <DokkaebiBirthForm
            key={stage}
            locale={locale}
            step={stage}
            form={form}
            topicKey={topicKey}
            onNext={() => setStage("time")}
          />
        )}
      </main>
    </div>
  );
}
