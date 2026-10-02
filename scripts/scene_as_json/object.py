import math
import mathutils
import json
from pathlib import Path
from types import SimpleNamespace

import bpy
from .common import serialize_value, preformat_json, parse_value
from .node import get_socket_value, get_geometry_node_group, set_socket_value

IGNORE_ATTR = [
    'is_active',
    'show_expanded',
    'show_group_selector',
    'show_manage_panel'
]

def get_object(name):
    return bpy.data.objects.get(name)  # Object names are unique in Blender.

def get_object_by_ref(ref):
    name = ref.split('>')[1]
    return get_object(name)

def get_object_path(obj):
    def walk(collection, path, is_top=False):
        if not is_top:
            path /= collection.name
        for subcollection in collection.children:
            result = walk(subcollection, path)
            if result:
                return result
        for subobj in collection.objects:
            if subobj == obj:
                return path / obj.name
    scene = bpy.context.scene.collection
    return walk(scene, Path(), True)

def serialize_object(log, obj):
    log(f'serialize_object {get_object_path(obj)}')
    data = SimpleNamespace()
    data.type = obj.type
    data.location = obj.location.to_tuple(3)
    data.rotation = [round(math.degrees(x), 3) for x in obj.rotation_euler]
    data.scale = obj.scale.to_tuple(3)
    data.hide_viewport = obj.hide_get()
    if obj.type == 'MESH':
        data.modifiers = [serialize_modifier(log, obj, m) for m in obj.modifiers]
        if len(obj.data.vertices) < 1000:
            data.vertices = [v.co.to_tuple(3) for v in obj.data.vertices]
            data.edges = [list(e.vertices) for e in obj.data.edges]
            data.polygons = [list(p.vertices) for p in obj.data.polygons]
            def attach_mesh_attr(attr_name):
                attr = obj.data.attributes.get(attr_name)
                if attr:
                    values = [vert.value for vert in attr.data]
                    if any(values):
                        setattr(data, attr_name, serialize_value(values))
            attach_mesh_attr('crease_vert')
            attach_mesh_attr('bevel_weight_vert')
            attach_mesh_attr('crease_edge')
            attach_mesh_attr('bevel_weight_edge')
        else:
            log(f"Excluded '{obj.name}' (too many vertices)")
            data.export_mesh = True
    json_string = json.dumps(vars(data), indent=2)
    json_string = preformat_json(json_string)
    export_mesh = hasattr(data, 'export_mesh')
    return json_string, export_mesh

def create_object(log, folder, path, data):
    log(f'create_object {path}')
    # Create collection hierarchy.
    collection = bpy.context.scene.collection
    subpath = path
    while len(subpath.parts) > 1:
        parent = subpath.parts[0]
        new_collection = bpy.data.collections.get(parent)
        if not new_collection:
            new_collection = bpy.data.collections.new(parent)
            collection.children.link(new_collection)
        collection = new_collection
        subpath = subpath.relative_to(parent)
    # Reconstruct object.
    name = str(subpath)
    if data.type == 'MESH':
        mesh = bpy.data.meshes.new(name)
        if hasattr(data, 'vertices'):
            mesh.from_pydata(data.vertices, data.edges, data.polygons)
        if hasattr(data, 'crease_vert'):
            create_mesh_attribute(mesh, 'crease_vert', 'POINT', data.crease_vert)
        if hasattr(data, 'bevel_weight_vert'):
            create_mesh_attribute(mesh, 'bevel_weight_vert', 'POINT', data.bevel_weight_vert)
        if hasattr(data, 'crease_edge'):
            create_mesh_attribute(mesh, 'crease_edge', 'EDGE', data.crease_edge)
        if hasattr(data, 'bevel_weight_edge'):
            create_mesh_attribute(mesh, 'bevel_weight_edge', 'EDGE', data.bevel_weight_edge)
        # Import from binary.
        if hasattr(data, 'export_mesh'):
            glb_path = folder / '_big_mesh' / f'{name}.glb'
            mesh = gltf_to_mesh(log, glb_path, name)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
    elif data.type == 'EMPTY':
        obj = bpy.data.objects.new(name, None)
    else:
        return
    collection.objects.link(obj)
    # Reconstruct properties.
    obj.location = data.location
    obj.rotation_euler = [math.radians(deg) for deg in data.rotation]
    obj.scale = data.scale
    obj.hide_set(data.hide_viewport)

def create_mesh_attribute(mesh, name, domain, values):
    attr = mesh.attributes.get(name) or mesh.attributes.new(name=name, type='FLOAT', domain=domain)
    attr.data.foreach_set("value", values)

