"""
[Blender Plugins] A little Mixamo rig bone renamer plugin
Mina Pêcheux
. v1: September 2021
. v2: January 2022
Email: mina.pecheux@gmail.com

A very basic Blender addon to rename Mixamo rigs to the usual Blender convention:
instead of having bone names like "LeftArm", you get back the "Arm.L" equivalent.

v2: Can now also go the other way around and assume a "mixamorig" equivalent to a
usual Blender-named rig.

This is particularly useful when using the X-Axis mirror edition :)

The renaming logic is inspired by this gist by eeltork:
    https://gist.github.com/eelstork/6b2944d74ec9dd229938

--------

MIT License

Copyright (c) 2022 Mina Pêcheux

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
def get_mix_to_blend_bone_name(mixamo_prefix, name, with_prefix=True):
    if with_prefix:
        name = name[len(mixamo_prefix + '.'):]
    if 'Left' in name:
        name = name[4:] + '.L'
    elif 'Right' in name:
        name = name[5:] + '.R'
    return name

def get_blend_to_mix_bone_name(mixamo_prefix, name):
    if name.endswith('.L'):
        name = 'Left' + name[:-2]
    elif name.endswith('.R'):
        name = 'Right' + name[:-2]
    name = mixamo_prefix + ':' + name
    return name

def replace_action_name_mix_to_blend(mixamo_prefix, match):
    name = get_mix_to_blend_bone_name(mixamo_prefix, match.group(1), with_prefix=False)
    return '"%s"' % name

def replace_action_name_blend_to_mix(mixamo_prefix, match):
    name = get_blend_to_mix_bone_name(mixamo_prefix, match.group(1))
    return '"%s"' % name

# == OPERATORS
class MixamoRigRenamerOperator(bpy.types.Operator):
    
    bl_idname = 'opr.mixamo_rig_renamer_operator'
    bl_label = 'Mixamo Rig Renamer'
    
    def execute(self, context):
        mixamo_prefix = context.scene.mixamo_prefix
        
        # get selected armature
        armature = bpy.context.active_object
        if armature is None:
            return

        # remember associated actions and cut the
        # connection for now
        object_actions = {}
        for obj in bpy.data.objects:
            if obj.animation_data is not None:
                object_actions[obj.name] = obj.animation_data.action
                obj.animation_data_clear()

        # change bone names (mixamo > blender) of selected armature
        for bone in armature.data.bones:
            bone.name = self.replace_bone_name(mixamo_prefix, bone.name)

        # convert animation channel names
        for action in bpy.data.actions:
            for curve in action.fcurves:
                self.replace_action_name(mixamo_prefix, curve)

        # re-assign remembered actions
        for obj_name, action_name in object_actions.items():
            bpy.data.objects[obj_name].animation_data_create()
            bpy.data.objects[obj_name].animation_data.action = action_name

        return {'FINISHED'}
    
    def replace_bone_name(self, mixamo_prefix, name):
        raise NotImplementedError()
    
    def replace_action_name(self, mixamo_prefix, curve):
        raise NotImplementedError()
    
class MixamoRigMixToBlendRenamerOperator(MixamoRigRenamerOperator):
    
    bl_idname = 'opr.mixamo_rig_mix_to_blend_renamer_operator'
    bl_label = 'Mixamo Rig Renamer (Mixamo > Blender)'
    
    def replace_bone_name(self, mixamo_prefix, name):
        if mixamo_prefix in name:
            return get_mix_to_blend_bone_name(mixamo_prefix, name)
        else:
            return name
    
    def replace_action_name(self, mixamo_prefix, curve):
        if mixamo_prefix in curve.data_path:
            bone_pose_regex = r'"%s:(\w+)"' % mixamo_prefix
            curve.data_path = re.sub(
                bone_pose_regex,
                lambda m: replace_action_name_mix_to_blend(mixamo_prefix, m),
                curve.data_path)
    
class MixamoRigBlendToMixRenamerOperator(MixamoRigRenamerOperator):
    
    bl_idname = 'opr.mixamo_rig_blend_to_mix_renamer_operator'
    bl_label = 'Mixamo Rig Renamer (Blender > Mixamo)'
    
    def replace_bone_name(self, mixamo_prefix, name):
        if mixamo_prefix not in name:
            return get_blend_to_mix_bone_name(mixamo_prefix, name)
        else:
            return name
    
    def replace_action_name(self, mixamo_prefix, curve):
        bone_pose_regex = r'"([\w\.]+)"'
        if mixamo_prefix not in curve.data_path:
            curve.data_path = re.sub(
                bone_pose_regex,
                lambda m: replace_action_name_blend_to_mix(mixamo_prefix, m),
                curve.data_path)

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
        
        col.separator()

        col.operator('opr.mixamo_rig_mix_to_blend_renamer_operator', text='Mixamo > Blender')
        col.operator('opr.mixamo_rig_blend_to_mix_renamer_operator', text='Blender > Mixamo')

# == MAIN ROUTINE
CLASSES = [
    MixamoRigMixToBlendRenamerOperator,
    MixamoRigBlendToMixRenamerOperator,
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
