#  Copyright (c) 2021
#
#  This file, CoquiAsr.py, is part of Project Alice.
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
#  Last modified: 2021.04.13 at 12:56:45 CEST

import numpy as np
from pathlib import Path
from typing import Generator, Optional

from core.asr.model.ASRResult import ASRResult
from core.asr.model.Asr import Asr
from core.asr.model.Recorder import Recorder
from core.dialog.model.DialogSession import DialogSession
from core.util.Stopwatch import Stopwatch


try:
	import stt
except:
	pass


class CoquiAsr(Asr):
	NAME = 'Coqui Asr'
	DEPENDENCIES = {
		'system': [],
		'pip'   : {
			'stt-tflite'
		}
	}


	def __init__(self):
		super().__init__()
		self._capableOfArbitraryCapture = True
		self._isOnlineASR = False

		self._langPath = Path(self.Commons.rootDir(), f'trained/asr/coqui/{self.LanguageManager.activeLanguage}')

		self._model: Optional[stt.Model] = None
		self._triggerFlag = self.ThreadManager.newEvent('asrTriggerFlag')


	def onStart(self):
		super().onStart()
		self.installDependencies()
		if not self.checkLanguage():
			self.downloadLanguage()
		self.logInfo('Loading Model')
		self._model = stt.Model(str(self.tFlite))

		self.logInfo('Model Loaded')
		self._model.enableExternalScorer(f'{self._langPath}/lm.scorer')
		self.logInfo('Scorer Loaded')


	def installDependencies(self) -> bool:
		#		if not super().installDependencies():
		#	return False
		# TODO TEMP! as long as the whl is not on pypi
		self.Commons.runSystemCommand(['wget', 'https://github.com/coqui-ai/STT/releases/download/v0.10.0-alpha.6/stt_tflite-0.10.0a6-cp37-cp37m-linux_armv7l.whl'])
		self.Commons.runSystemCommand(['./venv/bin/pip', 'install', 'stt_tflite-0.10.0a6-cp37-cp37m-linux_armv7l.whl'])
		self.Commons.runSystemCommand(['rm', 'stt_tflite-0.10.0a6-cp37-cp37m-linux_armv7l.whl'])

		return self.downloadLanguage() if not self.checkLanguage() else True


	def checkLanguage(self) -> bool:
		if not self._langPath.exists():
			self._langPath.mkdir(parents=True)
			return False

		return self.tFlite.exists()


	@property
	def tFlite(self) -> Path:
		return self._langPath / 'output_graph.tflite'


	# noinspection DuplicatedCode
	def downloadLanguage(self) -> bool:  # NOSONAR
		self.logInfo(f'Downloading language model for "{self.LanguageManager.activeLanguage}", hold on, this is going to take some time!')
		# TODO TEMP! until real model zoo exists
		target = str(self._langPath / 'lm.scorer')
		if self.LanguageManager.activeLanguage == 'de':
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/german/AASHISHAG/v0.9.0/model.tflite', str(self.tFlite))
			self.Commons.downloadFile('https://github.com/philipp2310/Coqui-models/releases/download/de_v093/lm.scorer', target)
			return True
		elif self.LanguageManager.activeLanguage == 'en':
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/english%2Fcoqui%2Fv1.0.0-large-vocab/model.tflite', str(self.tFlite))
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/english%2Fcoqui%2Fv1.0.0-large-vocab/large_vocabulary.scorer', target)
			return True
		elif self.LanguageManager.activeLanguage == 'fr':
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/french/commonvoice-fr/v0.6/model.tflite', str(self.tFlite))
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/french/commonvoice-fr/v0.6/fr-cvfr-2-prune-kenlm.scorer', target)
			return True
		elif self.LanguageManager.activeLanguage == 'it':
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/italian/mozillaitalia/2020.8.7/model.tflite', str(self.tFlite))
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/italian/mozillaitalia/2020.8.7/it-mzit-1-prune-kenlm.scorer', target)
			return True
		elif self.LanguageManager.activeLanguage == 'pl':
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/polish/jaco-assistant/v0.0.1/model.tflite', str(self.tFlite))
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/polish/jaco-assistant/v0.0.1/kenlm_pl.scorer', target)
			return True
		elif self.LanguageManager.activeLanguage == 'pt':
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/portuguese/itml/v0.1.0/model.tflite', str(self.tFlite))
			self.Commons.downloadFile('https://github.com/coqui-ai/STT-models/releases/download/portuguese/itml/v0.1.0/pt-itml-0-prune-kenlm.scorer', target)
			return True
		else:
			self.logError('WIP! Only de/en supported for now - Please install language manually into PA/trained/asr/Coqui/<language>/!')
			return False


	def onVadUp(self):
		self._triggerFlag.set()


	def onVadDown(self):
		if not self._triggerFlag.is_set():
			return

		self._recorder.stopRecording()


	def decodeStream(self, session: DialogSession) -> Optional[ASRResult]:
		super().decodeStream(session)
		result = None

		with Stopwatch() as processingTime:
			with Recorder(self._timeout, session.user, session.deviceUid) as recorder:
				self.ASRManager.addRecorder(session.deviceUid, recorder)
				self._recorder = recorder
				streamContext = self._model.createStream()
				for chunk in recorder:
					if not chunk:
						break

					streamContext.feedAudioContent(np.frombuffer(chunk, np.int16))

					result = streamContext.intermediateDecode()
					self.partialTextCaptured(session=session, text=result, likelihood=1, seconds=0)

			text = streamContext.finishStream()
			self._triggerFlag.clear()
			self.end()

		return ASRResult(
			text=text,
			session=session,
			likelihood=1.0,
			processingTime=processingTime.time
		) if result else None


	# noinspection DuplicatedCode
	def _checkResponses(self, session: DialogSession, responses: Generator) -> Optional[tuple]:  # NOSONAR
		if responses is None:
			return None

		for response in responses:
			if not response.results:
				continue

			result = response.results[0]
			if not result.alternatives:
				continue

			if result.is_final:
				return result.alternatives[0].transcript, result.alternatives[0].confidence
			else:
				self.partialTextCaptured(session=session, text=result.alternatives[0].transcript, likelihood=result.alternatives[0].confidence, seconds=0)

		return None
