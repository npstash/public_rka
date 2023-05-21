import xml
from xml.dom.minidom import Element

from rka.eq2.master.game import get_canonical_zone_name, get_canonical_zone_name_with_tier, is_unknown_zone
from rka.eq2.master.game.interfaces import IPlayer
from rka.eq2.master.game.player import PlayerStatus
from rka.eq2.parsing.parsing_util import ANY_NAMED_G, ANY_NAMED_L, ANY_COMBATANT_G

ALL_YOU_STRS_LOWER = {'you', 'your', 'yourself', 'yours'}


class TriggerUtil:
    @staticmethod
    def regex_for_any_named_color_g1() -> str:
        col = r'\\#[0-9A-Fa-f]{6}'
        result = f'{col}({ANY_NAMED_L})'
        return result

    @staticmethod
    def regex_for_color_emote(emote: str) -> str:
        col = r'\\#[0-9A-Fa-f]{6}'
        result = f'(?:{col}){emote}'
        return result

    @staticmethod
    def regex_for_named_opt_color(named: str) -> str:
        col = r'\\#[0-9A-Fa-f]{6}'
        result = f'(?:{col})?{named}'
        return result

    @staticmethod
    def regex_for_any_named_anpc_g1() -> str:
        result = rf'\\aNPC -?\d+ ({ANY_NAMED_G}):\1\\/a'
        return result

    @staticmethod
    def regex_for_any_combatant_anpc_g1() -> str:
        result = rf'\\aNPC -?\d+ ({ANY_COMBATANT_G}):\1\\/a'
        return result

    @staticmethod
    def regex_for_player_names(players: [IPlayer], status=PlayerStatus.Offline) -> str:
        player_names = '|'.join([player.get_player_name() for player in players if player.get_status() >= status])
        return player_names

    @staticmethod
    def compare_zones(actual_zone: str, reference_zone: str, ignore_tier: bool) -> bool:
        if is_unknown_zone(actual_zone) or is_unknown_zone(reference_zone):
            return False
        if ignore_tier:
            canonical_actual_zone = get_canonical_zone_name(actual_zone)
            canonical_reference_zone = get_canonical_zone_name(reference_zone)
        else:
            canonical_actual_zone = get_canonical_zone_name_with_tier(actual_zone)
            canonical_reference_zone = get_canonical_zone_name_with_tier(reference_zone)
        return canonical_actual_zone == canonical_reference_zone

    @staticmethod
    def is_you(playerstr: str) -> bool:
        playerstr_lower = playerstr.lower()
        if not playerstr_lower.startswith('you'):
            return False
        return playerstr_lower in ALL_YOU_STRS_LOWER

    @staticmethod
    def strip_s(player_s: str):
        if player_s.endswith('\'s'):
            return player_s[:-2]
        if player_s.endswith('s\''):
            return player_s[:-1]
        return player_s


class ACTXMLElement(Element):
    def __init__(self, tag_name):
        Element.__init__(self, tagName=tag_name)

    def writexml(self, writer, indent="", addindent="", newl=""):
        # indent = current indentation
        # addindent = indentation to add to higher levels
        # newl = newline string
        writer.write(indent + "<" + self.tagName)

        attrs = self._get_attributes()
        a_names = attrs.keys()

        for a_name in a_names:
            writer.write(" %s=\"" % a_name)
            # noinspection PyProtectedMember
            xml.dom.minidom._write_data(writer, attrs[a_name].value)
            writer.write("\"")
        if self.childNodes:
            writer.write(">")
            if (len(self.childNodes) == 1 and
                    self.childNodes[0].nodeType == xml.dom.minidom.Node.TEXT_NODE):
                self.childNodes[0].writexml(writer, '', '', '')
            else:
                writer.write(newl)
                for node in self.childNodes:
                    node.writexml(writer, indent + addindent, addindent, newl)
                writer.write(indent)
            writer.write("</%s>%s" % (self.tagName, newl))
        else:
            # noinspection PyRedundantParentheses
            writer.write("/>%s" % (newl))
