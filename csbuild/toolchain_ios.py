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
Contains a plugin class for building iOS projects.
"""

import csbuild
import subprocess
import sys

from . import toolchain_gcc
from . import toolchain_gcc_darwin


HAS_RUN_XCRUN = False
DEFAULT_DEVICE_SDK_DIR = None
DEFAULT_SIMULATOR_SDK_DIR = None
DEFAULT_DEVICE_SDK_VERSION = None
DEFAULT_SIMULATOR_SDK_VERSION = None


class iOSArchitecture( object ):
	DEVICE_ARMV7 =   "device-armv7"
	DEVICE_ARM64 =   "device-arm64"
	SIMULATOR_I386 = "simulator-i386"
	SIMULATOR_X64 =  "simulator-x64"


class iOSBase( object ):
	def __init__( self ):
		global HAS_RUN_XCRUN
		if not HAS_RUN_XCRUN:
			global DEFAULT_DEVICE_SDK_DIR
			global DEFAULT_SIMULATOR_SDK_DIR
			global DEFAULT_DEVICE_SDK_VERSION
			global DEFAULT_SIMULATOR_SDK_VERSION

			try:
				DEFAULT_DEVICE_SDK_DIR = subprocess.check_output(["xcrun", "--sdk", "iphoneos", "--show-sdk-path"])
				DEFAULT_SIMULATOR_SDK_DIR = subprocess.check_output(["xcrun", "--sdk", "iphonesimulator", "--show-sdk-path"])
			except:
				DEFAULT_DEVICE_SDK_DIR = "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk"
				DEFAULT_SIMULATOR_SDK_DIR = "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator.sdk"

			try:
				DEFAULT_DEVICE_SDK_VERSION = subprocess.check_output(["xcrun", "--sdk", "iphoneos", "--show-sdk-version"])
				DEFAULT_SIMULATOR_SDK_VERSION = subprocess.check_output(["xcrun", "--sdk", "iphonesimulator", "--show-sdk-version"])
			except:
				DEFAULT_DEVICE_SDK_VERSION = ""
				DEFAULT_SIMULATOR_SDK_VERSION = ""

			if sys.version_info >= (3, 0):
				DEFAULT_DEVICE_SDK_DIR = DEFAULT_DEVICE_SDK_DIR.decode("utf-8")
				DEFAULT_SIMULATOR_SDK_DIR = DEFAULT_SIMULATOR_SDK_DIR.decode("utf-8")
				DEFAULT_DEVICE_SDK_VERSION = DEFAULT_DEVICE_SDK_VERSION.decode("utf-8")
				DEFAULT_SIMULATOR_SDK_VERSION = DEFAULT_SIMULATOR_SDK_VERSION.decode("utf-8")

			DEFAULT_DEVICE_SDK_DIR = DEFAULT_DEVICE_SDK_DIR.strip("\n")
			DEFAULT_SIMULATOR_SDK_DIR = DEFAULT_SIMULATOR_SDK_DIR.strip("\n")
			DEFAULT_DEVICE_SDK_VERSION = DEFAULT_DEVICE_SDK_VERSION.strip("\n")
			DEFAULT_SIMULATOR_SDK_VERSION = DEFAULT_SIMULATOR_SDK_VERSION.strip("\n")

			HAS_RUN_XCRUN = True

		self.shared._deviceSdkDir = DEFAULT_DEVICE_SDK_DIR
		self.shared._simulatorSdkDir = DEFAULT_SIMULATOR_SDK_DIR
		self.shared._targetDeviceVersion = DEFAULT_DEVICE_SDK_VERSION
		self.shared._targetSimulatorVersion = DEFAULT_SIMULATOR_SDK_VERSION


	def _copyTo( self, other ):
		other.shared._deviceSdkDir = self.shared._deviceSdkDir
		other.shared._simulatorSdkDir = self.shared._simulatorSdkDir
		other.shared._targetDeviceVersion = self.shared._targetDeviceVersion
		other.shared._targetSimulatorVersin = self.shared._targetSimulatorVersion


	def GetDefaultArchitecture( self ) :
		return iOSArchitecture.SIMULATOR_X64


	def GetValidArchitectures( self ):
		return [iOSArchitecture.DEVICE_ARMV7, iOSArchitecture.DEVICE_ARM64, iOSArchitecture.SIMULATOR_I386, iOSArchitecture.SIMULATOR_X64]


	def SetTargetDeviceVersion( self, version ):
		"""
		Set the target device version to compile against.

		:param version: Target device version.
		:type version: str
		"""
		self.shared._deviceSdkDir = "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS{}.sdk".format( version )
		self.shared._targetDeviceVersion = version


	def SetTargetSimulatorVersion( self, version ):
		"""
		Set the target simulator version to compile against.

		:param version: Target simulator version.
		:type version: str
		"""
		self.shared._simulatorSdkDir = "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator{}.sdk".format( version )
		self.shared._targetSimulatorVersion = version


	def GetTargetDeviceVersion( self ):
		return self.shared._targetDeviceVersion


	def GetTargetSimulatorVersion( self ):
		return self.shared._targetSimulatorVersion


	def _getMinVersionArg( self, arch ):
		argumentMap = {
			iOSArchitecture.DEVICE_ARMV7:   "-miphoneos-version-min={} ".format( self.shared._targetDeviceVersion ) if self.shared._targetDeviceVersion else "",
			iOSArchitecture.DEVICE_ARM64:   "-miphoneos-version-min={} ".format( self.shared._targetDeviceVersion ) if self.shared._targetDeviceVersion else "",
			iOSArchitecture.SIMULATOR_I386: "-mios-simulator-version-min={} ".format( self.shared._targetSimulatorVersion ) if self.shared._targetSimulatorVersin else "",
			iOSArchitecture.SIMULATOR_X64:  "-mios-simulator-version-min={} ".format( self.shared._targetSimulatorVersion ) if self.shared._targetSimulatorVersin else "",
		}
		return argumentMap[arch]


	def _getArchitectureArg( self, arch ):
		argumentMap = {
			iOSArchitecture.DEVICE_ARMV7:   "armv7",
			iOSArchitecture.DEVICE_ARM64:   "arm64",
			iOSArchitecture.SIMULATOR_I386: "i386",
			iOSArchitecture.SIMULATOR_X64:  "x86_64",
		}
		return "-arch {} ".format( argumentMap[arch] )


	def _getAugmentedCommand( self, originalCmd, project ):
		return "{} {}{}".format(
			originalCmd,
			self._getMinVersionArg( project.outputArchitecture ),
			self._getArchitectureArg( project.outputArchitecture ),
		)


	def _setSysRoot( self, arch ):
		sysRootMap = {
			iOSArchitecture.DEVICE_ARMV7:   self.shared._deviceSdkDir,
			iOSArchitecture.DEVICE_ARM64:   self.shared._deviceSdkDir,
			iOSArchitecture.SIMULATOR_I386: self.shared._simulatorSdkDir,
			iOSArchitecture.SIMULATOR_X64:  self.shared._simulatorSdkDir,
		}
		self.shared._sysroot = sysRootMap[arch]


class iOSCompiler( iOSBase, toolchain_gcc_darwin.GccCompilerDarwin ):
	def __init__( self, shared ):
		toolchain_gcc_darwin.GccCompilerDarwin.__init__( self, shared )
		iOSBase.__init__( self )


	def copy( self, shared ):
		ret = toolchain_gcc_darwin.GccCompilerDarwin.copy( self, shared )
		iOSBase._copyTo( self, ret )
		return ret


	def _getArchFlag( self, project ):
		# iOS builds should not receive the -m32 or -m64 flags when compiling for iOS.
		return ""


	def _getBaseCommand( self, compiler, project, isCpp ):
		return "{} ".format( toolchain_gcc_darwin.GccCompilerDarwin._getBaseCommand( self, compiler, project, isCpp ) )


	def GetBaseCcCommand( self, project ):
		self._setSysRoot( project.outputArchitecture )
		originalCmd = toolchain_gcc.GccCompiler.GetBaseCcCommand( self, project )
		return self._getAugmentedCommand( originalCmd, project )


	def GetBaseCxxCommand( self, project ):
		self._setSysRoot( project.outputArchitecture )
		originalCmd = toolchain_gcc.GccCompiler.GetBaseCxxCommand( self, project )
		return self._getAugmentedCommand( originalCmd, project )


class iOSLinker( iOSBase, toolchain_gcc_darwin.GccLinkerDarwin ):
	def __init__( self, shared ):
		toolchain_gcc_darwin.GccLinkerDarwin.__init__( self, shared )
		iOSBase.__init__( self )


	def copy( self, shared ):
		ret = toolchain_gcc_darwin.GccLinkerDarwin.copy( self, shared )
		iOSBase._copyTo( self, ret )
		return ret


	def _getArchFlag( self, project ):
		# iOS builds should not receive the -m32 or -m64 flags.
		return ""


	def GetLinkCommand( self, project, outputFile, objList ):
		self._setSysRoot( project.outputArchitecture )
		originalCmd = toolchain_gcc_darwin.GccLinkerDarwin.GetLinkCommand( self, project, outputFile, objList )
		if project.type != csbuild.ProjectType.StaticLibrary:
			ret =  "{} -Xlinker -no_implicit_dylibs ".format( self._getAugmentedCommand( originalCmd, project ) )
		else:
			ret = originalCmd
		return ret
