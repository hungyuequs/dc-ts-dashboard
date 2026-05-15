@echo off
title DC Test Structure Analysis Dashboard (jcfit)
echo ================================================
echo  DC Test Structure Analysis Dashboard
echo  Environment: jcfit
echo ================================================
echo.

REM Find Anaconda activate.bat
set CONDA_ACTIVATE=
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat"  set CONDA_ACTIVATE=%USERPROFILE%\anaconda3\Scripts\activate.bat
if exist "%USERPROFILE%\Anaconda3\Scripts\activate.bat"  set CONDA_ACTIVATE=%USERPROFILE%\Anaconda3\Scripts\activate.bat
if exist "%PROGRAMDATA%\anaconda3\Scripts\activate.bat"  set CONDA_ACTIVATE=%PROGRAMDATA%\anaconda3\Scripts\activate.bat
if exist "%PROGRAMDATA%\Anaconda3\Scripts\activate.bat"  set CONDA_ACTIVATE=%PROGRAMDATA%\Anaconda3\Scripts\activate.bat

if "%CONDA_ACTIVATE%"=="" (
    echo ERROR: Could not find Anaconda installation.
    pause & exit /b 1
)

echo Activating "jcfit"...
call "%CONDA_ACTIVATE%" jcfit
if errorlevel 1 (
    echo ERROR: Could not activate "jcfit". Run "conda env list" to check it exists.
    pause & exit /b 1
)

echo.
echo Starting Streamlit dashboard...
cd /d "C:\Users\tsaoh\MIT Dropbox\EQuS\MIT. Nano Fabrication\Python Code for DC TS Analysis\Dashboard"
start "" http://localhost:8501
streamlit run dashboard_refactored.py
pause