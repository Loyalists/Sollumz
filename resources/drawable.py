import os
import xml.etree.ElementTree as ET
import time
from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from mathutils import Vector, Quaternion, Matrix
from ..ybnimport import read_composite_info_children
from ..tools import xmlhelper, xml
from .shader import ShaderGroup
from collections import deque

layout_map = {
    "Position": 0,
    "Normal": 1,
    "Colour0": 2,
    "Colour1": 3,
    "TexCoord0": 4,
    "TexCoord1": 5,
    "TexCoord2": 6,
    "TexCoord3": 7,
    "TexCoord4": 8,
    "TexCoord5": 9,
    "TexCoord6": 10,
    "TexCoord7": 11,
    "Tangent": 12,
    "BlendWeights": 13,
    "BlendIndices": 14,
}

class Bone:

    def __init__(self):
        self.name = ""
        self.tag = 0
        self.index = 0
        self.parent_index = -1
        self.sibling_index = -1
        self.flags = []
        self.translation = Vector()
        self.rotation = Quaternion()
        self.scale = Vector()
        self.transform_unk = Quaternion((0, 4, -3, 0))

    def read_xml(self, root):

        if root is None:
            return

        flags_item = root.find("Flags")
        translation_item = root.find("Translation")
        rotation_item = root.find("Rotation")
        scale_item = root.find("Scale")

        self.name = root.find("Name").text
        self.tag = xmlhelper.ReadInt(root.find("Tag"))
        self.index = xmlhelper.ReadInt(root.find("Index"))
        self.parent_index = xmlhelper.ReadInt(root.find("ParentIndex"))
        self.sibling_index = xmlhelper.ReadInt(root.find("SiblingIndex"))
        if (flags_item.text != None):
            self.flags = flags_item.text.strip().split(", ")

        self.transform_unk = xmlhelper.ReadQuaternion(root.find("TransformUnk"))

        self.translation = Vector()
        self.translation.x = float(translation_item.attrib["x"])
        self.translation.y = float(translation_item.attrib["y"])
        self.translation.z = float(translation_item.attrib["z"])

        self.rotation = Quaternion()
        self.rotation.w = float(rotation_item.attrib["w"])
        self.rotation.x = float(rotation_item.attrib["x"])
        self.rotation.y = float(rotation_item.attrib["y"])
        self.rotation.z = float(rotation_item.attrib["z"])

        self.scale = Vector()
        self.scale.x = float(scale_item.attrib["x"])
        self.scale.y = float(scale_item.attrib["y"])
        self.scale.z = float(scale_item.attrib["z"])

    @staticmethod
    def from_xml(root):
        bone = Bone()
        bone.read_xml(root)
        return bone

    def write_xml(self):
        bone_node = Element("Item")

        name_node = Element("Name")
        name_node.text = self.name

        tag_node = Element("Tag")
        tag_node.set("value", str(self.tag))

        index_node = Element("Index")
        index_node.set("value", str(self.index))

        parent_index_node = Element("ParentIndex")
        parent_index_node.set("value", str(self.parent_index))

        sibling_index_node = Element("SiblingIndex")
        sibling_index_node.set("value", str(self.sibling_index))

        flags_node = Element("Flags")
        flags_node.text = ", ".join(self.flags)

        translation_node = Element("Translation")
        translation_node.set("x", str(self.translation.x))
        translation_node.set("y", str(self.translation.y))
        translation_node.set("z", str(self.translation.z))

        rotation_node = Element("Rotation")
        rotation_node.set("w", str(self.rotation.w))
        rotation_node.set("x", str(self.rotation.x))
        rotation_node.set("y", str(self.rotation.y))
        rotation_node.set("z", str(self.rotation.z))

        scale_node = Element("Scale")
        scale_node.set("x", str(self.scale.x))
        scale_node.set("y", str(self.scale.y))
        scale_node.set("z", str(self.scale.z))

        transform_unk_node = Element("TransformUnk")
        transform_unk_node.set("w", str(self.transform_unk.w))
        transform_unk_node.set("x", str(self.transform_unk.x))
        transform_unk_node.set("y", str(self.transform_unk.y))
        transform_unk_node.set("z", str(self.transform_unk.z))

        bone_node.append(name_node)
        bone_node.append(tag_node)
        bone_node.append(index_node)
        bone_node.append(parent_index_node)
        bone_node.append(sibling_index_node)
        bone_node.append(flags_node)
        bone_node.append(translation_node)
        bone_node.append(rotation_node)
        bone_node.append(scale_node)
        bone_node.append(transform_unk_node)

        return bone_node

