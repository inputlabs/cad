from pathlib import Path
import math
import bpy

def export(stl_name, obj_names, modifiers, rotation=[0,0,0]):
    # Select objects.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in reversed(bpy.data.objects):
        obj.hide_set(False)
        if obj.name in obj_names:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            # Modifiers.
            for mod in obj.modifiers:
                if 'body_top' in modifiers or 'body_bottom' in modifiers:
                    if obj.name == 'Body' and 'Cut' in mod.name:
                        mod.show_viewport = True
                        mod['Socket_2'] = 'body_top' in modifiers
                        mod['Socket_3'] = 'body_bottom' in modifiers
                if 'grip_left' in modifiers or 'grip_right' in modifiers:
                    if obj.name == 'grip' and 'Cut' in mod.name:
                        mod.show_viewport = True
                        mod['Socket_2'] = 'grip_left' in modifiers
                        mod['Socket_3'] = 'grip_right' in modifiers
                if 'bumper_mirror' in modifiers:
                    if obj.name == 'bumper':
                        obj.scale[0] = -1
                if 'disable_body_pegs' in modifiers:
                    if obj.name == 'Body' and 'Holes' in mod.name:
                        mod.show_viewport = False
    # Export STL.
    root = Path(bpy.path.abspath("//")).parent
    path = root / 'stl' / f'{stl_name}.stl'
    bpy.ops.wm.stl_export(
        filepath=str(path),
        export_selected_objects=True,
        apply_modifiers=True,
        global_rotation=(
            math.radians(rotation[0]),
            math.radians(rotation[1]),
            math.radians(rotation[2]),
        ),
    )

# WARNING:
# All exports are done on the same blender instance, modifiers that are not
# reverted could have an impact on subsequent exports.
bpy.ops.wm.open_mainfile(filepath="kapybara/blender/kapybara.blend")

# Case.
export('case_bottom_right', ['Body', 'trigger', 'bumper', 'home'], ['body_bottom'], [35, 0, 0])
export('case_bottom_left', ['Body', 'trigger', 'bumper', 'home'], ['body_bottom', 'bumper_mirror'])
export('case_top', ['Body', 'thumbstick', 'select', 'wheel'], ['body_top'])
export('case_peg', ['Body peg'], [])

# Grip.
export('grip_half_left', ['grip'], ['grip_left', 'disable_body_pegs'])
export('grip_half_right', ['grip'], ['grip_right', 'disable_body_pegs'])
export('grip_joiner', ['joiner'], [])

