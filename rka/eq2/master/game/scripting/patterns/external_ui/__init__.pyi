from rka.components.resources import Resource
from rka.components.resources import ResourceBundle


class ExternalBundle (ResourceBundle):
	def __init__(self, *args, **kwargs):
		ResourceBundle.__init__(self, *args, **kwargs)

	PATTERN_TV_BUTTON_OK: Resource = None
