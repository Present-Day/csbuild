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

"""Contains the vsgen platform for WiiU."""

import os
import csbuild
import xml.etree.ElementTree as ET

from ...proprietary import toolchain_wiiu
from ...vsgen.platform_base import PlatformBase


_addNode = ET.SubElement


class PlatformWiiU( PlatformBase ):
	def __init__( self ):
		PlatformBase.__init__( self )


	@staticmethod
	def GetToolchainName():
		return "wiiu-ppc"


	@staticmethod
	def GetVisualStudioName():
		return "Cafe"


	def WriteGlobalHeader( self, parentXmlNode ):
		# Nothing special to do for WiiU.
		pass


	def WriteGlobalFooter( self, parentXmlNode ):
		# Nothing to do for WiiU.
		pass


	def WriteProjectConfiguration( self, parentXmlNode, vsConfigName ):
		platformName = self.GetVisualStudioName()
		includeString = "{}|{}".format( vsConfigName, platformName )

		projectConfigNode = _addNode(parentXmlNode, "ProjectConfiguration")
		configNode = _addNode(projectConfigNode, "Configuration")
		platformNode = _addNode(projectConfigNode, "Platform")

		projectConfigNode.set( "Include", includeString )
		configNode.text = vsConfigName
		platformNode.text = platformName


	def WriteConfigPropertyGroup( self, parentXmlNode, vsConfigName, vsPlatformToolsetName, isNative ):
		platformName = self.GetVisualStudioName()

		propertyGroupNode = _addNode( parentXmlNode, "PropertyGroup" )
		propertyGroupNode.set( "Label", "Configuration")
		propertyGroupNode.set( "Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format( vsConfigName, platformName ) )

		wiiuGlobalData = toolchain_wiiu.GlobalData.Instance

		ghsRootNode = _addNode( propertyGroupNode, "GHS_ROOT" )
		cafeRootNode = _addNode( propertyGroupNode, "CAFE_ROOT" )

		ghsRootNode.text = wiiuGlobalData.ghsRoot
		cafeRootNode.text = wiiuGlobalData.cafeRoot

		if isNative:
			#TODO: Add properties for native projects.
			pass
		else:
			configTypeNode = _addNode( propertyGroupNode, "ConfigurationType" )
			configTypeNode.text = "Makefile"


	def WriteImportProperties( self, parentXmlNode, vsConfigName, isNative ):
		platformName = self.GetVisualStudioName()

		importGroupNode = _addNode( parentXmlNode, "ImportGroup" )
		importGroupNode.set( "Label", "PropertySheets")
		importGroupNode.set( "Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format( vsConfigName, platformName ) )

		importNode = _addNode( importGroupNode, "Import" )
		importNode.set( "Label", "LocalAppDataPlatform" )
		importNode.set( "Project", r"$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" )
		importNode.set( "Condition", "exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" )


	def WriteUserDebugPropertyGroup( self, parentXmlNode, vsConfigName, projectData ):
		platformName = self.GetVisualStudioName()

		propertyGroupNode = _addNode( parentXmlNode, "PropertyGroup" )
		propertyGroupNode.set( "Condition", "'$(Configuration)|$(Platform)'=='{}|{}'".format( vsConfigName, platformName ) )

		useDebugOsNode = _addNode( propertyGroupNode, "CafeDebuggerUsedDebugOS" )
		workingDirNode = _addNode( propertyGroupNode, "CafeDebuggerWorkingDirectory" )
		debuggerFlavorNode = _addNode( propertyGroupNode, "DebuggerFlavor" )

		projectSettings = self.GetProjectSettings( vsConfigName, projectData.name )

		useDebugOsNode.text = "true" if projectSettings.optLevel == csbuild.OptimizationLevel.Disabled else "false"
		workingDirNode.text = "$(OutDir)"
		debuggerFlavorNode.text = "CafeDebugger"


	def WriteExtraPropertyGroupBuildNodes( self, parentXmlNode, vsConfigName, projectData ):
		#TODO: Add nodes for disc emulation paths.
		pass


	def WriteGlobalImportTargets( self, parentXmlNode, isNative ):
		# Nothing extra to write for WiiU.
		pass
