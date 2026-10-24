import { useEffect, useId, useState } from "react";
import type { Locale } from "../../../shared/copy";
import type { PreviewProgress } from "../../../shared/api/previewProgress";
import { DokkaebiSticker } from "../../character/DokkaebiSticker";
import {
  experienceCopy,
  experienceExpressions,
} from "./experienceCopy";
import { formatWaitingElapsed, hasFreshWaitingSignal, waitingCopy, waitingMessage, waitingStepStates } from "./waitingModel";

export function DokkaebiWaiting({
  locale,
  progress,
  previewElapsedSeconds = 0,
}: {
  locale: Locale;
  progress: PreviewProgress;
  // Used by the development-only visual preview; production starts at zero.
  previewElapsedSeconds?: number;
}) {
  const copy = experienceCopy[locale];
  const content = waitingCopy[locale];
  const titleId = useId();
  const [startedAt] = useState(() => Date.now() - previewElapsedSeconds * 1000);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.floor((now - startedAt) / 1000));
  const steps = waitingStepStates(progress.stage);
  const fresh = hasFreshWaitingSignal(progress, now);
  return (
    <section className="dk-waiting" aria-labelledby={titleId}>
      <DokkaebiSticker
        expression={
          experienceExpressions.waiting[
            Math.floor(seconds / 8) % experienceExpressions.waiting.length
          ]
        }
        decorative
        size={168}
      />
      <h1 id={titleId}>{copy.loadingTitle}</h1>
      <p className="dk-waiting-message" role="status">{waitingMessage(progress, seconds, locale)}</p>
      <ol className="dk-waiting-steps" aria-label={content.stepsLabel}>
        {content.steps.map((label, index) => (
          <li key={label} className={`dk-waiting-step is-${steps[index]}`} aria-current={steps[index] === "active" ? "step" : undefined}>
            <span className="dk-waiting-step-mark" aria-hidden="true">{steps[index] === "done" ? "✓" : index + 1}</span>
            <span>{label}<span className="dk-sr-only"> · {content[steps[index]]}</span></span>
          </li>
        ))}
      </ol>
      <div className="dk-waiting-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
      <p className="dk-waiting-meta">
        <span>{content.elapsed} <span role="timer" aria-live="off">{formatWaitingElapsed(seconds)}</span></span>
        {progress.lastSignalAt !== null ? (
          <span className={`dk-waiting-connection${fresh ? " is-connected" : ""}`}>
            <i aria-hidden="true" />{fresh ? content.connected : content.quiet}
          </span>
        ) : null}
      </p>
      {seconds >= 45 ? <p className="dk-waiting-patience">{content.longWait}</p> : null}
    </section>
  );
}
