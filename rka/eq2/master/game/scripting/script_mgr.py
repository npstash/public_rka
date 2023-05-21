from typing import Type, Dict, List, Union, Optional

from rka.eq2.master.game.scripting.categories import ScriptCategory
from rka.eq2.master.game.scripting.script_task import ScriptTask


class RegisteredGameScript:
    def __init__(self, name: str, category: ScriptCategory, clazz: Type[ScriptTask]):
        self.name = name
        self.category = category
        self.clazz = clazz

    def create(self, *args, **kwargs) -> ScriptTask:
        script = self.clazz(*args, **kwargs)
        script.set_default_description(self.name)
        return script


class GameScriptManager:
    registered_game_scripts: Dict[ScriptCategory, List[RegisteredGameScript]] = dict()

    @staticmethod
    def register_game_script(categories: Union[ScriptCategory, List[ScriptCategory]], description: Optional[str] = None):
        if isinstance(categories, ScriptCategory):
            categories = [categories]
        assert isinstance(categories, List)

        def combat_script_register_fn(clazz: Type[ScriptTask]):
            assert issubclass(clazz, ScriptTask), clazz
            description_local = description
            if not description_local:
                description_local = clazz.__name__
            for category in categories:
                if category not in GameScriptManager.registered_game_scripts:
                    GameScriptManager.registered_game_scripts[category] = list()
                assert description_local not in GameScriptManager.registered_game_scripts[category], description_local
                record = RegisteredGameScript(description_local, category, clazz)
                GameScriptManager.registered_game_scripts[category].append(record)
            return clazz

        return combat_script_register_fn

    # noinspection PyUnresolvedReferences
    @staticmethod
    def __load_scripts():
        # make sure necessary scripts are registered by just importing them - they self-register
        import rka.eq2.master.game.scripting.scripts.combat_monitoring_scripts
        import rka.eq2.master.game.scripting.scripts.game_command_scripts
        import rka.eq2.master.game.scripting.scripts.host_control_scripts
        import rka.eq2.master.game.scripting.scripts.inventory_scripts
        import rka.eq2.master.game.scripting.scripts.location_scripts
        import rka.eq2.master.game.scripting.scripts.movement_scripts
        import rka.eq2.master.game.scripting.scripts.ooz_control_scripts
        import rka.eq2.master.game.scripting.scripts.overseer_scripts
        import rka.eq2.master.game.scripting.scripts.player_state_scripts
        import rka.eq2.master.game.scripting.scripts.test_scripts
        import rka.eq2.master.game.scripting.scripts.tradeskill_scripts
        import rka.eq2.master.game.scripting.scripts.ui_interaction_scripts

    @staticmethod
    def get_game_scripts(category: ScriptCategory) -> List[RegisteredGameScript]:
        GameScriptManager.__load_scripts()
        if category not in GameScriptManager.registered_game_scripts:
            return []
        return list(GameScriptManager.registered_game_scripts[category])
