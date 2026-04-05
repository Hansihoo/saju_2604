# suju-insight

사주 정보를 더 쉽고 현대적으로 전달하는 웹 서비스의 첫 부트스트랩입니다. 현재 버전은 다음을 포함합니다.

- `apps/web`: React + Vite 기반 랜딩/입력 미리보기 화면
- `apps/api`: FastAPI 기반 헬스체크 및 서비스 메타데이터 API
- `docs/planning`: MVP 방향과 다음 작업 정리

## 구조

```text
apps/
  api/
  web/
docs/
  planning/
  delivery/
Template/
```

## 실행 전제

- Node.js 20+
- pnpm 9+
- Python 3.8+ 권장
- `uv` 또는 `pip`

## 웹 실행

```bash
pnpm install
pnpm dev:web
```

기본 주소는 `http://localhost:5173` 입니다. 웹 앱은 `/api` 요청을 로컬 API 서버로 프록시합니다.

## API 실행

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```

기본 주소는 `http://localhost:8000` 입니다.

## 환경 변수

웹:

```bash
VITE_API_BASE_URL=/api
```

API:

```bash
SAJU_APP_NAME=suju-insight
SAJU_API_VERSION=0.1.0
SAJU_CORS_ORIGINS=http://localhost:5173
```

## 다음 단계 제안

1. 실제 사주 입력 폼 필드와 검증 규칙 정의
2. 해석 결과 도메인 모델과 API 스키마 설계
3. 회원/비회원 조회 정책과 개인정보 처리 범위 확정
4. PostgreSQL 스키마 및 배포 환경 연결
