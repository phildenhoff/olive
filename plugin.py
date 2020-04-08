from abc import abstractmethod, ABC
from typing import Any, Dict, List, Optional, Union
from nio import Event, MatrixRoom, RoomMessageText

from messaging import Messenger

# TODO: Add some kind of logging callback when plugins are registered


class Command(ABC):
    trigger: Any = None

    @abstractmethod
    def process_event(
        self, room: MatrixRoom, event: Event, messenger: Messenger
    ) -> None:
        """Processes a user message. Optionally provides a response.

        Args:
            room (MatrixRoom): the room where the event occurred
            event (Event): the event itself
            messenger (Messenger): the client's Messenger instance, for emitting
                events
        """
        pass


class TextCommand(Command):
    trigger: List[str] = []

    @abstractmethod
    def process_event(
        self,
        room: MatrixRoom,
        event: RoomMessageText,
        messenger: Messenger,
        tokens: List[str],
    ) -> None:
        """Processes a user message. Optionally provides a response.

        Args:
            room (MatrixRoom): the room where the event occurred
            event (Event): the event itself
            messenger (Messenger): the client's Messenger instance, for emitting
                events
            tokens (List[str]): a santisied version of the event.body, which
                removes the trigger word if it was originally included
        """
        pass

    @abstractmethod
    def is_triggered(self, tokens: List[str]) -> bool:
        """Returns True if the command is triggered by the sanitised input, split into tokens.

        Args:
            tokens (List[str]): a sanitised verison of the message body, which
                removes the trigger word if it was originalyl included
        """
        pass
