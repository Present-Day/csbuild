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

"""Contains the the vsgen platforms for x64 and Win32."""

import xml.etree.ElementTree as ET

from .platform_base import PlatformBase


_addNode = ET.SubElement


def _writeProjectConfiguration( platformName, parentXmlNode, vsConfigName ):
	includeString = "{}|{}".format( vsConfigName, platformName )

	projectConfigNode = _addNode( parentXmlNode, "ProjectConfiguration" )
	configNode = _addNode( projectConfigNode, "Configuration" )
	platformNode = _addNode( projectConfigNode, "Platform" )

	projectConfigNode.set( "Include", includeString )
	configNode.text = vsConfigName
	platformNode.text = platformName


def _writePropertyGroup( platformName, parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative ):
	propertyGroupNode = _addNode( parentXmlNode, "PropertyGroup" )
	propertyGroupNode.set( "Label", "Configuration")
	propertyGroupNode.set( "Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format( vsConfigName, platformName ) )

	# Required for both native and makefiles projects.  Makefiles projects won't really suffer any ill effects from not having this,
	# but Visual Studio will sometimes annoyingly list each project as being built for another version of Visual Studio.  Adding the
	# correct toolset for the running version of Visual Studio will make that annoyance go away.
	platformToolsetNode = _addNode(propertyGroupNode, "PlatformToolset")
	platformToolsetNode.text = vsPlatformToolsetName

	if isNative:
		#TODO: Add properties for native projects.
		pass
	else:
		configTypeNode = _addNode( propertyGroupNode, "ConfigurationType" )
		configTypeNode.text = "Makefile"


def _writeImportProperties( platformName, parentXmlNode, vsConfigName, isNative ):
	importGroupNode = _addNode( parentXmlNode, "ImportGroup" )
	importGroupNode.set( "Label", "PropertySheets")
	importGroupNode.set( "Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format( vsConfigName, platformName ) )

	importNode = _addNode( importGroupNode, "Import" )
	importNode.set( "Label", "LocalAppDataPlatform" )
	importNode.set( "Project", r"$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" )
	importNode.set( "Condition", "exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" )


def _writeUserDebugPropertyGroup( platformName, parentXmlNode, vsConfigName, projectData ):
		propertyGroupNode = _addNode( parentXmlNode, "PropertyGroup" )
		workingDirNode = _addNode( propertyGroupNode, "LocalDebuggerWorkingDirectory" )
		debuggerTypeNode = _addNode( propertyGroupNode, "LocalDebuggerDebuggerType" )
		debuggerFlavorNode = _addNode( propertyGroupNode, "DebuggerFlavor" )

		propertyGroupNode.set( "Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format( vsConfigName, platformName ) )
		workingDirNode.text = "$(OutDir)"
		debuggerTypeNode.text = "NativeOnly"
		debuggerFlavorNode.text = "WindowsLocalDebugger"


class PlatformWindowsX86( PlatformBase ):
	def __init__( self ):
		PlatformBase.__init__( self )


	@staticmethod
	def GetToolchainName():
		return "msvc-x86"


	@staticmethod
	def GetVisualStudioName():
		return "Win32"


	def WriteTopLevelInfo( self, parentXmlNode ):
		# Nothing to do for Win32.
		pass


	def WriteProjectConfiguration( self, parentXmlNode, vsConfigName ):
		_writeProjectConfiguration( self.GetVisualStudioName(), parentXmlNode, vsConfigName )


	def WritePropertyGroup( self, parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative ):
		_writePropertyGroup( self.GetVisualStudioName(), parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative )


	def WriteImportProperties( self, parentXmlNode, vsConfigName, isNative ):
		_writeImportProperties( self.GetVisualStudioName(), parentXmlNode, vsConfigName, isNative )


	def WriteUserDebugPropertyGroup( self, parentXmlNode, vsConfigName, projectData ):
		_writeUserDebugPropertyGroup( self.GetVisualStudioName(), parentXmlNode, vsConfigName, projectData )



class PlatformWindowsX64( PlatformBase ):
	def __init__( self ):
		PlatformBase.__init__( self )


	@staticmethod
	def GetToolchainName():
		return "msvc-x64"


	@staticmethod
	def GetVisualStudioName():
		return "x64"


	def WriteTopLevelInfo( self, parentXmlNode ):
		# Nothing to do for x64.
		pass


	def WriteProjectConfiguration( self, parentXmlNode, vsConfigName ):
		_writeProjectConfiguration( self.GetVisualStudioName(), parentXmlNode, vsConfigName )


	def WritePropertyGroup( self, parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative ):
		_writePropertyGroup( self.GetVisualStudioName(), parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative )


	def WriteImportProperties( self, parentXmlNode, vsConfigName, isNative ):
		_writeImportProperties( self.GetVisualStudioName(), parentXmlNode, vsConfigName, isNative )


	def WriteUserDebugPropertyGroup(self, parentXmlNode, vsConfigName, projectData ):
		_writeUserDebugPropertyGroup( self.GetVisualStudioName(), parentXmlNode, vsConfigName, projectData )
