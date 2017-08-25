#!/usr/bin/python

import sys

# Force the local copy of csbuild to be used rather than the installed copy.
sys.path.insert(0, "../../../")

import csbuild

csbuild.Toolchain( "gcc", "ios" ).Compiler().SetCppStandard( "c++11" )
csbuild.Toolchain( "gcc", "ios" ).SetCppStandardLibrary( "libc++" )

csbuild.DisablePrecompile()
csbuild.DisableChunkedBuild()

OUT_DIR = "out/{project.activeToolchainName}-{project.outputArchitecture}/{project.targetName}"
INT_DIR = "obj/{project.activeToolchainName}-{project.outputArchitecture}/{project.targetName}/{project.name}"

csbuild.SetOutputDirectory( OUT_DIR )
csbuild.SetIntermediateDirectory( INT_DIR )

csbuild.AddIncludeDirectories( "src" )
csbuild.AddLibraryDirectories( OUT_DIR )


@csbuild.project( "sharedLibrary", "src/sharedLibrary" )
def sharedLibrary():
	csbuild.SetOutput( "sharedLibrary", csbuild.ProjectType.SharedLibrary )


@csbuild.project( "staticLibrary", "src/staticLibrary" )
def staticLibrary():
	csbuild.SetOutput( "staticLibrary", csbuild.ProjectType.StaticLibrary )


@csbuild.project( "loadableModule", "src/loadableModule" )
def loadableModule():
	csbuild.SetOutput( "loadableModule", csbuild.ProjectType.LoadableModule )


@csbuild.project( "mainApp", "src/mainApp", ["sharedLibrary", "staticLibrary", "loadableModule"] )
def mainApp():
	csbuild.SetOutput( "mainApp", csbuild.ProjectType.Application )
