# coding=utf-8
import functools
import re
import stat
import sys
if sys.version_info >= (3,0):
	import io
	StringIO = io.StringIO
else:
	import cStringIO
	StringIO = cStringIO.StringIO
import csbuild
from . import log

# try:
# 	from PyQt5 import QtCore, QtGui, QtWidgets
# 	QMainWindow = QtWidgets.QMainWindow
# 	QApplication = QtWidgets.QApplication
# 	QtGui.QWidget = QtWidgets.QWidget
# 	QtGui.QHBoxLayout = QtWidgets.QHBoxLayout
# 	QtGui.QVBoxLayout = QtWidgets.QVBoxLayout
# 	QtGui.QSplitter = QtWidgets.QSplitter
# 	QtGui.QLabel = QtWidgets.QLabel
# 	QtGui.QProgressBar = QtWidgets.QProgressBar
# 	QtGui.QPushButton = QtWidgets.QPushButton
# 	QtGui.QTreeWidget = QtWidgets.QTreeWidget
# 	QtGui.QTreeWidgetItem = QtWidgets.QTreeWidgetItem
# 	QtGui.QSpacerItem = QtWidgets.QSpacerItem
# 	QtGui.QSizePolicy = QtWidgets.QSizePolicy
# 	QtGui.QTextEdit = QtWidgets.QTextEdit
# 	QtGui.QTabWidget = QtWidgets.QTabWidget
# 	log.LOG_INFO("Using Qt5")
# except:
try:
	from PyQt4 import QtCore, QtGui
	QMainWindow = QtGui.QMainWindow
	QApplication = QtGui.QApplication
	log.LOG_INFO("Using Qt4")
except:
	log.LOG_ERROR("PyQt4 must be installed on your system to load the CSBuild GUI")
	csbuild.Exit( 1 )

import os
import threading
import time
import math
import signal

from . import _shared_globals

class TreeWidgetItem(QtGui.QTreeWidgetItem):
	def __init__(self, *args, **kwargs):
		QtGui.QTreeWidgetItem.__init__(self, *args, **kwargs)
		self.numericColumns = set()

	def setColumnNumeric(self, col):
		self.numericColumns.add(col)

	def __lt__(self, other):
		if self.parent():
			return False

		sortCol = self.treeWidget().sortColumn()
		numericColumns = self.treeWidget().headerItem().numericColumns
		try:
			if sortCol in numericColumns:
				myNumber = float(self.text(sortCol))
				otherNumber = float(other.text(sortCol))
				return myNumber > otherNumber
		except:
			pass

		myText = str(self.text(sortCol))
		otherText = str(other.text(sortCol))
		return myText > otherText

class TreeWidgetWithBarGraph(QtGui.QTreeWidgetItem):
	def __init__(self, parent, renderParent, isFile):
		QtGui.QTreeWidgetItem.__init__(self, parent)
		self.numericColumns = set()
		self.startTime = -1
		self.buildEnd = -1
		self.linkQueueStart = -1
		self.linkStart = -1
		self.endTime = -1

		self.isFile = isFile

		self.m_childrenShowing = False
		self.renderParent = renderParent
		self.lastUpdate = 0

	def setChildrenShowing(self, showing):
		self.m_childrenShowing = showing

	def childrenShowing(self):
		return self.m_childrenShowing

	def setStartTime(self, startTime):
		self.startTime = startTime
		self.lastUpdate = time.time()

	def setBuildEnd(self, buildEnd):
		self.buildEnd = buildEnd

	def setLinkStart(self, linkStart):
		self.linkStart = linkStart

	def setLinkQueueStart(self, linkQueueStart):
		self.linkQueueStart = linkQueueStart

	def setEndTime(self, endTime):
		self.endTime = endTime

	def draw(self, painter):
		rect = self.renderParent.visualItemRect(self)
		def drawBar(color, startTime, endTime):
			if startTime != -1:
				if endTime == -1:
					endTime = self.lastUpdate

				topLeft = rect.topLeft()
				if topLeft.y() < 0:
					return
				bottomRight = rect.bottomRight()
				xoffset = 24
				if self.isFile:
					xoffset += 20
				topLeft.setX(topLeft.x() + (250-xoffset) + math.floor((startTime - _shared_globals.starttime) * 30))
				topLeft.setY(topLeft.y())
				bottomRight.setX(topLeft.x() + math.ceil((endTime - startTime) * 30))
				bottomRight.setY(topLeft.y() + rect.height() - 2)
				drawRect = QtCore.QRect(topLeft, bottomRight)
				brush = painter.brush()
				painter.setBrush(QtGui.QColor(color))
				painter.drawRect(drawRect)
				painter.setBrush(brush)

		if self.isFile:
			drawBar("#FF4000", self.startTime, self.buildEnd)
		else:
			drawBar("#0040FF", self.startTime, self.buildEnd)
			drawBar("#008080", self.buildEnd, self.linkQueueStart)
			drawBar("#00C0C0", self.linkQueueStart, self.linkStart)
			drawBar("#00E080", self.linkStart, self.endTime)


class SyntaxHighlighter( QtGui.QSyntaxHighlighter ):

	class HighlightRule( object ):
		def __init__(self, pattern, argument):
			self.pattern = pattern
			self.format = argument

	def __init__(self, *args):
		QtGui.QSyntaxHighlighter.__init__(self, *args)
		self.highlightRules = []

		self.commentStart = re.compile("/\\*")
		self.commentEnd = re.compile("\\*/")

		self.keywordFormat = QtGui.QTextCharFormat()
		self.commentFormat = QtGui.QTextCharFormat()
		self.stringFormat = QtGui.QTextCharFormat()
		self.functionFormat = QtGui.QTextCharFormat()

		self.keywordFormat.setForeground(QtGui.QColor("#800000"))
		self.keywordFormat.setFontWeight(QtGui.QFont.Bold)

		for pattern in [
			"\\b__alignof\\b",
			"\\b__asm\\b",
			"\\b__assume\\b",
			"\\b__based\\b",
			"\\b__box\\b",
			"\\b__cdecl\\b",
			"\\b__declspec\\b",
			"\\b__delegate\\b",
			"\\b__event\\b",
			"\\b__except\\b",
			"\\b__fastcall\\b",
			"\\b__finally\\b",
			"\\b__forceinline\\b",
			"\\b__gc\\b",
			"\\b__hook\\b",
			"\\b__identifier\\b",
			"\\b__if_exists\\b",
			"\\b__if_not_exists\\b",
			"\\b__inline\\b",
			"\\b__int16\\b",
			"\\b__int32\\b",
			"\\b__int64\\b",
			"\\b__int8\\b",
			"\\b__interface\\b",
			"\\b__leave\\b",
			"\\b__m128\\b",
			"\\b__m128d\\b",
			"\\b__m128i\\b",
			"\\b__m64\\b",
			"\\b__multiple_inheritance\\b",
			"\\b__nogc\\b",
			"\\b__noop\\b",
			"\\b__pin\\b",
			"\\b__property\\b",
			"\\b__raise\\b",
			"\\b__restrict\\b",
			"\\b__single_inheritance\\b",
			"\\b__stdcall\\b",
			"\\b__super\\b",
			"\\b__thiscall\\b",
			"\\b__try\\b",
			"\\b__try_cast\\b",
			"\\b__unaligned\\b",
			"\\b__uuidof\\b",
			"\\b__value\\b",
			"\\b__virtual_inheritance\\b",
			"\\b__w64\\b",
			"\\b__wchar_t\\b",
			"\\babstract\\b",
			"\\barray\\b",
			"\\balignas\\b",
			"\\balignof\\b",
			"\\band\\b",
			"\\band_eq\\b",
			"\\basm\\b",
			"\\bauto\\b",
			"\\bbitand\\b",
			"\\bbitor\\b",
			"\\bbool\\b",
			"\\bbreak\\b",
			"\\bcase\\b",
			"\\bcatch\\b",
			"\\bchar\\b",
			"\\bchar16_t\\b",
			"\\bchar32_t\\b",
			"\\bclass\\b",
			"\\bcompl\\b",
			"\\bconst\\b",
			"\\bconst_cast\\b",
			"\\bconstexpr\\b",
			"\\bcontinue\\b",
			"\\bdecltype\\b",
			"\\bdefault\\b",
			"\\bdelegate\\b",
			"\\bdelete\\b",
			"\\bdeprecated\\b",
			"\\bdllexport\\b",
			"\\bdllimport\\b",
			"\\bdo\\b",
			"\\bdouble\\b",
			"\\bdynamic_cast\\b",
			"\\belse\\b",
			"\\benum\\b",
			"\\bevent\\b",
			"\\bexplicit\\b",
			"\\bexport\\b",
			"\\bextern\\b",
			"\\bfalse\\b",
			"\\bfinal\\b",
			"\\bfinally\\b",
			"\\bfloat\\b",
			"\\bfor\\b",
			"\\bfor each\\b",
			"\\bfriend\\b",
			"\\bfriend_as\\b",
			"\\bgcnew\\b",
			"\\bgeneric\\b",
			"\\bgoto\\b",
			"\\bif\\b",
			"\\bin\\b",
			"\\binitonly\\b",
			"\\binline\\b",
			"\\bint\\b",
			"\\bint16_t\\b",
			"\\bint32_t\\b",
			"\\bint64_t\\b",
			"\\bint8_t\\b",
			"\\binterface\\b",
			"\\binterior_ptr\\b",
			"\\bliteral\\b",
			"\\blong\\b",
			"\\bmutable\\b",
			"\\bnaked\\b",
			"\\bnamespace\\b",
			"\\bnew\\b",
			"\\bnoexcept\\b",
			"\\bnoinline\\b",
			"\\bnoreturn\\b",
			"\\bnot\\b",
			"\\bnot_eq\\b",
			"\\bnothrow\\b",
			"\\bnovtable\\b",
			"\\bNULL\\b",
			"\\bnullptr\\b",
			"\\bnullptr_t\\b",
			"\\boperator\\b",
			"\\bor\\b",
			"\\bor_eq\\b",
			"\\boverride\\b",
			"\\bproperty\\b",
			"\\bprivate\\b",
			"\\bprotected\\b",
			"\\bpublic\\b",
			"\\braise\\b",
			"\\bref\\b",
			"\\bregister\\b",
			"\\breinterpret_cast\\b",
			"\\brestrict\\b",
			"\\breturn\\b",
			"\\bsafecast\\b",
			"\\bsealed\\b",
			"\\bselectany\\b",
			"\\bshort\\b",
			"\\bsignals\\b",
			"\\bsigned\\b",
			"\\bsize_t\\b",
			"\\bsizeof\\b",
			"\\bslots\\b",
			"\\bstatic\\b",
			"\\bstatic_assert\\b",
			"\\bstatic_cast\\b",
			"\\bstruct\\b",
			"\\bswitch\\b",
			"\\btemplate\\b",
			"\\btypedef\\b",
			"\\btypename\\b",
			"\\bthis\\b",
			"\\bthread\\b",
			"\\bthread_local\\b",
			"\\bthrow\\b",
			"\\btrue\\b",
			"\\btry\\b",
			"\\btypeid\\b",
			"\\buint16_t\\b",
			"\\buint32_t\\b",
			"\\buint64_t\\b",
			"\\buint8_t\\b",
			"\\bunion\\b",
			"\\bunsigned\\b",
			"\\busing\\b",
			"\\buuid\\b",
			"\\bvalue\\b",
			"\\bvirtual\\b",
			"\\bvoid\\b",
			"\\bvolatile\\b",
			"\\bwchar_t\\b",
			"\\bwhile\\b",
			"\\bxor\\b",
			"\\bxor_eq\\b",
		]:
			self.highlightRules.append(SyntaxHighlighter.HighlightRule(re.compile(pattern), self.keywordFormat))

		#self.functionFormat.setForeground(QtCore.Qt.darkMagenta)
		#self.highlightRules.append(SyntaxHighlighter.HighlightRule(re.compile("\\b[A-Za-z0-9_]+(?=\\()"), self.functionFormat))

		self.numberFormat = QtGui.QTextCharFormat()
		self.numberFormat.setForeground(QtGui.QColor("#008c00"))
		self.highlightRules.append(SyntaxHighlighter.HighlightRule(re.compile("\\b\d+\\b"), self.numberFormat))

		self.symbolFormat = QtGui.QTextCharFormat()
		self.symbolFormat.setForeground(QtGui.QColor("#808030"))
		self.highlightRules.append(SyntaxHighlighter.HighlightRule(re.compile(r"[\[\]\+\=\-\*\/\(\)\{\}\;\,\.\<\>\?\&\^\%\!\~\|]"), self.symbolFormat))

		self.commentFormat.setForeground(QtGui.QColor("#696969"))

		self.highlightRules.append(SyntaxHighlighter.HighlightRule(re.compile("//[^\n]*"), self.commentFormat))

		self.preprocessorFormat = QtGui.QTextCharFormat()
		self.preprocessorFormat.setForeground(QtGui.QColor("#004a43"))
		self.highlightRules.append(SyntaxHighlighter.HighlightRule(re.compile("^\s*#.*$"), self.preprocessorFormat))

		self.stringFormat.setForeground(QtCore.Qt.darkCyan)
		self.highlightRules.append(SyntaxHighlighter.HighlightRule(re.compile("\".*?\""), self.stringFormat))


	def highlightBlock(self, line):
		for rule in self.highlightRules:
			match = rule.pattern.search(line)
			while match:
				start, end = match.span()
				length = end - start
				self.setFormat(start, length, rule.format)
				match = rule.pattern.search(line, end)

		self.setCurrentBlockState(0)
		startIndex = 0
		if self.previousBlockState() != 1:
			match = self.commentStart.search(line)
			if match:
				startIndex = match.start()
			else:
				startIndex = -1

		while startIndex >= 0:
			endIndex = -1
			match = self.commentEnd.search(line, startIndex)
			if match:
				endIndex = match.end()
			length = -1
			if endIndex == -1:
				self.setCurrentBlockState(1)
				length = len(line) - startIndex
			else:
				length = endIndex - startIndex
			self.setFormat(startIndex, length, self.commentFormat)
			match = self.commentStart.search(line, startIndex + length)
			if match:
				startIndex = match.start()
			else:
				startIndex = -1

