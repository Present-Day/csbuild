
class Plugin(object):
	def prePrepareBuildStep( self, project ):
		pass

	def postPrepareBuildStep( self, project ):
		pass

	def preMakeStep( self, project ):
		pass

	def postMakeStep( self, project ):
		pass

	def preBuildStep( self, project ):
		pass

	def postBuildStep( self, project ):
		pass

	def preLinkStep( self, project ):
		pass

	@staticmethod
	def globalPostMakeStep():
		pass

	@staticmethod
	def globalPreMakeStep():
		pass
