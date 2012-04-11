; -- Example1.iss --
; Demonstrates copying 3 files and creating an icon.

; SEE THE DOCUMENTATION FOR DETAILS ON CREATING .ISS SCRIPT FILES!

[Setup]
AppName=Timetracker
AppVerName=Timetracker 1.0 (beta)
DefaultDirName={pf}\Timetracker
DefaultGroupName=Timetracker
UninstallDisplayIcon={app}\timetracker.ico
Compression=lzma
SolidCompression=yes
;OutputDir=userdocs:Inno Setup Examples Output

[Dirs]
Name: "{app}/cache"

[Files]
Source: "dist/*"; DestDir: "{app}"
Source: "timetracker.ico"; DestDir: "{app}"

[Icons]
Name: "{group}\Timetracker"; Filename: "{app}\timetracker.exe"; IconFilename: "{app}\timetracker.ico"; WorkingDir: "{app}"
Name: "{group}\Uninstall Timetracker"; Filename: "{uninstallexe}"

[UninstallDelete]
Type: files; Name: "{app}\timetracker.db"

