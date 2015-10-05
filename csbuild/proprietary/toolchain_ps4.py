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
Contains a plugin class for interfacing with Clang for PS4.
"""

import csbuild

from .. import _shared_globals
from .. import toolchain_gcc
from ..plugin_plist_generator import *


SCE_ORBIS_SDK_DIR = os.environ.get( "SCE_ORBIS_SDK_DIR", "" )
SCE_ORBIS_SYSLIB_DIR = os.path.join( SCE_ORBIS_SDK_DIR, "target", "lib" )


class Ps4Base( object ):
	def __init__( self ):
		pass


	def GetValidArchitectures( self ):
		return ["x64"]


	def GetDefaultArchitecture(self):
		return "x64"


	def _copyTo( self, other ):
		pass


	def _getSysRoot( self ):
		# PS4 does not set the sysroot.
		return ""


	def _getStandardLibraryArg( self, project ):
		# PS4 does not set the standard library.
		return ""


class Ps4Compiler( Ps4Base, toolchain_gcc.GccCompiler ):
	def __init__( self, shared ):
		toolchain_gcc.GccCompiler.__init__( self, shared )
		Ps4Base.__init__( self )

		self._settingsOverrides["cxx"] = os.path.join( SCE_ORBIS_SDK_DIR, "host_tools", "bin", "orbis-clang++.exe" )
		self._settingsOverrides["cc"] = os.path.join( SCE_ORBIS_SDK_DIR, "host_tools", "bin", "orbis-clang.exe" )


	def copy(self, shared):
		ret = toolchain_gcc.GccCompiler.copy( self, shared )
		Ps4Base._copyTo( self, ret )
		return ret


	def _getIncludeDirs( self, includeDirs ):
		"""Returns a string containing all of the passed include directories, formatted to be passed to gcc/g++."""
		ret = ""
		for inc in includeDirs:
			ret += '-I"{}" '.format( os.path.abspath( inc ) )
		ret += '-I"{}" -I"{}" '.format( os.path.join( SCE_ORBIS_SDK_DIR, "target", "include" ), os.path.join( SCE_ORBIS_SDK_DIR, "target", "include_common" ) )
		return ret


	def _getBaseCommand( self, compiler, project, isCpp ):
		ret = toolchain_gcc.GccCompiler._getBaseCommand( self, compiler, project, isCpp )
		ret = "{}".format( ret )
		return ret


	def SupportsObjectScraping(self):
		return False


	def GetObjectScraper(self):
		return None


class Ps4Linker( Ps4Base, toolchain_gcc.GccLinker ):
	def __init__( self, shared ):
		toolchain_gcc.GccLinker.__init__( self, shared )
		Ps4Base.__init__( self )

		self._ar = os.path.join( SCE_ORBIS_SDK_DIR, "host_tools", "bin", "orbis-ar.exe" )

		self._settingsOverrides["cxx"] = os.path.join( SCE_ORBIS_SDK_DIR, "host_tools", "bin", "orbis-clang++.exe" )
		self._settingsOverrides["cc"] = os.path.join( SCE_ORBIS_SDK_DIR, "host_tools", "bin", "orbis-clang.exe" )


	def copy( self, shared ):
		ret = toolchain_gcc.GccLinker.copy( self, shared )
		Ps4Base._copyTo( self, ret )
		return ret


	def InterruptExitCode( self ):
		return 2


	def _getLibraryDirs( self, libDirs, forLinker ):
		# No library directories necessary since all libraries are linked with full paths.
		return ""


	def _getStartGroupFlags( self ):
		return "-Wl,--start-group"


	def _getSharedLibraryFlag( self, project ):
		# PS4 has no explicit "shared" flag.
		return ""


	def _setupForProject( self, project ):
		self._project_settings = project
		if not SCE_ORBIS_SDK_DIR:
			log.LOG_ERROR( "No PS4 SDK installation detected!" )
			csbuild.Exit( -1 )


	def _getLibraryArg(self, lib):
		for depend in self._project_settings.reconciledLinkDepends:
			dependProj = _shared_globals.projects[depend]
			dependLibName = dependProj.outputName
			splitName = os.path.splitext(dependLibName)[0]
			if splitName == lib or splitName == "lib{}".format( lib ):
				if dependProj.type == csbuild.ProjectType.LoadableModule:
					return ""
				if not dependLibName.startswith( "lib" ):
					dependLibName = "lib{}".format( dependLibName )
				return '"{}" '.format( os.path.join( dependProj.outputDir, dependLibName ) )
		return '"{}" '.format( self._actual_library_names[lib] )


	def _getObjcAbiVersionArg(self):
		# Objective-C is not supported on PS4.
		return ""


	def GetLinkCommand( self, project, outputFile, objList ):
		# The PS4 linker does not implicitly prepend libraries with "lib", but it does seem to want them that way
		# when linking against them via "-l". The easy answer is to force all libraries to be prepended with "lib".
		if project.type != csbuild.ProjectType.Application:
			outputBasename = os.path.basename( outputFile )
			if not outputBasename.startswith( "lib" ):
				outputDirname = os.path.dirname( outputFile )
				outputFile = os.path.join( outputDirname, "lib{}".format( outputBasename ) )
		ret = toolchain_gcc.GccLinker.GetLinkCommand( self, project, outputFile, objList )
		if project.type == csbuild.ProjectType.SharedLibrary or project.type == csbuild.ProjectType.LoadableModule:
			ret = '{} -Wl,-oformat=prx -Wl,-prx-stub-output-dir="{}"'.format( ret, project.outputDir )
		return ret


	def FindLibrary( self, project, library, libraryDirs, force_static, force_shared ):
		self._setupForProject( project )
		libraryDirs.append( SCE_ORBIS_SYSLIB_DIR )

		for lib_dir in libraryDirs:
			log.LOG_INFO( "Looking for library {} in directory {}...".format( library, lib_dir ) )
			lib_file_path = os.path.join( lib_dir, library )
			libFileStatic = "{}.a".format( lib_file_path )
			libFileDynamic = "{}.prx".format( lib_file_path )
			# Check for a static lib.
			if os.access( libFileStatic , os.F_OK ) and not force_shared:
				self._actual_library_names.update( { library : libFileStatic } )
				return libFileStatic
			# Check for a dynamic lib.
			if os.access( libFileDynamic , os.F_OK ) and not force_static:
				self._actual_library_names.update( { library : libFileDynamic } )
				return libFileDynamic

		for lib_dir in libraryDirs:
			# Compatibility with Linux's way of adding lib- to the front of its libraries
			libfileCompat = "lib{}".format( library )
			log.LOG_INFO( "Looking for library {} in directory {}...".format( libfileCompat, lib_dir ) )
			lib_file_path = os.path.join( lib_dir, libfileCompat )
			libFileStatic = "{}.a".format( lib_file_path )
			libFileDynamic = "{}.prx".format( lib_file_path )
			# Check for a static lib.
			if os.access( libFileStatic , os.F_OK ) and not force_shared:
				self._actual_library_names.update( { library : libFileStatic } )
				return libFileStatic
			# Check for a dynamic lib.
			if os.access( libFileDynamic , os.F_OK ) and not force_static:
				self._actual_library_names.update( { library : libFileDynamic } )
				return libFileDynamic

		# The library wasn't found.
		return None


	def GetDefaultOutputExtension( self, projectType ):
		if projectType == csbuild.ProjectType.Application:
			return ".elf"
		elif projectType == csbuild.ProjectType.StaticLibrary:
			return ".a"
		elif projectType == csbuild.ProjectType.SharedLibrary or projectType == csbuild.ProjectType.LoadableModule:
			return ".prx"
