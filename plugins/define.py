import sys
import os.path

from typing import List
from plugin import BasePlugin, PluginConfig
from nio import MatrixRoom, RoomMessageText
import subprocess
from urllib import request
import urllib.parse
import json
import re

from messaging import Messenger

"""
define.py requires some configuration setup:
"""

CONFIG_SAMPLE = """
# Your DictionaryAPI.com API key
api_key = "YOUR-API-KEY-HERE"
# The number of definitions you'd like to see on each call
max_def_count = 3

# Non-user configurable

# How the messages should be returned from the API (do not change)
format = "json"
api_endpoint = "https://www.dictionaryapi.com/api/v3/references/collegiate"
# The 
"""

CONFIG_FILE_NAME = "__config_define.py"


class Define(BasePlugin):
    # import __config_define
    # from _Define__config import api_key, api_endpoint, max_def_count, api_format

    trigger = ["define"]
    config: PluginConfig = None
    enabled = False

    def __init__(self, config: PluginConfig):
        self.config = config

        path_to_config = os.path.join(*sys.modules[__name__].__name__.rsplit(".")[:-1], CONFIG_FILE_NAME)

        if not os.path.exists(path_to_config) or not os.path.isfile(path_to_config):
            try:
                open(path_to_config, "w").write(path_to_config)
                self.config.logger.critical("Missing configuration file; one has been made for you but you'll need to configure it.")
            except IOError as err:
                self.config.logger.critical(f"Missing configuration file and unable to generate one for you. Perhaps you don't have permission to write over {CONFIG_FILE_NAME}? {err}")
            finally:
                return

        self.enabled = True
        # Create a new updated PluginConfig based on our config file
        self.config = config.config_from_file(path_to_config)

        self.config.logger.info(
            self.config.api_endpoint, self.config.api_key, self.config.api_format, self.config.max_def_count
        )

    async def process_event(
        self, room: MatrixRoom, event: RoomMessageText, messenger: Messenger,
    ) -> None:
        """Define a provided word.
        
        Submits up to MAX_DEF_COUNT number of definitions.
        
        Arguments:
            room {MatrixRoom} -- the room from which the message came
            event {RoomMessageText} -- the message that triggered this call
            messenger {Messenger} -- for sending messages out
        """
        tokens = self.tokens(event)

        # UNSAFE! Do NOT directly submit to an API
        term = " ".join(tokens[1:])
        # We use urllib to at least _try_ to clean up the term
        query = urllib.parse.quote(term, safe="")
        url = request.urlopen(f"{self.config.api_endpoint}/{self.config.api_format}/{query}?key={self.config.api_key}")
        data: dict = None
        try:
            data = json.loads(url.read().decode())
        except json.JSONDecodeError as err:
            self.config.logger.warn(f"Failed to read from the Merriam-Webster API. Error: {err}")
            return

        if "meta" not in data[0]:
            await messenger.send_text(
                room.room_id,
                body="The word you've entered isn't in the Merriam-Webster dictionary",
            )
            return

        # Noun, adjective, adverb, etc.
        functional_label = data[0]["fl"]

        definition_collection: List[str] = []
        for sense_collection in data[0]["def"][0]["sseq"]:
            sense = sense_collection[0][1]
            if sense["dt"][0][0] == "text":
                defining_text = sense["dt"][0][1]

            if sense["dt"][0][0] == "uns":
                defining_text = "—" + sense["dt"][0][1][0][0][1]

            definition = re.sub(
                # Remove any tags other than {bc}
                r"\{.*\}",
                "",
                # {bc} is supposed to be a bold colon; we remove them and
                # use our own styling
                defining_text.replace("{bc}", "", 1).replace(" {bc}", "; "),
            )
            # some senses only include {} tags; if that's the case, we skip it
            if definition != "":
                definition_collection.append(definition)

        if len(definition_collection) == 0:
            await messenger.send_text(
                room.room_id,
                body="The word you've entered isn't in the Merriam-Webster dictionary",
            )
            return

        body = f"{term} {functional_label}"
        formatted_body = f"<b>{term}</b> <i>{functional_label}</i>"

        for index, definition in enumerate(definition_collection[:self.config.max_def_count]):
            body += f" {index + 1}. {definition}"
            formatted_body += f"<br>&ensp;{index + 1}. {definition}"

        await messenger.send_text(
            room.room_id, body=body, formatted_body=formatted_body
        )
        return