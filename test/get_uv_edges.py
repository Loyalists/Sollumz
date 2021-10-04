import bpy
import bmesh
import math

obj = bpy.context.object
me = obj.data
bm = bmesh.from_edit_mesh(me)
uv_layer = bm.loops.layers.uv.active
vert_uv_map = {}
unsafe_verts = set()

for face in bm.faces:
    for loop in face.loops:
        vert = loop.vert
        uv = loop[uv_layer].uv
        value = vert_uv_map.get(vert)
        if value is None:
            vert_uv_map[vert] = uv
        else:
            if not vert in unsafe_verts:
                indicator = math.sqrt((value[0]-uv[0])**2 + (value[1]-uv[1])**2)
                if indicator > 0.0001:
                    unsafe_verts.add(vert)

for vert in unsafe_verts:
    for edge in vert.link_edges:
        if edge.other_vert(vert) in unsafe_verts:
            edge.select_set(True)

bmesh.update_edit_mesh(me)