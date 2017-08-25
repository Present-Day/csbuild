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
Contains a plugin class for interfacing with MSVC
"""

import os
import platform
import re
import subprocess
import sys
import glob

from collections import OrderedDict

from . import toolchain
from . import _shared_globals
from . import log
from .scrapers import COFF

import csbuild

### Reference: http://msdn.microsoft.com/en-us/library/f35ctcxw.aspx

class VcVarsCache:
	def __init__( self, environPath_, binPath_, includePathList_, libPathList_ ):
		self.environPath = environPath_
		self.binPath = binPath_
		self.includePathList = includePathList_
		self.libPathList = libPathList_

VC_VARS_CACHE_MAP = {} # Dictionary mapping output architecture to cached data from vcvarsall.bat.
DEFAULT_MSVC_VERSION = 0

MSVC_VERSION = OrderedDict([
	("2010", 100),
	("2012", 110),
	("2013", 120),
	("2015", 140),
])

IS_PLATFORM_64_BIT = {
	"amd64":  True,
	"x86_64": True,
	"x86":    False,
	"i386":   False,
}


class SubSystem( object ):
	"""
	Enum to define the subsystem to compile against.
	"""
	DEFAULT = 0
	CONSOLE = 1
	WINDOWS = 2
	WINDOWS_CE = 3
	NATIVE = 4
	POSIX = 5
	BOOT_APPLICATION = 6
	EFI_APPLICATION = 7
	EFI_BOOT_SERVICE_DRIVER = 8
	EFI_ROM = 9
	EFI_RUNTIME_DRIVER = 10


class MsvcBase( object ):
	def __init__(self):
		self.shared._project_settings = None
		self.shared.debug_runtime = False
		self.shared.debug_runtime_set = False
		self.shared.msvc_version = 0

		self.shared._vc_env_var = ""
		self.shared._toolchain_path = ""
		self.shared._include_path = []
		self.shared._lib_path = []
		self.shared.binPath = ""
		self.shared.environPath = ""


	@staticmethod
	def AdditionalArgs( parser ):
		parser.add_argument( "--msvc-version", help="Version of msvc to use.", choices=sorted( MSVC_VERSION.keys() ) )


	def _copyTo(self, other):
		other.shared._project_settings = self.shared._project_settings
		other.shared.debug_runtime = self.shared.debug_runtime
		other.shared.debug_runtime_set = self.shared.debug_runtime_set
		other.shared.msvc_version = self.shared.msvc_version

		other.shared._vc_env_var = self.shared._vc_env_var
		other.shared._toolchain_path = self.shared._toolchain_path
		other.shared._include_path = list( self.shared._include_path )
		other.shared._lib_path = list( self.shared._lib_path )
		other.shared.binPath = self.shared.binPath
		other.shared.environPath = self.shared.environPath


	def SetMsvcVersion( self, visual_studio_version ):
		"""
		Set the MSVC version.

		:param visual_studio_version: The version of Visual Studio associated with the desired version of msvc.
		:type visual_studio_version: str
		"""
		self.shared.msvc_version = MSVC_VERSION[visual_studio_version]

		if "msvc" in _shared_globals.selectedToolchains:
			# Verify the selected version of Visual Studio is installed.
			macroName = "VS{}COMNTOOLS".format( self.shared.msvc_version )
			assert macroName in os.environ, 'Required environment variable "{}" is missing; unable to verify installation of Visual Studio {}!'.format( macroName, visual_studio_version )


	def GetMsvcVersion( self ):
		"""
		Get the MSVC version.

		:return: int
		"""
		self._setupMsvcVersion()
		return self.shared.msvc_version


	def GetBinPath(self):
		"""
		Get the MSVC bin path.

		:return: str
		"""
		return self.shared.binPath


	def GetValidArchitectures(self):
		return ['x86', 'x64', "arm"]


	def _setupForProject( self, project ):
		if platform.system() != "Windows":
			return

		self._setupMsvcVersion()

		# If ARM is selected, make sure we can actually build for it.
		assert not ( project.outputArchitecture == "arm" and self.shared.msvc_version < MSVC_VERSION["2012"] ), "Compiling for ARM is only available from Visual Studio 2012 and up!"

		self.shared._project_settings = project
		self.shared._vc_env_var = "VS{}COMNTOOLS".format( self.shared.msvc_version )
		self.shared._toolchain_path = os.path.normpath( os.path.join( os.environ[self.shared._vc_env_var], "..", "..", "VC" ) )

		isPlatform64Bit = IS_PLATFORM_64_BIT[platform.machine().lower()]

		global VC_VARS_CACHE_MAP
		if not self.shared._project_settings.outputArchitecture in VC_VARS_CACHE_MAP:
			# Versions prior to Visual Studio 2013 had a slightly different set of arguments.
			if self.shared.msvc_version < MSVC_VERSION["2013"]:
				vcvarsallArg = {
					"x86": "x86",
					"x64": "amd64" if isPlatform64Bit else "x86_amd64",
					"arm": "x86_arm",
				}
			else:
				vcvarsallArg = {
					"x86": "amd64_x86" if isPlatform64Bit else "x86",
					"x64": "amd64" if isPlatform64Bit else "x86_amd64",
					"arm": "amd64_arm" if isPlatform64Bit else "x86_arm",
				}

			vcvarsallArg = vcvarsallArg[self.shared._project_settings.outputArchitecture]
			batchFilePath = os.path.join( self.shared._toolchain_path, "vcvarsall.bat" )
			fd = subprocess.Popen( '"{}" {} & set'.format( batchFilePath, vcvarsallArg ), stdout = subprocess.PIPE, stderr = subprocess.PIPE )

			if sys.version_info >= ( 3, 0 ):
				(output, errors) = fd.communicate( str.encode( "utf-8" ) )
			else:
				(output, errors) = fd.communicate()

			outputLines = output.splitlines()

			windowsEnvironPath = ""
			windowsBinPath = ""
			windowsIncludePathList = []
			windowsLibPathList = []

			for line in outputLines:

				# Convert to a string in Python3.
				if sys.version_info >= ( 3, 0 ):
					line = line.decode( "utf-8" )

				keyValueList = line.split( "=", 1 )

				# Only accept lines that contain key/value pairs.
				if len( keyValueList ) == 2:

					# In Windows, all environment variables are case insensitive.
					keyValueList[0] = keyValueList[0].lower()

					if keyValueList[0] == "path":
						windowsEnvironPath = keyValueList[1]

						# Passing a custom environment to subprocess.Popen() does not always help in locating a command
						# to execute on Windows (seems to be a bug with CreateProcess()),so we still need to find the
						# bin path where the tools live.  Luckily, the modified path vars are setup such that the first
						# we come across containing "cl.exe" is the one we want.
						for envPath in [ path for path in windowsEnvironPath.split( ";" ) if path ]:
							if os.access( os.path.join( envPath, "cl.exe" ), os.F_OK ):
								windowsBinPath = envPath
								break

					elif keyValueList[0] == "include":
						windowsIncludePathList = [ path for path in keyValueList[1].split( ";" ) if path ]

					elif keyValueList[0] == "lib":
						windowsLibPathList = [ path for path in keyValueList[1].split( ";" ) if path ]

			VC_VARS_CACHE_MAP[self.shared._project_settings.outputArchitecture] = VcVarsCache( windowsEnvironPath, windowsBinPath, windowsIncludePathList, windowsLibPathList )

		vcVarsCache = VC_VARS_CACHE_MAP[self.shared._project_settings.outputArchitecture]

		self.shared._include_path = vcVarsCache.includePathList
		self.shared._lib_path = vcVarsCache.libPathList
		self.shared.binPath = vcVarsCache.binPath
		self.shared.environPath = vcVarsCache.environPath


	def GetEnv( self ):
		return { "PATH": self.shared.environPath }


	def InterruptExitCode( self ):
		return 4


	def _setupMsvcVersion(self):
		verCmdLine = csbuild.GetOption("msvc_version")

		# Do nothing if we already have a version set and nothing was passed in from the command line.
		if self.shared.msvc_version and not verCmdLine:
			return

		# If a version was passed to us from the command line, use that.
		if verCmdLine:
			self.shared.msvc_version = MSVC_VERSION[verCmdLine]

		# If we still don't have a version, fallback to the default.
		if not self.shared.msvc_version:
			global DEFAULT_MSVC_VERSION
			if not DEFAULT_MSVC_VERSION:
				# Find the highest version of Visual Studio a user has install so we can use that as the default
				# in case they don't provide a version manually.
				reversedKeys = reversed( MSVC_VERSION )
				for versionKey in reversedKeys:
					versionValue = MSVC_VERSION[versionKey]
					macroName = "VS{}COMNTOOLS".format( versionValue )
					if macroName in os.environ:
						DEFAULT_MSVC_VERSION = versionValue
						break
			if not DEFAULT_MSVC_VERSION:
				log.LOG_ERROR("No supported version of Visual Studio detected.  Please install a supported version ({}) or try another toolchain.".format( ", ".join( [ key for key in MSVC_VERSION.keys() ] ) ) )
				csbuild.Exit(1)
			self.shared.msvc_version = DEFAULT_MSVC_VERSION


	def _convertArgListToString( self, argList ):
		return " ".join( [x for x in argList if x] )


	def _parseOutput(self, outputStr):
		compileDetail = re.compile(r"^(cl|LINK|.+?)(\((\d*)\))?\s*: (Command line |fatal )?(warning|error) ([A-Z]+\d\d\d\d: .*)$")
		additionalInfo = re.compile(r"^        \s*(?:(could be |or )\s*')?(.*)\((\d+)\) : (.*)$")

		line = None
		ret = []
		detailsToAppend = []

		try:
			for text in outputStr.split('\n'):
				if not text.strip():
					continue

				match = additionalInfo.search(text)
				if text.startswith("        ") and not match:
					subline = _shared_globals.OutputLine()
					subline.text = text.rstrip()
					subline.line = -1
					subline.file = ""
					subline.level = _shared_globals.OutputLevel.NOTE
					subline.column = -1
					if line is None:
						detailsToAppend.append(subline)
					else:
						line.details.append(subline)
					continue

				if match:
					subline = _shared_globals.OutputLine()
					subline.text = match.group(4)
					subline.line = int(match.group(3))
					subline.file = match.group(2)
					subline.level = _shared_globals.OutputLevel.NOTE
					subline.column = -1
					if line is None:
						detailsToAppend.append(subline)
					else:
						line.details.append(subline)
					continue

				compileMatch = compileDetail.search(text)
				if compileMatch:
					line = _shared_globals.OutputLine()
					fileName = compileMatch.group(1)
					if fileName != 'cl' and fileName != 'LINK':
						line.file = fileName
					lineNumber = compileMatch.group(3)
					if lineNumber:
						line.line = int(lineNumber)

					category = compileMatch.group(5)
					line.column = -1

					if category == "error":
						line.level = _shared_globals.OutputLevel.ERROR
					else:
						line.level = _shared_globals.OutputLevel.WARNING

					line.text = compileMatch.group(6)

					line.details = detailsToAppend
					detailsToAppend = []
					ret.append(line)
					continue

				if text.startswith("Error:"):
					line = _shared_globals.OutputLine()
					line.text = text[6:].strip()
					line.fileName = ""
					line.line = -1
					line.details = detailsToAppend
					detailsToAppend = []
					line.level = _shared_globals.OutputLevel.ERROR
					ret.append(line)
					continue

				if text.startswith("Warning:"):
					line = _shared_globals.OutputLine()
					line.text = text[8:].strip()
					line.fileName = ""
					line.line = -1
					line.details = detailsToAppend
					detailsToAppend = []
					line.level = _shared_globals.OutputLevel.WARNING
					ret.append(line)
					continue

			return ret
		except Exception as e:
			print(e)
			return None



class MsvcCompiler( MsvcBase, toolchain.compilerBase ):
	def __init__( self, shared ):
		toolchain.compilerBase.__init__( self, shared )
		MsvcBase.__init__( self )


	def copy(self, shared):
		ret = toolchain.compilerBase.copy(self, shared)
		MsvcBase._copyTo(self, ret)
		return ret


	def _getCompilerExe( self ):
		return '"{}"'.format( os.path.join( self.shared.binPath, "cl.exe" ) )


	def _getDefaultCompilerArgs( self ):
		return "/nologo /c /Oi /GS"


	def _getDefaultExtendedCompilerArgs( self ):
		return "/Gm- /errorReport:none"


	def _getDebugArg(self):
		debugLevel = self.shared._project_settings.debugLevel
		if debugLevel == csbuild.DebugLevel.EmbeddedSymbols:
			return "/Z7"
		if debugLevel == csbuild.DebugLevel.ExternalSymbols:
			return "/Zi"
		if debugLevel == csbuild.DebugLevel.ExternalSymbolsPlus:
			return "/ZI"
		return ""


	def _getOptArg(self):
		optLevel = self.shared._project_settings.optLevel
		if optLevel == csbuild.OptimizationLevel.Max:
			return "/Ox"
		if optLevel == csbuild.OptimizationLevel.Speed:
			return "/O2"
		if optLevel == csbuild.OptimizationLevel.Size:
			return "/O1"
		return "/Od"


	def _getRuntimeLinkageArg( self ):
		return "/{}{}".format(
			"MT" if self.shared._project_settings.useStaticRuntime else "MD",
			"d" if self.shared.debug_runtime else ""
		)


	def _getPreprocessorDefinitionArgs( self ):
		argList = []

		# Add the defines.
		for defineName in self.shared._project_settings.defines:
			argList.append( "/D{}".format( defineName ) )

		# Add the undefines.
		for defineName in self.shared._project_settings.undefines:
			argList.append( "/U{}".format( defineName ) )

		return self._convertArgListToString( argList )


	def _getRuntimeErrorChecksArg( self ):
		return "/RTC1" if self.shared._project_settings.optLevel == csbuild.OptimizationLevel.Disabled else ""


	def _getProjectSettingsArgs( self, isCpp ):
		return " ".join( self.shared._project_settings.cxxCompilerFlags ) if isCpp else " ".join( self.shared._project_settings.ccCompilerFlags )


	def _getPdbArg( self ):
		return '/Fd"{}"'.format( os.path.join( self.shared._project_settings.outputDir, "{}.pdb".format( self.shared._project_settings.outputName.rsplit( '.', 1 )[0] ) ) )

	def _getCompilerArgs( self ):
		argList = [
			self._getDefaultCompilerArgs(),
			self._getPreprocessorDefinitionArgs(),
			self._getRuntimeLinkageArg(),
			self._getWarningArgs(),
			self._getIncludeDirectoryArgs(),
			self._getDebugArg(),
			self._getOptArg(),
			self._getRuntimeErrorChecksArg(),
		]
		return self._convertArgListToString( argList )


	def _getCompilerCommand( self, isCpp ):
		argList = [
			self._getCompilerExe(),
			self._getCompilerArgs(),
			self._getProjectSettingsArgs( isCpp ),
		]
		return self._convertArgListToString( argList )


	def _getExtendedCompilerArgs( self, base_cmd, force_include_file, output_obj, input_file ):
		pch = self.GetPchFile( force_include_file )
		if os.access(pch , os.F_OK):
			pch = '/Fp"{0}"'.format( pch )
		else:
			pch = ""

		argList = [
			base_cmd,
			pch,
			self._getDefaultExtendedCompilerArgs(),
			self._getPdbArg(),
			'/Fo"{}"'.format( output_obj ),
			'/FI"{}"'.format( force_include_file ) if force_include_file else "",
			'/Yu"{}"'.format( force_include_file ) if force_include_file else "",
			"/FS" if self.shared.msvc_version >= MSVC_VERSION["2013"] else "",
			'"{}"'.format( input_file )
		]
		return self._convertArgListToString( argList )


	def preLinkStep( self, project ):
		if project.cHeaderFile:
			project.extraObjs.add( "{}.obj".format( project.cHeaderFile.rsplit( ".", 1 )[0]) )
		if project.cppHeaderFile:
			project.extraObjs.add( "{}.obj".format( project.cppHeaderFile.rsplit( ".", 1 )[0]) )


	def _getExtendedPrecompilerArgs( self, base_cmd, force_include_file, output_obj, input_file ):
		split = input_file.rsplit( ".", 1 )
		#This is safe to do because csbuild always creates C++ precompiled headers with a .hpp extension.
		srcFile = os.path.join( "{}.{}".format( split[0], "c" if split[1] == "h" else "cpp" ) )
		file_mode = 438 # Octal 0666
		fd = os.open( srcFile, os.O_WRONLY | os.O_CREAT | os.O_NOINHERIT | os.O_TRUNC, file_mode )
		data = "#include \"{}\"\n".format( input_file )
		if sys.version_info >= ( 3, 0 ):
			data = data.encode( "utf-8" )
		os.write( fd, data )
		os.fsync( fd )
		os.close( fd )

		objFile = "{}.obj".format( split[0] )
		argList = [
			base_cmd,
			self._getDefaultExtendedCompilerArgs(),
			self._getPdbArg(),
			'/Yc"{}"'.format( input_file ),
			'/Fp"{}"'.format( output_obj ),
			'/FI"{}"'.format( input_file ),
			'/Fo"{}"'.format( objFile ),
			'"{}"'.format( srcFile ),
		]
		return self._convertArgListToString( argList )


	def _getWarningArgs( self ):
		#TODO: Support additional warning options.
		if self.shared._project_settings.noWarnings:
			return "/w"
		elif self.shared._project_settings.warningsAsErrors:
			return "/WX"

		return ""


	def _getIncludeDirectoryArgs( self ):
		includeArgs = []

		for incDir in self.shared._project_settings.includeDirs:
			includeArgs.append( '/I"{}"'.format( os.path.normpath( incDir ) ) )

		# The default include paths should be added last so that any paths set by the user get searched first.
		for incDir in self.shared._include_path:
			includeArgs.append( '/I"{}"'.format( incDir ) )

		return self._convertArgListToString( includeArgs )


	def GetBaseCxxCommand( self, project ):
		self._setupForProject( project )
		return self._getCompilerCommand( True )


	def GetBaseCcCommand( self, project ):
		self._setupForProject( project )
		return self._getCompilerCommand( False )


	def GetExtendedCommand( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		self._setupForProject( project )
		return self._getExtendedCompilerArgs( baseCmd, forceIncludeFile, outObj, inFile )


	def GetBaseCxxPrecompileCommand( self, project ):
		self._setupForProject( project )
		return self.GetBaseCxxCommand( project )


	def GetBaseCcPrecompileCommand( self, project ):
		self._setupForProject( project )
		return self.GetBaseCcCommand( project )


	def GetExtendedPrecompileCommand( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		self._setupForProject( project )
		return self._getExtendedPrecompilerArgs( baseCmd, forceIncludeFile, outObj, inFile )


	def GetPreprocessCommand( self, baseCmd, project, inFile ):
		return '{} /E /wd"4005" "{}"'.format( baseCmd, inFile )


	def PragmaMessage( self, message ):
		return '#pragma message("{}")'.format( message )


	def GetObjExt( self ):
		return ".obj"


	def GetPchFile( self, fileName ):
		return fileName.rsplit( ".", 1 )[0] + ".pch"


	def SupportsObjectScraping(self):
		return False


	def GetObjectScraper(self):
		return None #COFF.COFFScraper()


	def SupportsDummyObjects(self):
		return True


	def MakeDummyObjects(self, objList):
		for obj in objList:
			if self.shared._project_settings.outputArchitecture == "x64":
				COFF.COFFScraper.CreateEmptyXCOFFObject( COFF.MachineType.X64, obj )
			else:
				COFF.COFFScraper.CreateEmptyCOFFObject( COFF.MachineType.Win32, obj )


class MsvcLinker( MsvcBase, toolchain.linkerBase ):
	def __init__( self, shared ):
		toolchain.linkerBase.__init__( self, shared )
		MsvcBase.__init__( self )
		self._subsystem = SubSystem.DEFAULT

		self._actual_library_names = { }


	def copy(self, shared):
		ret = toolchain.linkerBase.copy(self, shared)
		MsvcBase._copyTo(self, ret)

		ret._subsystem = self._subsystem
		ret._actual_library_names = dict(self._actual_library_names)
		return ret


	def _getLinkerExe( self ):
		return '"{}"'.format( os.path.join( self.shared.binPath, "lib.exe" if self.shared._project_settings.type == csbuild.ProjectType.StaticLibrary else "link.exe" ) )


	def _getDefaultLinkerArgs( self ):
		argList = [
			"/ERRORREPORT:NONE /NOLOGO",
			"/NXCOMPAT /DYNAMICBASE" if self.shared._project_settings.type != csbuild.ProjectType.StaticLibrary else ""
		]
		for libPath in self.shared._lib_path:
			argList.append( '/LIBPATH:"{}"'.format( libPath.strip( "\\") ) )
		return self._convertArgListToString( argList )


	def _getNonStaticLibraryLinkerArgs( self ):
		argList = []

		# The following arguments should only be specified for dynamic libraries and executables (being used with link.exe, not lib.exe).
		if not self.shared._project_settings.type == csbuild.ProjectType.StaticLibrary:
			argList.extend([
				"/PROFILE" if self.shared._project_settings.profile else "",
				"/DEBUG" if self.shared._project_settings.profile or self.shared._project_settings.debugLevel != csbuild.DebugLevel.Disabled else "",
			])

			if not self.shared._project_settings.type == csbuild.ProjectType.Application:
				argList.append( "/DLL" )

		return self._convertArgListToString( argList )


	def _getLinkerArgs( self, output_file, obj_list ):
		argList = [
			self._getDefaultLinkerArgs(),
			self._getImportLibraryArg( output_file ),
			self._getNonStaticLibraryLinkerArgs(),
			self._getSubsystemArg(),
			self._getArchitectureArg(),
			self._getLinkerWarningArg(),
			self._getLibraryDirectoryArgs(),
			self._getLinkerOutputArg( output_file ),
			self._getLibraryArgs(),
			self._getLinkerObjFileArgs( obj_list )
		]
		return self._convertArgListToString( argList )


	def _getArchitectureArg( self ):
		return "/MACHINE:{}".format( self.shared._project_settings.outputArchitecture.upper() )


	def _getImportLibraryArg(self, output_file):
		if self.shared._project_settings.type == csbuild.ProjectType.SharedLibrary or self.shared._project_settings.type == csbuild.ProjectType.LoadableModule:
			return '/IMPLIB:"{}"'.format(os.path.splitext(output_file)[0] + ".lib")
		else:
			return ""


	def _getSubsystemArg( self ):
		# The default subsystem is implied, so it has no explicit argument.
		# When no argument is specified, the linker will assume a default subsystem which depends on a number of factors:
		#   CONSOLE -> Either main or wmain are defined (or int main(array<String^>^) for managed code).
		#   WINDOWS -> Either WinMain or wWinMain are defined (or WinMain(HINSTANCE*, HINSTANCE*, char*, int) or wWinMain(HINSTANCE*, HINSTANCE*, wchar_t*, int) for managed code).
		#   NATIVE -> The /DRIVER:WDM argument is specified (currently unsupported).
		if self._subsystem == SubSystem.DEFAULT:
			return ""

		sub_system_type = {
			SubSystem.CONSOLE: "CONSOLE",
			SubSystem.WINDOWS: "WINDOWS",
			SubSystem.WINDOWS_CE: "WINDOWSCE",
			SubSystem.NATIVE: "NATIVE",
			SubSystem.POSIX: "POSIX",
			SubSystem.BOOT_APPLICATION: "BOOT_APPLICATION",
			SubSystem.EFI_APPLICATION: "EFI_APPLICATION",
			SubSystem.EFI_BOOT_SERVICE_DRIVER: "EFI_BOOT_SERVICE_DRIVER",
			SubSystem.EFI_ROM: "EFI_ROM",
			SubSystem.EFI_RUNTIME_DRIVER: "EFI_RUNTIME_DRIVER"
		}

		return "/SUBSYSTEM:{}".format( sub_system_type[self._subsystem] )


	def _getLibraryArgs( self ):
		argList = []

		# Static libraries don't require any libraries to be linked.
		if not self.shared._project_settings.type == csbuild.ProjectType.StaticLibrary:
			argList.extend([
				"kernel32.lib",
				"user32.lib",
				"gdi32.lib",
				"winspool.lib",
				"comdlg32.lib",
				"advapi32.lib",
				"shell32.lib",
				"ole32.lib",
				"oleaut32.lib",
				"uuid.lib",
				"odbc32.lib",
				"odbccp32.lib",
			])

		for lib in (
			self.shared._project_settings.libraries |
			self.shared._project_settings.staticLibraries |
			self.shared._project_settings.sharedLibraries
		):
			found = False
			for depend in self.shared._project_settings.reconciledLinkDepends:
				dependProj = _shared_globals.projects[depend]
				if dependProj.type == csbuild.ProjectType.Application:
					continue
				dependLibName = dependProj.outputName
				splitName = os.path.splitext(dependLibName)[0]
				if splitName == lib or splitName == "lib{}".format( lib ):
					found = True
					argList.append( '"{}.lib"'.format( splitName ) )
					break
			if not found:
				argList.append( '"{}"'.format( self._actual_library_names[lib] ) )

		return self._convertArgListToString( argList )


	def _getLinkerWarningArg( self ):
		# When linking, the only warning argument supported is whether or not to treat warnings as errors.
		return "/WX{}".format( "" if self.shared._project_settings.warningsAsErrors else ":NO" )


	def _getLibraryDirectoryArgs( self ):
		libDirArgs = []

		for libDir in self.shared._project_settings.libraryDirs:
			libDirArgs.append( '/LIBPATH:"{}"'.format( os.path.normpath( libDir ) ) )

		return self._convertArgListToString( libDirArgs )


	def _getLinkerOutputArg( self, output_file ):
		return '/OUT:"{}"'.format( output_file )


	def _getLinkerObjFileArgs( self, obj_file_list ):
		args = []
		for objFile in obj_file_list:
			args.append( '"{}"'.format( objFile ) )

		return self._convertArgListToString( args )


	def _getProjectSettingsLinkerArgs( self ):
		return " ".join( self.shared._project_settings.linkerFlags )


	def _getLinkerCommand( self, output_file, obj_list ):
		linkFile = os.path.join(self.shared._project_settings.csbuildDir, "{}.cmd".format(self.shared._project_settings.name))

		file_mode = 438 # Octal 0666
		fd = os.open(linkFile, os.O_WRONLY | os.O_CREAT | os.O_NOINHERIT | os.O_TRUNC, file_mode)

		data = self._getLinkerArgs( output_file, obj_list )
		if sys.version_info >= (3, 0):
			data = data.encode("utf-8")
		os.write(fd, data)
		os.fsync(fd)
		os.close(fd)

		argList = [
			self._getLinkerExe(),
			self._getProjectSettingsLinkerArgs(),
			'@"{}"'.format(linkFile),
		]
		return self._convertArgListToString( argList )


	def FindLibrary( self, project, library, libraryDirs, force_static, force_shared ):
		self._setupForProject(project)
		libfile = "{}.lib".format( library )

		for lib_dir in self.shared._lib_path:
			log.LOG_INFO("Looking for library {} in directory {}...".format(libfile, lib_dir))
			lib_file_path = os.path.join( lib_dir, libfile )
			# Do a simple check to see if the file exists.
			if os.access(lib_file_path , os.F_OK):
				self._actual_library_names.update( { library : libfile } )
				return lib_file_path

		for lib_dir in libraryDirs:
			log.LOG_INFO("Looking for library {} in directory {}...".format(libfile, lib_dir))
			lib_file_path = os.path.join( lib_dir, libfile )
			# Do a simple check to see if the file exists.
			if os.access(lib_file_path , os.F_OK):
				self._actual_library_names.update( { library : libfile } )
				return lib_file_path

		for lib_dir in libraryDirs:
			#Compatibility with Linux's way of adding lib- to the front of its libraries
			libfileCompat = "lib{}".format( libfile )
			log.LOG_INFO("Looking for library {} in directory {}...".format(libfileCompat, lib_dir))
			lib_file_path = os.path.join( lib_dir, libfileCompat )
			if os.access(lib_file_path , os.F_OK):
				self._actual_library_names.update( { library : libfileCompat } )
				return lib_file_path

		# The library wasn't found.
		return None


	def GetLinkCommand( self, project, outputFile, objList ):
		self._setupForProject( project )
		return self._getLinkerCommand( outputFile, objList )


	def GetDefaultOutputExtension( self, projectType ):
		if projectType == csbuild.ProjectType.Application:
			return ".exe"
		elif projectType == csbuild.ProjectType.StaticLibrary:
			return ".lib"
		elif projectType == csbuild.ProjectType.SharedLibrary or projectType == csbuild.ProjectType.LoadableModule:
			return ".dll"


	def LinkDebugRuntime( self ):
		"""
		Link with debug runtime
		"""
		self.shared.debug_runtime = True
		self.shared.debug_runtime_set = True


	def LinkReleaseRuntime( self ):
		"""
		Link with release runtime
		"""
		self.shared.debug_runtime = False
		self.shared.debug_runtime_set = True


	def SetOutputSubSystem( self, subsystem ):
		"""
		Sets the subsystem to compile against

		:param subsystem: The subsystem to be used to compile
		:type subsystem: A SubSystem enum value
		"""
		self._subsystem = subsystem

