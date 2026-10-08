@echo off
REM Run on Windows with Python 3.10+ installed
pip install -r requirements.txt
pyinstaller --noconfirm --windowed --name AsphaltGradationDesign asphalt_gradation_design.py
echo Build done: dist\AsphaltGradationDesign\AsphaltGradationDesign.exe
echo Next: open installer.iss in Inno Setup (jrsoftware.org) and click Compile to create the Setup .exe
