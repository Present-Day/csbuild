from . import scraper
import struct
import time

from . import BYTE, SHORT, LONG, LONGLONG
from .. import log

class SymbolClass:
	STATIC = 2
	EXTERNAL = 3

class Section:
	UNDEFINED = 0

class FileType:
	UNKNOWN = 0
	COFF = 1
	XCOFF = 2

class SymbolType:
	FUNCTION = 0x20

class MachineType:
	X64 = 0x8664
	Win32 = 0x14c

class COFFScraper(scraper.Scraper):
	def __init__(self):
		scraper.Scraper.__init__(self)
		self._type = FileType.UNKNOWN
		self._symPtr = 0
		self._numSyms = 0
		self._stringPtr = 0
		self._symSize = 0

		self._comdatSections = set()
		self._dataSections = set()

		self._symsToScrape = set()

	def RemoveSharedSymbols(self, objectsWithSymbols, objectToScrape):
		for object in objectsWithSymbols:
			self._collectSymbols(object)
		self._eraseSymbols(objectToScrape)

	@staticmethod
	def CreateEmptyCOFFObject(machine, name):
		with open(name, "wb") as f:
			f.write(struct.pack("Hhlllhhl", machine, 0, 0, 0x14, 0, 0, 0, 4))

	@staticmethod
	def CreateEmptyXCOFFObject(machine, name):
		with open(name, "wb") as f:
			#00ff0200, machine, timestamp
			f.write(struct.pack("hhhHl", 0, -1, 2, machine, 0))
			#32 bytes unknown data...
			#TODO: This is being copied directly from existing XCOFF files that all seem to have the same data.
			#There's no documentation on this format to know what goes here, it would be nice to figure it out some day
			f.write(struct.pack("LLLLLLLL", 0xD1BAA1C7, 0x4BA9BAEE, 0xF6FA20AF, 0xB8DCA46A, 0, 0, 0, 0))
			#num sections, pointer to symbol table, num symbols, padding, size of string table
			f.write(struct.pack("llhhl", 0, 0x38, 0, 0, 4))

	def Close(self):
		scraper.Scraper.Close(self)
		self._type = FileType.UNKNOWN
		self._symPtr = 0
		self._numSyms = 0
		self._stringPtr = 0
		self._symSize = 0

		self._comdatSections = set()
		self._dataSections = set()


	def _readHeader(self):
		zeroes, ones = self.ReadShort(), self.ReadShort()
		if zeroes == 0 and ones == -1:
			self.SeekToPosition(SHORT * 3)
			machine = self.ReadUnsignedShort()
		else:
			machine = zeroes
			#ignore ones

		if machine == MachineType.X64:
			self._type = FileType.XCOFF
			self.SkipBytes(LONG * 10)

			self._symSize = 20
		elif machine == MachineType.Win32:
			self._type = FileType.COFF
			self.SkipBytes(LONG)

			self._symSize = 18
		self._symPtr = self.ReadLong()
		self._numSyms = self.ReadLong()
		self._stringPtr = self._symPtr + (self._numSyms * self._symSize)

	def _readSymbol(self):
		name, ptrData = self._readSymbolName()
		value = self.ReadLong()
		if self._type == FileType.XCOFF:
			section = self.ReadLong()
		else:
			section = self.ReadShort()
		symType = self.ReadShort()
		symbolClass = self.ReadByte()
		numAux = self.ReadByte()
		return name, ptrData, value, section, symType, symbolClass, numAux

	def _readSymbolName(self):
		bytes = self.ReadBytes(8)
		ptrData = struct.unpack("LL", bytes)
		return bytes, ptrData

	def _resolveSymbolName(self, name, ptrData):
		if ptrData[0] == 0:
			pos = self.GetPosition()
			self.SeekToPosition(self._stringPtr + ptrData[1])
			name = b''
			oneChar = self.ReadChar()
			while oneChar != '\0':
				name += oneChar
				oneChar = self.ReadChar()
			self.SeekToPosition(pos)
		return name

	def _checkForCOMDAT(self, section):
		self.SkipBytes(14)
		selection = self.ReadByte()
		if self._type == FileType.XCOFF:
			self.SkipBytes(5)
		else:
			self.SkipBytes(3)
		if selection != 0:
			self._comdatSections.add(section)

	def _skipSymbols(self, numToSkip):
		self.SkipBytes(self._symSize * numToSkip)

	@staticmethod
	def _isDataSection(name):
		return name == b'.bss\0\0\0\0' or name == b'.data\0\0\0'

	def _collectSymbols(self, object):
		self.Open(object, "rb")
		self._readHeader()
		self.SeekToPosition(self._symPtr)

		i = 0
		numSyms = self._numSyms
		while i < numSyms:
			name, ptrData, value, section, symType, symbolClass, numAux = self._readSymbol()

			if value == 0 and numAux != 0:
				self._checkForCOMDAT(section)
				numAux -= 1
				i += 1

			if COFFScraper._isDataSection(name):
				self._dataSections.add(section)
			elif symbolClass == SymbolClass.STATIC and section is not Section.UNDEFINED and section not in self._comdatSections and ( symType == SymbolType.FUNCTION or section in self._dataSections ):
				name = self._resolveSymbolName(name, ptrData)
				self._symsToScrape.add(name)

			self._skipSymbols(numAux)
			i += numAux + 1

		self.Close()

	def _eraseSymbols(self, object):
		self.Open(object, "rb+")
		self._readHeader()
		self.SeekToPosition(self._symPtr)

		i = 0
		scrapedASymbol = False
		numSyms = self._numSyms
		while i < numSyms:
			name, ptrData, value, section, symType, symbolClass, numAux = self._readSymbol()

			if value == 0 and numAux != 0:
				self._checkForCOMDAT(section)
				numAux -= 1
				i += 1

			if COFFScraper._isDataSection(name):
				self._dataSections.add(section)
			elif symbolClass == SymbolClass.STATIC and section is not Section.UNDEFINED and section not in self._comdatSections and ( symType == SymbolType.FUNCTION or section in self._dataSections ):
				name = self._resolveSymbolName(name, ptrData)
				if name in self._symsToScrape:
					log.LOG_INFO("Scraping symbol {}".format(name))
					scrapedASymbol = True
					pos = self.GetPosition()
					if self._type == FileType.XCOFF:
						self.SeekToPosition(pos - 12)
					else:
						self.SeekToPosition(pos - 10)

					#Value
					self.WriteLong(0)
					#Section
					self.WriteShort(Section.UNDEFINED)

					self.SeekToPosition(pos)

			self._skipSymbols(numAux)
			i += numAux + 1

		if scrapedASymbol:
			#Update timestamp so incremental link re-parses this object
			if self._type == FileType.COFF:
				self.SeekToPosition(SHORT + SHORT)
			else:
				self.SeekToPosition(LONG + LONG)

			self.WriteLong(int(time.time()))

		self.Close()
