#!/usr/bin/env python3
import subprocess
from pathlib import Path
from distutils.command.build import build
from distutils.dir_util import copy_tree

import setuptools
from setuptools import setup

this_dir = Path(__file__).parent

requirements = []
requirements_path = this_dir / "requirements.txt"
if requirements_path.is_file():
    with open(requirements_path, "r", encoding="utf-8") as requirements_file:
        requirements = requirements_file.read().splitlines()

module_name = "wyoming_snowboy"
module_dir = this_dir / module_name
data_dir = module_dir / "data"
data_files = list(data_dir.glob("*.umdl")) + [data_dir / "common.res"]

# -----------------------------------------------------------------------------


class SnowboyBuild(build):
    def run(self):
        cmd = ["make"]
        swig_dir = Path("swig", "Python3")

        def compile_snowboy():
            subprocess.check_call(cmd, cwd=str(swig_dir))

        self.execute(compile_snowboy, [], "Compiling snowboy...")

        # copy generated .so to build folder
        self.mkpath(str(self.build_lib))
        snowboy_build_lib = Path(self.build_lib, module_name)
        self.mkpath(str(snowboy_build_lib))
        target_file = Path(swig_dir, "_snowboydetect.so")
        target_py_file = Path(swig_dir, "snowboydetect.py")
        if not self.dry_run:
            self.copy_file(target_file, snowboy_build_lib)
            self.copy_file(target_py_file, snowboy_build_lib)

        build.run(self)


# -----------------------------------------------------------------------------

setup(
    name=module_name,
    version="1.0.0",
    description="Wyoming Server for Snowboy",
    url="http://github.com/rhasspy/wyoming-snowboy",
    author="Michael Hansen",
    author_email="mike@rhasspy.org",
    license="MIT",
    packages=setuptools.find_packages(),
    package_data={
        "wyoming_snowboy": [str(p.relative_to(module_dir)) for p in data_files]
    },
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Text Processing :: Linguistic",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="rhasspy wyoming snowboy wake word",
    cmdclass={"build": SnowboyBuild},
)
