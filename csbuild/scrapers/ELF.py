from . import scraper

from . import BYTE, SHORT, LONG, LONGLONG

class ElfClass:
	cNone = 0
	c32 = 1
	c64 = 2

class ELFScraper(scraper.Scraper):
	def __init__(self):
		scraper.Scraper.__init__(self)
		self._scrapeLocations = {}
		self._header = None

	def RemoveSharedSymbols(self, objectsWithSymbols, objectToScrape):
		for object in objectsWithSymbols:
			self._collectSymbols(object)
		self._eraseSymbols(objectToScrape)

	def _readHeader(self):
		magic = b'';
		self.SkipBytes(1);
		magic += self.ReadChar()
		magic += self.ReadChar()
		magic += self.ReadChar()
		assert(magic == b'ELF')

		class Header(object):
			def __init__(self, scraper):
				self.cls = scraper.ReadByte()

				scraper.SkipBytes(11)
				scraper.SkipBytes(SHORT + SHORT + LONG)

				if self.cls == ElfClass.c32:
					scraper.SkipBytes(LONG + LONG)
					self.shoff = scraper.ReadLong()
				else:
					scraper.SkipBytes(LONGLONG + LONGLONG)
					self.shoff = scraper.ReadLongLong()

				scraper.SkipBytes(LONG + SHORT + SHORT + SHORT + SHORT)
				self.shnum = scraper.ReadShort()
				self.shstrndx = scraper.ReadShort()

		return Header(self)

	def _readSections(self, header):
		sections = []
		class Section(object):
			def __init__(self, scraper):
				self.nameOffset = scraper.ReadLong()
				self.name = b''
				self.type = scraper.ReadLong()

				if header.cls == ElfClass.c32:
					self.flags = scraper.ReadLong()
					self.addr = scraper.ReadLong()
					self.offset = scraper.ReadLong()
					self.size = scraper.ReadLong()
				else:
					self.flags = scraper.ReadLongLong()
					self.addr = scraper.ReadLongLong()
					self.offset = scraper.ReadLongLong()
					self.size = scraper.ReadLongLong()

				self.link = scraper.ReadLong()
				self.info = scraper.ReadLong()

				if header.cls == ElfClass.c32:
					self.addralign = scraper.ReadLong()
					self.entsize = scraper.ReadLong()
				else:
					self.addralign = scraper.ReadLongLong()
					self.entsize = scraper.ReadLongLong()

				self.data = None

		for i in range(header.shnum):
			sections.append(Section(self))

		for i in range(header.shnum):
			self.SeekToPosition(sections[header.shstrndx].offset + sections[i].nameOffset)
			oneChar = self.ReadChar()
			while oneChar != '\0':
				sections[i].name += oneChar
				oneChar = self.ReadChar()
			if sections[i].name == ".strtab":
				symStrSection = sections[i]

		return sections, symStrSection

	def _collectSymbols(self, object):
		self.Open(object, "rb")

		header = self._readHeader()

		self.SeekToPosition(header.shoff)

		sections, symStrSection = self._readSections(header)

		for i in range(header.shnum):
			if sections[i].type == 2:
				self.SeekToPosition(sections[i].offset)
				while self.GetPosition() - sections[i].offset < sections[i].size:
					pos = self.GetPosition()
					if header.cls == ElfClass.c32:
						nameOffset = self.ReadLong()
						value = self.ReadLong()
						size = self.ReadLong()
						info = self.ReadByte()
						other = self.ReadByte()
						shndx = self.ReadShort()
					else:
						nameOffset = self.ReadLong()
						info = self.ReadByte()
						other = self.ReadByte()
						shndx = self.ReadShort()
						value = self.ReadLongLong()
						size = self.ReadLongLong()
				
					pos = self.GetPosition()
					self.SeekToPosition(symStrSection.offset + nameOffset)
					name = b''
					oneChar = self.ReadChar()
					while oneChar != '\0':
						name += oneChar
						oneChar = self.ReadChar()
					if info == 17 or info == 18:
						self._scrapeLocations[name] = pos
					self.SeekToPosition(pos)
		self.Close()

	def _eraseSymbols(self, object):
		self.Open(object, "rb+")

		header = self._readHeader()

		self.SeekToPosition(header.shoff)

		sections, symStrSection = self._readSections(header)

		for i in range(header.shnum):
			if sections[i].type == 2:
				self.SeekToPosition(sections[i].offset)
				while self.GetPosition() - sections[i].offset < sections[i].size:
					startpos = self.GetPosition()
					if header.cls == ElfClass.c32:
						nameOffset = self.ReadLong()
						value = self.ReadLong()
						size = self.ReadLong()
						info = self.ReadByte()
						other = self.ReadByte()
						shndx = self.ReadShort()
					else:
						nameOffset = self.ReadLong()
						info = self.ReadByte()
						other = self.ReadByte()
						shndx = self.ReadShort()
						value = self.ReadLongLong()
						size = self.ReadLongLong()
				
					pos = self.GetPosition()
					self.SeekToPosition(symStrSection.offset + nameOffset)
					name = b''
					oneChar = self.ReadChar()
					while oneChar != '\0':
						name += oneChar
						oneChar = self.ReadChar()
					
					if name in self._scrapeLocations:
						self.SeekToPosition(startpos + LONG)
						
						if header.cls == ElfClass.c32:
							self.WriteLong(0)
							self.WriteLong(0)
							self.WriteByte(16)
							self.WriteByte(0)
							self.WriteShort(0)
						else:
							self.WriteByte(16)
							self.WriteByte(0)
							self.WriteShort(0)
							self.WriteLongLong(0)
							self.WriteLongLong(0)
					self.SeekToPosition(pos)
		self.Close()					

