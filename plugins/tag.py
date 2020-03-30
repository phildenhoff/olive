from typing import List
from plugin import TextCommand
from nio import MatrixRoom, RoomMessageText

from messaging import Messenger

class Tag(TextCommand):
    trigger = ["tag"]

    @staticmethod
    async def process_event(room: MatrixRoom, event: RoomMessageText, messenger: Messenger) -> None:
        await messenger.send_text(
            room.room_id,
            body=f"{room.user_name(event.sender)}: You're it!",
            formatted_body=f"<a href=\"https://matrix.to/#/{event.sender}\">{room.user_name(event.sender)}</a> You're it!"
        )
        
    def is_triggered(self, tokens: List[str]) -> bool:
        """Returns True if the second token matches the trigger word.

        Expects the first token to be bot trigger word, and the second a
        command.
        """
        return tokens[1].lower() == self.trigger[0]
        