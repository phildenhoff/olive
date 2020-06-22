from typing import List
from plugin import TextCommand
from nio import MatrixRoom, MatrixUser, RoomMessageText
from random import choice

from messaging import Messenger


class Tag(TextCommand):
    """Play tag by @-ing each other in a room!
    """

    trigger = ["tag"]

    @staticmethod
    async def process_event(
        room: MatrixRoom,
        event: RoomMessageText,
        messenger: Messenger,
        tokens: List[str],
    ) -> None:
        """Tags a random user from the room.
        """
        random_user = choice(list(room.users.values()))
        await messenger.send_text(
            room.room_id,
            body=f"{room.user_name(random_user.user_id)}: You're it!",
            formatted_body=f'<a href="https://matrix.to/#/{random_user.user_id}">{room.user_name(random_user.user_id)}</a> You\'re it!',
        )

    def is_triggered(self, tokens: List[str]) -> bool:
        """Returns True if the second token matches the trigger word.
        """

        return tokens[0] == self.trigger[0]
