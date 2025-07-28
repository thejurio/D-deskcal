# Glassy Calendar Widget

![Project Screenshot](https://user-images.githubusercontent.com/12345/screenshot.png) <!-- TODO: 추후 스크린샷 이미지 링크로 교체 -->

Glassy Calendar는 PyQt6로 제작된 미려한 디자인의 데스크톱 캘린더 위젯 애플리케이션입니다. Google 캘린더 및 로컬 캘린더와 연동하여 사용자의 일정을 바탕화면에서 편리하게 확인하고 관리할 수 있습니다.

## ✨ 주요 기능

- **다중 캘린더 지원**: Google 계정 하나에 연결된 모든 캘린더와 로컬 DB 기반의 개인 캘린더를 동시에 사용할 수 있습니다.
- **다양한 테마**: 사용자의 취향에 맞춰 선택할 수 있는 어두운 테마(Dark)와 밝은 테마(Light)를 제공합니다.
- **전체 일정 검색**: 현재 보고 있는 날짜와 상관없이, 로컬 및 Google 캘린더의 모든 과거/미래 일정을 대상으로 강력한 키워드 검색을 지원합니다.
- **다양한 뷰 모드**: 월별(Month) 및 주별(Week) 뷰를 제공하며, 추후 일간/안건 뷰를 추가할 예정입니다.
- **상세한 일정 관리**: 반복 일정, 종일 일정, 설명 추가 등 상세한 옵션을 포함한 이벤트 생성 및 편집 기능을 제공합니다.
- **지능형 데이터 관리**: 백그라운드 스레드를 통해 데이터를 캐싱하고 주기적으로 동기화하여, 부드럽고 빠른 UI 반응성을 보장합니다.
- **높은 사용자 정의**: 투명도 조절, 표시할 캘린더 선택, 캘린더별 색상 지정 등 다양한 개인화 옵션을 제공합니다.

## 🏛️ 아키텍처

본 프로젝트는 유지보수성과 확장성을 고려하여 다음과 같은 아키텍처 패턴을 기반으로 설계되었습니다.

- **Model-View-Controller (MVC) 유사 패턴**: 데이터 로직(Model), UI(View), 사용자 입력 처리(Controller)를 분리하여 각 컴포넌트의 독립성을 높였습니다. PyQt의 시그널-슬롯 메커니즘이 컨트롤러 역할을 수행합니다.
- **Provider 패턴**: `BaseCalendarProvider`라는 추상 클래스를 통해 데이터 소스를 추상화했습니다. `GoogleCalendarProvider`와 `LocalCalendarProvider`가 이를 각각 구현하며, 향후 다른 캘린더 서비스(예: CalDAV)를 쉽게 추가할 수 있는 확장 가능한 구조입니다.
- **비동기 처리 (Multi-threading)**: Google API 연동, 데이터 동기화 등 시간이 오래 걸리는 작업을 별도의 `QThread`에서 처리하여 UI가 멈추는 현상을 방지하고 부드러운 사용자 경험을 제공합니다.

## 📂 모듈 및 클래스 상세 설명

| 파일 경로 | 클래스/모듈 | 역할 |
| :--- | :--- | :--- |
| `ui_main.py` | `MainWidget` | 애플리케이션의 메인 윈도우. 전체 UI 레이아웃, 뷰 전환, 메뉴 등을 관리합니다. |
| `data_manager.py` | `DataManager` | 모든 데이터 흐름을 총괄하는 중앙 허브. Provider들로부터 데이터를 가져오고, 캐싱 및 동기화를 관리하며, UI에 데이터를 제공합니다. |
| `auth_manager.py` | `AuthManager` | Google 계정의 OAuth 2.0 인증 및 토큰 관리를 전담합니다. 로그인/로그아웃 절차를 비동기 스레드로 처리하여 안정성을 확보했습니다. |
| `providers/` | (패키지) | 다양한 데이터 소스와의 연동을 담당하는 모듈들의 집합입니다. |
| `  base_provider.py` | `BaseCalendarProvider` | 모든 Provider가 따라야 할 공통 인터페이스를 정의한 추상 클래스입니다. |
| `  google_provider.py`| `GoogleCalendarProvider` | Google Calendar API와 통신하여 캘린더 목록, 이벤트 조회, 검색, 수정 등의 작업을 수행합니다. |
| `  local_provider.py` | `LocalCalendarProvider` | SQLite DB(`calendar.db`)를 사용하여 로컬 캘린더의 이벤트를 저장하고 관리합니다. |
| `views/` | (패키지) | 월간, 주간 등 다양한 캘린더 뷰 위젯들을 포함합니다. |
| `  base_view.py` | `BaseViewWidget` | 모든 뷰 위젯의 공통 기능을 담은 부모 클래스로, 코드 중복을 최소화합니다. |
| `  month_view.py` | `MonthViewWidget` | 월별 달력 UI를 생성하고 이벤트를 그립니다. |
| `  week_view.py` | `WeekViewWidget` | 주별 타임라인 UI를 생성하고 이벤트를 그립니다. |
| `  layout_calculator.py`| `Month/WeekLayoutCalculator` | 월간/주간 뷰에 표시될 이벤트의 위치, 길이, 겹침 등을 계산하는 복잡한 로직을 분리하여 처리합니다. |
| `settings_window.py`| `SettingsWindow` | 계정 연동, 캘린더 선택, 테마, 투명도 등 각종 설정을 변경하는 UI를 제공합니다. |
| `event_editor_window.py`| `EventEditorWindow` | 새 일정을 추가하거나 기존 일정을 수정하는 UI를 제공합니다. |
| `search_dialog.py` | `SearchDialog` | 전체 일정 검색을 위한 UI와 결과 목록을 표시합니다. |
| `custom_dialogs.py` | (모듈) | `MoreEventsDialog` 등 앱 전반에서 사용되는 커스텀 팝업창들을 포함합니다. |
| `settings_manager.py`| (모듈) | `settings.json` 파일의 로드 및 저장을 담당합니다. |

## 🚀 개발 과정 요약

1.  **기반 구축**: Google API 연동 및 PyQt6를 사용한 기본 UI 창 구현.
2.  **핵심 기능 구현**: 월간/주간 뷰, Google/로컬 캘린더 데이터 연동, 이벤트 CRUD 기능 구현.
3.  **인증 버그 해결**: Google OAuth 2.0 인증 과정에서 발생한 401 오류를 스코프 권한 및 토큰 파일 저장 로직 수정을 통해 해결.
4.  **안정성 확보**: `unittest`를 사용한 자동화된 테스트 코드를 작성하여 `DataManager`, `AuthManager` 등 핵심 로직의 안정성을 확보.
5.  **대규모 리팩토링**:
    - **스타일시트 분리**: UI 스타일을 `.qss` 파일로 분리하여 테마 관리의 기반 마련.
    - **UI/로직 분리**: 복잡한 이벤트 위치 계산 로직을 `LayoutCalculator` 클래스로 분리.
    - **중복 코드 제거**: `BaseViewWidget` 부모 클래스를 도입하여 코드 재사용성 증대.
6.  **UI/UX 개선**:
    - **테마 기능**: 라이트/다크 테마를 추가하고 실시간으로 적용하는 기능 구현.
    - **가독성 향상**: 테마별 폰트 색상, 위젯 크기 및 모양 등을 조절하여 시각적 완성도 향상.
    - **안정성 강화**: 로그인 프로세스를 비동기 스레드로 전환하여 UI 멈춤 및 충돌 문제 해결.
7.  **신규 기능 추가**:
    - **전체 일정 검색**: 캐시 데이터의 한계를 넘어, Google API와 연동하여 모든 기간의 일정을 검색하는 강력한 기능 구현.

## 🗺️ 향후 개발 과제 (미래 로드맵)

### Phase 1: 핵심 기능 완성

- [ ] **일간 뷰 (Day View) 추가**: 특정 날짜의 시간대별 일정을 상세히 볼 수 있는 뷰.
- [ ] **안건 뷰 (Agenda View) 추가**: 다가오는 일정들을 시간 순서대로 목록 형태로 보여주는 뷰.

### Phase 2: 사용자 편의성 극대화

- [ ] **시스템 트레이 아이콘**: 프로그램을 닫아도 트레이 아이콘으로 최소화되어 백그라운드에서 실행되는 기능.
- [ ] **이벤트 알림**: 이벤트 시작 시간에 맞춰 데스크톱 알림을 표시하는 기능.
- [ ] **단축키(Hotkeys) 지원**: `Ctrl+N`으로 새 일정 추가, `Ctrl+F`로 검색창 열기 등.

### Phase 3: 데이터 확장성 확보

- [ ] **iCal(.ics) 파일 지원**: 표준 캘린더 파일을 가져오거나 내보내는 기능.
- [ ] **읽기 전용 캘린더 구독**: 공휴일 캘린더 등 공개된 `.ics` 링크를 구독하는 기능.

### Phase 4: 배포

- [ ] **아이콘 및 브랜딩**: 애플리케이션 아이콘 제작.
- [ ] **실행 파일 패키징**: `PyInstaller` 등을 사용하여 `exe` 파일로 패키징.

## 🛠️ 설치 및 실행 방법

1.  **저장소 복제**:
    ```bash
    git clone https://github.com/your-username/your-repository-name.git
    cd your-repository-name
    ```

2.  **가상 환경 생성 및 활성화**:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **필요 라이브러리 설치**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **`credentials.json` 파일 준비**:
    - [Google Cloud Console](https://console.cloud.google.com/)에서 `데스크톱 앱` 유형으로 OAuth 2.0 클라이언트 ID를 생성합니다.
    - 다운로드한 `credentials.json` 파일을 프로젝트 루트 폴더(`C:\dcwidget`)에 위치시킵니다.

5.  **프로그램 실행**:
    ```bash
    python ui_main.py
    ```
