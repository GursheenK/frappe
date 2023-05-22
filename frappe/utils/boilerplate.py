# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import contextlib
import glob
import json
import os
import pathlib
import re
import textwrap

import click
import git

import frappe
from frappe.utils import touch_file

APP_TITLE_PATTERN = re.compile(r"^(?![\W])[^\d_\s][\w -]+$", flags=re.UNICODE)


def make_boilerplate(dest, app_name, no_git=False):
	if not os.path.exists(dest):
		print("Destination directory does not exist")
		return

	# app_name should be in snake_case
	app_name = frappe.scrub(app_name)
	hooks = _get_user_inputs(app_name)
	_create_app_boilerplate(dest, hooks, no_git=no_git)


def _get_user_inputs(app_name):
	"""Prompt user for various inputs related to new app and return config."""
	app_name = frappe.scrub(app_name)

	hooks = frappe._dict()
	hooks.app_name = app_name
	app_title = hooks.app_name.replace("_", " ").title()

	new_app_config = {
		"app_title": {
			"prompt": "App Title",
			"default": app_title,
			"validator": is_valid_title,
		},
		"app_description": {"prompt": "App Description"},
		"app_publisher": {"prompt": "App Publisher"},
		"app_email": {"prompt": "App Email"},
		"app_license": {"prompt": "App License", "default": "MIT"},
		"create_github_workflow": {
			"prompt": "Create GitHub Workflow action for unittests",
			"default": False,
			"type": bool,
		},
	}

	for property, config in new_app_config.items():
		value = None
		input_type = config.get("type", str)

		while value is None:
			if input_type == bool:
				value = click.confirm(config["prompt"], default=config.get("default"))
			else:
				value = click.prompt(config["prompt"], default=config.get("default"), type=input_type)

			if validator_function := config.get("validator"):
				if not validator_function(value):
					value = None
		hooks[property] = value

	return hooks


def is_valid_title(title) -> bool:
	if not APP_TITLE_PATTERN.match(title):
		print(
			"App Title should start with a letter and it can only consist of letters, numbers, spaces and underscores"
		)
		return False
	return True


def _create_app_boilerplate(dest, hooks, no_git=False):
	frappe.create_folder(
		os.path.join(dest, hooks.app_name, hooks.app_name, frappe.scrub(hooks.app_title)),
		with_init=True,
	)
	frappe.create_folder(
		os.path.join(dest, hooks.app_name, hooks.app_name, "templates"), with_init=True
	)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "www"))
	frappe.create_folder(
		os.path.join(dest, hooks.app_name, hooks.app_name, "templates", "pages"), with_init=True
	)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "templates", "includes"))
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "config"), with_init=True)
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "public", "css"))
	frappe.create_folder(os.path.join(dest, hooks.app_name, hooks.app_name, "public", "js"))

	# add .gitkeep file so that public folder is committed to git
	# this is needed because if public doesn't exist, bench build doesn't symlink the apps assets
	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "public", ".gitkeep"), "w") as f:
		f.write("")

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "__init__.py"), "w") as f:
		f.write(frappe.as_unicode(init_template))

	with open(os.path.join(dest, hooks.app_name, "MANIFEST.in"), "w") as f:
		f.write(frappe.as_unicode(manifest_template.format(**hooks)))

	with open(os.path.join(dest, hooks.app_name, "requirements.txt"), "w") as f:
		f.write("# frappe -- https://github.com/frappe/frappe is installed via 'bench init'")

	with open(os.path.join(dest, hooks.app_name, "README.md"), "w") as f:
		f.write(
			frappe.as_unicode(
				"## {}\n\n{}\n\n#### License\n\n{}".format(
					hooks.app_title, hooks.app_description, hooks.app_license
				)
			)
		)

	with open(os.path.join(dest, hooks.app_name, "license.txt"), "w") as f:
		f.write(frappe.as_unicode("License: " + hooks.app_license))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "modules.txt"), "w") as f:
		f.write(frappe.as_unicode(hooks.app_title))

	# These values could contain quotes and can break string declarations
	# So escaping them before setting variables in setup.py and hooks.py
	for key in ("app_publisher", "app_description", "app_license"):
		hooks[key] = hooks[key].replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

	with open(os.path.join(dest, hooks.app_name, "setup.py"), "w") as f:
		f.write(frappe.as_unicode(setup_template.format(**hooks)))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "hooks.py"), "w") as f:
		f.write(frappe.as_unicode(hooks_template.format(**hooks)))

	with open(os.path.join(dest, hooks.app_name, hooks.app_name, "patches.txt"), "w") as f:
		f.write(frappe.as_unicode(patches_template.format(**hooks)))

	app_directory = os.path.join(dest, hooks.app_name)

	if hooks.create_github_workflow:
		_create_github_workflow_files(dest, hooks)

	if not no_git:
		with open(os.path.join(dest, hooks.app_name, ".gitignore"), "w") as f:
			f.write(frappe.as_unicode(gitignore_template.format(app_name=hooks.app_name)))

		# initialize git repository
		app_repo = git.Repo.init(app_directory, initial_branch="develop")
		app_repo.git.add(A=True)
		app_repo.index.commit("feat: Initialize App")

	print(f"'{hooks.app_name}' created at {app_directory}")


