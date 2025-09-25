"""
3D Home Viewer using PyQt6 OpenGL for GLB file visualization.
"""

import sys
import math
import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLabel, QSlider, QPushButton, QGroupBox
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QWheelEvent, QKeyEvent

try:
    import trimesh
    TRIMESH_AVAILABLE = True
except ImportError:
    TRIMESH_AVAILABLE = False
    print("Warning: trimesh not available. Install with: pip install trimesh")

try:
    import pygltflib
    GLTF_AVAILABLE = True
except ImportError:
    GLTF_AVAILABLE = False
    print("Warning: pygltflib not available. Install with: pip install pygltflib")


class Home3DViewer(QOpenGLWidget):
    """3D viewer widget for home GLB file using OpenGL."""
    
    # Signals
    view_changed = pyqtSignal(float, float, float)  # camera position
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Camera parameters
        self.camera_distance = 3.0
        self.camera_angle_x = math.radians(90)  # 90 degrees
        self.camera_angle_y = math.radians(40)  # 40 degrees
        self.camera_target = [0, 0, 0]
        
        # Mouse interaction
        self.last_mouse_pos = None
        self.mouse_pressed = False
        self.user_interacting = False
        self.interaction_timer = QTimer()
        self.interaction_timer.timeout.connect(self.resume_auto_rotation)
        self.interaction_timer.setSingleShot(True)
        
        # 3D model data
        self.vertices = []
        self.normals = []
        self.indices = []
        self.model_loaded = False
        self.model_center = [0, 0, 0]
        self.model_scale = 1.0
        
        # OpenGL objects
        self.shader_program = None
        self.vao = None
        self.vbo_vertices = None
        self.vbo_normals = None
        self.ebo = None
        
        # Animation
        self.rotation_angle = 0.0
        self.auto_rotate = True  # Enable auto-rotation by default to preview whole model
        
        # Load the model
        self.load_home_model()
        
        # Setup timer for auto-rotation
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_rotation)
        if self.auto_rotate:
            self.timer.start(16)  # ~60 FPS
    
    def load_home_model(self):
        """Load the home.glb model."""
        try:
            if not TRIMESH_AVAILABLE:
                # Create a simple house model as fallback
                self.create_simple_house()
                return
            
            # Try to load GLB file
            import os
            # Look for home.glb in the project root directory
            current_dir = os.path.dirname(__file__)
            project_root = os.path.join(current_dir, "..", "..", "..")
            glb_path = os.path.join(project_root, "home.glb")
            glb_path = os.path.abspath(glb_path)
            
            if os.path.exists(glb_path):
                # Load with trimesh
                scene = trimesh.load(glb_path)
                
                if hasattr(scene, 'geometry'):
                    # Combine all meshes
                    all_vertices = []
                    all_normals = []
                    all_indices = []
                    index_offset = 0
                    
                    for name, mesh in scene.geometry.items():
                        if hasattr(mesh, 'vertices') and hasattr(mesh, 'faces'):
                            vertices = mesh.vertices
                            faces = mesh.faces
                            normals = mesh.vertex_normals if hasattr(mesh, 'vertex_normals') else None
                            
                            if normals is None:
                                # Calculate normals
                                normals = np.zeros_like(vertices)
                                for face in faces:
                                    v0, v1, v2 = vertices[face]
                                    normal = np.cross(v1 - v0, v2 - v0)
                                    normal = normal / np.linalg.norm(normal)
                                    normals[face[0]] += normal
                                    normals[face[1]] += normal
                                    normals[face[2]] += normal
                                
                                # Normalize normals
                                for i in range(len(normals)):
                                    norm = np.linalg.norm(normals[i])
                                    if norm > 0:
                                        normals[i] /= norm
                            
                            all_vertices.extend(vertices)
                            all_normals.extend(normals)
                            
                            # Adjust indices for combined mesh
                            adjusted_faces = faces + index_offset
                            all_indices.extend(adjusted_faces.flatten())
                            index_offset += len(vertices)
                    
                    if all_vertices:
                        self.vertices = np.array(all_vertices, dtype=np.float32)
                        self.normals = np.array(all_normals, dtype=np.float32)
                        self.indices = np.array(all_indices, dtype=np.uint32)
                        
                        # Calculate model center and scale
                        self.calculate_model_bounds()
                        self.model_loaded = True
                        print(f"Loaded home model: {len(self.vertices)} vertices, {len(self.indices)//3} faces")
                    else:
                        self.create_simple_house()
                else:
                    self.create_simple_house()
            else:
                print(f"GLB file not found at {glb_path}")
                self.create_simple_house()
                
        except Exception as e:
            print(f"Error loading home model: {e}")
            self.create_simple_house()
    
    def create_simple_house(self):
        """Create a simple house model as fallback."""
        # Simple house vertices (cube + roof)
        vertices = [
            # Base cube
            -2, -1, -2,  # 0
             2, -1, -2,  # 1
             2,  1, -2,  # 2
            -2,  1, -2,  # 3
            -2, -1,  2,  # 4
             2, -1,  2,  # 5
             2,  1,  2,  # 6
            -2,  1,  2,  # 7
            # Roof
             0,  2, -2,  # 8
             0,  2,  2,  # 9
        ]
        
        # Calculate normals for each face
        normals = []
        for i in range(0, len(vertices), 3):
            normals.extend([0, 1, 0])  # Simple upward normals
        
        # Indices for faces
        indices = [
            # Bottom
            0, 1, 2, 0, 2, 3,
            # Top
            4, 7, 6, 4, 6, 5,
            # Front
            0, 4, 5, 0, 5, 1,
            # Back
            2, 6, 7, 2, 7, 3,
            # Left
            0, 3, 7, 0, 7, 4,
            # Right
            1, 5, 6, 1, 6, 2,
            # Roof front
            3, 2, 8,
            # Roof back
            7, 9, 6,
            # Roof left
            3, 8, 9, 3, 9, 7,
            # Roof right
            2, 6, 9, 2, 9, 8,
        ]
        
        self.vertices = np.array(vertices, dtype=np.float32)
        self.normals = np.array(normals, dtype=np.float32)
        self.indices = np.array(indices, dtype=np.uint32)
        self.model_loaded = True
        self.calculate_model_bounds()
        print("Created simple house model")
    
    def calculate_model_bounds(self):
        """Calculate model center and scale."""
        if len(self.vertices) == 0:
            return
        
        min_coords = np.min(self.vertices.reshape(-1, 3), axis=0)
        max_coords = np.max(self.vertices.reshape(-1, 3), axis=0)
        
        self.model_center = (min_coords + max_coords) / 2
        size = max_coords - min_coords
        max_size = np.max(size)
        self.model_scale = 2.0 / max_size if max_size > 0 else 1.0
        
        # Scale and center the model
        self.vertices = (self.vertices.reshape(-1, 3) - self.model_center) * self.model_scale
        self.vertices = self.vertices.flatten()
    
    def initializeGL(self):
        """Initialize OpenGL."""
        from OpenGL import GL
        
        # Enable depth testing
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_CULL_FACE)
        GL.glCullFace(GL.GL_BACK)
        
        # Set clear color
        GL.glClearColor(0.1, 0.1, 0.2, 1.0)
        
        # Create shader program
        self.create_shader_program()
        
        # Create buffers
        self.create_buffers()
    
    def create_shader_program(self):
        """Create OpenGL shader program."""
        from OpenGL import GL
        
        vertex_shader_source = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        layout (location = 1) in vec3 aNormal;
        
        uniform mat4 model;
        uniform mat4 view;
        uniform mat4 projection;
        uniform vec3 lightPos;
        
        out vec3 FragPos;
        out vec3 Normal;
        out vec3 LightPos;
        
        void main()
        {
            FragPos = vec3(model * vec4(aPos, 1.0));
            Normal = mat3(transpose(inverse(model))) * aNormal;
            LightPos = vec3(view * vec4(lightPos, 1.0));
            
            gl_Position = projection * view * vec4(FragPos, 1.0);
        }
        """
        
        fragment_shader_source = """
        #version 330 core
        out vec4 FragColor;
        
        in vec3 FragPos;
        in vec3 Normal;
        in vec3 LightPos;
        
        uniform vec3 lightColor;
        uniform vec3 objectColor;
        
        void main()
        {
            // Ambient
            float ambientStrength = 0.3;
            vec3 ambient = ambientStrength * lightColor;
            
            // Diffuse
            vec3 norm = normalize(Normal);
            vec3 lightDir = normalize(LightPos - FragPos);
            float diff = max(dot(norm, lightDir), 0.0);
            vec3 diffuse = diff * lightColor;
            
            vec3 result = (ambient + diffuse) * objectColor;
            FragColor = vec4(result, 1.0);
        }
        """
        
        # Compile vertex shader
        vertex_shader = GL.glCreateShader(GL.GL_VERTEX_SHADER)
        GL.glShaderSource(vertex_shader, vertex_shader_source)
        GL.glCompileShader(vertex_shader)
        
        # Compile fragment shader
        fragment_shader = GL.glCreateShader(GL.GL_FRAGMENT_SHADER)
        GL.glShaderSource(fragment_shader, fragment_shader_source)
        GL.glCompileShader(fragment_shader)
        
        # Create program
        self.shader_program = GL.glCreateProgram()
        GL.glAttachShader(self.shader_program, vertex_shader)
        GL.glAttachShader(self.shader_program, fragment_shader)
        GL.glLinkProgram(self.shader_program)
        
        # Clean up shaders
        GL.glDeleteShader(vertex_shader)
        GL.glDeleteShader(fragment_shader)
    
    def create_buffers(self):
        """Create OpenGL buffers."""
        from OpenGL import GL
        
        if not self.model_loaded:
            return
        
        # Create VAO
        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        
        # Create VBO for vertices
        self.vbo_vertices = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo_vertices)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, self.vertices.nbytes, self.vertices, GL.GL_STATIC_DRAW)
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, GL.GL_FALSE, 0, None)
        GL.glEnableVertexAttribArray(0)
        
        # Create VBO for normals
        self.vbo_normals = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo_normals)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, self.normals.nbytes, self.normals, GL.GL_STATIC_DRAW)
        GL.glVertexAttribPointer(1, 3, GL.GL_FLOAT, GL.GL_FALSE, 0, None)
        GL.glEnableVertexAttribArray(1)
        
        # Create EBO for indices
        self.ebo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, self.indices.nbytes, self.indices, GL.GL_STATIC_DRAW)
        
        GL.glBindVertexArray(0)
    
    def paintGL(self):
        """Paint the 3D scene."""
        from OpenGL import GL
        import numpy as np
        
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        
        if not self.model_loaded or not self.shader_program:
            return
        
        GL.glUseProgram(self.shader_program)
        
        # Set up matrices
        model = np.eye(4, dtype=np.float32)
        model = self.rotate_matrix(model, self.rotation_angle, [0, 1, 0])
        
        view = self.get_view_matrix()
        projection = self.get_projection_matrix()
        
        # Set uniforms
        model_loc = GL.glGetUniformLocation(self.shader_program, "model")
        view_loc = GL.glGetUniformLocation(self.shader_program, "view")
        proj_loc = GL.glGetUniformLocation(self.shader_program, "projection")
        light_pos_loc = GL.glGetUniformLocation(self.shader_program, "lightPos")
        light_color_loc = GL.glGetUniformLocation(self.shader_program, "lightColor")
        object_color_loc = GL.glGetUniformLocation(self.shader_program, "objectColor")
        
        GL.glUniformMatrix4fv(model_loc, 1, GL.GL_FALSE, model)
        GL.glUniformMatrix4fv(view_loc, 1, GL.GL_FALSE, view)
        GL.glUniformMatrix4fv(proj_loc, 1, GL.GL_FALSE, projection)
        GL.glUniform3f(light_pos_loc, 5.0, 5.0, 5.0)
        GL.glUniform3f(light_color_loc, 1.0, 1.0, 1.0)
        GL.glUniform3f(object_color_loc, 0.7, 0.7, 0.9)
        
        # Draw the model
        GL.glBindVertexArray(self.vao)
        GL.glDrawElements(GL.GL_TRIANGLES, len(self.indices), GL.GL_UNSIGNED_INT, None)
        GL.glBindVertexArray(0)
    
    def get_view_matrix(self):
        """Get the view matrix."""
        import numpy as np
        
        # Calculate camera position
        x = self.camera_distance * math.cos(self.camera_angle_y) * math.cos(self.camera_angle_x)
        y = self.camera_distance * math.sin(self.camera_angle_y)
        z = self.camera_distance * math.cos(self.camera_angle_y) * math.sin(self.camera_angle_x)
        
        camera_pos = np.array([x, y, z])
        target = np.array(self.camera_target)
        up = np.array([0, 1, 0])
        
        # Calculate view matrix
        f = target - camera_pos
        f = f / np.linalg.norm(f)
        s = np.cross(f, up)
        s = s / np.linalg.norm(s)
        u = np.cross(s, f)
        
        view = np.array([
            [s[0], u[0], -f[0], 0],
            [s[1], u[1], -f[1], 0],
            [s[2], u[2], -f[2], 0],
            [-np.dot(s, camera_pos), -np.dot(u, camera_pos), np.dot(f, camera_pos), 1]
        ], dtype=np.float32)
        
        return view
    
    def get_projection_matrix(self):
        """Get the projection matrix."""
        import numpy as np
        
        fov = math.radians(45)
        aspect = self.width() / self.height() if self.height() > 0 else 1.0
        near = 0.1
        far = 100.0
        
        f = 1.0 / math.tan(fov / 2.0)
        
        projection = np.array([
            [f / aspect, 0, 0, 0],
            [0, f, 0, 0],
            [0, 0, (far + near) / (near - far), -1],
            [0, 0, (2 * far * near) / (near - far), 0]
        ], dtype=np.float32)
        
        return projection
    
    def rotate_matrix(self, matrix, angle, axis):
        """Rotate matrix around axis."""
        import numpy as np
        
        axis = np.array(axis)
        axis = axis / np.linalg.norm(axis)
        
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        
        rotation = np.array([
            [cos_a + axis[0]**2 * (1 - cos_a),
             axis[0] * axis[1] * (1 - cos_a) - axis[2] * sin_a,
             axis[0] * axis[2] * (1 - cos_a) + axis[1] * sin_a, 0],
            [axis[1] * axis[0] * (1 - cos_a) + axis[2] * sin_a,
             cos_a + axis[1]**2 * (1 - cos_a),
             axis[1] * axis[2] * (1 - cos_a) - axis[0] * sin_a, 0],
            [axis[2] * axis[0] * (1 - cos_a) - axis[1] * sin_a,
             axis[2] * axis[1] * (1 - cos_a) + axis[0] * sin_a,
             cos_a + axis[2]**2 * (1 - cos_a), 0],
            [0, 0, 0, 1]
        ])
        
        return matrix @ rotation
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = True
            self.last_mouse_pos = event.position()
            self.user_interacting = True
            self.interaction_timer.stop()  # Stop the resume timer
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events."""
        if self.mouse_pressed and self.last_mouse_pos:
            dx = event.position().x() - self.last_mouse_pos.x()
            dy = event.position().y() - self.last_mouse_pos.y()
            
            self.camera_angle_x += dx * 0.01
            self.camera_angle_y += dy * 0.01
            
            # Clamp vertical rotation
            self.camera_angle_y = max(-math.pi/2 + 0.1, min(math.pi/2 - 0.1, self.camera_angle_y))
            
            self.last_mouse_pos = event.position()
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = False
            # Resume auto-rotation after 2 seconds of no interaction
            self.interaction_timer.start(2000)
    
    def wheelEvent(self, event: QWheelEvent):
        """Handle wheel events for zooming."""
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        self.camera_distance *= zoom_factor
        self.camera_distance = max(1.0, min(50.0, self.camera_distance))
        self.user_interacting = True
        self.interaction_timer.stop()
        self.interaction_timer.start(2000)  # Resume auto-rotation after 2 seconds
        self.update()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_R:
            self.auto_rotate = not self.auto_rotate
            if self.auto_rotate:
                self.timer.start(16)
            else:
                self.timer.stop()
        elif event.key() == Qt.Key.Key_Reset:
            self.reset_view()
        elif event.key() == Qt.Key.Key_Plus:
            self.camera_distance *= 0.9
            self.update()
        elif event.key() == Qt.Key.Key_Minus:
            self.camera_distance *= 1.1
            self.update()
    
    def reset_view(self):
        """Reset camera to default position."""
        self.camera_distance = 3.0
        self.camera_angle_x = math.radians(90)  # 90 degrees
        self.camera_angle_y = math.radians(40)  # 40 degrees
        self.rotation_angle = 0.0
        self.update()
    
    def update_rotation(self):
        """Update rotation for auto-rotate."""
        if self.auto_rotate and not self.user_interacting:
            self.rotation_angle += 0.01
            self.update()
    
    def resume_auto_rotation(self):
        """Resume auto-rotation after user interaction ends."""
        self.user_interacting = False
    
    def resizeGL(self, width, height):
        """Handle resize events."""
        from OpenGL import GL
        GL.glViewport(0, 0, width, height)
