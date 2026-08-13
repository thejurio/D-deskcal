# Code Signing Policy

## 코드 서명 정보

이 프로젝트는 **SignPath Foundation**의 무료 오픈소스 코드 서명 프로그램 승인을 신청 중입니다.

**Code signing certification pending approval from [SignPath.io](https://signpath.io) OSS program**

## 팀 역할 및 구성원

### Authors (코드 작성자)
- **thejurio** - 프로젝트 소유자 및 주요 개발자
  - GitHub: [@thejurio](https://github.com/thejurio)
  - 역할: 소스 코드 수정 권한 보유

### Reviewers (리뷰어)
- **thejurio** - 모든 코드 변경사항 리뷰 및 승인
  - 역할: Pull Request 리뷰 및 승인 권한

### Approvers (승인자)
- **thejurio** - 릴리즈 서명 승인 권한자
  - 역할: 코드 서명 요청 최종 승인

## 개인정보처리방침

이 프로그램의 개인정보처리방침은 <https://d-deskcal.duckdns.org/privacy.html> 에서만
관리합니다. 어떤 정보를 어디에 저장하고 어떻게 보호하는지 그곳에 적혀 있습니다.

## 서명 정책

### 서명 대상
- **자체 프로젝트만**: thejurio가 개발한 D-DeskCal 프로젝트만 서명
- **자체 빌드만**: 프로젝트 소스 코드로부터 직접 빌드된 바이너리만 서명
- **공식 릴리즈만**: GitHub Releases를 통해 공식 배포되는 버전만 서명

### 빌드 요구사항
- **소스 검증**: 모든 서명된 바이너리는 GitHub 저장소의 검증된 소스 코드로부터 빌드
- **자동 빌드**: GitHub Actions를 통한 자동화된 빌드 프로세스 사용
- **메타데이터 설정**: 모든 서명된 파일에 제품명과 버전 정보 포함

### 보안 요구사항
- **다중 인증**: GitHub 계정 및 SignPath 계정에 2FA(이중 인증) 활성화
- **수동 승인**: 모든 릴리즈는 수동 승인 과정을 거쳐 서명
- **변경 리뷰**: 모든 코드 변경사항은 릴리즈 전 검토됨

## 기술적 제약사항

### SignPath.io OSS 구독 제약사항
- **바이너리 출처 검증**: 서명된 모든 파일은 소스 코드로부터 검증 가능한 방식으로 빌드
- **수동 승인 필수**: 모든 릴리즈는 수동 승인 과정 필요
- **기술적 제약 준수**: SignPath.io OSS 구독의 모든 기술적 제약사항 준수

### 인증서 정보
- **발급자**: SignPath Foundation
- **유형**: 코드 서명 인증서
- **용도**: D-DeskCal 프로젝트 바이너리 서명 전용

## 라이선스

이 프로젝트는 **MIT 라이선스** 하에 배포됩니다.

- **오픈소스**: OSI 승인 오픈소스 라이선스 사용
- **상업적 이중 라이선스 없음**: 상업적 목적의 별도 라이선스 제공하지 않음
- **독점 코드 없음**: 모든 구성 요소가 오픈소스

자세한 라이선스 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 문의

코드 서명 정책이나 보안에 관한 문의사항은 다음을 통해 연락해주세요:

- **GitHub Issues**: [https://github.com/thejurio/D-deskcal/issues](https://github.com/thejurio/D-deskcal/issues)
- **프로젝트 메인테이너**: [@thejurio](https://github.com/thejurio)

---

**최종 업데이트**: 2025년 1월  
**정책 버전**: 1.0