from rka.components.events import event, Events
from rka.eq2.master.parsing import CTConfirmRule
from rka.eq2.master.parsing import CombatantType


class CombatParserEvents(Events):
    # events from DPS parser
    DPS_PARSE_START = event(attacker_name=str, target_name=str, timestamp=float)
    DPS_PARSE_TICK = event(combat_flag=bool)
    DPS_PARSE_END = event(timestamp=float)
    COMBATANT_CONFIRMED = event(combatant_name=str, combatant_type=CombatantType, confirm_rule=CTConfirmRule)
    COMBAT_HIT = event(attacker_name=str, attacker_type=int, target_name=str, target_type=int,
                       ability_name=str, damage=int, damage_type=str,
                       is_autoattack=bool, is_drain=bool, is_multi=bool, is_dot=bool, is_aoe=bool,
                       timestamp=float)
    DETRIMENT_RELIEVED = event(by_combatant=str, by_combatant_type=int, from_combatant=str, from_combatant_type=int,
                               ability_name=str, detriment_name=str, is_curse=bool)
    EFFECT_DISPELLED = event(by_combatant=str, by_combatant_type=int, from_combatant=str, from_combatant_type=int,
                             ability_name=str, effect_name=str)
    WARD_EXPIRED = event(caster_name=str, caster_type=int, target_name=str, target_type=int, ability_name=str, timestamp=float)
    CRITICAL_STONESKIN = event(amount=int, amount_readable=str)
    PLAYER_INTERRUPTED = event(player_name=str)


if __name__ == '__main__':
    CombatParserEvents.update_stub_file()
