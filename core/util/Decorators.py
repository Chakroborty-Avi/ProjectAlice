#  Copyright (c) 2021
#
#  This file, Decorators.py, is part of Project Alice.
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
#  Last modified: 2021.04.13 at 12:56:47 CEST

from __future__ import annotations

import functools
import warnings
from flask import jsonify, request
from typing import Any, Callable, Optional, Tuple, Union

from core.base.SuperManager import SuperManager
from core.base.model.Intent import Intent
from core.commons import constants
from core.user.model.AccessLevels import AccessLevel
from core.util.model.Logger import Logger


def deprecated(func):
	"""
	https://stackoverflow.com/questions/2536307/decorators-in-the-python-standard-lib-deprecated-specifically
	This is a decorator which can be used to mark functions
	as deprecated. It will result in a warning being emitted
	when the function is used.
	"""


	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		warnings.simplefilter('always', DeprecationWarning)  # turn off filter
		warnings.warn(f'Call to deprecated function {func.__name__}.',
		              category=DeprecationWarning,
		              stacklevel=2)
		warnings.simplefilter('default', DeprecationWarning)  # reset filter
		return func(*args, **kwargs)


	return wrapper


def IntentHandler(intent: Union[str, Intent], requiredState: str = None, authLevel: AccessLevel = AccessLevel.ZERO, userIntent: bool = True):  # NOSONAR
	"""Decorator for adding a method as an intent handler."""
	if isinstance(intent, str):
		intent = Intent(intent, authLevel=authLevel, userIntent=userIntent)


	def wrapper(func):
		# store the intent in the function
		if not hasattr(func, 'intents'):
			func.intents = []
		func.intents.append({'intent': intent, 'requiredState': requiredState})
		return func


	return wrapper


def MqttHandler(intent: Union[str, Intent], requiredState: str = None, authLevel: AccessLevel = AccessLevel.ZERO):  # NOSONAR
	"""Decorator for adding a method as a mqtt handler."""
	if isinstance(intent, str):
		intent = Intent(intent, userIntent=False, authLevel=authLevel)


	def wrapper(func):
		# store the intent in the function
		if not hasattr(func, 'intents'):
			func.intents = []
		func.intents.append({'intent': intent, 'requiredState': requiredState})
		return func


	return wrapper


def _exceptHandler(*args, text: str, exceptHandler: Optional[Callable], returnText: bool, **kwargs) -> Union[Callable, str]:
	if exceptHandler:
		return exceptHandler(*args, **kwargs)

	caller = args[0] if args else None
	skill = getattr(caller, 'name', 'system')
	newText = SuperManager.getInstance().TalkManager.randomTalk(text, skill=skill)
	if not newText:
		newText = SuperManager.getInstance().TalkManager.randomTalk(text, skill='system') or text

	if not newText:
		raise Exception('String **text** not found in either skill or system strings')

	if returnText:
		return newText

	session = kwargs.get('session')
	try:
		if session.sessionId in SuperManager.getInstance().DialogManager.sessions:
			SuperManager.getInstance().MqttManager.endDialog(sessionId=session.sessionId, text=newText)
		else:
			SuperManager.getInstance().MqttManager.say(text=newText, deviceUid=session.deviceUid)
	except AttributeError:
		return newText


def Online(func: Callable = None, text: str = 'offline', offlineHandler: Callable = None, returnText: bool = False, catchOnly: bool = False):  # NOSONAR
	# noinspection HttpUrlsUsage
	"""
		(return a) decorator to mark a function that requires ethernet.

		This decorator can be used (with or without parameters) to define
		a function that requires ethernet. In the Default mode without arguments shown
		in the example it will either execute what's in the function or when alice is
		offline ends the dialog with a random offline answer.
		Using the parameters:
			@online(text=<myText>)
		An own text can be used when being offline as well and using the parameters:
			@online(offlineHandler=<myFunc>)
		An own offline handler can be called, which is helpful when not only endDialog has to be called,
		but some other cleanup is required as well

		When there is no named argument 'session' of type DialogSession in the arguments of the decorated function,
		the decorator will return the text instead. This behaviour can be enforced as well using:
			@online(returnText=True)

		:param catchOnly: If catch only, do not raise anything
		:param func:
		:param text:
		:param offlineHandler:
		:param returnText:
		:return: return value of function or random offline string in the current language
		Examples:
			An intent that requires ethernet can be defined the following way:

			@online
			def exampleIntent(self, session: DialogSession, **_kwargs):
				request = requests.get('http://api.open-notify.org')
				self.endDialog(sessionId=session.sessionId, text=request.text)
		"""


	# noinspection PyShadowingNames
	def argumentWrapper(func):
		@functools.wraps(func)
		def offlineDecorator(*args, **kwargs):
			internetManager = SuperManager.getInstance().InternetManager
			if internetManager.online:
				try:
					return func(*args, **kwargs)
				except:
					if internetManager.checkOnlineState():
						raise

			if catchOnly:
				return

			return _exceptHandler(*args, text=text, exceptHandler=offlineHandler, returnText=returnText, **kwargs)


		return offlineDecorator


	return argumentWrapper(func) if func else argumentWrapper


