import os
import sys
from setuptools import setup, Extension
from Cython.Build import cythonize

def find_python_files():
    py_files = []
    # Engine & API directories
    targets = ["api", "hl_bot", "meme_bot"]
    for target in targets:
        if os.path.exists(target):
            for root, dirs, files in os.walk(target):
                for file in files:
                    if file.endswith(".py") and file != "__init__.py":
                        py_files.append(os.path.join(root, file))
    
    # Root level files
    root_files = ["db.py", "config.py", "alerts.py", "main.py"]
    for file in root_files:
        if os.path.exists(file):
            py_files.append(file)
            
    return py_files

py_files = find_python_files()
print("=" * 60)
print(f"Found {len(py_files)} Python files for Cython compilation:")
for f in py_files:
    print(f"  - {f}")
print("=" * 60)

extensions = []
for py_file in py_files:
    norm_path = os.path.normpath(py_file)
    name = norm_path.replace(".py", "").replace(os.sep, ".")
    extensions.append(Extension(name, [norm_path]))

setup(
    name="hyperscalp-client-compiled",
    ext_modules=cythonize(
        extensions,
        compiler_directives={"language_level": "3", "always_allow_keywords": True},
        annotate=False
    )
)
