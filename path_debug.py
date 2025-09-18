#!/usr/bin/env python3
"""
경로 디버깅 스크립트 - 실제 프로그램 경로 확인
"""
import sys
from pathlib import Path

print("=== 경로 디버깅 정보 ===")
print(f"sys.executable: {sys.executable}")
print(f"Path(sys.executable).parent: {Path(sys.executable).parent}")
print(f"Path(sys.executable).name: {Path(sys.executable).name}")
print(f"Path.cwd(): {Path.cwd()}")
print(f"sys.frozen: {getattr(sys, 'frozen', False)}")

if getattr(sys, 'frozen', False):
    current_exe_dir = Path(sys.executable).parent
    current_exe_name = Path(sys.executable).name
    print(f"\n=== PyInstaller 모드 ===")
    print(f"감지된 실행 디렉토리: {current_exe_dir}")
    print(f"감지된 실행 파일명: {current_exe_name}")

    # 실제 파일 존재 여부 확인
    exe_path = current_exe_dir / current_exe_name
    print(f"실행 파일 존재: {exe_path.exists()}")
    if exe_path.exists():
        print(f"파일 크기: {exe_path.stat().st_size} bytes")
else:
    print("\n=== 개발 모드 ===")
    print(f"작업 디렉토리: {Path.cwd()}")

print("\n=== 현재 디렉토리 파일 목록 ===")
try:
    for item in Path.cwd().glob("*"):
        if item.is_file() and item.suffix in ['.exe', '.py']:
            print(f"  {item.name}")
except Exception as e:
    print(f"파일 목록 오류: {e}")