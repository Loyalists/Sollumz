import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator
from bpy.props import StringProperty
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.dom import minidom
from mathutils import Vector, Matrix
from collections import deque
import os 
import sys 
import shutil
import ntpath
import bmesh
import math
import numpy as np
from numpy import dot
from numpy.linalg import norm
from datetime import datetime 
from . import shaderoperators as Shader
from .tools import jenkhash as JenkHash
from .resources.drawable import Drawable, DrawableDictionary, DrawableModel, Skeleton, Bone, Vertex, VertexBuffer, IndexBuffer, Geometry

def get_obj_children(obj):
    children = [] 
    objects = bpy.context.scene.objects
    for ob in obj.children: 
        if objects.get(ob.name):
            children.append(ob) 

    return children 
    
def process_uv(uv):
    u = uv[0]
    v = (uv[1] - 1.0) * -1

    return [u, v]

def get_similarity(a, b):
    # cosine similarity
    similarity = dot(a, b)/(norm(a)*norm(b))
    return similarity

def get_distance(a, b):
    # distance
    dist = math.sqrt(abs(a[0]-b[0])**2 + abs(a[1]-b[1])**2)
    return dist

def get_manhattan_distance(a, b):
    # manhattan distance
    dist = abs(a[0]-b[0]) + abs(a[1]-b[1])
    return dist

def get_vertex_string(obj, vlayout, bones, depsgraph):
    mesh = bpy.data.meshes.new_from_object(obj, preserve_all_data_layers=True, depsgraph=depsgraph)

    # vertices sanitizing
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.split(bm, use_only_faces=True)
    uv_layer = bm.loops.layers.uv.active
    vert_uv_map = {}
    unsafe_loops = deque()
    for face in bm.faces:
        for loop in face.loops:
            vert = loop.vert
            uv = loop[uv_layer].uv
            value = vert_uv_map.get(vert)
            if value is None:
                vert_uv_map[vert] = uv
            else:
                indicator = get_distance(value, uv)
                if indicator > 0.0001:
                    unsafe_loops.append(loop)
    
    for loop in unsafe_loops:
        bmesh.utils.loop_separate(loop)

    unsafe_loops.clear()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update(calc_edges=True, calc_edges_loose=True)

    vertamount = len(mesh.vertices)
    texcoords = {}

    vb = VertexBuffer()
    vb.vertices = [None] * vertamount
    vb.layout = vlayout

    for i in range(6):
        texcoords[i] = [None] * vertamount       
    
    if mesh.has_custom_normals:
        mesh.calc_normals_split()
    else:
        mesh.calc_normals()

    mesh.calc_tangents()

    vertex_groups = obj.vertex_groups

    bones_index_dict = {}
    for i in range(len(bones)):
        bones_index_dict[bones[i].name] = i

    clr0_layer = None 
    clr1_layer = None
    if(mesh.vertex_colors == None):
        clr0_layer = mesh.vertex_colors.new()
        clr1_layer = mesh.vertex_colors.new()
    else:
        clr0_layer = mesh.vertex_colors[0]
        if len(mesh.vertex_colors) >= 2:
            clr1_layer = mesh.vertex_colors[1]
        else:
            clr1_layer = mesh.vertex_colors.new()

    for poly in mesh.polygons:
        for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
            vi = mesh.loops[loop_index].vertex_index
            if vb.vertices[vi] is not None:
                continue
            
            vertex = Vertex()
            vertex.position = mesh.vertices[vi].co
            vertex.normal = mesh.loops[loop_index].normal
            vertex.colors0 = clr0_layer.data[loop_index].color
            vertex.colors1 = clr1_layer.data[loop_index].color
            for uv_layer_id in range(len(mesh.uv_layers)):
                uv_layer = mesh.uv_layers[uv_layer_id].data
                uv = process_uv(uv_layer[loop_index].uv)
                u = uv[0]
                v = uv[1]
                fixed_uv = Vector((u, v))
                # texcoords[uv_layer_id][vi] = fixed_uv
                layer = "texcoord" + str(uv_layer_id)
                setattr(vertex, layer, fixed_uv)

            vertex.tangent = mesh.loops[loop_index].tangent.to_4d()
            # bitangent = bitangent_sign * cross(normal, tangent)
            vertex.tangent.w = mesh.loops[loop_index].bitangent_sign
            #FIXME: one vert can only be influenced by 4 weights at most
            vertex_group_elements = mesh.vertices[vi].groups

            if len(vertex_group_elements) > 0:
                vertex.blendweights = [0] * 4
                vertex.blendindices = [0] * 4
                valid_weights = 0
                total_weights = 0
                max_weights = 0
                max_weights_index = -1

                for element in vertex_group_elements:
                    if element.group >= len(vertex_groups):
                        continue

                    vertex_group = vertex_groups[element.group]
                    bone_index = bones_index_dict.get(vertex_group.name, -1)
                    # 1/255 = 0.0039 the minimal weight for one vertex group
                    weight = round(element.weight * 255)
                    if (vertex_group.lock_weight == False and bone_index != -1 and weight > 0 and valid_weights < 4):
                        vertex.blendweights[valid_weights] = weight
                        vertex.blendindices[valid_weights] = bone_index
                        if (max_weights < weight):
                            max_weights_index = valid_weights
                            max_weights = weight

                        valid_weights += 1
                        total_weights += weight

                # weights verification stuff
                # wtf rockstar
                # why do you even use int for weights
                if valid_weights > 0 and max_weights_index != -1:
                    vertex.blendweights[max_weights_index] = vertex.blendweights[max_weights_index] + (255 - total_weights)
            else:
                vertex.blendweights = [0, 0, 255, 0]
                vertex.blendindices = [0] * 4
            
            vb.vertices[vi] = vertex

    vb.vertices_to_data()

    ib = get_index_string(mesh)

    return vb, ib

