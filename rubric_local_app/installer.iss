; Inno Setup 6 Script for Rubric-Local
; Offline AI Question Recognition & Solver Engine

#define MyAppName "Rubric-Local"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Rubric-Local Open Source Project"
#define MyAppURL "https://github.com/rubric-local/rubric-local"
#define MyAppExeName "Rubric-Local.exe"

[Setup]
AppId={{D37E88BC-3FA8-4E0E-8521-1D0A3C9A8B62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release_dist
OutputBaseFilename=Rubric-Local-v{#MyAppVersion}-Setup
SetupIconFile=rubric.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
CloseApplicationsFilter=Rubric-Local.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start Rubric-Local automatically when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "dist\Rubric-Local\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "rubric.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\rubric.ico"; Comment: "Offline AI Question Recognition & Solver Engine"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\rubric.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
