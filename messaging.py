import sys

from nio import AsyncClient, RoomSendError, SendRetryError

class Messenger():
    client: AsyncClient = None

    def __init__(self, client: AsyncClient) -> None:
        self.client = client

    async def send_text(self, room_id: str, body: str, formatted_body: str = None) -> None:
        """Sends a text message to a room.

        Arguments:
            room_id {str} -- the id of the room to send the message in
            body {str} -- the unformatted text to send in the room

        Keyword Arguments:
            formatted_body {str} -- Any custom HTML to send alongside the message (default: {None})
        """

        assert isinstance(body, str)
        content = {
            "msgtype": "m.text",
            "body": body
        }
        if formatted_body:
                content.update({
                    "format": "org.matrix.custom.html",
                    "formatted_body": formatted_body
                })

        try:
            send_status = await self.client.room_send(room_id,
                message_type="m.room.message",
                content = content)
        except SendRetryError as err:
            print(f"Failed to send message '{body}' to room '{room}'. Error:\n{err}", file=sys.stderr)

        if isinstance(send_status, RoomSendError):
            print(send_status, file=sys.stderr)