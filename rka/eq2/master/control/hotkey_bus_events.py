from rka.components.events import Events, event


class HotkeyEvents(Events):
    FUNCTION_KEY = event(function_num=int)


if __name__ == '__main__':
    HotkeyEvents.update_stub_file()
