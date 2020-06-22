import sys
import os
import importlib
import inspect
import asyncio
import traceback
from datetime import datetime
from typing import Dict, List

from nio import (
    AsyncClient,
    DevicesResponse,
    InviteEvent,
    LoginError,
    MatrixRoom,
    MatrixInvitedRoom,
    ReceiptEvent,
    RoomMessageText,
    RoomSendError,
    SendRetryError,
    SyncResponse,
    logger_group as nio_logger_group,
    log as nio_log,
)
from logbook import Logger, StreamHandler, INFO

from plugin import BasePlugin, PluginConfig
from messaging import Messenger
from session_config import SessionConfig
from log import logger_group

CORE_LOG = Logger("olive.core")
OUTPUT_NIO_LOGS = False


class Session:
    client: AsyncClient = None
    config: SessionConfig = None
    plugins: Dict[str, BasePlugin] = None
    messenger: Messenger = None
    loggers: List[Logger] = []

    def __init__(self, config: SessionConfig):
        self.config = config
        self.client = AsyncClient(config.homeserver, config.matrix_id)
        try:
            with open(config.next_batch_file, "r") as next_batch_token:
                self.client.next_batch = next_batch_token.read()
        except FileNotFoundError:
            # No existing next_batch file; no worries.
            self.client.next_batch = 0

        # Update next_batch every sync
        self.client.add_response_callback(self.__sync_cb, SyncResponse)
        # Handle text messages
        self.client.add_event_callback(self.__message_cb, RoomMessageText)
        # Handle invites
        self.client.add_event_callback(self.__autojoin_room_cb, InviteEvent)

        self.client.add_ephemeral_callback(self.sample, ReceiptEvent)

        self.load_plugins()
        self.messenger = Messenger(self.client)

    async def sample(self, room: MatrixRoom, event: ReceiptEvent) -> None:
        CORE_LOG.info(room.read_receipts)

    async def start(self) -> None:
        """Start the session.

        Logs in as the user provided in the config and begins listening for
        events to respond to. For security, it will logout any other
        sessions.
        """

        login_status = await self.client.login(
            password=self.config.password, device_name="remote-bot"
        )
        if isinstance(login_status, LoginError):
            print(f"Failed to login: {login_status}", file=sys.stderr)
            await self.stop()
        else:
            # Remove previously registered devices; ignore this device
            maybe_devices = await self.client.devices()
            if isinstance(maybe_devices, DevicesResponse):
                await self.client.delete_devices(
                    list(
                        map(
                            lambda x: x.id,
                            filter(
                                lambda x: x.id != self.client.device_id,
                                maybe_devices.devices,
                            ),
                        )
                    ),
                    auth={
                        "type": "m.login.password",
                        "user": self.config.matrix_id,
                        "password": self.config.password,
                    },
                )

            CORE_LOG.info(login_status)

        # Force a full state sync to load Room info
        await self.client.sync(full_state=True)
        await self.client.sync_forever(timeout=30000)

    async def stop(self) -> None:
        """Politely closes the session and ends the process.
        
        If logged in, logs out.
        """
        print("Shutting down...")
        if self.client.logged_in:
            await self.client.logout()
        await self.client.close()
        sys.exit(0)

    def load_plugins(self) -> None:
        """Dynamically loads all plugins from the plugins directory.

        New plugins can be added by creating new classes in the `plugins` module.
        """
        self.plugins = {}
        importlib.import_module("plugins")
        modules = []
        plugin_files = os.listdir(os.path.join(os.path.dirname(__file__), "plugins"))
        if len(plugin_files) == 0:
            print("NOTE: No plugin files found.")

        for plugin in plugin_files:
            if plugin.startswith("__") or not plugin.endswith(".py"):
                # Skip files like __init__.py and .gitignore
                continue

            module_name = "plugins." + plugin.rsplit(".")[0]
            modules.append(importlib.import_module(module_name, package="plugins"))

        for module in modules:
            if module.__name__ in sys.modules:
                importlib.reload(module)

            clsmembers = inspect.getmembers(
                module,
                lambda member: inspect.isclass(member)
                and member.__module__ == module.__name__,
            )

            for name, cls in clsmembers:
                if not issubclass(cls, BasePlugin):
                    # We only want plugins that derive from BasePlugin
                    CORE_LOG.warn(
                        f"Skipping {name} as it doesn't derive from the BasePlugin"
                    )
                    continue
                CORE_LOG.info(f"Loading plugin {name} ...")

                # Create logger for each plugin
                plugin_logger = Logger(f"olive.plugin.{name}")
                plugin_logger.info(f"{name}'s logger is working hard!")
                logger_group.add_logger(plugin_logger)

                # Generate standard config
                config = PluginConfig(plugin_logger)

                # Instantiate the plugin!
                self.plugins[name] = cls(config)

        CORE_LOG.info("Loaded plugins")

    async def __send(
        self, room: MatrixRoom, body: str = None, content: dict = None
    ) -> bool:
        # You must either include a body message or build your own content dict.
        assert body or content
        if not content:
            content = {"msgtype": "m.text", "body": body}
        try:
            send_status = await self.client.room_send(
                room.room_id, message_type="m.room.message", content=content
            )
        except SendRetryError as err:
            print(f"Failed to send message '{body}' to room '{room}'. Error:\n{err}")
            return False

        if isinstance(send_status, RoomSendError):
            print(send_status)
            return False

        return True

    async def __autojoin_room_cb(
        self, room: MatrixInvitedRoom, event: InviteEvent
    ) -> None:
        if room.room_id not in self.client.rooms:
            await self.client.join(room.room_id)
            await self.__send(room, f"Hello, {room.display_name}!")

            # TODO: Replace forced client sync. I'd like to avoid handling the
            # Invite event three times, but dont' want to force syncs. Probably
            # not common enought to matter?
            await self.client.sync(300)

    async def __message_cb(self, room: MatrixRoom, event: RoomMessageText):
        """Executes any time a MatrixRoom the bot is in receives a RoomMessageText.

        On each message, it tests each plugin to see if it is triggered by the
        event; if so, the method will run that plugins `process_event` method.
        """

        await self.client.room_read_markers(
            room.room_id, event.event_id, event.event_id
        )

        # tokens = list(filter(lambda x: x != " " and x != "", event.body.split(" ")))

        if event.sender == self.client.user_id:
            # Message is from us; we can ignore.
            return

        # # TODO: Clean up this logic
        # if room.is_group and room.member_count == 2:
        #     if not tokens[0].startswith(self.config.username):
        #         tokens = [self.config.username] + tokens

        # if not tokens[0].startswith(self.config.username):
        #     return
        # else:
        #     # Standardise `tokens` by removing the username
        #     tokens = tokens[1:]

        # # System-related commands?
        # if (tokens[0] == "plugin" and tokens[1] == "reload") or tokens[0] == "pr":
        #     self.load_plugins()
        #     return

        for name, plugin in self.plugins.items():
            try:
                await plugin.process_event(room, event, self.messenger)
            except Exception as err:
                print(
                    f"Plugin {name} encountered an error while "
                    + f"processing the event {event} in room {room.display_name}."
                    + f"\n{err}",
                    file=sys.stderr,
                )
                _, _, tb = sys.exc_info()
                traceback.print_tb(tb)

        # if not matched:
        #     now = datetime.now()

        #     print(
        #         "Didn't understand message from room {} \n\tmessage: {}: '{}' \n\tserver timestamp: {} \n\treceived: {}".format(
        #             room.display_name,
        #             room.user_name(event.sender),
        #             event.body,
        #             event.server_timestamp,
        #             now,
        #         )
        #     )

    async def __sync_cb(self, response: SyncResponse) -> None:
        with open(self.config.next_batch_file, "w") as next_batch_token:
            next_batch_token.write(response.next_batch)


if __name__ == "__main__":
    # Handle log output
    StreamHandler(sys.stdout).push_application()
    logger_group.add_logger(CORE_LOG)

    if True:
        logger_group.level = INFO

    # if (OUTPUT_NIO_LOGS):
    # nio_logger_group.level = nio_log.logbook.INFO

    conf = SessionConfig()
    session = Session(conf)

    try:
        CORE_LOG.info("Starting up")
        asyncio.get_event_loop().run_until_complete(session.start())
    except KeyboardInterrupt:
        asyncio.get_event_loop().run_until_complete(session.stop())
