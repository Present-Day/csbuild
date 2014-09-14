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

@undocumented: X64
@undocumented: X86
@undocumented: HAS_SET_VC_VARS
@undocumented: WINDOWS_SDK_DIR
"""

import os
import platform
import re
import subprocess
import sys

from csbuild import toolchain
from csbuild import _shared_globals
from csbuild import log
import csbuild

### Reference: http://msdn.microsoft.com/en-us/library/f35ctcxw.aspx
import time

X64 = "X64"
X86 = "X86"

HAS_SET_VC_VARS = False
WINDOWS_SDK_DIR = ""


class SubSystem:
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
		self._project_settings = None
		self.debug_runtime = False
		self.debug_runtime_set = False
		self.msvc_version = 100

		self._vc_env_var = ""
		self._toolchain_path = ""
		self._bin_path = ""
		self._include_path = []
		self._lib_path = []
		self._platform_arch = ""
		self._build_64_bit = False

	def copyTo(self, other):
		other._project_settings = self._project_settings
		other.debug_runtime = self.debug_runtime
		other.debug_runtime_set = self.debug_runtime_set
		other.msvc_version = self.msvc_version

		other._vc_env_var = self._vc_env_var
		other._toolchain_path = self._toolchain_path
		other._bin_path = self._bin_path
		other._include_path = list(self._include_path)
		other._lib_path = list(self._lib_path)
		other._platform_arch = self._platform_arch
		other._build_64_bit = self._build_64_bit

	def SetMsvcVersion( self, msvc_version ):
		"""
		Set the MSVC version

		@param msvc_version: The version to compile with
		@type msvc_version: int
		"""
		self.msvc_version = msvc_version

	def GetValidArchitectures(self):
		return ['x86', 'x64']

	def SetupForProject( self, project ):
		platform_architectures = {
			"amd64": X64,
			"x86_64": X64,
			"x86": X86,
			"i386": X86 }

		self._project_settings = project
		self._vc_env_var = r"VS{}COMNTOOLS".format( self.msvc_version )
		self._toolchain_path = os.path.normpath( os.path.join( os.environ[self._vc_env_var], "..", "..", "VC" ) )
		self._bin_path = os.path.join( self._toolchain_path, "bin" )
		self._include_path = [os.path.join( self._toolchain_path, "include" )]
		self._lib_path = [os.path.join( self._toolchain_path, "lib" )]
		self._platform_arch = platform_architectures.get( platform.machine( ).lower( ), X86 )
		self._build_64_bit = False

		# Determine if we need to build for 64-bit.
		if(
			self._platform_arch == X64
			and self._project_settings.outputArchitecture != "x86"
		):
			self._build_64_bit = True
		elif self._project_settings.outputArchitecture == "x64":
			self._build_64_bit = True

		# If we're trying to build for 64-bit, determine the appropriate path for the 64-bit tools based on the machine's architecture.
		if self._build_64_bit:
			#TODO: Switch the assembler to ml64.exe when assemblers are supported.
			self._bin_path = os.path.join( self._bin_path, "amd64" if self._platform_arch == X64 else "x86_amd64" )
			self._lib_path[0] = os.path.join( self._lib_path[0], "amd64" )

		global HAS_SET_VC_VARS
		global WINDOWS_SDK_DIR
		if not HAS_SET_VC_VARS:

			batch_file_path = os.path.join( self._toolchain_path, "vcvarsall.bat" )
			fd = subprocess.Popen( '"{}" {} & set'.format( batch_file_path, "x64" if self._build_64_bit else "x86" ),
				stdout = subprocess.PIPE, stderr = subprocess.PIPE )

			if sys.version_info >= (3, 0):
				(output, errors) = fd.communicate( str.encode("utf-8") )
			else:
				(output, errors) = fd.communicate( )

			output_lines = output.splitlines( )

			for line in output_lines:
				# Convert to a string on Python3.
				if sys.version_info >= (3, 0):
					line = line.decode("utf-8")

				key_value_list = line.split( "=", 1 )

				# Only accept lines that contain key/value pairs.
				if len( key_value_list ) == 2:
					os.environ[key_value_list[0]] = key_value_list[1]

					# Check if the line we're on has the Windows SDK directory listed.
					if key_value_list[0] == "WindowsSdkDir":
						WINDOWS_SDK_DIR = key_value_list[1]

			HAS_SET_VC_VARS = True

		sdkInclude = os.path.join( WINDOWS_SDK_DIR, "include" )
		self._include_path.append( sdkInclude )
		includeShared = os.path.join( sdkInclude, "Shared" )
		includeUm = os.path.join( sdkInclude, "um" )
		includeWinRT = os.path.join( sdkInclude, "WinRT" )

		if os.access(includeShared, os.F_OK):
			self._include_path.append(includeShared)
		if os.access(includeUm, os.F_OK):
			self._include_path.append(includeUm)
		if os.access(includeWinRT, os.F_OK):
			self._include_path.append(includeWinRT)

		libPath = os.path.join( WINDOWS_SDK_DIR, "lib", "x64" if self._build_64_bit else "" )
		sdk8path = os.path.join( WINDOWS_SDK_DIR, "lib", "win8", "um", "x64" if self._build_64_bit else "x86" )

		if os.access(sdk8path, os.F_OK):
			self._lib_path.append( sdk8path )
		else:
			self._lib_path.append( libPath )


	def interrupt_exit_code( self ):
		return -1


	def _get_runtime_linkage_arg( self ):
		return "/{}{} ".format(
			"MT" if self._project_settings.static_runtime else "MD",
			"d" if self.debug_runtime else "" )


	def parseOutput(self, outputStr):
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



class compiler_msvc( MsvcBase, toolchain.compilerBase ):
	def __init__( self ):
		MsvcBase.__init__( self )
		toolchain.compilerBase.__init__( self )

	def copy(self):
		ret = toolchain.compilerBase.copy(self)
		MsvcBase.copyTo(self, ret)
		return ret

	### Private methods ###

	def _get_compiler_exe( self ):
		return '"{}" '.format( os.path.join( self._bin_path, "cl" ) )

	def _get_default_compiler_args( self ):
		return "/nologo /c "

	def _get_debug_arg(self):
		debugLevel = self._project_settings.debug_level
		if debugLevel == csbuild.DebugLevel.EmbeddedSymbols:
			return "/Z7 "
		if debugLevel == csbuild.DebugLevel.ExternalSymbols:
			return "/Zi "
		if debugLevel == csbuild.DebugLevel.ExternalSymbolsPlus:
			return "/ZI "
		return " "

	def _get_opt_arg(self):
		optLevel = self._project_settings.opt_level
		if optLevel == csbuild.OptimizationLevel.Max:
			return "/Ox "
		if optLevel == csbuild.OptimizationLevel.Speed:
			return "/O2 "
		if optLevel == csbuild.OptimizationLevel.Size:
			return "/O1 "
		return "/Od "

	def _get_compiler_args( self ):
		return "{}{}{}{}{}{}{}/Oi /GS {} ".format(
			self._get_default_compiler_args( ),
			self._get_preprocessor_definition_args( ),
			self._get_runtime_linkage_arg( ),
			self._get_warning_args( ),
			self._get_include_directory_args( ),
			self._get_debug_arg( ),
			self._get_opt_arg( ),
			"/RTC1" if self._project_settings.opt_level == csbuild.OptimizationLevel.Disabled else ""
		)


	def _get_preprocessor_definition_args( self ):
		define_args = ""

		# Add the defines.
		for define_name in self._project_settings.defines:
			define_args += "/D{} ".format( define_name )

		# Add the undefines.
		for define_name in self._project_settings.undefines:
			define_args += "/U{} ".format( define_name )

		return define_args

	### Public methods ###

	def getCompilerCommand( self, isCpp ):
		return "{}{}{}".format(
			self._get_compiler_exe( ),
			self._get_compiler_args( ),
			" ".join( self._project_settings.cpp_compiler_flags ) if isCpp else " ".join(
				self._project_settings.c_compiler_flags ) )


	def getExtendedCompilerArgs( self, base_cmd, force_include_file, output_obj, input_file ):
		pch = self.get_pch_file( force_include_file )
		if os.access(pch , os.F_OK):
			pch = '/Fp"{0}"'.format( pch )
		else:
			pch = ""

		return '{} /Fo"{}" /Fd"{}" /Gm- /errorReport:none "{}" {} {} {} {}'.format(
			base_cmd,
			output_obj,
			os.path.join(self._project_settings.output_dir, "{}.pdb".format(self._project_settings.output_name.rsplit('.', 1)[0])),
			input_file,
			'/FI"{}"'.format( force_include_file ) if force_include_file else "",
			'/Yu"{}"'.format( force_include_file ) if force_include_file else "",
			"/FS" if self.msvc_version >= 120 else "",
			pch )

	def preLinkStep(self, project):
		if project.cheaderfile:
			self._project_settings.extraObjs.append("{}.obj".format(project.cheaderfile.rsplit(".", 1)[0]))
		if project.cppheaderfile:
			self._project_settings.extraObjs.append("{}.obj".format(project.cppheaderfile.rsplit(".", 1)[0]))

	def getExtendedPrecompilerArgs( self, base_cmd, force_include_file, output_obj, input_file ):
		split = input_file.rsplit(".", 1)
		#This is safe to do because csbuild always creates C++ precompiled headers with a .hpp extension.
		srcFile = os.path.join("{}.{}".format(split[0], "c" if split[1] == "h" else "cpp"))
		file_mode = 438 # Octal 0666
		fd = os.open(srcFile, os.O_WRONLY | os.O_CREAT | os.O_NOINHERIT, file_mode)
		data = "#include \"{}\"\n".format(input_file)
		if sys.version_info >= (3, 0):
			data = data.encode("utf-8")
		os.write(fd, data)
		os.fsync(fd)
		os.close(fd)

		objFile = "{}.obj".format(split[0])

		return '{} /Yc"{}" /Gm- /errorReport:none /Fp"{}" /FI"{}" /Fo"{}" /Fd"{}" "{}"'.format(
			base_cmd,
			input_file,
			output_obj,
			input_file,
			objFile,
			os.path.join(self._project_settings.output_dir, "{}.pdb".format(self._project_settings.output_name.rsplit('.', 1)[0])),
			srcFile )


	def _get_warning_args( self ):
		#TODO: Support additional warning options.
		if self._project_settings.no_warnings:
			return "/w "
		elif self._project_settings.warnings_as_errors:
			return "/WX "

		return ""


	def _get_include_directory_args( self ):
		include_dir_args = ""

		for inc_dir in self._project_settings.include_dirs:
			include_dir_args += '/I"{}" '.format( os.path.normpath( inc_dir ) )

		# The default include paths should be added last so that any paths set by the user get searched first.
		for inc_dir in self._include_path:
			include_dir_args += '/I"{}" '.format( inc_dir )

		return include_dir_args


	def get_base_cxx_command( self, project ):
		self.SetupForProject( project )
		return self.getCompilerCommand( True )


	def get_base_cc_command( self, project ):
		self.SetupForProject( project )
		return self.getCompilerCommand( False )


	def get_extended_command( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		self.SetupForProject( project )
		return self.getExtendedCompilerArgs( baseCmd, forceIncludeFile, outObj, inFile )


	def get_base_cxx_precompile_command( self, project ):
		self.SetupForProject( project )
		return self.get_base_cxx_command( project )


	def get_base_cc_precompile_command( self, project ):
		self.SetupForProject( project )
		return self.get_base_cc_command( project )


	def get_extended_precompile_command( self, baseCmd, project, forceIncludeFile, outObj, inFile ):
		self.SetupForProject( project )
		return self.getExtendedPrecompilerArgs( baseCmd, forceIncludeFile, outObj, inFile )


	def get_preprocess_command(self, baseCmd, project, inFile ):
		return "{} /E /wd\"4005\" \"{}\"".format(baseCmd, inFile)


	def pragma_message(self, message):
		return "#pragma message(\"{}\")".format(message)


	def get_obj_ext(self):
		return ".obj"


	def get_pch_file( self, fileName ):
		return fileName.rsplit( ".", 1 )[0] + ".pch"

class linker_msvc( MsvcBase, toolchain.linkerBase ):
	def __init__( self ):
		MsvcBase.__init__( self )
		toolchain.linkerBase.__init__( self )
		self._subsystem = SubSystem.DEFAULT

		self._actual_library_names = { }

	def copy(self):
		ret = toolchain.linkerBase.copy(self)
		MsvcBase.copyTo(self, ret)

		ret._subsystem = self._subsystem
		ret._actual_library_names = dict(self._actual_library_names)
		return ret

	### Private methods ###

	def _get_linker_exe( self ):
		return '"{}" '.format( os.path.join( self._bin_path,
			"lib" if self._project_settings.type == csbuild.ProjectType.StaticLibrary else "link" ) )

	def _get_default_linker_args( self ):
		default_args = "/NOLOGO "
		for lib_path in self._lib_path:
			default_args += '/LIBPATH:"{}" '.format( lib_path.strip("\\") )
		return default_args


	def _get_non_static_library_linker_args( self ):
		# The following arguments should only be specified for dynamic libraries and executables (being used with link.exe, not lib.exe).
		return "" if self._project_settings.type == csbuild.ProjectType.StaticLibrary else "{}{}{}{}".format(
			self._get_runtime_library_arg( ),
			"/PROFILE " if self._project_settings.profile else "",
			"/DEBUG " if self._project_settings.profile or self._project_settings.debug_level != csbuild.DebugLevel.Disabled else "",
			"/DLL " if self._project_settings.type == csbuild.ProjectType.SharedLibrary else "" )


	def _get_linker_args( self, output_file, obj_list ):
		return "/ERRORREPORT:NONE {}{}{}{}{}{}{}{}{}{}".format(
			self._get_default_linker_args( ),
			self._get_import_library_arg(output_file),
			self._get_non_static_library_linker_args( ),
			self._get_subsystem_arg( ),
			self._get_architecture_arg( ),
			self._get_linker_warning_arg( ),
			self._get_library_directory_args( ),
			self._get_linker_output_arg( output_file ),
			self._get_library_args( ),
			self._get_linker_obj_file_args( obj_list ) )


	def _get_architecture_arg( self ):
		#TODO: This will need to change to support other machine architectures.
		return "/MACHINE:{} ".format( "X64" if self._build_64_bit else "X86" )


	def _get_runtime_library_arg( self ):
		return '/DEFAULTLIB:{}{}.lib '.format(
			"libcmt" if self._project_settings.static_runtime else "msvcrt",
			"d" if self.debug_runtime else "" )


	def _get_import_library_arg(self, output_file):
		if self._project_settings.type == csbuild.ProjectType.SharedLibrary:
			return '/IMPLIB:"{}" '.format(os.path.splitext(output_file)[0] + ".lib")
		else:
			return ''


	def _get_subsystem_arg( self ):
		# The default subsystem is implied, so it has no explicit argument.
		# When no argument is specified, the linker will assume a default subsystem which depends on a number of factors:
		#   CONSOLE -> Either main or wmain are defined (or int main(array<String^>^) for managed code).
		#   WINDOWS -> Either WinMain or wWinMain are defined (or WinMain(HINSTANCE*, HINSTANCE*, char*, int) or wWinMain(HINSTANCE*, HINSTANCE*, wchar_t*, int) for managed code).
		#   NATIVE -> The /DRIVER:WDM argument is specified (currently unsupported).
		if self._subsystem == SubSystem.DEFAULT:
			return ''

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
			SubSystem.EFI_RUNTIME_DRIVER: "EFI_RUNTIME_DRIVER" }

		return "/SUBSYSTEM:{} ".format( sub_system_type[self._subsystem] )


	def _get_library_args( self ):
		# Static libraries don't require any libraries to be linked.
		if self._project_settings.type == csbuild.ProjectType.StaticLibrary:
			args = ''
		else:
			args = '"kernel32.lib" "user32.lib" "gdi32.lib" "winspool.lib" "comdlg32.lib" "advapi32.lib" "shell32.lib" "ole32.lib" "oleaut32.lib" "uuid.lib" "odbc32.lib" "odbccp32.lib" '

		for lib in (
			self._project_settings.libraries |
			self._project_settings.static_libraries |
			self._project_settings.shared_libraries
		):
			found = False
			for depend in self._project_settings.reconciledLinkDepends:
				dependProj = _shared_globals.projects[depend]
				if dependProj.type == csbuild.ProjectType.Application:
					continue
				dependLibName = dependProj.output_name
				splitName = os.path.splitext(dependLibName)[0]
				if ( splitName == lib or splitName == "lib{}".format( lib ) ):
					found = True
					args += '"{}" '.format( dependLibName )
					break
			if not found:
				args += '"{}" '.format( self._actual_library_names[lib] )

		return args


	def _get_linker_warning_arg( self ):
		# When linking, the only warning argument supported is whether or not to treat warnings as errors.
		return "/WX{} ".format( "" if self._project_settings.warnings_as_errors else ":NO" )


	def _get_library_directory_args( self ):
		library_dir_args = ""

		for lib_dir in self._project_settings.library_dirs:
			library_dir_args += '/LIBPATH:"{}" '.format( os.path.normpath( lib_dir ) )

		return library_dir_args


	def _get_linker_output_arg( self, output_file ):
		return '/OUT:"{}" '.format( output_file )


	def _get_linker_obj_file_args( self, obj_file_list ):
		args = ""
		for obj_file in obj_file_list:
			args += '"{}" '.format( obj_file )

		return args


	### Public methods ###


	def getLinkerCommand( self, output_file, obj_list ):
		return "{}{}{}{}".format(
			self._get_linker_exe( ),
			"/NXCOMPAT /DYNAMICBASE " if self._project_settings.type != csbuild.ProjectType.StaticLibrary else "",
			self._get_linker_args( output_file, obj_list ),
			" ".join( self._project_settings.linker_flags ) )


	### Required functions ###

	def find_library( self, project, library, library_dirs, force_static, force_shared ):
		self.SetupForProject(project)
		libfile = "{}.lib".format( library )

		for lib_dir in self._lib_path:
			log.LOG_INFO("Looking for library {} in directory {}...".format(libfile, lib_dir))
			lib_file_path = os.path.join( lib_dir, libfile )
			# Do a simple check to see if the file exists.
			if os.access(lib_file_path , os.F_OK):
				self._actual_library_names.update( { library : libfile } )
				return lib_file_path

		for lib_dir in library_dirs:
			log.LOG_INFO("Looking for library {} in directory {}...".format(libfile, lib_dir))
			lib_file_path = os.path.join( lib_dir, libfile )
			# Do a simple check to see if the file exists.
			if os.access(lib_file_path , os.F_OK):
				self._actual_library_names.update( { library : libfile } )
				return lib_file_path

		for lib_dir in library_dirs:
			#Compatibility with Linux's way of adding lib- to the front of its libraries
			libfileCompat = "lib{}".format( libfile )
			log.LOG_INFO("Looking for library {} in directory {}...".format(libfileCompat, lib_dir))
			lib_file_path = os.path.join( lib_dir, libfileCompat )
			if os.access(lib_file_path , os.F_OK):
				self._actual_library_names.update( { library : libfileCompat } )
				return lib_file_path

		# The library wasn't found.
		return None


	def get_link_command( self, project, outputFile, objList ):
		self.SetupForProject( project )
		return self.getLinkerCommand( outputFile, objList )


	def get_default_extension( self, projectType ):
		if projectType == csbuild.ProjectType.Application:
			return ".exe"
		elif projectType == csbuild.ProjectType.StaticLibrary:
			return ".lib"
		elif projectType == csbuild.ProjectType.SharedLibrary:
			return ".dll"


	def DebugRuntime( self ):
		"""
		Link with debug runtime
		"""
		self.debug_runtime = True
		self.debug_runtime_set = True


	def ReleaseRuntime( self ):
		"""
		Link with release runtime
		"""
		self.debug_runtime = False
		self.debug_runtime_set = True


	def SetOutputSubSystem( self, subsystem ):
		"""
		Sets the subsystem to compile against

		@param subsystem: The subsystem to be used to compile
		@type subsystem: A SubSystem enum value
		"""
		self._subsystem = subsystem

