#  Copyright (c) 2021
#
#  This file, SnipsAsr.py, is part of Project Alice.
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
#  Last modified: 2021.05.19 at 12:56:45 CEST

import threading
import time
from typing import Optional

from core.asr.model.Asr import Asr
from core.dialog.model.DialogSession import DialogSession


class SnipsAsr(Asr):
	NAME = 'Snips Asr'
	DEPENDENCIES = {
		'internal': {
			'snips-kaldi-atlas': 'system/snips/snips-kaldi-atlas_0.26.1_armhf.deb',
			'snips-asr': 'system/snips/snips-asr_0.64.0_armhf.deb'
		},
		'external': {
			'snips-asr-model-en-500mb': 'https://raspbian.snips.ai/stretch/pool/s/sn/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb'
		},
		'system'  : [
			'libgfortran3'
		],
		'pip'     : []
	}


	def __init__(self):
		super().__init__()
		self._capableOfArbitraryCapture = True
		self._isOnlineASR = False
		self._listening = False
		self._thread: Optional[threading.Thread] = None
		self._flag = threading.Event()


	def installDependencies(self):
		super().installDependencies()
		self.Commons.runRootSystemCommand(['systemctl', 'stop', 'snips-asr'])
		self.Commons.runRootSystemCommand(['systemctl', 'disable', 'snips-asr'])


	def onStartListening(self, session):
		self._listening = True


	def onAsrToggleOff(self, deviceUid: str):
		self._listening = False


	def decodeStream(self, session: DialogSession):
		while self._listening:
			time.sleep(0.1)


	def onStart(self):
		super().onStart()

		if self.LanguageManager.activeLanguage != 'en':
			raise Exception('Snips generic ASR only for english')

		# noinspection DuplicatedCode
		cmd = f'snips-asr --assistant {self.Commons.rootDir()}/assistant --mqtt {self.ConfigManager.getAliceConfigByName("mqttHost")}:{self.ConfigManager.getAliceConfigByName("mqttPort")}'

		if self.ConfigManager.getAliceConfigByName('mqttUser'):
			cmd += f' --mqtt-username {self.ConfigManager.getAliceConfigByName("mqttUser")} --mqtt-password {self.ConfigManager.getAliceConfigByName("mqttPassword")}'

		if self.ConfigManager.getAliceConfigByName('mqttTLSFile'):
			cmd += f' --mqtt-tls-cafile {self.ConfigManager.getAliceConfigByName("mqttTLSFile")}'

		cmd += ' --model /usr/share/snips/snips-asr-model-en-500MB'
		cmd += ' --partial'

		self.SubprocessManager.runSubprocess(name='SnipsASR', cmd=cmd, autoRestart=True)


	def onStop(self):
		super().onStop()
		self.SubprocessManager.terminateSubprocess(name='SnipsASR')
