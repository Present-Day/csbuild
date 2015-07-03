#!/usr/bin/python

import os
import csbuild
import sys

from csbuild.toolchain_msvc import VisualStudioPackage

# Force the local copy of csbuild to be used rather than the installed copy.
sys.path.insert(0, "../../../")

csbuild.Toolchain("gcc", "ios").Compiler().SetCppStandard("c++11")
csbuild.Toolchain("gcc", "ios").SetCppStandardLibrary("libc++")

csbuild.Toolchain("msvc").SetMsvcVersion(VisualStudioPackage.Vs2012)

csbuild.DisablePrecompile()
csbuild.DisableChunkedBuild()

OUT_DIR = "out/{project.activeToolchainName}-{project.outputArchitecture}/{project.targetName}"
INT_DIR = "obj/{project.activeToolchainName}-{project.outputArchitecture}/{project.targetName}/{project.name}"

csbuild.SetOutputDirectory(OUT_DIR)
csbuild.SetIntermediateDirectory(INT_DIR)

csbuild.AddIncludeDirectories("src")
csbuild.AddLibraryDirectories(OUT_DIR)


@csbuild.project("sharedLibrary", "src/sharedLibrary")
def sharedLibrary():
	csbuild.SetOutput("sharedLibrary", csbuild.ProjectType.SharedLibrary)


@csbuild.project("staticLibrary", "src/staticLibrary")
def staticLibrary():
	csbuild.SetOutput("staticLibrary", csbuild.ProjectType.StaticLibrary)


@csbuild.project("loadableModule", "src/loadableModule")
def loadableModule():
	csbuild.SetOutput("loadableModule", csbuild.ProjectType.LoadableModule)


@csbuild.project("mainApp", "src/mainApp", ["sharedLibrary", "staticLibrary"])
def mainApp():
	csbuild.AddLibraries("sharedLibrary", "staticLibrary")
	csbuild.SetOutput("mainApp", csbuild.ProjectType.Application)
