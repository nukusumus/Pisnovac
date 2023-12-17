@echo off

cd Src

wget https://www.stud.fit.vutbr.cz/~xsterb16/Downloads/files/new_version.txt

fc version.txt new_version.txt > nul
if errorlevel 1 goto stahnout

goto run

:stahnout
wget https://www.stud.fit.vutbr.cz/~xsterb16/Downloads/files/pisnovac.txt
mv pisnovac.txt pisnovac.py

:run
cls
rm new_version.txt
cd ..
call "%cd%\venv\Scripts\activate"

python\python.exe Src\pisnovac.py