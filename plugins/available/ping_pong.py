from typing import List
from plugin import BasePlugin, PluginConfig
from nio import MatrixRoom, RoomMessageText

from messaging import Messenger

from time import sleep


class PingPong(BasePlugin):
    trigger = ["ping"]
    config: PluginConfig = None

    def __init__(self, config: PluginConfig):
        self.config = PluginConfig

    async def process_event(
        self, room: MatrixRoom, event: RoomMessageText, messenger: Messenger,
    ) -> None:
        tokens = self.tokens(event)
        if not (tokens[0] == self.trigger[0] and len(tokens) == 1):
            return

        sleep(2.5)
        await messenger.send_text(
            room.room_id,
            body=f"{room.user_name(event.sender)}: Pong!",
            formatted_body=f'<a href="https://matrix.to/#/{event.sender}">{room.user_name(event.sender)}</a> Pong!',
        )

    def is_triggered(self, tokens: List[str]) -> bool:
        """Returns True if the first token matches the trigger.
        """
        return tokens[0] == self.trigger[0] and len(tokens) == 1
