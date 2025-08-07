# timezone_helper.py
import requests
import json

def get_timezone_from_ip():
    """
    Fetches the timezone based on the user's public IP address using ipinfo.io.
    Returns a default timezone if the request fails.
    """
    default_timezone = "Asia/Seoul"
    try:
        response = requests.get("https://ipinfo.io/json", timeout=5)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        timezone = data.get("timezone")
        
        if timezone and isinstance(timezone, str):
            print(f"자동 감지된 시간대: {timezone}")
            return timezone
        else:
            print(f"IP 정보에서 시간대를 찾을 수 없어 기본값({default_timezone})을 사용합니다.")
            return default_timezone
            
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"IP 기반 시간대 조회 중 오류 발생: {e}. 기본값({default_timezone})을 사용합니다.")
        return default_timezone

if __name__ == '__main__':
    # Test the function
    user_timezone = get_timezone_from_ip()
    print(f"최종 반환된 시간대: {user_timezone}")
