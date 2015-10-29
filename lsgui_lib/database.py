import sqlite3
import os.path
import shutil
from datetime import datetime
from .constants import CONFIGFILE
from .database_migrations import DatabaseMigrations

class Config(object):
	"""Reads and writes config data to an SQLite database."""
	INITIAL_DBVERSION = 1

	connection = None

	def __init__(self, dbversion):
		self.expected_version = dbversion

		do_db_init = False
		if not os.path.exists(CONFIGFILE):
			do_db_init = True

		self.do_connect()

		if not do_db_init:
			c = self.connection.cursor()
			# Vacuum the database
			c.execute("VACUUM")
			# Gather new statistics
			c.execute("ANALYZE")
			c.close()

		if do_db_init:
			try:
				self.init_db()
			except:
				os.remove(CONFIGFILE)
				raise

		# Clean cache
		self.clean_quality_cache()

	def do_connect(self):
		if self.connection is None:
			self.connection = sqlite3.connect(CONFIGFILE, detect_types=sqlite3.PARSE_DECLTYPES, isolation_level="DEFERRED")
			self.connection.row_factory = sqlite3.Row

			# Set some pragma
			c = self.connection.cursor()
			c.execute("PRAGMA foreign_keys = ON")
			c.close()

	def make_database_backup(self):
		# Disconnect from the database before copying the file
		self.connection.close()
		self.connection = None

		backup_file = "{}.{}.backup".format(os.path.splitext(CONFIGFILE)[0], datetime.now().strftime("%Y%m%d_%H%M%S"))
		shutil.copy(CONFIGFILE, backup_file)

		# Reconnect to the database before returning
		self.do_connect()
		return backup_file

	def init_db(self):
		"""Initializes the database."""
		self.init_config_tables()
		self.init_streamer_tables()
		self.init_cache_tables()

		self.execute_migration()

	def init_config_tables(self):
		c = self.connection.cursor()
		# Create the config table
		c.execute("CREATE TABLE config (name TEXT PRIMARY KEY, intval INTEGER, strval TEXT)")

		c.execute("BEGIN")
		# Populate the config table with integer data
		c.execute("INSERT INTO config (name, intval) VALUES ('db-version', :version)", {"version": self.INITIAL_DBVERSION})
		values = [
			"('is-configured', 0)",
			"('root-width', 800)",
			"('root-height', 400)",
			"('root-xoffset', 0)",
			"('root-yoffset', 0)",
			"('quality-cache-persistance', 1440)", # Value is in minutes!
			"('auto-refresh-quality', 0)",
			]
		c.execute("INSERT INTO config (name, intval) VALUES {}".format(','.join(values)))

		# Populate the config table with string data
		values = [
			"('command-format', '{livestreamer} --player=\"{player}\" \"{url}\" \"{quality}\"')",
			"('livestreamer-path', '')",
			"('player-path', '')",
			"('timestamp-format', '[%H:%M:%S]')",
			"('foreground-color', '#fbff00')",
			"('background-color', '#4646d9')",
			"('button-foreground-favorite', '#FF4F4F')",
			"('button-foreground-edit', '#0E38F0')",
			"('button-foreground-add', '#5EBF3B')",
			"('button-foreground-delete', '#BD0B0E')",
			]
		c.execute("INSERT INTO config (name, strval) VALUES {}".format(','.join(values)))
		self.connection.commit()
		c.close()

	def init_streamer_tables(self):
		c = self.connection.cursor()

		# Create the streamer and channel tables
		c.execute("CREATE TABLE streamer (id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, icon TEXT NOT NULL, favorite BOOLEAN NOT NULL DEFAULT 0)")
		c.execute("CREATE UNIQUE INDEX streamer_name ON streamer(name)")
		c.execute("CREATE TABLE channel (id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, favorite BOOLEAN NOT NULL DEFAULT 0, streamer_id INTEGER NOT NULL, FOREIGN KEY (streamer_id) REFERENCES streamer(id))")
		c.execute("CREATE UNIQUE INDEX channel_unique_name_url ON channel(streamer_id, name, url)")
		c.execute("CREATE UNIQUE INDEX channel_unique_name ON channel(streamer_id, name)")
		c.execute("CREATE UNIQUE INDEX channel_unique_url ON channel(streamer_id, url)")
		c.execute("CREATE INDEX channel_streamer_id ON channel(streamer_id)")
		
		c.execute("BEGIN")
		# Add streamers
		c.execute("INSERT INTO streamer VALUES (null, 'twitch.tv', 'http://www.twitch.tv', 'twitch.gif', 1)")
		# c.execute("INSERT INTO streamer VALUES (null, 'Youtube', 'https://www.youtube.com/something', 'youtube.gif', 0)")
		self.connection.commit()

		c.close()

	def init_cache_tables(self):
		c = self.connection.cursor()

		# Create cache table for stream qualities, so there will be no need for constant probing
		c.execute("CREATE TABLE quality_cache (streamer_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, name TEXT NOT NULL, FOREIGN KEY (channel_id) REFERENCES channel(id), PRIMARY KEY (streamer_id, channel_id, name))")

		c.close()

	def get_config_value(self, name):
		"""Gets the value of a named config option. The return is either an integer or a string."""
		c = self.connection.cursor()
		c.execute("SELECT intval, strval FROM config WHERE name = :name", {"name": name})
		row = c.fetchone()
		c.close()
		if row is None:
			return
		if row['intval'] is not None:
			return row['intval']
		else:
			return row['strval']

	def set_config_value(self, name, value):
		"""Sets an existing config option's value. Be sure to use the correct type!"""
		c = self.connection.cursor()
		s = ["UPDATE config SET"]
		if type(value) is int:
			s.append("intval")
		else:
			s.append("strval")
		s.append("= :value WHERE name = :name")
		c.execute("BEGIN")
		c.execute(' '.join(s), {"name": name, "value": value})
		self.connection.commit()
		c.close()

	def get_streamer(self, name):
		c = self.connection.cursor()
		c.execute("SELECT * FROM streamer WHERE name = :name", {"name": name})
		row = c.fetchone()
		c.close()
		return row

	def get_streamers(self, only_favorite=False):
		"""Gets all streamers or only the favorite one."""
		c = self.connection.cursor()
		s = ["SELECT * FROM streamer"]
		if only_favorite:
			s.append("WHERE favorite")
		s.append("ORDER BY name")
		c.execute(' '.join(s))
		rows = c.fetchall()
		c.close()
		return rows[0] if only_favorite else rows

	def get_streamer_channel(self, streamer_name, channel_name):
		c = self.connection.cursor()
		c.execute("SELECT * FROM channel WHERE streamer_id = (SELECT streamer_id FROM streamer WHERE name = :streamer_name LIMIT 1) AND name = :channel_name", {"streamer_name": streamer_name, "channel_name": channel_name})
		row = c.fetchone()
		c.close()
		return row

	def get_streamer_channels(self, streamer_name):
		c = self.connection.cursor()
		c.execute("SELECT * FROM channel WHERE streamer_id = (SELECT id FROM streamer WHERE name = :streamer_name LIMIT 1)", {"streamer_name": streamer_name})
		rows = c.fetchall()
		c.close()
		return rows

	def get_channel_id(self, streamer_name, channel_name):
		c = self.connection.cursor()
		c.execute("SELECT id FROM channel WHERE streamer_id = (SELECT id FROM streamer WHERE name = :streamer_name LIMIT 1) AND name = :channel_name", {"channel_name": channel_name, "streamer_name": streamer_name})
		row = c.fetchone()
		c.close()
		return row["id"] if row else None

	def add_quality_to_cache(self, streamer_name, channel_name, stream_qualities):
		streamer_id = self.get_streamer(streamer_name)["id"]
		channel_id = self.get_channel_id(streamer_name, channel_name)
		c = self.connection.cursor()
		c.execute("BEGIN")
		for name in stream_qualities:
			c.execute("INSERT INTO quality_cache (streamer_id, channel_id, name) VALUES (:streamer_id, :channel_id, :name)", {"streamer_id": streamer_id, "channel_id": channel_id, "name": name})
		self.connection.commit()
		c.close()

	def get_quality_from_cache(self, streamer_name, channel_name):
		streamer_id = self.get_streamer(streamer_name)["id"]
		channel_id = self.get_channel_id(streamer_name, channel_name)
		cache_live_time = self.get_config_value("quality-cache-persistance")
		c = self.connection.cursor()
		c.execute("SELECT name FROM quality_cache WHERE streamer_id = :streamer_id AND channel_id = :channel_id AND timestamp > datetime(CURRENT_TIMESTAMP, '-' || :cache_live_time || ' minutes')", {"streamer_id": streamer_id, "channel_id": channel_id, "cache_live_time": cache_live_time})
		streams = []
		for row in c:
			streams.append(row["name"])
		c.close()
		return streams

	def clean_quality_cache(self, streamer_name=None, channel_name=None, ignore_timestamp=False):
		if channel_name is not None and streamer_name is not None:
			channel_id = self.get_channel_id(streamer_name, channel_name)
			streamer_id = self.get_streamer(streamer_name)["id"]
		else:
			channel_id = None
			streamer_id = None
		cache_live_time = self.get_config_value("quality-cache-persistance")
		c = self.connection.cursor()
		c.execute("BEGIN")
		s = ["DELETE FROM quality_cache"]
		if not ignore_timestamp:
			if len(s) == 1:
				s.append("WHERE")
			s.append("timestamp < datetime(CURRENT_TIMESTAMP, '-' || :cache_live_time || ' minutes')")
		if streamer_id is not None and channel_id is not None:
			if len(s) == 1:
				s.append("WHERE")
			else:
				s.append("AND")
			s.append("streamer_id = :streamer_id AND channel_id = :channel_id")
		c.execute(' '.join(s), {"streamer_id": streamer_id, "channel_id": channel_id, "cache_live_time": cache_live_time})
		self.connection.commit()
		c.close()

	def set_favorite_streamer(self, streamer_name):
		c = self.connection.cursor()
		c.execute("BEGIN")
		c.execute("UPDATE streamer SET favorite = 0")
		c.execute("UPDATE streamer SET favorite = 1 WHERE name = :streamer_name", {"streamer_name": streamer_name})
		self.connection.commit()
		c.close()

	def set_favorite_channel(self, streamer_name, channel_name):
		channel_id = self.get_channel_id(streamer_name, channel_name)
		c = self.connection.cursor()
		c.execute("BEGIN")
		c.execute("UPDATE channel SET favorite = 0 WHERE streamer_id = (SELECT id FROM streamer WHERE name = :streamer_name LIMIT 1)", {"streamer_name": streamer_name})
		c.execute("UPDATE channel SET favorite = 1 WHERE id = :channel_id AND streamer_id = (SELECT id FROM streamer WHERE name = :streamer_name LIMIT 1)", {"streamer_name": streamer_name, "channel_id": channel_id})
		self.connection.commit()
		c.close()

	def get_channel_by_url(self, streamer_name, url):
		c = self.connection.cursor()
		c.execute("SELECT * FROM channel WHERE streamer_id = (SELECT id FROM streamer WHERE name = :streamer_name LIMIT 1) AND url = :url", {"streamer_name": streamer_name, "url":url})
		row = c.fetchone()
		c.close()
		return row

	def add_new_channel(self, streamer_name, channel_name, url, favorite):
		self.add_update_channel(streamer_name, channel_name, url, favorite, op="add")

	def update_existing_channel(self, streamer_name, channel_name, url, favorite, old_name, old_url):
		self.add_update_channel(streamer_name, channel_name, url, favorite, old_name, old_url, op="update")

	def delete_channel(self, streamer_name, channel_name):
		"""Removes the channel from the database."""
		streamer = self.get_streamer(streamer_name)
		channel_id = self.get_channel_id(streamer_name, channel_name)
		c = self.connection.cursor()
		c.execute("BEGIN")
		c.execute("DELETE FROM quality_cache WHERE streamer_id = :streamer_id AND channel_id = :channel_id", {"streamer_id": streamer["id"], "channel_id": channel_id})
		c.execute("DELETE FROM channel WHERE streamer_id = :streamer_id AND name = :channel_name", {"streamer_id": streamer["id"], "channel_name": channel_name})
		self.connection.commit()
		c.close()

	def add_update_channel(self, streamer_name, channel_name, url, favorite, old_name=None, old_url=None, op="add"):
		streamer = self.get_streamer(streamer_name)
		c = self.connection.cursor()
		c.execute("BEGIN")
		if op == "add":
			c.execute("INSERT INTO channel (name, url, streamer_id) VALUES (:name, :url, :streamer_id)", {
				"name": channel_name.strip(),
				"url": url.strip(),
				"streamer_id": streamer["id"],
				})
		else:
			c.execute("UPDATE channel SET name = :name, url = :url, favorite = 0 WHERE streamer_id = :streamer_id AND name = :old_name AND url = :old_url", {
				"name": channel_name.strip(),
				"url": url.strip(),
				"streamer_id": streamer["id"],
				"old_name": old_name,
				"old_url": old_url,
				})
		self.connection.commit()
		c.close()

		if favorite:
			self.set_favorite_channel(streamer_name, channel_name)

	def is_migration_needed(self):
		return self.get_config_value("db-version") < self.expected_version

	def execute_migration(self):
		dm = DatabaseMigrations(self)
		dm.execute_migrations()
