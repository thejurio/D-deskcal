# hotkey_test.py
import keyboard
import time

# 이 스크립트를 실행하려면 먼저 라이브러리를 설치해야 합니다:
# pip install keyboard

def on_hotkey_triggered():
    print("성공: keyboard 라이브러리가 Ctrl + Alt + H 단축키를 감지했습니다!")
    print("이제 이 창을 닫고(Ctrl+C) Gemini로 돌아가 결과를 알려주세요.")

print("keyboard 라이브러리 테스트를 시작합니다.")
print("Ctrl + Alt + H 를 눌러주세요...")
print("(Windows에서 관리자 권한을 요청할 수 있습니다.)")
print("(테스트 종료는 터미널에서 Ctrl + C)")

try:
    # 단축키 등록
    keyboard.add_hotkey('ctrl+alt+h', on_hotkey_triggered)
    
    # 스크립트가 바로 종료되지 않도록 대기
    # keyboard.wait()는 특정 키를 기다리므로, 여기서는 루프로 대기합니다.
    while True:
        time.sleep(1)

except Exception as e:
    print(f"오류가 발생했습니다: {e}")
    print("아마도 관리자 권한으로 이 스크립트를 실행해야 할 수 있습니다.")

finally:
    # 스크립트 종료 시 등록된 모든 단축키 해제
    keyboard.unhook_all_hotkeys()
    print("\n테스트를 종료합니다.")