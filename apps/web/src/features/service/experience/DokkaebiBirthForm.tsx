import { type FormEvent, useRef, useState } from "react";
import type { Locale } from "../../../shared/copy";
import type { useSajuInputForm } from "../../shared/useSajuInputForm";
import { DokkaebiSticker } from "../../character/DokkaebiSticker";
import {
  experienceCopy,
  experienceExpressions,
  readingTopics,
  type ReadingTopicKey,
} from "./experienceCopy";
import { isValidBirthDate } from "./validateBirthDate";

type InputController = ReturnType<typeof useSajuInputForm>;

export function DokkaebiBirthForm({
  locale,
  step,
  form,
  topicKey,
  onNext,
}: {
  locale: Locale;
  step: "birth" | "time";
  form: InputController;
  topicKey: ReadingTopicKey;
  onNext: () => void;
}) {
  const copy = experienceCopy[locale];
  const topic = readingTopics.find((item) => item.key === topicKey)!;
  const [stepError, setStepError] = useState<string | null>(null);
  const dateRef = useRef<HTMLInputElement>(null);
  const timeRef = useRef<HTMLInputElement>(null);
  const regionRef = useRef<HTMLInputElement>(null);
  const error = stepError ?? form.error;
  const showSuggestions =
    form.isRegionFocused &&
    !form.selectedRegion &&
    Boolean(form.regionQuery.trim());

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStepError(null);
    if (!isValidBirthDate(form.birthDate, form.calendarType)) {
      setStepError(copy.dateError);
      dateRef.current?.focus();
      return;
    }
    if (step === "birth") {
      onNext();
      return;
    }
    if (
      !form.isBirthTimeEstimated &&
      !/^([01]\d|2[0-3]):[0-5]\d$/.test(form.birthTime)
    ) {
      setStepError(copy.timeError);
      timeRef.current?.focus();
      return;
    } else if (!form.selectedRegion) {
      setStepError(copy.regionError);
      regionRef.current?.focus();
      return;
    }
    await form.submit();
  }

  return (
    <section className="dk-form-screen">
      <div
        className="dk-stepper"
        aria-label={
          locale === "ko"
            ? `2단계 중 ${step === "birth" ? "1" : "2"}단계`
            : `Step ${step === "birth" ? "1" : "2"} of 2`
        }
      >
        <span className="is-complete" />
        <span className={step === "time" ? "is-complete" : ""} />
        <b>{step === "birth" ? "01" : "02"} / 02</b>
      </div>
      <div className="dk-form-heading">
        <div>
          <span className="dk-selected-topic">{topic.label[locale]}</span>
          <h1>{step === "birth" ? copy.birthTitle : copy.timeTitle}</h1>
        </div>
        <DokkaebiSticker
          expression={experienceExpressions[step]}
          size={88}
          decorative
        />
      </div>
      <form className="dk-form" onSubmit={handleSubmit} noValidate>
        <div hidden={step !== "birth"}>
          <div className="dk-field">
            <label htmlFor="dk-birth-date">{copy.birthDate}</label>
            <input
              id="dk-birth-date"
              ref={dateRef}
              inputMode="numeric"
              autoComplete="bday"
              placeholder="1997-09-18"
              maxLength={10}
              value={form.birthDate}
              onChange={(e) => {
                setStepError(null);
                form.setBirthDate(e.target.value);
              }}
              aria-invalid={stepError === copy.dateError}
              aria-describedby={stepError ? "dk-input-error" : undefined}
            />
          </div>
          <fieldset className="dk-field">
            <legend>{copy.calendar}</legend>
            <div className="dk-segments">
              {(["solar", "lunar"] as const).map((value) => (
                <label key={value}>
                  <input
                    type="radio"
                    name="dk-calendar"
                    checked={form.calendarType === value}
                    onChange={() => {
                      form.setCalendarType(value);
                      if (value === "solar") form.setIsLunarLeapMonth(false);
                    }}
                  />
                  <span>{copy[value]}</span>
                </label>
              ))}
            </div>
            {form.calendarType === "lunar" ? (
              <label className="dk-check">
                <input
                  type="checkbox"
                  checked={form.isLunarLeapMonth}
                  onChange={(e) => form.setIsLunarLeapMonth(e.target.checked)}
                />
                <span>{copy.leap}</span>
              </label>
            ) : null}
          </fieldset>
          <fieldset className="dk-field">
            <legend>{copy.gender}</legend>
            <div className="dk-segments">
              {(["female", "male"] as const).map((value) => (
                <label key={value}>
                  <input
                    type="radio"
                    name="dk-gender"
                    checked={form.gender === value}
                    onChange={() => form.setGender(value)}
                  />
                  <span>{copy[value]}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </div>
        <div hidden={step !== "time"}>
          <div className="dk-field">
            <label htmlFor="dk-birth-time">{copy.birthTime}</label>
            <input
              id="dk-birth-time"
              ref={timeRef}
              inputMode="numeric"
              autoComplete="off"
              placeholder="14:30"
              maxLength={5}
              value={form.isBirthTimeEstimated ? "" : form.birthTime}
              disabled={form.isBirthTimeEstimated}
              aria-invalid={stepError === copy.timeError}
              aria-describedby={stepError ? "dk-input-error" : undefined}
              onChange={(e) => {
                setStepError(null);
                form.setBirthTime(e.target.value);
              }}
            />
            <label className="dk-check">
              <input
                type="checkbox"
                checked={form.isBirthTimeEstimated}
                onChange={(e) => {
                  setStepError(null);
                  form.handleUnknownTimeChange(e.target.checked);
                }}
              />
              <span>{copy.unknown}</span>
            </label>
            {form.isBirthTimeEstimated ? (
              <p className="dk-unknown-note">{copy.unknownNote}</p>
            ) : null}
          </div>
          <div className="dk-field dk-region-field" ref={form.regionBoxRef}>
            <label htmlFor="dk-birth-region">{copy.region}</label>
            <input
              id="dk-birth-region"
              ref={regionRef}
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={showSuggestions}
              aria-controls={showSuggestions ? "dk-region-options" : undefined}
              aria-activedescendant={
                showSuggestions &&
                form.highlightedRegionIndex >= 0 &&
                form.regionOptions[form.highlightedRegionIndex]
                  ? `dk-region-${form.highlightedRegionIndex}`
                  : undefined
              }
              autoComplete="off"
              placeholder={copy.regionPlaceholder}
              value={form.regionQuery}
              aria-describedby={`dk-region-note${form.selectedRegion ? " dk-region-selected" : ""}${stepError ? " dk-input-error" : ""}`}
              aria-invalid={stepError === copy.regionError}
              onFocus={() => form.setIsRegionFocused(true)}
              onKeyDown={form.handleRegionInputKeyDown}
              onChange={(e) => {
                setStepError(null);
                form.handleRegionInputChange(e.target.value);
              }}
            />
            <p className="dk-region-note" id="dk-region-note">
              {copy.regionNote}
            </p>
            {showSuggestions ? (
              <div
                className="dk-region-options"
                id="dk-region-options"
                role="listbox"
                aria-label={copy.region}
              >
                {form.regionLoading ? (
                  <p role="status">{copy.searching}</p>
                ) : form.regionOptions.length ? (
                  form.regionOptions.map((item, index) => (
                    <button
                      id={`dk-region-${index}`}
                      role="option"
                      aria-selected={index === form.highlightedRegionIndex}
                      type="button"
                      key={item.id}
                      tabIndex={-1}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => form.handleRegionSelect(item)}
                    >
                      {item.display_name}
                      <span aria-hidden="true">↗</span>
                    </button>
                  ))
                ) : (
                  <p>{copy.noRegions}</p>
                )}
              </div>
            ) : null}
            {form.selectedRegion ? (
              <>
                <span className="dk-region-confirmed" aria-hidden="true">
                  ✓
                </span>
                <span
                  className="dk-sr-only"
                  id="dk-region-selected"
                  role="status"
                >
                  {copy.selectedRegion}: {form.selectedRegion.display_name}
                </span>
              </>
            ) : null}
          </div>
        </div>
        {error ? (
          <div className="dk-form-error" id="dk-input-error" role="alert">
            <DokkaebiSticker
              expression={experienceExpressions.error}
              decorative
              size={48}
            />
            <div>
              <strong>{copy.retry}</strong>
              <p>{error}</p>
            </div>
          </div>
        ) : null}
        <button className="dk-primary" type="submit" disabled={form.loading}>
          {step === "birth"
            ? copy.next
            : locale === "ko"
              ? `${topic.label[locale]} 보기`
              : `${copy.submit} · ${topic.label[locale]}`}
          <span aria-hidden="true">→</span>
        </button>
      </form>
    </section>
  );
}
