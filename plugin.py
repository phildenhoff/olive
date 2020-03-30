from abc import abstractmethod, ABC
from typing import Any, Dict, List, Optional, Union
from nio import AsyncClient, Event, MatrixRoom, RoomMessageText

class Command(ABC):
    trigger: Any = None

    @abstractmethod
    def process_event(self, room: MatrixRoom, event: Event, client: AsyncClient) -> None:
        """Processes a user message. Optionally provides a response.
        """
        pass

class TextCommand(Command):
    trigger: List[str] = []

    @abstractmethod
    def process_event(self, room: MatrixRoom, event: RoomMessageText, client: AsyncClient) -> None:
        """Processes a user message. Optionally provides a response.
        """
        pass

    @abstractmethod
    def is_triggered(self, tokens: List[str]) -> bool:
        """Returns True if the command is triggered by the sanitised input, split into tokens.
        """
        pass