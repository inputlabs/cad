import sys
import importlib

# Allow development hot-reload.
extension_prefix = __name__ + "."
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith(extension_prefix) and sys.modules[mod_name]:
        importlib.reload(sys.modules[mod_name])

from .register import register, unregister

if __name__ == "__main__":
    register()
