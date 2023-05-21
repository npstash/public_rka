from typing import List

from rka.eq2.shared import GameServer, ClientFlags, Groups, ClientConfigData

client_config_data: List[ClientConfigData] = [
    ClientConfigData(host_id=0,
                     overlay_id=0,
                     client_id='LOCAL-1',
                     client_flags=ClientFlags.Local,
                     game_server=GameServer.beta,
                     player_name='Playername',
                     group_id=Groups.MAIN_1,
                     cred_key='key0',
                     ),
]
