@echo off
REM Change the current directory to the location of this .bat file
pushd "%~dp0"

REM Activate the correct conda environment for the resizer tool
call conda activate resizer-env

REM Run the python script
echo Starting Image Resizer...
python image_resizer.py

REM Pause to see the server output or any errors
pause

REM Return to the original directory (good practice)
popd