def serialize_modifier(log, obj, modifier):
    log(f'serialize_modifier {modifier}', 1)
    default = obj.modifiers.new(name='DEFAULT', type=modifier.type)
    data = {}
    data['type'] = modifier.type
    data['name'] = modifier.name
    try:
        # Static modifier attributes.
        for prop in modifier.rna_type.properties:
            if prop.is_readonly:
                continue
            key = prop.identifier
            log(f'value {key}', 2)
            if key in IGNORE_ATTR:
                continue
            val = serialize_value(getattr(modifier, key))
            val_default = serialize_value(getattr(default, key))
            if val == val_default:
                continue
            data[key] = val
        # Dynamic modifier attributes (node values).
        if modifier.type == 'NODES':
            default.node_group = modifier.node_group
            data['node_values'] = {}
            for key in modifier.node_group.interface.items_tree.keys():
                log(f'node value {key}', 2)
                if key == 'Geometry':
                    continue
                val = serialize_value(get_socket_value(modifier, key))
                val_default = serialize_value(get_socket_value(default, key))
                if val == val_default:
                    continue
                data['node_values'][key] = val
    finally:
        # Clean up temporal reference modifier even if there is an exception.
        obj.modifiers.remove(default)
    return data

def create_modifier(log, obj, data):
    log(f'create_modifier {obj} {data.type}')
    modifier = obj.modifiers.new(name=data.name, type=data.type)
    modifier.show_expanded = False  # Collapse UI panel.
    for key, value in vars(data).items():
        log(f'set value {key} {value}', 1)
        if key in ['name', 'type']:
            continue
        if isinstance(value, str) and value.startswith('<'):
            # Re-link referenced objects.
            if 'bpy_types.Object' in value:
                obj_name = value.split('>')[1]
                target_obj = get_object(obj_name)
                log(f'link object {key} {target_obj}', 1)
                setattr(modifier, key, target_obj)
                continue
            # Re-link node group used by modifier.
            if 'bpy.types.GeometryNodeTree' in value:
                ng_name = value.split('>')[1]
                ng = get_geometry_node_group(ng_name)
                log(f'link nodegroup {key} {ng}', 1)
                if ng:
                    setattr(modifier, key, ng)
                else:
                    log(f"Not found node tree '{value}'", 2)
                    break
                continue
        if key == 'node_values':
            for node_key, node_value in value.__dict__.items():
                log(f'set_socket_value {node_key}, {node_value}', 2)
                set_socket_value(modifier, node_key, parse_value(node_value))
            continue
        setattr(modifier, key, value)

def mesh_to_gltf(log, obj, filepath):
    log(f'mesh_to_gltf {obj.name} {filepath}')
    # Visibility.
    was_hidden = obj.hide_get()
    was_hidden_viewport = obj.hide_viewport
    obj.hide_viewport = False
    obj.hide_set(False)
    # Selection.
    deselect_all_objects()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    # Write.
    filepath.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(filepath),
        export_format='GLB',
        use_selection=True,
        use_visible=False,
        export_apply=False,  # Apply modifiers.
        export_normals=False,
        export_texcoords=False,
        export_attributes=False,
        export_lights=False,
        export_cameras=False,
        export_animations=False,
        export_skins=False,
        export_morph=False,
        export_extras=False,
        export_materials='NONE',
        use_mesh_edges=False,  # Exclude loose 1D edges (non-face lines).
        use_mesh_vertices=False,  # Exclude loose 0D vertices (point clouds).
        export_draco_mesh_compression_enable=True,  # Compression.
    )
    # Restore.
    obj.hide_viewport = was_hidden_viewport
    obj.hide_set(was_hidden)
    deselect_all_objects()

def gltf_to_mesh(log, filepath, name):
    # Import.
    log(f'gltf_to_mesh {filepath}', 1)
    bpy.ops.import_scene.gltf(filepath=str(filepath))
    temp_obj = get_object(name)
    temp_obj.name = f'{temp_obj.name}-imported'
    # Scale (GLTF unit is always 1 meter).
    temp_obj.scale *= 0.001
    scale_matrix = mathutils.Matrix.Diagonal((*temp_obj.scale, 1.0))
    temp_obj.data.transform(scale_matrix)
    temp_obj.scale = (1.0, 1.0, 1.0)
    # Copy mesh.
    temp_mesh = temp_obj.data
    mesh = temp_mesh.copy()
    mesh.name = name
    # Clean up.
    bpy.data.objects.remove(temp_obj, do_unlink=True)
    bpy.data.meshes.remove(temp_mesh)
    return mesh

def deselect_all_objects():
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