class LineNumberArea( QtGui.QWidget ):
	def __init__(self, editor):
		QtGui.QWidget.__init__(self, editor)
		self.editor = editor
		self.buttonDown = False

	def sizeHint(self):
		return QtCore.QSize(self.editor.lineNumberAreaWidth(), 0)

	def paintEvent(self, event):
		self.editor.lineNumberAreaPaintEvent(event)

	def mouseMoveEvent(self, event):
		if self.buttonDown:
			self.editor.sideBarMousePress(event)

	def mousePressEvent(self, event):
		if event.button() == QtCore.Qt.LeftButton:
			self.buttonDown = True
			self.editor.sideBarMousePress(event)

	def mouseReleaseEvent(self, event):
		if event.button() == QtCore.Qt.LeftButton:
			self.buttonDown = False



class CodeEditor( QtGui.QPlainTextEdit ):
	def __init__(self, parent, parentEditor, project, directory = None):
		QtGui.QPlainTextEdit.__init__(self, parent)

		self.parentEditor = parentEditor
		self.project = project

		font = QtGui.QFont()
		font.setFamily("monospace")
		font.setFixedPitch(True)
		font.setPointSize(10)

		metrics = QtGui.QFontMetrics(font)
		self.setTabStopWidth(4 * metrics.width(' '))

		self.setFont(font)

		self.sideBar = LineNumberArea(self)

		self.cursorPositionChanged.connect(self.highlightCurrentLine)
		self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
		self.updateRequest.connect(self.updateLineNumberArea)

		self.updateLineNumberAreaWidth(0)
		self.highlightCurrentLine()

	def lineNumberAreaPaintEvent(self, event):
		painter = QtGui.QPainter(self.sideBar)
		painter.fillRect(event.rect(), QtCore.Qt.lightGray)

		block = self.firstVisibleBlock()
		blockNum = block.blockNumber()
		top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
		bottom = top + int(self.blockBoundingRect(block).height())

		while block.isValid() and top <= event.rect().bottom():
			if block.isVisible and bottom >= event.rect().top():
				number = str(blockNum + 1)
				painter.setPen(QtCore.Qt.black)
				painter.drawText(0, top, self.sideBar.width(), self.fontMetrics().height(), QtCore.Qt.AlignRight, number)
			block = block.next()
			top = bottom
			bottom = top + int(self.blockBoundingRect(block).height())
			blockNum += 1


	def lineNumberAreaWidth(self):
		digits = 1
		maxDigits = max(1, self.blockCount())
		while maxDigits >= 10:
			maxDigits /= 10
			digits += 1

		space = 3 + self.fontMetrics().width("9") * digits

		return space

	def resizeEvent(self, event):
		QtGui.QPlainTextEdit.resizeEvent(self, event)

		cr = self.contentsRect()
		self.sideBar.setGeometry(QtCore.QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

	def updateLineNumberAreaWidth(self, blockCount):
		self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

	def highlightCurrentLine(self):
		extraSelections = []

		lineColor = "#DDEDEC"

		selection = QtGui.QTextEdit.ExtraSelection()
		selection.format.setBackground(QtGui.QColor(lineColor))
		selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
		selection.cursor = self.textCursor()
		selection.cursor.clearSelection()
		extraSelections.append(selection)

		self.setExtraSelections(extraSelections)

	def updateLineNumberArea(self, rect, num):
		if num:
			self.sideBar.scroll(0, num)
		else:
			self.sideBar.update(0, rect.y(), self.sideBar.width(), rect.height())

		if rect.contains(self.viewport().rect()):
			self.updateLineNumberAreaWidth(0)


	def sideBarMousePress(self, event):
		pass


class CodeProfileDisplay(CodeEditor):
	def __init__(self, parent, parentEditor, project, directory):
		self.visualizationWidth = 15
		CodeEditor.__init__(self, parent, parentEditor, project)
		self.directory = directory

		self.setReadOnly(True)
		self.vals = []
		self.highVal = 0.0

		self.setMouseTracking(True)
		self.selections = []

		self.mousePos = None
		self.mouseGlobalPos = None
		self.maxVal = 0.0

		self.settingValue = False

	def keyPressEvent(self, event):
		if not self.mousePos:
			return
		if event.key() == QtCore.Qt.Key_Control:
			mouseEvent = QtGui.QMouseEvent(
				QtCore.QEvent.MouseMove,
				self.mousePos,
				self.mouseGlobalPos,
				QtCore.Qt.NoButton,
				QtCore.Qt.NoButton,
				QtGui.QApplication.keyboardModifiers()
			)
			self.mouseMoveEvent(mouseEvent)


	def keyReleaseEvent(self, event):
		if not self.mousePos:
			return
		if event.key() == QtCore.Qt.Key_Control:
			mouseEvent = QtGui.QMouseEvent(
				QtCore.QEvent.MouseMove,
				self.mousePos,
				self.mouseGlobalPos,
				QtCore.Qt.NoButton,
				QtCore.Qt.NoButton,
				QtGui.QApplication.keyboardModifiers()
			)
			self.mouseMoveEvent(mouseEvent)


	def mouseMoveEvent(self, event):
		cursor = self.cursorForPosition(event.pos())
		block = cursor.block()
		line = str(block.text())
		RMatch = re.search( r"#\s*include\s*[<\"](.*?)[\">]", line )
		if RMatch:
			extraSelections = list(self.selections)
			selection = QtGui.QTextEdit.ExtraSelection()
			selection.format.setFontUnderline(True)
			modifiers = QtGui.QApplication.keyboardModifiers()
			if modifiers == QtCore.Qt.ControlModifier:
				selection.format.setForeground(QtGui.QColor("#0000FF"))
				selection.format.setFontWeight(QtGui.QFont.Bold)
				QApplication.setOverrideCursor(QtCore.Qt.PointingHandCursor)
				QtGui.QToolTip.showText(event.globalPos(), "", self)
			else:
				QtGui.QToolTip.showText(event.globalPos(), "Ctrl+click to open profile view for {}".format(RMatch.group(1)), self)
				QApplication.restoreOverrideCursor()
			selection.cursor = QtGui.QTextCursor(self.document())
			selection.cursor.movePosition(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor, block.blockNumber())
			selection.cursor.movePosition(QtGui.QTextCursor.Right, QtGui.QTextCursor.MoveAnchor, RMatch.start())
			selection.cursor.clearSelection()
			selection.cursor.movePosition(QtGui.QTextCursor.Right, QtGui.QTextCursor.KeepAnchor, RMatch.end() - RMatch.start())
			extraSelections.append(selection)
			self.setExtraSelections(extraSelections)
			self.mousePos = event.pos()
			self.mouseGlobalPos = event.globalPos()
		else:
			QtGui.QToolTip.showText(event.globalPos(), "", self)
			self.setExtraSelections(self.selections)
			QApplication.restoreOverrideCursor()
			self.mousePos = None
			self.mouseGlobalPos = None

	def highlightCurrentLine(self):
		pass

	def sideBarMousePress(self, event):
		if event.pos().x() <= self.visualizationWidth:
			totalLines = self.blockCount()
			pct = float(event.pos().y()) / self.sideBar.rect().height()
			cursor = self.textCursor()
			block = cursor.block()
			blockNo = block.blockNumber()
			desiredBlockNo = int(totalLines * pct)
			if blockNo > desiredBlockNo:
				cursor.movePosition(QtGui.QTextCursor.Up, QtGui.QTextCursor.MoveAnchor, blockNo - desiredBlockNo)
			else:
				cursor.movePosition(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor, desiredBlockNo - blockNo)
			self.setTextCursor(cursor)
			self.centerCursor()


	def mousePressEvent(self, event):
		if event.button() == QtCore.Qt.LeftButton and event.modifiers() == QtCore.Qt.ControlModifier:
			cursor = self.cursorForPosition(event.pos())
			block = cursor.block()
			line = str(block.text())
			RMatch = re.search( r"#\s*include\s*[<\"](.*?)[\">]", line )
			if RMatch:
				includeFile = RMatch.group(1)
				project = self.project

				#First try: Absolute path relative to base file directory.
				absPath = os.path.abspath(os.path.join(self.directory, includeFile))
				if not os.access(absPath, os.F_OK):
					#Second try: Look in the project's include directories.
					for directory in project.includeDirs:
						absPath = os.path.abspath(os.path.join(directory, includeFile))
						if os.access(absPath, os.F_OK):
							break
				if not os.access(absPath, os.F_OK):
					#Third try, brute force it against the filemap our parent has for us.
					base = os.path.basename(includeFile)
					if base in self.parentEditor.filemap:
						options = self.parentEditor.filemap[base]
						if len(options) == 1:
							absPath = list(options)[0]
						else:
							log.LOG_ERROR("TODO: Multiple options exist for header {}: {}".format(includeFile, options))
							return
					else:
						return

				with open(absPath, "r") as f:
					data = f.read().split("\n")
				io = StringIO()

				absPath = os.path.normcase(absPath)
				baseFile = self.parentEditor.sourceFile

				lineNo = 1

				for line in data:
					lineTime = 0.0

					if lineNo in project.times[baseFile][absPath]:
						lineTime = project.times[baseFile][absPath][lineNo]

					io.write("{: 9.6f}\t\t{}\n".format(lineTime, line))
					lineNo += 1

				data = io.getvalue()
				io.close()

				window = EditorWindow(baseFile, 0, 0, CodeProfileDisplay, self, project=project, directory=os.path.dirname(absPath), data=data, filemap=self.parentEditor.filemap, baseFile=os.path.basename(absPath))
				window.show()


	def setPlainText(self, text):
		CodeEditor.setPlainText(self, text)

		text = text.split("\n")
		class VisMode:
			Mean = 1
			HighVal = 3
			Constant = 4

		mode = VisMode.Mean
		skipIncludes = True
		maxVal = 0.0
		for line in text:
			if not line.strip():
				continue
			val = float(line.split('\t')[0])
			maxVal = max(maxVal, val)
		self.maxVal = maxVal

		self.parentEditor.slider.setMaximum(self.toLog(maxVal))
		self.parentEditor.slider.setMinimum(1)

		if mode == VisMode.Mean:
			highVal = 0.0
			num = 0
			for line in text:
				if not line.strip():
					continue
				if skipIncludes:
					RMatch = re.search( r"#\s*include\s*[<\"](.*?)[\">]", line )
					if RMatch:
						continue
				val = float(line.split('\t')[0])
				highVal += val
				num += 1

			if num == 0:
				return

			highVal /= num
			highVal *= 2
			if not highVal:
				for line in text:
					if not line.strip():
						continue
					val = float(line.split('\t')[0])
					highVal += val
					num += 1

				if num == 0:
					return

				highVal /= num
				highVal *= 2
		elif mode == VisMode.HighVal:
			highVal = 0.0
			for line in text:
				if not line.strip():
					continue
				if skipIncludes:
					RMatch = re.search( r"#\s*include\s*[<\"](.*?)[\">]", line )
					if RMatch:
						continue
				val = float(line.split('\t')[0])
				highVal = max(highVal, val)
				if not highVal:
					for line in text:
						if not line.strip():
							continue
						val = float(line.split('\t')[0])
						highVal = max(highVal, val)
		elif mode == VisMode.Constant:
			highVal = 0.01

		if not highVal:
			return

		self.highVal = highVal

		self.settingValue = True
		self.parentEditor.slider.setValue(self.toLog(highVal))
		self.settingValue = False

		self.parentEditor.textBox.setText("{:f}".format(highVal))
		self.highlightProblemAreas(text)


	def toLog(self, val):
		normalized = float(val)/self.maxVal
		return int(round(math.sqrt(normalized) * 1000))

	def fromLog(self, val):
		if val == 0:
			return 0
		val = float(val)/1000.0
		return val * val * self.maxVal


	def sliderMoved(self, value):
		if self.settingValue:
			return

		self.highVal = self.fromLog(value)
		self.parentEditor.textBox.setText("{:f}".format(self.highVal))
		if not self.parentEditor.slider.isSliderDown():
			text = str(self.toPlainText())
			self.highlightProblemAreas(text.split("\n"))


	def textEdited(self):
		try:
			val = float(self.parentEditor.textBox.text())
		except:
			self.parentEditor.textBox.setText("{:f}".format(self.highVal))
		else:
			if val <= 0.0:
				self.parentEditor.textBox.setText("{:f}".format(self.highVal))
				return
			if val > self.maxVal:
				val = self.maxVal
				self.parentEditor.textBox.setText("{:f}".format(val))

			self.highVal = val
			self.settingValue = True
			self.parentEditor.slider.setValue(self.toLog(self.highVal))
			self.settingValue = False

			text = str(self.toPlainText())
			self.highlightProblemAreas(text.split("\n"))




	def sliderReleased(self):
		self.highVal = self.fromLog(self.parentEditor.slider.value())
		text = str(self.toPlainText())
		self.highlightProblemAreas(text.split("\n"))


	def highlightProblemAreas(self, text):
		extraSelections = []
		self.vals = []

		lineNo = 0
		for line in text:
			if not line.strip():
				continue
			val = float(line.split('\t')[0])
			if val > self.highVal:
				val = self.highVal
			selection = QtGui.QTextEdit.ExtraSelection()
			gbVals = 255 - math.ceil(255 * (val/self.highVal))
			selection.format.setBackground(QtGui.QColor(255, gbVals, gbVals))
			selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
			selection.cursor = QtGui.QTextCursor(self.document())
			selection.cursor.movePosition(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor, lineNo)
			selection.cursor.clearSelection()
			extraSelections.append(selection)
			lineNo += 1
			self.vals.append(val)

		self.selections = extraSelections
		self.setExtraSelections(extraSelections)


	def lineNumberAreaWidth(self):
		return self.visualizationWidth + CodeEditor.lineNumberAreaWidth(self)


	def lineNumberAreaPaintEvent(self, event):
		painter = QtGui.QPainter(self.sideBar)
		painter.fillRect(event.rect(), QtCore.Qt.lightGray)

		width = self.visualizationWidth
		visualHeight = self.sideBar.rect().height()
		height = min(visualHeight, len(self.vals))
		image = QtGui.QImage(width, height, QtGui.QImage.Format_RGB32)
		image.fill(QtGui.qRgb(255, 255, 255))
		lineNo = 0
		for val in self.vals:
			y = int(lineNo * (float(height) / float(len(self.vals))))
			color = QtGui.QColor(image.pixel(0, y))
			gbVal = min(255 - int(math.ceil((val / self.highVal) * 255)), color.blue())
			onColor = QtGui.qRgb(255, gbVal, gbVal)
			for x in range(width):
				image.setPixel(x, y, onColor)
			lineNo += 1

		block = self.firstVisibleBlock()
		blockNum = block.blockNumber()
		top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
		bottom = top + int(self.blockBoundingRect(block).height())

		topLeft = self.sideBar.rect().topLeft()
		bottomRight = self.sideBar.rect().bottomRight()
		bottomRight.setX(self.visualizationWidth)
		rect = QtCore.QRect(topLeft, bottomRight)

		painter.drawImage(rect, image, image.rect())

		image2 = QtGui.QImage(self.sideBar.rect().width(), self.sideBar.rect().height(), QtGui.QImage.Format_ARGB32)

		firstNum = -1
		lastNum = -1
		while block.isValid() and top <= self.rect().bottom():
			if block.isVisible() and bottom >= self.rect().top():
				if firstNum == -1:
					firstNum = blockNum
				lastNum = blockNum + 1
			block = block.next()
			top = bottom
			bottom = top + int(self.blockBoundingRect(block).height())
			blockNum += 1

		mult = float(self.sideBar.rect().height())/float(len(self.vals))
		fillColor = QtGui.qRgba(192, 192, 192, 64)
		onColor = QtGui.qRgba(64, 64, 64, 127)
		offColor = QtGui.qRgba(127, 127, 127, 127)
		image2.fill(offColor)
		startPixel = int(math.floor(firstNum * mult))
		endPixel = min(int(math.ceil(lastNum * mult)) - 1, self.sideBar.rect().height() - 1)

		for i in range(startPixel, endPixel):
			for j in range(self.sideBar.rect().width()):
				image2.setPixel(j, i, fillColor)

			image2.setPixel(0, i, onColor)
			image2.setPixel(1, i, onColor)
			image2.setPixel(self.sideBar.width()-2, i, onColor)
			image2.setPixel(self.sideBar.width()-1, i, onColor)

		for i in range(self.sideBar.rect().width()):
			image2.setPixel(i, startPixel, onColor)
			image2.setPixel(i, endPixel, onColor)
			image2.setPixel(i, startPixel + 1, onColor)
			image2.setPixel(i, endPixel - 1, onColor)


		painter.drawImage(rect, image2, image2.rect())

		block = self.firstVisibleBlock()
		blockNum = block.blockNumber()
		top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
		bottom = top + int(self.blockBoundingRect(block).height())

		while block.isValid() and top <= event.rect().bottom():
			if block.isVisible() and bottom >= event.rect().top():
				number = str(blockNum + 1)
				painter.setPen(QtCore.Qt.black)
				painter.drawText(0, top, self.sideBar.width(), self.fontMetrics().height(), QtCore.Qt.AlignRight, number)
			block = block.next()
			top = bottom
			bottom = top + int(self.blockBoundingRect(block).height())
			blockNum += 1




class GridLineDelegate(QtGui.QStyledItemDelegate):
	def __init__(self, parent, *args, **kwargs):
		self.parent = parent
		QtGui.QStyledItemDelegate.__init__(self, *args, **kwargs)
		self.highCol = 0
		self.lastRow = 0

	def paint(self, painter, option, index):
		QtGui.QStyledItemDelegate.paint(self, painter, option, index)

		item = self.parent.itemFromIndex(index)

		pen = QtGui.QPen()
		pen.setWidth(1)
		painter.setPen(pen)

		if isinstance(item, TreeWidgetWithBarGraph):
			painter.drawRect(option.rect)
			painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

			if index.row() <= self.lastRow:
				self.highCol = index.column()

				item.draw(painter)
			elif index.column() == self.highCol:
				item.draw(painter)
				self.lastRow = index.row()


class EditorWindow( QMainWindow ):
	def __init__(self, sourceFile, line, column, EditorType, parent, project = None, directory = None, baseFile = None, data = None, filemap = None, *args, **kwargs):
		QMainWindow.__init__(self, parent, *args, **kwargs)

		self.resize(1275, 600)
		self.project = project

		self.centralWidget = QtGui.QWidget(self)
		self.centralWidget.setObjectName("centralWidget")

		self.outerLayout = QtGui.QVBoxLayout(self.centralWidget)

		self.editor = EditorType(self.centralWidget, self, project, directory)
		self.editor.setStyleSheet(
			"""
			QPlainTextEdit
			{
				color: black;
				background-color: white;
			}
			"""
		)

		self.filemap = filemap

		self.highlighter = SyntaxHighlighter(self.editor.document())

		self.editor.setLineWrapMode(QtGui.QPlainTextEdit.NoWrap)

		self.statusBar = QtGui.QStatusBar()
		self.setStatusBar(self.statusBar)

		self.outerLayout.addWidget(self.editor)

		self.highlighting = False
		self.sourceFile = sourceFile

		self.innerLayout = QtGui.QHBoxLayout()
		if EditorType == CodeEditor:
			self.isCodeEditor = True
			horizontalSpacer = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
			self.innerLayout.addItem(horizontalSpacer)

			self.makeWriteable = QtGui.QPushButton(self.centralWidget)
			self.makeWriteable.setText("Make Writeable")
			self.makeWriteable.pressed.connect(self.MakeWriteable)
			self.innerLayout.addWidget(self.makeWriteable)

			if os.access(sourceFile, os.W_OK):
				self.makeWriteable.hide()
			else:
				self.editor.setReadOnly(True)

			self.saveButton = QtGui.QPushButton(self.centralWidget)
			self.saveButton.setText("Save")
			self.saveButton.pressed.connect(self.save)
			self.innerLayout.addWidget(self.saveButton)

			self.outerLayout.addLayout(self.innerLayout)

			self.saveAction = QtGui.QAction(self)
			self.saveAction.setShortcut( QtCore.Qt.CTRL | QtCore.Qt.Key_S )
			self.saveAction.triggered.connect(self.save)
			self.addAction(self.saveAction)
		else:
			self.isCodeEditor = False
			label = QtGui.QLabel(self.centralWidget)
			label.setText("Highlight values approaching:")
			self.innerLayout.addWidget(label)
			self.slider = QtGui.QSlider(QtCore.Qt.Horizontal, self.centralWidget)
			self.innerLayout.addWidget(self.slider)
			self.slider.valueChanged.connect(self.editor.sliderMoved)
			self.slider.sliderReleased.connect(self.editor.sliderReleased)

			self.textBox = QtGui.QLineEdit(self.centralWidget)
			self.textBox.setMaximumWidth(160)
			self.innerLayout.addWidget(self.textBox)
			self.textBox.editingFinished.connect(self.editor.textEdited)

			self.outerLayout.addLayout(self.innerLayout)

		if data:
			self.editor.setPlainText(data)
		else:
			with open(sourceFile, "r") as f:
				self.editor.setPlainText(f.read())

		self.setCentralWidget(self.centralWidget)
		if baseFile:
			self.setWindowTitle("Profile view: {}".format(baseFile))
		else:
			self.setWindowTitle(sourceFile)


	def ScrollTo(self, line, column):
		if line or column:
			cursor = self.editor.textCursor()
			cursor.setPosition(0)
			if line:
				line = int(line)
				cursor.movePosition( QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor, line - 1 )
			if column:
				column = int(column)
				cursor.movePosition( QtGui.QTextCursor.NextCharacter, QtGui.QTextCursor.MoveAnchor, column - 1 )
			self.editor.setTextCursor(cursor)

	def MakeWriteable(self):
		stats = os.stat(self.sourceFile)
		mode = stats.st_mode
		try:
			os.chmod( self.sourceFile, mode | stat.S_IWRITE )
		except:
			self.statusBar.showMessage("Could not open file for writing. Permission error?.", 5000)
		else:
			self.makeWriteable.hide()
			self.editor.setReadOnly(False)
			self.statusBar.showMessage("File opened for writing.", 5000)

	def save(self):
		with open(self.sourceFile, "w") as f:
			f.write(self.editor.toPlainText())
		self.statusBar.showMessage("Saved.", 5000)

	def closeEvent(self, event):
		if self.isCodeEditor:
			del self.parent().openWindows[self.sourceFile]
		QMainWindow.closeEvent(self, event)


class MainWindow( QMainWindow ):
	def __init__(self, *args, **kwargs):
		self.exitRequested = False

		QMainWindow.__init__(self, *args, **kwargs)

		self.setObjectName("MainWindow")

		self.resize(1275, 600)

		self.centralWidget = QtGui.QWidget(self)
		self.centralWidget.setObjectName("centralWidget")

		self.outerLayout = QtGui.QVBoxLayout(self.centralWidget)

		self.mainLayout = QtGui.QHBoxLayout()

		self.m_splitter = QtGui.QSplitter(self.centralWidget)
		self.m_splitter.setOrientation(QtCore.Qt.Vertical)

		self.innerWidget = QtGui.QWidget(self.centralWidget)
		self.innerLayout = QtGui.QVBoxLayout(self.innerWidget)

		self.verticalLayout = QtGui.QVBoxLayout()
		self.verticalLayout.setObjectName("verticalLayout")

		self.m_buildSummaryLabel = QtGui.QLabel(self.innerWidget)
		self.m_buildSummaryLabel.setObjectName("m_buildSummaryLabel")
		font = QtGui.QFont()
		font.setPointSize( 16 )
		self.m_buildSummaryLabel.setFont(font)

		self.verticalLayout.addWidget(self.m_buildSummaryLabel)

		self.horizontalLayout = QtGui.QHBoxLayout()
		self.horizontalLayout.setObjectName("horizontalLayout")
		self.m_successfulBuildsLabel = QtGui.QLabel(self.innerWidget)
		self.m_successfulBuildsLabel.setObjectName("m_successfulBuildsLabel")

		self.horizontalLayout.addWidget(self.m_successfulBuildsLabel)

		self.m_failedBuildsLabel = QtGui.QLabel(self.innerWidget)
		self.m_failedBuildsLabel.setObjectName("m_failedBuildsLabel")

		self.horizontalLayout.addWidget(self.m_failedBuildsLabel)

		self.m_warningLabel = QtGui.QLabel(self.innerWidget)
		self.m_warningLabel.setObjectName("m_successfulBuildsLabel")

		self.horizontalLayout.addWidget(self.m_warningLabel)

		self.m_errorLabel = QtGui.QLabel(self.innerWidget)
		self.m_errorLabel.setObjectName("m_failedBuildsLabel")

		self.horizontalLayout.addWidget(self.m_errorLabel)

		horizontalSpacer_2 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)

		self.horizontalLayout.addItem(horizontalSpacer_2)

		self.m_filesCompletedLabel = QtGui.QLabel(self.centralWidget)
		self.m_filesCompletedLabel.setObjectName("m_filesCompletedLabel")

		self.horizontalLayout.addWidget(self.m_filesCompletedLabel)

		self.verticalLayout.addLayout(self.horizontalLayout)

		self.m_mainProgressBar = QtGui.QProgressBar(self.centralWidget)
		self.m_mainProgressBar.setObjectName("m_mainProgressBar")
		self.m_mainProgressBar.setValue(0)

		self.verticalLayout.addWidget(self.m_mainProgressBar)

		self.topPane = QtGui.QTabWidget(self.innerWidget)

		self.buildWidget = QtGui.QWidget(self.innerWidget)

		verticalLayout = QtGui.QVBoxLayout(self.buildWidget)
		self.m_buildTree = QtGui.QTreeWidget(self.buildWidget)
		self.m_buildTree.setColumnCount(12)
		self.m_buildTree.setUniformRowHeights(True)

		self.m_treeHeader = TreeWidgetItem()
		self.m_buildTree.setHeaderItem(self.m_treeHeader)

		self.m_buildTree.setObjectName("m_buildTree")
		self.m_buildTree.setAlternatingRowColors(True)
		self.m_buildTree.setUniformRowHeights(True)
		self.m_buildTree.setSortingEnabled(True)
		self.m_buildTree.setAnimated(True)
		self.m_buildTree.header().setStretchLastSection(True)
		self.m_buildTree.currentItemChanged.connect(self.SelectionChanged)
		self.m_buildTree.itemExpanded.connect(self.UpdateProjects)
		self.m_buildTree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.m_buildTree.customContextMenuRequested.connect(self.buildTreeContextMenu)
		verticalLayout.addWidget(self.m_buildTree)

		self.topPane.addTab(self.buildWidget, "Build Progress")

		self.timelinePage = QtGui.QWidget(self.centralWidget)

		verticalLayout = QtGui.QVBoxLayout(self.timelinePage)
		self.timelineWidget = QtGui.QTreeWidget(self.timelinePage)


		self.m_timelineHeader = TreeWidgetItem()
		self.timelineWidget.setHeaderItem(self.m_timelineHeader)

		self.timelineWidget.setFocusPolicy(QtCore.Qt.NoFocus)
		self.timelineWidget.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
		self.timelineWidget.setProperty("showDropIndicator", False)
		#self.timelineWidget.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
		self.timelineWidget.setAlternatingRowColors(True)
		#self.timelineWidget.setVerticalScrollMode(QtGui.QAbstractItemView.ScrollPerPixel)
		#self.timelineWidget.setAnimated(True)
		self.timelineWidget.header().setDefaultSectionSize(30)
		self.timelineWidget.header().setStretchLastSection(False)

		self.timelineWidget.header().setResizeMode(QtGui.QHeaderView.Fixed)

		self.timelineWidget.itemExpanded.connect(self.TimelineItemExpended)
		self.timelineWidget.itemCollapsed.connect(self.TimelineItemExpended)

		self.timelineWidget.setItemDelegate(GridLineDelegate(self.timelineWidget))
		self.timelineWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.timelineWidget.customContextMenuRequested.connect(self.timelineContextMenu)

		verticalLayout.addWidget(self.timelineWidget)

		self.topPane.addTab(self.timelinePage, "Build Timeline")

		self.verticalLayout.addWidget(self.topPane)

		self.innerLayout.addLayout(self.verticalLayout)

		self.m_pushButton =  QtGui.QPushButton(self.buildWidget)
		self.m_pushButton.setObjectName("self.m_pushButton")
		sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(self.m_pushButton.sizePolicy().hasHeightForWidth())
		self.m_pushButton.setSizePolicy(sizePolicy)
		self.m_pushButton.setMaximumSize(QtCore.QSize(16777215, 20))
		self.m_pushButton.setCheckable(True)
		self.m_pushButton.toggled.connect(self.ButtonClicked)

		self.innerLayout.addWidget(self.m_pushButton)
		self.m_splitter.addWidget(self.innerWidget)

		self.innerWidget2 = QtGui.QTabWidget(self.centralWidget)

		self.textPage = QtGui.QWidget(self.innerWidget2)
		self.innerLayout2 = QtGui.QVBoxLayout(self.textPage)
		self.m_textEdit = QtGui.QTextEdit(self.textPage)
		self.m_textEdit.setObjectName("textEdit")
		self.m_textEdit.setReadOnly(True)
		self.m_textEdit.setFontFamily("monospace")
		self.innerLayout2.addWidget(self.m_textEdit)

		self.commandPage = QtGui.QWidget(self.innerWidget2)
		self.innerLayout2 = QtGui.QVBoxLayout(self.commandPage)
		self.m_commandEdit = QtGui.QTextEdit(self.commandPage)
		self.m_commandEdit.setObjectName("commandEdit")
		self.m_commandEdit.setReadOnly(True)
		self.m_commandEdit.setFontFamily("monospace")
		self.innerLayout2.addWidget(self.m_commandEdit)

		self.errorsPage = QtGui.QWidget(self.innerWidget2)

		self.innerLayout3 = QtGui.QVBoxLayout(self.errorsPage)
		self.m_errorTree = QtGui.QTreeWidget(self.errorsPage)
		self.m_errorTree.setColumnCount(5)
		self.m_errorTree.setUniformRowHeights(True)

		self.m_treeHeader2 = TreeWidgetItem()
		self.m_errorTree.setHeaderItem(self.m_treeHeader2)

		self.m_errorTree.setObjectName("m_errorTree")
		self.m_errorTree.setAlternatingRowColors(True)
		self.m_errorTree.setUniformRowHeights(True)
		self.m_errorTree.setSortingEnabled(True)
		self.m_errorTree.setAnimated(True)
		self.m_errorTree.header().setStretchLastSection(True)
		self.m_errorTree.itemDoubleClicked.connect(self.OpenFileForEdit)
		self.innerLayout3.addWidget(self.m_errorTree)

		self.innerWidget2.addTab(self.errorsPage, "Errors/Warnings")
		self.innerWidget2.addTab(self.textPage, "Text Output")
		self.innerWidget2.addTab(self.commandPage, "Command Line")

		self.m_splitter.addWidget(self.innerWidget2)

		self.m_splitter.setSizes( [ 1, 0 ] )
		self.m_splitter.setCollapsible( 0, False )
		self.m_splitter.splitterMoved.connect(self.SplitterMoved)

		sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(self.m_splitter.sizePolicy().hasHeightForWidth())
		self.m_splitter.setSizePolicy(sizePolicy)

		self.mainLayout.addWidget(self.m_splitter)
		self.outerLayout.addLayout(self.mainLayout)

		#self.horizontalLayout_2 = QtGui.QHBoxLayout()
		#self.horizontalLayout_2.setObjectName("horizontalLayout_2")

		#horizontalSpacer = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)

		#self.horizontalLayout_2.addItem(horizontalSpacer)

		self.m_timeLeftLabel = QtGui.QLabel(self.centralWidget)
		#self.m_timeLeftLabel.setObjectName("m_timeLeftLabel")

		#self.horizontalLayout_2.addWidget(self.m_timeLeftLabel)
		self.m_timeLeftLabel.hide()

		#self.outerLayout.addLayout(self.horizontalLayout_2)

		self.setCentralWidget(self.centralWidget)

		self.retranslateUi()

		self.timer = QtCore.QTimer()
		self.timer.timeout.connect(self.onTick)
		self.timer.start(100)

		QtCore.QMetaObject.connectSlotsByName(self)

		self.readyToClose = False
		self.exiting = False

		self.marqueeValue = 0
		self.marqueeInverted = True

		self.successfulBuilds = set()
		self.failedBuilds = set()
		self.m_ignoreButton = False
		self.pulseColor = 0
		self.pulseUp = False
		self.animatingBars = {}
		self.projectToItem = {}
		self.itemToProject = {}
		self.warningErrorCount = 0

		self.openWindows = {}

		self.tick = 0

	def buildTreeContextMenu(self, point):
		if not _shared_globals.profile:
			return

		if not self.readyToClose:
			return

		item = self.m_buildTree.itemAt(point)
		parent = item.parent()
		if not parent:
			return
		if parent.parent():
			return
		menu = QtGui.QMenu(self)
		action = QtGui.QAction("View profile data", self)
		action.triggered.connect(functools.partial(self.buildTreeViewProfile, item))
		menu.addAction(action)
		menu.popup(self.m_buildTree.viewport().mapToGlobal(point))

	def timelineContextMenu(self, point):
		if not _shared_globals.profile:
			return

		if not self.readyToClose:
			return

		item = self.timelineWidget.itemAt(point)
		parent = item.parent()
		if not parent:
			return
		if parent.parent():
			return
		menu = QtGui.QMenu(self)
		action = QtGui.QAction("View profile data", self)
		action.triggered.connect(functools.partial(self.timelineViewProfile, item))
		menu.addAction(action)
		menu.popup(self.timelineWidget.viewport().mapToGlobal(point))


	def launchProfileView(self, project, filename):
		baseFile = os.path.basename(filename)
		directory = os.path.dirname(filename)

		with open(filename, "r") as f:
			data = f.read().split("\n")
		io = StringIO()

		lineNo = 1
		for line in data:
			lineTime = 0.0

			if lineNo in project.times[filename][filename]:
				lineTime = project.times[filename][filename][lineNo]

			io.write("{: 9.6f}\t\t{}\n".format(lineTime, line))
			lineNo += 1

		data = io.getvalue()
		io.close()

		filemap = {}
		for otherfile in project.times[filename]:
			baseName = os.path.basename(otherfile)
			if baseName not in filemap:
				filemap[baseName] = {otherfile}
			else:
				filemap[baseName].add(otherfile)


		window = EditorWindow(filename, 0, 0, CodeProfileDisplay, self, baseFile=baseFile, project=project, directory=directory, data=data, filemap=filemap)
		window.show()


	def buildTreeViewProfile(self, item, checked):
		filename = os.path.normcase(str(item.toolTip(3)))

		project = self.itemToProject[str(item.parent().text(0))]

		self.launchProfileView(project, filename)


	def timelineViewProfile(self, item, checked):
		filename = os.path.normcase(str(item.toolTip(0)))

		idx = self.timelineWidget.indexOfTopLevelItem(self.parent())

		project = _shared_globals.sortedProjects[idx]

		self.launchProfileView(project, filename)

	def ButtonClicked(self, toggled):
		if self.m_ignoreButton:
			return

		if toggled:
			self.m_splitter.setSizes( [ 1275, max( self.width() - 1275, 600 ) ] )
			self.m_errorTree.setColumnWidth( 0, 50 )
			self.m_errorTree.setColumnWidth( 1, max(250, self.m_errorTree.width() - 350) )
			self.m_errorTree.setColumnWidth( 2, 200 )
			self.m_errorTree.setColumnWidth( 3, 50 )
			self.m_errorTree.setColumnWidth( 4, 50 )
			self.m_pushButton.setText(u"▾ Output ▾")
		else:
			self.m_splitter.setSizes( [ 1, 0 ] )
			self.m_pushButton.setText(u"▴ Output ▴")

	def OpenFileForEdit(self, item, column):
		file = str(item.toolTip(2))
		line = item.text(3)
		col = item.text(4)

		if not file or not os.access(file, os.F_OK):
			return

		if file in self.openWindows:
			window = self.openWindows[file]
			window.setWindowState(QtCore.Qt.WindowActive)
			window.activateWindow()
			window.raise_()
			window.ScrollTo(line, col)
			return

		if(
			#TODO: Somehow get extension from the active toolchain?
			not file.endswith(".o")
			and not file.endswith(".so")
			and not file.endswith(".a")
			and not file.endswith(".exe")
			and not file.endswith(".dll")
			and not file.endswith(".lib")
			and not file.endswith(".obj")
		):
			window = EditorWindow(file, line, col, CodeEditor, self)
			window.show()
			window.ScrollTo(line, col)
			self.openWindows[file] = window


	def resizeEvent(self, event):
		QMainWindow.resizeEvent(self, event)
		textBoxSize = self.m_splitter.sizes()[1]
		if textBoxSize != 0:
			self.m_splitter.setSizes( [ 1275, max( self.width() - 1275, 600 ) ] )
			self.m_errorTree.setColumnWidth( 0, 50 )
			self.m_errorTree.setColumnWidth( 1, max(250, self.m_errorTree.width() - 350) )
			self.m_errorTree.setColumnWidth( 2, 200 )
			self.m_errorTree.setColumnWidth( 3, 50 )
			self.m_errorTree.setColumnWidth( 4, 50 )


	def SplitterMoved(self, index, pos):
		textBoxSize = self.m_splitter.sizes()[1]
		if textBoxSize == 0:
			if self.m_pushButton.isChecked():
				self.m_ignoreButton = True
				self.m_pushButton.setChecked(False)
				self.m_ignoreButton = False
			self.m_pushButton.setText(u"▴ Output ▴")
		else:
			if not self.m_pushButton.isChecked():
				self.m_ignoreButton = True
				self.m_pushButton.setChecked(True)
				self.m_ignoreButton = False
			self.m_errorTree.setColumnWidth( 0, 50 )
			self.m_errorTree.setColumnWidth( 1, max(250, self.m_errorTree.width() - 350) )
			self.m_errorTree.setColumnWidth( 2, 200 )
			self.m_errorTree.setColumnWidth( 3, 50 )
			self.m_errorTree.setColumnWidth( 4, 50 )
			self.m_pushButton.setText(u"▾ Output ▾")


	def SelectionChanged(self, current, previous):
		if self.m_textEdit.isVisible():
			if current is None:
				outStr = ""
				for project in _shared_globals.sortedProjects:
					outStr += ("=" * 40) + "\n\n"
					outStr += project.name
					outStr += ("=" * 40) + "\n\n"
					with project.mutex:
						for filename in project.compileOutput:
							outStr += filename
							errors = ""
							output = ""
							if filename in project.compileErrors:
								errors = project.compileErrors[filename]
							output = project.compileOutput[filename]
							if errors or output:
								outStr += "\n" + ("-" * len(filename)) + "\n\n"
								outStr += "\n" + ("-" * 40) + "\n\n"
								if errors:
									outStr += "ERROR OUTPUT:\n\n" + errors + "\n\n"
								if output:
									outStr += "OUTPUT:\n\n" + output + "\n\n"
						if project.linkErrors:
							outStr += "LINK ERRORS:\n\n" + project.linkErrors + "\n\n"
						if project.linkOutput:
							outStr += "LINK OUTPUT:\n\n" + project.linkOutput + "\n\n"

					outStr += "\n\n"
				if outStr != self.m_textEdit.toPlainText():
					self.m_textEdit.setText(outStr)
			else:
				for project in _shared_globals.sortedProjects:
					widget = self.projectToItem[project]
					if not widget:
						continue

					if widget == current:
						outStr = ""
						with project.mutex:
							for filename in project.compileOutput:
								errors = ""
								output = ""
								if filename in project.compileErrors:
									errors = project.compileErrors[filename]
								output = project.compileOutput[filename]
								if errors or output:
									outStr += filename
									outStr += "\n" + ("=" * 40) + "\n\n"
									if errors:
										outStr += "ERROR OUTPUT:\n\n" + errors + "\n\n"
									if output:
										outStr += "OUTPUT:\n\n" + output + "\n\n"

							if project.linkErrors:
								outStr += "LINK ERRORS:\n\n" + project.linkErrors + "\n\n"
							if project.linkOutput:
								outStr += "LINK OUTPUT:\n\n" + project.linkOutput + "\n\n"

							if outStr != self.m_textEdit.toPlainText():
								self.m_textEdit.setText(outStr)
					elif widget.isExpanded():
						def HandleChild( idx, file ):
							file = os.path.normcase(file)
							childWidget = widget.child(idx)

							if childWidget == current:
								outStr = ""
								errors = ""
								output = ""
								with project.mutex:
									if file in project.compileErrors:
										errors = project.compileErrors[file]
									if file in project.compileOutput:
										output = project.compileOutput[file]

								if errors or output:
									outStr += file
									outStr += "\n" + ("=" * 40) + "\n\n"
									if errors:
										outStr += "ERROR OUTPUT:\n\n" + errors + "\n\n"
									if output:
										outStr += "OUTPUT:\n\n" + output + "\n\n"
								if outStr != self.m_textEdit.toPlainText():
									self.m_textEdit.setText(outStr)


						idx = 0
						if project.needsPrecompileCpp:
							HandleChild( idx, project.cppHeaderFile )
							idx += 1

						if project.needsPrecompileC:
							HandleChild( idx, project.cHeaderFile )
							idx += 1

						used_chunks = set()
						for source in project.allsources:
							inThisBuild = False
							if source not in project._finalChunkSet:
								chunk = project.get_chunk( source )
								if not chunk:
									continue

								extension = "." + source.rsplit(".", 1)[1]
								if extension in project.cExtensions:
									extension = ".c"
								else:
									extension = ".cpp"

								chunk = os.path.join( project.csbuildDir, "{}{}".format( chunk, extension ) )

								if chunk in used_chunks:
									continue
								if chunk in project._finalChunkSet:
									inThisBuild = True
									source = chunk
									used_chunks.add(chunk)
							else:
								inThisBuild = True

							if inThisBuild:
								HandleChild( idx, source )

							idx += 1
		elif self.m_commandEdit.isVisible():
			if current is not None:
				for project in _shared_globals.sortedProjects:
					widget = self.projectToItem[project]
					if not widget:
						continue

					if widget == current:
						self.m_commandEdit.setText(project.linkCommand)
					elif widget.isExpanded():
						def HandleChild( idx, file ):
							file = os.path.normcase(file)
							childWidget = widget.child(idx)

							if childWidget == current:
								if file in project.compileCommands:
									self.m_commandEdit.setText(project.compileCommands[file])
								else:
									self.m_commandEdit.setText("")


						idx = 0
						if project.needsPrecompileCpp:
							HandleChild( idx, project.cppHeaderFile )
							idx += 1

						if project.needsPrecompileC:
							HandleChild( idx, project.cHeaderFile )
							idx += 1

						used_chunks = set()
						for source in project.allsources:
							inThisBuild = False
							if source not in project._finalChunkSet:
								chunk = project.get_chunk( source )
								if not chunk:
									continue

								extension = "." + source.rsplit(".", 1)[1]
								if extension in project.cExtensions:
									extension = ".c"
								else:
									extension = ".cpp"

								chunk = os.path.join( project.csbuildDir, "{}{}".format( chunk, extension ) )

								if chunk in used_chunks:
									continue
								if chunk in project._finalChunkSet:
									inThisBuild = True
									source = chunk
									used_chunks.add(chunk)
							else:
								inThisBuild = True

							if inThisBuild:
								HandleChild( idx, source )

							idx += 1
		else:
			if current != previous:
				while self.m_errorTree.takeTopLevelItem(0):
					pass

			def HandleError(datas):
				if datas is None:
					return

				for data in datas:
					exists = False
					for i in range(self.m_errorTree.topLevelItemCount()):
						tempWidget = self.m_errorTree.topLevelItem(i)
						if(
							tempWidget.text(1) == data.text
							and tempWidget.text(2) == os.path.basename( data.file )
							and (
								( tempWidget.text(3) == "" and data.line == -1 )
								or ( tempWidget.text(3) == str(data.line) )
							)
							and (
								( tempWidget.text(4) == "" and data.column == -1 )
								or ( tempWidget.text(4) == str(data.column) )
							)
						):
							#don't re-add data that already exists.
							exists = True
							break
					if exists:
						continue

					font = QtGui.QFont()
					font.setFamily("monospace")

					newItem = TreeWidgetItem()
					if data.level == _shared_globals.OutputLevel.WARNING:
						newItem.setText(0, "W")
						brush = QtGui.QBrush( QtCore.Qt.darkYellow )
						newItem.setForeground(0, brush )
						#newItem.setForeground(1, brush )
						#newItem.setForeground(2, brush )
						#newItem.setForeground(3, brush )
						#newItem.setForeground(4, brush )
					elif data.level == _shared_globals.OutputLevel.ERROR:
						newItem.setText(0, "E")
						brush = QtGui.QBrush( QtCore.Qt.red )
						newItem.setForeground(0, brush )
						#newItem.setForeground(1, brush )
						#newItem.setForeground(2, brush )
						#newItem.setForeground(3, brush )
						#newItem.setForeground(4, brush )
						font.setBold(True)
					elif data.level == _shared_globals.OutputLevel.NOTE:
						newItem.setText(0, "N")
					else:
						newItem.setText(0, "?")

					newItem.setText(1, data.text)
					newItem.setToolTip(1, data.text)

					if data.file:
						newItem.setText(2, os.path.basename(data.file))
						newItem.setToolTip(2, os.path.abspath(data.file))
					if data.line != -1:
						newItem.setText(3, str(data.line))
					if data.column != -1:
						newItem.setText(4, str(data.column))

					newItem.setFont(0, font)
					newItem.setFont(1, font)
					newItem.setFont(2, font)
					newItem.setFont(3, font)
					newItem.setFont(4, font)

					for detail in data.details:
						font = QtGui.QFont()
						font.setItalic(True)
						font.setFamily("monospace")
						childItem = TreeWidgetItem(newItem)
						childItem.setDisabled(True)

						if detail.level == _shared_globals.OutputLevel.NOTE:
							font.setBold(True)

						childItem.setText(1, detail.text)
						childItem.setToolTip(1, detail.text)

						if detail.file:
							childItem.setText(2, os.path.basename(detail.file))
							childItem.setToolTip(2, os.path.abspath(detail.file))
						if detail.line != -1:
							childItem.setText(3, str(detail.line))
						if detail.column != -1:
							childItem.setText(4, str(detail.column))

						childItem.setFont(0, font)
						childItem.setFont(1, font)
						childItem.setFont(2, font)
						childItem.setFont(3, font)
						childItem.setFont(4, font)

						newItem.addChild(childItem)
					self.m_errorTree.addTopLevelItem(newItem)

			self.m_errorTree.setSortingEnabled(False)
			if current is None:
				for project in _shared_globals.sortedProjects:
					with project.mutex:
						for filename in project.parsedErrors:
							HandleError(project.parsedErrors[filename])
						HandleError(project.parsedLinkErrors)
			else:
				for project in _shared_globals.sortedProjects:
					widget = self.projectToItem[project]
					if not widget:
						continue

					if widget == current:
						with project.mutex:
							for filename in project.parsedErrors:
								HandleError(project.parsedErrors[filename])
							HandleError(project.parsedLinkErrors)
					elif widget.isExpanded():
						def HandleChild( idx, file ):
							file = os.path.normcase(file)
							childWidget = widget.child(idx)

							if childWidget == current:
								with project.mutex:
									if file in project.parsedErrors:
										HandleError(project.parsedErrors[file])

						idx = 0
						if project.needsPrecompileCpp:
							HandleChild( idx, project.cppHeaderFile )
							idx += 1

						if project.needsPrecompileC:
							HandleChild( idx, project.cHeaderFile )
							idx += 1

						used_chunks = set()
						for source in project.allsources:
							inThisBuild = False
							if source not in project._finalChunkSet:
								chunk = project.get_chunk( source )
								if not chunk:
									continue

								extension = "." + source.rsplit(".", 1)[1]
								if extension in project.cExtensions:
									extension = ".c"
								else:
									extension = ".cpp"

								chunk = os.path.join( project.csbuildDir, "{}{}".format( chunk, extension ) )

								if chunk in used_chunks:
									continue
								if chunk in project._finalChunkSet:
									inThisBuild = True
									source = chunk
									used_chunks.add(chunk)
							else:
								inThisBuild = True

							if inThisBuild:
								HandleChild( idx, source )

							idx += 1
			self.m_errorTree.setSortingEnabled(True)

	def TimelineItemExpended(self, item):
		self.UpdateTimeline(False)

	def UpdateTimeline(self, addTime = False):
		needsUpdate = False
		if addTime:
			font = QtGui.QFont()
			font.setPointSize(5)
			curtime = time.time( ) - _shared_globals.starttime
			mult = 1
			curtime *= mult
			cols = self.m_timelineHeader.columnCount()
			colsNeeded = int(math.ceil(curtime)) + 1
			if colsNeeded > cols:
				scrollBar = self.timelineWidget.horizontalScrollBar()
				max = scrollBar.maximum()
				needsUpdate = True
				for i in range(colsNeeded - cols):
					idx = cols + i - 1
					self.m_timelineHeader.setFont(idx + 1, font)
					if idx % (10*mult) == 0:
						minutes = int(math.floor( idx / (60*mult) ))
						seconds = int(round( idx % (60*mult) ))
						self.m_timelineHeader.setText(idx+1, "{}:{:02}".format(minutes, seconds/mult))
					else:
						self.m_timelineHeader.setText(idx+1, "")
				if scrollBar.value() == max:
					scrollBar.setValue(scrollBar.maximum())
		else:
			needsUpdate = True

		if not needsUpdate:
			return

		idx = 0
		for project in _shared_globals.sortedProjects:
			item = self.timelineWidget.topLevelItem(idx)
			if project.startTime != 0:
				item.setStartTime(project.startTime)
				if project.buildEnd != 0:
					item.setBuildEnd(project.buildEnd)
					if project.linkQueueStart != 0:
						item.setLinkQueueStart(project.linkQueueStart)
						if project.linkStart != 0:
							item.setLinkStart(project.linkStart)
							if project.endTime != 0:
								item.setEndTime(project.endTime)

			if item.isExpanded() or item.childrenShowing():
				item.setChildrenShowing(item.isExpanded())
				def HandleChildTimeline( idx2, file ):
					childWidget = item.child(idx2)
					file = os.path.normcase(file)

					project.mutex.acquire( )
					try:
						startTime = project.fileStart[file]
					except:
						startTime = 0

					try:
						endTime = project.fileEnd[file]
					except:
						endTime = 0

					project.mutex.release( )

					if startTime != 0:
						childWidget.setStartTime(startTime)
						if endTime != 0:
							childWidget.setBuildEnd(endTime)


				idx2 = 0
				if project.needsPrecompileCpp:
					HandleChildTimeline( idx2, project.cppHeaderFile )
					idx2 += 1

				if project.needsPrecompileC:
					HandleChildTimeline( idx2, project.cHeaderFile )
					idx2 += 1

				used_chunks = set()
				for source in project.allsources:
					inThisBuild = False
					if source not in project._finalChunkSet:
						chunk = project.get_chunk( source )
						if not chunk:
							continue

						extension = "." + source.rsplit(".", 1)[1]
						if extension in project.cExtensions:
							extension = ".c"
						else:
							extension = ".cpp"

						chunk = os.path.join( project.csbuildDir, "{}{}".format( chunk, extension ) )

						if chunk in used_chunks:
							continue
						if chunk in project._finalChunkSet:
							inThisBuild = True
							source = chunk
							used_chunks.add(chunk)
					else:
						inThisBuild = True

					if inThisBuild:
						HandleChildTimeline( idx2, source )

					idx2 += 1
			idx += 1

	def UpdateProjects(self, expandedItem = None):
		updatedProjects = []

		if expandedItem is not None:
			text = str( expandedItem.text(0) )
			if text and text in self.itemToProject:
				updatedProjects = [ self.itemToProject[text] ]
		else:
			for project in _shared_globals.sortedProjects:
				with project.mutex:
					if project.updated or project:
						updatedProjects.append(project)
						project.updated = False

		class SharedLocals(object):
			foundAnError = bool(self.warningErrorCount != 0)

		def drawProgressBar( progressBar, widget, state, startTime, endTime, percent, forFile, warnings, errors ):
			if warnings > 0:
				brush = QtGui.QBrush( QtCore.Qt.darkYellow )
				font = QtGui.QFont()
				font.setBold(True)
				widget.setForeground( 7, brush )
				widget.setFont( 7, font )
			if errors > 0:
				brush = QtGui.QBrush( QtCore.Qt.red )
				font = QtGui.QFont()
				font.setBold(True)
				widget.setForeground( 8, brush )
				widget.setFont( 8, font )

			if ( warnings > 0 or errors > 0 ) and not SharedLocals.foundAnError:
				self.m_buildTree.setCurrentItem(widget)
				if not self.m_pushButton.isChecked():
					self.m_pushButton.setChecked(True)
				SharedLocals.foundAnError = True

			if _shared_globals.ProjectState.BUILDING <= state < _shared_globals.ProjectState.FAILED:
				if not forFile or state != _shared_globals.ProjectState.BUILDING:
					if state == _shared_globals.ProjectState.BUILDING:
						if percent < 1:
							percent = 1
						value = progressBar.value()
						quarter = max( 4.0, (percent - value) / 4.0 )
						if value < percent - quarter:
							progressBar.setValue( value + quarter )
						else:
							progressBar.setValue( percent )
					else:
						progressBar.setValue( percent )
					progressBar.setTextVisible(True)
					if widget.text(1) != str(percent):
						widget.setText(1, str(percent))
				else:
					if widget.text(1) != "0":
						widget.setText(1, "0")

				progressBar.setFormat( "%p%" )

			if state >= _shared_globals.ProjectState.BUILDING:
				widget.setText(7, str(warnings))
				widget.setText(8, str(errors))
				widget.setText(9, time.asctime(time.localtime(startTime)))

			if state == _shared_globals.ProjectState.BUILDING:
				self.animatingBars[progressBar] = ( widget, state, startTime, endTime, percent, forFile, warnings, errors )
				widget.setText(2, "Building")
				if forFile:
					progressBar.setStyleSheet(
						"""
						QProgressBar::chunk
						{{
							background-color: #FF{:02x}00;
						}}
						QProgressBar
						{{
							border: 1px solid black;
							border-radius: 3px;
							padding: 0px;
							text-align: center;
						}}
						""".format(self.pulseColor+127)
					)

					progressBar.setValue( 100 )

					progressBar.setTextVisible(False)
				else:
					progressBar.setStyleSheet(
						"""
						QProgressBar::chunk
						{{
							background-color: #00{:02x}FF;
						}}
						QProgressBar
						{{
							border: 1px solid black;
							border-radius: 3px;
							padding: 0px;
							text-align: center;
						}}
						""".format(self.pulseColor)
					)
			elif state == _shared_globals.ProjectState.LINK_QUEUED:
				if progressBar in self.animatingBars:
					del self.animatingBars[progressBar]
				widget.setText(2,"Link/Queue")
				progressBar.setStyleSheet(
					"""
					QProgressBar::chunk
					{
						background-color: #00C0C0;
					}
					QProgressBar
					{
						border: 1px solid black;
						border-radius: 3px;
						background: #505050;
						padding: 0px;
						text-align: center;
					}
					"""
				)
			elif state == _shared_globals.ProjectState.WAITING_FOR_LINK:
				if progressBar in self.animatingBars:
					del self.animatingBars[progressBar]
				widget.setText(2,"Link/Wait")
				progressBar.setStyleSheet(
					"""
					QProgressBar::chunk
					{
						background-color: #008080;
					}
					QProgressBar
					{
						border: 1px solid black;
						border-radius: 3px;
						background: #505050;
						padding: 0px;
						text-align: center;
					}
					"""
				)
			elif state == _shared_globals.ProjectState.LINKING:
				self.animatingBars[progressBar] = ( widget, state, startTime, endTime, percent, forFile, warnings, errors )
				widget.setText(2, "Linking")
				progressBar.setStyleSheet(
					"""
					QProgressBar::chunk
					{{
						background-color: #00E0{:02x};
					}}
					QProgressBar
					{{
						border: 1px solid black;
						border-radius: 3px;
						background: #505050;
						padding: 0px;
						text-align: center;
						color: black;
					}}
					""".format(self.pulseColor + 64)
				)
			elif state == _shared_globals.ProjectState.FINISHED:
				if progressBar in self.animatingBars:
					del self.animatingBars[progressBar]
				widget.setText(2, "Done!")
				progressBar.setStyleSheet(
					"""
					QProgressBar::chunk
					{{
						background-color: #{};
					}}
					QProgressBar
					{{
						border: 1px solid black;
						border-radius: 3px;
						background: #505050;
						padding: 0px;
						text-align: center;
						color: black;
					}}
					""".format( "ADFFD0" if forFile else "00FF80" )
				)

				widget.setText(10, time.asctime(time.localtime(endTime)))
				timeDiff = endTime - startTime
				minutes = math.floor( timeDiff / 60 )
				seconds = math.floor( timeDiff % 60 )
				widget.setText(11, "{0:2}:{1:02}".format( int(minutes), int(seconds) ) )

			elif state == _shared_globals.ProjectState.FAILED or state == _shared_globals.ProjectState.LINK_FAILED:
				if progressBar in self.animatingBars:
					del self.animatingBars[progressBar]
				progressBar.setTextVisible(True)
				progressBar.setStyleSheet(
					"""
					QProgressBar::chunk
					{
						background-color: #800000;
					}
					QProgressBar
					{
						border: 1px solid black;
						border-radius: 3px;
						background: #505050;
						padding: 0px;
						text-align: center;
					}
					"""
				)
				progressBar.setValue(100)
				if state == _shared_globals.ProjectState.FAILED:
					widget.setText(2, "Failed!")
					progressBar.setFormat("FAILED!")
				else:
					widget.setText(2, "Link Failed!")
					progressBar.setFormat("LINK FAILED!")

				widget.setText(10, time.asctime(time.localtime(endTime)))
				timeDiff = endTime - startTime
				minutes = math.floor( timeDiff / 60 )
				seconds = math.floor( timeDiff % 60 )
				widget.setText(11, "{0:2}:{1:02}".format( int(minutes), int(seconds) ) )

			elif state == _shared_globals.ProjectState.UP_TO_DATE:
				self.SetProgressBarUpToDate( progressBar, widget, endTime, startTime, forFile )

			elif state == _shared_globals.ProjectState.ABORTED:
				if progressBar in self.animatingBars:
					del self.animatingBars[progressBar]
				widget.setText(2, "Aborted!")
				progressBar.setTextVisible(True)
				progressBar.setStyleSheet(
					"""
					QProgressBar::chunk
					{
						background-color: #800040;
					}
					QProgressBar
					{
						border: 1px solid black;
						border-radius: 3px;
						background: #505050;
						padding: 0px;
						text-align: center;
					}
					"""
				)
				progressBar.setValue(100)
				if forFile:
					progressBar.setFormat("ABORTED! (PCH Failed!)")
				else:
					progressBar.setFormat("ABORTED! (Dependency Failed!)")

		if updatedProjects:

			self.m_buildTree.setSortingEnabled(False)

			if self.pulseColor == 0 or self.pulseColor == 128:
				self.pulseUp = not self.pulseUp

			if self.pulseUp:
				self.pulseColor += 32
			else:
				self.pulseColor -= 32

			if self.pulseColor > 128:
				self.pulseColor = 128
			if self.pulseColor < 0:
				self.pulseColor = 0

			selectedWidget = self.m_buildTree.currentItem()

			for project in updatedProjects:
				widget = self.projectToItem[project]
				if not widget:
					continue

				if selectedWidget == widget:
					self.SelectionChanged(selectedWidget, selectedWidget)

				progressBar = self.m_buildTree.itemWidget(widget, 1)

				project.mutex.acquire( )
				complete = project.compilationCompleted
				project.mutex.release( )

				total = len( project._finalChunkSet ) + int(
						project.needsPrecompileC ) + int(
						project.needsPrecompileCpp )
				percent = 100 if total == 0 else ( float(complete) / float(total) ) * 100
				if percent == 100 and project.state < _shared_globals.ProjectState.FINISHED:
					percent = 99

				drawProgressBar( progressBar, widget, project.state, project.startTime, project.endTime, percent, False, project.warnings, project.errors )


				if project.state == _shared_globals.ProjectState.FINISHED or project.state == _shared_globals.ProjectState.UP_TO_DATE:
					self.successfulBuilds.add(project.key)
				elif(
					project.state == _shared_globals.ProjectState.FAILED
					or project.state == _shared_globals.ProjectState.LINK_FAILED
					or project.state == _shared_globals.ProjectState.ABORTED
				):
					self.failedBuilds.add(project.key)

				if widget.isExpanded():
					def HandleChildProgressBar( idx, file ):
						childWidget = widget.child(idx)
						progressBar = self.m_buildTree.itemWidget(childWidget, 1)
						file = os.path.normcase(file)

						project.mutex.acquire( )
						try:
							state = project.fileStatus[file]
						except:
							state = _shared_globals.ProjectState.PENDING

						try:
							startTime = project.fileStart[file]
						except:
							startTime = 0

						try:
							endTime = project.fileEnd[file]
						except:
							endTime = 0

						warnings = 0
						errors = 0

						if file in project.warningsByFile:
							warnings = project.warningsByFile[file]
						if file in project.errorsByFile:
							errors = project.errorsByFile[file]

						project.mutex.release( )

						drawProgressBar( progressBar, childWidget, state, startTime, endTime, 0 if state <= _shared_globals.ProjectState.BUILDING else 100, True, warnings, errors )

						if selectedWidget == childWidget:
							self.SelectionChanged(selectedWidget, selectedWidget)


					idx = 0
					if project.needsPrecompileCpp:
						HandleChildProgressBar( idx, project.cppHeaderFile )
						idx += 1

					if project.needsPrecompileC:
						HandleChildProgressBar( idx, project.cHeaderFile )
						idx += 1

					used_chunks = set()
					for source in project.allsources:
						inThisBuild = False
						if source not in project._finalChunkSet:
							chunk = project.get_chunk( source )
							if not chunk:
								continue

							extension = "." + source.rsplit(".", 1)[1]
							if extension in project.cExtensions:
								extension = ".c"
							else:
								extension = ".cpp"

							chunk = os.path.join( project.csbuildDir, "{}{}".format( chunk, extension ) )

							if chunk in used_chunks:
								continue
							if chunk in project._finalChunkSet:
								inThisBuild = True
								source = chunk
								used_chunks.add(chunk)
						else:
							inThisBuild = True

						if inThisBuild:
							HandleChildProgressBar( idx, source )

						idx += 1

			self.m_buildTree.setSortingEnabled(True)

			successcount = len(self.successfulBuilds)
			failcount = len(self.failedBuilds)

			self.m_successfulBuildsLabel.setText("Successful Builds: {}".format(successcount))
			self.m_failedBuildsLabel.setText("Failed Builds: {}".format(failcount))

			if failcount > 0:
				font = QtGui.QFont()
				font.setBold(True)
				self.m_failedBuildsLabel.setFont( font )
				palette = QtGui.QPalette()
				palette.setColor( self.m_errorLabel.foregroundRole(), QtCore.Qt.red )
				self.m_failedBuildsLabel.setPalette(palette)

			if successcount + failcount == len(_shared_globals.sortedProjects):
				if _shared_globals.profile and not self.readyToClose:
					window = QtGui.QMainWindow(self)
					window.centralWidget = QtGui.QWidget(window)
					window.setCentralWidget(window.centralWidget)
					layout = QtGui.QHBoxLayout(window.centralWidget)

					window.editor = QtGui.QPlainTextEdit(window.centralWidget)
					font = QtGui.QFont()
					font.setFamily("monospace")
					window.editor.setFont(font)
					window.editor.setLineWrapMode(QtGui.QPlainTextEdit.NoWrap)

					layout.addWidget(window.editor)

					summedTimes = {}
					for project in _shared_globals.sortedProjects:
						for filename in project.summedTimes:
							if filename in summedTimes:
								summedTimes[filename] += project.summedTimes[filename]
							else:
								summedTimes[filename] = project.summedTimes[filename]

					builder = StringIO()

					for item in sorted(summedTimes.items(), key=lambda tup: tup[1], reverse=True):
						builder.write("{:f}\t::{}\n".format(item[1], item[0]))

					window.editor.setPlainText(builder.getvalue())

					window.setWindowTitle("Profile Summary")
					window.resize(1275,600)

					window.show()

				self.readyToClose = True
				if _shared_globals.autoCloseGui and failcount == 0:
					self.exiting = True
					self.close()
		if self.animatingBars:
			for bar in self.animatingBars:
				data = self.animatingBars[bar]
				drawProgressBar( bar, *data )


	def retranslateUi(self):
		self.setWindowTitle("CSBuild {}".format(csbuild.__version__.strip()))
		self.m_buildSummaryLabel.setText("Build Started at 00:00... (00:00)")
		self.m_successfulBuildsLabel.setText("Successful Builds: 0")
		self.m_failedBuildsLabel.setText("Failed Builds: 0")
		self.m_warningLabel.setText("Warnings: 0")
		self.m_errorLabel.setText("Errors: 0")
		self.m_treeHeader.setText(0, "#")
		self.m_treeHeader.setText(1, "Progress")
		self.m_treeHeader.setText(2, "Status")
		self.m_treeHeader.setText(3, "Name")
		self.m_treeHeader.setText(4, "Target")
		self.m_treeHeader.setText(5, "Arch")
		self.m_treeHeader.setText(6, "Toolchain")
		self.m_treeHeader.setText(7, "W")
		self.m_treeHeader.setText(8, "E")
		self.m_treeHeader.setText(9, "Build Started")
		self.m_treeHeader.setText(10, "Build Finished")
		self.m_treeHeader.setText(11, "Time")
		self.m_treeHeader.setColumnNumeric(0)
		self.m_treeHeader.setColumnNumeric(1)
		self.m_treeHeader.setColumnNumeric(6)
		self.m_treeHeader.setColumnNumeric(7)

		self.m_buildTree.setColumnWidth( 0, 50 )
		self.m_buildTree.setColumnWidth( 1, 250 )
		self.m_buildTree.setColumnWidth( 2, 75 )
		self.m_buildTree.setColumnWidth( 3, 125 )
		self.m_buildTree.setColumnWidth( 4, 75 )
		self.m_buildTree.setColumnWidth( 5, 75 )
		self.m_buildTree.setColumnWidth( 6, 75 )
		self.m_buildTree.setColumnWidth( 7, 25 )
		self.m_buildTree.setColumnWidth( 8, 25 )
		self.m_buildTree.setColumnWidth( 9, 175 )
		self.m_buildTree.setColumnWidth( 10, 175 )
		self.m_buildTree.setColumnWidth( 11, 50 )

		self.m_timelineHeader.setText(0, "Name")
		self.timelineWidget.setColumnWidth(0,250)

		self.m_treeHeader2.setText(0, "Type")
		self.m_treeHeader2.setText(1, "Output")
		self.m_treeHeader2.setText(2, "File")
		self.m_treeHeader2.setText(3, "Line")
		self.m_treeHeader2.setText(4, "Col")
		self.m_treeHeader2.setColumnNumeric(3)
		self.m_treeHeader2.setColumnNumeric(4)
		self.m_errorTree.setColumnWidth( 0, 50 )
		self.m_errorTree.setColumnWidth( 1, max(250, self.m_errorTree.width() - 350) )
		self.m_errorTree.setColumnWidth( 2, 200 )
		self.m_errorTree.setColumnWidth( 3, 50 )
		self.m_errorTree.setColumnWidth( 4, 50 )

		self.m_filesCompletedLabel.setText("0/0 files compiled")
		self.m_timeLeftLabel.setText("Est. Time Left: 0:00")
		self.m_pushButton.setText(u"▴ Output ▴")

	def onTick(self):
		self.UpdateProjects()
		self.UpdateTimeline(True)
		self.tick += 1

		totalCompletedCompiles = 0
		for project in _shared_globals.sortedProjects:
			totalCompletedCompiles += project.compilationCompleted

		perc = 100 if _shared_globals.total_compiles == 0 else float(totalCompletedCompiles)/float(_shared_globals.total_compiles) * 100
		if perc == 100 and not self.readyToClose:
			perc = 99

		self.m_mainProgressBar.setValue( perc )
		self.m_filesCompletedLabel.setText("{}/{} files compiled".format(totalCompletedCompiles, _shared_globals.total_compiles))

		curtime = time.time( )
		timeDiff = curtime - _shared_globals.starttime
		minutes = math.floor( timeDiff / 60 )
		seconds = math.floor( timeDiff % 60 )

		self.m_buildSummaryLabel.setText("Build Started {0}... ({1}:{2:02})".format( time.asctime(time.localtime(_shared_globals.starttime)), int(minutes), int(seconds) ))

		with _shared_globals.sgmutex:
			warningcount = _shared_globals.warningcount
			errorcount = _shared_globals.errorcount

		self.m_warningLabel.setText("Warnings: {}".format(warningcount))
		self.m_errorLabel.setText("Errors: {}".format(errorcount))

		if warningcount > 0:
			font = QtGui.QFont()
			font.setBold(True)
			self.m_warningLabel.setFont( font )
			palette = QtGui.QPalette()
			palette.setColor( self.m_warningLabel.foregroundRole(), QtCore.Qt.darkYellow )
			self.m_warningLabel.setPalette(palette)

		if errorcount > 0:
			font = QtGui.QFont()
			font.setBold(True)
			self.m_errorLabel.setFont( font )
			palette = QtGui.QPalette()
			palette.setColor( self.m_errorLabel.foregroundRole(), QtCore.Qt.red )
			self.m_errorLabel.setPalette(palette)

		self.warningErrorCount = warningcount + errorcount

		if self.exitRequested:
			self.timer.stop()
			self.close()
		elif self.readyToClose:
			self.timer.stop()

	def closeEvent(self, event):
		if not self.readyToClose:
			answer = QtGui.QMessageBox.question(
				self,
				"Really close?",
				"A compile is still in progress. Closing will cancel it. Are you sure you want to close?",
				QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
				QtGui.QMessageBox.No
			)
			if answer == QtGui.QMessageBox.Yes:
				QMainWindow.closeEvent(self, event)
				self.timer.stop()
				os.kill(os.getpid(), signal.SIGINT)
			else:
				event.ignore()
		else:
			QMainWindow.closeEvent(self, event)
			self.timer.stop()

	def SetProgressBarUpToDate( self, progressBar, widget, endTime, startTime, forFile ):
		if progressBar in self.animatingBars:
			del self.animatingBars[progressBar]
		widget.setText(2, "Up-to-date!")
		progressBar.setTextVisible(True)
		progressBar.setStyleSheet(
			"""
			QProgressBar::chunk
			{{
				background-color: #{};
			}}
			QProgressBar
			{{
				border: 1px solid black;
				border-radius: 3px;
				background: #505050;
				padding: 0px;
				text-align: center;
				color: black;
			}}
			""".format( "ADFFD0" if forFile else "00FF80" )
		)
		progressBar.setValue(100)
		progressBar.setFormat("Up-to-date!")

		if endTime != 0 and startTime != 0:
			widget.setText(10, time.asctime(time.localtime(endTime)))
			timeDiff = endTime - startTime
			minutes = math.floor( timeDiff / 60 )
			seconds = math.floor( timeDiff % 60 )
			widget.setText(11, "{0:2}:{1:02}".format( int(minutes), int(seconds) ) )



