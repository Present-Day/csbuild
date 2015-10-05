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
Contains a plugin class for interfacing with GCC/Clang on MacOSX.
"""

import platform
import shutil
import sys
import csbuild

from . import _shared_globals
from . import _utils
from . import toolchain_gcc
from .plugin_plist_generator import *


HAS_RUN_XCRUN = False
DEFAULT_OSX_SDK_DIR = None
DEFAULT_OSX_SDK_VERSION = None
DEFAULT_XCODE_ACTIVE_DEV_DIR = None
DEFAULT_XCODE_TOOLCHAIN_DIR = None


class GccDarwinBase( object ):
	def __init__( self ):
		global HAS_RUN_XCRUN
		if not HAS_RUN_XCRUN:
			global DEFAULT_OSX_SDK_DIR
			global DEFAULT_OSX_SDK_VERSION
			global DEFAULT_XCODE_ACTIVE_DEV_DIR
			global DEFAULT_XCODE_TOOLCHAIN_DIR

			# Default the target SDK version to the version of OSX we're currently running on.
			try:
				DEFAULT_OSX_SDK_DIR = subprocess.check_output( ["xcrun", "--sdk", "macosx", "--show-sdk-path"] )
				DEFAULT_OSX_SDK_VERSION = subprocess.check_output( ["xcrun", "--sdk", "macosx", "--show-sdk-version"] )
				DEFAULT_XCODE_ACTIVE_DEV_DIR = subprocess.check_output( ["xcode-select", "-p"] )

				if sys.version_info >= (3, 0):
					DEFAULT_OSX_SDK_DIR = DEFAULT_OSX_SDK_DIR.decode( "utf-8" )
					DEFAULT_OSX_SDK_VERSION = DEFAULT_OSX_SDK_VERSION.decode( "utf-8" )
					DEFAULT_XCODE_ACTIVE_DEV_DIR = DEFAULT_XCODE_ACTIVE_DEV_DIR.decode( "utf-8" )

				DEFAULT_OSX_SDK_DIR = DEFAULT_OSX_SDK_DIR.strip( "\n" )
				DEFAULT_OSX_SDK_VERSION = DEFAULT_OSX_SDK_VERSION.strip( "\n" )
				DEFAULT_XCODE_ACTIVE_DEV_DIR = DEFAULT_XCODE_ACTIVE_DEV_DIR.strip( "\n" )
			except:
				# Otherwise, fallback to a best guess.
				macVersion = platform.mac_ver()[0]
				DEFAULT_OSX_SDK_VERSION = ".".join( macVersion.split( "." )[:2] )
				DEFAULT_OSX_SDK_DIR = "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX{}.sdk".format( DEFAULT_OSX_SDK_VERSION )
				DEFAULT_XCODE_ACTIVE_DEV_DIR = "/Applications/Xcode.app/Contents/Developer"

			DEFAULT_XCODE_TOOLCHAIN_DIR = os.path.join( DEFAULT_XCODE_ACTIVE_DEV_DIR, "Toolchains", "XcodeDefault.xctoolchain" )

			HAS_RUN_XCRUN = True

		self.shared._targetMacVersion = DEFAULT_OSX_SDK_VERSION
		self.shared._sysroot = DEFAULT_OSX_SDK_DIR


	def _copyTo( self, other ):
		other.shared._targetMacVersion = self.shared._targetMacVersion
		other.shared._sysroot = self.shared._sysroot


	def SetTargetMacVersion( self, version ):
		"""
		Set the version of MacOSX to target and the sysroot of the SDK for that version.

		:param version: Version of MacOSX to target. Possible values are "10.9", "10.10", etc.
		:type version: str
		"""
		self.shared._targetMacVersion = version
		self.shared._sysroot = "{}/Platforms/MacOSX.platform/Developer/SDKs/MacOSX{}.sdk".format( DEFAULT_XCODE_ACTIVE_DEV_DIR, self.shared._targetMacVersion )


	def GetTargetMacVersion( self ):
		"""
		Retrieve the target of MacOSX that is being targetted.

		:return: str
		"""
		return self.shared._targetMacVersion


	def _getSysRoot( self ):
		return '-isysroot "{}" '.format( self.shared._sysroot )


class GccCompilerDarwin( GccDarwinBase, toolchain_gcc.GccCompiler ):
	def __init__( self, shared ):
		toolchain_gcc.GccCompiler.__init__( self, shared )
		GccDarwinBase.__init__( self )

		# Force the use of clang for now since that's what is typically used on Mac.
		self._settingsOverrides["cxx"] = "clang++"
		self._settingsOverrides["cc"] = "clang"
		self._settingsOverrides["stdLib"] = "libc++"


	def copy(self, shared):
		ret = toolchain_gcc.GccCompiler.copy( self, shared )
		GccDarwinBase._copyTo( self, ret )
		return ret


	def _getNoCommonFlag( self, project ):
		if project.type == csbuild.ProjectType.SharedLibrary or project.type == csbuild.ProjectType.LoadableModule:
			return "-fno-common "
		else:
			return ""


	def _getIncludeDirs( self, includeDirs ):
		"""Returns a string containing all of the passed include directories, formatted to be passed to gcc/g++."""
		ret = ""
		for inc in includeDirs:
			ret += "-I{} ".format( os.path.abspath( inc ) )
		ret += "-I{}/usr/include ".format( DEFAULT_XCODE_TOOLCHAIN_DIR )
		return ret


	def _getBaseCommand( self, compiler, project, isCpp ):
		ret = toolchain_gcc.GccCompiler._getBaseCommand( self, compiler, project, isCpp )
		ret = "{}{}{} -fobjc-arc ".format(
			ret,
			self._getSysRoot(),
			self._getNoCommonFlag( project ),
		)
		return ret


	def SupportsObjectScraping(self):
		return False


	def GetObjectScraper(self):
		return None


class GccLinkerDarwin( GccDarwinBase, toolchain_gcc.GccLinker ):
	def __init__( self, shared ):
		toolchain_gcc.GccLinker.__init__( self, shared )
		GccDarwinBase.__init__( self )

		self._settingsOverrides["cxx"] = "clang++"
		self._settingsOverrides["cc"] = "clang"


	def copy( self, shared ):
		ret = toolchain_gcc.GccLinker.copy( self, shared )
		GccDarwinBase._copyTo( self, ret )
		return ret


	def InterruptExitCode( self ):
		return 2


	def _getFrameworkDirectories(self, project):
		ret = ""
		for directory in project.frameworkDirs:
			ret += "-F{} ".format(directory)
		return ret


	def _getFrameworks(self, project):
		ret = ""
		for framework in project.frameworks:
			ret += "-framework {} ".format(framework)
		return ret


	def _getSharedLibraryFlag( self, project ):
		flagMap = {
			csbuild.ProjectType.SharedLibrary: "-dynamiclib ",
			csbuild.ProjectType.LoadableModule: "-bundle ",
		}

		return flagMap[project.type] if project.type in flagMap else ""


	def _setupForProject( self, project ):
		self._include_lib64 = False
		self._project_settings = project

		# Only include lib64 if we're on a 64-bit platform and we haven't specified whether to build a 64bit or 32bit
		# binary or if we're explicitly told to build a 64bit binary.
		if project.outputArchitecture == "x64":
			self._include_lib64 = True


	def _getLibraryArg(self, lib):
		for depend in self._project_settings.reconciledLinkDepends:
			dependProj = _shared_globals.projects[depend]
			dependLibName = dependProj.outputName
			splitName = os.path.splitext(dependLibName)[0]
			if splitName == lib or splitName == "lib{}".format( lib ):
				if dependProj.type == csbuild.ProjectType.Application or dependProj.type == csbuild.ProjectType.LoadableModule:
					# Loadable modules and applications should not be linked into the executables. They are only dependencies so they can be copied into the app bundles.
					return ""
				return '"{}" '.format( os.path.join( dependProj.outputDir, dependLibName ) )
		return '"{}" '.format( self._actual_library_names[lib] )


	def _getLibraryDirs( self, libDirs, forLinker ):
		# Libraries are linked with full paths on Mac, so library directories are unnecessary.
		return ""


	def _getStartGroupFlags(self):
		# OSX doesn't support the start/end group flags.
		return ""


	def _getEndGroupFlags(self):
		# OSX doesn't support the start/end group flags.
		return ""

	def _getObjcAbiVersionArg(self):
		return "-Xlinker -objc_abi_version -Xlinker {} ".format( self.shared._objcAbiVersion )


	def GetLinkCommand( self, project, outputFile, objList ):
		ret = toolchain_gcc.GccLinker.GetLinkCommand( self, project, outputFile, objList )
		if project.type != csbuild.ProjectType.StaticLibrary:
			ret = "{}{}{}{} -ObjC ".format(
				ret,
				self._getSysRoot(),
				self._getFrameworkDirectories( project ),
				self._getFrameworks( project ),
			)
		return ret


	def FindLibrary( self, project, library, libraryDirs, force_static, force_shared ):
		self._setupForProject( project )

		for lib_dir in libraryDirs:
			log.LOG_INFO( "Looking for library {} in directory {}...".format( library, lib_dir ) )
			lib_file_path = os.path.join( lib_dir, library )
			libFileStatic = "{}.a".format( lib_file_path )
			libFileDynamic = "{}.dylib".format( lib_file_path )
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
			libFileDynamic = "{}.dylib".format( lib_file_path )
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
			return ""
		elif projectType == csbuild.ProjectType.StaticLibrary:
			return ".a"
		elif projectType == csbuild.ProjectType.SharedLibrary:
			return ".dylib"
		elif projectType == csbuild.ProjectType.LoadableModule:
			return ".bundle"


	def _cleanupOldAppBundle( self, project ):
		# Remove the temporary .app directory if it already exists.
		if os.access( project.tempAppDir, os.F_OK ):
			_utils.DeleteTree( project.tempAppDir )

		# Recreate the temp .app directory and any necessary sub-directories underneath it.
		# This must be a set in case any of these paths point to the same location.
		appDirs = {
			project.tempAppDir,
			self.GetAppBundleRootPath( project.tempAppDir ),
			self.GetAppBundleExePath( project.tempAppDir ),
			self.GetAppBundleResourcePath( project.tempAppDir ),
			self.GetAppBundleFrameworksPath( project.tempAppDir ),
			self.GetAppBundlePlugInsPath( project.tempAppDir ),
			self.GetAppBundleSharedSupportPath( project.tempAppDir ),
		}

		for dirPath in sorted( appDirs ):
			os.makedirs( dirPath )


	def _createNewAppBundle( self, project ):
		log.LOG_BUILD( "Generating {}.app...".format( project.name ) )

		inputExePath = os.path.join( project.outputDir, project.outputName )
		outputExePath = os.path.join( self.GetAppBundleExePath( project.tempAppDir ), project.outputName )

		tempAppDsymDir = "{}.dSYM".format( project.tempAppDir )
		finalAppDsymDir = "{}.dSYM".format( project.finalAppDir )

		# Move this project's just-built application file into the temp .app directory.
		shutil.move( inputExePath, outputExePath )

		# Copy the relevant dependencies into the app bundle.
		for dep in project.reconciledLinkDepends:
			depProj = _shared_globals.projects[dep]
			if depProj.type == csbuild.ProjectType.Application or depProj.type == csbuild.ProjectType.SharedLibrary:
				outPath = self.GetAppBundleExePath( project.tempAppDir )
			elif depProj.type == csbuild.ProjectType.LoadableModule:
				outPath = self.GetAppBundlePlugInsPath( project.tempAppDir )
			else:
				# Don't copy static libraries.
				continue
			libFile = os.path.join( depProj.outputDir, depProj.outputName )
			shutil.copyfile( libFile, os.path.join( outPath, os.path.basename( libFile ) ) )

		dsymCmd = [
			"dsymutil",
			outputExePath,
			"-o", tempAppDsymDir,
		]

		# Run dsymutil to generate the DWARF debug symbols file.
		fd = subprocess.Popen( dsymCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
		( output, errors ) = fd.communicate()

		# Bail out if dsymutil produced any errors.
		if fd.returncode != 0:
			if sys.version_info >= ( 3, 0 ):
				errors = errors.decode( "utf-8" )
			errorList = errors.split( "\n" )
			for error in errorList:
				if error:
					error = error.replace( "error: ", "" )
					log.LOG_ERROR( error )
			return

		# If an existing .app directory exists in the project's output path, remove it.
		if os.access( project.finalAppDir, os.F_OK ):
			_utils.DeleteTree( project.finalAppDir )

		# Remove the existing .app.dSYM if one exists.
		if os.access( finalAppDsymDir, os.F_OK ):
			_utils.DeleteTree( finalAppDsymDir )

		# Move the .app directory into the project's output path.
		shutil.move( project.tempAppDir, project.finalAppDir )
		shutil.move( tempAppDsymDir, finalAppDsymDir )


	def GetAppBundleRootPath( self, appBundlePath ):
		"""
		Get the root directory under the app bundle. All files contained in the bundles must be somewhere under the root directory.

		:param appBundlePath: Path the to the .app directory.
		:type appBundlePath: str

		:return: str
		"""
		return os.path.join( appBundlePath, "Contents" )


	def GetAppBundleExePath( self, appBundlePath ):
		"""
		Get the app bundle directory where application executables are stored.

		:param appBundlePath: Path the to the .app directory.
		:type appBundlePath: str

		:return: str
		"""
		return os.path.join( self.GetAppBundleRootPath( appBundlePath ), "MacOS" )


	def GetAppBundleResourcePath( self, appBundlePath ):
		"""
		Get the app bundle directory where application resources (such as images, NIBs, or localization files) are typically stored.

		:param appBundlePath: Path the to the .app directory.
		:type appBundlePath: str

		:return: str
		"""
		return os.path.join( self.GetAppBundleRootPath( appBundlePath ), "Resources" )


	def GetAppBundleFrameworksPath( self, appBundlePath ):
		"""
		Get the app bundle directory where required application frameworks are stored.  These are private frameworks required
		for the application to work and will override frameworks installed on the running system.

		:param appBundlePath: Path the to the .app directory.
		:type appBundlePath: str

		:return: str
		"""
		return os.path.join( self.GetAppBundleRootPath( appBundlePath ), "Frameworks" )


	def GetAppBundlePlugInsPath( self, appBundlePath ):
		"""
		Get the app bundle directory where loadable modules are typically stored.

		:param appBundlePath: Path the to the .app directory.
		:type appBundlePath: str

		:return: str
		"""
		return os.path.join( self.GetAppBundleRootPath( appBundlePath ), "PlugIns" )


	def GetAppBundleSharedSupportPath( self, appBundlePath ):
		"""
		Get the app bundle directory where support files are typically stored.  These are files that supplement the application
		in some way, but are not required for the application to run.

		:param appBundlePath: Path the to the .app directory.
		:type appBundlePath: str

		:return: str
		"""
		return os.path.join( self.GetAppBundleRootPath( appBundlePath ), "SharedSupport" )


	def postBuildStep( self, project ):
		if project.type != csbuild.ProjectType.Application or not project.plistFile:
			return

		if project.plistFile and isinstance( project.plistFile, PListGenerator ):

			project.tempAppDir = os.path.join( project.csbuildDir, project.activeToolchainName, "{}.app".format( project.name ) )
			project.finalAppDir = os.path.join( project.outputDir, "{}.app".format( project.name ) )

			# Delete the old, temporary .app and all it's contents, then re-create the directories for it.
			self._cleanupOldAppBundle( project )

			# Build the project plist.
			project.plistFile.Output( project, self.GetAppBundleRootPath( project.tempAppDir ) )

			# Create the new .app bundle.
			self._createNewAppBundle( project )
