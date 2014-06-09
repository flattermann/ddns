#!/usr/bin/python
###############################################################################
#                                                                             #
# ddns - A dynamic DNS client for IPFire                                      #
# Copyright (C) 2012 IPFire development team                                  #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU General Public License as published by        #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU General Public License for more details.                                #
#                                                                             #
# You should have received a copy of the GNU General Public License           #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
#                                                                             #
###############################################################################

import logging
import logging.handlers
import ConfigParser

from i18n import _

logger = logging.getLogger("ddns.core")
logger.propagate = 1

from .providers import *
from .system import DDNSSystem

# Setup the logger.
def setup_logging():
	rootlogger = logging.getLogger("ddns")
	rootlogger.setLevel(logging.DEBUG)

	# Setup a logger that logs to syslog.
	#handler = logging.handlers.SysLogHandler(address="/dev/log")

	handler = logging.StreamHandler()
	rootlogger.addHandler(handler)

setup_logging()

class DDNSCore(object):
	def __init__(self, debug=False):
		# In debug mode, enable debug logging.
		if debug:
			logger.setLevel(logging.DEBUG)

		# Initialize the settings array.
		self.settings = {}

		# Dict with all providers, that are supported.
		self.providers = {}
		self.register_all_providers()

		# List of configuration entries.
		self.entries = []

		# Add the system class.
		self.system = DDNSSystem(self)

	def register_provider(self, provider):
		"""
			Registers a new provider.
		"""
		assert issubclass(provider, DDNSProvider)

		provider_handle = provider.INFO.get("handle")
		assert provider_handle

		assert not self.providers.has_key(provider_handle), \
			"Provider '%s' has already been registered" % provider_handle

		provider_name = provider.INFO.get("name")
		assert provider_name

		logger.debug("Registered new provider: %s (%s)" % (provider_name, provider_handle))
		self.providers[provider_handle] = provider

	def register_all_providers(self):
		"""
			Simply registers all providers.
		"""
		for provider in (
			DDNSProviderNOIP,
			DDNSProviderSelfhost,
		):
			self.register_provider(provider)

	def load_configuration(self, filename):
		configs = ConfigParser.SafeConfigParser()
		configs.read([filename,])

		# First apply all global configuration settings.
		for k, v in configs.items("config"):
			self.settings[k] = v

		for entry in configs.sections():
			# Skip the special config section.
			if entry == "config":
				continue

			settings = {}
			for k, v in configs.items(entry):
				settings[k] = v
			settings["hostname"] = entry

			# Get the name of the provider.
			provider = settings.get("provider", None)
			if not provider:
				logger.warning("Entry '%s' lacks a provider setting. Skipping." % entry)
				continue

			# Try to find the provider with the wanted name.
			try:
				provider = self.providers[provider]
			except KeyError:
				logger.warning("Could not find provider '%s' for entry '%s'." % (provider, entry))
				continue

			# Create an instance of the provider object with settings from the
			# configuration file.
			entry = provider(self, **settings)

			# Add new entry to list (if not already exists).
			if not entry in self.entries:
				self.entries.append(entry)

	def updateall(self):
		# If there are no entries, there is nothing to do.
		if not self.entries:
			logger.debug(_("Found no entries in the configuration file. Exiting."))
			return

		# Update them all.
		for entry in self.entries:
			self.update(entry)

	def update(self, entry):
		try:
			entry()

		except DDNSUpdateError, e:
			logger.error(_("Dynamic DNS update for %(hostname)s (%(provider)s) failed:") % \
				{ "hostname" : entry.hostname, "provider" : entry.name })
			logger.error("  %s" % e)

		except Exception, e:
			logger.error(_("Dynamic DNS update for %(hostname)s (%(provider)s) throwed an unhandled exception:") % \
				{ "hostname" : entry.hostname, "provider" : entry.name })
			logger.error("  %s" % e)

		logger.info(_("Dynamic DNS update for %(hostname)s (%(provider)s) successful") % \
			{ "hostname" : entry.hostname, "provider" : entry.name })