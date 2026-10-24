import { useEffect, useState } from "react";
import type { Locale } from "../../shared/copy";
import type { PreviewStage } from "../../shared/api/previewProgress";
import { DokkaebiWaiting } from "../service/experience/DokkaebiWaiting";
import "../service/experience/experience.css";

// Explicit synthetic states, accessible only through the development design lab.
// No birth inputs, backend jobs or model requests are made by this preview.
export function WaitingPreview({ onExit }: { onExit: () => void }) {
  const [stage, setStage] = useState<PreviewStage>("writing");
  const [locale, setLocale] = useState<Locale>("ko");
  const [elapsed, setElapsed] = useState(65);
  const [connected, setConnected] = useState(true);
  const [signalAt, setSignalAt] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setSignalAt(Date.now()), 10_000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <div className="dk-experience">
      <header style={{ padding: 16, display: "flex", flexWrap: "wrap", gap: 12 }}>
        <strong>대기 화면 검토 · 합성 상태</strong>
        <button onClick={onExit}>서비스로 돌아가기</button>
        <label>단계 <select value={stage} onChange={(event) => setStage(event.target.value as PreviewStage)}>
          <option value="sending">정보 보내는 중</option><option value="accepted">정보 접수</option>
          <option value="calculating">사주 계산</option><option value="writing">풀이 정리</option>
          <option value="waiting">기존 API 대기</option>
        </select></label>
        <label>언어 <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
          <option value="ko">KO</option><option value="en">EN</option>
        </select></label>
        <label>경과 시간 <select value={elapsed} onChange={(event) => setElapsed(Number(event.target.value))}>
          <option value={0}>0초</option><option value={65}>1분 5초</option><option value={185}>3분 5초</option>
        </select></label>
        <label><input type="checkbox" checked={connected} onChange={(event) => setConnected(event.target.checked)} />연결 응답 있음</label>
      </header>
      <main className="dk-main">
        <DokkaebiWaiting key={elapsed} locale={locale} previewElapsedSeconds={elapsed}
          progress={{ stage, transport: stage === "waiting" ? "legacy" : "stream",
            lastSignalAt: stage === "sending" || stage === "waiting" ? null : connected ? signalAt : signalAt - 40_000 }} />
      </main>
    </div>
  );
}
