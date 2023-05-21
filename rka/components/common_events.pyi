from typing import Optional, Type
from rka.components.events import Event


class CommonEvents:
	# noinspection PyPep8Naming
	class FLAG_CHANGED(Event):
		flag_name: Optional[str]
		new_value: Optional[bool]

		# noinspection PyMissingConstructor
		def __init__(self, flag_name: Optional[str] = None, new_value: Optional[bool] = None): ...

	# noinspection PyPep8Naming
	class RESOURCE_BUNDLE_ADDED(Event):
		bundle_id: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, bundle_id: Optional[str] = None): ...

	# noinspection PyPep8Naming
	class RESOURCE_BUNDLE_REMOVED(Event):
		bundle_id: Optional[str]

		# noinspection PyMissingConstructor
		def __init__(self, bundle_id: Optional[str] = None): ...

	@staticmethod
	def get_by_name(event_name: str) -> Type[Event]: ...

	@staticmethod
	def contains(event_name: str) -> bool: ...

	@staticmethod
	def update_stub_file(): ...

