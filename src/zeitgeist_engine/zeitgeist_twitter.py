from zeitgeist_base import Data, DataProvider

try:
	import twitter
except ImportError:
	twitter = None
	print "Twitter support is disabled. Please install python-twitter to enable it."

class TwitterSource(DataProvider):
	"""
	Indexes Twitter statuses.
	"""
	
	def __init__(self):
		# TODO: Store the user's username and password using GNOME Keychain.
		DataProvider.__init__(self, uri="gzg/twitter", name="Twitter")
		self.username = ""
		self.password = ""
		self.comment = " tweets to Twitter"
		
	def get_icon_static(self,icon_size):
		loc = glob.glob(os.path.expanduser("~/.Zeitgeist/twitter.png"))
		self.icon = gtk.gdk.pixbuf_new_from_file_at_size(loc[0], -1, int(24))
		
	def get_items_uncached(self):
		# If twitter isn't installed or if we don't have a username and password
		if twitter is None or username=="" or password="":
			return
		
		# Connect to twitter, loop over statuses, and create items for each status
		self.api = twitter.Api(username=self.username, password=self.password)
		for status in self.api.GetUserTimeline(count = 500):
			yield Data(type = "Twitter",
						icon = None, count=0, use="tweet",
						name = tweet.user.name + ":\n" + tweet.text,
						timestamp = tweet.created_at_in_seconds,
						uri = "http://explore.twitter.com/" + tweet.user.screen_name + "/status/" + str(tweet.id))