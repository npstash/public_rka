from rka.components.events import event, Events
from rka.eq2.master.game.effect import EffectType, EffectScopeType
from rka.eq2.master.game.interfaces import IPlayer, IEffect, IAbility
from rka.eq2.master.game.player import PlayerStatus


class ObjectStateEvents(Events):
    # the total combat state (from combatstate)
    COMBAT_STATE_START = event()
    COMBAT_STATE_END = event()

    # ability state change
    ABILITY_EXPIRED = event(ability=IAbility, ability_name=str, ability_shared_key=str, ability_unique_key=str, ability_variant_key=str)
    ABILITY_CASTING_CONFIRMED = event(ability=IAbility, ability_name=str, ability_shared_key=str, ability_unique_key=str, ability_variant_key=str)

    # player state change
    PLAYER_STATUS_CHANGED = event(player=IPlayer, from_status=PlayerStatus, to_status=PlayerStatus)

    # effect state change
    EFFECT_STARTED = event(effect_type=EffectType, effect_scope_type=EffectScopeType, effect=IEffect)
    EFFECT_CANCELLED = event(effect_type=EffectType, effect_scope_type=EffectScopeType, effect=IEffect)


if __name__ == '__main__':
    ObjectStateEvents.update_stub_file()
