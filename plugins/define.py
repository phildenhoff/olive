import sys
from typing import List
from plugin import TextCommand
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

API_KEY = ""
FORMAT = "json"
API_ENDPOINT = "https://www.dictionaryapi.com/api/v3/references/collegiate"
MAX_DEF_COUNT = 3


class Define(TextCommand):
    trigger = ["define"]

    @staticmethod
    async def process_event(
        room: MatrixRoom,
        event: RoomMessageText,
        messenger: Messenger,
        tokens: List[str],
    ) -> None:
        """Define a provided word.
        
        Submits up to MAX_DEF_COUNT number of definitions.
        
        Arguments:
            room {MatrixRoom} -- the room from which the message came
            event {RoomMessageText} -- the message that triggered this call
            messenger {Messenger} -- for sending messages out
        """

        # UNSAFE! Do NOT directly submit to an API
        term = " ".join(tokens[1:])
        # We use urllib to at least _try_ to clean up the term
        query = urllib.parse.quote(term, safe="")
        url = request.urlopen(f"{API_ENDPOINT}/{FORMAT}/{query}?key={API_KEY}")
        data = json.loads(url.read().decode())

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

        for index, definition in enumerate(definition_collection[:MAX_DEF_COUNT]):
            body += f" {index + 1}. {definition}"
            formatted_body += f"<br>&ensp;{index + 1}. {definition}"

        await messenger.send_text(
            room.room_id, body=body, formatted_body=formatted_body
        )
        return

    def is_triggered(self, tokens: List[str]) -> bool:
        """Returns True if the first token matches the trigger word.
        """

        return tokens[0].lower() == self.trigger[0]
