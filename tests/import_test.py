import sys
import os

# Add the project root to the python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

print(f"Python path: {sys.path}")
print(f"Current directory: {os.getcwd()}")
print("Attempting to import moderator_interface...")

try:
    from robotaste.views.moderator import moderator_interface
    print("Successfully imported moderator_interface")
except ImportError as e:
    print(f"Failed to import moderator_interface: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    import traceback
    traceback.print_exc()
