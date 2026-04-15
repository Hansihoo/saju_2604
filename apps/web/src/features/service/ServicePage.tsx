import { FormEvent } from "react";

import { SajuPreviewResponse } from "../../shared/api/contracts";
import { Locale, getCopy } from "../../shared/copy";
import { useSajuInputForm } from "../shared/useSajuInputForm";
import { ServiceHeader } from "./components/ServiceHeader";
import { SajuForm } from "./components/SajuForm";
import { SajuLoadingView } from "./components/SajuLoadingView";
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
  const texts = getCopy(locale);
  const form = useSajuInputForm({
    locale,
    debug: false,
    onSuccess: onResultChange,
    onErrorResult: () => onResultChange(null),
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await form.submit();
  }

  const isLoadingView = form.loading && !result;

  return (
    <main
      className={`service-page${result ? " result-mode" : ""}${isLoadingView ? " loading-mode" : ""}`}
    >
      <ServiceHeader
        title={texts.title}
        subtitle={texts.subtitle}
        locale={locale}
        languageLabel={texts.language}
        onLocaleChange={onLocaleChange}
      />

      {result ? (
        <SajuResultView locale={locale} result={result} onReset={() => onResultChange(null)} />
      ) : isLoadingView ? (
        <SajuLoadingView locale={locale} />
      ) : (
        <SajuForm
          locale={locale}
          birthDate={form.birthDate}
          birthTime={form.birthTime}
          isBirthTimeEstimated={form.isBirthTimeEstimated}
          regionQuery={form.regionQuery}
          regionOptions={form.regionOptions}
          highlightedRegionIndex={form.highlightedRegionIndex}
          isRegionFocused={form.isRegionFocused}
          regionLoading={form.regionLoading}
          gender={form.gender}
          calendarType={form.calendarType}
          isLunarLeapMonth={form.isLunarLeapMonth}
          loading={form.loading}
          error={form.error}
          regionBoxRef={form.regionBoxRef}
          onSubmit={handleSubmit}
          onBirthDateChange={form.setBirthDate}
          onBirthTimeChange={form.setBirthTime}
          onUnknownTimeChange={form.handleUnknownTimeChange}
          onRegionFocus={() => form.setIsRegionFocused(true)}
          onRegionInputChange={form.handleRegionInputChange}
          onRegionInputKeyDown={form.handleRegionInputKeyDown}
          onRegionSelect={form.handleRegionSelect}
          onGenderChange={form.setGender}
          onCalendarTypeChange={form.setCalendarType}
          onLeapMonthChange={form.setIsLunarLeapMonth}
        />
      )}
    </main>
  );
}
