import math
import mathutils
import json
from pathlib import Path
from types import SimpleNamespace

import bpy
from .common import write_file, dict_to_namespace
from .node import serialize_nodegroup, create_nodegroup
from .object import (
    get_object,
    get_object_path,
    serialize_object,
    create_object,
    create_modifier,
    mesh_to_gltf,
)

def export_scene(log, folder):
    folder = Path(folder)
    objs = list(bpy.context.scene.collection.all_objects)
    for obj in objs:
        obj_json, export_mesh = serialize_object(log, obj)
        obj_path = folder / f'{get_object_path(obj)}.json'
        write_file(obj_path, obj_json)
        if export_mesh:
            pass  # This is very buggy in Blender 5.2 / doing exports manually for now.
            # glb_path = folder / '_big_mesh' / f'{obj.name}.glb'
            # mesh_to_gltf(log, obj, glb_path)
    for nodegroup in bpy.data.node_groups:
        if nodegroup.library:  # Ignore built-in or external node groups.
            continue
        ng_json = serialize_nodegroup(log, nodegroup)
        ng_path = folder / '_geometry_nodes' / f'{nodegroup.name}.json'
        write_file(ng_path, ng_json)

def import_scene(log, folder):
    folder = Path(folder)
    clear_scene()
    set_scene()
    json_objects = {}
    # Parse files.
    for json_path in folder.rglob('*.json'):
        log(f'Parse {json_path}')
        with json_path.open('r', encoding='utf-8') as json_file:
            data = dict_to_namespace(json.load(json_file))
            data_path = json_path.relative_to(folder).with_suffix('')
            json_objects[data_path] = data
    # Recreate nodegroups.
    for data_path, data in json_objects.items():
        root = data_path.parts[0]
        name = data_path.parts[-1]
        if root == '_geometry_nodes':
            create_nodegroup(log, name, data)
    # Recreate objects.
    for data_path, data in json_objects.items():
        root = data_path.parts[0]
        if not root.startswith('_'):
            create_object(log, folder, data_path, data)
    # Recreate modifiers (all objects can be cross-linked).
    for data_path, data in json_objects.items():
        root = data_path.parts[0]
        name = data_path.parts[-1]
        if not root.startswith('_'):
            obj = get_object(name)
            if hasattr(data, 'modifiers'):
                for modifier_data in data.modifiers:
                    create_modifier(log, obj, modifier_data)

def clear_scene():
    # Delete all objects.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    # Delete all collections.
    for collection in list(bpy.data.collections):
            bpy.data.collections.remove(collection)
    # Clean up orphan data blocks.
    data_blocks = [
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.textures,
        bpy.data.images,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.curves,
    ]
    for data_type in data_blocks:
        for block in list(data_type):
            if block.users == 0:
                data_type.remove(block)

def set_scene():
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    scene.unit_settings.scale_length = 0.001
    # Set tab.
    modeling = bpy.data.workspaces.get("Modeling")
    window = bpy.context.window
    window.workspace = modeling  # Set active.
    # View settings.
    for screen in modeling.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                # Distance and position.
                rv3d = area.spaces.active.region_3d
                rv3d.view_location = mathutils.Vector((0.0, 0.0, 0.0))
                rv3d.view_distance = 250.0
                # Rotation.
                region = next(
                    (r for r in area.regions if r.type == 'WINDOW'),
                    area.regions[-1],
                )
                params = dict(window=window, screen=screen, area=area, region=region)
                with bpy.context.temp_override(**params):
                    bpy.ops.view3d.view_axis(type='LEFT')
                # Shading.
                space = area.spaces.active
                space.shading.type = 'SOLID'
                space.shading.light = 'MATCAP'
                space.shading.studio_light = 'check_normal+y.exr'
                # Grid and gizmo.
                space.overlay.grid_scale = 0.001
                space.show_gizmo = True
                space.show_gizmo_object_translate = True
