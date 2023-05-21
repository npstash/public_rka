from rka.components.resources import Resource
from rka.components.resources import ResourceBundle


class CraftBundle (ResourceBundle):
	def __init__(self, *args, **kwargs):
		ResourceBundle.__init__(self, *args, **kwargs)

	PATTERN_BUTTON_BEGIN: Resource = None
	PATTERN_BUTTON_CREATE: Resource = None
	PATTERN_BUTTON_FIND_RECIPE: Resource = None
	PATTERN_DIALOG_I_HAVE_MY_ASSIGNED_TASK: Resource = None
	PATTERN_DIALOG_I_WOULD_LIKE_A_WRIT: Resource = None
	PATTERN_DIALOG_TAKE_INVOICE: Resource = None
	PATTERN_DIALOG_THANK_YOU_I_WILL_GET: Resource = None
	PATTERN_GFX_CRAFTING_BOOK: Resource = None
	PATTERN_GFX_CRAFT_QUANTITY_1: Resource = None
	PATTERN_GFX_CRAFT_QUANTITY_DROPDOWN_10: Resource = None
	PATTERN_GFX_DIFFICULTY: Resource = None
	PATTERN_GFX_PRISTINE_ITEM: Resource = None
	PATTERN_GFX_RUSH: Resource = None
	PATTERN_GFX_START_CRAFTING: Resource = None
	PATTERN_GFX_STOP_CRAFTING: Resource = None
	PATTERN_GFX_TASKBOARD_1: Resource = None
	PATTERN_GFX_TASKBOARD_10: Resource = None
	PATTERN_GFX_TASKBOARD_11: Resource = None
	PATTERN_GFX_TASKBOARD_12: Resource = None
	PATTERN_GFX_TASKBOARD_13: Resource = None
	PATTERN_GFX_TASKBOARD_14: Resource = None
	PATTERN_GFX_TASKBOARD_15: Resource = None
	PATTERN_GFX_TASKBOARD_16: Resource = None
	PATTERN_GFX_TASKBOARD_17: Resource = None
	PATTERN_GFX_TASKBOARD_18: Resource = None
	PATTERN_GFX_TASKBOARD_19: Resource = None
	PATTERN_GFX_TASKBOARD_2: Resource = None
	PATTERN_GFX_TASKBOARD_20: Resource = None
	PATTERN_GFX_TASKBOARD_3: Resource = None
	PATTERN_GFX_TASKBOARD_4: Resource = None
	PATTERN_GFX_TASKBOARD_5: Resource = None
	PATTERN_GFX_TASKBOARD_6: Resource = None
	PATTERN_GFX_TASKBOARD_7: Resource = None
	PATTERN_GFX_TASKBOARD_8: Resource = None
	PATTERN_GFX_TASKBOARD_9: Resource = None
	PATTERN_GFX_TRIVIAL_1: Resource = None
