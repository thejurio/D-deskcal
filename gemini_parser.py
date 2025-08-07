# gemini_parser.py
import google.generativeai as genai
import datetime
import json

def parse_events_with_gemini(api_key, text_to_analyze):
    """
    Gemini API를 사용하여 텍스트에서 일정 정보를 추출합니다.

    Args:
        api_key (str): 사용자의 Gemini API 키.
        text_to_analyze (str): 분석할 원본 텍스트.

    Returns:
        list: 추출된 일정 정보 딕셔너리의 리스트.
              오류 발생 시 빈 리스트를 반환합니다.
    """
    if not api_key:
        raise ValueError("Gemini API 키가 제공되지 않았습니다.")
    if not text_to_analyze:
        raise ValueError("분석할 텍스트가 없습니다.")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        today = datetime.date.today().isoformat()
        
        prompt = f"""
            다음 텍스트에서 찾을 수 있는 **모든** 구글 캘린더 일정을 추출해서 **JSON 배열(Array)** 형식으로 반환해줘.
            - 각 일정은 JSON 객체로 표현해야 해.
            - 날짜는 'YYYY-MM-DD', 시간은 'HH:MM' (24시간제) 형식으로 변환해야 해.
            - '오늘', '내일' 같은 상대적 날짜는 오늘 날짜({today})를 기준으로 계산해줘.
            - 시간이 명시되지 않으면 startTime, endTime은 빈 문자열("")로 설정해줘.
            - 종료 날짜가 없으면 시작 날짜와 동일하게 설정해줘.
            - 각 객체는 'title', 'startDate', 'startTime', 'endDate', 'endTime', 'location', 'description' 필드를 가져야 해.
            - 만약 텍스트가 '접수 기간', '신청 기간', '제출 기한' 등 명확한 시작일과 종료일이 있는 '기간'을 나타내면, 'isDeadline': true 필드를 추가해줘.
            - location 필드가 없으면 빈 문자열로 설정해줘.
            - description 필드에는 원본 텍스트와 추출된 주요 정보를 요약해서 넣어줘.
            - 만약 일정 정보를 하나도 찾을 수 없다면, 빈 배열 '[]'을 반환해줘.
            --- 텍스트 원본 ---
            {text_to_analyze}
            --------------------
        """

        response = model.generate_content(prompt)
        
        # 응답에서 JSON 부분만 정리
        cleaned_json = response.text.replace('```json', '').replace('```', '').strip()
        
        # JSON 파싱
        parsed_events = json.loads(cleaned_json)
        return parsed_events

    except Exception as e:
        print(f"Gemini 파싱 중 오류 발생: {e}")
        # 실제 앱에서는 이 오류를 사용자에게 더 친절하게 보여줘야 합니다.
        raise RuntimeError(f"AI 모델 호출에 실패했습니다. API 키 또는 네트워크 연결을 확인해주세요.\n\n상세 정보: {e}")

def verify_api_key(api_key):
    """
    주어진 Gemini API 키의 유효성을 검사합니다.
    가장 가벼운 'list_models'를 호출하여 확인합니다.
    """
    if not api_key:
        return False, "API 키를 입력해주세요."
    try:
        genai.configure(api_key=api_key)
        # 단순히 모델 목록을 순회하는 것만으로도 인증 확인이 가능합니다.
        for model in genai.list_models():
            pass
        return True, "API 키가 유효합니다."
    except Exception as e:
        # 보통 잘못된 키는 PermissionDenied 오류를 발생시킵니다.
        if "API_KEY_INVALID" in str(e):
             return False, "API 키가 잘못되었습니다."
        return False, f"확인 실패: 네트워크 또는 키 권한 문제"