def get_index_string(mesh):
    
    ib = IndexBuffer()
    index_list = deque()
    
    for poly in mesh.polygons:
        for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
            index_list.append(str(mesh.loops[loop_index].vertex_index))
            
    ib.data = " ".join(index_list)

    return ib

def fix_shader_name(name, no_extension = False): #because blender renames everything to .00X
    newname = ""
    n = name.split(".")
    if(len(n) == 3):
        newname += n[0]
        newname += "."  
        newname += n[1]
    else:
        newname = name
    if(no_extension):
        newname = newname[:-4]
    return newname

def get_vertex_layout(shader):
    shader = fix_shader_name(shader) 

    parameter_set = Shader.shaders.get(shader)
    if parameter_set is not None:
        for p in parameter_set:
            if p.Type == "Layout":
                return p.get_value()

    print('Unknown shader: ', shader)

def write_model_node(objs, materials, bones):
    
    m_node = DrawableModel()
    m_node.render_mask = objs[0].mask

    if len(objs[0].vertex_groups) > 0:
        m_node.has_skin = True
    else:
        m_node.has_skin = False

    if bones != None:
        m_node.unknown_1 = len(bones)

    # depsgraph stuff, for the purpose of auto-applying modifiers on exporting
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in objs:
        obj_eval = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(obj_eval, preserve_all_data_layers=True, depsgraph=depsgraph)

        i_node = Geometry()
        
        shader_index = 0
        shader = None
        for idx in range(len(materials)):
            if(mesh.materials[0] == materials[idx]):
                shader_index = idx
                shader = materials[idx] 

        i_node.shader_index = shader_index
        i_node.bound_box_min = obj.bound_box[0] 
        i_node.bound_box_max = obj.bound_box[6]
        
        if bones != None:
            for i in range(len(bones)):
                i_node.bone_ids.append(i)

        if(shader.sollumtype != "GTA"):
            print("Error Material Type Is Not GTA!!")
            return m_node
        
        print('Processing shader', shader_index, shader.name)
        vlayout = get_vertex_layout(shader.name)

        vb, ib = get_vertex_string(obj_eval, vlayout, bones, depsgraph)
        i_node.vertex_buffer = vb
        i_node.index_buffer = ib

        m_node.geometries.append(i_node)

    return m_node
    
