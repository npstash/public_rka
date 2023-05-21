from threading import RLock
from typing import Optional, Generator, Tuple

from rka.components.ui.capture import Point, CaptureArea
from rka.eq2.master.game.player import CharacterGearSlots
from rka.eq2.master.game.scripting import RepeatMode
from rka.eq2.master.game.scripting.patterns.default_ui.bundle import ui_patterns
from rka.eq2.master.game.scripting.procedures.items import ActionOnItemInBagProcedure
from rka.eq2.master.game.scripting.scripts import logger
from rka.eq2.master.game.scripting.toolkit import PlayerScriptingToolkit, Procedure


class UseItemOnEquippedItemProcedure(Procedure):
    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)

    def __get_equipment_window_start(self) -> Optional[Point]:
        window_area = CaptureArea()
        result = self._get_player_toolkit().find_match_by_tag(pattern_tag=ui_patterns.PATTERN_GFX_CHARACTER_EQUIPMENT,
                                                              area=window_area, repeat=RepeatMode.DONT_REPEAT)
        if not result:
            return None
        equipment_window_start = Point(x=result.x1 + (338 - 185), y=result.y1 + (129 - 125))
        return equipment_window_start

    def toggle_character_screen(self):
        # dont use toolkit, script may be expired
        self._get_player().get_inputs().special.open_character.call_action(self._get_player().get_client_id())

    def open_character_and_apply_item(self, slots: Generator[Tuple[int, CharacterGearSlots], None, None], use_time: float) -> bool:
        try:
            latency_delay = 1.0 if self._get_player().is_remote() else 0.1
            self.toggle_character_screen()
            # wait for window to pop up
            self._get_player_toolkit().sleep(1.0 + latency_delay)
            # find window location
            window_start = self.__get_equipment_window_start()
            if not window_start:
                logger.warn('Could not open character window')
                return False
            slot_size_x = 47
            slot_size_y = 46
            for item_id, slot in slots:
                logger.info(f'Apply {item_id} on {slot} for {self._get_player().get_player_name()}')
                # slot location using slot size including padding
                x = window_start.x + slot.column() * slot_size_x + slot_size_x // 2
                y = window_start.y + slot.row() * slot_size_y + slot_size_y // 2
                use_action = self._get_player_toolkit().build_command(f'use_itemvdl {item_id}')
                self._get_player_toolkit().call_player_action(use_action, delay=0.3)
                self._get_player_toolkit().click_at(x, y, delay=0.7)
                self._get_player_toolkit().move_mouse_to_middle()
                self._get_player_toolkit().try_click_ok()
                self._get_player_toolkit().sleep(use_time)
        finally:
            self.toggle_character_screen()
        return True


class ApplyAdornsProcedure(Procedure):
    CRAFTED_ADORN_SLOTS_CB = [
        CharacterGearSlots.head, CharacterGearSlots.shoulder, CharacterGearSlots.chest,
        CharacterGearSlots.forearms, CharacterGearSlots.hands, CharacterGearSlots.legs,
        CharacterGearSlots.feet, CharacterGearSlots.primary, CharacterGearSlots.secondary,
    ]
    CRAFTED_ADORN_SLOTS_POT = [
        CharacterGearSlots.head, CharacterGearSlots.shoulder, CharacterGearSlots.chest,
        CharacterGearSlots.forearms, CharacterGearSlots.hands, CharacterGearSlots.legs,
        CharacterGearSlots.feet, CharacterGearSlots.primary, CharacterGearSlots.secondary,
        CharacterGearSlots.ring_left, CharacterGearSlots.ring_right, CharacterGearSlots.cloak,
    ]
    CRAFTED_ADORN_SLOTS_HP = [
        CharacterGearSlots.head, CharacterGearSlots.shoulder, CharacterGearSlots.chest,
        CharacterGearSlots.primary, CharacterGearSlots.secondary,
        CharacterGearSlots.wrist_left, CharacterGearSlots.wrist_right, CharacterGearSlots.waist,
    ]

    CRAFTED_ADORN_QUIALITY = [
        'Void Etched',
        'True Blood',
        'Bloodbound',
        'Dreadfell',
        'Forlorn',
    ]

    CRAFTED_ADORN_DURATION = [
        'Maintained',
        'Extended',
    ]

    ADORN_SLOT_MAP = {
        # CB
        '{duration} {quality} Injector': (CRAFTED_ADORN_SLOTS_CB, CRAFTED_ADORN_QUIALITY, CRAFTED_ADORN_DURATION),
        # POT
        '{duration} {quality} Insight': (CRAFTED_ADORN_SLOTS_POT, CRAFTED_ADORN_QUIALITY, CRAFTED_ADORN_DURATION),
        # HP
        '{duration} {quality} Coating': (CRAFTED_ADORN_SLOTS_HP, CRAFTED_ADORN_QUIALITY, CRAFTED_ADORN_DURATION),
    }

    ADORN_USE_TIME = 1.3

    item_name_to_id_lock = RLock()

    def __init__(self, scripting: PlayerScriptingToolkit):
        Procedure.__init__(self, scripting)
        self.__use_time = ApplyAdornsProcedure.ADORN_USE_TIME

    def find_adorn_names(self) -> Generator[Tuple[str, CharacterGearSlots], None, None]:
        adorns_found_in_bags = dict()
        item_clicker = ActionOnItemInBagProcedure(self._get_player_toolkit())
        for slot in CharacterGearSlots:
            adorn_found = False
            for adorn_name_template, (slots, qualities, durations) in ApplyAdornsProcedure.ADORN_SLOT_MAP.items():
                if slot not in slots:
                    continue
                for duration in durations:
                    for quality in qualities:
                        adorn_name = adorn_name_template.format(duration=duration, quality=quality)
                        if adorn_name in adorns_found_in_bags and not adorns_found_in_bags[adorn_name]:
                            # already tried this adorn, not in bags
                            continue
                        item_location = item_clicker.find_item_in_bags(adorn_name)
                        if not item_location:
                            adorns_found_in_bags[adorn_name] = False
                            continue
                        adorns_found_in_bags[adorn_name] = True
                        adorn_found = True
                        yield adorn_name, slot
                        break
                    if adorn_found:
                        break
                if adorn_found:
                    break

    def get_adorn_id(self, adorn_name: str) -> int:
        with ApplyAdornsProcedure.item_name_to_id_lock:
            item_id = self._get_runtime().census_cache.get_item_id(adorn_name)
            logger.info(f'ID of {adorn_name} = {item_id}')
            return item_id

    def find_adorn_ids(self) -> Generator[Tuple[int, CharacterGearSlots], None, None]:
        for adorn_name, slot in self.find_adorn_names():
            adorn_id = self.get_adorn_id(adorn_name)
            yield adorn_id, slot

    def apply_adorns(self):
        item_clicker = UseItemOnEquippedItemProcedure(self._get_player_toolkit())
        item_clicker.open_character_and_apply_item(self.find_adorn_ids(), use_time=self.__use_time)
