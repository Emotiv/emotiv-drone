; Inno Setup script for EMOTIV Drone BCI (Windows).
;
; Wraps the PyInstaller onedir output into a single setup.exe. Onedir rather
; than onefile on purpose: a onefile build of a PyQt6 + OpenCV + PyAV app
; unpacks itself to %TEMP% on every launch, which costs 10-20 seconds of cold
; start. Installing the folder once keeps startup at a couple of seconds.
;
; Built by .github/workflows/build.yml after PyInstaller runs. To build by hand
; from the repository root:
;     pyinstaller packaging/EmotivDrone.spec --noconfirm
;     iscc packaging/EmotivDrone.iss

#define AppName "EMOTIV Drone BCI"
#define AppPublisher "EMOTIV"
#define AppExe "EMOTIV Drone BCI.exe"
#define AppURL "https://github.com/giovaniemotiv/emotiv-drone"

; Overridden by the workflow with /DAppVersion=<tag>; 0.0.0 marks a local build.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1F2C4A-9C2B-4E43-9C1A-1E7B0B5B9D21}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install by default, so no UAC prompt and no admin rights needed —
; this gets handed to people on machines they may not administer.
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest
OutputDir=..
OutputBaseFilename=EMOTIV-Drone-BCI-windows-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole PyInstaller output folder: the exe plus _internal and its DLLs.
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; \
    Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Settings and the log live in %APPDATA%\EmotivDrone and are deliberately left
; behind on uninstall — the leaderboard is in there, and a reinstall should not
; wipe the scores. Only what the installer itself created is removed.
Type: filesandordirs; Name: "{app}\_internal"
