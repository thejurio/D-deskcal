#!/usr/bin/env python3
"""
GitHub 릴리즈용 ZIP 패키지 생성 스크립트
"""

import zipfile
import os
import shutil
from pathlib import Path

def create_release_package():
    """릴리즈용 ZIP 패키지 생성"""
    
    print("릴리즈 패키지를 생성합니다...")
    
    # 소스 및 대상 경로
    source_dir = Path("dist/D-deskcal")
    if not source_dir.exists():
        print("❌ dist/D-deskcal 디렉토리가 없습니다. 먼저 빌드를 실행하세요.")
        return False
    
    # 릴리즈 디렉토리 생성
    release_dir = Path("release")
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir()
    
    # ZIP 파일명
    zip_filename = "D-deskcal-v1.1.3-installer.zip"
    zip_path = release_dir / zip_filename
    
    print(f"ZIP 파일 생성: {zip_path}")
    
    # ZIP 파일 생성
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # dist/D-deskcal 폴더의 모든 내용을 ZIP 파일 루트에 추가
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                # 상대 경로 계산 (dist/D-deskcal 제거)
                arcname = file_path.relative_to(source_dir)
                zipf.write(file_path, arcname)
                print(f"  추가됨: {arcname}")
    
    print(f"\n✅ 릴리즈 패키지 생성 완료!")
    print(f"파일 위치: {zip_path.absolute()}")
    print(f"파일 크기: {zip_path.stat().st_size / (1024*1024):.1f} MB")
    
    # ZIP 파일 내용 확인
    print("\nZIP 파일 내용:")
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        for info in zipf.filelist:
            print(f"  {info.filename} ({info.file_size} bytes)")
    
    return True

if __name__ == "__main__":
    success = create_release_package()
    if success:
        print("\n이제 release/D-deskcal-v1.1.0-installer.zip 파일을 GitHub 릴리즈에 업로드하세요.")
    else:
        print("❌ 패키지 생성 실패")