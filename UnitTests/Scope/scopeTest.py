#!/usr/bin/python

import sys
sys.path.insert(0, "../../")

import csbuild

csbuild.Toolchain("gcc").SetCxxCommand("clang++")

@csbuild.project(
	name="myApp_toolchain",
	workingDirectory="myApp_toolchain",
	depends=[
		"myLib_toolchain",
	],
)
def myApp():
	csbuild.Toolchain("gcc", "msvc").SetOutput("myApp_toolchain", csbuild.ProjectType.Application)

@csbuild.project(
	name="myLib_toolchain",
	workingDirectory="myLib_toolchain",
	depends=[
		"myLib2_toolchain",
	],
)
def myLib():
	csbuild.Toolchain("gcc", "msvc").SetOutput("myLib_toolchain", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.Toolchain("gcc", "msvc").AddDefines("WITH_HELLO")

@csbuild.project(
	name="myLib2_toolchain",
	workingDirectory="myLib2_toolchain",
	depends=[],
)
def myLib():
	csbuild.Toolchain("gcc", "msvc").SetOutput("myLib2_toolchain", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Intermediate)
	def intermediateScope():
		csbuild.Toolchain("gcc", "msvc").AddDefines("WITH_PRINT")

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.Toolchain("gcc", "msvc").AddDefines("HAS_MYLIB2")


@csbuild.project(
	name="myApp",
	workingDirectory="myApp",
	depends=[
		"myLib",
	],
)
def myApp():
	csbuild.SetOutput("myApp", csbuild.ProjectType.Application)

@csbuild.project(
	name="myLib",
	workingDirectory="myLib",
	depends=[
		"myLib2",
	],
)
def myLib():
	csbuild.SetOutput("myLib", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.AddDefines("WITH_HELLO")

@csbuild.project(
	name="myLib2",
	workingDirectory="myLib2",
	depends=[],
)
def myLib():
	csbuild.SetOutput("myLib2", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Intermediate)
	def intermediateScope():
		csbuild.AddDefines("WITH_PRINT")

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.AddDefines("HAS_MYLIB2")
