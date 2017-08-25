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
Contains a plugin class for interfacing with the Green Hills Software tools for WiiU.
"""

import csbuild
import os
import subprocess
import sys

from .. import _shared_globals
from .. import log
from .. import toolchain


class GlobalData(object):
	Instance = None

	def __init__(self):
		self.ghsRoot = os.environ.get("GHS_ROOT", "")
		self.cafeRoot = os.environ.get("CAFE_ROOT", "")


class WiiUBase(object):
	def __init__(self):
		if not GlobalData.Instance:
			GlobalData.Instance = GlobalData()

		self._globalData = GlobalData.Instance


	def GetValidArchitectures(self):
		return ["ppc"]


	def GetDefaultArchitecture(self):
		return "ppc"


	def copy(self, other):
		other._globalData = self._globalData


class WiiUCompiler(WiiUBase, toolchain.compilerBase):
	def __init__(self, shared):
		toolchain.compilerBase.__init__(self, shared)
		WiiUBase.__init__(self)

		self.ccCompilerPath = os.path.join(self._globalData.ghsRoot, "ccppc.exe")
		self.cxxCompilerPath = os.path.join(self._globalData.ghsRoot, "cxppc.exe")


	def copy(self, shared):
		ret = toolchain.compilerBase.copy(self, shared)
		WiiUBase.copy(self, ret)

		ret.ccCompilerPath = self.ccCompilerPath
		ret.cxxCompilerPath = self.cxxCompilerPath

		return ret

	
	def _setupForProject(self, project):
		missingEnvVar = 'Environment variable "{}" is not set!'

		assert self._globalData.ghsRoot, missingEnvVar.format("GHS_ROOT")
		assert self._globalData.cafeRoot, missingEnvVar.format("CAFE_ROOT")


	def _getIncludePathList(self, project):
		includePaths = [
			os.path.join(self._globalData.ghsRoot, "include", "ppc"),
			os.path.join(self._globalData.ghsRoot, "ansi"),
			os.path.join(self._globalData.ghsRoot, "scxx"),
			os.path.join(self._globalData.cafeRoot, "system", "include")
		]

		for incPath in project.includeDirs:
			includePaths.append(incPath)

		return ['-I"{}"'.format(x) for x in includePaths]


	def _getDefinesList(self, project):
		defines = [
			"-DNDEV=1",
			"-DCAFE=2",
			"-DPLATFORM=CAFE",
			"-DEPPC=1",
		]

		for define in project.defines:
			defines.append("-D{}".format(define))

		return defines


	def _getCompilerFlags(self, project, isCpp):
		return project.cxxCompilerFlags if isCpp else project.ccCompilerFlags


	def _getOptimizationArg(self, project):
		# Other optimization arguments:
		# 	MinimumDebug = "-Odebug"
		# 	OptimizedDebug = "-Omoredebug"
		# 	FullDebug = "-Omaxdebug"
		optMap = {
			csbuild.OptimizationLevel.Disabled: "-Onone",
			csbuild.OptimizationLevel.Size: "-Osize",
			csbuild.OptimizationLevel.Speed: "-Ospeed",
			csbuild.OptimizationLevel.Max: "-Ogeneral",
		}
		return optMap[project.optLevel]


	def _getBaseCommand(self, project, isCpp, isPch):
		cmdList = [
			self.cxxCompilerPath if isCpp else self.ccCompilerPath,
			"-pch" if isPch else "-c",
			self._getOptimizationArg(project),
			'-cpu="espresso"',
			"-kanji=shiftjis",
			"-only_explicit_reg_use",
			"--no_wrap_diagnostics",
			"-sda=none",
			"--no_commons",
			"--no_exceptions",
			"-MD",
			"-c99",
		]

		if project.debugLevel != csbuild.DebugLevel.Disabled:
			cmdList.append("-G")

		cmdList.extend(self._getIncludePathList(project))
		cmdList.extend(self._getDefinesList(project))
		cmdList.extend(self._getCompilerFlags(project, isCpp))

		return cmdList


	def InterruptExitCode(self):
		return -1073741510


	def GetBaseCxxCommand(self, project):
		return " ".join(self._getBaseCommand(project, True, False))


	def GetBaseCcCommand(self, project):
		return " ".join(self._getBaseCommand(project, False, False))


	def GetExtendedCommand(self, baseCmd, project, forceIncludeFile, outObj, inFile):
		cmdList = [
			baseCmd,
		]

		if forceIncludeFile:
			cmdList.append('-include "{}"'.format(forceIncludeFile))

		cmdList.extend([
			'-o "{}"'.format(outObj),
			inFile,
		])

		return " ".join(cmdList)


	def GetBaseCxxPrecompileCommand(self, project):
		return " ".join(self._getBaseCommand(project, True, True))


	def GetBaseCcPrecompileCommand(self, project):
		return " ".join(self._getBaseCommand(project, False, True))


	def GetExtendedPrecompileCommand(self, baseCmd, project, forceIncludeFile, outObj, inFile):
		return self.GetExtendedCommand(baseCmd, project, forceIncludeFile, outObj, inFile)


	def GetPchFile(self, fileName):
		return "{}.pch".format(fileName)


	def GetPreprocessCommand(self, baseCmd, project, inFile):
		return '"{}" -E "{}"'.format(baseCmd, inFile)


	def PragmaMessage(self, message):
		return '#pragma message "{}"'.format(message)


	def GetObjExt(self):
		return ".o"


	def _parseOutput(self, outputStr):
		return None


class WiiULinker(WiiUBase, toolchain.linkerBase):
	def __init__(self, shared):
		toolchain.linkerBase.__init__(self, shared)
		WiiUBase.__init__(self)

		cafeToolsPath = os.path.join(self._globalData.cafeRoot, "system", "bin", "tool")

		self._ghsLibPath = os.path.join(self._globalData.ghsRoot, "lib", "ppc")
		self._cafeLibRootPath = os.path.join(self._globalData.cafeRoot, "system", "lib", "ghs", "cafe")

		self._actual_library_names = {}
		self._linkerDefinitionFile = ""

		self.cxxCompilerPath = os.path.join(self._globalData.ghsRoot, "cxppc.exe")
		self.linkerPath = os.path.join(self._globalData.ghsRoot, "elxr.exe")
		self.makeRplPath = os.path.join(cafeToolsPath, "makerpl32.exe")
		self.prepRplPath = os.path.join(cafeToolsPath, "preprpl32.exe")


	def copy(self, shared):
		ret = toolchain.linkerBase.copy(self, shared)
		WiiUBase.copy(self, ret)

		ret._ghsLibPath = self._ghsLibPath
		ret._cafeLibRootPath = self._cafeLibRootPath
		ret._actual_library_names = self._actual_library_names
		ret._linkerDefinitionFile = self._linkerDefinitionFile
		ret.cxxCompilerPath = self.cxxCompilerPath
		ret.linkerPath = self.linkerPath
		ret.makeRplPath = ret.makeRplPath
		ret.prepRplPath = ret.prepRplPath

		return ret


	def InterruptExitCode( self ):
		return -1073741510


	def _getEntryPoint(self, project):
		return "-e _start" if project.type == csbuild.ProjectType.Application else "-e __rpl_crt"


	def _getLinkerDefinitionFile(self, project):
		if self._linkerDefinitionFile:
			return self._linkerDefinitionFile
		else:
			lnkFileDir = os.path.join(self._globalData.cafeRoot, "system", "include", "cafe")
			return os.path.join(lnkFileDir, "eppc.Cafe{}.ld".format("" if project.type == csbuild.ProjectType.Application else ".rpl"))


	def _getLibraryDirectoryList(self, project):
		sysDirList = [
			self._ghsLibPath,
			os.path.join(self._cafeLibRootPath, "{}DEBUG".format("" if project.optLevel == csbuild.OptimizationLevel.Disabled else "N"))
		]
		return sysDirList + project.libraryDirs


	def _createLinkerOptionFile(self, project, optionList):
		linkerCommandFilePath = os.path.join(project.csbuildDir, "{}.cmd".format(project.name))

		cmdString = "\n".join(optionList)
		if sys.version_info >= (3, 0):
			cmdString = cmdString.encode("utf-8")

		with open(linkerCommandFilePath, "w") as f:
			f.write(cmdString)
			f.flush()
			os.fsync(f.fileno())

		return linkerCommandFilePath


	def _getLibraryArg( self, lib, project ):
		for depend in project.reconciledLinkDepends:
			dependProj = _shared_globals.projects[depend]
			if dependProj.type == csbuild.ProjectType.Application:
				continue
			dependLibName = dependProj.outputName
			splitName = os.path.splitext(dependLibName)[0]
			if splitName == lib or splitName == "lib{}".format( lib ):
				return '-l{}.a '.format( splitName )
		return "-l{} ".format( self._actual_library_names[lib] )


	def _getLibraryArgList( self, libraries, project ):
		ret = []
		for lib in libraries:
			ret.append(self._getLibraryArg(lib, project))
		return ret


	def GetLinkCommand( self, project, outputFile, objList ):
		validRplTargets = [
			csbuild.ProjectType.Application,
			csbuild.ProjectType.SharedLibrary,
			csbuild.ProjectType.LoadableModule,
		]

		exportObjectFilePath = os.path.join(project.objDir, "{}_rpl_export.o".format(project.name))

		if project.type in validRplTargets:
			exportLibFilePath = os.path.join(project.outputDir, "{}.a".format(project.name))

			cmdList = [
				self.prepRplPath,
				"-xall",
				"-o {}".format(exportObjectFilePath),
				"-l {}".format(exportLibFilePath),
				"-r {}".format(project.name),
			] + objList
			fd = subprocess.Popen(" ".join(cmdList), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

			if sys.version_info >= ( 3, 0 ):
				(output, errors) = fd.communicate( str.encode( "utf-8" ) )
			else:
				(output, errors) = fd.communicate()

			if output:
				if sys.version_info >= (3, 0):
					output = output.decode("utf-8")
				log.LOG_INFO(output)

			if errors:
				if sys.version_info >= (3, 0):
					errors = errors.decode("utf-8")
				log.LOG_ERROR(errors)

		cmdList = [self.cxxCompilerPath]

		if project.type == csbuild.ProjectType.StaticLibrary:
			cmdList.extend([
				"-archive",
				'-o "{}"'.format(outputFile),
			])
			cmdList.extend(objList)
		else:
			linkerOptionFile = self._createLinkerOptionFile(project, objList)
			libDirList = self._getLibraryDirectoryList(project)
			cmdList.extend([
				"-relprog_cafe",
				"-lnk=-nosegments_always_executable",
				"-nostartfile",
				"-sda=none",
				"--no_exceptions",
				"-cpu=espresso",
				"-Ogeneral",
				"-G",
				"-Mn",
				"-Mu",
				"-map",
				self._getLinkerDefinitionFile(project),
				self._getEntryPoint(project),
				'-o "{}.elf"'.format(os.path.splitext(outputFile)[0]),
				'-lnkcmd="{}"'.format(linkerOptionFile),
			])
			cmdList.extend(['-L"{}"'.format(x) for x in libDirList])

			sharedLibraryType = [
				csbuild.ProjectType.SharedLibrary,
				csbuild.ProjectType.LoadableModule,
			]
			if project.type in sharedLibraryType:
				# Requried by all shared libraries.  Must always be the first library in the list!
				cmdList.append("-lrpl.a")

			cmdList.extend(self._getLibraryArgList(project.libraries, project))
			cmdList.extend(self._getLibraryArgList(project.staticLibraries, project))
			cmdList.extend(self._getLibraryArgList(project.sharedLibraries, project))
			cmdList.append("-lcoredyn.a")



		return " ".join(cmdList)


	def postBuildStep(self, project):
		validRplTargets = [
			csbuild.ProjectType.Application,
			csbuild.ProjectType.SharedLibrary,
			csbuild.ProjectType.LoadableModule,
		]

		if project.type in validRplTargets:
			cmdList = [
				self.makeRplPath,
				"-nolib",
				"-t BUILD_TYPE={}DEBUG".format("" if project.optLevel == csbuild.OptimizationLevel.Disabled else "N"),
				'-dbg_source_root "{}"'.format(project.workingDirectory),
				"-checknosda",
				'"{}.elf"'.format(os.path.join(project.outputDir, os.path.splitext(project.outputName)[0])),
			]

			if project.type == csbuild.ProjectType.Application:
				cmdList.append("-f")

			fd = subprocess.Popen(" ".join(cmdList), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

			if sys.version_info >= ( 3, 0 ):
				(output, errors) = fd.communicate( str.encode( "utf-8" ) )
			else:
				(output, errors) = fd.communicate()

			if output:
				if sys.version_info >= (3, 0):
					output = output.decode("utf-8")
				log.LOG_INFO(output)

			if errors:
				if sys.version_info >= (3, 0):
					errors = errors.decode("utf-8")
				log.LOG_ERROR(errors)


	def FindLibrary( self, project, library, libraryDirs, force_static, force_shared ):
		libDirList = self._getLibraryDirectoryList(project)

		def lookupLibrary(libPrefix):
			for libDir in libDirList:
				libFilePath = "{}{}.a".format(libPrefix, library)
				log.LOG_INFO("Looking for library {} in directory {}...".format(library, libFilePath))

				libFilePath = os.path.join(libDir, libFilePath)

				# Check for a static lib.
				if os.access( libFilePath , os.F_OK ):
					self._actual_library_names.update( { library : os.path.basename(libFilePath) } )
					return libFilePath

		foundPath = lookupLibrary("")
		if foundPath:
			return foundPath

		# Check with the lib- prefix on each library filename.
		foundPath = lookupLibrary("lib")
		if foundPath:
			return foundPath

		# The library wasn't found.
		return None


	def GetDefaultOutputExtension( self, projectType ):
		return {
			csbuild.ProjectType.Application:    ".rpx",
			csbuild.ProjectType.StaticLibrary:  ".a",
			csbuild.ProjectType.SharedLibrary:  ".rpl",
			csbuild.ProjectType.LoadableModule: ".rpl",
		}[projectType]
