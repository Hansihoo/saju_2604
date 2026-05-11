import { KeyboardEvent, useEffect, useRef, useState } from "react";

import { RegionSuggestion, SajuPreviewResponse } from "../../shared/api/contracts";
import { createSajuPreview, searchRegionSuggestions } from "../../shared/api/saju";
import { Locale, getCopy } from "../../shared/copy";

type UseSajuInputFormOptions = {
  locale: Locale;
  debug: boolean;
  onSuccess: (result: SajuPreviewResponse) => void;
  onErrorResult?: () => void;
  initialValues?: Partial<{
    birthDate: string;
    birthTime: string;
    gender: "male" | "female";
    calendarType: "solar" | "lunar";
  }>;
};

export function useSajuInputForm({
  locale,
  debug,
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
  const [isLunarLeapMonth, setIsLunarLeapMonth] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const regionBoxRef = useRef<HTMLDivElement | null>(null);

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
      setError(null);
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

  async function submit() {
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

    try {
      const response = await createSajuPreview(
        {
          locale,
          calendar_type: calendarType,
          birth_date: birthDate,
          birth_time: birthTime,
          is_birth_time_estimated: isBirthTimeEstimated,
          is_lunar_leap_month: isLunarLeapMonth,
          gender,
          region_id: selectedRegion.id,
          debug,
        },
        debug,
      );
      onSuccess(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : texts.noResult);
      onErrorResult?.();
    } finally {
      setLoading(false);
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
    isLunarLeapMonth,
    loading,
    error,
    regionBoxRef,
    setBirthDate: handleBirthDateChange,
    setBirthTime: handleBirthTimeChange,
    setGender,
    setCalendarType,
    setIsLunarLeapMonth,
    handleUnknownTimeChange,
    handleRegionSelect,
    handleRegionInputChange,
    handleRegionInputKeyDown,
    setIsRegionFocused,
    submit,
  };
}
