import asyncio
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discord_bot.bot.client import FarmersDiscordBot


class DummyMessage:
    def __init__(self, content: str, channel=None):
        self.content = content
        self.channel = channel
        self.author = type("Author", (), {"bot": False})()


class DummyChannel:
    def __init__(self):
        self.messages = []

    async def send(self, content):
        self.messages.append(content)


class ReloadHandlerTests(unittest.TestCase):
    def test_handle_reload_command_accepts_dash_prefix_even_when_config_prefix_is_not_dash(self):
        base_path = Path(__file__).resolve().parents[1]
        bot = FarmersDiscordBot(base_path=base_path)
        bot.settings["prefix"] = "!"
        channel = DummyChannel()
        message = DummyMessage("-reload giveaway", channel=channel)

        async def fake_reload_json_if_needed():
            return None

        async def fake_force_reload():
            return True, False

        async def fake_register_slash_commands():
            return None

        class DummyTree:
            async def sync(self):
                return None

        bot.reload_json_if_needed = fake_reload_json_if_needed
        bot.force_reload = fake_force_reload
        bot._register_slash_commands = fake_register_slash_commands
        bot.tree = DummyTree()

        handled = asyncio.run(bot.handle_reload_command(message))

        self.assertTrue(handled)
        self.assertTrue(channel.messages)
        self.assertIn("Reloaded catagory", channel.messages[0])


if __name__ == "__main__":
    unittest.main()
