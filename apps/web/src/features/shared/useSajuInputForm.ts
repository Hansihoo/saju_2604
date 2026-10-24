import { KeyboardEvent, useEffect, useRef, useState } from "react";

import {
  AccuracyMode,
  RegionSuggestion,
  SajuPreviewRequest,
  SajuPreviewResponse,
} from "../../shared/api/contracts";
import { createSajuBasic, createSajuReading, createSajuPreview, searchRegionSuggestions } from "../../shared/api/saju";
import type { PreviewProgress } from "../../shared/api/previewProgress";
import { Locale, getCopy } from "../../shared/copy";

type UseSajuInputFormOptions = {
  locale: Locale;
  debug: boolean;
  progressive?: boolean;
  basicFirst?: boolean;
  readingFirst?: boolean;
  onSuccess: (result: SajuPreviewResponse) => void;
  onErrorResult?: () => void;
  initialValues?: Partial<{
    birthDate: string;
    birthTime: string;
    gender: "male" | "female";
    calendarType: "solar" | "lunar";
    accuracyMode: AccuracyMode;
  }>;
};

export function useSajuInputForm({
  locale,
  debug,
  progressive = false,
  basicFirst = false,
  readingFirst = false,
  onSuccess,
  onErrorResult,
  initialValues,
}: UseSajuInputFormOptions) {
  const texts = getCopy(locale);
  const [birthDate, setBirthDate] = useState(initialValues?.birthDate ?? "");
  const [birthTime, setBirthTime] = useState(initialValues?.birthTime ?? "");
  const [isBirthTimeEstimated, setIsBirthTimeEstimated] = useState(false);
  const [regionQuery, setRegionQuery] = useState("");
  const [selectedRegion, setSelectedRegion] = useState<RegionSuggestion | null>(null);
  const [regionOptions, setRegionOptions] = useState<RegionSuggestion[]>([]);
  const [highlightedRegionIndex, setHighlightedRegionIndex] = useState(-1);
  const [isRegionFocused, setIsRegionFocused] = useState(false);
  const [regionLoading, setRegionLoading] = useState(false);
  const [gender, setGender] = useState<"male" | "female">(initialValues?.gender ?? "female");
  const [calendarType, setCalendarType] = useState<"solar" | "lunar">(
    initialValues?.calendarType ?? "solar",
  );
  const [accuracyMode, setAccuracyMode] = useState<AccuracyMode>(
    initialValues?.accuracyMode ?? "legacy",
  );
  const [isLunarLeapMonth, setIsLunarLeapMonth] = useState(false);
  const [lastSubmittedPayload, setLastSubmittedPayload] = useState<SajuPreviewRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<PreviewProgress>({ stage: "sending", lastSignalAt: null, transport: "stream" });
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => () => { requestRef.current?.abort(); }, []);

  const regionBoxRef = useRef<HTMLDivElement | null>(null);
  const knownBirthTimeRef = useRef(initialValues?.birthTime ?? "");

  function formatBirthDateInput(value: string) {
    const digits = value.replace(/\D/g, "").slice(0, 8);
    if (digits.length <= 4) {
      return digits;
    }
    if (digits.length <= 6) {
      return `${digits.slice(0, 4)}-${digits.slice(4)}`;
    }
    return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6)}`;
  }

  function formatBirthTimeInput(value: string) {
    const digits = value.replace(/\D/g, "").slice(0, 4);
    if (digits.length <= 2) {
      return digits;
    }
    return `${digits.slice(0, 2)}:${digits.slice(2)}`;
  }

  function handleBirthDateChange(value: string) {
    setBirthDate(formatBirthDateInput(value));
    setError(null);
  }

  function handleBirthTimeChange(value: string) {
    setBirthTime(formatBirthTimeInput(value));
    setError(null);
  }

  useEffect(() => {
    let cancelled = false;
    setRegionOptions([]);
    setHighlightedRegionIndex(-1);
    if (!isRegionFocused || selectedRegion || regionQuery.trim().length === 0) {
      setRegionLoading(false);
      return;
    }

    setRegionLoading(true);
    const timeoutId = window.setTimeout(async () => {
      try {
        const items = await searchRegionSuggestions(regionQuery.trim());
        if (cancelled) return;
        setRegionOptions(items);
        setHighlightedRegionIndex(items.length > 0 ? 0 : -1);
      } catch (_error) {
        if (!cancelled) { setRegionOptions([]); setHighlightedRegionIndex(-1); }
      } finally {
        if (!cancelled) setRegionLoading(false);
      }
    }, 250);

    return () => { cancelled = true; window.clearTimeout(timeoutId); };
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
      knownBirthTimeRef.current = birthTime;
      setBirthTime("00:00");
    } else {
      setBirthTime(knownBirthTimeRef.current);
    }
    setError(null);
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

  async function submit() {
    if (requestRef.current) return;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(birthDate)) {
      setError(texts.birthDateInvalid);
      return;
    }

    if (!isBirthTimeEstimated && !/^\d{2}:\d{2}$/.test(birthTime)) {
      setError(texts.birthTimeInvalid);
      return;
    }

    if (!selectedRegion) {
      setError(texts.regionRequired);
      return;
    }

    setLoading(true);
    setError(null);
    setProgress({ stage: "sending", lastSignalAt: null, transport: "stream" });
    const controller = new AbortController();
    requestRef.current = controller;

    try {
      const payload: SajuPreviewRequest = {
        locale,
        calendar_type: calendarType,
        birth_date: birthDate,
        birth_time: birthTime,
        is_birth_time_estimated: isBirthTimeEstimated,
        is_lunar_leap_month: isLunarLeapMonth,
        gender,
        region_id: selectedRegion.id,
        accuracy_mode: accuracyMode,
        debug,
      };
      setLastSubmittedPayload(payload);
      const readingOptions = {
        signal: controller.signal,
        onProgress: progressive ? (next) => {
          if (!controller.signal.aborted) setProgress(next);
        } : undefined,
      } satisfies { signal: AbortSignal; onProgress?: (next: PreviewProgress) => void };
      const response = readingFirst ? await createSajuReading(payload, readingOptions)
        : basicFirst ? await createSajuBasic(payload, { signal: controller.signal })
        : await createSajuPreview(payload, readingOptions);
      if (!controller.signal.aborted) onSuccess(response);
    } catch (requestError) {
      if (controller.signal.aborted) return;
      setError(requestError instanceof Error ? requestError.message : texts.noResult);
      onErrorResult?.();
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setLoading(false);
      }
    }
  }

  return {
    birthDate,
    birthTime,
    isBirthTimeEstimated,
    regionQuery,
    selectedRegion,
    regionOptions,
    highlightedRegionIndex,
    isRegionFocused,
    regionLoading,
    gender,
    calendarType,
    accuracyMode,
    isLunarLeapMonth,
    lastSubmittedPayload,
    loading,
    progress,
    error,
    regionBoxRef,
    setBirthDate: handleBirthDateChange,
    setBirthTime: handleBirthTimeChange,
    setGender,
    setCalendarType,
    setAccuracyMode,
    setIsLunarLeapMonth,
    handleUnknownTimeChange,
    handleRegionSelect,
    handleRegionInputChange,
    handleRegionInputKeyDown,
    setIsRegionFocused,
    submit,
  };
}
