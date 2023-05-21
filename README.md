# RKA

## Installing

Execute setup_venv_on_host.bat on host machine, in the RKA directory.
Execute setup_venv_on_vm.bat on slave machines, in the RKA directory.
(note: VMs are no longer supported, only use native hosts)

To update AutoIt, run setup_ext_pkg_deps.bat in RKA directory, 
activate the appropriate VENV and run setup_manual_pkgs.bat.

## Configuring:
1) Setup EQ2 account credentials
into file eq2/configs/credentials.json
```
{
    "login_key_1": {
        "login": "user",
        "password": "password"
    },
    "discord": {
        "channel": 12345,
        "token": "discord bot token"
    },
    "discord-voice": {
        "channel": 12345,
        "token": "discord bot token"
    }
}
```
and delete previous credentials.enc.

2) Setup exeuction hosts
In file eq2/configs/shared/hosts.py, for every host make:
```
host_configs = {
    'MAIN': HostConfig(0, HostRole.Master, HostType.Native, 'C:\\EQ2', beta_path='C:\\EQ2\\BetaServer', secure=True),
    'ALT_1': HostConfig(1, HostRole.Slave, HostType.Native, 'C:\\EQ2'),
    ...
}
```
note the first integer argument - it is host_id, which is later used with Clients.

3) Setup network clients
In file eq2/configs/shared/clients.py, for every player make:
```
client_config_data: List[ClientConfigData] = [
    ClientConfigData(host_id=0,
                     overlay_id=0,
                     client_id='<some_unique_ID>',
                     client_flags=ClientFlags.Local,
                     game_server=GameServer.thurgadin,
                     player_name='<playername>',
                     group_id=Groups.MAIN_1,
                     cred_key='login_key_1',
                     )
    ...
]
```

4) Fill game constants in eq2/configs/shared/game_constants.py
Especially:
```
EQ2_WINDOW_NAME (substring is enough)
EQ2_REMOTE_SLAVE_TOOLBAR_PATH
EQ2_LOCAL_SLAVE_TOOLBAR_PATH
EQ2_LAUNCHER_BATCH_SLAVE_PATH
MONGODB_SERVICE_URI
MONGODB_CERTIFICATE_FILENAME
MONGODB_DATABASE_NAME
CENSUS_SERVICE_NAME
```

6) Configure Players in eq2/configs/master/players.py

6) Configure hotkeys in eq2/configs/master/keyspecs.py

7) Configure guildhalls in eq2/configs/master/guildhalls.py

8) Connect players with hotkey specs in eq2/configs/master/player_controls.py


## Running

```
venv\Scripts\python -m rka.app.starter
```
Master or Slave is automatically detected if hosts are configured properly.
