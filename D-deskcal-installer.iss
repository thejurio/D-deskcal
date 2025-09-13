[Setup]
; 기본 정보
AppName=D-deskcal
AppVersion=1.1.8
AppPublisher=D-deskcal Development Team
AppPublisherURL=https://github.com/thejurio/D-deskcal
AppSupportURL=https://github.com/thejurio/D-deskcal/issues
AppUpdatesURL=https://github.com/thejurio/D-deskcal/releases
DefaultDirName={autopf}\D-deskcal
DefaultGroupName=D-deskcal
AllowNoIcons=yes
OutputDir=release
OutputBaseFilename=D-deskcal-v1.1.8-installer
SetupIconFile=icons\tray_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; 권한 및 설치 옵션
PrivilegesRequired=admin
DisableProgramGroupPage=yes
DisableReadyPage=no
DisableFinishedPage=no

; 언인스톨 정보
UninstallDisplayName=D-deskcal v1.1.8
UninstallDisplayIcon={app}\D-deskcal.exe

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "startupicon"; Description: "시스템 시작 시 자동 실행"; GroupDescription: "시작 옵션"

[Files]
; 메인 실행 파일과 모든 라이브러리
Source: "dist\D-deskcal\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 설정 파일 (덮어쓰지 않음)
Source: "settings.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
; 아이콘 파일
Source: "icons\*"; DestDir: "{app}\icons"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\D-deskcal"; Filename: "{app}\D-deskcal.exe"
Name: "{group}\{cm:UninstallProgram,D-deskcal}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\D-deskcal"; Filename: "{app}\D-deskcal.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\D-deskcal"; Filename: "{app}\D-deskcal.exe"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\D-deskcal.exe"; Description: "{cm:LaunchProgram,D-deskcal}"; Flags: nowait postinstall skipifsilent
; Visual C++ Redistributable 설치 (필요한 경우)
Filename: "{app}\vcredist_x64.exe"; Parameters: "/quiet"; StatusMsg: "Visual C++ Redistributable 설치 중..."; Flags: waituntilterminated; Check: VCRedistNeedsInstall

[UninstallRun]
; 언인스톨 시 실행 중인 프로세스 종료
Filename: "{cmd}"; Parameters: "/C taskkill /f /im D-deskcal.exe"; Flags: runhidden; RunOnceId: "KillDDeskcal"

[Registry]
; 시작프로그램 등록 (선택 사항)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "D-deskcal"; ValueData: "{app}\D-deskcal.exe"; Flags: uninsdeletevalue; Tasks: startupicon

[Code]
function VCRedistNeedsInstall: Boolean;
begin
  // Visual C++ Redistributable 설치 확인 로직
  Result := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 설치 후 추가 작업
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // 언인스톨 시 실행 중인 프로세스 강제 종료
    Exec(ExpandConstant('{cmd}'), '/C taskkill /f /im D-deskcal.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

[Messages]
korean.BeveledLabel=한국어
english.BeveledLabel=English