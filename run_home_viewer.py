#!/usr/bin/env python3
"""
Launcher script for ARAS Home Viewer application.
"""

import sys
import os

# Add the src directory to the Python path
src_path = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_path)

# Also add the ui directory for direct imports
ui_path = os.path.join(src_path, 'aras', 'ui')
sys.path.insert(0, ui_path)

try:
    from aras.ui.home_viewer_app import main
    
    if __name__ == "__main__":
        print("Starting ARAS Home Viewer...")
        print("Features:")
        print("  • 3D GLB model visualization")
        print("  • 2D floor plan view")
        print("  • Interactive controls")
        print("  • Synchronized views")
        print()
        
        main()
        
except ImportError as e:
    print(f"Error: Missing dependencies - {e}")
    print("\nPlease install required packages:")
    print("pip install PyQt6 PyOpenGL numpy")
    print("pip install trimesh pygltflib  # Optional for GLB support")
    sys.exit(1)
except Exception as e:
    print(f"Error starting application: {e}")
    sys.exit(1)
