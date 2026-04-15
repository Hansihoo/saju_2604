import { FormEvent } from "react";

import { Locale } from "../../../shared/copy";
import { SajuForm } from "../../service/components/SajuForm";
import { getDevCopy } from "../devCopy";
import { useSajuInputForm } from "../../shared/useSajuInputForm";

type DeveloperInputPanelProps = {
  locale: Locale;
  form: ReturnType<typeof useSajuInputForm>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function DeveloperInputPanel({ locale, form, onSubmit }: DeveloperInputPanelProps) {
  const text = getDevCopy(locale);

  return (
    <section className="dev-section dev-input-panel">
      <h2>{text.inputTitle}</h2>
      <p>{text.inputLead}</p>
      <SajuForm
        className="service-form dev-form"
        locale={locale}
        submitLabel={text.submit}
        loadingLabel={text.loading}
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
        onSubmit={onSubmit}
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
    </section>
  );
}
