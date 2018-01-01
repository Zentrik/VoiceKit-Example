#!/usr/bin/env python3
# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run a recognizer using the Google Assistant Library with button support.

The Google Assistant Library has direct access to the audio API, so this Python
code doesn't need to record audio. Hot word detection "OK, Google" is supported.

The Google Assistant Library can be installed with:
    env/bin/pip install google-assistant-library==0.0.2

It is available for Raspberry Pi 2/3 only; Pi Zero is not supported.
"""

import logging
import sys
import threading
import subprocess

import aiy.assistant.auth_helpers
import aiy.audio
import aiy.voicehat
from google.assistant.library import Assistant
from google.assistant.library.event import EventType
aiy.i18n.set_language_code('en-GB')
aiy.audio.set_tts_pitch(95)
aiy.audio.set_tts_volume(2)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
)

def power_off_pi():
    aiy.audio.say('Good bye!')
    subprocess.call('sudo shutdown now', shell=True)

def reboot_pi():
    aiy.audio.say('See you in a bit!')
    subprocess.call('sudo reboot', shell=True)

def say_ip():
    ip_address = subprocess.check_output("hostname -I | cut -d' ' -f1", shell=True)
    aiy.audio.say('My IP address is %s' % ip_address.decode('utf-8'))   

def volume_down():
    volume_actual = aiy.audio.get_tts_volume()
    if volume_actual < 2:
        aiy.audio.set_tts_volume(0)
        aiy.audio.say('Ok, done')
    else:
        aiy.audio.set_tts_volume(volume_actual - 2)
        aiy.audio.say('Ok, done')
    
def volume_up():
    volume_actual = aiy.audio.get_tts_volume()
    if volume_actual > 98:
        aiy.audio.set_tts_volume(100)
        aiy.audio.say('Ok, done')
    else:
        aiy.audio.set_tts_volume(volume_actual + 2)
        aiy.audio.say('Ok, done') 

class MyAssistant(object):
    """An assistant that runs in the background.

    The Google Assistant Library event loop blocks the running thread entirely.
    To support the button trigger, we need to run the event loop in a separate
    thread. Otherwise, the on_button_pressed() method will never get a chance to
    be invoked.
    """
    def __init__(self):
        self._task = threading.Thread(target=self._run_task)
        self._can_start_conversation = False
        self._assistant = None

    def start(self):
        """Starts the assistant.

        Starts the assistant event loop and begin processing events.
        """
        self._task.start()

    def _run_task(self):
        credentials = aiy.assistant.auth_helpers.get_assistant_credentials()
        with Assistant(credentials) as assistant:
            self._assistant = assistant
            for event in assistant.start():
                self._process_event(event)

    def _process_event(self, event):
        status_ui = aiy.voicehat.get_status_ui()
        if event.type == EventType.ON_START_FINISHED:
            status_ui.status('ready')
            self._can_start_conversation = True
            # Start the voicehat button trigger.
            aiy.voicehat.get_button().on_press(self._on_button_pressed)
            if sys.stdout.isatty():
                print('Say "OK, Google" or press the button, then speak. '
                      'Press Ctrl+C to quit...')

        elif event.type == EventType.ON_CONVERSATION_TURN_STARTED:
            self._can_start_conversation = False
            status_ui.status('listening')
            # Start the voicehat button trigger.
            aiy.voicehat.get_button().on_press(self._on_button_pressed)
        
        elif event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED and event.args:
            print('You said:', event.args['text'])
            text = event.args['text'].lower()
            if text == 'power off':
                self._assistant.stop_conversation()
                power_off_pi()
            elif text == 'reboot':
                self._assistant.stop_conversation()
                reboot_pi()
            elif 'what is' and 'ip address' in text:
                self._assistant.stop_conversation()
                say_ip()
            elif 'repeat' in text:
                self._assistant.stop_conversation()
                to_repeat = text.replace('repeat', '', 1)
                aiy.audio.say(to_repeat)
            elif 'set' and 'secondary volume to' in text:
                self._assistant.stop_conversation()
                text = text.replace('%', '')
                volume = [int(s) for s in text.split() if s.isdigit()]
                print(volume)
                aiy.audio.say("Ok, I've set the secondary volume to" + str(volume[0]) + '%')
                print(volume)
                aiy.audio.set_tts_volume(volume[0])
            elif 'secondary volume down' in text:
                self._assistant.stop_conversation()
                volume_down()
            elif 'secondary volume up' in text:
                self._assistant.stop_conversation()
                volume_down()
                    
        elif event.type == EventType.ON_END_OF_UTTERANCE:
            status_ui.status('thinking')

        elif event.type == EventType.ON_CONVERSATION_TURN_FINISHED:
            status_ui.status('ready')
            self._can_start_conversation = True

        elif event.type == EventType.ON_ASSISTANT_ERROR and event.args and event.args['is_fatal']:
            sys.exit(1)

    def _on_button_pressed(self):
        # Check if we can start a conversation. 'self._can_start_conversation'
        # is False when either:
        # 1. The assistant library is not yet ready; OR
        # 2. The assistant library is already in a conversation.
        if self._can_start_conversation:
            self._assistant.start_conversation()
        else:
            self._assistant.stop_conversation()

def main():
    MyAssistant().start()

if __name__ == '__main__':
    main()
