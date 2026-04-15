import { useEffect, useState } from "react";

import { Locale } from "../../../shared/copy";

type LoadingSlide = {
  label: string;
  title: string;
  body: string;
};

const loadingSlidesByLocale: Record<
  Locale,
  {
    eyebrow: string;
    title: string;
    note: string;
    benefitsTitle: string;
    benefits: string[];
    slides: LoadingSlide[];
  }
> = {
  ko: {
    eyebrow: "잠시만 기다려 주세요",
    title: "사주 풀이 중입니다.",
    note: "시간이 소요될 수 있습니다.",
    benefitsTitle: "이 풀이의 장점",
    benefits: [
      "꾸며낸 해석보다 실제 사주 구조를 먼저 확인합니다.",
      "지역 시차와 역법 보정을 반영해 기준 데이터를 맞춥니다.",
      "검증된 기준 위에서 읽기 쉽게 풀이를 정리합니다.",
    ],
    slides: [
      {
        label: "정확한 기준",
        title: "꾸며낸 해석이 아닌, 내 사주를 정확하게 보기 위해 만들었습니다.",
        body: "좋게 들리는 말보다 실제 사주 구조를 먼저 확인하는 방식으로 풀이를 준비합니다.",
      },
      {
        label: "오차 최소화",
        title: "지역 시차와 역법을 반영해 만세력을 직접 계산하여 오차를 최소화했습니다.",
        body: "출생 지역과 시간 보정까지 계산에 반영해 기준 데이터부터 흔들리지 않도록 맞춥니다.",
      },
      {
        label: "검증된 해석",
        title: "검증된 주요 학파를 기준으로 신뢰할 수 있는 방식으로 풀이했습니다.",
        body: "임의로 꾸민 표현보다 검토된 기준을 바탕으로, 읽기 쉽게 해석을 정리합니다.",
      },
    ],
  },
  en: {
    eyebrow: "Please wait",
    title: "Your saju reading is in progress.",
    note: "This may take a little time.",
    benefitsTitle: "Why this reading is useful",
    benefits: [
      "It checks the manse data before writing the interpretation.",
      "It shows both strengths and weak points.",
      "It organizes the result by topic so it is easier to read.",
    ],
    slides: [
      {
        label: "Accurate first",
        title: "We calculate the manse data first to read your chart more accurately",
        body: "Your birth date, time, and region are used to calculate the chart structure before the explanation is written. That helps the reading stay closer to the actual chart.",
      },
      {
        label: "As it is",
        title: "It looks at both strong points and weak points",
        body: "This reading is not designed to sound flattering at all costs. It tries to show what is strong, what is unstable, and what needs care in a clearer way.",
      },
      {
        label: "Easy to read",
        title: "The result is organized into clear sections",
        body: "Your core traits, love, career, wealth, and luck flow are separated into readable sections. That makes it easier to find what matters first.",
      },
      {
        label: "Engine first",
        title: "The engine calculates and the reading explains",
        body: "The backend structures the pillars, luck cycles, and star data first. Then the interpretation layer turns those facts into language that is easier to read.",
      },
    ],
  },
};

type SajuLoadingViewProps = {
  locale: Locale;
};

export function SajuLoadingView({ locale }: SajuLoadingViewProps) {
  const content = loadingSlidesByLocale[locale];
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveIndex((currentIndex) => (currentIndex + 1) % content.slides.length);
    }, 3200);

    return () => window.clearInterval(timer);
  }, [content.slides.length]);

  const activeSlide = content.slides[activeIndex];

  return (
    <section className="loading-view" aria-live="polite" aria-busy="true">
      <div className="loading-status-card">
        <div className="loading-status">
          <span className="loading-status-indicator" aria-hidden="true" />
          <div className="loading-status-copy">
            <p className="loading-status-eyebrow">{content.eyebrow}</p>
            <h2>{content.title}</h2>
            <p className="loading-status-note">{content.note}</p>
          </div>
        </div>
      </div>

      <div className="loading-content-grid">
        <article className="loading-slide-card" key={`${locale}-${activeIndex}`}>
          <span className="loading-slide-label">{activeSlide.label}</span>
          <div className="loading-slide">
            <h3>{activeSlide.title}</h3>
            <p>{activeSlide.body}</p>
          </div>

          <div className="loading-slide-dots" aria-hidden="true">
            {content.slides.map((slide, index) => (
              <span
                key={slide.title}
                className={`loading-slide-dot${index === activeIndex ? " active" : ""}`}
              />
            ))}
          </div>
        </article>

        <section className="loading-benefits-card">
          <span className="loading-slide-label">{content.benefitsTitle}</span>
          <ul className="loading-benefits-list">
            {content.benefits.map((benefit) => (
              <li key={benefit}>{benefit}</li>
            ))}
          </ul>
        </section>
      </div>
    </section>
  );
}
