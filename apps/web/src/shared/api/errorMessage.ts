import type { Locale } from "../copy";

const errors: Record<string, [string, string]> = {
  INPUT_SCHEMA_ERROR: ["입력한 생년월일과 시간을 다시 확인해 주세요.", "Check your birth date and time."],
  REGION_NOT_SELECTED: ["태어난 곳을 검색한 뒤 목록에서 선택해 주세요.", "Search for your birthplace and select it from the list."],
  INVALID_BIRTH_TIME: ["태어난 시간을 확인해 주세요. 모르면 시간 미상을 선택할 수 있어요.", "Check your birth time, or select unknown time."],
  NON_EXISTENT_LOCAL_TIME: ["그 지역에서 사용하지 않았던 시각이에요. 태어난 시간을 확인해 주세요.", "That local time did not exist in this region. Check your birth time."],
  INVALID_TIMEZONE: ["태어난 곳을 목록에서 다시 선택해 주세요.", "Select your birthplace from the list again."],
  UNSUPPORTED_SOLAR_DATE: ["지원하는 생년월일 범위를 확인해 주세요.", "Check the supported birth date range."],
  UNSUPPORTED_LUNAR_DATE: ["음력 생년월일과 윤달 여부를 확인해 주세요.", "Check your lunar birth date and leap month selection."],
  CALENDAR_NORMALIZATION_ERROR: ["생년월일과 양력·음력 선택을 확인해 주세요.", "Check your birth date and calendar selection."],
};

// API diagnostics belong in logs. Never display raw JSON, HTML, or internal messages.
export function getApiErrorMessage(status: number, body: unknown, locale: Locale): string {
  const data = body && typeof body === "object" ? body as Record<string, unknown> : {};
  const detail = data.detail && typeof data.detail === "object" ? data.detail as Record<string, unknown> : {};
  const code = typeof data.error_code === "string" ? data.error_code : detail.error_code;
  const message = typeof code === "string" ? errors[code] : undefined;
  if (message) return message[locale === "ko" ? 0 : 1];
  if (status === 429) return locale === "ko"
    ? "요청이 잠시 몰렸어요. 조금 뒤 다시 눌러 주세요."
    : "It's busy right now. Please try again shortly.";
  return locale === "ko"
    ? "풀이를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요."
    : "Couldn't load your reading. Please try again shortly.";
}
