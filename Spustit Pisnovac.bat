@echo off

cd Src

curl --no-ssl https://www.stud.fit.vutbr.cz/~xsterb16/Downloads/files/pisnovac.txt > pisnovac.py

echo:
echo Pisnovac: Nezavirejte toto okno, zavre se automaticky
cd ..
call "%cd%\venv\Scripts\activate"

python\python.exe Src\pisnovac.py