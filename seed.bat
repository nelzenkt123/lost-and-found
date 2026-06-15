@echo off
echo Seeding FindBack Database with sample data...
echo.
"C:\Users\ANJANA JINIL\.local\bin\uv.exe" run --with Flask --with Werkzeug --python 3.11 python setup_sample_data.py
echo.
echo Done! You can now run the app using run.bat
pause
