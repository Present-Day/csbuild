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

import glob
import platform
import os
import shutil
import subprocess
import sys
import shlex
import re
import platform

from . import toolchain_gcc
from . import log
from . import _shared_globals
import csbuild


class iOSArchitecture:
	DEVICE_ARMV7 = "device-armv7"
	DEVICE_ARM64 = "device-arm64"
	SIMULATOR_I386 = "simulator-i386"


class iOSBase(object):
	def __init__(self):
		self._targetDeviceVersion = "8.1"
		self._targetSimulatorVersion = "8.1"


	def _copyTo(self, other):
		other._targetDeviceVersion = self._targetDeviceVersion
		other._targetSimulatorVersin = self._targetSimulatorVersion


	def GetDefaultArchitecture(self):
		return iOSArchitecture.SIMULATOR_I386


	def GetValidArchitectures(self):
		return [iOSArchitecture.DEVICE_ARMV7, iOSArchitecture.DEVICE_ARM64, iOSArchitecture.SIMULATOR_I386]


	def SetTargetDeviceVersion(self, versionStr):
		self._targetDeviceVersion = versionStr


	def SetTargetSimulatorVersion(self, versionStr):
		self._targetSimulatorVersion = versionStr


	def GetTargetDeviceVersion(self):
		return self._targetDeviceVersion


	def GetTargetSimulatorVersion(self):
		return self._targetSimulatorVersion


	def _getMinVersionArg(self, arch):
		argumentMap = {
			iOSArchitecture.DEVICE_ARMV7: "-miphoneos-version-min={} ".format(self._targetDeviceVersion),
			iOSArchitecture.DEVICE_ARM64: "-miphoneos-version-min={} ".format(self._targetDeviceVersion),
			iOSArchitecture.SIMULATOR_I386: "-mios-simulator-version-min={} ".format(self._targetSimulatorVersion),
		}
		return argumentMap[arch]


	def _getArchitectureArg(self, arch):
		argumentMap = {
			iOSArchitecture.DEVICE_ARMV7: "armv7",
			iOSArchitecture.DEVICE_ARM64: "arm64",
			iOSArchitecture.SIMULATOR_I386: "i386",
		}
		return "-arch {} ".format(argumentMap[arch])


	def _getAugmentedCommand(self, originalCmd, project):
		return "{} {}{}".format(
			originalCmd,
			self._getMinVersionArg(project.outputArchitecture),
			self._getArchitectureArg(project.outputArchitecture),
		)


	def _setSysRoot(self, arch):
		sysRootMap = {
			iOSArchitecture.DEVICE_ARMV7: "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS{}.sdk".format(self._targetDeviceVersion),
			iOSArchitecture.DEVICE_ARM64: "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS{}.sdk".format(self._targetDeviceVersion),
			iOSArchitecture.SIMULATOR_I386: "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator{}.sdk".format(self._targetSimulatorVersion),
		}
		self._sysroot = sysRootMap[arch]


class iOSCompiler(iOSBase, toolchain_gcc.compiler_gcc):
	def __init__(self):
		iOSBase.__init__(self)
		toolchain_gcc.compiler_gcc.__init__(self)

		# iOS requires the Objective-C ABI version to be set when compiling.
		self.SetObjcAbiVersion(2)


	def copy(self):
		ret = toolchain_gcc.compiler_gcc.copy(self)
		iOSBase._copyTo(self, ret)
		return ret


	def _getArchFlag(self, project):
		# iOS builds should not receive the -m32 or -m64 flags when compiling for iOS.
		return ""


	def GetBaseCcCommand( self, project ):
		self._setSysRoot(project.outputArchitecture)
		originalCmd = toolchain_gcc.compiler_gcc.GetBaseCcCommand(self, project)
		return self._getAugmentedCommand(originalCmd, project)


	def GetBaseCxxCommand( self, project ):
		self._setSysRoot(project.outputArchitecture)
		originalCmd = toolchain_gcc.compiler_gcc.GetBaseCxxCommand(self, project)
		return self._getAugmentedCommand(originalCmd, project)



class iOSLinker(iOSBase, toolchain_gcc.linker_gcc):
	def __init__(self):
		iOSBase.__init__(self)
		toolchain_gcc.linker_gcc.__init__(self)


	def copy(self):
		ret = toolchain_gcc.linker_gcc.copy(self)
		iOSBase._copyTo(self, ret)
		return ret


	def _getArchFlag(self, project):
		# iOS builds should not receive the -m32 or -m64 flags when compiling for iOS.
		return ""


	def _getStartGroupFlags(self):
		return ""


	def _getEndGroupFlags(self):
		return ""


	def GetLinkCommand( self, project, outputFile, objList ):
		self._setSysRoot(project.outputArchitecture)
		originalCmd = toolchain_gcc.linker_gcc.GetLinkCommand(self, project, outputFile, objList)
		if not project.type == csbuild.ProjectType.StaticLibrary:
			return self._getAugmentedCommand(originalCmd, project)
		else:
			return originalCmd