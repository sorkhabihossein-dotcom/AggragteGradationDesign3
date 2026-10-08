[Setup]
AppName=Asphalt Gradation Design
AppVersion=1.0
DefaultDirName={autopf}\AsphaltGradationDesign
DefaultGroupName=Asphalt Gradation Design
OutputBaseFilename=AsphaltGradationDesign_Setup
Compression=lzma
SolidCompression=yes
[Files]
Source: "dist\AsphaltGradationDesign\*"; DestDir: "{app}"; Flags: recursesubdirs
[Icons]
Name: "{group}\Asphalt Gradation Design"; Filename: "{app}\AsphaltGradationDesign.exe"
Name: "{autodesktop}\Asphalt Gradation Design"; Filename: "{app}\AsphaltGradationDesign.exe"
