"""
[Blender and Python] Model Views Exporter
Mina Pêcheux - January 2022
Email: mina.pecheux@gmail.com

A simple Blender addon to quickly prepare and export various views of a 3D model
from common points of view (front, side, top...). To choose the model to export,
simply select it.

If the selected object is a mesh, only still images will be produced. Otherwise,
all the actions in the scene will be listed and you can choose which one to apply
and export.

More info on how I developed the plugin:
    
    - https://medium.com/p/how-i-automated-the-marketing-of-my-blender-3d-models-1-2-bc4f0454dfc3
    - https://medium.com/p/how-i-automated-the-marketing-of-my-blender-3d-models-2-2-4687e5625e

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
    'name': 'Model Views Exporter',
    'blender': (2, 93, 0),
    'category': 'Import-Export',
    # optional
    'version': (1, 0, 0),
    'author': 'Mina Pêcheux',
    'description': 'Export various views of a 3D model (front, side, top...), static or animated.',
}


import bpy
import os
from math import pi

# == GLOBAL VARIABLES
class POVProp(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty(name='Name', default='')
    enabled : bpy.props.BoolProperty(
        name='Enabled', default=True, description='Export with this point of view')
    suffix : bpy.props.StringProperty(
        name='Suffix', default='', description='Suffix to add to the exported images/clips file paths')

class AnimationProp(bpy.types.PropertyGroup):
    name : bpy.props.StringProperty(name='Name', default='')
    enabled : bpy.props.BoolProperty(
        name='Enabled', default=True, description='Export this animation')
    anchor : bpy.props.PointerProperty(
        name='Anchor', type=bpy.types.Object, description='Anim-specific camera anchor')

bpy.utils.register_class(POVProp)
bpy.utils.register_class(AnimationProp)

MARGIN = 0.5
POVs = {
    # offset to anchor, enabled by default
    'front': ((0, -1, 0), True),
    'left': ((1, 0, 0), True),
    'right': ((-1, 0, 0), True),
    'top': ((0, 0, 1), True),
    'persp': ((1, -1, 1), True),
    'turntable': ((0, -1, 0.2), True),
    'back': ((0, 1, 0), False),
    'bottom': ((0, 0, -1), False),
}

PROPS = [
    ('prefix', bpy.props.StringProperty(
        name='Prefix', default='', description='Prefix to add to all export file paths')),
    ('anchor', bpy.props.PointerProperty(
        name='Anchor', type=bpy.types.Object, description='Custom camera anchor')),
    ('do_wireframes', bpy.props.BoolProperty(
        name='Do Wireframes', default=True, description='Export all images/clips with a secondary wireframe version')),
    ('wireframe_suffix', bpy.props.StringProperty(
        name='Wireframe Suffix', default='_wireframe', description='Suffix to add to all wireframe export file paths')),
    ('base_path', bpy.props.StringProperty(
        name='Export Path', default='./', subtype='DIR_PATH',
        description='Path to the export folder')),
    ('export_resolution', bpy.props.IntVectorProperty(
        name='Export Resolution', subtype='TRANSLATION', size=2, default=(1920, 1080),
        description='Width/Height to use for the exported images/clips')),
    ('bg_is_transparent', bpy.props.BoolProperty(
        name='Bg Is Transparent', default=False, description='Set a transparent or opaque export background')),
    ('bg_color', bpy.props.FloatVectorProperty(
        name='Bakground Color', subtype='COLOR', default=(0.057, 0.057, 0.057),
        description='Background color for all exports')),
    ('turntable_length', bpy.props.IntProperty(
        name='Turntable Length', default=160, description='Number of frames for the turntables')),
    ('povs', bpy.props.CollectionProperty(name='POVs', type=POVProp)),
    ('animations', bpy.props.CollectionProperty(name='Animations', type=AnimationProp)),
]

# == UTILS
def delete_obj(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.delete()

def make_camera(anchor, pov, model_size, turntable_length):
    offset, _ = POVs[pov]
    d = 3 # (arbitrary distance to avoid clipping)
    loc = (
        anchor.location[0] + d * offset[0],
        anchor.location[1] + d * offset[1],
        anchor.location[2] + d * offset[2])
        
    # create camera object
    bpy.ops.object.camera_add(location=loc)
    camera = bpy.context.active_object

    # set camera options
    bpy.context.object.data.type = 'ORTHO'
    max_size = max(model_size.x, model_size.y, model_size.z)
    bpy.context.object.data.ortho_scale = max_size * (1 + MARGIN)
    
    # add tracking to anchor
    bpy.ops.object.constraint_add(type='TRACK_TO')
    bpy.context.object.constraints['Track To'].target = anchor
    
    # special case: turntable => create a center anchor,
    # parent the camera and add keyframes
    cam_anchor = None
    if pov == 'turntable':
        # (create anchor and parent the camera)
        bpy.ops.object.empty_add(location=(0, 0, 0))
        cam_anchor = bpy.context.active_object
        camera.parent = cam_anchor
        # (add keyframes)
        cam_anchor.animation_data_create()
        cam_anchor.animation_data.action = bpy.data.actions.new(name='RotationAction')
        fcurve = cam_anchor.animation_data.action.fcurves.new(data_path='rotation_euler', index=2)
        k1 = fcurve.keyframe_points.insert(frame=1, value=0)
        k1.interpolation = 'LINEAR'
        k2 = fcurve.keyframe_points.insert(frame=turntable_length, value=2.0*pi)
        k2.interpolation = 'LINEAR'
    
    return (camera, cam_anchor)

def show_wireframes(on):
    for obj in bpy.data.objects:
        obj.show_wire = on

def export_pov(
    space3d, pov, prefix, suffix, bg,
    export_resolution, base_path, turntable_length,
    animation=None, wireframe=False, wireframe_suffix=''):
    scene = bpy.context.scene

    scene.render.resolution_x = export_resolution[0]
    scene.render.resolution_y = export_resolution[1]
    
    space3d.shading.type = 'SOLID'
    if wireframe:
        show_wireframes(True)
    
    # special case: turntable
    if pov == 'turntable':
        p = base_path + '{}{}'.format(prefix, suffix)
        if wireframe:
            p += wireframe_suffix
        p += '.avi'
        scene.render.filepath = p

        scene.frame_start = 1
        scene.frame_end = turntable_length
        
        scene.render.film_transparent = False
        if bg != 'transparent':
            space3d.shading.background_color = bg
        scene.render.image_settings.file_format = 'AVI_JPEG'
        bpy.ops.render.opengl(write_still=True, view_context=True, animation=True)
    # all other cases
    else:
        if animation is None:
            p = base_path + '{}{}'.format(prefix, suffix)
            if wireframe:
                p += wireframe_suffix
            p += '.png'
            scene.render.filepath = p
            
            scene.render.image_settings.file_format = 'PNG'
            if bg == 'transparent':
                scene.render.film_transparent = True
                scene.render.image_settings.color_mode = 'RGBA'
            else:
                scene.render.film_transparent = False
                scene.render.image_settings.color_mode = 'RGB'
                space3d.shading.background_color = bg
            bpy.ops.render.opengl(write_still=True, view_context=True)
        else:
            s = '-' if prefix != '' else ''
            p = base_path + '{}{}{}{}'.format(prefix, s, animation, suffix)
            if wireframe:
                p += wireframe_suffix
            p += '.avi'
            scene.render.filepath = p
            
            range = bpy.data.actions[animation].frame_range
            scene.frame_start = range.x
            scene.frame_end = range.y - 1
            
            scene.render.film_transparent = False
            if bg != 'transparent':
                space3d.shading.background_color = bg
            scene.render.image_settings.file_format = 'AVI_JPEG'
            bpy.ops.render.opengl(write_still=True, view_context=True, animation=True)
            
    if wireframe:
        show_wireframes(False)


def get_3d_scene():
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            return area.spaces[0]

def setup_scene(space3d):
    # remember some values
    armature = bpy.data.objects.get('Armature', None)
    scene_parameters = {
        'armature': armature,
        'armature_pose_position': armature.data.pose_position if armature else '',
        'shading_color_type': space3d.shading.color_type,
        'bg_type': space3d.shading.background_type,
        'bg_color': space3d.shading.background_color,
        'frame_start': bpy.context.scene.frame_start,
        'frame_end': bpy.context.scene.frame_end,
    }

    # set viewport with user-defined background type
    space3d.shading.background_type = 'VIEWPORT'
    
    # use texture coloring
    space3d.shading.color_type = 'TEXTURE'
    
    # hide armature
    space3d.show_object_viewport_armature = False
    
    # hide all extras/lines/grids in solid mode
    space3d.overlay.show_floor = False
    space3d.overlay.show_axis_x = False
    space3d.overlay.show_axis_y = False
    space3d.overlay.show_outline_selected = False
    space3d.overlay.show_relationship_lines = False
    space3d.overlay.show_extras = False
    space3d.overlay.show_cursor = False
    space3d.overlay.show_object_origins = False
    space3d.overlay.show_bones = False
    
    return scene_parameters

def reset_scene(space3d, scene_parameters):
    # restore some values
    if scene_parameters['armature']:
        scene_parameters['armature'].data.pose_position = scene_parameters['armature_pose_position']
    space3d.shading.color_type = scene_parameters['shading_color_type']
    space3d.shading.background_type = scene_parameters['bg_type']
    space3d.shading.background_color = scene_parameters['bg_color']
    bpy.context.scene.frame_start = scene_parameters['frame_start']
    bpy.context.scene.frame_end = scene_parameters['frame_end']
    
    # re-enable armature
    space3d.show_object_viewport_armature = True
    
    # re-enable all extras/lines/grids in solid mode
    space3d.overlay.show_floor = True
    space3d.overlay.show_axis_x = True
    space3d.overlay.show_axis_y = True
    space3d.overlay.show_outline_selected = True
    space3d.overlay.show_relationship_lines = True
    space3d.overlay.show_extras = True
    space3d.overlay.show_cursor = True
    space3d.overlay.show_object_origins = True
    space3d.overlay.show_bones = True
    
    show_wireframes(False)

# == OPERATORS
class MVEExportOperator(bpy.types.Operator):
    
    bl_idname = 'opr.mve_export_operator'
    bl_label = 'MVE Export'
    bl_description = 'Export images/clips for the 3D model'
    
    def execute(self, context):
        if len(bpy.context.selected_objects) == 0:
            return {'FINISHED'}
        
        # extract util context variables
        base_path = context.scene.base_path
        # make sure the path is a folder
        if not base_path.endswith(os.path.sep):
            base_path += os.path.sep

        prefix = context.scene.prefix
        if context.scene.bg_is_transparent:
            background = 'transparent'
        else:
            background = context.scene.bg_color
        
        export_resolution = context.scene.export_resolution
        turntable_length = context.scene.turntable_length

        # get current scene setup
        space3d = get_3d_scene()
        scene_parameters = setup_scene(space3d)
        
        model = bpy.context.active_object
        model_size = model.dimensions
        animations = []
        if model.type == 'ARMATURE':
            animations = [anim for anim in context.scene.animations if anim.enabled]

        # deselect all to avoid overlays with wireframe
        bpy.ops.object.select_all(action='DESELECT')
        
        # try to get user-defined anchor
        anchor = context.scene.anchor
        destroy_anchor = False
        # else create anchor
        if anchor is None:
            bpy.ops.object.empty_add(location=(0, 0, model_size.z / 2.0))
            anchor = bpy.context.active_object
            destroy_anchor = True
            
        # iterate through POVs
        for pov in context.scene.povs:
            show_wireframes(False)
            
            pov_name = pov.name.lower()
            if scene_parameters['armature']:
                scene_parameters['armature'].data.pose_position = 'REST'
            # (check if POV is enabled)
            if not pov.enabled:
                continue
            # (create camera for POV)
            cam, cam_anchor = make_camera(anchor, pov_name, model_size, turntable_length)
            # (assign camera)        
            bpy.context.scene.camera = cam
            space3d.region_3d.view_perspective = 'CAMERA'
            # (make suffix + export)
            suffix = '_{}'.format(pov_name)
            export_pov(
                space3d, pov_name, prefix, suffix, background,
                export_resolution, base_path, turntable_length,
                animation=None)
                
            if context.scene.do_wireframes:
                export_pov(
                    space3d, pov_name, prefix, suffix, background,
                    export_resolution, base_path, turntable_length,
                    animation=None, wireframe=True,
                    wireframe_suffix=context.scene.wireframe_suffix)
                    
            if pov_name != 'turntable':
                for animation in animations:
                    # (recompute anchor if need be)
                    if animation.anchor is not None:
                        delete_obj(cam)
                        cam, _ = make_camera(animation.anchor, pov_name, model_size, turntable_length)
                        bpy.context.scene.camera = cam
                        space3d.region_3d.view_perspective = 'CAMERA'
                    # (set anim)
                    model.data.pose_position = 'POSE'
                    model.animation_data.action = bpy.data.actions[animation.name]
                    export_pov(
                        space3d, pov_name, prefix, suffix, background,
                        export_resolution, base_path, turntable_length,
                        animation=animation.name)

                    if context.scene.do_wireframes:
                        export_pov(
                            space3d, pov_name, prefix, suffix, background,
                            export_resolution, base_path, turntable_length,
                            animation=animation.name, wireframe=True,
                            wireframe_suffix=context.scene.wireframe_suffix)

                    model.data.pose_position = 'REST'
                    
                    if animation.anchor is not None:
                        delete_obj(cam)
                        cam, _ = make_camera(anchor, pov_name, model_size, turntable_length)
                        bpy.context.scene.camera = cam
                        space3d.region_3d.view_perspective = 'CAMERA'
            if cam_anchor is not None:
                delete_obj(cam_anchor)
            # (delete camera for POV)
            delete_obj(cam)
            
        # delete temporary anchor
        if destroy_anchor:
            delete_obj(anchor)
        
        # restore scene setup
        reset_scene(space3d, scene_parameters)
        model.select_set(True)
        bpy.context.view_layer.objects.active = model

        return {'FINISHED'}

class MVESelectAllPOVsOperator(bpy.types.Operator):
    
    bl_idname = 'opr.mve_select_all_povs_operator'
    bl_label = 'MVE Select All POVs'
    bl_description = 'Enable all points of views for export'
    
    def execute(self, context):
        for item in context.scene.povs:
            item.enabled = True
        
        return {'FINISHED'}

class MVEDeselectAllPOVsOperator(bpy.types.Operator):
    
    bl_idname = 'opr.mve_deselect_all_povs_operator'
    bl_label = 'MVE Deelect All POVs'
    bl_description = 'Disable all points of views for export'
    
    def execute(self, context):
        for item in context.scene.povs:
            item.enabled = False
        
        return {'FINISHED'}

class MVESelectAllAnimsOperator(bpy.types.Operator):
    
    bl_idname = 'opr.mve_select_all_anims_operator'
    bl_label = 'MVE Select All POVs'
    bl_description = 'Enable all animations for export'
    
    def execute(self, context):
        for item in context.scene.animations:
            item.enabled = True
        
        return {'FINISHED'}

class MVEDeselectAllAnimsOperator(bpy.types.Operator):
    
    bl_idname = 'opr.mve_deselect_all_anims_operator'
    bl_label = 'MVE Deselect All POVs'
    bl_description = 'Disable all animations for export'
    
    def execute(self, context):
        for item in context.scene.animations:
            item.enabled = False
        
        return {'FINISHED'}

class MVEPickAnimationOperator(bpy.types.Operator):
    
    bl_idname = 'opr.mve_pick_animation_operator'
    bl_label = 'MVE Pick Animation'
    bl_description = 'See the animation on the character'
    
    anim_name : bpy.props.StringProperty()
    
    def execute(self, context):
        if len(bpy.context.selected_objects) == 0:
            return {'FINISHED'}
        
        model = bpy.context.active_object
        if model.type != 'ARMATURE':
            return {'FINISHED'}
        
        model.animation_data.action = bpy.data.actions[self.anim_name]
        
        return {'FINISHED'}

# == PANELS
class MVEExportPanel(bpy.types.Panel):
    
    bl_idname = 'VIEW3D_PT_mve_export'
    bl_label = 'Model Views Export'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
        
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def draw(self, context):
        col = self.layout.column()

        # check for empty path
        invalid_path = False
        if context.scene.base_path == '':
            col.label(text='Path cannot be empty', icon='ERROR')
            invalid_path = True
        
        op_cell = col.row()
        op_cell.enabled = not invalid_path
        op_cell.operator('opr.mve_export_operator', text='Export')

class MVEExportPanelSubpanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MVE Tab'

class MVEExportPanelBaseOptions(MVEExportPanelSubpanel, bpy.types.Panel):
    
    bl_idname = 'VIEW3D_PT_mve_export_base_options'
    bl_parent_id = 'VIEW3D_PT_mve_export'
    bl_label = 'Base Options'

    def draw_header(self, context):
        layout = self.layout
        layout.label(text='', icon='PREFERENCES')

    def draw(self, context):
        col = self.layout.column()
        col.prop(context.scene, 'base_path', text='Path')
        col.prop(context.scene, 'export_resolution')
        col.separator()
        col.prop(context.scene, 'prefix')
        col.prop(context.scene, 'anchor')
        col.prop(context.scene, 'do_wireframes')
        wire_suffix_cell = col.row()
        wire_suffix_cell.enabled = context.scene.do_wireframes
        wire_suffix_cell.prop(context.scene, 'wireframe_suffix')

class MVEExportPanelBgOptions(MVEExportPanelSubpanel, bpy.types.Panel):
    
    bl_idname = 'VIEW3D_PT_mve_export_bg_options'
    bl_parent_id = 'VIEW3D_PT_mve_export'
    bl_label = 'Background Options'

    def draw_header(self, context):
        layout = self.layout
        layout.label(text='', icon='SCENE_DATA')

    def draw(self, context):
        col = self.layout.column()
        bg_row = col.row()
        bg_row.prop(context.scene, 'bg_is_transparent', text='Transparent stills')
        bg_row.prop(context.scene, 'bg_color', text='')

class MVEExportPanelPOVs(MVEExportPanelSubpanel, bpy.types.Panel):
    
    bl_idname = 'VIEW3D_PT_mve_export_povs'
    bl_parent_id = 'VIEW3D_PT_mve_export'
    bl_label = 'Points of view'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        layout = self.layout
        layout.label(text='', icon='OUTLINER_OB_CAMERA')

    def draw(self, context):
        col = self.layout.column()
        
        btns_row = col.row()
        btns_row.operator('opr.mve_select_all_povs_operator', text='Select All')
        btns_row.operator('opr.mve_deselect_all_povs_operator', text='Deselect All')
        
        col.separator()
        
        for item in context.scene.povs:
            pov_row = col.row()
            pov_row.prop(item, 'enabled', text='')
            pov_row.label(text=item.name)
            
            extras = pov_row.row()
            extras.enabled = getattr(item, 'enabled')
            extras.prop(item, 'suffix', text='')
            
            if item.name.lower() == 'turntable' and item.enabled:
                subrow = col.row()
                subrow.prop(context.scene, 'turntable_length')

class MVEExportPanelAnimations(MVEExportPanelSubpanel, bpy.types.Panel):
    
    bl_idname = 'VIEW3D_PT_mve_export_animations'
    bl_parent_id = 'VIEW3D_PT_mve_export'
    bl_label = 'Animations'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def draw_header(self, context):
        layout = self.layout
        layout.label(text='', icon='ARMATURE_DATA')
        
    def draw(self, context):
        col = self.layout.column()
        
        btns_row = col.row()
        btns_row.operator('opr.mve_select_all_anims_operator', text='Select All')
        btns_row.operator('opr.mve_deselect_all_anims_operator', text='Deselect All')
        
        col.separator()
        
        for item in context.scene.animations:
            anim_row = col.row()
            anim_row.prop(item, 'enabled', text='')
            anim_row.label(text=item.name)
            
            op = anim_row.operator('opr.mve_pick_animation_operator', text='', icon='HIDE_OFF')
            op.anim_name = item.name
            
            extras = anim_row.row()
            extras.enabled = getattr(item, 'enabled')
            extras.prop(item, 'anchor', text='')

# == MAIN ROUTINE
CLASSES = [
    MVEExportOperator,
    MVESelectAllPOVsOperator,
    MVEDeselectAllPOVsOperator,
    MVESelectAllAnimsOperator,
    MVEDeselectAllAnimsOperator,
    MVEPickAnimationOperator,
    
    MVEExportPanel,
    MVEExportPanelBaseOptions,
    MVEExportPanelBgOptions,
    MVEExportPanelPOVs,
    MVEExportPanelAnimations,
]

@bpy.app.handlers.persistent
def load_animations_and_povs(*args):
    scene = bpy.context.scene
    scene.povs.clear()
    for pov_name, (_, is_enabled) in POVs.items():
        pov = scene.povs.add()
        pov.name = pov_name.title()
        pov.enabled = is_enabled
        pov.suffix = '_{}'.format(pov_name)

    scene.animations.clear()
    anim_names = sorted(bpy.data.actions.keys())
    for anim_name in anim_names:
        anim = scene.animations.add()
        anim.name = anim_name

def register():
    for (prop_name, prop_value) in PROPS:
        setattr(bpy.types.Scene, prop_name, prop_value)
    
    for klass in CLASSES:
        bpy.utils.register_class(klass)

    if load_animations_and_povs not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_animations_and_povs)

def unregister():
    for (prop_name, _) in PROPS:
        delattr(bpy.types.Scene, prop_name)

    for klass in CLASSES:
        bpy.utils.unregister_class(klass)
    bpy.utils.unregister_class(POVProp)
    bpy.utils.unregister_class(AnimationProp)

    if load_animations_and_povs in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_animations_and_povs)


if __name__ == '__main__':
    register()
