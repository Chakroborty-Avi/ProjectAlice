#  Copyright (c) 2021
#
#  This file, AliceWatchManager.py, is part of Project Alice.
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
#  Last modified: 2021.04.24 at 12:56:47 CEST
import json
import os
import requests
import subprocess
import traceback
from AliceGit.Git import Repository
from pathlib import Path

from core.base.model.Manager import Manager
from core.commons import constants


class BugReportManager(Manager):

	ERROR_LOGS = [
		'fatal',
		'error',
		'critical'
	]

	def __init__(self):
		super().__init__(name='BugReportManager')

		self._flagFile = Path('alice.bugreport')
		if self._flagFile.exists():
			self._recording = True
			self.logInfo('Flag file detected, recording errors for this run')
			version = subprocess.run('git rev-parse HEAD', capture_output=True, text=True, shell=True).stdout.strip()
			self.logInfo('Project Alice logs')
			self.logInfo(f'Git commit id: {version}')
		else:
			self._recording = False
		self._history = list()
		self._title = ''


	@property
	def isRecording(self) -> bool:
		return self._recording


	def addToHistory(self, function: str, log: str):
		if not self._recording:
			return

		self._history.append(log)

		if function in self.ERROR_LOGS and not self._title and traceback.format_exc().strip() != 'NoneType: None':
			self._title = traceback.format_exc().strip().split('\n').pop()


	def onStop(self):
		super().onStop()
		if not self._recording:
			return

		try:
			online = requests.get('https://api.projectalice.io/generate_204').status_code == 204
		except:
			online = False

		if not online:
			self.logInfo('We are currently offline, cannot send log reports')
			os.remove(self._flagFile)
			return

		repo = Repository(directory=self.Commons.rootDir())
		if not repo.isUpToDate():
			self.logInfo('Alice is not up to date. Please first update to latest version and retry before trying to submit a bug report again.')
			os.remove(self._flagFile)
			return

		if not self._history or not self._title:
			self.logInfo('Nothing to report')
		elif not self.ConfigManager.githubAuth:
			self.logWarning('Cannot report bugs if Github user and token are not set in configs')
		else:
			title = f'[AUTO BUG REPORT] {self._title}'
			body = '\n'.join(self._history)
			data = {
				'title': title,
				'body': f'```\n{body}\n```'
			}

			request = requests.post(url=f'{constants.GITHUB_API_URL}/ProjectAlice/issues', data=json.dumps(data), auth=self.ConfigManager.githubAuth)
			if request.status_code != 201:
				self.logError(f'Something went wrong reporting a bug, status: {request.status_code}, error: {request.json()}')
			else:
				self.logInfo(f'Created new issue: {request.json()["html_url"]}')

		os.remove(self._flagFile)
