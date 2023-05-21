from rka.components.resources import Resource
from rka.components.resources import ResourceBundle


class VOVBundle (ResourceBundle):
	def __init__(self, *args, **kwargs):
		ResourceBundle.__init__(self, *args, **kwargs)

	ANASHTI_SUL_UNDYING_BLESSING: Resource = None
	ARCH_ENEMY_BLUE: Resource = None
	ARCH_ENEMY_RED: Resource = None
	ARCH_ENEMY_YELLOW: Resource = None
	CASTING_BAR_WING_BEAT: Resource = None
	DEATH_SENTENCE: Resource = None
	EMBRACE_THE_POWER: Resource = None
	ETERNAL_WATERS: Resource = None
	JUGULAR: Resource = None
	LIBANT_DECREE: Resource = None
	MAYONG_EMPOWERED_ABSORBTION_1: Resource = None
	MAYONG_EMPOWERED_ABSORBTION_2: Resource = None
	MAYONG_JOUST_CURSE: Resource = None
	MELODIC_DISTRACTION: Resource = None
	MIRACLE_OF_UNLIFE: Resource = None
	REJOICE_IN_HER_POWER: Resource = None
	SPELL_SANCTIONS: Resource = None
	VENRIL_KNEW_THE_POWER: Resource = None
