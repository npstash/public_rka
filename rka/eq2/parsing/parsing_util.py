from datetime import datetime
from time import time
from typing import Optional, Iterable, Tuple

import regex as re

from rka.eq2.parsing import logger

__L = r'\p{L}'
S_POSTFIX = r'(?:s\'|\'s)'
YOU = f'YOU|You|you'
YOUR = f'YOUR|Your|your'
SELF = f'HIMSELF|himself|HERSELF|herself'
__pc_chars = fr'[{__L}]'
__npc_chars = fr'(?:[{__L}\- \'\?]|, )'
__ab_chars = fr'[{__L}\'\- `:\(\)]'
__abpet_chars = fr'[{__L}\'\- `:,]'
__npc_aan = '(?:a|an)'
ANY_PLAYER_G = fr'[A-Z]{__pc_chars}+'
ANY_PLAYER_L = fr'{ANY_PLAYER_G}?'
ANY_PLAYERS = fr'{ANY_PLAYER_G}{S_POSTFIX}'
ANY_NAMED_G = fr'[A-Z]{__npc_chars}+'
ANY_NAMED_L = fr'{ANY_NAMED_G}?'
ANY_NAMEDS = fr'{ANY_NAMED_L}{S_POSTFIX}'
ANY_PET_G = fr'[A-Za-z]{__npc_chars}+'
ANY_PET_L = fr'{ANY_PET_G}?'
ANY_ABILITY_G = fr'[A-Z]{__ab_chars}+'
ANY_ABILITY_L = fr'{ANY_ABILITY_G}?'
ANY_PET_OR_ABILITY_G = fr'{__abpet_chars}+'
ANY_PET_OR_ABILITY_L = fr'{ANY_PET_OR_ABILITY_G}?'
ANY_PLAYER_INCL_YOU_G = fr'(?:{YOU}|{ANY_PLAYER_G})'
ANY_PLAYER_INCL_YOU_L = fr'(?:{YOU}|{ANY_PLAYER_L})'
ANY_PLAYER_INCL_SELF_G = fr'(?:{SELF}|{ANY_PLAYER_G})'
ANY_PLAYERS_INCL_YOUR = fr'(?:{YOUR}|{ANY_PLAYERS})'
ANY_ENEMY_G = fr'(?:{__npc_aan} )?{__npc_chars}+'
ANY_ENEMY_L = fr'{ANY_ENEMY_G}?'
ANY_ENEMYS_L = fr'{ANY_ENEMY_L}{S_POSTFIX}'
ANY_ENEMY_L_OPT_S = fr'{ANY_ENEMY_L}(?:{S_POSTFIX})?'
ANY_ENEMY_G_OPT_S = fr'{ANY_ENEMY_G}(?:{S_POSTFIX})?'
ANY_COMBATANT_G = fr'(?:{YOU}|{ANY_ENEMY_G})'
ANY_COMBATANT_L = fr'(?:{YOU}|{ANY_ENEMY_L})'
ANY_COMBATANTS = fr'(?:{YOUR}|{ANY_ENEMYS_L})'
ANY_COMBATANT_L_OPT_S = fr'(?:{YOUR}|{YOU}|{ANY_ENEMY_L_OPT_S})'
ANY_COMBATANT_G_OPT_S = fr'(?:{YOUR}|{YOU}|{ANY_ENEMY_G_OPT_S})'
COLOR_RE_STR = r'\\#[0-9A-Fa-f]{6}'


