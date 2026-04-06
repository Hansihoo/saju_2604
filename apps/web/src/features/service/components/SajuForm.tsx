import { FormEvent, KeyboardEvent, RefObject } from "react";

import { RegionSuggestion } from "../../../shared/api/contracts";
import { Locale, getCopy } from "../../../shared/copy";

type SajuFormProps = {
  locale: Locale;
  birthDate: string;
  birthTime: string;
  isBirthTimeEstimated: boolean;
  regionQuery: string;
  regionOptions: RegionSuggestion[];
  highlightedRegionIndex: number;
  isRegionFocused: boolean;
  regionLoading: boolean;
  gender: "male" | "female";
  calendarType: "solar" | "lunar";
  isLunarLeapMonth: boolean;
  loading: boolean;
  error: string | null;
  regionBoxRef: RefObject<HTMLDivElement>;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onBirthDateChange: (value: string) => void;
  onBirthTimeChange: (value: string) => void;
  onUnknownTimeChange: (checked: boolean) => void;
  onRegionFocus: () => void;
  onRegionInputChange: (value: string) => void;
  onRegionInputKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onRegionSelect: (region: RegionSuggestion) => void;
  onGenderChange: (value: "male" | "female") => void;
  onCalendarTypeChange: (value: "solar" | "lunar") => void;
  onLeapMonthChange: (checked: boolean) => void;
};

export function SajuForm({
  locale,
  birthDate,
  birthTime,
  isBirthTimeEstimated,
  regionQuery,
  regionOptions,
  highlightedRegionIndex,
  isRegionFocused,
  regionLoading,
  gender,
  calendarType,
  isLunarLeapMonth,
  loading,
  error,
  regionBoxRef,
  onSubmit,
  onBirthDateChange,
  onBirthTimeChange,
  onUnknownTimeChange,
  onRegionFocus,
  onRegionInputChange,
  onRegionInputKeyDown,
  onRegionSelect,
  onGenderChange,
  onCalendarTypeChange,
  onLeapMonthChange,
}: SajuFormProps) {
  const texts = getCopy(locale);
  const showRegionSuggestions = isRegionFocused && regionQuery.trim().length > 0;

  return (
    <form className="service-form" onSubmit={onSubmit}>
      <div className="form-field">
        <label htmlFor="birth-date">{texts.birthDate}</label>
        <input
          id="birth-date"
          type="date"
          value={birthDate}
          onChange={(event) => onBirthDateChange(event.target.value)}
        />
      </div>

      <div className="form-field">
        <label htmlFor="birth-time">{texts.birthTime}</label>
        <div className="time-field-row">
          <input
            id="birth-time"
            type="time"
            value={birthTime}
            disabled={isBirthTimeEstimated}
            onChange={(event) => onBirthTimeChange(event.target.value)}
          />
          <label className="inline-check">
            <input
              type="checkbox"
              checked={isBirthTimeEstimated}
              onChange={(event) => onUnknownTimeChange(event.target.checked)}
            />
            <span>{texts.unknownTime}</span>
          </label>
        </div>
      </div>

      <div className="form-field" ref={regionBoxRef}>
        <label htmlFor="birth-region">{texts.region}</label>
        <div className="region-input-shell">
          <input
            id="birth-region"
            type="text"
            autoComplete="off"
            value={regionQuery}
            placeholder={texts.regionPlaceholder}
            onFocus={onRegionFocus}
            onKeyDown={onRegionInputKeyDown}
            onChange={(event) => onRegionInputChange(event.target.value)}
          />
        </div>

        {showRegionSuggestions ? (
          <div className="autocomplete-list" role="listbox">
            {regionLoading ? (
              <div className="autocomplete-empty">Loading...</div>
            ) : regionOptions.length > 0 ? (
              regionOptions.map((item, index) => (
                <button
                  key={item.id}
                  type="button"
                  className={`autocomplete-item${highlightedRegionIndex === index ? " active" : ""}`}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    onRegionSelect(item);
                  }}
                >
                  {item.display_name}
                </button>
              ))
            ) : (
              <div className="autocomplete-empty">{texts.noSuggestions}</div>
            )}
          </div>
        ) : null}
      </div>

      <div className="form-field">
        <span className="field-legend">{texts.gender}</span>
        <div className="radio-group">
          <label className="radio-inline">
            <input
              type="radio"
              name="gender"
              checked={gender === "male"}
              onChange={() => onGenderChange("male")}
            />
            <span>{texts.male}</span>
          </label>
          <label className="radio-inline">
            <input
              type="radio"
              name="gender"
              checked={gender === "female"}
              onChange={() => onGenderChange("female")}
            />
            <span>{texts.female}</span>
          </label>
        </div>
      </div>

      <div className="form-field">
        <span className="field-legend">{texts.calendarType}</span>
        <div className="radio-group">
          <label className="radio-inline">
            <input
              type="radio"
              name="calendar-type"
              checked={calendarType === "solar"}
              onChange={() => onCalendarTypeChange("solar")}
            />
            <span>{texts.solar}</span>
          </label>
          <label className="radio-inline">
            <input
              type="radio"
              name="calendar-type"
              checked={calendarType === "lunar"}
              onChange={() => onCalendarTypeChange("lunar")}
            />
            <span>{texts.lunar}</span>
          </label>
        </div>
        {calendarType === "lunar" ? (
          <label className="inline-check subtle">
            <input
              type="checkbox"
              checked={isLunarLeapMonth}
              onChange={(event) => onLeapMonthChange(event.target.checked)}
            />
            <span>{texts.leapMonth}</span>
          </label>
        ) : null}
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      <button className="submit-button" type="submit" disabled={loading}>
        {loading ? texts.loading : texts.submit}
      </button>
    </form>
  );
}
