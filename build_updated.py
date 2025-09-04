#!/usr/bin/env python3
"""
D-deskcal 빌드 스크립트 (업데이트된 자동 업데이트 기능 포함)
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def build_application():
    """PyInstaller로 애플리케이션 빌드"""
    
    print("D-deskcal 빌드를 시작합니다...")
    
    # 기존 빌드 파일 정리
    if Path("build").exists():
        shutil.rmtree("build")
        print("기존 build 디렉토리 삭제됨")
    
    if Path("dist").exists():
        shutil.rmtree("dist") 
        print("기존 dist 디렉토리 삭제됨")
    
    if Path("D-deskcal.spec").exists():
        os.remove("D-deskcal.spec")
        print("기존 spec 파일 삭제됨")
    
    # PyInstaller 명령어
    cmd = [
        "pyinstaller",
        "--windowed",
        "--name=D-deskcal",
        "--icon=icons/tray_icon.ico",
        "--add-data=icons/;icons",
        "--add-data=themes/;themes",
        "--add-data=providers/;providers",
        "--add-data=views/;views",
        "--add-data=VERSION;.",
        "ui_main.py"
    ]
    
    try:
        print("PyInstaller 실행 중...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        print("빌드 성공!")
        print(f"실행 파일 위치: {Path('dist/D-deskcal').absolute()}")
        
        # 빌드된 파일 확인
        dist_dir = Path("dist/D-deskcal")
        if dist_dir.exists():
            print(f"\n빌드된 파일 목록:")
            for file in dist_dir.iterdir():
                print(f"  {file.name}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"빌드 실패: {e}")
        print(f"에러 출력: {e.stderr}")
        return False

if __name__ == "__main__":
    success = build_application()
    if success:
        print("\n✅ 빌드 완료! 개선된 자동 업데이트 기능이 포함되었습니다.")
        print("이제 업데이트 다운로드 후 설치가 제대로 동작할 것입니다.")
    else:
        print("\n❌ 빌드 실패")
        sys.exit(1)