#!/bin/env python

# file hello_glfw.py

from textwrap import dedent

from OpenGL.GL import *  # @UnusedWildImport # this comment squelches an IDE warning
from OpenGL.GL.shaders import compileShader, compileProgram
from OpenGL.arrays import vbo
import glfw
import numpy

import openvr

"""
Minimal glfw programming example which creates a blue OpenGL window that can be closed by pressing ESCAPE.
"""


class GlfwApp(object):
    "GlfwApp uses glfw library to create an opengl context, listen to keyboard events, and clean up"

    def __init__(self, renderer, title="GLFW test"):
        "Creates an OpenGL context and a window, and acquires OpenGL resources"
        self.renderer = renderer
        self.title = title
        self._is_initialized = False # keep track of whether self.init_gl() has been called
        self.window = None

    def __enter__(self):
        "setup for RAII using 'with' keyword"
        return self

    def __exit__(self, type_arg, value, traceback):
        "cleanup for RAII using 'with' keyword"
        self.dispose_gl()

    def init_gl(self):
        if self._is_initialized:
            return # only initialize once
        if not glfw.init():
            raise Exception("GLFW Initialization error")
        # Get OpenGL 4.1 context
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        self.window = glfw.create_window(800, 600, self.title, None, None)
        if self.window is None:
            glfw.terminate()
            raise Exception("GLFW window creation error")
        glfw.set_key_callback(self.window, self.key_callback)
        glfw.make_context_current(self.window)
        if self.renderer is not None:
            self.renderer.init_gl()
        self._is_initialized = True

    def render_scene(self):
        "render scene one time"
        self.init_gl() # should be a no-op after the first frame is rendered
        glfw.make_context_current(self.window)
        self.renderer.render_scene()
        # Done rendering
        glfw.swap_buffers(self.window)
        glfw.poll_events()

    def dispose_gl(self):
        if self.window is not None:
            glfw.make_context_current(self.window)
            if self.renderer is not None:
                self.renderer.dispose_gl()
        glfw.terminate()
        self._is_initialized = False

    def key_callback(self, window, key, scancode, action, mods):
        "press ESCAPE to quit the application"
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.set_window_should_close(self.window, True)

    def run_loop(self):
        "keep rendering until the user says quit"
        while not glfw.window_should_close(self.window):
            self.render_scene()


class BasicGlResource(object):
    "No-op OpenGL object to be used as an abstract base class for OpenGL actors"

    def init_gl(self):
        "allocate OpenGL resources"
        pass

    def display_gl(self, modelview, projection):
        "render scene one time"
        pass

    def dispose_gl(self):
        "delete OpenGL resources"
        pass


class OpenVrGlRenderer(BasicGlResource):
    "Renders to virtual reality headset using OpenVR and OpenGL APIs"

    def __init__(self, actor):
        self.actor = actor
        self.vr_system = None
        self.texture_id = 0
        self.fb = 0
        self.depth_buffer = 0

    def init_gl(self):
        "allocate OpenGL resources"
        self.actor.init_gl()
        self.vr_system = openvr.init(openvr.VRApplication_Scene)
        self.vr_width, self.vr_height = self.vr_system.getRecommendedRenderTargetSize()
        self.compositor = openvr.VRCompositor()
        if self.compositor is None:
            raise Exception("Unable to create compositor") 
        poses_t = openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount
        self.poses = poses_t()
        # Set up framebuffer and render textures
        self.fb = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fb)
        self.depth_buffer = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth_buffer)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, self.vr_width, self.vr_height)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, self.depth_buffer)
        self.texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, self.vr_width, self.vr_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 0)  
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.texture_id, 0)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if status != GL_FRAMEBUFFER_COMPLETE:
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            raise Exception("Incomplete framebuffer")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)   
        # OpenVR texture data
        self.texture = openvr.Texture_t()
        self.texture.handle = self.texture_id
        self.texture.eType = openvr.API_OpenGL
        self.texture.eColorSpace = openvr.ColorSpace_Gamma 

    def render_scene(self):
        self.compositor.waitGetPoses(self.poses, openvr.k_unMaxTrackedDeviceCount, None, 0)
        hmd_pose0 = self.poses[openvr.k_unTrackedDeviceIndex_Hmd]
        if not hmd_pose0.bPoseIsValid:
            return
        # hmd_pose = hmd_pose0.mDeviceToAbsoluteTracking
        # TODO: use the pose to compute things
        # 1) On-screen render:
        modelview = None # TODO:
        projection = None # TODO:
        self.display_gl(modelview, projection)
        # 2) VR render
        # TODO: render different things to each eye
        glBindFramebuffer(GL_FRAMEBUFFER, self.fb)
        self.display_gl(modelview, projection)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        #
        # TODO: use different textures for each eye
        self.compositor.submit(openvr.Eye_Left, self.texture)
        self.compositor.submit(openvr.Eye_Right, self.texture)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        
    def display_gl(self, modelview, projection):
        self.actor.display_gl(modelview, projection)

    def dispose_gl(self):
        self.actor.dispose_gl()
        if self.vr_system is not None:
            openvr.shutdown()
            self.vr_system = None
        glDeleteTextures([self.texture_id])
        glDeleteRenderbuffers(1, [self.depth_buffer])
        glDeleteFramebuffers([self.fb])
        self.fb = 0


