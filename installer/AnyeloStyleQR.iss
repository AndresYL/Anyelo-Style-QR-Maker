; Instalador de Anyelo Style QR (Inno Setup 6). Se compila desde GitHub con build-windows.yml.
; Instala solo para el usuario actual: no pide permisos de administrador.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B7A1F6C2-5D0E-4E7A-9C3B-1A2F5E6D7C80}
AppName=Anyelo Style QR
AppVersion={#AppVersion}
AppVerName=Anyelo Style QR {#AppVersion}
AppPublisher=Anyelo Style
AppPublisherURL=https://anyelo.style
DefaultDirName={autopf}\Anyelo Style QR
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=AnyeloStyleQR-Setup
SetupIconFile=..\anyelo_qr\assets\icon.ico
UninstallDisplayIcon={app}\AnyeloStyleQR.exe
UninstallDisplayName=Anyelo Style QR
WizardStyle=modern
WizardImageFile=wizard_large.bmp
WizardSmallImageFile=wizard_small.bmp
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=AnyeloStyleQR_Mutex
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "autostart"; Description: "Abrir al iniciar Windows, minimizado junto al reloj"; GroupDescription: "Opciones:"
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Opciones:"; Flags: unchecked

[Files]
Source: "..\dist\AnyeloStyleQR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Anyelo Style QR"; Filename: "{app}\AnyeloStyleQR.exe"
Name: "{autodesktop}\Anyelo Style QR"; Filename: "{app}\AnyeloStyleQR.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AnyeloStyleQR"; ValueData: """{app}\AnyeloStyleQR.exe"" --minimized"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\AnyeloStyleQR.exe"; Description: "Abrir Anyelo Style QR"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { Si activaste el inicio con Windows desde el programa, también se quita al desinstalar. }
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'AnyeloStyleQR');
end;
