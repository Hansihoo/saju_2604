import { useEffect, useState } from "react";
import type { Locale } from "../../../shared/copy";
import { DokkaebiSticker } from "../../character/DokkaebiSticker";
import {
  experienceCopy,
  experienceExpressions,
  readingTopics,
  type ReadingTopicKey,
} from "./experienceCopy";

export function DokkaebiWaiting({
  locale,
  topicKey,
}: {
  locale: Locale;
  topicKey: ReadingTopicKey;
}) {
  const copy = experienceCopy[locale];
  const topic = readingTopics.find((item) => item.key === topicKey)!;
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(
      () => setIndex((value) => value + 1),
      4000,
    );
    return () => window.clearInterval(timer);
  }, []);
  return (
    <section className="dk-waiting" aria-busy="true">
      <DokkaebiSticker
        expression={
          experienceExpressions.waiting[
            index % experienceExpressions.waiting.length
          ]
        }
        decorative
        size={230}
      />
      <h1 role="status">
        {locale === "ko"
          ? `${topic.label[locale]} ${copy.loadingTopic}`
          : `${copy.loadingTopic} ${topic.label[locale]}`}
      </h1>
      <div className="dk-waiting-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
    </section>
  );
}
