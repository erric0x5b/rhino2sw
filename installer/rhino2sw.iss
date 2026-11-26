; Installatore rhino2sw (Inno Setup 6)
; Compilare da riga di comando:  iscc /DAppVersion=0.2.0 installer\rhino2sw.iss
; Presuppone la build PyInstaller in dist\rhino2sw

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F3C2B0E-8C1D-4E7A-9A55-2B7D4E1C9F10}
AppName=rhino2sw
AppVersion={#AppVersion}
AppVerName=rhino2sw {#AppVersion}
AppPublisher=erric0x5b
AppPublisherURL=https://github.com/erric0x5b/rhino2sw
AppSupportURL=https://github.com/erric0x5b/rhino2sw/issues
DefaultDirName={autopf}\rhino2sw
DefaultGroupName=rhino2sw
DisableProgramGroupPage=yes
; installazione per utente senza diritti di amministratore (l'IT puo' scegliere "per tutti")
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=rhino2sw-{#AppVersion}-setup
SetupIconFile=..\assets\rhino2sw.ico
UninstallDisplayIcon={app}\rhino2sw.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
; i rapporti e le impostazioni (in %LOCALAPPDATA%\rhino2sw) NON vengono cancellati alla disinstallazione

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul desktop"; GroupDescription: "Icone:"
Name: "sendto"; Description: "Aggiungi rhino2sw al menu «Invia a» (tasto destro sui file STEP)"; GroupDescription: "Integrazione:"

[Files]
Source: "..\dist\rhino2sw\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\rhino2sw"; Filename: "{app}\rhino2sw.exe"
Name: "{group}\Disinstalla rhino2sw"; Filename: "{uninstallexe}"
Name: "{autodesktop}\rhino2sw"; Filename: "{app}\rhino2sw.exe"; Tasks: desktopicon
Name: "{usersendto}\rhino2sw (converti per SolidWorks)"; Filename: "{app}\rhino2sw.exe"; Tasks: sendto

[Run]
Filename: "{app}\rhino2sw.exe"; Description: "Avvia rhino2sw"; Flags: nowait postinstall skipifsilent
