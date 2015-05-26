import struct

from . import BYTE, SHORT, LONG, LONGLONG

class Scraper(object):
	def __init__(self):
		self._file = None

	def ReadByte(self):
		return struct.unpack("b", self._file.read(BYTE))[0]

	def WriteByte(self, data):
		self._file.write(struct.pack("b", data))

	def ReadChar(self):
		return self._file.read(BYTE)

	def WriteChar(self, data):
		self._file.write(data[0])

	def ReadShort(self):
		return struct.unpack("h", self._file.read(SHORT))[0]

	def WriteShort(self, data):
		self._file.write(struct.pack("h", data))

	def ReadUnsignedShort(self):
		return struct.unpack("H", self._file.read(SHORT))[0]

	def WriteUnsignedShort(self, data):
		self._file.write(struct.pack("H", data))

	def ReadLong(self):
		return struct.unpack("i", self._file.read(LONG))[0]

	def WriteLong(self, data):
		self._file.write(struct.pack("i", data))

	def ReadUnsignedLong(self):
		return struct.unpack("I", self._file.read(LONG))[0]

	def WriteUnsignedLong(self, data):
		self._file.write(struct.pack("I", data))

	def ReadLongLong(self):
		return struct.unpack("q", self._file.read(LONGLONG))[0]

	def WriteLongLong(self, data):
		self._file.write(struct.pack("q", data))

	def ReadUnsignedLongLong(self):
		return struct.unpack("Q", self._file.read(LONGLONG))[0]

	def WriteUnsignedLongLong(self, data):
		self._file.write(struct.pack("Q", data))

	def ReadBytes(self, numBytes):
		return self._file.read(numBytes)

	def WriteBytes(self, data):
		self._file.write(data)

	def SkipBytes(self, bytesToSkip):
		self._file.seek(bytesToSkip, 1)

	def SeekToPosition(self, position):
		self._file.seek(position)

	def GetPosition(self):
		return self._file.tell()

	def Open(self, filename, mode):
		if self._file:
			self._file.close()
		self._file = open(filename, mode)

	def Close(self):
		if self._file:
			self._file.close()

	def RemoveSharedSymbols(self, objectsWithSymbols, objectToScrape):
		pass
