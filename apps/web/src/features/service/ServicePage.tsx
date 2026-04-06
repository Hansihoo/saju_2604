import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

import { RegionSuggestion, SajuPreviewResponse } from "../../shared/api/contracts";
import { createSajuPreview, searchRegionSuggestions } from "../../shared/api/saju";
import { Locale, getCopy } from "../../shared/copy";
import { ServiceHeader } from "./components/ServiceHeader";
import { SajuForm } from "./components/SajuForm";
import { SajuResultView } from "./components/SajuResultView";

type ServicePageProps = {
  locale: Locale;
  onLocaleChange: (locale: Locale) => void;
  result: SajuPreviewResponse | null;
  onResultChange: (result: SajuPreviewResponse | null) => void;
};

export function ServicePage({
  locale,
  onLocaleChange,
  result,
  onResultChange,
}: ServicePageProps) {
  const [birthDate, setBirthDate] = useState("1994-10-13");
  const [birthTime, setBirthTime] = useState("08:30");
  const [isBirthTimeEstimated, setIsBirthTimeEstimated] = useState(false);
  const [regionQuery, setRegionQuery] = useState("");
  const [selectedRegion, setSelectedRegion] = useState<RegionSuggestion | null>(null);
  const [regionOptions, setRegionOptions] = useState<RegionSuggestion[]>([]);
  const [highlightedRegionIndex, setHighlightedRegionIndex] = useState(-1);
  const [isRegionFocused, setIsRegionFocused] = useState(false);
  const [regionLoading, setRegionLoading] = useState(false);
  const [gender, setGender] = useState<"male" | "female">("female");
  const [calendarType, setCalendarType] = useState<"solar" | "lunar">("solar");
  const [isLunarLeapMonth, setIsLunarLeapMonth] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const texts = getCopy(locale);
  const regionBoxRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isRegionFocused || selectedRegion || regionQuery.trim().length === 0) {
      setRegionOptions([]);
      setHighlightedRegionIndex(-1);
      return;
    }

    const timeoutId = window.setTimeout(async () => {
      setRegionLoading(true);
      try {
        const items = await searchRegionSuggestions(regionQuery.trim());
        setRegionOptions(items);
        setHighlightedRegionIndex(items.length > 0 ? 0 : -1);
      } catch (_error) {
        setRegionOptions([]);
        setHighlightedRegionIndex(-1);
      } finally {
        setRegionLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [isRegionFocused, regionQuery, selectedRegion]);

  useEffect(() => {
    function handleDocumentClick(event: MouseEvent) {
      if (!regionBoxRef.current?.contains(event.target as Node)) {
        setIsRegionFocused(false);
      }
    }

    document.addEventListener("mousedown", handleDocumentClick);
    return () => document.removeEventListener("mousedown", handleDocumentClick);
  }, []);

  function handleUnknownTimeChange(checked: boolean) {
    setIsBirthTimeEstimated(checked);
    if (checked) {
      setBirthTime("00:00");
    }
  }

  function handleRegionSelect(region: RegionSuggestion) {
    setSelectedRegion(region);
    setRegionQuery(region.display_name);
    setRegionOptions([]);
    setHighlightedRegionIndex(-1);
    setIsRegionFocused(false);
    setError(null);
  }

  function handleRegionInputChange(value: string) {
    setRegionQuery(value);
    setSelectedRegion(null);
    setIsRegionFocused(true);
    setError(null);
  }

  function handleRegionInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setIsRegionFocused(false);
      setHighlightedRegionIndex(-1);
      return;
    }

    if (!regionOptions.length) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedRegionIndex((current) => (current + 1) % regionOptions.length);
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedRegionIndex((current) =>
        current <= 0 ? regionOptions.length - 1 : current - 1,
      );
    }

    if (event.key === "Enter" && highlightedRegionIndex >= 0) {
      event.preventDefault();
      handleRegionSelect(regionOptions[highlightedRegionIndex]);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedRegion) {
      setError(texts.regionRequired);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await createSajuPreview(
        {
          calendar_type: calendarType,
          birth_date: birthDate,
          birth_time: birthTime,
          is_birth_time_estimated: isBirthTimeEstimated,
          is_lunar_leap_month: isLunarLeapMonth,
          gender,
          region_id: selectedRegion.id,
          debug: false,
        },
        false,
      );
      onResultChange(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : texts.noResult);
      onResultChange(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="service-page">
      <ServiceHeader
        title={texts.title}
        subtitle={texts.subtitle}
        locale={locale}
        languageLabel={texts.language}
        onLocaleChange={onLocaleChange}
      />

      {result ? (
        <SajuResultView locale={locale} result={result} onReset={() => onResultChange(null)} />
      ) : (
        <SajuForm
          locale={locale}
          birthDate={birthDate}
          birthTime={birthTime}
          isBirthTimeEstimated={isBirthTimeEstimated}
          regionQuery={regionQuery}
          regionOptions={regionOptions}
          highlightedRegionIndex={highlightedRegionIndex}
          isRegionFocused={isRegionFocused}
          regionLoading={regionLoading}
          gender={gender}
          calendarType={calendarType}
          isLunarLeapMonth={isLunarLeapMonth}
          loading={loading}
          error={error}
          regionBoxRef={regionBoxRef}
          onSubmit={handleSubmit}
          onBirthDateChange={setBirthDate}
          onBirthTimeChange={setBirthTime}
          onUnknownTimeChange={handleUnknownTimeChange}
          onRegionFocus={() => setIsRegionFocused(true)}
          onRegionInputChange={handleRegionInputChange}
          onRegionInputKeyDown={handleRegionInputKeyDown}
          onRegionSelect={handleRegionSelect}
          onGenderChange={setGender}
          onCalendarTypeChange={setCalendarType}
          onLeapMonthChange={setIsLunarLeapMonth}
        />
      )}
    </main>
  );
}
