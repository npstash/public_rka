import sys


def reload_modules():
    module_names = list(sys.modules.keys())
    for module_name in module_names:
        if not module_name.startswith('rka'):
            continue
        print(f'Reloading {module_name}', file=sys.stderr)
        del sys.modules[module_name]
    from rka.app.starter import Starter
    starter = Starter()
    starter.launch_application()
    starter.run_command_console()