class Skeleton:

    def __init__(self):
        #TODO: the current implementation works but IMHO there should be something more meaningful than "0"
        #as long as it doesn't break in game
        # from player_zero.yft
        self.unknown_1c = 16777216
        self.unknown_50 = 567032952
        self.unknown_54 = 2134582703
        self.unknown_58 = 0
        self.bones = []

    def read_xml(self, root):
        self.unknown_1c = xmlhelper.ReadInt(root.find("Unknown1C"))
        self.unknown_50 = xmlhelper.ReadInt(root.find("Unknown50"))
        self.unknown_54 = xmlhelper.ReadInt(root.find("Unknown54"))
        self.unknown_58 = xmlhelper.ReadInt(root.find("Unknown58"))

        for node in root.find("Bones"):
            b = Bone().from_xml(node)
            self.bones.append(b)

    @staticmethod
    def from_xml(root):
        skel = Skeleton()
        skel.read_xml(root)
        return skel

    def write_xml(self):
        skeleton_node = Element("Skeleton")
        unk1c_node = Element("Unknown1C")
        unk1c_node.set("value", str(self.unknown_1c))

        unk50_node = Element("Unknown50")
        unk50_node.set("value", str(self.unknown_50))

        unk54_node = Element("Unknown54")
        unk54_node.set("value", str(self.unknown_54))

        unk58_node = Element("Unknown58")
        unk58_node.set("value", str(self.unknown_58))

        bones_node = Element("Bones")
        for bone in self.bones:
            bone_node = bone.write_xml()
            bones_node.append(bone_node)

        skeleton_node.append(unk1c_node)
        skeleton_node.append(unk50_node)
        skeleton_node.append(unk54_node)
        skeleton_node.append(unk58_node)
        skeleton_node.append(bones_node)

        return skeleton_node

class Joint:

    def __init__(self, xml, type):

        self.type = type
        self.tag = xmlhelper.ReadInt(xml.find("BoneId"))

        min_item = xml.find("Min")
        self.min = Vector()
        self.min.x = float(min_item.attrib["x"])
        self.min.y = float(min_item.attrib["y"])
        self.min.z = float(min_item.attrib["z"])

        max_item = xml.find("Max")
        self.max = Vector()
        self.max.x = float(max_item.attrib["x"])
        self.max.y = float(max_item.attrib["y"])
        self.max.z = float(max_item.attrib["z"])

    def apply(self, bone):

        if bone is None:
            return None

        constraint = bone.constraints.new('LIMIT_ROTATION')
        constraint.owner_space = 'LOCAL'
        constraint.use_limit_x = True
        constraint.use_limit_y = True
        constraint.use_limit_z = True
        constraint.max_x = float(self.max.x)
        constraint.max_y = float(self.max.y)
        constraint.max_z = float(self.max.z)
        constraint.min_x = float(self.min.x)
        constraint.min_y = float(self.min.y)
        constraint.min_z = float(self.min.z)

        return bone.name

    def write_xml(self, bone):
        if bone is None:
            return None
        
        nodes = []
        for con in bone.constraints:
            if con.type == 'LIMIT_ROTATION':
                self.type = "RotationLimits"
                self.tag = bone.bone.bone_properties.tag
                self.min = Vector(con.min_x, con.min_y, con.min_z)
                self.max = Vector(con.max_x, con.max_y, con.max_z)
                con_node = Element(self.type)

                tag_node = Element("BoneId")
                tag_node.set("value", str(self.tag))

                unka_node = Element("UnknownA")
                unka_node.set("value", "0")

                min_node = Element("Min")
                min_node.set("x", con.min_x)
                min_node.set("y", con.min_y)
                min_node.set("z", con.min_z)

                max_node = Element("Max")
                max_node.set("x", con.max_x)
                max_node.set("y", con.max_y)
                max_node.set("z", con.max_z)

                con_node.append(tag_node)
                con_node.append(unka_node)
                con_node.append(min_node)
                con_node.append(max_node)
                nodes.append(con_node)

        return nodes

