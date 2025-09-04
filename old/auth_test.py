# auth_test.py
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- 설정 ---
# 이 스크립트는 'credentials.json' 파일과 동일한 폴더에 있어야 합니다.
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
SCOPES = ['openid', 'https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/userinfo.email']
# --- ---

def main():
    """
    최소한의 코드로 Google 인증 및 API 호출을 테스트합니다.
    """
    creds = None
    
    # 1. token.json 파일이 있으면, 기존 인증 정보를 로드합니다.
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            print(f"✅ '{TOKEN_FILE}'에서 인증 정보 로드 성공.")
        except Exception as e:
            print(f"⚠️ '{TOKEN_FILE}' 로드 실패: {e}. 새 로그인을 시도합니다.")

    # 2. 유효한 인증 정보가 없거나 만료된 경우, 새로 로그인하거나 갱신합니다.
    if not creds or not creds.valid:
        # 토큰이 만료되었고, 갱신 토큰이 있는 경우 갱신을 시도합니다.
        if creds and creds.expired and creds.refresh_token:
            try:
                print("🔄 토큰이 만료되어 갱신을 시도합니다...")
                creds.refresh(Request())
                print("✅ 토큰 갱신 성공.")
            except Exception as e:
                print(f"❌ 토큰 갱신 실패: {e}")
                print("   새 로그인이 필요합니다.")
                creds = None # 갱신 실패 시, 새 로그인을 위해 creds를 비웁니다.
        
        # 새 로그인이 필요한 경우
        if not creds:
            try:
                # token.json을 삭제하여 완전한 새 로그인을 보장합니다.
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE)
                    print(f"🗑️ 기존 '{TOKEN_FILE}' 삭제 완료.")

                print("🌐 새 로그인을 시작합니다. 브라우저를 확인하세요.")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
                print("✅ 새 로그인 및 토큰 교환 성공.")
            except Exception as e:
                print(f"❌ 로그인 절차 중 심각한 오류 발생: {e}")
                return # 로그인 실패 시, 더 이상 진행하지 않음

        # 3. 새로 발급받거나 갱신된 인증 정보를 파일에 저장합니다.
        try:
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            print(f"💾 인증 정보를 '{TOKEN_FILE}'에 저장했습니다.")
        except Exception as e:
            print(f"❌ 인증 정보 저장 실패: {e}")


    # 4. 최종적으로 유효한 인증 정보를 사용하여 API를 호출합니다.
    if creds and creds.valid:
        print("\n🚀 최종 API 호출 테스트를 시작합니다...")
        try:
            service = build('oauth2', 'v2', credentials=creds)
            user_info = service.userinfo().get().execute()
            print("\n🎉🎉🎉 최종 테스트 성공! 🎉🎉🎉")
            print(f"  - 이메일: {user_info.get('email')}")
            print(f"  - 사용자 ID: {user_info.get('id')}")

        except HttpError as e:
            print("\n🔥🔥🔥 최종 테스트 실패! 🔥🔥🔥")
            print(f"  - 오류 종류: HttpError")
            print(f"  - 상태 코드: {e.resp.status}")
            print(f"  - 오류 메시지: {e}")
            print("\n결론: 코드의 문제가 아닌, Google Cloud 프로젝트 설정 또는 환경 문제입니다.")
            print("      'credentials.json'을 새로 발급받거나, OAuth 동의 화면 설정을 확인하세요.")
        except Exception as e:
            print(f"\n🔥🔥🔥 최종 테스트 실패! (기타 예외) 🔥🔥🔥: {e}")

    else:
        print("\n❌ 최종적으로 유효한 인증 정보를 얻지 못해 API를 호출할 수 없습니다.")


if __name__ == '__main__':
    main()