def write_drawablemodels_node(models, materials, bones):
    
    high_models = []
    
    for obj in models:
        high_models.append(obj)
    
    dm_nodes = []
    
    if(len(high_models) != 0):
        dm_nodes.append(write_model_node(high_models, materials, bones))
    
    return dm_nodes

def write_imageparam_node(node):
    
    paramname = node.name 
    
    #if the same parameter is imported multiple time naming gets prefixed with .00X 
    #if("." in paramname): 
    #    split = paramname.split(".")
       # paramname = split[0]
        
    iname = node.name 
    type = "Texture"
    tname = "None" #givemechecker? 
    
    #if(node.image != None):
        #tname = os.path.basename(node.image.filepath)
    tname = node.texture_name.split(".")[0] #delete file extension
    
    i_node = Element("Item")
    i_node.set("name", iname)
    i_node.set("type", type)

    if (tname != None and len(tname) > 0):
        name_node = Element("Name")
        name_node.text = tname
    
        unk32_node = Element("Unk32")
        unk32_node.set("value", "128")
    
        i_node.append(name_node)
        i_node.append(unk32_node)
    
    return i_node 

#some parameters use y,z,w
def write_vectorparam_node(nodes):
    
    i_node = Element("Item")
    
    name = nodes[0].name[:-2] #remove _x
    type = "Vector"
    
    i_node.set("name", name)
    i_node.set("type", type)
    i_node.set("x", str(nodes[0].outputs[0].default_value))
    i_node.set("y", str(nodes[1].outputs[0].default_value))
    i_node.set("z", str(nodes[2].outputs[0].default_value))
    i_node.set("w", str(nodes[3].outputs[0].default_value))
    
    return i_node

def write_shader_node(mat):
    
    i_node = Element("Item")
    
    name_node = Element("Name")
    name_node.text = fix_shader_name(mat.name, True)
    
    filename_node = Element("FileName")
    filename_node.text = fix_shader_name(mat.name) 
    
    renderbucket_node = Element("RenderBucket")
    renderbucket_node.set("value", "0")
    parameter_set = Shader.shaders.get(fix_shader_name(mat.name))
    if parameter_set is not None:
        for p in parameter_set:
            if p.Type == "RenderBucket":
                renderbucket_node = p.write()
                break
    
    params_node = Element("Parameters")
    
    mat_nodes = mat.node_tree.nodes
    for node in mat_nodes:
        if(isinstance(node, bpy.types.ShaderNodeTexImage)):
            imgp_node = write_imageparam_node(node)
            params_node.append(imgp_node) 
        if(isinstance(node, bpy.types.ShaderNodeValue)):
            if(node.name[-1] == "x"):
                x = node
                y = mat_nodes[node.name[:-1] + "y"]
                z = mat_nodes[node.name[:-1] + "z"]
                w = mat_nodes[node.name[:-1] + "w"]
                vnode = write_vectorparam_node([x, y, z, w])
                params_node.append(vnode)
    
    i_node.append(name_node)
    i_node.append(filename_node)
    i_node.append(renderbucket_node)
    i_node.append(params_node)
    
    return i_node
    

def write_shaders_node(materials):
    
    shaders_node = Element("Shaders")

    for mat in materials:
        shader_node = write_shader_node(mat)
        shaders_node.append(shader_node)
        
    #print(prettify(shader_node))    
    
    return shaders_node

