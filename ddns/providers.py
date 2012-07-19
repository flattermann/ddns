#!/usr/bin/python

# Import all possible exception types.
from .errors import *

class DDNSProvider(object):
	INFO = {
		# A short string that uniquely identifies
		# this provider.
		"handle"    : None,

		# The full name of the provider.
		"name"      : None,

		# A weburl to the homepage of the provider.
		# (Where to register a new account?)
		"website"   : None,

		# A list of supported protocols.
		"protocols" : ["ipv6", "ipv4"],
	}

	DEFAULT_SETTINGS = {}

	def __init__(self, core, **settings):
		self.core = core

		# Copy a set of default settings and
		# update them by those from the configuration file.
		self.settings = self.DEFAULT_SETTINGS.copy()
		self.settings.update(settings)

	def __repr__(self):
		return "<DDNS Provider %s (%s)>" % (self.name, self.handle)

	def __cmp__(self, other):
		return cmp(self.hostname, other.hostname)

	@property
	def name(self):
		"""
			Returns the name of the provider.
		"""
		return self.INFO.get("name")

	@property
	def website(self):
		"""
			Returns the website URL of the provider
			or None if that is not available.
		"""
		return self.INFO.get("website", None)

	@property
	def handle(self):
		"""
			Returns the handle of this provider.
		"""
		return self.INFO.get("handle")

	def get(self, key, default=None):
		"""
			Get a setting from the settings dictionary.
		"""
		return self.settings.get(key, default)

	@property
	def hostname(self):
		"""
			Fast access to the hostname.
		"""
		return self.get("hostname")

	@property
	def username(self):
		"""
			Fast access to the username.
		"""
		return self.get("username")

	@property
	def password(self):
		"""
			Fast access to the password.
		"""
		return self.get("password")

	def __call__(self):
		raise NotImplementedError

	def send_request(self, *args, **kwargs):
		"""
			Proxy connection to the send request
			method.
		"""
		return self.core.system.send_request(*args, **kwargs)

	def get_address(self, proto):
		"""
			Proxy method to get the current IP address.
		"""
		return self.core.system.get_address(proto)


class DDNSProviderNOIP(DDNSProvider):
	INFO = {
		"handle"    : "no-ip.com",
		"name"      : "No-IP",
		"website"   : "http://www.no-ip.com/",
		"protocols" : ["ipv4",]
	}

	# Information about the format of the HTTP request is to be found
	# here: http://www.no-ip.com/integrate/request and
	# here: http://www.no-ip.com/integrate/response

	url = "http://%(username)s:%(password)s@dynupdate.no-ip.com/nic/update?hostname=%(hostname)s&myip=%(address)s"

	def __call__(self):
		url = self.url % {
			"hostname" : self.hostname,
			"username" : self.username,
			"password" : self.password,
			"address"  : self.get_address("ipv4"),
		}

		# Send update to the server.
		response = self.send_request(url)

		# Get the full response message.
		output = response.read()

		# Handle success messages.
		if output.startswith("good") or output.startswith("nochg"):
			return

		# Handle error codes.
		if output == "badauth":
			raise DDNSAuthenticationError
		elif output == "aduse":
			raise DDNSAbuseError
		elif output == "911":
			raise DDNSInternalServerError

		# If we got here, some other update error happened.
		raise DDNSUpdateError


class DDNSProviderSelfhost(DDNSProvider):
	INFO = {
		"handle"    : "selfhost.de",
		"name"      : "Selfhost.de",
		"website"   : "http://www.selfhost.de/",
		"protocols" : ["ipv4",],
	}

	url = "https://carol.selfhost.de/update?username=%(username)s&password=%(password)s&textmodi=1"

	def __call__(self):
		url = self.url % { "username" : self.username, "password" : self.password }

		response = self.send_request(url)

		match = re.search("status=20(0|4)", response.read())
		if not match:
			raise DDNSUpdateError