class ParsingHelpers:
    @staticmethod
    def is_pet(combatant_name: str) -> bool:
        if re.match(rf'{ANY_PLAYERS} {ANY_PET_G}', combatant_name):
            return True
        return False

    @staticmethod
    def get_pets_owner(combatant_name: str) -> Optional[str]:
        match = re.match(rf'({ANY_PLAYERS}) {ANY_PET_G}', combatant_name)
        if not match:
            return None
        owner_name = match.group(1).replace('\'s', '').replace('s\'', '')
        return owner_name

    @staticmethod
    def is_boss(combatant_name: str) -> bool:
        if not re.match(ANY_NAMED_G, combatant_name):
            return False
        if combatant_name.lower() == 'unknown':
            return False
        return True

    @staticmethod
    def get_canonical_combatant_name(parsing_player_name: str, combatant_name: Optional[str]) -> Tuple[Optional[str], bool]:
        if combatant_name is None:
            return None, False
        cn_lower = combatant_name.lower()
        if combatant_name[0] == 'Y':
            if cn_lower == 'you' or cn_lower == 'your' or cn_lower == 'yourself':
                return parsing_player_name, True
        cn_len = len(combatant_name)
        if cn_len > 3 and cn_lower[:3] == 'an ':
            combatant_name = cn_lower
        elif cn_len > 2 and cn_lower[:2] == 'a ':
            combatant_name = cn_lower
        if cn_len > 2 and combatant_name.endswith('\'s'):
            return combatant_name[:-2], False
        if cn_len > 1 and combatant_name.endswith('s\''):
            return combatant_name[:-1], False
        return combatant_name, False

    @staticmethod
    def get_canonical_player_name(parsing_player_name: str, player_name: str) -> str:
        player_name_lower = player_name.lower()
        if player_name_lower[0] == 'y':
            if player_name_lower == 'you' or player_name_lower == 'your' or player_name_lower == 'yourself':
                return parsing_player_name
        cn_len = len(player_name)
        if cn_len > 2 and player_name.endswith('\'s'):
            return player_name[:-2]
        if cn_len > 1 and player_name.endswith('s\''):
            return player_name[:-1]
        return player_name

    @staticmethod
    def get_canonical_ability_name(effect_name: str) -> str:
        if not effect_name:
            return 'unknown'
        return effect_name.lower().strip()


class EmoteInformation:
    def __init__(self, timestamp: float, readable: str, wildcarded: str):
        self.timestamp = timestamp
        self.readable = readable
        self.wildcarded = wildcarded

    def readable_with_timestamp(self) -> str:
        timestr = datetime.fromtimestamp(self.timestamp).strftime('%m-%d %H:%M:%S')
        readable_form = f'{timestr} {self.readable}'
        return readable_form


