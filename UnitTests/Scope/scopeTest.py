#!/usr/bin/python

import sys
sys.path.insert(0, "../../")

import csbuild

csbuild.Toolchain("gcc").CppCompiler("clang++")

@csbuild.project(
	name="myApp_toolchain",
	workingDirectory="myApp_toolchain",
	depends=[
		"myLib_toolchain",
	],
)
def myApp():
	csbuild.Toolchain("gcc", "msvc").Output("myApp_toolchain", csbuild.ProjectType.Application)

@csbuild.project(
	name="myLib_toolchain",
	workingDirectory="myLib_toolchain",
	depends=[
		"myLib2_toolchain",
	],
)
def myLib():
	csbuild.Toolchain("gcc", "msvc").Output("myLib_toolchain", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.Toolchain("gcc", "msvc").Define("WITH_HELLO")

@csbuild.project(
	name="myLib2_toolchain",
	workingDirectory="myLib2_toolchain",
	depends=[],
)
def myLib():
	csbuild.Toolchain("gcc", "msvc").Output("myLib2_toolchain", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Intermediate)
	def intermediateScope():
		csbuild.Toolchain("gcc", "msvc").Define("WITH_PRINT")

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.Toolchain("gcc", "msvc").Define("HAS_MYLIB2")


@csbuild.project(
	name="myApp",
	workingDirectory="myApp",
	depends=[
		"myLib",
	],
)
def myApp():
	csbuild.Output("myApp", csbuild.ProjectType.Application)

@csbuild.project(
	name="myLib",
	workingDirectory="myLib",
	depends=[
		"myLib2",
	],
)
def myLib():
	csbuild.Output("myLib", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.Define("WITH_HELLO")

@csbuild.project(
	name="myLib2",
	workingDirectory="myLib2",
	depends=[],
)
def myLib():
	csbuild.Output("myLib2", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Intermediate)
	def intermediateScope():
		csbuild.Define("WITH_PRINT")

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.Define("HAS_MYLIB2")
