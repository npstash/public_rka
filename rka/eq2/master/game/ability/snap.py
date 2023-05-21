from rka.eq2.master.game.interfaces import IAbility


class AbilitySnapshot:
    cached_methods = {
        IAbility.get_priority.__name__,
        IAbility.get_casting_secs.__name__,
        IAbility.get_recovery_secs.__name__,
        IAbility.get_casting_with_recovery_secs.__name__,
        IAbility.get_duration_secs.__name__,
        IAbility.get_reuse_secs.__name__,
        IAbility.get_remaining_duration_sec.__name__,
        IAbility.get_remaining_reuse_wait_td.__name__,
        IAbility.is_casting.__name__,
        IAbility.is_recovering.__name__,
        IAbility.is_after_recovery.__name__,
        IAbility.is_duration_expired.__name__,
        IAbility.is_reusable_and_duration_expired.__name__,
        IAbility.is_reusable.__name__,
        IAbility.is_reuse_expired.__name__,
    }

    def __init__(self, ability: IAbility):
        assert not isinstance(ability, AbilitySnapshot)
        self.ability = ability
        self.__cached_results = dict()

    def __eq__(self, other):
        assert False

    def __getattr__(self, item: str):
        if item in AbilitySnapshot.cached_methods:
            def cache_getter(*args):
                if item not in self.__cached_results:
                    self.__cached_results[item] = getattr(self.ability, item)(*args)
                return self.__cached_results[item]

            return cache_getter

        if not item.startswith('_') and hasattr(self.ability, item):
            attr = getattr(self.ability, item)
            return attr

        raise AttributeError

    def unwrap(self) -> IAbility:
        ability = self.ability
        while isinstance(ability, AbilitySnapshot):
            ability = ability.ability
        return ability
