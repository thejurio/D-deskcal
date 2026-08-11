# D-DeskCal

**English**: A beautiful desktop calendar widget application built with PyQt6. Seamlessly integrates with Google Calendar and local calendars, allowing users to conveniently view and manage their schedules directly from the desktop with multiple themes and intelligent data management.

**한국어**: PyQt6로 제작된 미려한 디자인의 데스크톱 캘린더 위젯 애플리케이션입니다. Google 캘린더 및 로컬 캘린더와 연동하여 사용자의 일정을 바탕화면에서 편리하게 확인하고 관리할 수 있습니다.

![Project Screenshot](https://user-images.githubusercontent.com/12345/screenshot.png) <!-- TODO: 추후 스크린샷 이미지 링크로 교체 -->

## ✨ Features / 주요 기능

### 📋 Calendar Display / 캘린더 표시
- **Monthly Calendar View**: Intuitive monthly schedule display / 직관적인 월별 일정 표시
- **Event Display**: Real-time event viewing with Google Calendar integration / Google Calendar와 연동하여 실시간 일정 확인
- **Multiple Themes**: Light/Dark mode support / 라이트/다크 모드 지원
- **Responsive UI**: Optimized for various screen sizes / 다양한 화면 크기에 최적화

### 🔗 Google Calendar Integration / Google Calendar 연동
- **OAuth 2.0 Authentication**: Secure Google account integration / 안전한 Google 계정 연동
- **Real-time Sync**: Automatic Google Calendar event updates / Google Calendar 일정 자동 업데이트
- **Offline Caching**: View recent events without network connection / 네트워크 연결 없이도 최근 일정 확인
- **Auto Token Refresh**: Seamless integration service / 중단 없는 연동 서비스

### ⚙️ User Settings / 사용자 설정
- **Start Day Configuration**: Choose Monday/Sunday start / 월요일/일요일 시작 선택
- **Weekend Display**: Weekend highlighting options / 주말 강조 표시 옵션
- **Language Settings**: Korean language support / 한국어 지원
- **Auto Start**: Automatic startup on Windows boot / Windows 부팅 시 자동 실행

### 🔄 Auto Update / 자동 업데이트
- **GitHub Integration**: Automatic latest version checking / 최신 버전 자동 확인
- **Silent Updates**: Background checking (72-hour cycle) / 백그라운드에서 자동 확인 (72시간 주기)
- **Manual Check**: Update check available anytime from menu / 메뉴에서 언제든 업데이트 확인
- **Safe Installation**: Update while preserving existing settings / 기존 설정 보존하며 업데이트

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


## 🛠️ 설치 및 실행 방법

### 다운로드
GitHub Releases에서 최신 버전을 다운로드하세요:
- [최신 릴리즈 다운로드](https://github.com/thejurio/D-deskcal/releases/latest)

### 시스템 요구사항
- **OS**: Windows 10/11
- **메모리**: 최소 100MB RAM
- **네트워크**: Google Calendar 연동 시 인터넷 연결 필요

### 설치 파일
- `D-deskcal-win-Setup.exe`: 처음 설치할 때 이것을 받으세요
- 나머지 파일은 **프로그램이 스스로 업데이트할 때** 쓰는 것이라 직접 받지 않아도 됩니다

### 소스 코드

이 저장소는 **내려받는 곳**입니다. 소스 코드는 공개하지 않습니다.

프로그램은 C#(.NET 8, WPF)으로 새로 만들어졌습니다. 위 설치 파일을 받아 쓰시면 됩니다.

## 🛡️ 개인정보 보호

이 프로그램은 다음 개인정보처리방침을 따릅니다:

- **Google Calendar 데이터**: OAuth 2.0을 통해 안전하게 처리되며, 로컬에만 저장됩니다
- **사용자 설정**: 모든 설정은 로컬 컴퓨터에만 저장됩니다
- **네트워크 통신**: Google Calendar API 및 업데이트 확인 외에는 외부 서버와 통신하지 않습니다
- **데이터 수집**: 개인정보나 사용 패턴을 수집하지 않습니다

자세한 내용은 [개인정보처리방침](PRIVACY_POLICY.md)을 참조하세요.

## 🔐 Code Signing Policy

Code signing certification pending approval from [SignPath.io](https://signpath.io) OSS program.

자세한 코드 서명 정책은 [CODE_SIGNING_POLICY.md](CODE_SIGNING_POLICY.md)를 참조하세요.

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 🐛 버그 리포트 및 기능 요청

버그 발견이나 새로운 기능 제안이 있으시면 [GitHub Issues](https://github.com/thejurio/D-deskcal/issues)에 등록해주세요.

## 🔄 업데이트 이력

현재 버전: v1.1.7

주요 업데이트 내역:
- **v1.1.7**: 업데이트 진행률 표시 개선, OAuth 토큰 만료 오류 수정
- **v1.1.5**: 실시간 설정 미리보기 기능 추가
- **v1.1.4**: 캐시 시스템 안정성 향상

전체 업데이트 이력은 [Releases](https://github.com/thejurio/D-deskcal/releases)에서 확인하세요.

---

**개발자**: [thejurio](https://github.com/thejurio)  
**프로젝트 홈**: [https://github.com/thejurio/D-deskcal](https://github.com/thejurio/D-deskcal)