def write_tditem_node(exportpath, mat):
    
    i_nodes = []
    
    mat_nodes = mat.node_tree.nodes
    for node in mat_nodes:
        if(isinstance(node, bpy.types.ShaderNodeTexImage)):
            
            if(node.embedded == False):
                i_nodes.append(None)
            else:
                if(node.image != None):
                    
                
                    foldername = "\\" + os.path.splitext(os.path.splitext(os.path.basename(exportpath))[0])[0]
                    
                    if(os.path.isdir(os.path.dirname(exportpath) + foldername) == False):
                        os.mkdir(os.path.dirname(exportpath) + foldername)
                    
                    sane_path = lambda p: os.path.abspath(bpy.path.abspath(p))

                    txtpath = node.image.filepath
                    if txtpath.startswith('//') is True:
                        txtpath = sane_path(txtpath)

                    dstpath = os.path.dirname(exportpath) + foldername + "\\" + os.path.basename(node.image.filepath)
                    # SameFileError
                    if txtpath != dstpath:
                        try:
                            shutil.copyfile(txtpath, dstpath)
                        except:
                            print("Error copying " + txtpath + " to " + dstpath)
                else:
                    print("Missing Embedded Texture, please supply texture! The texture will not be copied to the texture folder until entered!")

                #node.image.save_render(os.path.dirname(exportpath) + "\\untitled\\"+ os.path.basename(node.image.filepath), scene=None)
                
                i_node = Element("Item")
                
                name_node = Element("Name")
                name_node.text = os.path.splitext(node.texture_name)[0]
                i_node.append(name_node)
                
                unk32_node = Element("Unk32")
                unk32_node.set("value", "128")
                i_node.append(unk32_node)
                
                usage_node = Element("Usage")
                usage_node.text = node.usage
                i_node.append(usage_node)
                
                uflags_node = Element("UsageFlags")
                uflags_text = "" 
                 
                if(node.not_half == True):
                    uflags_text += "NOT_HALF, "
                if(node.hd_split == True):
                    uflags_text += "HD_SPLIT, "
                if(node.flag_full == True):
                    uflags_text += "FULL, "
                if(node.maps_half == True):
                    uflags_text += "MAPS_HALF, "
                if(node.x2 == True):
                    uflags_text += "X2, "
                if(node.x4 == True):
                    uflags_text += "X4, "
                if(node.y4 == True):
                    uflags_text += "Y4, "
                if(node.x8 == True):
                    uflags_text += "MAPS_HALF, "
                if(node.x16 == True):
                    uflags_text += "X16, "
                if(node.x32 == True):
                    uflags_text += "X32, "
                if(node.x64 == True):
                    uflags_text += "X64, "
                if(node.y64 == True):
                    uflags_text += "Y64, "
                if(node.x128 == True):
                    uflags_text += "X128, "
                if(node.x256 == True):
                    uflags_text += "X256, "
                if(node.x512 == True):
                    uflags_text += "X512, "
                if(node.y512 == True):
                    uflags_text += "Y512, "
                if(node.x1024 == True):
                    uflags_text += "X1024, "
                if(node.y1024 == True):
                    uflags_text += "Y1024, "
                if(node.x2048 == True):
                    uflags_text += "X2048, "
                if(node.y2048 == True):
                    uflags_text += "Y2048, "
                if(node.embeddedscriptrt == True):
                    uflags_text += "EMBEDDEDSCRIPTRT, "
                if(node.unk19 == True):
                    uflags_text += "UNK19, "
                if(node.unk20 == True):
                    uflags_text += "UNK20, "
                if(node.unk21 == True):
                    uflags_text += "UNK21, "
                if(node.unk24 == True):
                    uflags_text += "UNK24, "
                
                uflags_text = uflags_text[:-2] #remove , from str
                uflags_node.text = uflags_text
                
                i_node.append(uflags_node)

                eflags_node = Element("ExtraFlags")
                eflags_node.set("value", str(node.extra_flags))
                i_node.append(eflags_node)
                
                width_node = Element("Width")
                
                size = [0, 0]
                if(node.image != None):
                    size = node.image.size
                    
                width_node.set("value", str(size[0]))
                i_node.append(width_node)
                
                height_node = Element("Height")
                height_node.set("value", str(size[1]))
                i_node.append(height_node)
                
                miplevels_node = Element("MipLevels")
                miplevels_node.set("value", "8")
                i_node.append(miplevels_node)
                
                format_node = Element("Format")
                format_node.text = "D3DFMT_" + node.format_type
                i_node.append(format_node)
                
                filename_node = Element("FileName")
                filename_node.text = node.texture_name
                i_node.append(filename_node)
                
                i_nodes.append(i_node)
                    
    return i_nodes 

