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

def parse_version(version_str):
    """Parse version string to tuple (major, minor, patch, build)"""
    import re
    # Remove any non-numeric suffixes (like 'b', 'a', 'rc')
    clean_version = re.sub(r'[a-zA-Z]+', '', version_str)
    parts = clean_version.split('.')
    while len(parts) < 4:
        parts.append('0')
    return tuple(int(p) if p else 0 for p in parts[:4])

def create_version_info(version):
    """Create version_info.txt file with current version"""
    version_tuple = parse_version(version)
    version_with_build = f"{version}.0" if version.count('.') == 2 else version
    
    version_info_content = f'''# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers={version_tuple},
    prodvers={version_tuple},
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x4,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'DeskCal Team'),
        StringStruct(u'FileDescription', u'DeskCal - Desktop Calendar Widget'),
        StringStruct(u'FileVersion', u'{version_with_build}'),
        StringStruct(u'InternalName', u'D-deskcal'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2024 DeskCal Team'),
        StringStruct(u'OriginalFilename', u'D-deskcal.exe'),
        StringStruct(u'ProductName', u'DeskCal'),
        StringStruct(u'ProductVersion', u'{version_with_build}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)'''
    
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info_content)
    print(f"Created version_info.txt with version {version_with_build}")

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
    create_version_info(version)  # Create version info file
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

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
        ('credentials.json', '.'),
    ],
    collect_all_submodules=[
        'PyQt6',
        'google',
        'googleapiclient', 
        'google_auth_oauthlib',
        'keyboard',
        'plyer',
        'win10toast',
        'pywin32',
        'requests',
        'cryptography',
        'certifi',
        'Pillow',
        'dateutil',
        'pytz',
        'google.generativeai',
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
        'google_auth_oauthlib.flow',
        'google.generativeai',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtSvg',
        'PyQt6.QtPrintSupport',
        # Browser and network related modules
        'webbrowser',
        'subprocess',
        'threading',
        'os',
        'os.path',
        'urllib',
        'urllib.parse',
        'urllib.request',
        'urllib.error',
        'http.server',
        'socketserver',
        'requests',
        'requests.adapters',
        'requests.auth',
        'requests.exceptions',
        'requests.models',
        'requests.sessions',
        'requests.utils',
        'requests.packages.urllib3',
        # SSL certificate support
        'certifi',
        'ssl',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.backends.openssl',
        # JSON and data handling
        'dateutil',
        'dateutil.parser',
        'dateutil.tz',
        'dateutil.relativedelta',
        'pytz',
        'calendar',
        'datetime',
        'zoneinfo',
        # Google API dependencies
        'google_auth_oauthlib',
        'google_auth_httplib2',
        'httplib2',
        'oauth2client',
        'uritemplate',
        'six',
        'cachetools',
        'rsa',
        'pyasn1',
        'pyasn1_modules',
        # Keyboard library Windows dependencies
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'win32clipboard',
        'win32event',
        'win32file',
        'winsound',
        'pywintypes',
        'pythoncom',
        'ctypes',
        'ctypes.wintypes',
        '_ctypes',
        # Standard library modules
        'time',
        'collections',
        'collections.abc',
        'queue',
        'json',
        'string',
        'functools',
        'itertools',
        'enum',
        'pathlib',
        'logging',
        'logging.handlers',
        'configparser',
        'sqlite3',
        're',
        'base64',
        'hashlib',
        'hmac',
        'secrets',
        'uuid',
        'tempfile',
        'shutil',
        'zipfile',
        'tarfile',
        'pickle',
        'copy',
        'weakref',
        'gc',
        'sys',
        'platform',
        'socket',
        'select',
        'email',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',
        'mimetypes',
    ],
    hookspath=[],
    hooksconfig={},
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
    version='version_info.txt',  # Use version info file
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
        # Run PyInstaller with spec file only - all collection is handled in spec
        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', 'D-deskcal.spec']
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build completed successfully!")
        print("STDOUT:", result.stdout[-1000:])  # Show last 1000 chars of output
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