def _create_github_workflow_files(dest, hooks):
	workflows_path = pathlib.Path(dest) / hooks.app_name / ".github" / "workflows"
	workflows_path.mkdir(parents=True, exist_ok=True)

	ci_workflow = workflows_path / "ci.yml"
	with open(ci_workflow, "w") as f:
		f.write(github_workflow_template.format(**hooks))


PATCH_TEMPLATE = textwrap.dedent(
	'''
	import frappe

	def execute():
		"""{docstring}"""

		# Write your patch here.
		pass
'''
)


class PatchCreator:
	def __init__(self):
		self.all_apps = frappe.get_all_apps(sites_path=".", with_internal_apps=False)

		self.app = None
		self.app_dir = None
		self.patch_dir = None
		self.filename = None
		self.docstring = None
		self.patch_file = None

	def fetch_user_inputs(self):
		self._ask_app_name()
		self._ask_doctype_name()
		self._ask_patch_meta_info()

	def _ask_app_name(self):
		self.app = click.prompt("Select app for new patch", type=click.Choice(self.all_apps))
		self.app_dir = pathlib.Path(frappe.get_app_path(self.app))

	def _ask_doctype_name(self):
		def _doctype_name(filename):
			with contextlib.suppress(Exception):
				with open(filename) as f:
					return json.load(f).get("name")

		doctype_files = list(glob.glob(f"{self.app_dir}/**/doctype/**/*.json"))
		doctype_map = {_doctype_name(file): file for file in doctype_files}
		doctype_map.pop(None, None)

		doctype = click.prompt(
			"Provide DocType name on which this patch will apply",
			type=click.Choice(doctype_map.keys()),
			show_choices=False,
		)
		self.patch_dir = pathlib.Path(doctype_map[doctype]).parents[0] / "patches"

	def _ask_patch_meta_info(self):
		self.docstring = click.prompt("Describe what this patch does", type=str)
		default_filename = frappe.scrub(self.docstring) + ".py"

		def _valid_filename(name):
			if not name:
				return

			match name.partition("."):
				case filename, ".", "py" if filename.isidentifier():
					return True
				case _:
					click.echo(f"{name} is not a valid python file name")

		while not _valid_filename(self.filename):
			self.filename = click.prompt(
				"Provide filename for this patch", type=str, default=default_filename
			)

	def create_patch_file(self):
		self._create_parent_folder_if_not_exists()

		self.patch_file = self.patch_dir / self.filename

		if self.patch_file.exists():
			raise Exception(f"Patch {self.patch_file} already exists")

		*path, _filename = self.patch_file.relative_to(self.app_dir.parents[0]).parts
		dotted_path = ".".join(path + [self.patch_file.stem])

		patches_txt = self.app_dir / "patches.txt"
		existing_patches = patches_txt.read_text()

		if dotted_path in existing_patches:
			raise Exception(f"Patch {dotted_path} is already present in patches.txt")

		self.patch_file.write_text(PATCH_TEMPLATE.format(docstring=self.docstring))

		with open(patches_txt, "a+") as f:
			if not existing_patches.endswith("\n"):
				f.write("\n")  # ensure EOF
			f.write(dotted_path + "\n")
		click.echo(f"Created {self.patch_file} and updated patches.txt")

	def _create_parent_folder_if_not_exists(self):
		if not self.patch_dir.exists():
			click.confirm(
				f"Patch folder '{self.patch_dir}' doesn't exist, create it?",
				abort=True,
				default=True,
			)
			self.patch_dir.mkdir()

		init_py = self.patch_dir / "__init__.py"
		init_py.touch()