def AnyExcept(func: Callable = None, text: str = 'error', exceptions: Tuple[BaseException, ...] = None, exceptHandler: Callable = None, returnText: bool = False, printStack: bool = False):  # NOSONAR
	# noinspection PyShadowingNames
	def argumentWrapper(func):
		@functools.wraps(func)
		def exceptionDecorator(*args, **kwargs):
			try:
				return func(*args, **kwargs)
			except exceptions as e:
				Logger().logWarning(msg=e, printStack=printStack)
				return _exceptHandler(*args, text=text, exceptHandler=exceptHandler, returnText=returnText, **kwargs)


		return exceptionDecorator


	exceptions = exceptions or Exception
	return argumentWrapper(func) if func else argumentWrapper


def ApiAuthenticated(func: Callable):  # NOSONAR
	@functools.wraps(func)
	def wrapper(*args, **kwargs):
		if SuperManager.getInstance().UserManager.apiTokenValid(request.headers.get('auth', '')):
			return func(*args, **kwargs)
		else:
			return jsonify(message='ERROR: Unauthorized')


	return wrapper


def KnownUser(func: Callable = None):  # NOSONAR
	"""
	Checks if the session is started by a know user or not. This is important for skills that are security
	sensitive, and you need to make sure Alice is not talking to someone unknown
	:param func:
	:return:
	"""


	# noinspection PyShadowingNames
	def argumentWrapper(func: Callable):
		@functools.wraps(func)
		def decorator(*args, **kwargs):
			session = kwargs.get('session', None)
			if session and session.user != constants.UNKNOWN_USER:
				return func(*args, **kwargs)

			SuperManager.getInstance().MqttManager.endDialog(sessionId=session.sessionId, text=SuperManager.getInstance().TalkManager.randomTalk('unknownUser', skill='system'))


		return decorator


	return argumentWrapper(func) if func else argumentWrapper


def IfSetting(func: Callable = None, settingName: str = None, settingValue: Any = None, inverted: bool = False, skillName: str = None, returnValue: Optional[Any] = None):  # NOSONAR
	"""
	Checks whether a setting is equal to the given value before executing the wrapped method
	If the setting is not equal to the given value, the wrapped method is not called
	By providing a skill name the wrapper searches for a skill setting, otherwise for a system setting
	By setting inverted to True one can check for "not equal to", in other words, if the settingName is not equal to the settingValue
	:param func:
	:param settingName:
	:param settingValue:
	:param inverted:
	:param skillName:
	:param returnValue: The value to return if the setting check fails
	:return:
	"""


	# noinspection PyShadowingNames
	def argumentWrapper(func: Callable):
		@functools.wraps(func)
		def settingDecorator(*args, **kwargs):
			if not settingName:
				Logger().logWarning(msg='Cannot use IfSetting decorator without settingName')
				return None

			configManager = SuperManager.getInstance().ConfigManager
			value = configManager.getSkillConfigByName(skillName, settingName) if skillName else configManager.getAliceConfigByName(settingName)

			if value is None:
				return returnValue

			if (not inverted and value == settingValue) or \
					(inverted and value != settingValue):
				return func(*args, **kwargs)
			else:
				return returnValue


		return settingDecorator


	return argumentWrapper(func) if func else argumentWrapper
