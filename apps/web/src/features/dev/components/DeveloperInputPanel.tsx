import { FormEvent } from "react";

import { AccuracyMode } from "../../../shared/api/contracts";
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
  const accuracyModeOptions: Array<{ value: AccuracyMode; label: string }> = [
    { value: "legacy", label: "Legacy" },
    { value: "standard_time", label: "Standard time" },
    { value: "mean_solar_time", label: "Mean solar time" },
    { value: "compare", label: "Compare" },
  ];

  return (
    <section className="dev-section dev-input-panel">
      <h2>{text.inputTitle}</h2>
      <p>{text.inputLead}</p>
      <div className="form-field dev-accuracy-field">
        <label htmlFor="accuracy-mode">Accuracy mode</label>
        <select
          id="accuracy-mode"
          value={form.accuracyMode}
          onChange={(event) => form.setAccuracyMode(event.target.value as AccuracyMode)}
        >
          {accuracyModeOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
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
