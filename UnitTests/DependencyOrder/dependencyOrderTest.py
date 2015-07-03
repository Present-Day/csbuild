#!/usr/bin/python

import sys
sys.path.insert(0, "../../")

import csbuild
from csbuild import log

csbuild.Toolchain("gcc").SetCxxCommand("clang++")

@csbuild.project(
	name="myApp",
	workingDirectory="myApp",
	depends=[
		"myLib",
	],
)
def myApp():
	csbuild.AddLibraries("m", "c")
	csbuild.SetOutput("myApp", csbuild.ProjectType.Application)

	@csbuild.postPrepareBuildStep
	def ppbstep(project):
		expectedOrder =  [ "c", "myLib", "iberty", "myLib2", "m", "dl", "pthread", "bfd" ]
		if list(project.libraries) != expectedOrder:
			log.LOG_ERROR("{} != {}".format(list(project.libraries), expectedOrder))
			sys.exit(1)
		else:
			log.LOG_LINKER("Library order test successful.")
			sys.exit(0)

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
		csbuild.AddLibraries("m", "iberty", "bfd")

@csbuild.project(
	name="myLib2",
	workingDirectory="myLib2",
	depends=[],
)
def myLib():
	csbuild.SetOutput("myLib2", csbuild.ProjectType.StaticLibrary)

	@csbuild.scope(csbuild.ScopeDef.Final)
	def finalScope():
		csbuild.AddLibraries("m", "dl", "pthread", "bfd")
