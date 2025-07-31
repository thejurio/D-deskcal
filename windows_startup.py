# windows_startup.py
import sys
import os
import winreg

# 자동 시작 프로그램의 이름
APP_NAME = "DCWidget"

# 자동 시작 레지스트리 키 경로
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_executable_path():
    """
    GUI 애플리케이션에 적합한 pythonw.exe의 경로를 반환합니다.
    venv 환경을 고려하여 sys.executable을 사용합니다.
    """
    python_exe = sys.executable
    # python.exe를 pythonw.exe로 변경 (콘솔 창이 뜨지 않도록)
    pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
    
    # pythonw.exe가 존재하면 해당 경로를, 아니면 원래 python.exe 경로를 반환
    return pythonw_exe if os.path.exists(pythonw_exe) else python_exe

def get_script_path():
    """
    실행할 메인 스크립트(ui_main.py)의 절대 경로를 반환합니다.
    """
    # __main__ 모듈의 경로를 사용하여 항상 메인 스크립트의 경로를 정확하게 찾습니다.
    if getattr(sys, 'frozen', False):
        # PyInstaller 등으로 패키징된 경우
        return sys.executable
    else:
        # 일반 스크립트로 실행된 경우
        return os.path.abspath(sys.modules['__main__'].__file__)

def add_to_startup():
    """현재 사용자의 시작 프로그램으로 이 앱을 추가합니다."""
    try:
        # HKEY_CURRENT_USER (현재 사용자) 영역에 레지스트리 키를 엽니다.
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_WRITE)
        
        # 실행할 명령어 생성 (예: "C:\path\to\venv\Scripts\pythonw.exe" "C:\path\to\dcwidget\ui_main.py")
        # 경로에 공백이 있을 수 있으므로 각 경로를 큰따옴표로 감싸줍니다.
        executable = get_executable_path()
        script = get_script_path()
        command = f'"{executable}" "{script}"'
        
        # 레지스트리에 값 설정
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        print(f"'{APP_NAME}'을(를) 시작 프로그램에 추가했습니다.")
        return True
    except Exception as e:
        print(f"시작 프로그램 추가 중 오류 발생: {e}")
        return False

def remove_from_startup():
    """현재 사용자의 시작 프로그램에서 이 앱을 제거합니다."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_WRITE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print(f"'{APP_NAME}'을(를) 시작 프로그램에서 제거했습니다.")
        return True
    except FileNotFoundError:
        # 이미 제거된 경우이므로 성공으로 간주
        print(f"'{APP_NAME}'이(가) 시작 프로그램에 등록되어 있지 않습니다.")
        return True
    except Exception as e:
        print(f"시작 프로그램 제거 중 오류 발생: {e}")
        return False

def is_in_startup():
    """이 앱이 현재 사용자의 시작 프로그램에 등록되어 있는지 확인합니다."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"시작 프로그램 확인 중 오류 발생: {e}")
        return False
