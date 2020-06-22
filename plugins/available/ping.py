import sys
from typing import List
from plugin import TextCommand
from nio import MatrixRoom, RoomMessageText
import subprocess

from urllib.parse import urlparse
from messaging import Messenger


class Ping(TextCommand):
    trigger = ["ping"]

    @staticmethod
    async def process_event(
        room: MatrixRoom,
        event: RoomMessageText,
        messenger: Messenger,
        tokens: List[str],
    ) -> None:
        """Ping a domain and send a message back with the results.
        
        Arguments:
            room {MatrixRoom} -- the room from which the message came
            event {RoomMessageText} -- the message that triggered this call
            messenger {Messenger} -- for sending messages out
        """
        await messenger.send_text(room.room_id, "Running ping test...")

        # `tokens` should be "ping <host>"
        host = tokens[1]
        ping = subprocess.Popen(
            ["ping", "-c", "4", host], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, err = ping.communicate()

        if err:
            body = "There was an error running the ping test. See the logs for details."
            print(err, file=sys.stderr)
        else:
            # out is in bytes. We split on line breaks. The last line is empty.
            # ping produces a line like min/avg/max/stddev = num/num/num/num ms;
            # we pull only the numbers and then split it into digits.
            try:
                min_time, avg, max_time, stddev = (
                    out.decode("utf8").split("\n")[-2].split(" = ")[1].split("/")
                )
                body = f"Ping time to {host}:\n\tmin: {min_time}\n\tavg: {avg}\n\tmax: {max_time}\n\tstddev: {stddev}"
            except Exception as err:
                body = f"Couldn't ping {host}"
                print(f"Failed to ping {host}", file=sys.stderr)
                print(out.decode("utf8"))

        await messenger.send_text(room.room_id, body=body)
        return

    def is_triggered(self, tokens: List[str]) -> bool:
        """Returns True if a list of strings is a valid ping command.
        """

        result = (
            tokens[0].lower() == self.trigger[0]
            and len(tokens) == 2
            and self.__maybe_url(tokens[1])
        )
        return result

    def __maybe_url(self, given: str, no_recurse=False) -> bool:
        """Detect if the given input string might be a URL we can ping.

        Does not guarantee that the URL is active or that it's even valid.
        Refuses any domains containing .dev or .local.

        Params:
        - `given` str -- the input string to test.  
        - `no_recurse` bool -- True if the function should not make any
            assumptions about the input string.

        Returns:
        - bool -- if the given input string is maybe a URL.
        """

        # Ignore any local domains to prevent obviously local-network attacks.
        if ".local" in given:
            # TODO: We should also be avoiding pinging any IP addresses that
            # aren't explictly external, otherwise we'll be providing local IP
            # data to attackers.
            print("Ping | REFUSED: No .local domains.")
            return False

        # It should try to look like a domain name or IPv4 or IPv6 address
        if "." not in given and ":" not in given:
            print(
                "Ping | REFUSED: Provided text doesn't look like a domain name or IP address."
            )
            return False

        try:
            result = urlparse(given)
            if not result.scheme and not result.netloc and not no_recurse:
                return self.__maybe_url("https://" + result.path, no_recurse=True)

            return all([result.scheme, result.netloc])
        except ValueError:
            return False
