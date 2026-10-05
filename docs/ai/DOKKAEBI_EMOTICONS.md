# 도깨비 이모티콘

## 저장된 이미지

- 위치: `apps/web/public/characters/dokkaebi/`
- 표정 9개: `smile`, `smirk`, `laugh`, `surprised`, `shy`, `unimpressed`, `cry`, `sleepy`, `wink`.
- 각 표정은 1254 × 1254 투명 PNG다. 선택한 도깨비의 한 개 뿔, 연보라색 몸, 짙은 테두리를 유지했다.
- `source-sheet.png`: 사용자가 선택한 최초 표정 시트.
- `manifest.json`: 이미지 ID·한국어 이름·파일명·실제 생성 프롬프트 기록.
- `dokkaebi-emoticons.zip`: 표정 PNG 9개와 manifest를 포함한다.

## 사용 흐름

서비스 상단의 **캐릭터 아이콘**으로 `/stickers`를 연다. 접근성 이름은 `표정 고르기`다. 표정을 고르면 큰 미리보기와 이미지 저장 링크가 즉시 바뀐다. **선택 완료**를 누르면 첫 화면 또는 기존 결과로 돌아간다. 표정 선택 화면을 여는 동안 서비스 컴포넌트를 유지해 입력값과 상세 풀이용 제출 데이터를 잃지 않는다. 모바일 결과의 **카드 만들기 → 카드 표정 바꾸기**에서도 같은 선택 컴포넌트를 사용한다.

선택한 표정 ID만 `saju.dokkaebi.expression.v1`에 저장한다. 출생 정보나 해석 내용은 저장하지 않는다. 잘못된 저장값은 기본 능청 표정으로 돌아가며, 저장소 접근이 제한된 브라우저에서도 현재 세션의 선택은 동작한다.

첫 화면과 결과 화면은 사용자가 선택한 표정을 표시한다. 대기 화면은 졸림 → 깜짝 → 방긋 표정을 짧은 안내와 함께 사용한다. 주제와 입력 단계별 표정 역할은 `src/features/service/experience/experienceCopy.ts`에 분리했다. 표정은 UI 분위기이며 사주 분석 결과나 점수로 해석하지 않는다. 전체 모바일 UX는 [034 설계 문서](../planning/034-dokkaebi-mobile-reading-experience.md)를 따른다.

PNG는 메신저에 이미지로 첨부할 수 있다. 메신저 플랫폼에 등록된 이모티콘 상품은 아니다.

## 재사용과 교체

표정 목록, 한국어/영어 이름, UI 기본 표정은 `src/features/character/dokkaebiCatalog.ts`에서 관리한다. 파일 URL은 Vite의 `BASE_URL`을 반영한다.

```tsx
import { DokkaebiSticker } from "./features/character/DokkaebiSticker";

<DokkaebiSticker expression="smirk" size={48} />
<DokkaebiSticker expression="wink" size={32} decorative />
```

`DokkaebiPicker`는 선택 상태와 콜백을 받는 공통 컴포넌트다. native radio를 사용해 키보드 탐색, 단일 선택, 선택 표시를 제공한다. 주요 이미지에는 크기를 지정하고, 선택 목록 이미지는 lazy loading을 사용한다. 스타일은 `dokkaebi.css`로 분리했다.

이미지를 교체하려면 동일한 ID의 PNG를 교체하고 생성 기록과 ZIP을 갱신한다. 새 표정을 추가할 때는 catalog, PNG, manifest, ZIP을 함께 갱신한다. backend나 사주 계산 계약 수정은 필요 없다.

## 생성 기록

내장 `image_gen`으로 승인된 시트를 참조해 표정별 이미지를 각각 생성했다. CLI/API 키 방식은 사용하지 않았다. 공통 지시는 동일한 몸·뿔·색·테두리를 유지하고, 지정한 표정 하나를 투명 배경의 독립 이미지로 만드는 것이다. 실제 프롬프트 9개는 manifest에 보관했다.

## 검증

표정 PNG 9개를 읽어 크기와 네 모서리의 alpha=0을 확인했다. ZIP 안의 PNG 9개와 manifest를 확인했다. `pnpm build:web`의 타입 검사·프로덕션 빌드가 통과했다.

Chrome 데스크톱과 390px 모바일에서 이미지 표시·선택·키보드 이동·새로고침 유지·서비스 입력값/결과 유지·PNG와 ZIP 다운로드를 확인했다. 다운로드 파일의 SHA256이 원본과 일치하며, 브라우저 오류와 가로 넘침이 없었다. 기존 managed 개발 환경을 fallback provider로 실행해 실 API 입력→미리보기→표정 변경→결과 복귀도 확인했다. 변경은 프론트 표현과 이미지 자산에 한정해 backend 테스트 전체를 재실행하지 않았다.

검증 화면: [모바일](screenshots/dokkaebi-stickers-mobile.jpg), [데스크톱](screenshots/dokkaebi-stickers-desktop.jpg). 앱 내 브라우저 연결은 unavailable 상태였으므로 Chrome 연결을 사용했다. 브라우저의 native JPEG 캡처 형식으로 저장했다.
