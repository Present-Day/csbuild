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

"""Contains the vsgen platform for Tegra-Android."""

import xml.etree.ElementTree as ET

from .platform_base import PlatformBase


_addNode = ET.SubElement


class PlatformTegraAndroid( PlatformBase ):
	def __init__( self ):
		PlatformBase.__init__( self )


	@staticmethod
	def GetToolchainName():
		return "android-armeabi-v7a"


	@staticmethod
	def GetVisualStudioName():
		return "Tegra-Android"


	def WriteTopLevelInfo( self, parentXmlNode ):
		propertyGroupNode = _addNode( parentXmlNode, "PropertyGroup" )
		tegraRevisionNumberNode = _addNode( propertyGroupNode, "NsightTegraProjectRevisionNumber" )

		propertyGroupNode.set( "Label", "NsightTegraProject" )
		tegraRevisionNumberNode.text = "9"


	def WriteProjectConfiguration( self, parentXmlNode, vsConfigName ):
		platformName = self.GetVisualStudioName()
		includeString = "{}|{}".format( vsConfigName, platformName )

		projectConfigNode = _addNode(parentXmlNode, "ProjectConfiguration")
		configNode = _addNode(projectConfigNode, "Configuration")
		platformNode = _addNode(projectConfigNode, "Platform")

		projectConfigNode.set( "Include", includeString )
		configNode.text = vsConfigName
		platformNode.text = platformName


	def WritePropertyGroup( self, parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative ):
		platformName = self.GetVisualStudioName()

		propertyGroupNode = _addNode( parentXmlNode, "PropertyGroup" )
		propertyGroupNode.set( "Label", "Configuration")
		propertyGroupNode.set( "Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format( vsConfigName, platformName ) )

		if isNative:
			#TODO: Add properties for native projects.
			nativeApiNode = _addNode( propertyGroupNode, "AndroidNativeAPI" )
			nativeApiNode.text = "UseTarget"
		else:
			configTypeNode = _addNode( propertyGroupNode, "ConfigurationType" )
			configTypeNode.text = "ExternalBuildSystem"


	def WriteImportProperties( self, parentXmlNode, vsConfigName, isNative ):
		# Nothing to do for Tegra.
		pass


	def WriteUserDebugPropertyGroup( self, parentXmlNode, vsConfigName ):
		propertyGroupNode = _addNode( parentXmlNode, "PropertyGroup" )
		propertyGroupNode.set( "Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format( vsConfigName, self.GetVisualStudioName() ) )
