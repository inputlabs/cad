import json
from pathlib import Path
from types import SimpleNamespace

import bpy
from .common import serialize_value, preformat_json, parse_value

IGNORE_NODE_PROPERTIES = [
    'location_absolute',
    'width',
    'height',
    'label',
    'parent',
    'warning_propagation',
    'use_custom_color',
    'color',
    'select',
    'show_options',
    'show_preview',
    'hide',
    'show_texture',
    'bl_label',
    'bl_description',
    'bl_icon',
    'bl_width_default',
    'bl_width_min',
    'bl_width_max',
    'bl_height_default',
    'bl_height_min',
    'bl_height_max',
]

def get_geometry_node_group(name):
    # Try node group already loaded in the project.
    node_group = bpy.data.node_groups.get(name)
    if node_group:
        return node_group
    # Try built-in node groups.
    else:
        assets = Path(bpy.utils.system_resource('DATAFILES', path='assets'))
        for blend in assets.rglob("*.blend"):
            with bpy.data.libraries.load(str(blend), link=True, assets_only=True) as (src, dst):
                if name in src.node_groups:
                    dst.node_groups = [name]
                    break
        node_group = bpy.data.node_groups.get(name)
        if node_group:
            return node_group
    return None

def get_socket_value(modifier, name):
    for item in modifier.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT':
            if item.name == name:
                inputs = modifier.properties.inputs
                if hasattr(inputs, item.identifier):
                    socket_prop = getattr(inputs, item.identifier)
                    if hasattr(socket_prop, 'value'):
                        return getattr(socket_prop, 'value')
                    else:
                        return getattr(item, 'default_value', None)
    raise Exception(f"No socket found with name '{name}'")

def set_socket_value(modifier, name, value):
    for item in modifier.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT':
            if item.name == name:
                inputs = modifier.properties.inputs
                if hasattr(inputs, item.identifier):
                    socket_prop = getattr(inputs, item.identifier)
                    if hasattr(socket_prop, 'value'):
                        setattr(socket_prop, 'value', value)
                    else:
                        setattr(inputs, item.identifier, value)
                    return
    raise Exception(f"No socket found with name '{name}'")

def serialize_nodegroup(log, nodegroup):
    log(f'serialize_nodegroup {nodegroup}')
    data = {}
    data['bl_idname'] = nodegroup.bl_idname
    # External parameters.
    data['interface'] = []
    for item in nodegroup.interface.items_tree:
        if item.item_type == 'SOCKET':
            parameter = {}
            parameter['name'] = item.name
            parameter['in_out'] = item.in_out
            parameter['socket_type'] = item.socket_type
            parameter['subtype'] = getattr(item, 'subtype', None)
            # parameter['default_value'] = getattr(item, 'default_value', None)
            data['interface'].append(parameter)
    # Nodes.
    data['nodes'] = []
    for node in nodegroup.nodes:
        node_data = {}
        node_data['name'] = node.name
        node_data['bl_idname'] = node.bl_idname
        node_data['location'] = serialize_value(node.location)
        node_data['mute'] = node.mute
        # Properties.
        for prop in node.bl_rna.properties:
            ignore = prop.identifier in IGNORE_NODE_PROPERTIES
            if not prop.is_readonly and not ignore:
                value = serialize_value(getattr(node, prop.identifier))
                node_data[prop.identifier] = value
        # Inputs.
        node_data['inputs'] = {}
        for node_input in node.inputs:
            if node_input.is_linked:
                continue
            if not hasattr(node_input, 'default_value'):
                continue
            value = serialize_value(node_input.default_value)
            node_data['inputs'][node_input.name] = value
        # Outputs.
        node_data['outputs'] = {}
        for node_output in node.outputs:
            if node_output.is_linked:
                continue
            if not hasattr(node_output, 'default_value'):
                continue
            value = serialize_value(node_output.default_value)
            node_data['outputs'][node_output.name] = value
        data['nodes'].append(node_data)
    # Visual Connectors.
    data['links'] = []
    for link in nodegroup.links:
        link_data = {}
        link_data['from_node'] = link.from_node.name
        link_data['to_node'] = link.to_node.name
        link_data['from_socket'] = list(link.from_node.outputs).index(link.from_socket)
        link_data['to_socket'] = list(link.to_node.inputs).index(link.to_socket)
        data['links'].append(link_data)
    # Dump.
    json_string = json.dumps(data, indent=2)
    json_string = preformat_json(json_string)
    return json_string

def create_nodegroup(log, name, data):
    log(f'create_nodegroup {name}')
    ng = bpy.data.node_groups.new(name=name, type=data.bl_idname)
    # Recreate interface (in/out parameters).
    for socket_data in data.interface:
        socket = ng.interface.new_socket(
            name=socket_data.name,
            in_out=socket_data.in_out,
            socket_type=socket_data.socket_type,
        )
        if socket_data.subtype:
            socket.subtype = socket_data.subtype
    # Recreate nodes (each box).
    for node_data in data.nodes:
        node = ng.nodes.new(type=node_data.bl_idname)
        for prop_key, prop_value in node_data.__dict__.items():
            if prop_key in ['inputs', 'outputs']:
                continue
            setattr(node, prop_key, prop_value)
        for input_key, input_value in node_data.inputs.__dict__.items():
            for input_instance in node.inputs:
                if input_instance.name == input_key:
                    log(f'set node input {input_key} {input_value}', 1)
                    input_instance.default_value = parse_value(input_value)
        for output_key, output_value in node_data.outputs.__dict__.items():
            for output_instance in node.outputs:
                if output_instance.name == output_key:
                    log(f'set node output {output_key} {output_value}', 1)
                    output_instance.default_value = parse_value(output_value)
    # Recreate links (each cable connector).
    for link_data in data.links:
        from_node = ng.nodes.get(link_data.from_node)
        to_node = ng.nodes.get(link_data.to_node)
        from_socket = from_node.outputs[link_data.from_socket]
        to_socket = to_node.inputs[link_data.to_socket]
        log(f'set link {from_socket} {to_socket}', 1)
        ng.links.new(from_socket, to_socket)
