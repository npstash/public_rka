from rka.components.resources import Resource
from rka.components.resources import ResourceBundle


class ROSBundle (ResourceBundle):
	def __init__(self, *args, **kwargs):
		ResourceBundle.__init__(self, *args, **kwargs)

	COLD_CUTTER_1: Resource = None
	COLD_CUTTER_10: Resource = None
	COLD_CUTTER_2: Resource = None
	COLD_CUTTER_3: Resource = None
	COLD_CUTTER_4: Resource = None
	COLD_CUTTER_5: Resource = None
	COLD_CUTTER_6: Resource = None
	COLD_CUTTER_7: Resource = None
	COLD_CUTTER_8: Resource = None
	COLD_CUTTER_9: Resource = None
	MATH_WRATH: Resource = None
