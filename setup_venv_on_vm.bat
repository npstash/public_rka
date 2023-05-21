python -m venv venv_vm
cd deps\pyautoit
..\..\venv_vm\Scripts\python setup.py install
cd ..\..
venv_vm\Scripts\python -m pip install -r requirements_vm.txt
