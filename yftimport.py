import bpy
import os
import xml.etree.ElementTree as ET
from mathutils import Vector, Quaternion, Matrix
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator
import time
import random 
from . import ydrimport as Drawable
from . import ybnimport as Bounds

def read_matrix(root, row=4, column=4):
    if (root == None):
        return None

    matrix = Matrix()
    mat_str = root.text.strip().replace("\n", "").replace(" " * column, "").split(" ")
    k = 0
    for i in range(row):
        for j in range(column):
            matrix[i][j] = float(mat_str[k])
            k = k + 1
    
    return matrix

def read_children(self, context, filepath, root, shd_node, td_node):

    filename = os.path.basename(filepath[:-8]) 

    drawable_node = root.find("Drawable")
    if (drawable_node == None):
        return None

    high_objects = []
    med_objects = []
    low_objects = []
    
    model_name = filename

    if(drawable_node.find("DrawableModelsHigh") != None):
        high_objects = Drawable.read_drawable_models(self, context, filepath, drawable_node, model_name, shd_node, td_node, "High", None)
    if(drawable_node.find("DrawableModelsMedium") != None):
        med_objects = Drawable.read_drawable_models(self, context, filepath, drawable_node, model_name, shd_node, td_node, "Medium", None)
    if(drawable_node.find("DrawableModelsLow") != None):
        low_objects = Drawable.read_drawable_models(self, context, filepath, drawable_node, model_name, shd_node, td_node, "Low", None)

    all_objects = []
    for o in high_objects:
        all_objects.append(o)
    for o in med_objects:
        all_objects.append(o)
    for o in low_objects:
        all_objects.append(o)

    return all_objects

def read_archetype(self, context, filepath, root):

    filename = os.path.basename(filepath[:-8]) 
    objs = []
    
    for bound in root.findall("Bounds"):
        objs.append(Bounds.read_bounds(filename + ".archetype", bound)) 

    return objs

def read_physics(self, context, filepath, root, shd_node, td_node):
    lod1_node = root.find("LOD1")
    if (lod1_node == None):
        return None, None

    archetype_node = lod1_node.find("Archetype")
    if (archetype_node == None):
        return None, None
    
    # read <Transforms> data, validity is questionable
    # transforms_node = lod1_node.find("Transforms")
    # matrices = None
    # if (transforms_node != None):
    #     matrices = []
    #     for transforms_item in transforms_node:
    #         if (transforms_item == None):
    #             continue
            
    #         matrix = read_matrix(transforms_item, 4, 4)
    #         if (matrix != None):
    #             matrices.append(matrix)

    archetypes = read_archetype(self, context, filepath, archetype_node)
    # if (matrices != None):
    #     children = objs[0].children
    #     for i in range(len(children)):
    #         children[i].matrix_world = matrices[i]

    children_node = lod1_node.find("Children")
    children = None
    if (children_node != None):
        children = []
        for children_item in children_node:
            if (children_item == None):
                continue
            
            child = read_children(self, context, filepath, children_item, shd_node, td_node)
            if (child != None):
                children.append(child)
            
    return archetypes, children

