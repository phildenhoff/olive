import sys
import os
import importlib
import inspect
import asyncio
import traceback
from typing import Dict

from nio import AsyncClient, InviteEvent, LoginError, MatrixRoom, \
    MatrixInvitedRoom, RoomMessageText, RoomSendError, SendRetryError, \
    SyncResponse

from plugin import TextCommand, Command
from messaging import Messenger
from session_config import SessionConfig



class Session:
    client: AsyncClient = None
    config: SessionConfig = None
    plugins: Dict[str, Command] = None
    messenger: Messenger = None

    def __init__(self, config: SessionConfig):
        self.config = config
        self.client = AsyncClient(config.homeserver, config.matrix_id)
        with open(config.next_batch_file, 'r') as next_batch_token:
            self.client.next_batch = next_batch_token.read()

        # Update next_batch every sync
        self.client.add_response_callback(self.__sync_cb, SyncResponse)
        # Handle text messages
        self.client.add_event_callback(self.__message_cb, RoomMessageText)
        # Handle invites
        self.client.add_event_callback(self.__autojoin_room_cb, InviteEvent)

        self.load_plugins()
        self.messenger = Messenger(self.client)

    async def start(self) -> None:
        """Start the session.

        Logs in as the user provided in the config and begins listening for
        events to respond to.
        """
        login_status = await self.client.login(password=self.config.password, device_name='remote-bot')
        if isinstance(login_status, LoginError):
            print(f"Failed to login: {login_status}", file=sys.stderr)
            await self.stop()
        else:
            print(login_status)

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
        """Dynamially loads all plugins from the plugins directory.

        New plugins can be added by creating new classes in the `plugins` module.
        """
        self.plugins: Dict[str, Command] = {}
        importlib.import_module('plugins')
        modules = []
        plugin_files = os.listdir(os.path.join(os.path.dirname(__file__), 'plugins'))
        if len(plugin_files) == 0:
            print("NOTE: No plugin files found.")

        for plugin in plugin_files:
            if plugin.startswith("__"):
                # Skip files like __init__.py
                continue

            module_name = "plugins." + plugin.rsplit('.')[0]
            modules.append(importlib.import_module(module_name, package='plugins')) 
        
        for module in modules:
            clsmembers = inspect.getmembers(module, lambda member: inspect.isclass(member) and member.__module__ == module.__name__)
            for name, cls in clsmembers:
                if not issubclass(cls, Command):
                    # We only want plugins that derive from Command.
                    continue
                print(f"Loading plugin {name}...")
                self.plugins[name] = cls()

        print("Loaded plugins.")

    async def __send(self, room: MatrixRoom, body: str = None,
        content: dict = None) -> bool:
        # You must either include a body message or build your own content dict.
        assert body or content
        if not content:
            content = {
                "msgtype": "m.text",
                "body": body
            }
        try:
            send_status = await self.client.room_send(room.room_id,
                message_type = 'm.room.message',
                content = content 
            )
        except SendRetryError as err:
            print(f"Failed to send message '{body}' to room '{room}'. Error:\n{err}")
            return False

        if isinstance(send_status, RoomSendError):
            print(send_status)
            return False
    
        return True
    
    async def __autojoin_room_cb(self, room: MatrixInvitedRoom, event: InviteEvent) -> None:
        if (room.room_id not in self.client.rooms):
            await self.client.join(room.room_id)
            await self.__send(room, f"Hello, {room.display_name}!")

            # TODO: Replace forced client sync. I'd like to avoid handling the
            # Invite event three times, but dont' want to force syncs. Probably
            # not common enought to matter?
            await self.client.sync(300)
            
    async def __message_cb(self, room: MatrixRoom, event: RoomMessageText):
        tokens = list(filter(lambda x: x != " " and x != "", event.body.split(" ")))

        if event.sender == self.client.user_id:
            # Message is from us; we can ignore.
            return

        if room.is_group and room.member_count == 2:
          if not tokens[0].startswith(self.config.username):
                tokens = [self.config.username] + tokens
        if not tokens[0].startswith(self.config.username):
            return

        matched = False
        for name, plugin in self.plugins.items():
            if isinstance(plugin, TextCommand):
                if plugin.is_triggered(tokens):
                    matched = True
                    try:
                        await plugin.process_event(room, event, self.messenger)
                        # await self.__send(room, content=plugin.process_event(room, event))
                    except Exception as err:
                        print(f"Plugin {name} encountered an error while " + \
                            f"processing the event {event} in room {room.display_name}." + \
                            f"\n{err}", file=sys.stderr)
                        _, _, tb = sys.exc_info()
                        traceback.print_tb(tb)

        if not matched:
            print(
                "Didn't understand message from room: {} | {}: '{}'".format(
                    room.display_name, room.user_name(event.sender), event.body
                )
            )

    async def __sync_cb(self, response: SyncResponse) -> None:
        with open(self.config.next_batch_file, "w") as next_batch_token:
            next_batch_token.write(response.next_batch)

if __name__ == "__main__":
    conf = SessionConfig()
    session = Session(conf)

    try:
        asyncio.get_event_loop().run_until_complete(session.start())
    except KeyboardInterrupt:
        asyncio.get_event_loop().run_until_complete(session.stop())