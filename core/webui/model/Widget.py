#  Copyright (c) 2021
#
#  This file, Widget.py, is part of Project Alice.
#
#  Project Alice is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>
#
#  Last modified: 2021.04.13 at 12:56:49 CEST

import htmlmin as htmlmin
import inspect
import json
import re
import sqlite3
from cssmin import cssmin
from jsmin import jsmin
from pathlib import Path
from typing import Dict, Match, Optional, Union

from core.base.model.AliceSkill import AliceSkill
from core.base.model.ProjectAliceObject import ProjectAliceObject
from core.webui.model.WidgetSizes import WidgetSizes


class Widget(ProjectAliceObject):
	DEFAULT_SIZE = WidgetSizes.w_small
	DEFAULT_OPTIONS = dict()


	def __init__(self, data: Union[sqlite3.Row, dict]):
		super().__init__()

		if isinstance(data, sqlite3.Row):
			data = self.Commons.dictFromRow(data)

		self._id = int(data.get('id', -1))
		self._skill = data['skill']
		self._name = data['name']
		self._settings = json.loads(data['settings'])
		self._configs = json.loads(data['configs'])
		self._page = data['page']
		self._lang = self.loadLanguageFile()
		self._skillInstance: AliceSkill = self.SkillManager.getSkillInstance(skillName=self._skill)

		if not self._configs:
			self._configs = self.DEFAULT_OPTIONS.copy()

		if not self._settings:
			self._settings = {
				'x'                 : 0,
				'y'                 : 0,
				'z'                 : self.WidgetManager.getNextZIndex(self._page),
				'w'                 : int(self.DEFAULT_SIZE.value.split('x')[0]),
				'h'                 : int(self.DEFAULT_SIZE.value.split('x')[1]),
				'r'                 : 0,
				'background'        : '#636363',
				'background-opacity': 1,
				'color'             : '#d1d1d1',
				'font-size'         : 1,
				'rgba'              : 'rgba(99, 99, 99, 1)',
				'title'             : True,
				'borders'           : True
			}

		if self._id == -1:
			self.saveToDB()


	def _setId(self, wid: int):
		"""
		If the widget is created through the interface, the id is unknown until db insert
		:param wid: int
		"""
		self._id = wid


	def loadLanguageFile(self) -> Optional[Dict]:
		try:
			ffile = self.getCurrentDir() / f'lang/{self.name}.lang.json'
			with ffile.open() as fp:
				return json.load(fp)
		except FileNotFoundError:
			self.logWarning(f'Missing language file for widget {self.name}')
			return None
		except Exception:
			self.logWarning(f"Couldn't import language file for widget {self.name}")
			return None


	# noinspection SqlResolve
	def saveToDB(self):
		if self._id != -1:
			self.DatabaseManager.replace(
				tableName=self.WidgetManager.WIDGETS_TABLE,
				query='REPLACE INTO :__table__ (id, skill, name, settings, configs, page) VALUES (:id, :skill, :name, :settings, :configs, :page)',
				callerName=self.WidgetManager.name,
				values={
					'id'      : self._id if self._id != 9999 else '',
					'skill'   : self._skill,
					'name'    : self._name,
					'settings': json.dumps(self._settings),
					'configs' : json.dumps(self._configs),
					'page'    : self._page
				}
			)
		else:
			widgetId = self.DatabaseManager.insert(
				tableName=self.WidgetManager.WIDGETS_TABLE,
				callerName=self.WidgetManager.name,
				values={
					'skill'   : self._skill,
					'name'    : self._name,
					'settings': json.dumps(self._settings),
					'configs' : json.dumps(self._configs),
					'page'    : self._page
				}
			)

			self._setId(widgetId)


	def getCurrentDir(self) -> Path:
		return Path(inspect.getfile(self.__class__)).parent


	def icon(self) -> str:
		try:
			ffile = Path(self.getCurrentDir(), f'templates/{self.name}.html')
			content = cssmin(ffile.read_text())
			header = re.search(r'<icon>(.*)</icon>', content)
			if header:
				return header.group(1)

			return ''
		except:
			self.logWarning("Widget doesn't have any icon")
			return ''


	def html(self) -> str:
		try:
			ffile = Path(self.getCurrentDir(), f'templates/{self.name}.html')
			content = ffile.read_text()
			content = re.sub(r'{{ lang\.(\w*) }}', self.langReplace, content)
			content = re.sub(r'<widget>(.*)</widget>', r'\1', content, flags=re.S)
			content = re.sub(r'<icon>.*</icon>(.*)', r'\1', content)
			content = htmlmin.minify(content,
			                         remove_comments=True,
			                         remove_empty_space=True,
			                         remove_all_empty_space=True,
			                         reduce_empty_attributes=True,
			                         reduce_boolean_attributes=True,
			                         remove_optional_attribute_quotes=False,
			                         convert_charrefs=True,
			                         keep_pre=False
			                         )
			return content
		except:
			self.logWarning("Widget doesn't have html file")
			return ''


	def css(self) -> str:
		try:
			ffile = Path(self.getCurrentDir(), f'css/{self.name}.css')
			content = cssmin(ffile.read_text())
			return content
		except:
			return ''


	def js(self) -> str:
		try:
			ffile = Path(self.getCurrentDir(), f'js/{self.name}.js')
			content = jsmin(ffile.read_text())
			return content
		except:
			return ''


	def langReplace(self, match: Match):
		return self.getLanguageString(match.group(1))


	def getLanguageString(self, key: str) -> str:
		try:
			return self._lang[self.LanguageManager.activeLanguage][key]
		except KeyError:
			return 'Missing string'


	@property
	def id(self) -> int:
		return self._id


	@property
	def x(self) -> int:  # NOSONAR
		return self._settings.get('x', 0)


	@x.setter
	def x(self, value: int):  # NOSONAR
		self._settings['x'] = value


	@property
	def y(self) -> int:  # NOSONAR
		return self._settings.get('y', 0)


	@y.setter
	def y(self, value: int):  # NOSONAR
		self._settings['y'] = value


	@property
	def z(self) -> int:  # NOSONAR
		return self._settings.get('z', 0)


	@z.setter
	def z(self, value: int):  # NOSONAR
		self._settings['z'] = value


	@property
	def w(self) -> int:  # NOSONAR
		return self._settings['w']


	@w.setter
	def w(self, w: int):  # NOSONAR
		self._settings['w'] = w


	@property
	def h(self) -> int:  # NOSONAR
		return self._settings['h']


	@h.setter
	def h(self, h: int):  # NOSONAR
		self._settings['h'] = h


	@property
	def skill(self) -> str:
		return self._skill


	@skill.setter
	def skill(self, value: str):
		self._skill = value


	@property
	def name(self) -> str:
		return self._name


	@name.setter
	def name(self, value: str):
		self._name = value


	@property
	def params(self) -> dict:
		return self._settings


	@params.setter
	def params(self, value: dict):
		self._settings = value


	@property
	def settings(self) -> dict:
		return self._settings


	@settings.setter
	def settings(self, value: dict):
		self._settings = value


	@property
	def page(self) -> int:
		return self._page


	@page.setter
	def page(self, value: int):
		self._page = value


	@property
	def skillInstance(self) -> AliceSkill:
		return self._skillInstance


	def toDict(self, isAuth: bool = False) -> dict:
		return {
			'id'            : self._id,
			'skill'         : self._skill,
			'name'          : self._name,
			'settings'      : self._settings,
			'configs'       : self._configs if isAuth else dict(),
			'configTemplate': self.skillInstance.getWidgetTemplate(self._name),
			'page'          : self._page,
			'icon'          : self.icon(),
			'html'          : self.html(),
			'css'           : self.css()
		}
