# Public Beta Runbook

## 확정된 제품 기준

- 첫 요청은 무료 미리보기만 생성하고, 전체 해석은 사용자가 펼칠 때 `/saju/free-detail`에서 지연 생성한다.
- 점수와 내부 등급은 일반 API·UI·LLM 입력에서 제외하고, 서버 내부 debug trace에서만 확인한다.
- 년주·월주는 현재의 `lunar_python` 기반 primary 계산을 유지한다. `SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS=0`을 유지한다.

## 배포 환경 변수

Vercel Production 환경에 아래 값을 설정한다. `VERCEL_ENV=production`은 Vercel이 제공하므로 별도 설정할 필요가 없다.

```text
SAJU_LLM_PROVIDER=openai
SAJU_LLM_STORE=0
SAJU_LLM_MAX_ATTEMPTS=1
SAJU_LLM_TIMEOUT_SECONDS=45
SAJU_LLM_ALLOW_REPAIR=0
SAJU_REQUEST_LOG_ENABLED=0
SAJU_REQUEST_LOG_INCLUDE_INPUT=0
SAJU_DETAIL_CACHE_TTL_SECONDS=900
SAJU_DETAIL_CACHE_MAX_ENTRIES=128
SAJU_INTERNAL_DEBUG_TOKEN=<long-random-secret>
SAJU_USE_CANONICAL_YEAR_MONTH_PILLARS=0
SAJU_CORS_ORIGINS=https://saju2604.vercel.app
```

`SAJU_INTERNAL_DEBUG_TOKEN`은 일반 사용자·프런트 환경 변수에 넣지 않는다. 서버 관리자가 `X-Saju-Internal-Debug-Token`과 함께 직접 호출할 때만 debug trace가 반환된다.

## Vercel Firewall 단계

이 저장소는 Vercel 프로젝트와 연결되어 있지 않으며, 코드가 WAF 규칙을 게시하지 않는다. Vercel 프로젝트 소유자가 다음 순서로 적용한다.

1. Firewall 대시보드에서 아래 POST API를 각각 대상으로 **log-only** rate-limit 규칙을 만든다.
   - `/api/saju/preview`: IP당 12회 / 10분
   - `/api/saju/free-detail`: IP당 4회 / 10분
   - `/api/saju/reports/*/detail-prepare`, `/api/saju/reports/*/detail-render`: IP당 각각 20회 / 10분
2. 최소 24시간 동안 정상 재시도와 차단 후보를 확인한다. WAF rate limit은 리전별 카운터이므로 글로벌 단일 카운터가 아님을 감안한다.
3. 정상 사용자가 막히지 않는지 확인한 뒤 Preview 환경에서 deny/rate 동작으로 전환해 재시험한다.
4. Production publish는 변경 내용을 검토한 Vercel 프로젝트 소유자가 직접 수행한다.

처음부터 차단 규칙을 게시하지 않는 이유는 공개 베타의 실제 재시도 패턴을 먼저 측정해 임계값을 조정하기 위해서다. IP 기반 제한만으로 대규모 악용을 완전히 막을 수 없으므로, 이후 로그인·사용량 한도가 필요해지면 공유 저장소 기반 제한을 별도 도입한다.

## 관측과 개인정보

- 사주 API 응답은 `Cache-Control: private, no-store`로 전송된다.
- 요청 파일 로그는 기본 비활성화다. 켜도 기본값은 입력을 지우며, 원본 입력 보관은 로컬 재현 때만 `SAJU_REQUEST_LOG_INCLUDE_INPUT=1`로 명시한다.
- 런타임 로그에서 생년월일·시간·기둥·내부 점수·등급은 자동으로 redaction 된다.
- 장애 분석은 응답의 `X-Trace-Id`와 Vercel Runtime Logs를 기준으로 한다. 사용자 입력값이나 LLM 전문을 관측 태그에 넣지 않는다.

베타 기간에는 아래 지표를 매일 확인한다.

- `/api/saju/preview`와 `/api/saju/free-detail`의 요청 수, 4xx/5xx 비율, p95 응답 시간
- `fallback` 비율과 LLM timeout/invalid-output 비율
- WAF log-only 후보 수와 상위 경로
- detail cache hit 비율과 메모리 경고

## 배포 전 검증

```powershell
pnpm test:api
pnpm build:web
```

배포 Preview에서 다음을 확인한다.

1. `/api/health`가 정상 응답한다.
2. `/api/saju/preview`는 `free_preview`만 반환하고 `interpretation`을 반환하지 않는다.
3. `/api/saju/free-detail`은 `interpretation`만 반환하며 무료 미리보기를 다시 생성하지 않는다.
4. 일반 응답 JSON에 `balance_score`, 도메인 점수, `internal_grade`, `debug_trace`가 없다.
5. 사주 API 응답에 `Cache-Control: private, no-store`와 `X-Trace-Id`가 있다.
