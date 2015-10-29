import sys

class DatabaseMigrations(object):
	def __init__(self, config):
		self.config = config

		self.config.do_connect()

	def execute_migrations(self):
		current_version = self.config.get_config_value("db-version")

		# Call all necessary migration functions
		for version in range(current_version + 1, self.config.expected_version + 1):
			method_name = "migration_to_version_{}".format(version)
			if hasattr(self, method_name):
				getattr(self, method_name)()
			else:
				raise Exception("Missing config database migration plan for version {}".format(version))

	def migration_to_version_2(self):
		version = sys._getframe().f_code.co_name.split("_")[-1]
		c = self.config.connection.cursor()
		
		values = [
			"('enable-systray-icon', 1)",
			"('minimize-to-systray', 0)",
			"('close-to-systray', 0)",
			]
		c.execute("INSERT INTO config (name, intval) VALUES {}".format(','.join(values)))

		c.execute("UPDATE config SET intval = :version WHERE name = 'db-version'", {"version": version})

		self.config.connection.commit()
		c.close()

	def migration_to_version_3(self):
		version = sys._getframe().f_code.co_name.split("_")[-1]
		c = self.config.connection.cursor()
		
		values = [
			"('remember-window-position', 0)",
			]
		c.execute("INSERT INTO config (name, intval) VALUES {}".format(','.join(values)))

		c.execute("UPDATE config SET intval = :version WHERE name = 'db-version'", {"version": version})

		self.config.connection.commit()
		c.close()

	def migration_to_version_4(self):
		version = sys._getframe().f_code.co_name.split("_")[-1]
		c = self.config.connection.cursor()
		
		values = [
			"('probe-command-format', '{livestreamer} \"{url}\"')",
			]
		c.execute("INSERT INTO config (name, strval) VALUES {}".format(','.join(values)))

		c.execute("UPDATE config SET intval = :version WHERE name = 'db-version'", {"version": version})

		self.config.connection.commit()
		c.close()
