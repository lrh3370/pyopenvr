#!/bin/env python

# file tracked_devices_actor.py

import time
from textwrap import dedent
from ctypes import sizeof, cast, c_float, c_void_p

import numpy
from OpenGL.GL import *  # @UnusedWildImport # this comment squelches an IDE warning
from OpenGL.GL.shaders import compileShader, compileProgram
from OpenGL.arrays import vbo

import openvr
from openvr.gl_renderer import matrixForOpenVrMatrix

"""
Tracked item (controllers, lighthouses, etc) actor for "hello world" openvr apps
"""

class TrackedDeviceMesh(object):
    def __init__(self, model_name):
        "This constructor must only be called with a live OpenGL context"
        self.model_name = model_name
        # http://stackoverflow.com/questions/14365484/how-to-draw-with-vertex-array-objects-and-gldrawelements-in-pyopengl
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        # Load controller model
        error = openvr.EVRRenderModelError()
        while True:
            error, model = openvr.VRRenderModels().loadRenderModel_Async(model_name)
            if error != openvr.VRRenderModelError_Loading:
                break
            time.sleep(1)
        vertices0 = list()
        indices0 = list()
        if model is not None:
            for v in range (model.unVertexCount):
                vd = model.rVertexData[v]
                vertices0.append(float(vd.vPosition.v[0])) # position X
                vertices0.append(float(vd.vPosition.v[1])) # position Y
                vertices0.append(float(vd.vPosition.v[2])) # position Z
                vertices0.append(float(vd.vNormal.v[0])) # normal X
                vertices0.append(float(vd.vNormal.v[1])) # normal Y
                vertices0.append(float(vd.vNormal.v[2])) # normal Z
                vertices0.append(float(vd.rfTextureCoord[0])) # texture coordinate U
                vertices0.append(float(vd.rfTextureCoord[1])) # texture coordinate V
            for i in range (model.unTriangleCount * 3):
                index = model.rIndexData[i]
                indices0.append(int(index))
        vertices0 = numpy.array(vertices0, dtype=numpy.float32)
        indices0 = numpy.array(indices0, dtype=numpy.uint32)
        #
        self.vertexPositions = vbo.VBO(vertices0)
        self.indexPositions = vbo.VBO(indices0, target=GL_ELEMENT_ARRAY_BUFFER)

    def display_gl(self, modelview, projection, pose):
        controller_X_room = pose.mDeviceToAbsoluteTracking
        controller_X_room = matrixForOpenVrMatrix(controller_X_room)
        modelview0 = controller_X_room * modelview
        # Repack before use, just in case
        modelview0 = numpy.matrix(modelview0, dtype=numpy.float32)
        glUniformMatrix4fv(4, 1, False, modelview0)
        normal_matrix = controller_X_room.I.T
        normal_matrix = numpy.matrix(normal_matrix, dtype=numpy.float32)
        glUniformMatrix4fv(8, 1, False, normal_matrix)
        self.indexPositions.bind()
        self.vertexPositions.bind()
        # Vertices
        glEnableVertexAttribArray(0)
        fsize = sizeof(c_float)
        glVertexAttribPointer(0, 3, GL_FLOAT, False, 8 * fsize, cast(0 * fsize, c_void_p))
        # Normals
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, False, 8 * fsize, cast(3 * fsize, c_void_p))
        # Texture coordinates    
        glEnableVertexAttribArray(2)
        glVertexAttribPointer(2, 2, GL_FLOAT, False, 8 * fsize, cast(6 * fsize, c_void_p))
        #
        glDrawElements(GL_TRIANGLES, len(self.indexPositions), GL_UNSIGNED_INT, None)
        
    def dispose_gl(self):
        glDeleteBuffers(1, (self.vbo,))
        self.vbo = 0        


class TrackedDevicesActor(object):
    """
    Draws Vive controllers and lighthouses.
    """
    
    def __init__(self, pose_array):
        self.shader = 0
        self.poses = pose_array
        self.meshes = dict()
    
    def _check_devices(self):
        "Enumerate OpenVR tracked devices and check whether any need to be initialized"
        for i in range(1, len(self.poses)):
            pose = self.poses[i]
            if not pose.bPoseIsValid:
                continue
            model_name = openvr.VRSystem().getStringTrackedDeviceProperty(i, openvr.Prop_RenderModelName_String)
            if not model_name in self.meshes:
                self.meshes[model_name] = TrackedDeviceMesh(model_name)
    
    def init_gl(self):
        vertex_shader = compileShader(dedent(
            """\
            #version 450 core
            #line 40
            
            layout(location = 0) in vec3 in_Position;
            layout(location = 1) in vec3 in_Normal;
            layout(location = 2) in vec2 in_TexCoord;
            
            layout(location = 0) uniform mat4 projection = mat4(1);
            layout(location = 4) uniform mat4 model_view = mat4(1);
            layout(location = 8) uniform mat4 normal_matrix = mat4(1);
            
            out vec3 color;
            
            void main() {
              gl_Position = projection * model_view * vec4(in_Position, 1.0);
              vec3 normal = normalize((normal_matrix * vec4(in_Normal, 0)).xyz);
              color = (normal + vec3(1,1,1)) * 0.5; // color by normal
              // color = vec3(in_TexCoord, 0.5); // color by texture coordinate
            }
            """), 
            GL_VERTEX_SHADER)
        fragment_shader = compileShader(dedent(
            """\
            #version 450 core
            #line 59
            
            in vec3 color;
            out vec4 fragColor;
            
            void main() {
              fragColor = vec4(color, 1.0);
            }
            """), 
            GL_FRAGMENT_SHADER)
        self.shader = compileProgram(vertex_shader, fragment_shader)
        self._check_devices()
        glEnable(GL_DEPTH_TEST)
        
    def display_gl(self, modelview, projection):
        self._check_devices()
        glUseProgram(self.shader)
        glUniformMatrix4fv(0, 1, False, projection)
        for i in range(1, len(self.poses)):
            pose = self.poses[i]
            if not pose.bPoseIsValid:
                continue
            model_name = openvr.VRSystem().getStringTrackedDeviceProperty(i, openvr.Prop_RenderModelName_String)
            if not model_name in self.meshes:
                continue # Come on, we already tried to load it a moment ago. Maybe next time.
            mesh = self.meshes[model_name]
            mesh.display_gl(modelview, projection, pose)
    
    def dispose_gl(self):
        glDeleteProgram(self.shader)
        self.shader = 0
        for key, mesh in self.meshes.iteritems():
            mesh.dispose_gl()
            del self.meshes[key]