from rka.components.events import event, Events


class CommonEvents(Events):
    FLAG_CHANGED = event(flag_name=str, new_value=bool)
    RESOURCE_BUNDLE_ADDED = event(bundle_id=str)
    RESOURCE_BUNDLE_REMOVED = event(bundle_id=str)


if __name__ == '__main__':
    CommonEvents.update_stub_file()
