from datetime import datetime
import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from .scene import export_scene, import_scene


class Log:
    def log_start(self):
        log_path = self.directory + 'log.txt'
        log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.indent = 0
        self.log_file = open(log_path, 'w', encoding='utf-8')
        self.log_file.write(f"---- Log started: {log_time} ----\n")

    def log(self, msg, level=0):
        indent = '    ' * level
        self.log_file.write(f'{indent}{msg}\n')


class SceneAsJsonExport(Operator, Log):
    bl_idname = "project.save_folder"
    bl_label = "Scene to JSON folder"
    directory: StringProperty(subtype='DIR_PATH', name="Target Directory")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        self.log_start()
        try:
            export_scene(self.log, self.directory)
            self.report({'INFO'}, f'Scene exported to: {self.directory}')
        finally:
            self.log_file.close()
        return {'FINISHED'}


class SceneAsJsonImport(Operator, Log):
    bl_idname = "project.load_folder"
    bl_label = "Scene from JSON folder"
    directory: StringProperty(subtype='DIR_PATH', name="Source Directory")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        # self.report({'INFO'}, f"Load directory: {self.directory}")
        self.log_start()
        try:
            import_scene(self.log, self.directory)
            self.report({'INFO'}, f'Scene imported from: {self.directory}')
        finally:
            self.log_file.close()
        return {'FINISHED'}


classes = (
    SceneAsJsonExport,
    SceneAsJsonImport,
)

def menu_func_export(self, context):
    self.layout.operator(SceneAsJsonExport.bl_idname, text="Scene to JSON folder")

def menu_func_import(self, context):
    self.layout.operator(SceneAsJsonImport.bl_idname, text="Scene from JSON folder")

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)