manifest_template = """include MANIFEST.in
include requirements.txt
include *.json
include *.md
include *.py
include *.txt
recursive-include {app_name} *.css
recursive-include {app_name} *.csv
recursive-include {app_name} *.html
recursive-include {app_name} *.ico
recursive-include {app_name} *.js
recursive-include {app_name} *.json
recursive-include {app_name} *.md
recursive-include {app_name} *.png
recursive-include {app_name} *.py
recursive-include {app_name} *.svg
recursive-include {app_name} *.txt
recursive-exclude {app_name} *.pyc"""

init_template = """
__version__ = '0.0.1'

"""

hooks_template = """from . import __version__ as app_version

app_name = "{app_name}"
app_title = "{app_title}"
app_publisher = "{app_publisher}"
app_description = "{app_description}"
app_email = "{app_email}"
app_license = "{app_license}"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/{app_name}/css/{app_name}.css"
# app_include_js = "/assets/{app_name}/js/{app_name}.js"

# include js, css files in header of web template
# web_include_css = "/assets/{app_name}/css/{app_name}.css"
# web_include_js = "/assets/{app_name}/js/{app_name}.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "{app_name}/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {{"doctype": "public/js/doctype.js"}}
# webform_include_css = {{"doctype": "public/css/doctype.css"}}

# include js in page
# page_js = {{"page" : "public/js/file.js"}}

# include js in doctype views
# doctype_js = {{"doctype" : "public/js/doctype.js"}}
# doctype_list_js = {{"doctype" : "public/js/doctype_list.js"}}
# doctype_tree_js = {{"doctype" : "public/js/doctype_tree.js"}}
# doctype_calendar_js = {{"doctype" : "public/js/doctype_calendar.js"}}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {{
#	"Role": "home_page"
# }}

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {{
#	"methods": "{app_name}.utils.jinja_methods",
#	"filters": "{app_name}.utils.jinja_filters"
# }}

# Installation
# ------------

# before_install = "{app_name}.install.before_install"
# after_install = "{app_name}.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "{app_name}.uninstall.before_uninstall"
# after_uninstall = "{app_name}.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "{app_name}.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {{
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }}
#
# has_permission = {{
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {{
#	"ToDo": "custom_app.overrides.CustomToDo"
# }}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {{
#	"*": {{
#		"on_update": "method",
#		"on_cancel": "method",
#		"on_trash": "method"
#	}}
# }}

# Scheduled Tasks
# ---------------

# scheduler_events = {{
#	"all": [
#		"{app_name}.tasks.all"
#	],
#	"daily": [
#		"{app_name}.tasks.daily"
#	],
#	"hourly": [
#		"{app_name}.tasks.hourly"
#	],
#	"weekly": [
#		"{app_name}.tasks.weekly"
#	],
#	"monthly": [
#		"{app_name}.tasks.monthly"
#	],
# }}

# Testing
# -------

# before_tests = "{app_name}.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {{
#	"frappe.desk.doctype.event.event.get_events": "{app_name}.event.get_events"
# }}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {{
#	"Task": "{app_name}.task.get_dashboard_data"
# }}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["{app_name}.utils.before_request"]
# after_request = ["{app_name}.utils.after_request"]

# Job Events
# ----------
# before_job = ["{app_name}.utils.before_job"]
# after_job = ["{app_name}.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{{
#		"doctype": "{{doctype_1}}",
#		"filter_by": "{{filter_by}}",
#		"redact_fields": ["{{field_1}}", "{{field_2}}"],
#		"partial": 1,
#	}},
#	{{
#		"doctype": "{{doctype_2}}",
#		"filter_by": "{{filter_by}}",
#		"partial": 1,
#	}},
#	{{
#		"doctype": "{{doctype_3}}",
#		"strict": False,
#	}},
#	{{
#		"doctype": "{{doctype_4}}"
#	}}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"{app_name}.auth.validate"
# ]
"""

