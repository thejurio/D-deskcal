#!/usr/bin/env python3
"""
D-deskcal Build Script
Builds the application using PyInstaller with proper configuration
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def get_version():
    """Get version from VERSION file"""
    try:
        with open('VERSION', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "1.0.0"

def clean_build():
    """Clean previous build artifacts"""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}/")
            shutil.rmtree(dir_name)

def create_spec_file():
    """Create PyInstaller spec file with proper configuration"""
    version = get_version()
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

# Get the current directory
current_dir = os.getcwd()

a = Analysis(
    ['ui_main.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[
        ('icons/', 'icons/'),
        ('themes/', 'themes/'),
        ('providers/', 'providers/'),
        ('views/', 'views/'),
        ('VERSION', '.'),
    ],
    hiddenimports=[
        'keyboard',
        'plyer',
        'win10toast',
        'pywin32',
        'google.auth',
        'google.auth.transport.requests',
        'google.oauth2.credentials',
        'googleapiclient',
        'googleapiclient.discovery',
        'google.generativeai',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='D-deskcal',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Hide console for GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/tray_icon.ico',  # Application icon
    version_info={{
        'version': (1, 0, 0, 0),
        'file_description': 'D-deskcal - Desktop Calendar Widget',
        'product_name': 'D-deskcal',
        'product_version': '{version}',
        'company_name': 'thejurio',
        'copyright': '© 2024 thejurio',
    }}
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='D-deskcal'
)
'''
    
    with open('D-deskcal.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("Created D-deskcal.spec")

def build_application():
    """Build the application using PyInstaller"""
    print("Building D-deskcal...")
    
    try:
        # Run PyInstaller with the spec file
        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', 'D-deskcal.spec']
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def create_installer():
    """Create installer using NSIS (if available) or simple zip"""
    print("Creating installer...")
    
    dist_path = Path('dist/D-deskcal')
    if not dist_path.exists():
        print("Build directory not found!")
        return False
    
    version = get_version()
    
    # Create a simple zip installer for now
    import zipfile
    installer_name = f"D-deskcal-v{version}-installer.zip"
    
    with zipfile.ZipFile(f"dist/{installer_name}", 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dist_path):
            for file in files:
                file_path = Path(root) / file
                arc_path = file_path.relative_to(dist_path.parent)
                zipf.write(file_path, arc_path)
    
    print(f"Created {installer_name}")
    return True

def main():
    """Main build process"""
    print("Starting D-deskcal build process...")
    
    # Check if we're in the right directory
    if not os.path.exists('ui_main.py'):
        print("ERROR: ui_main.py not found! Please run from the project root directory.")
        sys.exit(1)
    
    # Check if icons directory exists
    if not os.path.exists('icons/tray_icon.ico'):
        print("ERROR: Icon file icons/tray_icon.ico not found!")
        sys.exit(1)
    
    # Build process
    clean_build()
    create_spec_file()
    
    if build_application():
        create_installer()
        print("SUCCESS: Build process completed successfully!")
        print("Output files in: dist/")
    else:
        print("FAILED: Build process failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()