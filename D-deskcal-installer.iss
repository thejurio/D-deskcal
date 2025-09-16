#define AppVersion GetFileVersion("dist\D-deskcal\D-deskcal.exe")
#if AppVersion == ""
  #define AppVersion GetStringFileInfo("VERSION", "1.1.7")
#endif

[Setup]
; 기본 정보
AppName=D-deskcal
AppVersion={#AppVersion}
AppPublisher=D-deskcal Development Team
AppPublisherURL=https://github.com/thejurio/D-deskcal
AppSupportURL=https://github.com/thejurio/D-deskcal/issues
AppUpdatesURL=https://github.com/thejurio/D-deskcal/releases
DefaultDirName={autopf}\D-deskcal
DefaultGroupName=D-deskcal
AllowNoIcons=yes
OutputDir=release
OutputBaseFilename=D-deskcal-v{#AppVersion}-installer
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

; 업데이트 감지 설정
AppId={{8B5F9A3C-1E4D-4F2A-8B9C-3D5E7F8A9B0C}
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousSetupType=yes
UsePreviousTasks=yes
UsePreviousLanguage=yes

; 업데이트시 파일 보존 설정
CreateAppDir=yes
DirExistsWarning=no

; 언인스톨 정보
UninstallDisplayName=D-deskcal v{#AppVersion}
UninstallDisplayIcon={app}\D-deskcal.exe

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "startupicon"; Description: "시스템 시작 시 자동 실행"; GroupDescription: "시작 옵션"

[Files]
; 메인 실행 파일과 모든 라이브러리 (업데이트시 중요 설정파일 보존)
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
var
  IsUpgrade: Boolean;
  UserChoice: Integer;
  UpdateChoicePage: TInputOptionWizardPage;

function VCRedistNeedsInstall: Boolean;
begin
  // Visual C++ Redistributable 설치 확인 로직
  Result := False;
end;

function DoManualUninstall(InstallPath: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  
  try
    Log('수동 제거 시작: ' + InstallPath);
    
    // 1. 프로세스 다시 한번 종료
    Exec(ExpandConstant('{cmd}'), '/C taskkill /f /im D-deskcal.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    
    // 2. 설치 폴더 삭제
    if DirExists(InstallPath) then
    begin
      Log('설치 폴더 삭제 시도: ' + InstallPath);
      if not DelTree(InstallPath, True, True, True) then
      begin
        Log('설치 폴더 삭제 실패: ' + InstallPath);
        // 명령줄로 강제 삭제 시도
        Exec(ExpandConstant('{cmd}'), '/C rmdir /s /q "' + InstallPath + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      end;
    end;
    
    // 3. 레지스트리 정리 (HKLM)
    try
      RegDeleteKeyIncludingSubkeys(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8B5F9A3C-1E4D-4F2A-8B9C-3D5E7F8A9B0C}_is1');
      Log('HKLM 레지스트리 정리 완료');
    except
      Log('HKLM 레지스트리 정리 실패');
    end;
    
    // 4. 레지스트리 정리 (HKCU)
    try
      RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8B5F9A3C-1E4D-4F2A-8B9C-3D5E7F8A9B0C}_is1');
      Log('HKCU 레지스트리 정리 완료');
    except
      Log('HKCU 레지스트리 정리 실패');
    end;
    
    // 5. 시작 프로그램 레지스트리 정리
    try
      RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'D-deskcal');
      Log('시작 프로그램 레지스트리 정리 완료');
    except
      Log('시작 프로그램 레지스트리 정리 실패');
    end;
    
    Log('수동 제거 완료');
    
  except
    Log('수동 제거 중 오류 발생');
    Result := False;
  end;
end;

function DoUninstall(InstallPath: String): Boolean;
var
  UninstallString: String;
  ResultCode: Integer;
  UninstallFound: Boolean;
begin
  Result := False;
  UninstallFound := False;
  
  // 실행 중인 프로세스 종료
  Log('프로세스 종료 중...');
  Exec(ExpandConstant('{cmd}'), '/C taskkill /f /im D-deskcal.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // 1. HKLM에서 언인스톨 문자열 찾기
  if RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8B5F9A3C-1E4D-4F2A-8B9C-3D5E7F8A9B0C}_is1', 'UninstallString', UninstallString) then
  begin
    UninstallFound := True;
    Log('HKLM에서 언인스톨 문자열 발견: ' + UninstallString);
  end
  // 2. HKCU에서 언인스톨 문자열 찾기
  else if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8B5F9A3C-1E4D-4F2A-8B9C-3D5E7F8A9B0C}_is1', 'UninstallString', UninstallString) then
  begin
    UninstallFound := True;
    Log('HKCU에서 언인스톨 문자열 발견: ' + UninstallString);
  end;
  
  if UninstallFound then
  begin
    // 언인스톨러 실행
    Log('언인스톨러 실행: ' + UninstallString);
    if Exec(UninstallString, '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
    begin
      if ResultCode = 0 then
      begin
        MsgBox('D-DeskCal이 성공적으로 제거되었습니다.', mbInformation, MB_OK);
        Result := False; // 설치 프로그램 종료
      end
      else
      begin
        Log('언인스톨러 실행 실패, 수동 제거 시도');
        // 수동 제거 시도
        if DoManualUninstall(InstallPath) then
        begin
          MsgBox('D-DeskCal이 제거되었습니다.', mbInformation, MB_OK);
          Result := False;
        end
        else
        begin
          MsgBox('프로그램 제거 중 오류가 발생했습니다.', mbError, MB_OK);
          Result := False;
        end;
      end;
    end
    else
    begin
      Log('언인스톨러 실행 불가, 수동 제거 시도');
      // 수동 제거 시도
      if DoManualUninstall(InstallPath) then
      begin
        MsgBox('D-DeskCal이 제거되었습니다.', mbInformation, MB_OK);
        Result := False;
      end
      else
      begin
        MsgBox('언인스톨러를 실행할 수 없습니다.', mbError, MB_OK);
        Result := False;
      end;
    end;
  end
  else
  begin
    Log('언인스톨 레지스트리 정보 없음, 수동 제거 시도');
    // 수동 제거 시도
    if DoManualUninstall(InstallPath) then
    begin
      MsgBox('D-DeskCal이 제거되었습니다.', mbInformation, MB_OK);
      Result := False;
    end
    else
    begin
      MsgBox('언인스톨 정보를 찾을 수 없습니다.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function CheckExistingInstallation(var AppPath: String): Boolean;
begin
  Result := False;
  
  // 1. HKLM에서 확인 (전체 시스템 설치)
  if RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8B5F9A3C-1E4D-4F2A-8B9C-3D5E7F8A9B0C}_is1', 'InstallLocation', AppPath) then
  begin
    Result := True;
    Log('HKLM에서 기존 설치 감지: ' + AppPath);
    Exit;
  end;
  
  // 2. HKCU에서 확인 (사용자별 설치)
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8B5F9A3C-1E4D-4F2A-8B9C-3D5E7F8A9B0C}_is1', 'InstallLocation', AppPath) then
  begin
    Result := True;
    Log('HKCU에서 기존 설치 감지: ' + AppPath);
    Exit;
  end;
  
  // 3. 기본 설치 위치에서 직접 확인
  AppPath := ExpandConstant('{autopf}\D-deskcal');
  if FileExists(AppPath + '\D-deskcal.exe') then
  begin
    Result := True;
    Log('기본 위치에서 기존 설치 감지: ' + AppPath);
    Exit;
  end;
  
  // 4. 현재 사용자 AppData에서 확인
  AppPath := ExpandConstant('{localappdata}\D-deskcal');
  if FileExists(AppPath + '\D-deskcal.exe') then
  begin
    Result := True;
    Log('사용자 AppData에서 기존 설치 감지: ' + AppPath);
    Exit;
  end;
  
  // 5. Program Files (x86)에서 확인
  AppPath := ExpandConstant('{autopf32}\D-deskcal');
  if FileExists(AppPath + '\D-deskcal.exe') then
  begin
    Result := True;
    Log('Program Files (x86)에서 기존 설치 감지: ' + AppPath);
    Exit;
  end;
end;

function InitializeSetup(): Boolean;
var
  AppPath: String;
begin
  Result := True;
  
  // 기존 설치 감지 (여러 위치 확인)
  if CheckExistingInstallation(AppPath) then
  begin
    IsUpgrade := True;
    UserChoice := 0; // 초기값, 사용자가 나중에 선택
    Log('기존 D-DeskCal 설치 감지됨: ' + AppPath);
  end
  else
  begin
    IsUpgrade := False;
    UserChoice := 0;
    Log('새로운 설치');
  end;
end;


procedure InitializeWizard();
begin
  // 기존 설치가 감지된 경우에만 선택 페이지 생성
  if IsUpgrade then
  begin
    UpdateChoicePage := CreateInputOptionPage(wpWelcome,
      'D-DeskCal이 이미 설치되어 있습니다', 
      '원하는 작업을 선택해 주세요',
      '다음 옵션 중 하나를 선택하여 계속 진행할 수 있습니다.',
      True, False);
    
    UpdateChoicePage.Add('최신 버전으로 업데이트');
    UpdateChoicePage.Add('기존 설치 제거');
    
    // 기본값: 업데이트 선택
    UpdateChoicePage.SelectedValueIndex := 0;
  end;
  
  // Welcome 페이지 메시지 동적 설정  
  if IsUpgrade then
  begin
    WizardForm.WelcomeLabel2.Caption := ExpandConstant('{cm:WelcomeLabel2Detected}');
    WizardForm.WelcomeLabel1.Caption := 'D-DeskCal 설치 마법사에 오신 것을 환영합니다';
  end
  else
  begin
    WizardForm.WelcomeLabel2.Caption := ExpandConstant('{cm:WelcomeLabel2New}');
    WizardForm.WelcomeLabel1.Caption := 'D-DeskCal 설치에 오신 것을 환영합니다';
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  AppPath: String;
begin
  Result := True;
  
  // 커스텀 페이지에서 사용자 선택 처리
  if IsUpgrade and (CurPageID = UpdateChoicePage.ID) then
  begin
    UserChoice := UpdateChoicePage.SelectedValueIndex + 1; // 1=업데이트, 2=제거
    
    if UserChoice = 1 then
    begin
      // 업데이트 선택시 Welcome 페이지 메시지 변경
      WizardForm.WelcomeLabel2.Caption := ExpandConstant('{cm:WelcomeLabel2Update}');
      WizardForm.WelcomeLabel1.Caption := 'D-DeskCal 업데이트에 오신 것을 환영합니다';
    end
    else if UserChoice = 2 then
    begin
      // 제거 선택시 바로 제거 진행
      CheckExistingInstallation(AppPath);
      Result := DoUninstall(AppPath);
      if not Result then
      begin
        // 제거 완료시 설치 마법사 종료
        WizardForm.Close;
      end;
    end;
  end;
end;

procedure BackupUserSettings();
var
  SourcePath, BackupPath: String;
begin
  SourcePath := ExpandConstant('{app}');
  BackupPath := ExpandConstant('{tmp}\D-DeskCal-Backup');
  
  if DirExists(SourcePath) then
  begin
    Log('사용자 설정 백업 시작: ' + SourcePath);
    
    // 백업 폴더 생성
    if not DirExists(BackupPath) then
      CreateDir(BackupPath);
    
    // 중요한 설정 파일들 백업
    if FileExists(SourcePath + '\settings.json') then
    begin
      Log('settings.json 백업');
      FileCopy(SourcePath + '\settings.json', BackupPath + '\settings.json', False);
    end;
    
    if FileExists(SourcePath + '\calendar_cache.db') then
    begin
      Log('calendar_cache.db 백업');
      FileCopy(SourcePath + '\calendar_cache.db', BackupPath + '\calendar_cache.db', False);
    end;
    
    if FileExists(SourcePath + '\user_config.ini') then
    begin
      Log('user_config.ini 백업');
      FileCopy(SourcePath + '\user_config.ini', BackupPath + '\user_config.ini', False);
    end;
  end;
end;

procedure RestoreUserSettings();
var
  BackupPath, DestPath: String;
begin
  BackupPath := ExpandConstant('{tmp}\D-DeskCal-Backup');
  DestPath := ExpandConstant('{app}');
  
  if DirExists(BackupPath) then
  begin
    Log('사용자 설정 복원 시작: ' + BackupPath);
    
    // 백업된 설정 파일들 복원
    if FileExists(BackupPath + '\settings.json') then
    begin
      Log('settings.json 복원');
      FileCopy(BackupPath + '\settings.json', DestPath + '\settings.json', False);
    end;
    
    if FileExists(BackupPath + '\calendar_cache.db') then
    begin
      Log('calendar_cache.db 복원');
      FileCopy(BackupPath + '\calendar_cache.db', DestPath + '\calendar_cache.db', False);
    end;
    
    if FileExists(BackupPath + '\user_config.ini') then
    begin
      Log('user_config.ini 복원');
      FileCopy(BackupPath + '\user_config.ini', DestPath + '\user_config.ini', False);
    end;
    
    // 백업 폴더 정리
    DelTree(BackupPath, True, True, True);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    if IsUpgrade and (UserChoice = 1) then
    begin
      // 업데이트 전 실행 중인 프로세스 종료
      Log('업데이트 모드: 실행 중인 D-DeskCal 종료');
      Exec(ExpandConstant('{cmd}'), '/C taskkill /f /im D-deskcal.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      
      // 사용자 설정 백업
      BackupUserSettings();
      Log('업데이트를 위한 사용자 설정 백업 완료');
    end;
  end
  else if CurStep = ssPostInstall then
  begin
    if IsUpgrade and (UserChoice = 1) then
    begin
      // 사용자 설정 복원
      RestoreUserSettings();
      Log('업데이트 완료 - 사용자 설정 복원됨');
    end
    else if not IsUpgrade then
    begin
      Log('새로 설치 완료');
    end;
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

[CustomMessages]
korean.WelcomeLabel2New=D-DeskCal을 컴퓨터에 설치합니다.%n%n계속하기 전에 다른 응용 프로그램을 모두 닫는 것이 좋습니다.
korean.WelcomeLabel2Detected=기존 D-DeskCal 설치가 감지되었습니다.%n%n다음 단계에서 업데이트 또는 제거를 선택할 수 있습니다.
korean.WelcomeLabel2Update=D-DeskCal을 최신 버전으로 업데이트합니다.%n%n설치 프로그램이 실행 중인 D-DeskCal을 자동으로 종료합니다.%n%n기존 설정과 데이터는 보존됩니다.
english.WelcomeLabel2New=This will install D-DeskCal on your computer.%n%nIt is recommended that you close all other applications before continuing.
english.WelcomeLabel2Detected=An existing D-DeskCal installation has been detected.%n%nYou can choose to update or remove it in the next step.
english.WelcomeLabel2Update=This will update D-DeskCal to the latest version.%n%nSetup will automatically close any running instances of D-DeskCal.%n%nYour existing settings and data will be preserved.