def write_texturedictionary_node(materials, exportpath):
    
    td_node = Element("TextureDictionary")
    
    all_nodes = []
    
    for mat in materials:
        i_nodes = write_tditem_node(exportpath, mat)
        
        for node in i_nodes:
            if(node != None):
                all_nodes.append(node)
    
    #removes duplicate embedded textures!
    for node in all_nodes: 
        t_name = node[0].text
        
        append = True 
        
        for t in td_node:
            if(t[0].text == t_name):
                append = False
                
        if(append == True):
            td_node.append(node)        
    
    return td_node

def write_shader_group_node(materials, filepath):
    
    shaderg_node = Element("ShaderGroup")
    unk30_node = Element("Unknown30")
    unk30_node.set("value", "0")
    
    td_node = write_texturedictionary_node(materials, filepath)
    
    shader_node = write_shaders_node(materials)
    
    shaderg_node.append(unk30_node)
    shaderg_node.append(td_node)
    shaderg_node.append(shader_node)
    
    return shaderg_node

def write_skeleton_node(obj):
    bones = obj.pose.bones
    if len(bones) == 0:
        return None

    skeleton_node = Skeleton()

    ind = 0
    for pbone in bones:
        bone = pbone.bone
        bone["BONE_INDEX"] = ind
        ind = ind + 1

    for pbone in bones:
        bone = pbone.bone

        bone_node = Bone()
        bone_node.name = bone.name
        bone_node.tag = bone.bone_properties.tag
        bone_node.index = bone["BONE_INDEX"]

        if bone.parent != None:
            bone_node.parent_index = bone.parent["BONE_INDEX"]
            children = bone.parent.children
            sibling = -1
            if len(children) > 1:
                for i, child in enumerate(children):
                    if child["BONE_INDEX"] == bone["BONE_INDEX"] and i + 1 < len(children):
                        sibling = children[i + 1]["BONE_INDEX"]
                        break

            bone_node.sibling_index = sibling

        for flag in bone.bone_properties.flags:
            bone_node.flags.append(flag.name)

        if len(bone.children) > 0:
            bone_node.flags.append("Unk0")

        mat = bone.matrix_local
        if (bone.parent != None):
            mat = bone.parent.matrix_local.inverted() @ bone.matrix_local

        mat_decomposed = mat.decompose()

        bone_node.translation = mat_decomposed[0]
        bone_node.rotation = mat_decomposed[1]
        bone_node.scale = mat_decomposed[2]

        skeleton_node.bones.append(bone_node)

    return skeleton_node

def get_bbs(objs):
    bounding_boxs = []
    for obj in objs:
        bounding_boxs.append(obj.bound_box)
        
    bounding_boxmin = []
    bounding_boxmax = []

    for b in bounding_boxs:
        bounding_boxmin.append(b[0])
        bounding_boxmax.append(b[6])
    
    min_xs = []
    min_ys = []
    min_zs = []
    for v in bounding_boxmin:
        min_xs.append(v[0])
        min_ys.append(v[1])
        min_zs.append(v[2])
        
    max_xs = []
    max_ys = []
    max_zs = []
    for v in bounding_boxmax:
        max_xs.append(v[0])
        max_ys.append(v[1])
        max_zs.append(v[2])
    
    bounding_box_min = []    
    bounding_box_min.append(min(min_xs))
    bounding_box_min.append(min(min_ys))
    bounding_box_min.append(min(min_zs))
    
    bounding_box_max = []    
    bounding_box_max.append(max(max_xs))
    bounding_box_max.append(max(max_ys))
    bounding_box_max.append(max(max_zs))
    
    return [bounding_box_min, bounding_box_max]

def add_vector_list(list1, list2):
    x = list1[0] + list2[0]
    y = list1[1] + list2[1]
    z = list1[2] + list2[2]     
    return [x, y, z]

def subtract_vector_list(list1, list2):
    x = list1[0] - list2[0]
    y = list1[1] - list2[1]
    z = list1[2] - list2[2]     
    return [x, y, z]

