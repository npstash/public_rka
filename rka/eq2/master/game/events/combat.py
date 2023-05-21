from rka.components.events import event, Events
from rka.eq2.master.game.engine import HOStage
from rka.eq2.master.game.interfaces import IPlayer


class CombatEvents(Events):
    ENEMY_KILL = event(killer_name=str, enemy_name=str, killer_you=bool)
    READYUP = event(player=IPlayer)
    PLAYER_DIED = event(player=IPlayer)
    PLAYER_DEATHSAVED = event(player=IPlayer)
    PLAYER_REVIVED = event(player=IPlayer)

    # Balanced Synergy
    PLAYER_SYNERGIZED = event(caster_name=str, my_player=bool, reported_by_player=IPlayer)
    PLAYER_SYNERGY_FADES = event(caster_name=str, my_player=bool, reported_by_player=IPlayer)
    GROUP_SYNERGY_COMPLETED = event(reported_by_player=IPlayer)

    # Barrage and Bulwark of Order
    BARRAGE_READIED = event(caster_name=str)
    BARRAGE_PREPARED = event(caster_name=str, target_name=str, your_group=bool)
    BARRAGE_CANCELLED = event(caster_name=str)
    BARRAGE_RELEASED = event(caster_name=str, target_name=str)
    BULWARK_APPLIED = event(applied_by=str, timestamp=float)

    # Heroic Opportunity
    HO_CHAIN_STARTED = event(caster_name=str)
    HO_CHAIN_BROKEN = event(caster_name=str)
    HO_TRIGGERED = event(caster_name=str, ho_name=str)
    HO_ADVANCED = event(caster_name=str, ho_name=str)
    HO_COMPLETED = event(caster_name=str, ho_name=str)
    HO_STAGE_CHANGED = event(ho_name=str, caster_name=str, new_stage=HOStage, advances=int, hint=str)


if __name__ == '__main__':
    CombatEvents.update_stub_file()