class Vertex:

    def __init__(self):
        self.position = None
        self.blendweights = None
        self.blendindices = None
        self.colors0 = None
        self.colors1 = None
        self.texcoord0 = None
        self.texcoord1 = None
        self.texcoord2 = None
        self.texcoord3 = None
        self.texcoord4 = None
        self.texcoord5 = None
        self.texcoord6 = None
        self.texcoord7 = None
        self.tangent = None
        self.normal = None

    @staticmethod    
    def from_xml(layout, data):
        
        result = Vertex()

        for i in range(len(layout)):
            current_data = data[i].split()
            current_layout_key = layout[i]
            if(current_layout_key == "Position"):
                result.position = xmlhelper.StringListToVector(current_data)
            elif(current_layout_key == "BlendWeights"):
                result.blendweights = xmlhelper.StringListToIntList(current_data)
            elif(current_layout_key == "BlendIndices"):
                result.blendindices = xmlhelper.StringListToIntList(current_data)
            elif(current_layout_key == "Colour0"):
                result.colors0 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "Colour1"):
                result.colors1 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "TexCoord0"):
                result.texcoord0 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "TexCoord1"):
                result.texcoord1 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "TexCoord2"):
                result.texcoord2 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "TexCoord3"):
                result.texcoord3 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "TexCoord4"):
                result.texcoord4 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "TexCoord5"):
                result.texcoord5 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "TexCoord6"):
                result.texcoord6 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "TexCoord7"):
                result.texcoord7 = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "Tangent"):
                result.tangent = xmlhelper.StringListToFloatList(current_data)
            elif(current_layout_key == "Normal"):
                result.normal = xmlhelper.StringListToFloatList(current_data)

        return result

    @staticmethod
    def __vector_tostring(vector):
        string = [str(vector.x), str(vector.y)]
        if(hasattr(vector, "z")):
            string.append(str(vector.z))

        if(hasattr(vector, "w")):
            string.append(str(vector.w))

        return " ".join(string)

    @staticmethod
    def __meshloopcolor_tostring(color):
        string = " ".join(str(round(color[i] * 255)) for i in range(4))
        return string 

    def to_string(self, vlayout):
        vertex_str = [None] * 15

        if self.position is not None:
            vertex_str[0] = self.__vector_tostring(self.position)

        if self.normal is not None:
            vertex_str[1] = self.__vector_tostring(self.normal)

        if self.colors0 is not None:
            vertex_str[2] = self.__meshloopcolor_tostring(self.colors0)

        if self.colors1 is not None:
            vertex_str[3] = self.__meshloopcolor_tostring(self.colors1)

        if self.texcoord0 is not None:
            vertex_str[4] = self.__vector_tostring(self.texcoord0)

        if self.texcoord1 is not None:
            vertex_str[5] = self.__vector_tostring(self.texcoord1)

        if self.texcoord2 is not None:
            vertex_str[6] = self.__vector_tostring(self.texcoord2)

        if self.texcoord3 is not None:
            vertex_str[7] = self.__vector_tostring(self.texcoord3)

        if self.texcoord4 is not None:
            vertex_str[8] = self.__vector_tostring(self.texcoord4)

        if self.texcoord5 is not None:
            vertex_str[9] = self.__vector_tostring(self.texcoord5)

        if self.texcoord6 is not None:
            vertex_str[10] = self.__vector_tostring(self.texcoord6)

        if self.texcoord7 is not None:
            vertex_str[11] = self.__vector_tostring(self.texcoord7)

        if self.tangent is not None:
            vertex_str[12] = self.__vector_tostring(self.tangent)

        if self.blendweights is not None:
            vertex_str[13] = ' '.join(str(i) for i in self.blendweights)

        if self.blendindices is not None:
            vertex_str[14] = ' '.join(str(i) for i in self.blendindices)

        newlist = deque()

        for i in range(len(vlayout)):
            layout_key = layout_map[vlayout[i]]
            if layout_key != None:
                if vertex_str[layout_key] is None:
                    raise TypeError("Missing layout item " + vlayout[i])

                newlist.append(vertex_str[layout_key])
            else:
                print('Incorrect layout element', vlayout[i])

        if (len(newlist) != len(vlayout)):
            print('Incorrect layout parse')

        return (" " * 3).join(newlist)

