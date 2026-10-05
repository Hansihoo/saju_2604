import { useEffect, useState } from "react";

import { StickerPage } from "./features/character/StickerPage";
import { useDokkaebiPreference } from "./features/character/useDokkaebiPreference";
import { DesignLabPage } from "./features/design-lab/DesignLabPage";
import { DeveloperPage } from "./features/dev/DeveloperPage";
import { ServicePage } from "./features/service/ServicePage";
import { ApiHealth, SajuPreviewResponse } from "./shared/api/contracts";
import { getApiHealth } from "./shared/api/saju";
import { Locale } from "./shared/copy";
import { Mode, getMode, getModePath } from "./shared/navigation";

export default function App() {
  const [locale, setLocale] = useState<Locale>("ko");
  const [mode, setMode] = useState<Mode>(() => getMode(window.location.pathname));
  const [apiHealth, setApiHealth] = useState<ApiHealth | null>(null);
  const [result, setResult] = useState<SajuPreviewResponse | null>(null);
  const { expression, setExpression } = useDokkaebiPreference();

  useEffect(() => {
    const onPopState = () => setMode(getMode(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    void getApiHealth().then(setApiHealth).catch(() => setApiHealth(null));
  }, []);

  function navigate(nextMode: Mode) {
    window.history.pushState({}, "", getModePath(nextMode));
    setMode(nextMode);
    window.scrollTo(0, 0);
  }

  const pageShellClassName = [
    "page-shell",
    mode === "dev" ? "dev-page" : "",
    mode === "design" ? "design-page-shell" : "",
    mode === "stickers" ? "sticker-page-shell" : "",
    mode === "service" ? "dokkaebi-page-shell" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={pageShellClassName}>
      {mode === "dev" ? (
        <DeveloperPage
          locale={locale}
          onLocaleChange={setLocale}
          apiHealth={apiHealth}
          result={result}
          onResultChange={setResult}
          onNavigateToService={() => navigate("service")}
        />
      ) : mode === "design" ? (
        <DesignLabPage
          onNavigateToService={() => navigate("service")}
        />
      ) : (
        <>
          <div hidden={mode === "stickers"}>
            <ServicePage
              locale={locale}
              onLocaleChange={setLocale}
              result={result}
              onResultChange={setResult}
              expression={expression}
              onExpressionChange={setExpression}
              onChooseExpression={() => navigate("stickers")}
            />
          </div>
          {mode === "stickers" ? (
            <StickerPage
              locale={locale}
              expression={expression}
              onExpressionChange={setExpression}
              onNavigateToService={() => navigate("service")}
            />
          ) : null}
        </>
      )}
    </div>
  );
}