class BlueBackgroundActor(BasicGlResource):
    "Simplest possible renderer just paints the whole universe blue"

    def display_gl(self, modelview, projection):
        "render scene one time"
        glClearColor(0.5, 0.5, 1.0, 0.0)
        glClear(GL_COLOR_BUFFER_BIT)


class ColorCubeActor(BasicGlResource):
    """
    Draws a cube
    
       2________ 3
       /|      /|
     6/_|____7/ |
      | |_____|_| 
      | /0    | /1
      |/______|/
      4       5
    """
    
    def __init__(self):
        self.shader = 0
    
    def init_gl(self):
        vertex_shader = compileShader(dedent(
            """\
            #version 450 core
            #line 207
            
            // Adapted from @jherico's RiftDemo.py in pyovr
            
            layout(location = 0) uniform mat4 Projection = mat4(1);
            layout(location = 4) uniform mat4 ModelView = mat4(1);
            layout(location = 8) uniform float Size = 1.0;
            
            const vec3 UNIT_CUBE[8] = vec3[8](
              vec3(-1.0, -1.0, -1.0), // 0: lower left rear
              vec3(+1.0, -1.0, -1.0), // 1: lower right rear
              vec3(-1.0, +1.0, -1.0), // 2: upper left rear
              vec3(+1.0, +1.0, -1.0), // 3: upper right rear
              vec3(-1.0, -1.0, +1.0), // 4: lower left front
              vec3(+1.0, -1.0, +1.0), // 5: lower right front
              vec3(-1.0, +1.0, +1.0), // 6: upper left front
              vec3(+1.0, +1.0, +1.0)  // 7: upper right front
            );
            
            const vec3 UNIT_CUBE_NORMALS[6] = vec3[6](
              vec3(0.0, 0.0, -1.0),
              vec3(0.0, 0.0, 1.0),
              vec3(1.0, 0.0, 0.0),
              vec3(-1.0, 0.0, 0.0),
              vec3(0.0, 1.0, 0.0),
              vec3(0.0, -1.0, 0.0)
            );
            
            const int CUBE_INDICES[36] = int[36](
              0, 1, 2, 2, 1, 3, // front
              4, 6, 5, 6, 5, 7, // back
              0, 2, 4, 4, 2, 6, // left
              1, 3, 5, 5, 3, 7, // right
              2, 6, 3, 6, 3, 7, // top
              0, 1, 4, 4, 1, 5  // bottom
            );
            
            out vec3 _color;
            
            void main() {
              _color = vec3(1.0, 0.0, 0.0);
              int vertexIndex = CUBE_INDICES[gl_VertexID];
              int normalIndex = gl_VertexID / 6;
              
              _color = UNIT_CUBE_NORMALS[normalIndex];
              if (any(lessThan(_color, vec3(0.0)))) {
                  _color = vec3(1.0) + _color;
              }
            
              gl_Position = Projection * ModelView * vec4(UNIT_CUBE[vertexIndex] * Size, 1.0);
            }
            """), 
            GL_VERTEX_SHADER)
        fragment_shader = compileShader(dedent(
            """\
            #version 450 core
            #line 278
            
            in vec3 _color;
            out vec4 FragColor;
            
            void main() {
              FragColor = vec4(_color, 1.0);
            }
            """), 
            GL_FRAGMENT_SHADER)
        self.shader = compileProgram(vertex_shader, fragment_shader)
        #
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        
    def display_gl(self, modelview, projection):
        glClearColor(0.8, 0.5, 0.5, 0.0) # pink background
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        #
        glUseProgram(self.shader)
        glDrawArrays(GL_TRIANGLES, 0, 36)
    
    def dispose_gl(self):
        glDeleteProgram(self.shader)
        self.shader = 0
        glDeleteVertexArrays(1, (self.vao,))
        self.vao = 0


if __name__ == "__main__":
    # Show a blue OpenGL window
    actor0 = ColorCubeActor()
    renderer0 = OpenVrGlRenderer(actor0)
    with GlfwApp(renderer0, "glfw OpenVR color cube") as glfwApp:
        glfwApp.run_loop()