class VertexBuffer:

    def __init__(self):
        self.flags = 0
        self.layout = []
        self.data = ""
        self.vertices = []

    def read_xml(self, root):
        self.flags = xmlhelper.ReadInt(root.find("Flags"))

        layout = root.find("Layout")
        for node in layout:
            self.layout.append(node.tag)

        data_node = root[2]
        if data_node is None:
            return
            
        self.data = data_node.text.strip()

        lines = self.data.split("\n")
        for line in lines:
            v = Vertex.from_xml(self.layout, line.strip().split(" " * 3))
            self.vertices.append(v)

    def write_xml(self):
        vb_node = Element("VertexBuffer")

        vbflags_node = Element("Flags")
        vbflags_node.set("value", "0")
        
        vblayout_node = Element("Layout")
        vblayout_node.set("type", "GTAV1")
        for p in self.layout:
            p_node = Element(p)
            vblayout_node.append(p_node)

        data_node = Element("Data")
        data_node.text = self.data

        vb_node.append(vbflags_node)
        vb_node.append(vblayout_node)
        vb_node.append(data_node)

        return vb_node

    def vertices_to_data(self):
        allstrings = deque()
        allstrings.append("\n") #makes xml a little prettier

        for vertex in self.vertices:
            vstring = (" " * 5, vertex.to_string(self.layout))
            allstrings.append("".join(vstring))
            allstrings.append('\n')
        
        self.data = "".join(allstrings)