def multiple_vector_list(list, num):
    x = list[0] * num
    y = list[1] * num
    z = list[2] * num
    return [x, y, z]

def get_vector_list_length(list):
    
    sx = list[0]**2  
    sy = list[1]**2
    sz = list[2]**2
    length = (sx + sy + sz) ** 0.5
    return length 
    
    
def get_sphere_bb(objs, bbminmax):
    
    allverts = []
    for obj in objs:
        mesh = obj.data
        if mesh is None:
            continue
        
        for vert in mesh.vertices:
            allverts.append(vert)
    bscen = [0, 0, 0]
    bsrad = 0
    
    av = add_vector_list(bbminmax[0], bbminmax[1])
    bscen = multiple_vector_list(av, 0.5)

    for v in allverts:
        bsrad = max(bsrad, get_vector_list_length(subtract_vector_list(v.co, bscen)))

    return [bscen, bsrad]   

#still presents a problem where in a scenario you had other ydrs you didnt want to export in the scene it would pick up 
#them materials also 
def get_used_materials(drawable):
    
    materials = []
    
    children = drawable.children

    for obj in children:
        if(obj.sollumtype == "Geometry"):
            mat = obj.active_material
            if(mat != None):
                materials.append(mat)          

    return materials

def write_drawable(obj, filepath, root_name="Drawable", bones=None):
    
    children = get_obj_children(obj)
    bbminmax = get_bbs(children)
    bbsphere = get_sphere_bb(children, bbminmax)
    
    drawable_node = Drawable()
    drawable_node.name = obj.name.split(".")[0]
    
    drawable_node.bounding_sphere_center = bbsphere[0]
    drawable_node.bounding_sphere_radius = bbsphere[1]
    
    drawable_node.bounding_box_min = bbminmax[0]
    drawable_node.bounding_box_max = bbminmax[1]
    
    drawable_node.lod_dist_high = obj.drawble_distance_high
    drawable_node.lod_dist_med = obj.drawble_distance_medium
    drawable_node.lod_dist_low = obj.drawble_distance_low
    drawable_node.lod_dist_vlow = obj.drawble_distance_vlow

    geometries_high = []
    geometries_med = []
    geometries_low = []
    geometries_vlow = []

    materials = get_used_materials(obj)
    bounds = []
    if bones == None:
        bones = obj.pose.bones

    flagshigh = 0
    flagsmed = 0
    flagslow = 0
    flagsvlow = 0
    
    for c in children:
        if(c.sollumtype == "Geometry"):
            if(c.level_of_detail == "High"):
                geometries_high.append(c)
                flagshigh += 1
            if(c.level_of_detail == "Medium"):
                geometries_med.append(c)
                flagsmed += 1
            if(c.level_of_detail == "Low"):
                geometries_low.append(c)
                flagslow += 1
            if(c.level_of_detail == "Very Low"):
                geometries_vlow.append(c)
                flagsvlow += 1

    drawable_node.flags_high = flagshigh
    drawable_node.flags_med = flagsmed
    drawable_node.flags_low = flagslow
    drawable_node.flags_vlow = flagsvlow

    shadergroup_node = write_shader_group_node(materials, filepath)

    drawable_node.skeleton = write_skeleton_node(obj)
    drawable_node.drawable_models_high = write_drawablemodels_node(geometries_high, materials, bones)
    drawable_node.drawable_models_med = write_drawablemodels_node(geometries_med, materials, bones)
    drawable_node.drawable_models_low = write_drawablemodels_node(geometries_low, materials, bones)
    drawable_node.drawable_models_vlow = write_drawablemodels_node(geometries_vlow, materials, bones)

    bounds_node = None
    
    node = drawable_node.write_xml(root_name)
    node.append(shadergroup_node)

    if(bounds_node != None):
        node.append(bounds_node)
    
    return node
    
def get_hash(obj):
    return JenkHash.Generate(obj.name.split(".")[0])