class GuiThread( threading.Thread ):
	"""Multithreaded build system, launches a new thread to run the compiler in.
	Uses a threading.BoundedSemaphore object to keep the number of threads equal to the number of processors on the
	machine.
	"""


	def __init__( self ):
		"""Initialize the object. Also handles above-mentioned bug with dummy threads."""
		threading.Thread.__init__( self )
		self.app = None
		#Prevent certain versions of python from choking on dummy threads.
		if not hasattr( threading.Thread, "_Thread__block" ):
			threading.Thread._Thread__block = _shared_globals.dummy_block( )


	def run( self ):
		self.app = QApplication([])
		global lock
		lock.release()
		window = MainWindow()

		window.m_buildTree.setSortingEnabled(False)
		row = 0
		for project in _shared_globals.sortedProjects:
			row += 1
			widgetItem = TreeWidgetItem()
			window.m_buildTree.addTopLevelItem(widgetItem)
			widgetItem.setText(0, str(row))
			widgetItem.setText(1, "1000")
			widgetItem.setText(2, "Pending...")
			widgetItem.setText(3, project.name)
			widgetItem.setToolTip(3, project.name)
			widgetItem.setText(4, project.targetName)
			widgetItem.setToolTip(4, project.targetName)
			widgetItem.setText(5, project.outputArchitecture)
			widgetItem.setToolTip(5, project.outputArchitecture)
			widgetItem.setText(6, project.activeToolchainName)
			widgetItem.setToolTip(6, project.activeToolchainName)
			widgetItem.setText(7, "0")
			widgetItem.setText(8, "0")

			widgetItem2 = TreeWidgetWithBarGraph(window.timelineWidget, window.timelineWidget, False)
			window.timelineWidget.addTopLevelItem(widgetItem2)
			widgetItem2.setText(0, "{} ({} {}/{})".format(project.name, project.targetName, project.outputArchitecture, project.activeToolchainName ))

			window.projectToItem[project] = widgetItem
			window.itemToProject[str(row)] = project

			def AddProgressBar( widgetItem):
				progressBar = QtGui.QProgressBar()

				progressBar.setStyleSheet(
					"""
					QProgressBar::chunk
					{
						background-color: #808080;
					}
					QProgressBar
					{
						background-color: #808080;
						border: 1px solid black;
						border-radius: 3px;
						padding: 0px;
						text-align: center;
					}
					"""
				)

				progressBar.setFormat("Pending...")
				progressBar.setValue(0)
				window.m_buildTree.setItemWidget( widgetItem, 1, progressBar )

			AddProgressBar( widgetItem )

			idx = 0
			font = QtGui.QFont()
			font.setItalic(True)

			if project.needsPrecompileCpp:
				idx += 1
				childItem = TreeWidgetItem( widgetItem )
				childItem.setText(0, "{}.{}".format(row, idx))
				childItem.setText(1, "1000")
				childItem.setText(2, "Pending...")
				childItem.setText(3, os.path.basename(project.cppHeaderFile))
				childItem.setToolTip(3, project.cppHeaderFile)
				childItem.setText(4, project.targetName)
				childItem.setToolTip(4, project.targetName)
				childItem.setText(5, project.outputArchitecture)
				childItem.setToolTip(5, project.outputArchitecture)
				childItem.setText(6, project.activeToolchainName)
				childItem.setToolTip(6, project.activeToolchainName)
				childItem.setText(7, "0")
				childItem.setText(8, "0")

				childItem.setFont(0, font)
				childItem.setFont(1, font)
				childItem.setFont(2, font)
				childItem.setFont(3, font)
				childItem.setFont(4, font)
				childItem.setFont(5, font)
				childItem.setFont(6, font)
				childItem.setFont(7, font)
				childItem.setFont(8, font)
				childItem.setFont(9, font)
				childItem.setFont(10, font)

				AddProgressBar( childItem )

				widgetItem.addChild(childItem)

				timelineChild = TreeWidgetWithBarGraph(widgetItem2, window.timelineWidget, True)
				timelineChild.setText(0, os.path.basename(project.cppHeaderFile))
				timelineChild.setToolTip(0, project.cppHeaderFile)
				widgetItem2.addChild(timelineChild)

				for header in project.cppPchContents:
					subChildItem = TreeWidgetItem( childItem )
					subChildItem.setText( 0, os.path.basename(header) )
					subChildItem.setFirstColumnSpanned(True)
					subChildItem.setToolTip( 0, header )
					childItem.addChild(subChildItem)

					timelineSubChild = TreeWidgetItem(timelineChild)
					timelineSubChild.setText( 0, os.path.basename(header) )
					timelineSubChild.setFirstColumnSpanned(True)
					timelineSubChild.setToolTip( 0, header )
					timelineChild.addChild(timelineSubChild)


			if project.needsPrecompileC:
				idx += 1
				childItem = TreeWidgetItem( widgetItem )
				childItem.setText(0, "{}.{}".format(row, idx))
				childItem.setText(1, "1000")
				childItem.setText(2, "Pending...")
				childItem.setText(3, os.path.basename(project.cHeaderFile))
				childItem.setToolTip(3, project.cHeaderFile)
				childItem.setText(4, project.targetName)
				childItem.setToolTip(4, project.targetName)
				childItem.setText(5, project.outputArchitecture)
				childItem.setToolTip(5, project.outputArchitecture)
				childItem.setText(6, project.activeToolchainName)
				childItem.setToolTip(6, project.activeToolchainName)
				childItem.setText(7, "0")
				childItem.setText(8, "0")

				childItem.setFont(0, font)
				childItem.setFont(1, font)
				childItem.setFont(2, font)
				childItem.setFont(3, font)
				childItem.setFont(4, font)
				childItem.setFont(5, font)
				childItem.setFont(6, font)
				childItem.setFont(7, font)
				childItem.setFont(8, font)
				childItem.setFont(9, font)
				childItem.setFont(10, font)

				AddProgressBar( childItem )

				widgetItem.addChild(childItem)

				timelineChild = TreeWidgetItem(widgetItem2)
				timelineChild.setText(0, os.path.basename(project.cHeaderFile))
				timelineChild.setToolTip(0, project.cHeaderFile)
				widgetItem2.addChild(timelineChild)

				for header in project.cPchContents:
					subChildItem = TreeWidgetItem( childItem )
					subChildItem.setText( 0, os.path.basename(header) )
					subChildItem.setFirstColumnSpanned(True)
					subChildItem.setToolTip( 0, header )
					childItem.addChild(subChildItem)

					timelineSubChild = TreeWidgetItem(timelineChild)
					timelineSubChild.setText( 0, os.path.basename(header) )
					timelineSubChild.setFirstColumnSpanned(True)
					timelineSubChild.setToolTip( 0, header )
					timelineChild.addChild(timelineSubChild)

			used_chunks = set()
			for source in project.allsources:
				inThisBuild = False
				if source not in project._finalChunkSet:
					chunk = project.get_chunk( source )
					if not chunk:
						continue

					extension = "." + source.rsplit(".", 1)[1]
					if extension in project.cExtensions:
						extension = ".c"
					else:
						extension = ".cpp"

					chunk = os.path.join( project.csbuildDir, "{}{}".format( chunk, extension ) )

					if chunk in used_chunks:
						continue
					if chunk in project._finalChunkSet:
						inThisBuild = True
						source = chunk
						used_chunks.add(chunk)
				else:
					inThisBuild = True


				idx += 1
				childItem = TreeWidgetItem( widgetItem )
				childItem.setText(0, "{}.{}".format(row, idx))

				if inThisBuild:
					childItem.setText(1, "1000")
					childItem.setText(2, "Pending...")
				else:
					childItem.setText(1, "100")
					#"Up-to-date!" text gets set by window.SetProgressBarUpToDate

				name = os.path.basename(source)
				if source in project.splitChunks:
					name = "[Split Chunk] {}".format(name)

				childItem.setText(3, name)
				childItem.setToolTip(3, source)
				childItem.setText(4, project.targetName)
				childItem.setToolTip(4, project.targetName)
				childItem.setText(5, project.outputArchitecture)
				childItem.setToolTip(5, project.outputArchitecture)
				childItem.setText(6, project.activeToolchainName)
				childItem.setToolTip(6, project.activeToolchainName)
				childItem.setText(7, "0")
				childItem.setText(8, "0")

				childItem.setFont(0, font)
				childItem.setFont(1, font)
				childItem.setFont(2, font)
				childItem.setFont(3, font)
				childItem.setFont(4, font)
				childItem.setFont(5, font)
				childItem.setFont(6, font)
				childItem.setFont(7, font)
				childItem.setFont(8, font)
				childItem.setFont(9, font)
				childItem.setFont(10, font)

				AddProgressBar( childItem )

				if not inThisBuild:
					window.SetProgressBarUpToDate( window.m_buildTree.itemWidget(childItem, 1), childItem, 0, 0, True )

				widgetItem.addChild(childItem)

				timelineChild = TreeWidgetWithBarGraph(widgetItem2, window.timelineWidget, True)
				timelineChild.setText(0, os.path.basename(source))
				timelineChild.setToolTip(0, source)
				widgetItem2.addChild(timelineChild)

				if source in project.chunksByFile:
					for piece in project.chunksByFile[source]:
						subChildItem = TreeWidgetItem( childItem )
						subChildItem.setText( 0, os.path.basename( piece ) )
						subChildItem.setFirstColumnSpanned(True)
						subChildItem.setToolTip( 0, piece )
						childItem.addChild(subChildItem)

						timelineSubChild = TreeWidgetItem(timelineChild)
						timelineSubChild.setText( 0, os.path.basename(piece) )
						timelineSubChild.setFirstColumnSpanned(True)
						timelineSubChild.setToolTip( 0, piece )
						timelineChild.addChild(timelineSubChild)

		window.m_buildTree.setSortingEnabled(True)

		window.show()
		self.window = window
		self.app.exec_()

	def stop(self):
		self.window.exitRequested = True

_thread = None
lock = threading.Lock()

def run():
	global _thread
	_thread = GuiThread()
	_thread.start()
	lock.acquire()
	lock.acquire()

def stop():
	global _thread
	if _thread:
		_thread.stop()
		_thread.join()