setup_template = """from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\\n")

# get version from __version__ variable in {app_name}/__init__.py
from {app_name} import __version__ as version

setup(
	name="{app_name}",
	version=version,
	description="{app_description}",
	author="{app_publisher}",
	author_email="{app_email}",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
"""

gitignore_template = """.DS_Store
*.pyc
*.egg-info
*.swp
tags
node_modules"""

github_workflow_template = """
name: CI

on:
  push:
    branches:
      - develop
  pull_request:

concurrency:
  group: develop-{app_name}-${{{{ github.event.number }}}}
  cancel-in-progress: true

jobs:
  tests:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
    name: Server

    services:
      redis-cache:
        image: redis:alpine
        ports:
          - 13000:6379
      redis-queue:
        image: redis:alpine
        ports:
          - 11000:6379
      redis-socketio:
        image: redis:alpine
        ports:
          - 12000:6379
      mariadb:
        image: mariadb:10.6
        env:
          MYSQL_ROOT_PASSWORD: root
        ports:
          - 3306:3306
        options: --health-cmd="mysqladmin ping" --health-interval=5s --health-timeout=2s --health-retries=3

    steps:
      - name: Clone
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: 16
          check-latest: true

      - name: Cache pip
        uses: actions/cache@v2
        with:
          path: ~/.cache/pip
          key: ${{{{ runner.os }}}}-pip-${{{{ hashFiles('**/*requirements.txt', '**/pyproject.toml', '**/setup.py', '**/setup.cfg') }}}}
          restore-keys: |
            ${{{{ runner.os }}}}-pip-
            ${{{{ runner.os }}}}-

      - name: Get yarn cache directory path
        id: yarn-cache-dir-path
        run: 'echo "dir=$(yarn cache dir)" >> $GITHUB_OUTPUT'

      - uses: actions/cache@v3
        id: yarn-cache
        with:
          path: ${{{{ steps.yarn-cache-dir-path.outputs.dir }}}}
          key: ${{{{ runner.os }}}}-yarn-${{{{ hashFiles('**/yarn.lock') }}}}
          restore-keys: |
            ${{{{ runner.os }}}}-yarn-

      - name: Setup
        run: |
          pip install frappe-bench
          bench init --skip-redis-config-generation --skip-assets --python "$(which python)" ~/frappe-bench
          mysql --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL character_set_server = 'utf8mb4'"
          mysql --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'"

      - name: Install
        working-directory: /home/runner/frappe-bench
        run: |
          bench get-app {app_name} $GITHUB_WORKSPACE
          bench setup requirements --dev
          bench new-site --db-root-password root --admin-password admin test_site
          bench --site test_site install-app {app_name}
          bench build
        env:
          CI: 'Yes'

      - name: Run Tests
        working-directory: /home/runner/frappe-bench
        run: |
          bench --site test_site set-config allow_tests true
          bench --site test_site run-tests --app {app_name}
        env:
          TYPE: server
"""

patches_template = """[pre_model_sync]
# Patches added in this section will be executed before doctypes are migrated
# Read docs to understand patches: https://frappeframework.com/docs/v14/user/en/database-migrations 

[post_model_sync]
# Patches added in this section will be executed after doctypes are migrated"""