def write_drawable_dictionary(obj, filepath):
    drawable_dictionary_node = Element("DrawableDictionary")
    
    children = get_obj_children(obj)
    children.sort(key=get_hash)

    bones = None
    for c in children:
        if c.sollumtype == "Drawable" and len(c.pose.bones) > 0:
            bones = c.pose.bones
            break

    for c in children:
        if c.sollumtype == "Drawable":
            drawable_node = write_drawable(c, filepath, "Item", bones)
            drawable_dictionary_node.append(drawable_node)

    return drawable_dictionary_node

def write_ydr_xml(context, filepath):
    
    root = None

    # objects = bpy.context.scene.collection.objects
    active_object = context.active_object

    # if(len(objects) == 0):
    #     return "No objects in scene for Sollumz export"
    
    #select the object first?
    if(active_object.sollumtype == "Drawable"):
        root = write_drawable(active_object, filepath)
        try: 
            print("*** Complete ***")
        except:
            print(str(Exception))
            return str(Exception)

    if(root == None):
        return "No Sollumz Drawable found to export"
    
    # xmlstr = prettify(root)
    # Formatting.prettyxml(root)
    ElementTree.indent(root)
    xmlstr = ElementTree.tostring(root)
    with open(filepath, "wb") as f:
        f.write(xmlstr)
        return "Sollumz Drawable was succesfully exported to " + filepath

def write_ydd_xml(context, filepath):
    
    root = None

    active_object = context.active_object

    # if(len(objects) == 0):
    #     return "No objects in scene for Sollumz export"
    
    #select the object first?
    if(active_object.sollumtype == "Drawable Dictionary"):
        root = write_drawable_dictionary(active_object, filepath)
        try: 
            print("*** Complete ***")
        except:
            print(str(Exception))
            return str(Exception)

    if(root == None):
        return "No Sollumz Drawable found to export"
    
    # xmlstr = prettify(root)
    # Formatting.prettyxml(root)
    ElementTree.indent(root)
    xmlstr = ElementTree.tostring(root)
    with open(filepath, "wb") as f:
        f.write(xmlstr)
        return "Sollumz Drawable was succesfully exported to " + filepath

class ExportYDR(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "exportxml.ydr"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Ydr Xml (.ydr.xml)"

    # ExportHelper mixin class uses this
    filename_ext = ".ydr.xml"
    check_extension = None

    filter_glob: StringProperty(
        default="*.ydr.xml",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        start = datetime.now()
        
        #try:
        result = write_ydr_xml(context, self.filepath)
        self.report({'INFO'}, result)
        
        #except Exception:
        #    self.report({"ERROR"}, str(Exception) )
            
        finished = datetime.now()
        difference = (finished - start).total_seconds()
        print("Exporting : " + self.filepath)
        print("Export Time:")
        print("start time: " + str(start))
        print("end time: " + str(finished))
        print("difference: " + str(difference) + " seconds")
        return {'FINISHED'}

class ExportYDD(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "exportxml.ydd"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export Ydd Xml (.ydd.xml)"

    # ExportHelper mixin class uses this
    filename_ext = ".ydd.xml"
    check_extension = None

    filter_glob: StringProperty(
        default="*.ydd.xml",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        start = datetime.now()
        
        #try:
        result = write_ydd_xml(context, self.filepath)
        self.report({'INFO'}, result)
        
        #except Exception:
        #    self.report({"ERROR"}, str(Exception) )
            
        finished = datetime.now()
        difference = (finished - start).total_seconds()
        print("Exporting : " + self.filepath)
        print("Export Time:")
        print("start time: " + str(start))
        print("end time: " + str(finished))
        print("difference: " + str(difference) + " seconds")
        return {'FINISHED'}

# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportYDR.bl_idname, text="Ydr Xml Export (.ydr.xml)")
    self.layout.operator(ExportYDD.bl_idname, text="Ydd Xml Export (.ydd.xml)")

def register():
    bpy.utils.register_class(ExportYDR)
    bpy.utils.register_class(ExportYDD)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportYDR)
    bpy.utils.unregister_class(ExportYDD)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
