from rka.components.resources import Resource
from rka.components.resources import ResourceBundle


class UIBundle (ResourceBundle):
	def __init__(self, *args, **kwargs):
		ResourceBundle.__init__(self, *args, **kwargs)

	PATTERN_BUTTON_1000_PLAT: Resource = None
	PATTERN_BUTTON_ADD_STEP: Resource = None
	PATTERN_BUTTON_BUY_BROKER: Resource = None
	PATTERN_BUTTON_BUY_MERCHANT: Resource = None
	PATTERN_BUTTON_BUY_ONE: Resource = None
	PATTERN_BUTTON_CANCEL: Resource = None
	PATTERN_BUTTON_CLOSE: Resource = None
	PATTERN_BUTTON_DESTROY: Resource = None
	PATTERN_BUTTON_EQ2_MENU: Resource = None
	PATTERN_BUTTON_FIND_BROKER: Resource = None
	PATTERN_BUTTON_GUILD_PORTAL_CANCEL: Resource = None
	PATTERN_BUTTON_LOGIN: Resource = None
	PATTERN_BUTTON_LOGIN_PRESSED: Resource = None
	PATTERN_BUTTON_MACRO_OK: Resource = None
	PATTERN_BUTTON_O: Resource = None
	PATTERN_BUTTON_PLAY: Resource = None
	PATTERN_BUTTON_REPAIR_ALL: Resource = None
	PATTERN_BUTTON_REVIVE: Resource = None
	PATTERN_BUTTON_TEXT_ACCEPT: Resource = None
	PATTERN_BUTTON_TEXT_CANCEL_SMALL: Resource = None
	PATTERN_BUTTON_TEXT_OK: Resource = None
	PATTERN_BUTTON_TEXT_OK_UPPERCASE: Resource = None
	PATTERN_BUTTON_TEXT_OK_UPPERCASE_SMALL: Resource = None
	PATTERN_BUTTON_TEXT_YES: Resource = None
	PATTERN_BUTTON_X: Resource = None
	PATTERN_FIELD_ANY: Resource = None
	PATTERN_FIELD_CHARNAME: Resource = None
	PATTERN_FIELD_MACRO_COMMAND: Resource = None
	PATTERN_FIELD_MACRO_NAME: Resource = None
	PATTERN_FIELD_PASSWORD: Resource = None
	PATTERN_FIELD_USERNAME: Resource = None
	PATTERN_FIELD_WORLD: Resource = None
	PATTERN_GFX_0_PLAT_COIN: Resource = None
	PATTERN_GFX_ALL_ACCESS: Resource = None
	PATTERN_GFX_ALL_ACCESS_SMALL: Resource = None
	PATTERN_GFX_CHARACTER_EQUIPMENT: Resource = None
	PATTERN_GFX_EVERQUEST_II_LOADING: Resource = None
	PATTERN_GFX_SCROLLDOWN: Resource = None
	PATTERN_GFX_SCROLLUP: Resource = None
	PATTERN_GFX_SELECT_DESTINATION: Resource = None
	PATTERN_ITEM_MENU_ADDTOCOLLECTION: Resource = None
	PATTERN_ITEM_MENU_CONVERTAGENT: Resource = None
	PATTERN_ITEM_MENU_DESTROY: Resource = None
	PATTERN_ITEM_MENU_EQUIP: Resource = None
	PATTERN_ITEM_MENU_EXAMINE: Resource = None
	PATTERN_ITEM_MENU_INFUSE: Resource = None
	PATTERN_ITEM_MENU_SCRIBE: Resource = None
	PATTERN_ITEM_MENU_UNPACK: Resource = None
	PATTERN_ITEM_MENU_USE: Resource = None
	PATTERN_PLAYER_MENU_TRADE: Resource = None
	PATTERN_SEARCH_BUY: Resource = None
	PATTERN_SEARCH_RECIPE: Resource = None
	PATTERN_TAB_BUY: Resource = None
	PATTERN_TAB_CRAFT: Resource = None
	PATTERN_TAB_QUESTS: Resource = None
	PATTERN_TAB_TRADE: Resource = None
	RAID_WND_ARCHETYPE_ICON_FIGHTER: Resource = None
	RAID_WND_ARCHETYPE_ICON_MAGE: Resource = None
	RAID_WND_ARCHETYPE_ICON_PRIEST: Resource = None
	RAID_WND_ARCHETYPE_ICON_SCOUT: Resource = None
