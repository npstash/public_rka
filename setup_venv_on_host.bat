call setup_ext_pkg_deps.bat

python -m venv venv
cd deps\pyautoit
..\..\venv\Scripts\python setup.py install
cd ..\..
venv\Scripts\python -m pip install -r requirements_host.txt
