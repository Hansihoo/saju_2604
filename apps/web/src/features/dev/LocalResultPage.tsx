import { useEffect, useState } from "react";
import type { SajuPreviewRequest, SajuPreviewResponse } from "../../shared/api/contracts";
import type { DokkaebiExpression } from "../character/dokkaebiCatalog";
import { DokkaebiPicker } from "../character/DokkaebiPicker";
import { ServicePage } from "../service/ServicePage";
import { hasQuestionFlow } from "../service/experience/questionModel";
import type { Locale } from "../../shared/copy";

type Snapshot = {
  format: "local-result-snapshot-v1";
  input: SajuPreviewRequest;
  result: SajuPreviewResponse;
};

type Props = {
  id: string;
  expression: DokkaebiExpression;
  onExpressionChange: (expression: DokkaebiExpression) => void;
};

export default function LocalResultPage({ id, expression, onExpressionChange }: Props) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [result, setResult] = useState<SajuPreviewResponse | null>(null);
  const [locale, setLocale] = useState<Locale>("ko");
  const [error, setError] = useState(false);
  const [choosingExpression, setChoosingExpression] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void fetch(`/__local-results/${id}.json`, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unavailable result");
        const data = await response.json() as Snapshot;
        if (data.format !== "local-result-snapshot-v1" || !data.input ||
            !["ko", "en"].includes(data.input.locale) || !data.result || !hasQuestionFlow(data.result))
          throw new Error("Invalid result");
        if (!controller.signal.aborted) {
          setSnapshot(data);
          setResult(data.result);
          setLocale(data.input.locale);
        }
      })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [id]);

  if (error) return <main className="dk-main"><h1>결과를 찾을 수 없어.</h1><p>임시 결과 파일이 있는지 확인해줘.</p><a href="/">처음으로</a></main>;
  if (!snapshot) return <main className="dk-main"><p role="status">저장한 결과를 열고 있어.</p></main>;
  return <>
    {choosingExpression ? <section className="dk-main">
      <DokkaebiPicker locale={locale} expression={expression} onChange={(next) => {
        onExpressionChange(next);
        setChoosingExpression(false);
      }} />
      <button className="dk-text-button" onClick={() => setChoosingExpression(false)}>결과로 돌아가기</button>
    </section> : null}
    <div hidden={choosingExpression}><ServicePage
    locale={locale} onLocaleChange={setLocale} result={result} onResultChange={setResult}
    restoredInput={snapshot.input} expression={expression} onExpressionChange={onExpressionChange}
    onChooseExpression={() => setChoosingExpression(true)}
  /></div></>;
}
