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

import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import os
import sys

from . import project_generator
from . import projectSettings
from . import log
import csbuild


class ExtensionType:
	WORKSPACE = "vpw"
	PROJECT = "vpj"


class OutputType:
	WORKSPACE = "Workspace"
	PROJECT = "Project"


class project_generator_slickedit(project_generator.project_generator):
	"""
	Generator used to create a SlickEdit project files.
	"""

	def __init__(self, path, solutionName, extraArgs):
		project_generator.project_generator.__init__(self, path, solutionName, extraArgs)


	# Base class methods.

	@staticmethod
	def AdditionalArgs(parser):
		# No additional command line arguments at this time.
		pass


	def WriteProjectFiles(self):
		log.LOG_BUILD("Writing SlickEdit workspace {}...".format(self.solutionname))

		# Create the workspace root path if it doesn't exist.
		if not os.access(self.rootpath, os.F_OK):
			os.makedirs(self.rootpath)

		projectFiles = set()

		self._WriteSubGroup(self.rootpath, projectSettings.rootGroup, projectFiles)
		self._WriteWorkspace(projectFiles)


	# Private methods.

	def _WriteWorkspace(self, projectFiles):
		CreateRootNode = ET.Element
		AddNode = ET.SubElement

		rootNode = CreateRootNode(OutputType.WORKSPACE)
		rootNode.set("Version", "10.0")
		rootNode.set("VendorName", "SlickEdit")

		projectListNode = AddNode(rootNode, "Projects")

		# Add the path of each project file to the workspace.
		for project in projectFiles:
			projectNode = AddNode(projectListNode, "Project")
			relativeProjectPath = os.path.relpath(project, self.rootpath)
			projectNode.set("File", relativeProjectPath)

		xmlString = ET.tostring(rootNode)
		outputPath = os.path.join(self.rootpath, "{}.{}".format(self.solutionname, ExtensionType.WORKSPACE))

		self._SaveXmlFile(xmlString, outputPath, OutputType.WORKSPACE, ExtensionType.WORKSPACE)


	def _WriteSubGroup(self, projectOutputPath, projectGroup, projectFiles):
		# Write out each project first.
		for projectName, projectSettingsMap in projectGroup.projects.items():
			# Construct the output path to the project file.
			projectFilePath = os.path.join(projectOutputPath, "{}.{}".format(projectName, ExtensionType.PROJECT))

			# Cache the project output path so we can use it later when we build the workspace file.
			projectFiles.add(projectFilePath)

			# Save the project file to disk.
			self._WriteProject(projectFilePath, projectName, projectSettingsMap)

		# Next, iterate through each subgroup and handle each one recursively.
		for subGroupName, subGroup in projectGroup.subgroups.items():
			groupPath = os.path.join(projectOutputPath, subGroupName)

			# Create the group path if it doesn't exist.
			if not os.access(groupPath, os.F_OK):
				os.makedirs(groupPath)

			self._WriteSubGroup(groupPath, subGroup, projectFiles)


	def _WriteProject(self, projectFilePath, projectName, projectSettingsMap):
		CreateRootNode = ET.Element
		AddNode = ET.SubElement

		# When the main makefile is executed, chdir is called to set the currect working directory to the same directory
		# as the makefile itself, so using that directory is acceptable for project working directory.
		mainfileDirPath = os.getcwd()
		projectDirPath = os.path.dirname(projectFilePath)

		extraArgs = self.extraargs.replace(",", " ")

		rootNode = CreateRootNode(OutputType.PROJECT)
		rootNode.set("Version", "10.0")
		rootNode.set("VendorName", "SlickEdit")
		rootNode.set("WorkingDir", mainfileDirPath)

		filesNode = AddNode(rootNode, "Files")
		sourcesNode = AddNode(filesNode, "Folder")
		headersNode = AddNode(filesNode, "Folder")

		sourcesNode.set("Name", "Source Files")
		headersNode.set("Name", "Header Files")

		sourceFileList = set()
		headerFileList = set()

		# Because the list of sources and headers can differ between configurations and architectures,
		# we need to generate a complete list so the project can reference them all.
		for configName, archMap in projectSettingsMap.items():
			for archName, settings in archMap.items():
				sourceFileList.update(set(settings.allsources))
				headerFileList.update(set(settings.allheaders))

		# Add each source file to the project.
		for sourceFile in sourceFileList:
			relativeFilePath = os.path.relpath(sourceFile, projectDirPath)
			fileNode = AddNode(sourcesNode, "F")
			fileNode.set("N", relativeFilePath)

		# Add each header file to the project.
		for headerFile in headerFileList:
			relativeFilePath = os.path.relpath(headerFile, projectDirPath)
			fileNode = AddNode(headersNode, "F")
			fileNode.set("N", relativeFilePath)

		# Create a dictionary of the build targets and their command line specification.
		# It's assumed that (ALL_TARGETS) will not be defined by the makefiles.
		# TODO: Add handling for any custom build targets named (ALL_TARGETS).
		buildTargets = { "(ALL_TARGETS)": "--all-targets" }
		for targetName, _ in projectSettingsMap.items():
			buildTargets.update({ targetName: targetName })

		# Output nodes for each build target.
		for targetName, targetCommand in buildTargets.items():
			# Create the config node for this build target.
			configNode = AddNode(rootNode, "Config")
			configNode.set("Name", targetName)

			menuNode = AddNode(configNode, "Menu")

			# Create the individual nodes representing the compilation options available under this project.
			# SlickEdit refers to these options as "targets", so don't confuse that with csbuild targets.
			compileProjectNode = AddNode(menuNode, "Target")
			buildAllNode = AddNode(menuNode, "Target")
			rebuildAllNode = AddNode(menuNode, "Target")
			cleanAllNode = AddNode(menuNode, "Target")

			def SetCommonTargetOptions(targetNode):
				targetNode.set("RunFromDir", "%rw") # Project working directory.
				targetNode.set("CaptureOutputWith", "ProcessBuffer") # Send csbuild output to SlickEdit output window.
				targetNode.set("SaveOption", "SaveWorkspaceFiles") # Save all workspace files when initiating this target.

			SetCommonTargetOptions(compileProjectNode)
			SetCommonTargetOptions(buildAllNode)
			SetCommonTargetOptions(rebuildAllNode)
			SetCommonTargetOptions(cleanAllNode)

			compileProjectNode.set("Name", "Compile Project")
			compileProjectNode.set("MenuCaption", "Compile &Project")

			buildAllNode.set("Name", "Build All")
			buildAllNode.set("MenuCaption", "&Build All")

			rebuildAllNode.set("Name", "Rebuild All")
			rebuildAllNode.set("MenuCaption", "&Rebuild All")

			cleanAllNode.set("Name", "Clean All")
			cleanAllNode.set("MenuCaption", "&Clean All")

			commandNode = AddNode(compileProjectNode, "Exec")
			commandNode.set("CmdLine", "{} {} {} --project={} {}".format(sys.executable, csbuild.mainfile, targetCommand, projectName, extraArgs))

			commandNode = AddNode(buildAllNode, "Exec")
			commandNode.set("CmdLine", "{} {} {} {}".format(sys.executable, csbuild.mainfile, targetCommand, extraArgs))

			commandNode = AddNode(rebuildAllNode, "Exec")
			commandNode.set("CmdLine", "{} {} {} --rebuild {}".format(sys.executable, csbuild.mainfile, targetCommand, extraArgs))

			commandNode = AddNode(cleanAllNode, "Exec")
			commandNode.set("CmdLine", "{} {} {} --clean {}".format(sys.executable, csbuild.mainfile, targetCommand, extraArgs))

		# Grab a string of the XML document we've created and save it.
		xmlString = ET.tostring(rootNode)
		self._SaveXmlFile(xmlString, projectFilePath, OutputType.PROJECT, ExtensionType.PROJECT)


	def _SaveXmlFile(self, xmlString, xmlFilename, outputType, outputTypeExt):
		# Convert to the original XML to a string on Python3.
		if sys.version_info >= (3, 0):
			xmlString = xmlString.decode("utf-8")

		finalXmlString = '<!DOCTYPE {} SYSTEM "http://www.slickedit.com/dtd/vse/10.0/{}.dtd"><!-- Auto-generated by CSBuild for use with SlickEdit. -->{}'.format(outputType, outputTypeExt, xmlString)

		# Use minidom to reformat the XML since ElementTree doesn't do it for us.
		formattedXmlString = minidom.parseString(finalXmlString).toprettyxml("\t", "\n")
		inputLines = formattedXmlString.split("\n")
		outputLines = []

		# Copy each line of the XML to a list of strings.
		for line in inputLines:
			# Disregard the ?xml line at the start since SlickEdit doesn't care about that.
			if not line.startswith("<?xml") and line.strip():
				outputLines.append(line)

		# Concatenate each string with a newline.
		finalXmlString = "\n".join(outputLines)

		# Open the output file and write the new XML string to it.
		with open(xmlFilename, "w") as f:
			f.write(finalXmlString)
