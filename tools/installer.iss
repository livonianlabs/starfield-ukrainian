; Інсталятор українського перекладу Starfield (Steam)
; Збирається через build_release.py, який передає /DAppVersion=... /DSrc=... /DOut=...

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef Src
  #define Src "..\dist\Data"
#endif
#ifndef Out
  #define Out "..\dist"
#endif

[Setup]
AppId={{6E1B7A2C-5F3D-4C8E-9B1A-UA0STARFIELD01}
AppName=Starfield — українська локалізація
AppVersion={#AppVersion}
AppPublisher=Українська спільнота Starfield
DefaultDirName={userdocs}\My Games\Starfield
DirExistsWarning=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#Out}
OutputBaseFilename=Starfield_UA_Setup_{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
InfoBeforeFile=info_uk.txt
UninstallDisplayName=Starfield — українська локалізація
Uninstallable=yes

[Languages]
Name: "uk"; MessagesFile: "compiler:Languages\Ukrainian.isl"

[Messages]
uk.WelcomeLabel2=Буде встановлено український переклад Starfield (версія {#AppVersion}).%n%nФайли копіюються в Документи\My Games\Starfield\Data, а в StarfieldCustom.ini вмикається українська мова. Саму гру не змінено.%n%nПеред встановленням закрийте гру.
uk.SelectDirLabel3=Папка налаштувань Starfield у «Документах». Змінюйте лише якщо «Документи» у вас в іншому місці.

#ifndef Fem
  #define Fem "..\dist\Female"
#endif

[Tasks]
Name: "male";   Description: "Герой — чоловічий персонаж";  GroupDescription: "Стать вашого персонажа (звертання NPC, репліки, журнал):"; Flags: exclusive
Name: "female"; Description: "Героїня — жіночий персонаж"; GroupDescription: "Стать вашого персонажа (звертання NPC, репліки, журнал):"; Flags: exclusive unchecked

[Files]
Source: "{#Src}\*"; DestDir: "{app}\Data"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Fem}\Strings\*"; DestDir: "{app}\Data\Strings"; Tasks: female; Flags: ignoreversion skipifsourcedoesntexist
Source: "detect_sex.ps1"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\Starfield UA — повернути оригінал (видалити переклад)"; Filename: "{uninstallexe}"

[Code]
const
  NONE = '<<none>>';

function IniPath(): String; begin Result := ExpandConstant('{app}\StarfieldCustom.ini'); end;
function BackupDir(): String; begin Result := ExpandConstant('{app}\StarfieldUA_backup'); end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not RegKeyExists(HKCU, 'Software\Valve\Steam') then
    Result := MsgBox('Steam не знайдено. Цей інсталятор розрахований на Steam-версію Starfield.' + #13#10 +
                     'Продовжити все одно?', mbConfirmation, MB_YESNO) = IDYES;
end;

{ зберегти чужі файли *_uk.* (напр. інший переклад), щоб повернути їх при видаленні }
procedure BackupFiles(const Sub: String);
var FR: TFindRec; Src, Dst: String;
begin
  Src := ExpandConstant('{app}\Data\' + Sub + '\');
  Dst := BackupDir() + '\' + Sub + '\';
  if FindFirst(Src + '*_uk.*', FR) then
  try
    repeat
      ForceDirectories(Dst);
      FileCopy(Src + FR.Name, Dst + FR.Name, False);
    until not FindNext(FR);
  finally
    FindClose(FR);
  end;
end;

procedure RestoreFiles(const Sub: String);
var FR: TFindRec; Src, Dst: String;
begin
  Src := BackupDir() + '\' + Sub + '\';
  Dst := ExpandConstant('{app}\Data\' + Sub + '\');
  if FindFirst(Src + '*', FR) then
  try
    repeat
      if (FR.Attributes and FILE_ATTRIBUTE_DIRECTORY) = 0 then
      begin
        ForceDirectories(Dst);
        FileCopy(Src + FR.Name, Dst + FR.Name, False);
      end;
    until not FindNext(FR);
  finally
    FindClose(FR);
  end;
end;

procedure SaveKey(const Sec, Key: String);
var B: String;
begin
  B := BackupDir() + '\ini_original.ini';
  { не перезаписувати оригінал при повторному встановленні/оновленні }
  if GetIniString(Sec, Key, '<<unset>>', B) = '<<unset>>' then
    SetIniString(Sec, Key, GetIniString(Sec, Key, NONE, IniPath()), B);
end;

procedure RestoreKey(const Sec, Key: String);
var V: String;
begin
  V := GetIniString(Sec, Key, NONE, BackupDir() + '\ini_original.ini');
  if V = NONE then DeleteIniEntry(Sec, Key, IniPath())
  else SetIniString(Sec, Key, V, IniPath());
end;

var SexChecked: Boolean;

{ автоматично обрати стать героя за найсвіжішим збереженням (detect_sex.ps1: 10 = чоловік, 11 = жінка) }
procedure CurPageChanged(CurPageID: Integer);
var RC: Integer; Params: String;
begin
  if (CurPageID = wpSelectTasks) and not SexChecked then
  begin
    SexChecked := True;
    ExtractTemporaryFile('detect_sex.ps1');
    Params := '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + ExpandConstant('{tmp}\detect_sex.ps1') +
              '" -Saves "' + ExpandConstant('{userdocs}\My Games\Starfield\Saves') + '"';
    if Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, RC) then
    begin
      if RC = 11 then WizardSelectTasks('female')
      else if RC = 10 then WizardSelectTasks('male');
      if (RC = 10) or (RC = 11) then
        WizardForm.SelectTasksLabel.Caption := 'Стать вибрано автоматично за вашим останнім збереженням. За потреби змініть.';
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    ForceDirectories(BackupDir());
    if not FileExists(BackupDir() + '\done.flag') then
    begin
      BackupFiles('Strings');
      BackupFiles('Interface');
      SaveKey('General', 'sLanguage');
      SaveKey('Archive', 'bInvalidateOlderFiles');
      SaveKey('Archive', 'sResourceDataDirsFinal');
      SaveStringToFile(BackupDir() + '\done.flag', '1', False);
    end;
  end;
  if CurStep = ssPostInstall then
  begin
    SetIniString('General', 'sLanguage', 'uk', IniPath());
    SetIniString('Archive', 'bInvalidateOlderFiles', '1', IniPath());
    SetIniString('Archive', 'sResourceDataDirsFinal', '', IniPath());
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and FileExists(BackupDir() + '\done.flag') then
  begin
    RestoreFiles('Strings');
    RestoreFiles('Interface');
    { повертаємо лише наші 3 ключі - інші налаштування, додані пізніше, не чіпаємо }
    RestoreKey('General', 'sLanguage');
    RestoreKey('Archive', 'bInvalidateOlderFiles');
    RestoreKey('Archive', 'sResourceDataDirsFinal');
    DelTree(BackupDir(), True, True, True);
  end;
end;