class IndexBuffer:

    def __init__(self):
        self.data = ""
        self.buffer = None

    def read_xml(self, root):
        self.data = root.text

        index_buffer = self.data.strip().replace("\n", "").split()
        i_buf = []
        for num in index_buffer:
            i_buf.append(int(num))

        self.buffer = [i_buf[i * 3:(i + 1) * 3] for i in range((len(i_buf) + 3 - 1) // 3 )] #split index buffer into 3s for each triangle

    def write_xml(self):
        ib_node = Element("IndexBuffer")

        data_node = Element("Data")
        data_node.text = self.data
        
        ib_node.append(data_node)

        return ib_node

class Geometry:

    def __init__(self):
        self.shader_index = 0
        self.bounding_box_min = []
        self.bounding_box_max = []
        self.vertex_buffer = "" 
        self.index_buffer = ""
        self.bone_ids = []

    def read_xml(self, root):
        self.shader_index = xmlhelper.ReadInt(root.find("ShaderIndex"))
        self.bounding_box_min = xmlhelper.ReadVector(root.find("BoundingBoxMin"))
        self.bounding_box_max = xmlhelper.ReadVector(root.find("BoundingBoxMax"))

        vb = VertexBuffer()
        vb.read_xml(root.find("VertexBuffer"))
        self.vertex_buffer = vb
        if not len(self.vertex_buffer.vertices) > 0:
            return

        ib = IndexBuffer()
        ib.read_xml(root.find("IndexBuffer")[0])
        self.index_buffer = ib

    @staticmethod
    def from_xml(root):
        geo = Geometry()
        geo.read_xml(root)
        return geo

    @staticmethod
    def set_parent(obj, armature):
        obj.parent = armature
        mod = obj.modifiers.new("Armature", 'ARMATURE')
        mod.object = armature

    def write_xml(self):
        i_node = Element("Item")
        
        shd_index = Element("ShaderIndex")
        shd_index.set("value", str(self.shader_index))
        
        bbmin_node = Element("BoundingBoxMin")
        bbmin_node.set("x", str(self.bound_box_min[0]))
        bbmin_node.set("y", str(self.bound_box_min[1]))
        bbmin_node.set("z", str(self.bound_box_min[2]))
        bbmin_node.set("w", "0")

        bbmax_node = Element("BoundingBoxMax")
        bbmax_node.set("x", str(self.bound_box_max[0]))
        bbmax_node.set("y", str(self.bound_box_max[1]))  
        bbmax_node.set("z", str(self.bound_box_max[2]))
        bbmax_node.set("w", "0")

        boneids_node = Element("BoneIDs")
        boneids_node.text = ", ".join(str(i) for i in range(len(self.bone_ids)))

        vb_node = self.vertex_buffer.write_xml()
        ib_node = self.index_buffer.write_xml()

        i_node.append(shd_index)
        i_node.append(bbmin_node)
        i_node.append(bbmax_node)
        i_node.append(boneids_node)
        i_node.append(vb_node)
        i_node.append(ib_node)

        return i_node

class DrawableModel:

    def __init__(self):
        self.render_mask = 0
        self.flags = 1
        self.has_skin = False
        self.bone_index = 0
        self.unknown_1 = 0
        self.geometries = []

    def read_xml(self, root):
        if root is None:
            return

        self.render_mask = int(root.find("RenderMask").attrib["value"])

        for model in root.find('Geometries'):
            d_obj = Geometry.from_xml(model)
            self.geometries.append(d_obj)

    @staticmethod
    def from_xml(root):
        model = DrawableModel()
        model.read_xml(root)
        return model

    @staticmethod
    def set_parent(objs, armature):
        if objs is not None:
            for obj in objs:
                Geometry.set_parent(obj, armature)

    def write_xml(self):
        m_node = Element("Item")
        
        rm_node = Element("RenderMask")
        rm_node.set("value", str(self.render_mask))

        flags_node = Element("Flags")
        flags_node.set("value", str(self.flags))

        has_skin_node = Element("HasSkin")
        has_skin_node.set("value", str(int(self.has_skin)))

        bone_index_node = Element("BoneIndex")
        bone_index_node.set("value", str(self.bone_index))

        unk1_node = Element("Unknown1")
        unk1_node.set("value", str(self.unknown_1))

        geo_node = Element("Geometries")
        for geo in self.geometries:
            item = geo.write_xml()
            geo_node.append(item)

        m_node.append(rm_node)
        m_node.append(flags_node)
        m_node.append(has_skin_node)
        m_node.append(bone_index_node)
        m_node.append(unk1_node)
        m_node.append(geo_node)

        return m_node

class Drawable:

    def __init__(self):

        self.name = "Drawable"
        self.bounding_sphere_center = [0, 0, 0]
        self.bounding_sphere_radius = 0
        self.bounding_box_min = [0, 0, 0]
        self.bounding_box_max = [0, 0, 0]
        self.lod_dist_high = 0 #9998?
        self.lod_dist_med = 0 #9998?
        self.lod_dist_low = 0 #9998?
        self.lod_dist_vlow = 0 #9998?
        self.flags_high = 0 
        self.flags_med = 0 
        self.flags_low = 0  
        self.flags_vlow = 0
        self.unknown_9A = 0

        self.shader_group = None
        self.skeleton = None
        self.bounds = []
        self.joints = []
        self.drawable_models_high = []
        self.drawable_models_med = []
        self.drawable_models_low = []
        self.drawable_models_vlow = []

    def read_xml(self, root):

        if root is None:
            return

        self.name = xml.ReadText(root.find("Name"), "Drawable", str)

        self.lod_dist_high = float(root.find("LodDistHigh").attrib["value"])
        self.lod_dist_med = float(root.find("LodDistMed").attrib["value"])
        self.lod_dist_low = float(root.find("LodDistLow").attrib["value"])
        self.lod_dist_vlow = float(root.find("LodDistVlow").attrib["value"])

        sg = root.find("ShaderGroup")
        if(sg != None):
            shader_group = ShaderGroup()
            shader_group.read_xml(root.find("ShaderGroup"))
            self.shader_group = shader_group

        skeleton_node = root.find("Skeleton")
        if skeleton_node is not None:
            self.skeleton = Skeleton.from_xml(skeleton_node)

        joints_node = root.find("Joints")
        if joints_node is not None:
            self.joints = []
            if joints_node.find("RotationLimits") is not None:
                for item in joints_node.find("RotationLimits"):
                    joint = Joint(item, "RotationLimits")
                    self.joints.append(joint)

        dmh = root.find("DrawableModelsHigh")
        if(dmh != None):
            for node in dmh:
                dm = DrawableModel()
                dm.read_xml(node)
                self.drawable_models_high.append(dm)

        dmm = root.find("DrawableModelsMed")
        if(dmm != None):
            for node in dmm:
                dm = DrawableModel()
                dm.read_xml(node)
                self.drawable_models_med.append(dm)

        dml = root.find("DrawableModelsLow")
        if(dml != None):
            for node in dml:
                dm = DrawableModel()
                dm.read_xml(node)
                self.drawable_models_low.append(dm)

        dmvl = root.find("DrawableModelsVlow")
        if(dmvl != None):
            for node in dmvl:
                dm = DrawableModel()
                dm.read_xml(node)
                self.drawable_models_vlow.append(dm)

        bounds_node = root.find("Bounds")
        if bounds_node is not None:
            self.bounds = read_composite_info_children(bounds_node)

    @staticmethod
    def from_xml(root):

        drawable = Drawable()
        drawable.read_xml(root)
        return drawable

    def get_bones(self):

        if self.skeleton is None:
            return None

        return self.skeleton.bones

    def is_empty(self):

        if len(self.drawable_models_high) > 0:
            return False

        if len(self.drawable_models_med) > 0:
            return False

        if len(self.drawable_models_low) > 0:
            return False

        if len(self.drawable_models_vlow) > 0:
            return False

        return True

    def write_xml(self, root_name="Drawable"):

        drawable_node = Element(root_name)

        name_node = Element("Name")
        name_node.text = self.name
        
        bsc_node = Element("BoundingSphereCenter")
        bsc_node.set("x", str(self.bounding_sphere_center[0]))
        bsc_node.set("y", str(self.bounding_sphere_center[1]))
        bsc_node.set("z", str(self.bounding_sphere_center[2]))
        
        bsr_node = Element("BoundingSphereRadius")
        bsr_node.set("value", str(self.bounding_sphere_radius))
        
        bbmin_node = Element("BoundingBoxMin")
        bbmin_node.set("x", str(self.bounding_box_min[0]))
        bbmin_node.set("y", str(self.bounding_box_min[1]))
        bbmin_node.set("z", str(self.bounding_box_min[2]))
        
        bbmax_node = Element("BoundingBoxMax")
        bbmax_node.set("x", str(self.bounding_box_max[0]))
        bbmax_node.set("y", str(self.bounding_box_max[1]))
        bbmax_node.set("z", str(self.bounding_box_max[2]))
        
        ldh_node = Element("LodDistHigh")
        ldh_node.set("value", str(self.lod_dist_high))
        ldm_node = Element("LodDistMed")
        ldm_node.set("value", str(self.lod_dist_med))
        ldl_node = Element("LodDistLow")
        ldl_node.set("value", str(self.lod_dist_low))
        ldvl_node = Element("LodDistVlow")
        ldvl_node.set("value", str(self.lod_dist_vlow)) 

        flagsh_node = Element("FlagsHigh")
        flagsh_node.set("value", str(self.flags_high))
        flagsm_node = Element("FlagsMed")
        flagsm_node.set("value", str(self.flags_med))
        flagsl_node = Element("FlagsLow")
        flagsl_node.set("value", str(self.flags_low))
        flagsvl_node = Element("FlagsVlow")
        flagsvl_node.set("value", str(self.flags_vlow))
        Unk9a_node = Element("Unknown9A")
        Unk9a_node.set("value", str(self.unknown_9A))

        skeleton_node = None
        if self.skeleton is not None:
            skeleton_node = self.skeleton.write_xml()

        drawablemodels_high_node = None
        if len(self.drawable_models_high) != 0:
            drawablemodels_high_node = Element("DrawableModelsHigh")
            for model in self.drawable_models_high:
                item = model.write_xml()
                drawablemodels_high_node.append(item)

        drawablemodels_medium_node = None
        if len(self.drawable_models_med) != 0:
            drawablemodels_medium_node = Element("DrawableModelsMedium")
            for model in self.drawable_models_med:
                item = model.write_xml()
                drawablemodels_medium_node.append(item)

        drawablemodels_low_node = None
        if len(self.drawable_models_low) != 0:
            drawablemodels_low_node = Element("DrawableModelsLow")
            for model in self.drawable_models_low:
                item = model.write_xml()
                drawablemodels_low_node.append(item)

        drawablemodels_vlow_node = None
        if len(self.drawable_models_vlow) != 0:
            drawablemodels_vlow_node = Element("DrawableModelsLow")
            for model in self.drawable_models_vlow:
                item = model.write_xml()
                drawablemodels_vlow_node.append(item)

        bounds_node = None

        drawable_node.append(name_node)
        drawable_node.append(bsc_node)
        drawable_node.append(bsr_node)
        drawable_node.append(bbmin_node)
        drawable_node.append(bbmax_node)
        drawable_node.append(ldh_node)
        drawable_node.append(ldm_node)
        drawable_node.append(ldl_node)
        drawable_node.append(ldvl_node)
        drawable_node.append(flagsh_node)
        drawable_node.append(flagsm_node)
        drawable_node.append(flagsl_node)
        drawable_node.append(flagsvl_node)
        drawable_node.append(Unk9a_node)
        #drawable_node.append(shadergroup_node)
        if skeleton_node != None:
            drawable_node.append(skeleton_node)

        if drawablemodels_high_node != None:
            drawable_node.append(drawablemodels_high_node)

        if drawablemodels_medium_node != None:
            drawable_node.append(drawablemodels_medium_node)

        if drawablemodels_low_node != None:
            drawable_node.append(drawablemodels_low_node)

        if drawablemodels_vlow_node != None:
            drawable_node.append(drawablemodels_vlow_node)

        if(bounds_node != None):
            drawable_node.append(bounds_node)

        return drawable_node

class DrawableDictionary:

    def __init__(self):

        self.drawables = []

    def read_xml(self, root):

        if root is None:
            return

        for item in root:
            if item is None:
                continue

            drawable = Drawable.from_xml(item)
            self.drawables.append(drawable)

    @staticmethod
    def from_xml(root):
        drawable_dict = DrawableDictionary()
        drawable_dict.read_xml(root)
        return drawable_dict