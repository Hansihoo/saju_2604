import { useEffect, useRef, useState } from "react";
import type { Locale } from "../../../shared/copy";
import { DokkaebiPicker } from "../../character/DokkaebiPicker";
import type { DokkaebiExpression } from "../../character/dokkaebiCatalog";
import { experienceCopy } from "./experienceCopy";
import { createReadingShareCard, type ReadingShareContent } from "./shareCard";

type Props = {
  locale: Locale;
  content: ReadingShareContent;
  topicKey: string;
  expression: DokkaebiExpression;
  onExpressionChange: (expression: DokkaebiExpression) => void;
  onClose: () => void;
};

export function DokkaebiShareDialog({
  locale,
  content,
  topicKey,
  expression,
  onExpressionChange,
  onClose,
}: Props) {
  const copy = experienceCopy[locale];
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [card, setCard] = useState<{ url: string; file: File } | null>(null);
  const [error, setError] = useState(false);
  const [picking, setPicking] = useState(false);
  const [message, setMessage] = useState("");
  const [sharing, setSharing] = useState(false);
  const [showCopyText, setShowCopyText] = useState(false);
  const entryUrl = new URL(import.meta.env.BASE_URL, window.location.origin)
    .href;
  const shareText = `${content.topic}${content.periodLabel ? ` · ${content.periodLabel}` : ""}\n${content.title}\n\n${content.takeaway}${content.limitation ? `\n\n${content.limitation}` : ""}\n\n${entryUrl}`;
  let canShareFiles = false;
  try {
    canShareFiles = Boolean(
      card &&
        typeof navigator.share === "function" &&
        typeof navigator.canShare === "function" &&
        navigator.canShare({ files: [card.file] }),
    );
  } catch {
    /* Keep image download available. */
  }

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog?.close();
      document.body.style.overflow = oldOverflow;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | undefined;
    setCard(null);
    setError(false);
    setMessage("");
    void createReadingShareCard(content, expression)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setCard({
          url: objectUrl,
          file: new File([blob], `saju-${topicKey}.png`, {
            type: "image/png",
          }),
        });
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [
    content.title,
    content.takeaway,
    content.topic,
    content.periodLabel,
    content.limitation,
    expression,
    topicKey,
  ]);

  async function shareOrCopy() {
    if (!card || sharing) return;
    setSharing(true);
    try {
      if (canShareFiles) {
        // PNG is prepared before this click so native sharing retains user activation.
        await navigator.share({
          title: content.title,
          text: shareText,
          files: [card.file],
        });
      } else {
        await navigator.clipboard.writeText(shareText);
        setMessage(copy.copied);
      }
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError")
        return;
      setMessage(canShareFiles ? copy.shareFailed : copy.copyFailed);
      if (!canShareFiles) setShowCopyText(true);
    } finally {
      setSharing(false);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="dk-share-dialog"
      aria-labelledby="dk-share-title"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="dk-share-sheet">
        <div className="dk-share-sheet-top">
          <button
            className="dk-icon-button"
            aria-label={copy.close}
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <h2 id="dk-share-title">{copy.shareTitle}</h2>
        <div className="dk-share-image">
          {card ? (
            <img
              src={card.url}
              alt={`${content.topic}${content.periodLabel ? ` · ${content.periodLabel}` : ""}: ${content.title}. ${content.takeaway}${content.limitation ? `. ${content.limitation}` : ""}`}
              width={1080}
              height={1350}
            />
          ) : (
            <p role="status">{error ? copy.shareError : copy.preparing}</p>
          )}
        </div>
        <button
          className="dk-text-button dk-face-toggle"
          aria-expanded={picking}
          onClick={() => setPicking((value) => !value)}
        >
          {copy.changeFace}
          <span aria-hidden="true">{picking ? "−" : "+"}</span>
        </button>
        {picking ? (
          <DokkaebiPicker
            expression={expression}
            onChange={onExpressionChange}
            locale={locale}
          />
        ) : null}
        <div className="dk-share-actions">
          {card ? (
            <a className="dk-primary" href={card.url} download={card.file.name}>
              {copy.save}
              <span aria-hidden="true">↓</span>
            </a>
          ) : (
            <button className="dk-primary" disabled>
              {copy.save}
            </button>
          )}
          <button
            className="dk-secondary"
            disabled={!card || sharing}
            onClick={() => void shareOrCopy()}
          >
            {canShareFiles ? copy.send : copy.copy}
          </button>
        </div>
        {message ? (
          <p className="dk-share-feedback" role="status">
            {message}
          </p>
        ) : null}
        {showCopyText ? (
          <textarea
            className="dk-copy-text"
            value={shareText}
            readOnly
            aria-label={copy.copy}
            onFocus={(e) => e.target.select()}
          />
        ) : null}
      </div>
    </dialog>
  );
}