class EmoteParser:
    pronouns_1 = ['he', 'she', 'it']
    pronouns_2 = ['him', 'his', 'her', 'its']
    terminators = ['.', ' ', ',', ';', '?', '!', '"', ':']
    invalid_characters = ['#', '"']

    def __init__(self, emote: str):
        self.escaped_emote = ''
        self.readable_emote = ''
        self.emote_idx = 0
        self.emote = emote

    def __is_word_start_possible(self) -> bool:
        if self.emote_idx == 0:
            return True
        # if there is color match before
        if self.emote_idx > 7 and re.match(COLOR_RE_STR, self.emote[self.emote_idx - 8:]):
            return True
        if self.emote[self.emote_idx - 1].isalpha():
            return False
        return True

    def __matches_word(self, word: str, remaining_emote: Optional[str] = None, ignore_case=False, check_capitalized=False) -> bool:
        if not remaining_emote:
            remaining_emote = self.emote[self.emote_idx:]
        matched = False
        if ignore_case:
            word = word.lower()
            remaining_emote = remaining_emote.lower()
        if remaining_emote.startswith(word):
            matched = True
        if not matched and check_capitalized:
            if remaining_emote.startswith(word.upper()):
                matched = True
        if not matched:
            return False
        if self.emote_idx + len(word) == len(self.emote):
            return True
        if self.emote[self.emote_idx + len(word)].isalpha():
            return False
        return True

    def replace_player_combatants(self, player_names: Iterable[str]) -> bool:
        if not self.__is_word_start_possible():
            return False
        substring_replaced = False
        remaining_emote = self.emote[self.emote_idx:]
        for player_name in player_names:
            if not self.__matches_word(player_name, remaining_emote=remaining_emote, ignore_case=False, check_capitalized=True):
                continue
            player_name_s = f'{player_name}\'s'
            player_name_ = f'{player_name}\''
            if remaining_emote.startswith(player_name_s):
                self.escaped_emote += fr'({ANY_PLAYERS_INCL_YOUR})'
                self.readable_emote += '<player\'s>'
                matched_str = player_name_s
            elif remaining_emote.startswith(player_name_):
                self.escaped_emote += fr'({ANY_PLAYERS_INCL_YOUR})'
                self.readable_emote += '<player\'s>'
                matched_str = player_name_
            else:
                self.escaped_emote += fr'({ANY_PLAYER_INCL_YOU_L})'
                self.readable_emote += '<player>'
                matched_str = player_name
            substring_replaced = True
            self.emote_idx += len(matched_str)
            logger.detail(f'Player {matched_str} found in emote, generalized to: {self.escaped_emote}')
            break
        return substring_replaced

    def replace_npc_combatants(self, combatant_names: Iterable[str]) -> bool:
        if not self.__is_word_start_possible():
            return False
        substring_replaced = False
        remaining_emote = self.emote[self.emote_idx:]
        for combatant_name in combatant_names:
            if not combatant_name:
                continue
            if not self.__matches_word(combatant_name, remaining_emote=remaining_emote, ignore_case=False, check_capitalized=True):
                continue
            self.escaped_emote += ANY_NAMED_L
            self.readable_emote += '<boss>'
            self.emote_idx += len(combatant_name)
            substring_replaced = True
            logger.detail(f'Combatant {combatant_name} found in emote, generalized to: {self.escaped_emote}')
            break
        return substring_replaced

    def replace_pronouns(self) -> bool:
        if not self.__is_word_start_possible():
            return False
        substring_replaced = False
        remaining_emote = self.emote[self.emote_idx:]
        pronoun = 'your'
        if self.__matches_word(pronoun, remaining_emote=remaining_emote, ignore_case=True):
            self.escaped_emote += ANY_PLAYERS_INCL_YOUR
            self.readable_emote += '<player\'s>'
            self.emote_idx += len(pronoun)
            substring_replaced = True
            logger.detail(f'\'{pronoun}\' found in emote, generalized to: {self.escaped_emote}')
        if substring_replaced:
            return True
        pronoun = 'you'
        if self.__matches_word(pronoun, remaining_emote=remaining_emote, ignore_case=True):
            self.escaped_emote += ANY_PLAYER_INCL_YOU_L
            self.readable_emote += '<player>'
            self.emote_idx += len(pronoun)
            substring_replaced = True
            logger.detail(f'\'{pronoun}\' found in emote, generalized to: {self.escaped_emote}')
        if substring_replaced:
            return True
        for pronouns in (EmoteParser.pronouns_1, EmoteParser.pronouns_2):
            for pronoun in pronouns:
                if self.__matches_word(pronoun, ignore_case=True):
                    repl_str = '|'.join(pronouns)
                    self.escaped_emote += f'(?i:{repl_str})'
                    self.readable_emote += pronoun
                    self.emote_idx += len(pronoun)
                    substring_replaced = True
                    logger.detail(f'\'{pronoun}\' found in emote, generalized to: {self.escaped_emote}')
                    break
        return substring_replaced

    def replace_color(self) -> bool:
        remaining_emote = self.emote[self.emote_idx:]
        color_match = re.match(COLOR_RE_STR, remaining_emote)
        if color_match:
            self.escaped_emote += COLOR_RE_STR
            self.readable_emote += '#'
            color_str = color_match.group(0)
            self.emote_idx += len(color_str)
            logger.detail(f'Color {color_str} found in emote, generalized to: {self.escaped_emote}')
            return True
        return False

    def replace_numbers(self) -> bool:
        remaining_emote = self.emote[self.emote_idx:]
        digits_match = re.match(r'\d+', remaining_emote)
        if digits_match:
            self.escaped_emote += r'\d+'
            self.readable_emote += '<X>'
            self.emote_idx += len(digits_match.group(0))
            logger.detail(f'Digits {digits_match.group(0)} found in emote, generalized to: {self.escaped_emote}')
            return True
        return False

    def replace_other(self) -> bool:
        char_to_replace = self.emote[self.emote_idx]
        if char_to_replace in EmoteParser.invalid_characters:
            self.escaped_emote += '.'
            self.readable_emote += char_to_replace
            self.emote_idx += 1
            logger.detail(f'Character {char_to_replace} replaced')
            return True
        return False

    def escape_next_character(self):
        char_to_escape = self.emote[self.emote_idx]
        if char_to_escape != ' ':
            self.escaped_emote += re.escape(char_to_escape)
        else:
            self.escaped_emote += ' '
        self.readable_emote += char_to_escape
        self.emote_idx += 1

    def finish(self) -> EmoteInformation:
        self.escaped_emote += '$'
        return EmoteInformation(timestamp=time(), readable=self.readable_emote, wildcarded=self.escaped_emote)