def read_yft_xml(self, context, filepath, root):

    fname = os.path.basename(filepath)
    name = fname[:-8] #removes file extension

    model_name = root.find("Name").text
    drawable_node = root.find("Drawable")
    #get texture info
    shd_group = drawable_node.find("ShaderGroup")
    shd_node = shd_group.find("Shaders")
    td_node = shd_group.find("TextureDictionary")  
    physics_node = root.find("Physics")

    bones, drawable_with_bones_name = Drawable.read_bones(self, context, filepath, drawable_node)

    #get objects from drawable info
    high_objects = []
    med_objects = []
    low_objects = []
    
    if(drawable_node.find("DrawableModelsHigh") != None):
        high_objects = Drawable.read_drawable_models(self, context, filepath, drawable_node, model_name, shd_node, td_node, "High", bones)
    if(drawable_node.find("DrawableModelsMedium") != None):
        med_objects = Drawable.read_drawable_models(self, context, filepath, drawable_node, model_name, shd_node, td_node, "Medium", bones)
    if(drawable_node.find("DrawableModelsLow") != None):
        low_objects = Drawable.read_drawable_models(self, context, filepath, drawable_node, model_name, shd_node, td_node, "Low", bones)

    dd_high = float(drawable_node.find("LodDistHigh").attrib["value"])
    dd_med = float(drawable_node.find("LodDistMed").attrib["value"])
    dd_low = float(drawable_node.find("LodDistLow").attrib["value"])
    dd_vlow = float(drawable_node.find("LodDistVlow").attrib["value"])
    lod_dist = [dd_high, dd_med, dd_low, dd_vlow]

    all_objects = []
    for o in high_objects:
        all_objects.append(o)
    for o in med_objects:
        all_objects.append(o)
    for o in low_objects:
        all_objects.append(o)

    rotationlimits = Drawable.read_joints(self, context, filepath, drawable_node)

    bounds = []
    children = []
    if (physics_node != None):
        bounds, children = read_physics(self, context, filepath, physics_node, shd_node, td_node)

    return all_objects, lod_dist, bounds, children

class ImportYFT(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "importxml.yft"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Yft"

    # ImportHelper mixin class uses this
    filename_ext = ".yft.xml"

    filter_glob: StringProperty(
        default="*.yft.xml",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        start = time.time()
        
        tree = ET.parse(self.filepath)
        root = tree.getroot()

        name = os.path.basename(self.filepath)[:-8]
        armature = bpy.data.armatures.new(name + ".skel")
        vmodel_collection = bpy.data.collections.new(name)
        context.scene.collection.children.link(vmodel_collection)
        vmodel_obj = bpy.data.objects.new(name, armature)
        vmodel_collection.objects.link(vmodel_obj)
        context.view_layer.objects.active = vmodel_obj
        drawable_objs, lod_dist, bounds, children = read_yft_xml(self, context, self.filepath, root)

        drawable_collection = bpy.data.collections.new(name + ".Drawable")
        vmodel_collection.children.link(drawable_collection)

        archetype_collection = bpy.data.collections.new(name + ".Archetype")
        vmodel_collection.children.link(archetype_collection)

        children_collection = bpy.data.collections.new(name + ".Children")
        vmodel_collection.children.link(children_collection)

        for obj in drawable_objs:
            drawable_collection.objects.link(obj)
            obj.parent = vmodel_obj
            mod = obj.modifiers.new("Armature", 'ARMATURE')
            mod.object = vmodel_obj
        
        for child in children:
            for obj in child:
                children_collection.objects.link(obj)
                obj.parent = vmodel_obj

        for obj in bounds:
            context.scene.collection.objects.link(obj)
            obj.parent = vmodel_obj
            # for geo in obj.children:
            #     archetype_collection.objects.link(geo)

        #set sollum properties 
        vmodel_obj.sollumtype = "Drawable"
        vmodel_obj.drawble_distance_high = lod_dist[0] 
        vmodel_obj.drawble_distance_medium = lod_dist[1]
        vmodel_obj.drawble_distance_low = lod_dist[2]
        vmodel_obj.drawble_distance_vlow = lod_dist[3]

        # vmodel_collection.objects.link(vmodel_obj)

        finished = time.time()
        
        difference = finished - start
        
        print("start time: " + str(start))
        print("end time: " + str(finished))
        print("difference in seconds: " + str(difference))
        print("difference in milliseconds: " + str(difference * 1000))
                
        return {'FINISHED'}

# Only needed if you want to add into a dynamic menu
def menu_func_import_yft(self, context):
    self.layout.operator(ImportYFT.bl_idname, text="Yft (.yft.xml)")

def register():
    bpy.utils.register_class(ImportYFT)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_yft)

def unregister():
    bpy.utils.unregister_class(ImportYFT)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_yft)