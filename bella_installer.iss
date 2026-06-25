#define AppName "BELLA AI Script Generator"
#define AppVersion "1.0"
#define AppPublisher "BELLA"
#define AppExeName "BELLA_AI_Script.exe"

[Setup]
AppId={{A7F3B2C1-4D5E-4F6A-8B9C-0D1E2F3A4B5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\BELLA AI
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=BELLA_AI_Setup
SetupIconFile=bella_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
ShowLanguageDialog=no

[Languages]
Name: "vietnamese"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tao shortcut tren Desktop"; GroupDescription: "Tuy chon them:"

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "bella_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "bella_icon_512.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\bella_icon.ico"
Name: "{group}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\bella_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Khởi chạy {#AppName}"; Flags: nowait postinstall skipifsilent
