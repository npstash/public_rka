from rka.components.resources import Resource
from rka.components.resources import ResourceBundle


class DetrimBundle (ResourceBundle):
	def __init__(self, *args, **kwargs):
		ResourceBundle.__init__(self, *args, **kwargs)

	PERSONAL_ICON_CHAOTIC_LEECH: Resource = None
	PERSONAL_ICON_CURSE_1: Resource = None
	PERSONAL_ICON_ELEMENTAL_UNCURABLE: Resource = None
	PERSONAL_ICON_NOXIOUS_UNCURABLE: Resource = None
	PERSONAL_ICON_TRAUMA_UNCURABLE: Resource = None
	RAID_ICON_ARCANE_UNCURABLE: Resource = None
	RAID_ICON_CURSE_1: Resource = None
	RAID_ICON_CURSE_2: Resource = None
	RAID_ICON_CURSE_UNCURABLE: Resource = None
	RAID_ICON_ELEMENTAL_UNCURABLE: Resource = None
	RAID_ICON_NOXIOUS_1: Resource = None
	RAID_ICON_NOXIOUS_UNCURABLE: Resource = None
	RAID_ICON_TRAUMA_UNCURABLE: Resource = None
	RAID_WINDOW_STRIPE: Resource = None
