; Kernote installer (Inno Setup 6). Per-user: no admin rights, no UAC prompt.
;
; Build:  ISCC.exe packaging\kernote.iss
;   /DSourceDir=<dir containing kernote.exe and _internal\>   (default: build\dist\kernote)
;   /DOutputDir=<where Setup.exe lands>                        (default: build\installer)
;
; Uninstall removes the program only. The vault (%LOCALAPPDATA%\kernote) is the
; user's data and is deliberately never touched; the uninstaller says so.

#ifndef SourceDir
  #define SourceDir "..\..\kernote-build\dist\kernote"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\kernote-build\installer"
#endif
#define AppName "Kernote"
#define AppVersion "0.1.0"

[Setup]
AppId={{36A2DC39-E127-432F-B0D8-527137E58D22}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Kernote
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=Kernote-Setup-{#AppVersion}
SetupIconFile=kernote.ico
UninstallDisplayIcon={app}\kernote.exe
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; An upgrade replaces files in use unless the running app is closed first.
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\kernote.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\kernote.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\kernote.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usDone then
    MsgBox('Kernote was removed. Your memory vault was kept at:' + #13#10 +
           ExpandConstant('{localappdata}') + '\kernote\kernote' + #13#10#13#10 +
           'Delete that folder yourself if you want the data gone too.',
           mbInformation, MB_OK);
end;
