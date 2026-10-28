; Instalador de BillEase para Windows (Inno Setup 6).
;
;   1. pyinstaller billease.spec          → dist\BillEase\
;   2. compilar este fichero con Inno Setup → Output\BillEase-instalador.exe
;
; Lo que hace y lo que no:
;
;   · Instala en "Archivos de programa", que es de solo lectura para el
;     usuario. Por eso la base de datos NO va aquí: vive en
;     %LOCALAPPDATA%\BillEase\, que es donde la pone `config.py`.
;   · Al desinstalar NO se tocan ni la base ni las copias de seguridad.
;     Borrar las facturas de alguien porque desinstala el programa sería
;     imperdonable; se le dice dónde están y decide él.

#define Nombre "BillEase"
; La versión se puede pasar al compilar —ISCC /DVersion=1.2.3—, que es lo que
; hace la construcción automática cuando se publica con una etiqueta.
#ifndef Version
  #define Version "1.0.0"
#endif
#define Autor "BillEase"
#define Ejecutable "BillEase.exe"

[Setup]
AppName={#Nombre}
AppVersion={#Version}
AppPublisher={#Autor}
DefaultDirName={autopf}\{#Nombre}
DefaultGroupName={#Nombre}
OutputDir=Output
OutputBaseFilename={#Nombre}-instalador-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#Ejecutable}
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; \
    GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\BillEase\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nombre}"; Filename: "{app}\{#Ejecutable}"
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\{#Ejecutable}"; Tasks: escritorio

[Run]
Filename: "{app}\{#Ejecutable}"; Description: "Abrir {#Nombre}"; \
    Flags: nowait postinstall skipifsilent

[Messages]
spanish.FinishedLabel=BillEase está instalado.%n%nTus datos se guardan en %LOCALAPPDATA%\BillEase\, no en la carpeta del programa: desinstalarlo no los borra.
