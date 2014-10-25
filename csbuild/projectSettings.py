# Copyright (C) 2013 Jaedyn K. Draper
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
**ProjectSettings module**

Defines the projectSettings class.

:var currentProject: The current project being built. Note that if this is accessed outside of an @project
block, the project returned will only be a temporary variable that will not be valid for compilation
:type currentProject: projectSettings

:var rootGroup: This is the top-level project group that all projects and project groups fall under.
It has no name and is NOT itself a valid or "real" group.
:type rootGroup: ProjectGroup

:var currentGroup: The current group that's being populated
:type currentGroup: ProjectGroup
"""

import csbuild

import fnmatch
import os
import re
import hashlib
import time
import sys
import math
import platform
import glob
import itertools
import threading
import types

from . import log
from . import _shared_globals
from . import _utils
from . import toolchain

class projectSettings( object ):
	"""
	Contains settings for the project

	:ivar name: The project's name
	:type name: str

	:ivar key: A unique key made by combining project name and target
	:type key: str

	:ivar workingDirectory: The directory containing all of the project's files
	:type workingDirectory: str

	:ivar linkDepends: The projects that this one depends on for linking
	:type linkDepends: list[str]

	:ivar srcDepends: The projects that this one depends on for compiling
	:type srcDepends: str

	:ivar func: The project's settings function - the function wrapped in the @project decorator
	:type func: function

	:ivar libraries: The libraries the project will link against
	:type libraries: list[str]

	:ivar staticLibraries: The libraries the project will forcibly statically link against
	:type staticLibraries: list[str]

	:ivar sharedLibraries: The libraries the project will forcibly statically link against
	:type sharedLibraries: list[str]

	:ivar includeDirs: Directories to search for included headers in
	:type includeDirs: list[str]

	:ivar libraryDirs: Directories to search for libraries in
	:type libraryDirs: list[str]

	:ivar optLevel: Optimization level for this project
	:type optLevel: csbuild.OptimizationLevel

	:ivar debugLevel: Debug level for this project
	:type debugLevel: csbuild.DebugLevel

	:ivar defines: #define declarations for this project
	:type defines: list[str]

	:ivar undefines: #undef declarations for this project
	:type undefines: list[str]

	:ivar cxx: C++ compiler executable for this project
	:type cxx: str

	:ivar cc: C compiler executable for this project
	:type cc: str

	:ivar hasCppFiles: Whether or not the project includes C++ files
	:type hasCppFiles: bool

	:ivar objDir: Output directory for intermediate object files
	:type objDir: str

	:ivar outputDir: Output directory for the final output file
	:type outputDir: str

	:ivar csbuildDir: Output directory for csbuild internal data, subdir of objDir
	:type csbuildDir: str

	:ivar outputName: Final filename to be generated for this project
	:type outputName: str

	:ivar headerInstallSubdir: Subdirectory that headers live in for this project
	:type headerInstallSubdir: str

	:ivar sources: Source files within this project that are being compiled during this run
	:type sources: list[str]

	:ivar allsources: All source files within this project
	:type allsources: list[str]

	:ivar allheaders: Headers within this project
	:type allheaders: list[str]

	:ivar type: Project type
	:type type: :class:`csbuild.ProjectType`

	:ivar ext: Extension override for output
	:type ext: str or None

	:ivar profile: Whether or not to optimize for profiling
	:type profile: bool

	:ivar cxxCompilerFlags: Literal flags to pass to the C++ compiler
	:type cxxCompilerFlags: list[str]

	:ivar ccCompilerFlags: Literal flags to pass to the C compiler
	:type ccCompilerFlags: list[str]

	:ivar linkerFlags: Literal flags to pass to the linker
	:type linkerFlags: list[str]

	:ivar excludeDirs: Directories excluded from source file discovery
	:type excludeDirs: list[str]

	:ivar excludeFiles: Files excluded from source file discovery
	:type excludeFiles: list[str]

	:ivar _outputDir_set: Whether or not the output directory has been set
	:type _outputDir_set: bool

	:ivar _objDir_set: Whether or not the object directory has been set
	:type _objDir_set: bool

	:ivar _debugLevel_set: Whether or not debug settings have been set
	:type _debugLevel_set: bool

	:ivar _optLevel_set: Whether or not optimization settings have been set
	:type _optLevel_set: bool

	:ivar allPaths: All the paths used to contain all headers included by this project
	:type allPaths: list[str]

	:ivar chunks: Compiled list of chunks to be compiled in this project
	:type chunks: list[str]

	:ivar chunksByFile: Dictionary to get the list of files in a chunk from its filename
	:type chunksByFile: dict[str, list[str]]

	:ivar useChunks: Whether or not to use chunks
	:type useChunks: bool

	:ivar chunkTolerance: minimum number of modified files needed to build a chunk as a chunk
	:type chunkTolerance: int

	:ivar chunkSize: number of files per chunk
	:type chunkSize: int

	:ivar chunkFilesize: maximum file size of a built chunk, in bytes
	:type chunkFilesize: int

	:ivar chunkSizeTolerance: minimum total filesize of modified files needed to build a chunk as a chunk
	:type chunkSizeTolerance: int

	:ivar headerRecursionDepth: Depth to recurse when building header information
	:type headerRecursionDepth: int

	:ivar ignoreExternalHeaders: Whether or not to ignore external headers when building header information
	:type ignoreExternalHeaders: bool

	:ivar defaultTarget: The target to be built when none is specified
	:type defaultTarget: str

	:ivar chunkedPrecompile: Whether or not to precompile all headers in the project
	:type chunkedPrecompile: bool

	:ivar precompile: List of files to precompile
	:type precompile: list[str]

	:ivar precompileExcludeFiles: List of files NOT to precompile
	:type precompileExcludeFiles: list[str]

	:ivar cppHeaderFile: The C++ precompiled header that's been built (if any)
	:type cppHeaderFile: str

	:ivar cHeaderFile: The C precompiled header that's been built (if any)
	:type cHeaderFile: str

	:ivar needsPrecompileCpp: Whether or not the C++ precompiled header needs to be rebuilt during this compile
	:type needsPrecompileCpp: bool

	:ivar needsPrecompileC: Whether or not the C++ precompiled header needs to be rebuilt during this compile
	:type needsPrecompileC: bool

	:ivar unity: Whether or not to build in full unity mode (all files included in one translation unit)
	:type unity: bool

	:ivar precompileDone: Whether or not the project's precompile step has been completed
	:type precompileDone: bool

	:ivar noWarnings: Whether or not to disable all warnings for this project
	:type noWarnings: bool

	:ivar toolchains: All toolchains enabled for this project
	:type toolchains: dict[str, csbuild.toolchain.toolchain]

	:ivar cxxCmd: Base C++ compile command, returned from toolchain.get_base_cxx_command
	:type cxxCmd: str

	:ivar ccCmd: Base C compile command, returned from toolchain.get_base_cc_command
	:type ccCmd: str

	:ivar cxxpccmd: Base C++ precompile command, returned from toolchain.get_base_cxx_precompile_command
	:type cxxpccmd: str

	:ivar ccpccmd: Base C precompile command, returned from toolchain.get_base_cc_precompile_command
	:type ccpccmd: str

	:ivar recompileAll: Whether or not conditions have caused the entire project to need recompilation
	:type recompileAll: bool

	:ivar targets: List of targets in this project with their associated settings functions, decorated with @target
	:type targets: dict[str, list[function]]

	:ivar targetName: The target name for this project as it's currently being built
	:type targetName: str

	:ivar _finalChunkSet: The list of chunks to be built after building all chunks, determining whether or not to build
		them as chunks, etc.
	:type _finalChunkSet: list[str]

	:ivar compilationCompleted: The number of files that have been compiled (successfully or not) at this point in the
		compile process. Note that this variable is modified in multiple threads and should be handled within project.mutex
	:type compilationCompleted: int

	:ivar compilationFailed: Whether or not ANY compilation unit has failed to successfully compile in this build
	:type compilationFailed: bool

	:ivar useStaticRuntime: Whether or not to link against a static runtime
	:type useStaticRuntime: bool

	:ivar cppHeaders: List of C++ headers
	:type cppHeaders: list[str]

	:ivar cHeaders: List of C headers
	:type cHeaders: list[str]

	:ivar activeToolchainName: The name of the currently active toolchain
	:type activeToolchainName: str

	:ivar activeToolchain: The actual currently active toolchain
	:type activeToolchain: csbuild.toolchain.toolchain

	:ivar warningsAsErrors: Whether all warnings should be treated as errors
	:type warningsAsErrors: bool

	:ivar _builtSomething: Whether or not ANY file has been compiled in this build
	:type _builtSomething: bool

	:ivar outputArchitecture: The architecture to build against
	:type outputArchitecture: csbuild.ArchitectureType

	:ivar libraryLocations: evaluated locations of the project's libraries
	:type libraryLocations: list[str]

	:ivar scriptPath: The location of the script file this project is defined in
	:type scriptPath: str

	:ivar mutex: A mutex used to control modification of project data across multiple threads
	:type mutex: threading.Lock

	:ivar preBuildStep: A function that will be executed before compile of this project begins
	:type preBuildStep: function

	:ivar postBuildStep: A function that will be executed after compile of this project ends
	:type postBuildStep: function

	:ivar parentGroup: The group this project is contained within
	:type parentGroup: ProjectGroup

	:ivar state: Current state of the project
	:type state: :_shared_globals.ProjectState:

	:ivar startTime: The time the project build started
	:type startTime: float

	:ivar endTime: The time the project build ended
	:type endTime: float

	:type extraFiles: list[str]
	:ivar extraFiles: Extra files being compiled, these will be rolled into project.sources, so use that instead

	:type extraDirs: list[str]
	:ivar extraDirs: Extra directories used to search for files

	:type extraObjs: set[str]
	:ivar extraObjs: Extra objects to pass to the linker

	.. note:: Toolchains can define additional variables that will show up on this class's
		instance variable list when that toolchain is active. See toolchain documentation for
		more details on what additional instance variables are available.

	"""

	class UserData(object):
		def __init__(self):
			self.dataDict = {}

		def copy(self):
			ret = projectSettings.UserData()
			ret.dataDict = dict(self.dataDict)
			return ret

		def __getattr__(self, item):
			return object.__getattribute__(self, "dataDict")[item]

	def __init__( self ):
		"""
		Default projectSettings constructor
		"""
		self._currentScope = csbuild.ScopeDef.Self

		self.name = ""
		"""
		:type: :class:`str`
		Project name
		"""

		self.priority = -1
		self.ignoreDependencyOrdering = False
		self.key = ""
		self.workingDirectory = "./"
		self.linkDepends = []
		self.linkDependsIntermediate = []
		self.linkDependsFinal = []
		self.reconciledLinkDepends = set()
		self.flattenedDepends = set()
		self.srcDepends = []
		self.srcDependsIntermediate = []
		self.srcDependsFinal = []
		self.func = None

		self.libraries = set()
		self.staticLibraries = set()
		self.sharedLibraries = set()
		self.frameworks = set()
		self.includeDirs = []
		self.libraryDirs = []
		self.frameworkDirs = set()

		self.optLevel = csbuild.OptimizationLevel.Disabled
		self.debugLevel = csbuild.DebugLevel.Disabled
		self.defines = []
		self.undefines = []
		self.cxx = ""
		self.cc = ""
		self.hasCppFiles = False

		self.objDir = "."
		self.outputDir = "."
		self.csbuildDir = ".csbuild"
		self.outputName = ""
		self.installOutput = False
		self.installHeaders = False
		self.headerInstallSubdir = ""

		self.sources = []
		self.allsources = []
		self.allheaders = []

		self.type = csbuild.ProjectType.Application
		self.ext = None
		self.profile = False

		self.cxxCompilerFlags = []
		self.ccCompilerFlags = []
		self.linkerFlags = []

		self.excludeDirs = []
		self.excludeFiles = []

		self._outputDir_set = False
		self._objDir_set = False
		self._debugLevel_set = False
		self._optLevel_set = False

		self.allPaths = []
		self.chunks = []
		self.forceChunks = []
		self.chunksByFile = {}

		self.useChunks = True
		self.chunkTolerance = 3
		self.chunkSize = 0
		self.chunkFilesize = 512000
		self.chunkSizeTolerance = 128000

		self.headerRecursionDepth = 0
		self.ignoreExternalHeaders = False

		self.defaultTarget = "release"

		self.chunkedPrecompile = False
		self.precompile = []
		self.precompileAsC = []
		self.precompileExcludeFiles = []
		self.cppHeaderFile = ""
		self.cHeaderFile = ""
		self.needsPrecompileCpp = False
		self.needsPrecompileC = False

		self.unity = False

		self.precompileDone = False
		self.precompileStarted = True

		self.noWarnings = False

		self.toolchains = { }
		self.intermediateToolchains = {}
		self.finalToolchains = {}

		self.cxxCmd = ""  # return value of get_base_cxx_command
		self.ccCmd = ""  # return value of get_base_cc_command
		self.cxxpccmd = ""  # return value of get_base_cxx_precompile_command
		self.ccpccmd = ""  # return value of get_base_cc_precompile_command

		self.recompileAll = False

		self.targets = {}
		self.archFuncs = {}

		self.targetName = ""

		self._finalChunkSet = []

		self.compilationCompleted = 0

		self.compilationFailed = False
		self.precompileFailed = False

		self.useStaticRuntime = False

		self.cHeaders = []
		self.cppHeaders = []

		self.activeToolchainName = None
		self.activeToolchain = None

		self.warningsAsErrors = False

		self._builtSomething = False

		self.outputArchitecture = ""

		self.libraryLocations = []

		self.scriptPath = ""
		self.scriptFile = ""

		self.mutex = threading.Lock( )

		self.postBuildStep = None
		self.preBuildStep = None
		self.prePrepareBuildStep = None
		self.postPrepareBuildStep = None
		self.preLinkStep = None
		self.preMakeStep = None
		self.postMakeStep = None

		self.parentGroup = currentGroup

		self.extraFiles = []
		self.extraDirs = []
		self.extraObjs = set()

		self.cExtensions = {".c"}
		self.cppExtensions = {".cpp", ".cxx", ".cc", ".cp", ".c++"}
		self.asmExtensions = {".s", ".asm"}
		self.cHeaderExtensions = set()
		self.cppHeaderExtensions = {".hpp", ".hxx", ".hh", ".hp", ".h++"}
		self.ambiguousHeaderExtensions = {".h", ".inl"}

		#TODO: Add proper Objective-C/C++ support for all platforms.
		if platform.system() == "Darwin":
			self.cExtensions.add(".m")
			self.cppExtensions.add(".mm")

		self.chunkMutexes = {}
		self.chunkExcludes = set()

		self.fileOverrides = {}
		self.fileOverrideSettings = {}
		self.ccOverrideCmds = {}
		self.cxxOverrideCmds = {}
		self.ccpcOverrideCmds = {}
		self.cxxpcOverrideCmds = {}

		self.supportedArchitectures = set()
		self.supportedToolchains = set()

		self.linkMode = csbuild.StaticLinkMode.LinkLibs
		self.linkModeSet = False

		self.splitChunks = {}

		self.userData = projectSettings.UserData()

		self._intermediateScopeSettings = {}
		self._finalScopeSettings = {}

		#GUI support
		self.state = _shared_globals.ProjectState.PENDING
		self.startTime = 0
		self.buildEnd = 0
		self.linkQueueStart = 0
		self.linkStart = 0
		self.endTime = 0
		self.compileOutput = {}
		self.compileErrors = {}
		self.parsedErrors = {}
		self.fileStatus = {}
		self.fileStart = {}
		self.fileEnd = {}
		self.cPchContents = []
		self.cppPchContents = []
		self.updated = False
		self.warnings = 0
		self.errors = 0
		self.warningsByFile = {}
		self.errorsByFile = {}
		self.times = {}
		self.summedTimes = {}
		self.linkCommand = ""
		self.compileCommands = {}

		self.linkOutput = ""
		self.linkErrors = ""
		self.parsedLinkErrors = None

	def prepareBuild( self ):
		wd = os.getcwd( )
		os.chdir( self.workingDirectory )

		self.activeToolchain.SetActiveTool("linker")

		log.LOG_BUILD( "Preparing tasks for {} ({} {}/{})...".format( self.outputName, self.targetName, self.outputArchitecture, self.activeToolchainName ) )

		global currentProject
		currentProject = self

		self.activeToolchain.prePrepareBuildStep(self)
		if self.prePrepareBuildStep:
			log.LOG_BUILD( "Running pre-PrepareBuild step for {} ({} {}/{})".format( self.outputName, self.targetName, self.outputArchitecture, self.activeToolchainName ) )
			self.prePrepareBuildStep(self)

		self.outputDir = os.path.abspath( self.outputDir ).format(project=self)

		# Create the executable/library output directory if it doesn't exist.
		if not os.access(self.outputDir, os.F_OK):
			os.makedirs(self.outputDir)

		alteredLibraryDirs = []
		for directory in self.libraryDirs:
			directory = directory.format(project=self)
			if not os.access(directory, os.F_OK):
				log.LOG_WARN("Library path {} does not exist!".format(directory))
			alteredLibraryDirs.append(directory)
		self.libraryDirs = alteredLibraryDirs

		#Kind of hacky. The libraries returned here are a temporary object that's been created by combining
		#base, toolchain, and architecture information. We need to bind it to something more permanent so we
		#can actually modify it. Assigning it to itself makes that temporary list permanent.
		self.libraries = self.libraries

		for dep in self.reconciledLinkDepends:
			proj = _shared_globals.projects[dep]
			proj.activeToolchain.SetActiveTool("linker")
			if proj.type == csbuild.ProjectType.StaticLibrary and self.linkMode == csbuild.StaticLinkMode.LinkIntermediateObjects:
				continue
			self.libraries.add(proj.outputName.split(".")[0])
			dir = proj.outputDir.format(project=proj)
			if dir not in self.libraryDirs:
				self.libraryDirs.append(dir)

		self.activeToolchain.SetActiveTool("compiler")
		self.objDir = os.path.abspath( self.objDir ).format(project=self)
		self.csbuildDir = os.path.join( self.objDir, ".csbuild" )

		alteredIncludeDirs = []
		for directory in self.includeDirs:
			directory = directory.format(project=self)
			if not os.access(directory, os.F_OK):
				log.LOG_WARN("Include path {} does not exist!".format(directory))
			alteredIncludeDirs.append(directory)
		self.includeDirs = alteredIncludeDirs

		def apply_macro(l):
			alteredList = []
			for s in l:
				s = os.path.abspath(s.format(project=self))
				alteredList.append(s)
			return alteredList

		self.excludeDirs = apply_macro(self.excludeDirs)

		self.extraFiles = apply_macro(self.extraFiles)
		self.extraDirs = apply_macro(self.extraDirs)
		self.extraObjs = set(apply_macro(list(self.extraObjs)))
		self.excludeFiles = apply_macro(self.excludeFiles)
		self.precompile = apply_macro(self.precompile)
		self.precompileAsC = apply_macro(self.precompileAsC)
		self.precompileExcludeFiles = apply_macro(self.precompileExcludeFiles)

		self.headerInstallSubdir = self.headerInstallSubdir.format(project=self)

		self.excludeDirs.append( self.csbuildDir )

		self.activeToolchain.SetActiveTool("linker")
		if self.ext is None:
			self.ext = self.activeToolchain.Linker().GetDefaultOutputExtension( self.type )

		self.outputName += self.ext
		self.activeToolchain.SetActiveTool("compiler")

		if not os.access(self.csbuildDir , os.F_OK):
			os.makedirs( self.csbuildDir )

		# Walk the source directory and construct the paths to each possible intermediate object file.
		# Make sure the paths exist, and if they don't, create them.
		for root, _, _ in os.walk(self.workingDirectory):
			# Exclude the intermediate and output paths in case they're in the working directory.
			if ".csbuild" in root or self.outputDir in root or self.objDir in root:
				continue
			tempFilename = os.path.join(root, "not_a_real.file")
			objFilePath = os.path.dirname(_utils.GetSourceObjPath(self, tempFilename))
			if not os.access(objFilePath, os.F_OK):
				os.makedirs(objFilePath)

		for item in self.fileOverrideSettings.items():
			item[1].activeToolchain = item[1].toolchains[self.activeToolchainName]
			self.ccOverrideCmds[item[0]] = self.activeToolchain.Compiler().GetBaseCcCommand( item[1] )
			self.cxxOverrideCmds[item[0]] = self.activeToolchain.Compiler().GetBaseCxxCommand( item[1] )
			self.ccpcOverrideCmds[item[0]] = self.activeToolchain.Compiler().GetBaseCcPrecompileCommand( item[1] )
			self.cxxpcOverrideCmds[item[0]] = self.activeToolchain.Compiler().GetBaseCxxPrecompileCommand( item[1] )

		self.ccCmd = self.activeToolchain.Compiler().GetBaseCcCommand( self )
		self.cxxCmd = self.activeToolchain.Compiler().GetBaseCxxCommand( self )
		self.ccpccmd = self.activeToolchain.Compiler().GetBaseCcPrecompileCommand( self )
		self.cxxpccmd = self.activeToolchain.Compiler().GetBaseCxxPrecompileCommand( self )

		cmdfile = os.path.join( self.csbuildDir, "{}.csbuild".format( self.targetName ) )
		cmd = ""
		if os.access(cmdfile , os.F_OK):
			with open( cmdfile, "r" ) as f:
				cmd = f.read( )

		if self.cxxCmd + self.ccCmd != cmd or _shared_globals.rebuild:
			self.recompileAll = True
			with open( cmdfile, "w" ) as f:
				f.write( self.cxxCmd + self.ccCmd )


		self.RediscoverFiles()

		if self.name not in self.parentGroup.projects:
			self.parentGroup.projects[self.name] = {}

		if self.activeToolchainName not in self.parentGroup.projects[self.name]:
			self.parentGroup.projects[self.name][self.activeToolchainName] = {}

		if self.targetName not in self.parentGroup.projects[self.name][self.activeToolchainName]:
			self.parentGroup.projects[self.name][self.activeToolchainName][self.targetName] = {}

		self.parentGroup.projects[self.name][self.activeToolchainName][self.targetName][self.outputArchitecture] = self

		self.activeToolchain.postPrepareBuildStep(self)
		if self.postPrepareBuildStep:
			log.LOG_BUILD( "Running post-PrepareBuild step for {} ({} {}/{})".format( self.outputName, self.targetName, self.outputArchitecture, self.activeToolchainName ) )
			self.postPrepareBuildStep(self)

		os.chdir( wd )

	def RediscoverFiles(self):
		"""
		Force a re-run of the file discovery process. Useful if a postPrepareBuild step adds additional files to the project.
		This will have no effect when called from any place other than a postPrepareBuild step.
		"""
		self.sources = []
		if not self.forceChunks:
			self.allsources = []
			self.allheaders = []
			self.cppHeaders = []
			self.cHeaders = []

			self.get_files( self.allsources, self.cppHeaders, self.cHeaders )
			if self.extraFiles:
				log.LOG_INFO("Appending extra files {}".format(self.extraFiles))
				self.allsources += self.extraFiles
			self.allheaders = self.cppHeaders + self.cHeaders

			if not self.allsources:
				return

			#We'll do this even if _use_chunks is false, because it simplifies the linker logic.
			self.chunks = self.make_chunks( self.allsources )
		else:
			self.allsources = list( itertools.chain( *self.forceChunks ) )

		if not _shared_globals.CleanBuild and not _shared_globals.do_install and csbuild.GetOption(
				"generate_solution" ) is None:
			for source in self.allsources:
				if self.should_recompile( source ):
					self.sources.append( source )
		else:
			self.sources = list( self.allsources )

		_shared_globals.allfiles |= set(self.sources)

	def SetValue(self, key, value):
		scope = self._currentScope
		if scope & csbuild.ScopeDef.Self:
			setattr(self, key, value)
		if scope & csbuild.ScopeDef.Intermediate:
			self._intermediateScopeSettings[key] = value
		if scope & csbuild.ScopeDef.Final:
			self._finalScopeSettings[key] = value

	def ExtendList(self, key, value):
		scope = self._currentScope
		if scope & csbuild.ScopeDef.Self:
			setattr(self, key, getattr(self, key) + value)
		if scope & csbuild.ScopeDef.Intermediate:
			if key not in self._intermediateScopeSettings:
				self._intermediateScopeSettings[key] = []
			self._intermediateScopeSettings[key] += value
		if scope & csbuild.ScopeDef.Final:
			if key not in self._finalScopeSettings:
				self._finalScopeSettings[key] = []
			self._finalScopeSettings[key] += value

	def AppendList(self, key, value):
		scope = self._currentScope
		if scope & csbuild.ScopeDef.Self:
			getattr(self, key).append(value)
		if scope & csbuild.ScopeDef.Intermediate:
			if key not in self._intermediateScopeSettings:
				self._intermediateScopeSettings[key] = []
			self._intermediateScopeSettings[key].append(value)
		if scope & csbuild.ScopeDef.Final:
			if key not in self._finalScopeSettings:
				self._finalScopeSettings[key] = []
			self._finalScopeSettings[key].append(value)

	def UpdateDict(self, key, value):
		scope = self._currentScope
		if scope & csbuild.ScopeDef.Self:
			getattr(self, key).update(value)
		if scope & csbuild.ScopeDef.Intermediate:
			if key not in self._intermediateScopeSettings:
				self._intermediateScopeSettings[key] = {}
			self._intermediateScopeSettings[key].update(value)
		if scope & csbuild.ScopeDef.Final:
			if key not in self._finalScopeSettings:
				self._finalScopeSettings[key] = {}
			self._finalScopeSettings[key].update(value)

	def UnionSet(self, key, value):
		scope = self._currentScope
		if scope & csbuild.ScopeDef.Self:
			setattr(self, key, getattr(self, key) | value)
		if scope & csbuild.ScopeDef.Intermediate:
			if key not in self._intermediateScopeSettings:
				self._intermediateScopeSettings[key] = set()
			self._intermediateScopeSettings[key] |= value
		if scope & csbuild.ScopeDef.Final:
			if key not in self._finalScopeSettings:
				self._finalScopeSettings[key] = set()
			self._finalScopeSettings[key] |= value

	def AddToSet(self, key, value):
		scope = self._currentScope
		if scope & csbuild.ScopeDef.Self:
			getattr(self, key).add(value)
		if scope & csbuild.ScopeDef.Intermediate:
			if key not in self._intermediateScopeSettings:
				self._intermediateScopeSettings[key] = set()
			self._intermediateScopeSettings[key].add(value)
		if scope & csbuild.ScopeDef.Final:
			if key not in self._finalScopeSettings:
				self._finalScopeSettings[key] = set()
			self._finalScopeSettings[key].add(value)


	def GetAttr(self, name):
		return object.__getattribute__(self, name)


	def SetAttr(self, name, value):
		object.__setattr__(self, name, value)


	def __getattribute__(self, item):
		return object.__getattribute__(self, "GetAttr")(item)


	def __setattr__(self, key, value):
		object.__getattribute__(self, "SetAttr")(key, value)


	def GetAttrNext(self, name):
		settings = object.__getattribute__(self, "_finalizedSettings")
		if name == "_finalizedSettings":
			return settings

		tool = object.__getattribute__(self, "activeToolchain").activeToolName

		try:
			return settings[tool][name]
		except:
			return object.__getattribute__(self, name)

	def SetAttrNext(self, name, value):
		if name == "state":
			with self.mutex:
				self.updated = True

		settings = object.__getattribute__(self, "_finalizedSettings")
		toolchain = object.__getattribute__(self, "activeToolchain")

		wasSet = False
		for tool in toolchain.tools:
			if name in settings[tool]:
				settings[tool][name] = value
				wasSet = True

		if not wasSet:
			object.__setattr__(self, name, value)

	@staticmethod
	def _combineObjects(baseObj, newObj):
		if newObj is None:
			return

		if isinstance( newObj, dict ):
			baseObj["obj"].update( newObj )
		elif isinstance( newObj, list ):
			baseObj["obj"] += newObj
		elif isinstance( newObj, set ):
			baseObj["obj"] |= newObj
		elif isinstance( newObj, csbuild.projectSettings.projectSettings.UserData ):
			baseObj["obj"].dataDict.update( newObj.dataDict )
		else:
			baseObj["obj"] = newObj


	@staticmethod
	def _processToolchain(baseObj, toolchain, name):
		if toolchain:
			if toolchain.activeTool and name in toolchain.activeTool._settingsOverrides:
				obj = toolchain.activeTool._settingsOverrides[name]
				projectSettings._combineObjects(baseObj, obj)


	def finalizeSettings(self):
		"""
		Finalize the settings by applying the settings from the selected toolchain and architecture
		:return: None
		"""

		self._finalizedSettings = {}
		self.activeToolchain = self.toolchains[self.activeToolchainName]

		for tool in self.activeToolchain.tools:
			self._finalizedSettings[tool] = {}
			self.activeToolchain.SetActiveTool(tool)
			for name in self.__dict__:
				if name == "_finalizedSettings":
					continue

				base = { "obj" : object.__getattribute__(self, name) }

				projectSettings._processToolchain(base, self.activeToolchain, name)

				self._finalizedSettings[tool][name] = base["obj"]
		self.activeToolchain.SetActiveTool("linker")
		if sys.version_info >= (3,0):
			self.GetAttr = types.MethodType(projectSettings.GetAttrNext, self)
			self.SetAttr = types.MethodType(projectSettings.SetAttrNext, self)
		else:
			self.GetAttr = types.MethodType(projectSettings.GetAttrNext, self, projectSettings)
			self.SetAttr = types.MethodType(projectSettings.SetAttrNext, self, projectSettings)


	def finalizeSettings2(self):
		"""
		Extra-finalize the settings by pulling in settings from the project dependency tree
		:return: None
		"""

		for tool in self.activeToolchain.tools:
			self.activeToolchain.SetActiveTool(tool)
			for name in self.__dict__:
				if name not in self._finalizedSettings[tool]:
					continue

				base = { "obj" : self._finalizedSettings[tool][name] }

				for depend in object.__getattribute__(self, "flattenedDepends"):
					dependProj = _shared_globals.projects[depend]
					if self.type == csbuild.ProjectType.Application:
						settings = object.__getattribute__(dependProj, "_finalScopeSettings")
						if name in settings:
							obj = settings[name]
							projectSettings._combineObjects(base, obj)
						toolchain = object.__getattribute__(dependProj, "finalToolchains")[object.__getattribute__(self, "activeToolchainName")]
						toolchain.SetActiveTool(tool)
						projectSettings._processToolchain(base, toolchain, name)
					else:
						settings = object.__getattribute__(dependProj, "_intermediateScopeSettings")
						if name in settings:
							obj = settings[name]
							projectSettings._combineObjects(base, obj)
						toolchain = object.__getattribute__(dependProj, "intermediateToolchains")[object.__getattribute__(self, "activeToolchainName")]
						toolchain.SetActiveTool(tool)
						projectSettings._processToolchain(base, toolchain, name)

				self._finalizedSettings[tool][name] = base["obj"]


	def copy( self ):
		ret = projectSettings( )
		toolchains = { }
		intermediateToolchains = {}
		finalToolchains = {}
		for kvp in self.toolchains.items( ):
			toolchains[kvp[0]] = kvp[1].copy( )
		for kvp in self.intermediateToolchains.items( ):
			intermediateToolchains[kvp[0]] = kvp[1].copy( )
		for kvp in self.finalToolchains.items( ):
			finalToolchains[kvp[0]] = kvp[1].copy( )

		ret.__dict__ = {
			"name": self.name,
			"priority" : self.priority,
			"ignoreDependencyOrdering" : self.ignoreDependencyOrdering,
			"key": self.key,
			"workingDirectory": self.workingDirectory,
			"linkDepends": list( self.linkDepends ),
			"linkDependsIntermediate": list( self.linkDependsIntermediate ),
			"linkDependsFinal": list( self.linkDependsFinal ),
			"reconciledLinkDepends" : set( self.reconciledLinkDepends ),
			"flattenedDepends" : set(self.flattenedDepends),
			"srcDepends": list( self.srcDepends ),
			"srcDependsIntermediate": list( self.srcDependsIntermediate ),
			"srcDependsFinal": list( self.srcDependsFinal ),
			"func": self.func,
			"libraries": set( self.libraries ),
			"staticLibraries": set( self.staticLibraries ),
			"sharedLibraries": set( self.sharedLibraries ),
			"frameworks": set( self.frameworks ),
			"includeDirs": list( self.includeDirs ),
			"libraryDirs": list( self.libraryDirs ),
			"frameworkDirs": set( self.frameworkDirs ),
			"optLevel": self.optLevel,
			"debugLevel": self.debugLevel,
			"defines": list( self.defines ),
			"undefines": list( self.undefines ),
			"cxx": self.cxx,
			"cc": self.cc,
			"hasCppFiles": self.hasCppFiles,
			"objDir": self.objDir,
			"outputDir": self.outputDir,
			"csbuildDir": self.csbuildDir,
			"outputName": self.outputName,
			"installOutput": self.installOutput,
			"installHeaders": self.installHeaders,
			"headerInstallSubdir": self.headerInstallSubdir,
			"sources": list( self.sources ),
			"allsources": list( self.allsources ),
			"allheaders": list( self.allheaders ),
			"type": self.type,
			"ext": self.ext,
			"profile": self.profile,
			"cxxCompilerFlags": list( self.cxxCompilerFlags ),
			"ccCompilerFlags": list( self.ccCompilerFlags ),
			"linkerFlags": list( self.linkerFlags ),
			"excludeDirs": list( self.excludeDirs ),
			"excludeFiles": list( self.excludeFiles ),
			"_outputDir_set": self._outputDir_set,
			"_objDir_set": self._objDir_set,
			"_debugLevel_set": self._debugLevel_set,
			"_optLevel_set": self._optLevel_set,
			"allPaths": list( self.allPaths ),
			"chunks": list( self.chunks ),
			"forceChunks": list( self.forceChunks ),
			"chunksByFile" : dict( self.chunksByFile ),
			"useChunks": self.useChunks,
			"chunkTolerance": self.chunkTolerance,
			"chunkSize": self.chunkSize,
			"chunkFilesize": self.chunkFilesize,
			"chunkSizeTolerance": self.chunkSizeTolerance,
			"headerRecursionDepth": self.headerRecursionDepth,
			"ignoreExternalHeaders": self.ignoreExternalHeaders,
			"defaultTarget": self.defaultTarget,
			"chunkedPrecompile": self.chunkedPrecompile,
			"precompile": list( self.precompile ),
			"precompileAsC": list( self.precompileAsC ),
			"precompileExcludeFiles": list( self.precompileExcludeFiles ),
			"cppHeaderFile": self.cppHeaderFile,
			"cHeaderFile": self.cHeaderFile,
			"unity": self.unity,
			"precompileDone": self.precompileDone,
			"precompileStarted": self.precompileStarted,
			"noWarnings": self.noWarnings,
			"toolchains": toolchains,
			"intermediateToolchains": intermediateToolchains,
			"finalToolchains": finalToolchains,
			"cxxCmd": self.cxxCmd,
			"ccCmd": self.ccCmd,
			"recompileAll": self.recompileAll,
			"targets": {},
			"archFuncs" : {},
			"fileOverrides" : {},
			"fileOverrideSettings" : {},
			"ccOverrideCmds" : dict(self.ccOverrideCmds),
			"cxxOverrideCmds" : dict(self.cxxOverrideCmds),
			"ccpcOverrideCmds" : dict(self.ccpcOverrideCmds),
			"cxxpcOverrideCmds" : dict(self.cxxpcOverrideCmds),
			"targetName": self.targetName,
			"_finalChunkSet": list( self._finalChunkSet ),
			"needsPrecompileC": self.needsPrecompileC,
			"needsPrecompileCpp": self.needsPrecompileCpp,
			"compilationCompleted": self.compilationCompleted,
			"compilationFailed": self.compilationFailed,
			"precompileFailed": self.precompileFailed,
			"useStaticRuntime": self.useStaticRuntime,
			"cHeaders": list( self.cHeaders ),
			"cppHeaders": list( self.cppHeaders ),
			"activeToolchainName": self.activeToolchainName,
			"activeToolchain": None,
			"warningsAsErrors": self.warningsAsErrors,
			"_builtSomething": self._builtSomething,
			"outputArchitecture": self.outputArchitecture,
			"libraryLocations": list( self.libraryLocations ),
			"scriptPath": self.scriptPath,
			"scriptFile": self.scriptFile,
			"mutex": threading.Lock( ),
			"preBuildStep" : self.preBuildStep,
			"postBuildStep" : self.postBuildStep,
			"prePrepareBuildStep" : self.prePrepareBuildStep,
			"postPrepareBuildStep" : self.postPrepareBuildStep,
			"preLinkStep" : self.preLinkStep,
			"preMakeStep" : self.preMakeStep,
			"postMakeStep" : self.postMakeStep,
			"parentGroup" : self.parentGroup,
			"extraFiles": list(self.extraFiles),
			"extraDirs": list(self.extraDirs),
			"extraObjs": set(self.extraObjs),
			"linkMode" : self.linkMode,
			"linkModeSet" : self.linkModeSet,
			"splitChunks" : dict(self.splitChunks),
			"_currentScope" : self._currentScope,
			"_intermediateScopeSettings" : {},
			"_finalScopeSettings" : {},
			"state" : self.state,
			"startTime" : self.startTime,
			"buildEnd" : self.buildEnd,
			"linkQueueStart" : self.linkQueueStart,
			"linkStart" : self.linkStart,
			"endTime" : self.endTime,
			"compileOutput" : dict(self.compileOutput),
			"compileErrors" : dict(self.compileErrors),
			"parsedErrors" : dict(self.parsedErrors),
			"fileStatus" : dict(self.fileStatus),
			"fileStart" : dict(self.fileStart),
			"fileEnd" : dict(self.fileEnd),
			"cPchContents" : list(self.cPchContents),
			"cppPchContents" : list(self.cppPchContents),
			"updated" : self.updated,
			"warnings" : self.warnings,
			"errors" : self.errors,
			"warningsByFile" : self.warningsByFile,
			"errorsByFile" : self.errorsByFile,
			"linkOutput" : self.linkOutput,
			"linkErrors" : self.linkErrors,
			"parsedLinkErrors" : self.parsedLinkErrors,
			"cExtensions" : set(self.cExtensions),
			"cppExtensions" : set(self.cppExtensions),
			"asmExtensions" : set(self.asmExtensions),
			"cHeaderExtensions" : set(self.cHeaderExtensions),
			"cppHeaderExtensions" : set(self.cppHeaderExtensions),
			"ambiguousHeaderExtensions" : set(self.ambiguousHeaderExtensions),
			"chunkMutexes" : {},
			"chunkExcludes" : set(self.chunkExcludes),
			"times" : self.times,
			"summedTimes" : self.summedTimes,
			"supportedArchitectures" : set(self.supportedArchitectures),
			"supportedToolchains" : set(self.supportedToolchains),
			"linkCommand" : self.linkCommand,
			"compileCommands" : dict(self.compileCommands),
			"userData" : self.userData.copy(),
		}

		for name in self.targets:
			ret.targets.update( { name : list( self.targets[name] ) } )

		for arch in self.archFuncs:
			ret.archFuncs.update( { arch : list( self.archFuncs[arch] ) } )

		for srcFile in self.chunkMutexes:
			ret.chunkMutexes.update( { srcFile : set( self.chunkMutexes[srcFile] ) } )

		for file in self.fileOverrides:
			ret.fileOverrides.update( { file : list( self.fileOverrides[file] ) } )

		for file in self.fileOverrideSettings:
			ret.fileOverrideSettings.update( { file : self.fileOverrideSettings[file].copy() } )

		for key in self._intermediateScopeSettings:
			val = self._intermediateScopeSettings[key]
			if isinstance(val, list):
				ret._intermediateScopeSettings[key] = list(val)
			elif isinstance(val, set):
				ret._intermediateScopeSettings[key] = set(val)
			elif isinstance(val, dict):
				ret._intermediateScopeSettings[key] = dict(val)
			else:
				ret._intermediateScopeSettings[key] = val

		for key in self._finalScopeSettings:
			val = self._finalScopeSettings[key]
			if isinstance(val, list):
				ret._finalScopeSettings[key] = list(val)
			elif isinstance(val, set):
				ret._finalScopeSettings[key] = set(val)
			elif isinstance(val, dict):
				ret._finalScopeSettings[key] = dict(val)
			else:
				ret._finalScopeSettings[key] = val

		return ret


	def get_files( self, sources = None, headers = None, cHeaders = None ):
		"""
		Steps through the current directory tree and finds all of the source and header files, and returns them as a list.
		Accepts two lists as arguments, which it populates. If sources or headers are excluded from the parameters, it will
		ignore files of the relevant types.
		"""

		excludeFiles = set( )
		excludeDirs = set( )
		ambiguousHeaders = set()

		for exclude in self.excludeFiles:
			excludeFiles |= set( glob.glob( exclude ) )

		for exclude in self.excludeDirs:
			excludeDirs |= set( glob.glob( exclude ) )

		for sourceDir in [ '.' ] + self.extraDirs:
			for root, dirnames, filenames in os.walk( sourceDir ):
				absroot = os.path.abspath( root )
				if absroot in excludeDirs:
					if absroot != self.csbuildDir:
						log.LOG_INFO( "Skipping dir {0}".format( root ) )
					continue
				if ".csbuild" in root or self.objDir in root or self.outputDir in root:
					continue
				if absroot == self.csbuildDir or absroot.startswith( self.csbuildDir ):
					continue
				bFound = False
				for testDir in excludeDirs:
					if absroot.startswith( testDir ):
						bFound = True
						break
				if bFound:
					if not absroot.startswith( self.csbuildDir ):
						log.LOG_INFO( "Skipping dir {0}".format( root ) )
					continue
				log.LOG_INFO( "Looking in directory {0}".format( root ) )
				if sources is not None:
					for extension in self.cppExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in excludeFiles:
								sources.append( os.path.abspath( path ) )
								self.hasCppFiles = True
					for extension in self.cExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in excludeFiles:
								sources.append( os.path.abspath( path ) )

					sources.sort( key = str.lower )

				if headers is not None:
					for extension in self.cppHeaderExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in excludeFiles:
								headers.append( os.path.abspath( path ) )
								self.hasCppFiles = True
				if cHeaders is not None:
					for extension in self.cHeaderExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in excludeFiles:
								cHeaders.append( os.path.abspath( path ) )

				if headers is not None or cHeaders is not None:
					for extension in self.ambiguousHeaderExtensions:
						for filename in fnmatch.filter( filenames, '*'+extension ):
							path = os.path.join( absroot, filename )
							if path not in excludeFiles:
								ambiguousHeaders.add( os.path.abspath( path ) )

		if self.hasCppFiles:
			headers += list(ambiguousHeaders)
		else:
			cHeaders += list(ambiguousHeaders)

		headers.sort( key = str.lower )


	def get_full_path( self, headerFile, relativeDir ):
		if relativeDir in _shared_globals.headerPaths:
			if headerFile in _shared_globals.headerPaths[relativeDir]:
				return _shared_globals.headerPaths[relativeDir][headerFile]
		else:
			_shared_globals.headerPaths[relativeDir] = {}

		if os.access(headerFile, os.F_OK):
			_shared_globals.headerPaths[relativeDir][headerFile] = headerFile
			path = os.path.join(os.getcwd(), headerFile)
			_shared_globals.headerPaths[relativeDir][headerFile] = path
			return path
		else:
			if relativeDir is not None:
				path = os.path.join( relativeDir, headerFile )
				if os.access(path, os.F_OK):
					return path

			for incDir in self.includeDirs:
				path = os.path.join( incDir, headerFile )
				if os.access(path, os.F_OK):
					_shared_globals.headerPaths[relativeDir][headerFile] = path
					return path

			_shared_globals.headerPaths[relativeDir][headerFile] = ""
			return ""


	def get_included_files( self, headerFile ):
		headers = []
		if sys.version_info >= (3, 0):
			f = open( headerFile, encoding = "latin-1" )
		else:
			f = open( headerFile )
		with f:
			for line in f:
				if line[0] != '#':
					continue

				RMatch = re.search( r"#\s*include\s*[<\"](.*?)[\">]", line )
				if RMatch is None:
					continue

				#Don't follow system headers, we should assume those are immutable
				if "." not in RMatch.group( 1 ):
					continue

				headers.append( RMatch.group( 1 ) )

		return headers


	def follow_headers( self, headerFile, allheaders ):
		"""Follow the headers in a file.
		First, this will check to see if the given header has been followed already.
		If it has, it pulls the list from the allheaders global dictionary and returns it.
		If not, it populates a new allheaders list with follow_headers2, and then adds
		that to the allheaders dictionary
		"""
		headers = []

		if not headerFile:
			return

		path = self.get_full_path( headerFile, self.workingDirectory )

		if not path:
			return

		if path in _shared_globals.allheaders:
			allheaders.update(_shared_globals.allheaders[path])
			return

		headers = self.get_included_files( path )

		for header in headers:

			#Find the header in the listed includes.
			subpath = self.get_full_path( header, os.path.dirname( headerFile ) )

			if self.ignoreExternalHeaders and not subpath.startswith( self.workingDirectory ):
				continue

			#If we've already looked at this header (i.e., it was included twice) just ignore it
			if subpath in allheaders:
				continue

			if subpath in _shared_globals.allheaders:
				allheaders.update(_shared_globals.allheaders[subpath])
				continue

			allheaders.add( subpath )

			theseheaders = set( )

			if self.headerRecursionDepth != 1:
				self.follow_headers2( subpath, theseheaders, 1, headerFile )

			_shared_globals.allheaders.update( { subpath: theseheaders } )
			allheaders.update(theseheaders)

		_shared_globals.allheaders.update( { path: set( allheaders ) } )


	def follow_headers2( self, headerFile, allheaders, n, parent ):
		"""More intensive, recursive, and cpu-hogging function to follow a header.
		Only executed the first time we see a given header; after that the information is cached."""
		headers = []

		if not headerFile:
			return

		path = self.get_full_path( headerFile, os.path.dirname( parent ) )

		if not path:
			return

		if path in _shared_globals.allheaders:
			allheaders.update(_shared_globals.allheaders[path])
			return

		headers = self.get_included_files( path )

		for header in headers:
			subpath = self.get_full_path( header, os.path.dirname( headerFile ) )

			if self.ignoreExternalHeaders and not subpath.startswith( self.workingDirectory ):
				continue

				#Check to see if we've already followed this header.
			#If we have, the list we created from it is already stored in _allheaders under this header's key.
			if subpath in allheaders:
				continue

			if subpath in _shared_globals.allheaders:
				allheaders.update(_shared_globals.allheaders[subpath])
				continue

			allheaders.add( subpath )

			theseheaders = set( allheaders )

			if self.headerRecursionDepth == 0 or n < self.headerRecursionDepth:
				self.follow_headers2( subpath, theseheaders, n + 1, headerFile )

			_shared_globals.allheaders.update( { subpath: theseheaders } )
			allheaders.update(theseheaders)


	def should_recompile( self, srcFile, ofile = None, for_precompiled_header = False ):
		"""Checks various properties of a file to determine whether or not it needs to be recompiled."""

		log.LOG_INFO( "Checking whether to recompile {0}...".format( srcFile ) )

		if self.recompileAll:
			log.LOG_INFO(
				"Going to recompile {0} because settings have changed in the makefile that will impact output.".format(
					srcFile ) )
			return True

		if not ofile:
			ofile = _utils.GetSourceObjPath( self, srcFile )

		if self.useChunks and not _shared_globals.disable_chunks:
			chunk = self.get_chunk( srcFile )
			if chunk:
				log.LOG_INFO("{} belongs to chunk {}".format(srcFile, chunk))

				chunkfile = _utils.GetChunkedObjPath( self, chunk )

				log.LOG_INFO("Checking for chunk file {}...".format(chunkfile))
				#First check: If the object file doesn't exist, we obviously have to create it.
				if not os.access(ofile , os.F_OK):
					ofile = chunkfile

		if not os.access(ofile , os.F_OK):
			log.LOG_INFO(
				"Going to recompile {0} because the associated object file does not exist.".format( srcFile ) )
			return True

		#Third check: modified time.
		#If the source file is newer than the object file, we assume it's been changed and needs to recompile.
		mtime = os.path.getmtime( srcFile )
		omtime = os.path.getmtime( ofile )

		if mtime > omtime:
			if for_precompiled_header:
				log.LOG_INFO(
					"Going to recompile {0} because it has been modified since the last successful build.".format(
						srcFile ) )
				return True

			oldmd5 = 1
			newmd5 = 9

			try:
				newmd5 = _shared_globals.newmd5s[srcFile]
			except KeyError:
				with open( srcFile, "r" ) as f:
					newmd5 = _utils.GetMd5( f )
				_shared_globals.newmd5s.update( { srcFile: newmd5 } )

			if platform.system( ) == "Windows":
				src = srcFile[2:]
			else:
				src = srcFile

			if sys.version_info >= (3,0):
				src = src.encode("utf-8")
				baseName = os.path.basename( src ).decode("utf-8")
			else:
				baseName = os.path.basename( src )

			md5file = "{}.md5".format( os.path.join( self.csbuildDir, "md5s", hashlib.md5( src ).hexdigest(), baseName ) )

			if os.access(md5file , os.F_OK):
				try:
					oldmd5 = _shared_globals.oldmd5s[md5file]
				except KeyError:
					with open( md5file, "rb" ) as f:
						oldmd5 = f.read( )
					_shared_globals.oldmd5s.update( { md5file: oldmd5 } )

			if oldmd5 != newmd5:
				log.LOG_INFO(
					"Going to recompile {0} because it has been modified since the last successful build.".format(srcFile ) )
				return True

		#Fourth check: Header files
		#If any included header file (recursive, to include headers included by headers) has been changed,
		#then we need to recompile every source that includes that header.
		#Follow the headers for this source file and find out if any have been changed o necessitate a recompile.
		headers = set()

		self.follow_headers( srcFile, headers )

		updatedheaders = []

		for header in headers:
			if not header:
				continue

			path = header

			if header in _shared_globals.headerCheck:
				b = _shared_globals.headerCheck[header]
				if b:
					updatedheaders.append( [header, path] )
				else:
					continue


			header_mtime = os.path.getmtime( path )

			if header_mtime > omtime:
				if for_precompiled_header:
					updatedheaders.append( [header, path] )
					_shared_globals.headerCheck[header] = True
					continue

				#newmd5 is 0, oldmd5 is 1, so that they won't report equal if we ignore them.
				newmd5 = 0
				oldmd5 = 1

				if platform.system( ) == "Windows":
					header = header[2:]

				if sys.version_info >= (3,0):
					header = header.encode("utf-8")
					baseName = os.path.basename( header ).decode("utf-8")
				else:
					baseName = os.path.basename( header )

				md5file = "{}.md5".format( os.path.join( self.csbuildDir, "md5s", hashlib.md5( header ).hexdigest(), baseName ) )

				if os.access(md5file , os.F_OK):
					try:
						newmd5 = _shared_globals.newmd5s[path]
					except KeyError:
						if sys.version_info >= (3, 0):
							f = open( path, encoding = "latin-1" )
						else:
							f = open( path )
						with f:
							newmd5 = _utils.GetMd5( f )
						_shared_globals.newmd5s.update( { path: newmd5 } )
					if os.access(md5file , os.F_OK):
						try:
							oldmd5 = _shared_globals.oldmd5s[md5file]
						except KeyError:
							with open( md5file, "rb" ) as f:
								oldmd5 = f.read( )
							_shared_globals.oldmd5s.update( { md5file: oldmd5 } )

				if oldmd5 != newmd5:
					updatedheaders.append( [header, path] )
					_shared_globals.headerCheck[header] = True
					continue

			_shared_globals.headerCheck[header] = False

		if updatedheaders:
			files = []
			for pair in updatedheaders:
				files.append( pair[0] )
				path = pair[1]
				if path not in self.allPaths:
					self.allPaths.append( os.path.abspath( path ) )
			log.LOG_INFO(
				"Going to recompile {0} because included headers {1} have been modified since the last successful build."
				.format(
					srcFile, files ) )
			return True

		#If we got here, we assume the object file's already up to date.
		log.LOG_INFO( "Skipping {0}: Already up to date".format( srcFile ) )
		return False


	def check_libraries( self ):
		"""Checks the libraries designated by the make script.
		Invokes ld to determine whether or not the library exists.1
		Uses the -t flag to get its location.
		And then stores the library's last modified time to a global list to be used by the linker later, to determine
		whether or not a project with up-to-date objects still needs to link against new libraries.
		"""
		log.LOG_INFO( "Checking required libraries..." )

		def check_libraries( libraries, force_static, force_shared ):
			libraries_ok = True
			for library in libraries:
				bFound = False
				for depend in self.reconciledLinkDepends:
					if _shared_globals.projects[depend].outputName.startswith(library) or \
							_shared_globals.projects[depend].outputName.startswith(
									"lib{}.".format( library ) ):
						bFound = True
						break
				if bFound:
					continue

				log.LOG_INFO( "Looking for lib{0}...".format( library ) )
				lib = self.activeToolchain.Linker().FindLibrary( self, library, self.libraryDirs,
					force_static, force_shared )
				if lib:
					log.LOG_INFO( "Found library lib{0} at {1}".format( library, lib ) )
					self.libraryLocations.append( lib )
				else:
					log.LOG_ERROR( "Could not locate library: {0}".format( library ) )
					libraries_ok = False
			return libraries_ok


		libraries_ok = check_libraries( self.libraries, False, False )
		libraries_ok = check_libraries( self.staticLibraries, True, False ) and libraries_ok
		libraries_ok = check_libraries( self.sharedLibraries, False, True ) and libraries_ok
		if not libraries_ok:
			log.LOG_ERROR( "Some dependencies are not met on your system." )
			log.LOG_ERROR( "Check that all required libraries are installed." )
			log.LOG_ERROR(
				"If they are installed, ensure that the path is included in the makefile (use csbuild.LibDirs() to set "
				"them)" )
			return False
		log.LOG_INFO( "Libraries OK!" )
		return True

	def CanJoinChunk(self, chunk, newFile):
		if not chunk:
			return True

		extension = "." + chunk[0].rsplit(".", 1)[1]
		newFileExtension = "." + newFile.rsplit(".", 1)[1]

		#TODO: Remove this once the source file extension management has been reworked.
		# Objective-C/C++ files should not be chunked since they won't play nice with C++.
		if extension == ".m" or extension == ".mm":
			return False

		if(
			(extension in self.cExtensions and newFileExtension in self.cppExtensions) or
			(extension in self.cppExtensions and newFileExtension in self.cExtensions)
		):
			return False

		if newFile in self.chunkExcludes:
			return False #NEVER ok to join chunk with this file!

		for sourceFile in chunk:
			if newFile in self.chunkMutexes and sourceFile in self.chunkMutexes[newFile]:
				log.LOG_INFO("Rejecting {} for this chunk because it is labeled as mutually exclusive with {} for chunking".format(newFile, sourceFile))
				return False
			if sourceFile in self.chunkMutexes and newFile in self.chunkMutexes[sourceFile]:
				log.LOG_INFO("Rejecting {} for this chunk because it is labeled as mutually exclusive with {} for chunking".format(newFile, sourceFile))
				return False

		return True

	def make_chunks( self, l ):
		""" Converts the list into a list of lists - i.e., "chunks"
		Each chunk represents one compilation unit in the chunked build system.
		"""
		if _shared_globals.disable_chunks or not self.useChunks:
			return [l]

		if self.unity:
			return [l]
		chunks = []
		if self.chunkFilesize > 0:
			sorted_list = sorted( l, key = os.path.getsize, reverse=True )
			while sorted_list:
				remaining = []
				chunksize = 0
				chunk = [sorted_list[0]]
				chunksize += os.path.getsize( sorted_list[0] )
				sorted_list.pop( 0 )
				for i in reversed(range(len(sorted_list))):
					srcFile = sorted_list[i]
					if not self.CanJoinChunk(chunk, srcFile):
						remaining.append(srcFile)
						continue
					filesize = os.path.getsize( srcFile )
					if chunksize + filesize > self.chunkFilesize:
						chunks.append( chunk )
						remaining += sorted_list[i::-1]
						log.LOG_INFO( "Made chunk: {0}".format( chunk ) )
						log.LOG_INFO( "Chunk size: {0}".format( chunksize ) )
						chunk = []
						break
					else:
						chunk.append( srcFile )
						chunksize += filesize
				if remaining:
					sorted_list = sorted( remaining, key = os.path.getsize, reverse=True )
				else:
					sorted_list = None

				if chunk:
					chunks.append( chunk )
					log.LOG_INFO( "Made chunk: {0}".format( chunk ) )
					log.LOG_INFO( "Chunk size: {0}".format( chunksize ) )
		elif self.chunkSize > 0:
			tempList = l
			while tempList:
				chunk = []
				remaining = []
				for i in range(len(tempList)):
					srcFile = tempList[i]
					if not self.CanJoinChunk(chunk, srcFile):
						remaining.append(srcFile)
						continue

					chunk.append(srcFile)

					if len(chunk) == self.chunkSize:
						remaining += tempList[i+1:]
						chunks.append( chunk )
						log.LOG_INFO( "Made chunk: {0}".format( chunk ) )
						chunk = []
						break
				tempList = remaining
				if chunk:
					chunks.append( chunk )
					log.LOG_INFO( "Made chunk: {0}".format( chunk ) )
		else:
			return [l]
		return chunks


	def get_chunk( self, srcFile ):
		"""Retrieves the chunk that a given file belongs to."""
		for chunk in self.chunks:
			if srcFile in chunk:
				return _utils.GetChunkName( self.outputName, chunk )
		return None


	def ContainsChunk( self, inputChunkFile ):
		# This logic really sucks and needs to be improved.
		inputChunkFile = os.path.splitext( os.path.basename( inputChunkFile ) )[0]
		for chunk in self.chunks:
			chunkName = _utils.GetChunkName( self.outputName, chunk )
			if inputChunkFile == chunkName:
				return True
		return False


	def save_md5( self, inFile ):
		# If we're running on Windows, we need to remove the drive letter from the input file path.
		#if platform.system( ) == "Windows":
		#	inFile = inFile[2:]

		if sys.version_info >= (3,0):
			inFile = inFile.encode("utf-8")
			baseName = os.path.basename( inFile ).decode("utf-8")
		else:
			baseName = os.path.basename( inFile )

		md5file = "{}.md5".format( os.path.join( self.csbuildDir, "md5s", hashlib.md5( inFile ).hexdigest(), baseName ) )

		md5dir = os.path.dirname( md5file )
		if not os.access(md5dir , os.F_OK):
			os.makedirs( md5dir )
		newmd5 = ""
		try:
			newmd5 = _shared_globals.newmd5s[inFile]
		except KeyError:
			if sys.version_info >= (3, 0):
				f = open( inFile, encoding = "latin-1" )
			else:
				f = open( inFile )
			with f:
				newmd5 = _utils.GetMd5( f )
		finally:
			with open( md5file, "wb" ) as f:
				f.write( newmd5 )


	def save_md5s( self, sources, headers ):
		for source in sources:
			self.save_md5( source )

		for header in headers:
			self.save_md5( header )

		for path in self.allPaths:
			self.save_md5( path )


	def precompile_headers( self ):
		if not self.needsPrecompileC and not self.needsPrecompileCpp:
			return True

		starttime = time.time( )
		log.LOG_BUILD( "Precompiling headers..." )

		self._builtSomething = True

		if not os.access(self.objDir , os.F_OK):
			os.makedirs( self.objDir )

		thread = None
		cthread = None
		cppobj = ""
		cobj = ""
		if self.needsPrecompileCpp:
			if not _shared_globals.semaphore.acquire( False ):
				if _shared_globals.max_threads != 1:
					log.LOG_INFO( "Waiting for a build thread to become available..." )
				_shared_globals.semaphore.acquire( True )
			if _shared_globals.interrupted:
				csbuild.Exit( 2 )

			log.LOG_BUILD(
				"Precompiling {0} ({1}/{2})...".format(
					self.cppHeaderFile,
					_shared_globals.current_compile,
					_shared_globals.total_compiles ) )

			_shared_globals.current_compile += 1

			cppobj = self.activeToolchain.Compiler().GetPchFile( self.cppHeaderFile )

			#precompiled headers block on current thread - run runs on current thread rather than starting a new one
			thread = _utils.ThreadedBuild( self.cppHeaderFile, cppobj, self, True )
			thread.start( )

		if self.needsPrecompileC:
			if not _shared_globals.semaphore.acquire( False ):
				if _shared_globals.max_threads != 1:
					log.LOG_INFO( "Waiting for a build thread to become available..." )
				_shared_globals.semaphore.acquire( True )
			if _shared_globals.interrupted:
				csbuild.Exit( 2 )

			log.LOG_BUILD(
				"Precompiling {0} ({1}/{2})...".format(
					self.cHeaderFile,
					_shared_globals.current_compile,
					_shared_globals.total_compiles ) )

			_shared_globals.current_compile += 1

			cobj = self.activeToolchain.Compiler().GetPchFile( self.cHeaderFile )

			#precompiled headers block on current thread - run runs on current thread rather than starting a new one
			cthread = _utils.ThreadedBuild( self.cHeaderFile, cobj, self, True )
			cthread.start( )

		if thread:
			thread.join( )
			_shared_globals.precompiles_done += 1
		if cthread:
			cthread.join( )
			_shared_globals.precompiles_done += 1

		totaltime = time.time( ) - starttime
		totalmin = math.floor( totaltime / 60 )
		totalsec = math.floor( totaltime % 60 )
		log.LOG_BUILD( "Precompile took {0}:{1:02}".format( int( totalmin ), int( totalsec ) ) )

		self.precompileDone = True
		self.precompileFailed = self.compilationFailed

		return not self.compilationFailed



class ProjectGroup( object ):
	"""
	Defines a group of projects, and also may contain subgroups.

	:ivar tempprojects: Temporary list of projects directly under this group
	:type tempprojects: dict[str, projectSettings]

	:ivar projects: Fully fleshed-out list of projects under this group
	Dict is { name : { target : project } }
	:type projects: dict[str, dict[str, projectSettings]]

	:ivar subgroups: List of child groups
	:type subgroups: dict[str, ProjectGroup]

	:ivar name: Group name
	:type name: str

	:ivar parentGroup: The group's parent group
	:type parentGroup: ProjectGroup
	"""
	def __init__( self, name, parentGroup ):
		"""
		Create a new ProjectGroup

		:param name: Group name
		:type name: str

		:param parentGroup: parent group
		:type parentGroup: ProjectGroup
		"""
		self.tempprojects = {}
		self.projects = {}
		self.subgroups = {}
		self.name = name
		self.parentGroup = parentGroup


rootGroup = ProjectGroup( "", None )
currentGroup = rootGroup
currentProject = projectSettings( )
