if exist C:\storage\share\rka_logs (
    venv\Scripts\python -m rka.app.starter > C:\storage\share\rka_logs\server-%computername%.txt
) else if exist D:\storage\share\rka_logs (
    venv\Scripts\python -m rka.app.starter > D:\storage\share\rka_logs\server-%computername%.txt
) else (
    git pull github master
    venv_vm\Scripts\python -m rka.app.starter
)
