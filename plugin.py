from abc import abstractmethod, ABC
from typing import Any, Dict, List, Optional, Union
from logbook import Logger
import importlib
from os import path

from nio import Event, MatrixRoom, RoomMessageText

from messaging import Messenger


class PluginConfig:
    logger: Logger = None

    def __init__(self, logger: Logger):
        self.logger = logger

    def __copy__(self) -> 'PluginConfig':
        """Returns a deep copy of self.
        """
        new_config = PluginConfig(self.logger)
        for key in self.__dict__:
            new_config.__dict__[key] = self.__dict__[key]
        return new_config

    def config_from_file(self, config_file_path: str) -> 'PluginConfig':
        """Returns a new PluginConfig with the provided config file's settings
        included as children, if there were any.
        """
        if not path.exists(config_file_path) or not path.isfile(config_file_path):
            print(1)
            return self

        file_name = path.split(config_file_path)[-1]
        new_config = self.__copy__()
        module_name = "plugins." + file_name.rsplit(".")[0]
        module = importlib.import_module(module_name, package=".")

        print(file_name, new_config, module_name, module)

        for key in module.__dict__:
            print(key)
            new_config.__dict__[key] = module.__dict__[key]

        return new_config


class BasePlugin(ABC):
    trigger: Any = None
    plugin: PluginConfig = None

    @classmethod
    def name(cls) -> str:
        """Returns the name of the Plugin.
        """
        return type(cls).__name__

    @classmethod
    def tokens(self, event) -> List[str]:
        """Returns the body text of the event, split on spaces into an array.
        """
        return list(filter(lambda x: x != " " and x != "", event.body.split(" ")))

    @abstractmethod
    def process_event(
        self, room: MatrixRoom, event: Event, messenger: Messenger
    ) -> None:
        """Processes a room event. Optionally provides a response.

        Args:
            room (MatrixRoom): the room where the event occurred
            event (Event): the event itself
            messenger (Messenger): the client's Messenger instance, for emitting
                events
        """
        pass
