import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 프로그램이 Google Calendar API에 대해 요청할 권한의 범위를 지정합니다.
# 여기서는 '읽기 전용' 권한만 요청합니다.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def authenticate_google():
    """Google Calendar API와 통신하기 위한 서비스 객체를 생성하고 반환합니다."""
    creds = None
    # 'token.json' 파일은 사용자의 액세스 및 갱신 토큰을 저장합니다.
    # 사용자가 처음으로 로그인하면 자동으로 생성됩니다.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    # 유효한 자격 증명(creds)이 없는 경우, 사용자가 로그인하도록 합니다.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 다음 실행을 위해 자격 증명을 'token.json' 파일에 저장합니다.
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    # API와 통신할 수 있는 '서비스(service)' 객체를 생성하여 반환합니다.
    service = build("calendar", "v3", credentials=creds)
    return service

def get_calendar_list(service):
    """사용자의 캘린더 목록을 반환합니다."""
    return service.calendarList().list().execute().get("items", [])

# def main(): ... (이하 기존 코드는 그대로 둡니다)

def main():
    """이 스크립트의 메인 함수입니다. API 접속을 테스트합니다."""
    print("Google Calendar API에 접속을 시도합니다...")
    try:
        service = authenticate_google()

        # 지금부터 10개의 향후 일정을 가져옵니다.
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z'는 UTC 시간을 나타냅니다.
        print("앞으로 예정된 10개의 일정을 가져옵니다.")
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print("예정된 일정이 없습니다.")
            return

        # 가져온 일정을 출력합니다.
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(f"{start} - {event['summary']}")

    except HttpError as error:
        print(f"오류가 발생했습니다: {error}")
    except Exception as e:
        print(f"일반 오류가 발생했습니다: {e}")
    # google_api_client.py 파일에 추가




if __name__ == "__main__":
    main()