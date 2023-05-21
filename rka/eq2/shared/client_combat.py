from rka.components.events import Events
from rka.eq2.shared.client_event import client_event


class ClientCombatParserEvents(Events):
    COMBAT_PARSE_START = client_event(client_id=str, timestamp=float)
    COMBAT_PARSE_TICK = client_event(client_id=str, combat_flag=bool, timestamp=float)
    COMBAT_PARSE_END = client_event(client_id=str, timestamp=float)
    COMBATANT_JOINED = client_event(client_id=str, combatant_name=str, timestamp=float)


if __name__ == '__main__':
    ClientCombatParserEvents.update_stub_file()
