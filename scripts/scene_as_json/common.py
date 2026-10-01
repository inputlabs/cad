import mathutils
import re
from types import SimpleNamespace
import bpy

ITERABLE_TYPES = (
    list,
    tuple,
    set,
    mathutils.Euler,
    mathutils.Vector,
    mathutils.Quaternion,
    mathutils.Color,
    mathutils.Matrix,
    bpy.types.bpy_prop_array,
)

def get_type_uname(obj):
    cls = type(obj)
    return f'{cls.__module__}.{cls.__qualname__}'

def dict_to_namespace(d):
    if isinstance(d, dict):
        return SimpleNamespace(**{k: dict_to_namespace(v) for k, v in d.items()})
    elif isinstance(d, list):
        return [dict_to_namespace(item) for item in d]
    elif isinstance(d, tuple):
        return tuple(dict_to_namespace(item) for item in d)
    return d

def parse_value(value):
    if isinstance(value, str) and 'bpy_types.Object' in value:
        return bpy.data.objects.get(value)
    return value

def serialize_value(val):
    if val is None:
        return val
    if isinstance(val, (int, bool, str)):
        return val
    if isinstance(val, float):
        return round(val, 6)
    if hasattr(val, 'to_tuple'):
        return val.to_tuple(3)  # Vectors.
    if hasattr(val, 'to_list'):
        return [serialize_value(x) for x in val.to_list()]
    if hasattr(val, 'to_dict'):
        return {k: serialize_value(v) for k, v in val.to_dict().items()}
    if isinstance(val, ITERABLE_TYPES):
        return [serialize_value(x) for x in val]
    if hasattr(val, 'name'):
        return f'<{get_type_uname(val)}>{val.name}'  # References to data-blocks.
    raise Exception(f"Cannot serialize '{val}'")

def preformat_json(json_string, max_line_chars=100):
    # Join vector arrays in a single line.
    pattern = r'\[\s*([0-9\.,\s\-eE]+?)\s*\]'
    def join_arrays(m):
        single_line = '[' + re.sub(r'\s+', ' ', m.group(1)).strip() + ']'
        # Only if not too long.
        if len(single_line) > max_line_chars:
            return m.group(0)
        return single_line
    return re.sub(pattern, join_arrays, json_string)

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)  # Make sure subfolder exist.
    with open(path, "w", encoding='utf-8') as f:
        f.write(content)
