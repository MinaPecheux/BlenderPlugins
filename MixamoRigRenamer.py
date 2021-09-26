"""
[Blender Plugins] A little Mixamo rig bone renamer plugin
Mina Pêcheux - September 2021
Email: mina.pecheux@gmail.com

A very basic Blender addon to rename Mixamo rigs to the usual Blender convention:
instead of having bone names like "LeftArm", you get back the "Arm.L" equivalent.

This is particularly useful when using the X-Axis mirror edition :)

The renaming logic is inspired by this gist by eeltork:
    https://gist.github.com/eelstork/6b2944d74ec9dd229938

--------

MIT License

Copyright (c) 2021 Mina Pêcheux

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

bl_info = {
    # required
    'name': 'Mixamo Rig Renamer',
    'blender': (2, 93, 0),
    'category': 'Rigging',
    # optional
    'version': (1, 0, 0),
    'author': 'Mina Pêcheux',
    'description': 'A quick bone renamer to make Mixamo rigs compatible with Blender\'s usual convention (.L/.R).',
}

import bpy
import re

# == GLOBAL VARIABLES
PROPS = [
    ('mixamo_prefix', bpy.props.StringProperty(name='Mixamo Prefix', default='mixamorig')),
]

# == UTILS
def get_standard_bone_name(mixamo_prefix, name, with_prefix=True):
    if with_prefix:
        name = name[len(mixamo_prefix + '.'):]
    if 'Left' in name:
        name = name[4:] + '.L'
    elif 'Right' in name:
        name = name[5:] + '.R'
    return name

def replace_action_name(mixamo_prefix, match):
    name = get_standard_bone_name(mixamo_prefix, match.group(1), with_prefix=False)
    return '"%s"' % name

# == OPERATORS
class MixamoRigRenamerOperator(bpy.types.Operator):
    
    bl_idname = 'opr.mixamo_rig_renamer_operator'
    bl_label = 'Mixamo Rig Renamer'
    
    def execute(self, context):
        mixamo_prefix = context.scene.mixamo_prefix
        
        # remember associated actions and cut the
        # connection for now
        object_actions = {}
        for obj in bpy.data.objects:
            if obj.animation_data is not None:
                object_actions[obj.name] = obj.animation_data.action
                obj.animation_data_clear()
        
        # standardize bone names
        for armature in bpy.data.armatures:
            for bone in armature.bones:
                name = bone.name
                if mixamo_prefix in name:
                    bone.name = get_standard_bone_name(mixamo_prefix, name)

        # convert animation channel names
        bone_pose_regex = r'"%s:(\w+)"' % mixamo_prefix
        for action in bpy.data.actions:
            for curve in action.fcurves:
                p = curve.data_path
                if mixamo_prefix in p:
                    curve.data_path = re.sub(
                        bone_pose_regex,
                        lambda m: replace_action_name(mixamo_prefix, m),
                        curve.data_path)

        # re-assign remembered actions
        for obj_name, action_name in object_actions.items():
            bpy.data.objects[obj_name].animation_data_create()
            bpy.data.objects[obj_name].animation_data.action = action_name

        return {'FINISHED'}

# == PANELS
class MixamoRigRenamerPanel(bpy.types.Panel):
    
    bl_idname = 'VIEW3D_PT_mixamo_rig_renamer'
    bl_label = 'Mixamo Rig Renamer'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    
    def draw(self, context):
        col = self.layout.column()
        for (prop_name, _) in PROPS:
            row = col.row()
            row.prop(context.scene, prop_name)
            
        col.operator('opr.mixamo_rig_renamer_operator', text='Rename')

# == MAIN ROUTINE
CLASSES = [
    MixamoRigRenamerOperator,
    MixamoRigRenamerPanel,
]

def register():
    for (prop_name, prop_value) in PROPS:
        setattr(bpy.types.Scene, prop_name, prop_value)
    
    for klass in CLASSES:
        bpy.utils.register_class(klass)

def unregister():
    for (prop_name, _) in PROPS:
        delattr(bpy.types.Scene, prop_name)

    for klass in CLASSES:
        bpy.utils.unregister_class(klass)
        

if __name__ == '__main__':
    register()
