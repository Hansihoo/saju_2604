import { currentResultFixture, type DesignArticle, type DesignFixture } from "./currentResultFixture";

type DesignLabPageProps = {
  onNavigateToService: () => void;
};

const toneLabel: Record<DesignArticle["tone"], string> = {
  core: "성향",
  work: "일과 돈",
  love: "관계",
  flow: "운의 흐름",
};

export function DesignLabPage({ onNavigateToService }: DesignLabPageProps) {
  return (
    <main className="design-lab document-lab">
      <header className="design-lab-header document-lab-header">
        <div>
          <span className="design-lab-mark">DOCUMENT STUDY</span>
          <h1>문서형 결과지 시안</h1>
          <p>현재 결과값을 다시 생성하지 않고, 읽히는 리포트 형태만 비교합니다.</p>
        </div>
        <button className="design-ghost-button" type="button" onClick={onNavigateToService}>
          서비스로 돌아가기
        </button>
      </header>

      <section className="document-study">
        <VariantTitle
          eyebrow="Draft A"
          title="프리미엄 리포트"
          description="상담사가 정리해준 분석지처럼 표지, 요약, 본문 근거가 차례로 이어지는 방향입니다."
        />
        <PremiumReport data={currentResultFixture} />
      </section>

      <section className="document-study">
        <VariantTitle
          eyebrow="Draft B"
          title="에세이형 해석문"
          description="숫자와 패널을 줄이고 문장 중심으로 신뢰감 있게 읽히는 방향입니다."
        />
        <EssayReport data={currentResultFixture} />
      </section>

      <section className="document-study">
        <VariantTitle
          eyebrow="Draft C"
          title="인쇄용 요약지"
          description="한 페이지 안에서 핵심, 근거, 다음 행동을 빠르게 훑는 PDF형 결과지 방향입니다."
        />
        <BriefReport data={currentResultFixture} />
      </section>
    </main>
  );
}

function VariantTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="document-study-title">
      <span>{eyebrow}</span>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}

function PremiumReport({ data }: { data: DesignFixture }) {
  return (
    <article className="report-paper premium-report" aria-label="프리미엄 리포트 시안">
      <header className="report-cover">
        <div>
          <span className="report-kicker">Saju Insight Report</span>
          <h3>{data.headline}</h3>
          <p>{data.overview[0]}</p>
        </div>
        <dl className="report-meta">
          <div>
            <dt>사주 원국</dt>
            <dd>{data.pillars.join(" · ")}</dd>
          </div>
          <div>
            <dt>확인 기준</dt>
            <dd>{data.badges.join(" / ")}</dd>
          </div>
        </dl>
      </header>

      <section className="report-summary-band">
        {data.diagnoses.map((item) => (
          <div className={`report-note is-${item.tone}`} key={item.title}>
            <span>{item.title}</span>
            <p>{item.body}</p>
          </div>
        ))}
      </section>

      <section className="report-body-grid">
        {data.articles.map((article) => (
          <ArticleSection article={article} key={article.title} />
        ))}
      </section>
    </article>
  );
}

function EssayReport({ data }: { data: DesignFixture }) {
  return (
    <article className="report-paper essay-report" aria-label="에세이형 해석문 시안">
      <aside className="essay-margin">
        <span>읽기 순서</span>
        <ol>
          <li>첫인상</li>
          <li>반복 패턴</li>
          <li>관계와 일</li>
          <li>현재 흐름</li>
        </ol>
      </aside>
      <div className="essay-content">
        <span className="report-kicker">{data.pillars.join(" / ")}</span>
        <h3>{data.headline}</h3>
        <p className="essay-lead">{data.overview[1]}</p>
        {data.articles.map((article) => (
          <section className={`essay-section is-${article.tone}`} key={article.title}>
            <span>{toneLabel[article.tone]}</span>
            <h4>{article.title}</h4>
            {article.body.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
            <blockquote>{article.takeaway}</blockquote>
          </section>
        ))}
      </div>
    </article>
  );
}

function BriefReport({ data }: { data: DesignFixture }) {
  return (
    <article className="report-paper brief-report" aria-label="인쇄용 요약지 시안">
      <header className="brief-header">
        <div>
          <span className="report-kicker">One Page Reading</span>
          <h3>{data.headline}</h3>
        </div>
        <strong>{data.pillars.join(" · ")}</strong>
      </header>

      <section className="brief-columns">
        <div className="brief-main">
          <h4>핵심 해석</h4>
          <p>{data.overview[2]}</p>
          <div className="brief-questions">
            {data.articles.slice(0, 3).map((article) => (
              <p key={article.title}>{article.question}</p>
            ))}
          </div>
        </div>
        <div className="brief-side">
          <h4>이번 결과의 키워드</h4>
          <ul>
            {data.articles.flatMap((article) => article.chips.slice(0, 2)).map((chip) => (
              <li key={chip}>{chip}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="brief-timeline">
        {data.timeline.map((item) => (
          <div className={item.active ? "is-active" : ""} key={item.label}>
            <span>{item.label}</span>
            <strong>{item.period}</strong>
            <p>{item.note}</p>
          </div>
        ))}
      </section>
    </article>
  );
}

function ArticleSection({ article }: { article: DesignArticle }) {
  return (
    <section className={`report-section is-${article.tone}`}>
      <span>{toneLabel[article.tone]}</span>
      <h4>{article.title}</h4>
      <p>{article.subtitle}</p>
      <ul>
        {article.chips.map((chip) => (
          <li key={chip}>{chip}</li>
        ))}
      </ul>
      <small>{article.takeaway}</small>
    </section>
  );
}
