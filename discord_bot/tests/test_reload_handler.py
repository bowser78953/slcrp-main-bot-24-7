import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discord_bot.bot.client import FarmersDiscordBot
from discord_bot.bot.handlers import MessageHandler
from discord_bot.bot.json_store import JsonStore


class DummyMessage:
    def __init__(self, content: str, channel=None):
        self.content = content
        self.channel = channel
        self.author = type("Author", (), {"bot": False})()


class DummyChannel:
    def __init__(self):
        self.messages = []
        self.sent_messages = []
        self.send_kwargs = []

    async def send(self, content=None, **kwargs):
        self.messages.append(content)
        sent_message = DummySentMessage(self, len(self.messages) - 1, content)
        self.sent_messages.append(sent_message)
        self.send_kwargs.append(kwargs)
        return sent_message


class DummySentMessage:
    def __init__(self, channel, index, content):
        self.channel = channel
        self.index = index
        self.id = 9000 + index
        self.content = content
        self.initial_content = content
        self.edits = []

    async def edit(self, content):
        self.content = content
        self.channel.messages[self.index] = content
        self.edits.append(content)


class DummyAuditChannel:
    def __init__(self):
        self.messages = []

    async def send(self, **kwargs):
        self.messages.append(kwargs)
        return SimpleNamespace(id=8000 + len(self.messages))


class DummyRole:
    def __init__(self, role_id, position, assignable=True):
        self.id = role_id
        self.position = position
        self.assignable = assignable

    def is_assignable(self):
        return self.assignable


class DummyPurgeMessage:
    def __init__(self, message_id, content, author, created_at):
        self.id = message_id
        self.content = content
        self.clean_content = content
        self.author = author
        self.created_at = created_at
        self.attachments = []


class DummyPurgeChannel(DummyChannel):
    def __init__(self, deleted_messages):
        super().__init__()
        self.id = 808
        self.name = "general"
        self.deleted_messages = deleted_messages
        self.purge_limit = None

    def permissions_for(self, member):
        return SimpleNamespace(manage_messages=True)

    async def purge(self, *, limit, check, reason):
        self.purge_limit = limit
        return [deleted for deleted in self.deleted_messages if check(deleted)][:limit]


class ReloadHandlerTests(unittest.TestCase):
    def test_lockchannel_denies_typing_and_question_unlock_restores_overwrites(self):
        everyone = SimpleNamespace(id=1)
        protected_role = SimpleNamespace(id=1554697553461903400)
        bot_member = SimpleNamespace(id=2)
        initial_overwrites = {
            everyone.id: None,
            protected_role.id: True,
            bot_member.id: None,
        }
        channel = MagicMock(spec=discord.VoiceChannel)
        channel.id = 303
        channel.permissions_for.return_value = SimpleNamespace(manage_channels=True)

        def get_overwrite(target):
            return discord.PermissionOverwrite(send_messages=initial_overwrites.get(target.id))

        channel.overwrites_for.side_effect = get_overwrite

        async def set_permissions(target, *, overwrite, reason):
            initial_overwrites[target.id] = overwrite.send_messages if overwrite else None

        channel.set_permissions = AsyncMock(side_effect=set_permissions)
        channel.send = AsyncMock()
        guild = SimpleNamespace(
            id=404,
            icon=None,
            default_role=everyone,
            me=bot_member,
            get_role=lambda role_id: protected_role if role_id == protected_role.id else None,
        )
        author = SimpleNamespace(
            id=55,
            guild_permissions=SimpleNamespace(administrator=False, manage_channels=True),
        )
        store_saves = []
        bot = SimpleNamespace(
            handler=MessageHandler(settings={"prefix": "-"}, commands={}, responses={}),
            channel_lock_snapshots={},
            giveaways={},
            giveaway_ping_roles={},
            automod_cases={},
            last_moderation_cases={},
            persistent_state_store=SimpleNamespace(save=lambda data: store_saves.append(deepcopy(data))),
        )
        bot._save_persistent_state = lambda: FarmersDiscordBot._save_persistent_state(bot)
        bot._matches_prefix_command = lambda token, command: (
            FarmersDiscordBot._matches_prefix_command(bot, token, command)
        )
        bot._set_send_messages_overwrite = lambda target_channel, target, value, reason: (
            FarmersDiscordBot._set_send_messages_overwrite(bot, target_channel, target, value, reason)
        )
        bot._build_channel_lock_embed = lambda target_guild, locked: (
            FarmersDiscordBot._build_channel_lock_embed(bot, target_guild, locked)
        )

        locked_message = SimpleNamespace(content="!lockchannel", guild=guild, channel=channel, author=author)
        self.assertTrue(asyncio.run(FarmersDiscordBot._handle_channel_lock_command(bot, locked_message)))
        self.assertFalse(initial_overwrites[everyone.id])
        self.assertFalse(initial_overwrites[protected_role.id])
        self.assertTrue(initial_overwrites[bot_member.id])
        lock_embed = channel.send.await_args.kwargs["embed"]
        self.assertIn("Channel Locked", lock_embed.description)

        unlocked_message = SimpleNamespace(content="?unlock", guild=guild, channel=channel, author=author)
        self.assertTrue(asyncio.run(FarmersDiscordBot._handle_channel_lock_command(bot, unlocked_message)))
        self.assertIsNone(initial_overwrites[everyone.id])
        self.assertTrue(initial_overwrites[protected_role.id])
        self.assertIsNone(initial_overwrites[bot_member.id])
        unlock_embed = channel.send.await_args.kwargs["embed"]
        self.assertIn("Channel Unlocked", unlock_embed.description)
        self.assertFalse(bot.channel_lock_snapshots)
        self.assertEqual(len(store_saves), 2)

    def test_giveaway_and_ping_role_state_round_trips_through_json(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JsonStore(Path(directory) / "bot_state.json")
            original = SimpleNamespace(
                persistent_state_store=store,
                giveaways={
                    123: {
                        "giveaway_id": 123,
                        "guild_id": 303,
                        "channel_id": 404,
                        "end_ts": 500,
                        "entries": {11, 22},
                        "ended": False,
                        "winner_ids": [],
                        "result_posted": False,
                    }
                },
                giveaway_ping_roles={303: 505},
                channel_lock_snapshots={
                    "808": {
                        "guild_id": 303,
                        "channel_id": 808,
                        "overwrites": {"1": None, "2": True},
                    }
                },
                automod_cases={"123": {"guild_id": 303, "resolution": None}},
                last_moderation_cases={"303:11": "Ban"},
            )

            FarmersDiscordBot._save_persistent_state(original)

            restored = SimpleNamespace(
                persistent_state_store=store,
                giveaways={},
                giveaway_ping_roles={},
                channel_lock_snapshots={},
                automod_cases={},
                last_moderation_cases={},
            )
            FarmersDiscordBot._load_persistent_state(restored)

            self.assertEqual(restored.giveaways[123]["entries"], {11, 22})
            self.assertEqual(restored.giveaways[123]["end_ts"], 500)
            self.assertEqual(restored.giveaway_ping_roles, {303: 505})
            self.assertEqual(restored.channel_lock_snapshots, original.channel_lock_snapshots)
            self.assertEqual(restored.automod_cases, original.automod_cases)
            self.assertEqual(restored.last_moderation_cases, original.last_moderation_cases)

    def test_automod_logs_word_case_and_persists_button_resolution(self):
        cc_role = SimpleNamespace(id=1554635863739080764)
        guild = SimpleNamespace(
            id=303,
            name="Test Server",
            icon=None,
            get_role=lambda role_id: cc_role if role_id == cc_role.id else None,
        )
        channel = SimpleNamespace(id=404, mention="<#404>")
        author = SimpleNamespace(id=55, bot=False, roles=[])
        message = SimpleNamespace(
            id=123,
            content="You said BITCH loudly.",
            clean_content="You said BITCH loudly.",
            guild=guild,
            channel=channel,
            author=author,
        )
        audit_channel = DummyAuditChannel()
        saved_states = []
        bot = SimpleNamespace(
            automod_cases={},
            last_moderation_cases={},
            persistent_state_store=SimpleNamespace(save=lambda state: saved_states.append(deepcopy(state))),
            giveaways={},
            giveaway_ping_roles={},
            channel_lock_snapshots={},
            get_channel=lambda channel_id: audit_channel,
        )
        bot._save_persistent_state = lambda: FarmersDiscordBot._save_persistent_state(bot)
        bot._build_automod_audit_view = lambda target_message, word, case_id: (
            FarmersDiscordBot._build_automod_audit_view(bot, target_message, word, case_id)
        )

        triggered = asyncio.run(FarmersDiscordBot._handle_automod_message(bot, message))

        self.assertTrue(triggered)
        self.assertEqual(bot.automod_cases["123"]["word"], "BITCH")
        audit_view = audit_channel.messages[0]["view"]
        components = audit_view.to_components()[0]["components"]
        audit_text = "\n".join(component.get("content", "") for component in components)
        self.assertIn("# Automod Triggered", audit_text)
        self.assertIn("**Last Case:** N/A", audit_text)
        self.assertIn("||BITCH||", audit_text)
        action_row = next(component for component in components if component["type"] == 1)
        self.assertEqual([button["style"] for button in action_row["components"]], [3, 4])
        self.assertEqual(audit_channel.messages[0]["allowed_mentions"].roles, [cc_role])

        class DummyResponse:
            def __init__(self):
                self.edited = None
                self.messages = []

            async def edit_message(self, **kwargs):
                self.edited = kwargs

            async def send_message(self, content, *, ephemeral=False):
                self.messages.append((content, ephemeral))

        class DummyFollowup:
            def __init__(self):
                self.messages = []

            async def send(self, content, **kwargs):
                self.messages.append((content, kwargs))

        permissions = SimpleNamespace(administrator=False, manage_messages=True)
        moderator = SimpleNamespace(id=66, guild_permissions=permissions)
        response = DummyResponse()
        followup = DummyFollowup()
        interaction = SimpleNamespace(
            guild=guild,
            user=moderator,
            response=response,
            followup=followup,
        )

        asyncio.run(
            FarmersDiscordBot._handle_automod_case_interaction(
                bot,
                interaction,
                "automod-case:take:123",
            )
        )

        self.assertEqual(bot.automod_cases["123"]["resolution"], "take")
        self.assertEqual(bot.automod_cases["123"]["resolved_by"], 66)
        self.assertIsNone(response.edited["view"])
        self.assertIn("Has moderated the user.", followup.messages[0][0])
        self.assertTrue(saved_states)

        bot.automod_cases["124"] = {"guild_id": 303, "user_id": 55, "resolution": None}
        response = DummyResponse()
        interaction.response = response
        asyncio.run(
            FarmersDiscordBot._handle_automod_case_interaction(
                bot,
                interaction,
                "automod-case:dismiss:124",
            )
        )
        self.assertEqual(bot.automod_cases["124"]["resolution"], "dismiss")
        self.assertIn("Has dismissed this case.", followup.messages[-1][0])

        exempt_message = SimpleNamespace(
            id=125,
            content="ass",
            guild=guild,
            channel=channel,
            author=SimpleNamespace(
                id=77,
                bot=False,
                roles=[SimpleNamespace(id=1556404763887800370)],
            ),
        )
        self.assertFalse(asyncio.run(FarmersDiscordBot._handle_automod_message(bot, exempt_message)))
        self.assertEqual(len(audit_channel.messages), 1)

    def test_cmds_with_bang_prefix_shows_command_list(self):
        handler = MessageHandler(
            settings={"prefix": "-"},
            commands={
                "cmds": {"description": "Show commands", "response_key": "_help", "aliases": []},
                "ping": {"description": "Bot replies with pong", "response_key": "pong_text", "aliases": []},
                "rules": {"description": "Show rules", "response_key": "rules_text", "aliases": ["rule"]},
                "farm": {"description": "Show checklist", "response_key": "farm_checklist", "aliases": ["checklist"]},
                "giveaway": {"description": "Show giveaway info", "response_key": "giveaway_text", "aliases": ["gaw", "give"]},
                "hello": {"description": "Say hello", "response_key": "hello_text", "aliases": ["hi"]},
            },
            responses={"pong_text": "Pong"},
        )

        command_name = handler.resolve_command("!cmds")
        response = handler.get_response_for(command_name) if command_name else None

        self.assertEqual(command_name, "cmds")
        self.assertIn("-cmds", response)
        self.assertIn("-ping", response)
        self.assertNotIn("-rules", response)
        self.assertNotIn("-farm", response)
        self.assertNotIn("-giveaway", response)
        self.assertNotIn("-hello", response)

    def test_gsban_requires_admin_and_bans_across_connected_guilds(self):
        first_guild = SimpleNamespace(id=101, ban=AsyncMock())
        second_guild = SimpleNamespace(id=202, ban=AsyncMock())
        audit_channel = DummyAuditChannel()
        bot = SimpleNamespace(
            handler=MessageHandler(settings={"prefix": "-"}, commands={}, responses={}),
            guilds=[first_guild, second_guild],
            last_moderation_cases={},
            user=SimpleNamespace(id=999),
            _save_persistent_state=lambda: None,
            get_channel=lambda channel_id: audit_channel,
            _handle_global_server_moderation=lambda message, action: (
                FarmersDiscordBot._handle_global_server_moderation(bot, message, action)
            ),
            _build_global_moderation_audit_view=lambda action, user_id, executor_id, reason: (
                FarmersDiscordBot._build_global_moderation_audit_view(None, action, user_id, executor_id, reason)
            ),
            _build_global_ban_audit_view=lambda user_id, executor_id, reason: (
                FarmersDiscordBot._build_global_ban_audit_view(None, user_id, executor_id, reason)
            ),
        )
        author = SimpleNamespace(
            id=55,
            bot=False,
            guild_permissions=SimpleNamespace(administrator=True),
        )
        channel = DummyChannel()
        message = SimpleNamespace(
            content="!gsban <@!123> repeated spam",
            guild=SimpleNamespace(id=303),
            author=author,
            channel=channel,
        )

        handled = asyncio.run(FarmersDiscordBot._handle_global_server_ban(bot, message))

        self.assertTrue(handled)
        self.assertEqual(len(channel.messages), 1)
        self.assertIn("User has been banned from **2**", channel.messages[0])
        self.assertIn("Banning user from **2**", channel.sent_messages[0].initial_content)
        first_guild.ban.assert_awaited_once()
        second_guild.ban.assert_awaited_once()
        self.assertEqual(first_guild.ban.await_args.args[0].id, 123)
        self.assertEqual(len(audit_channel.messages), 1)
        self.assertEqual(
            bot.last_moderation_cases,
            {"101:123": "Ban", "202:123": "Ban"},
        )

        first_guild.ban.reset_mock()
        second_guild.ban.reset_mock()
        author.guild_permissions.administrator = False
        channel.messages.clear()

        asyncio.run(FarmersDiscordBot._handle_global_server_ban(bot, message))

        self.assertFalse(first_guild.ban.await_count)
        self.assertFalse(second_guild.ban.await_count)
        self.assertIn("Administrator", channel.messages[0])

    def test_gsunban_unbans_across_guilds_and_counts_already_unbanned(self):
        first_guild = SimpleNamespace(id=101, unban=AsyncMock())
        not_found = discord.NotFound(
            SimpleNamespace(status=404, reason="Not Found", headers={}),
            "unknown ban",
        )
        second_guild = SimpleNamespace(id=202, unban=AsyncMock(side_effect=not_found))
        audit_channel = DummyAuditChannel()
        bot = SimpleNamespace(
            handler=MessageHandler(settings={"prefix": "-"}, commands={}, responses={}),
            guilds=[first_guild, second_guild],
            user=SimpleNamespace(id=999),
            get_channel=lambda channel_id: audit_channel,
        )
        bot._handle_global_server_moderation = lambda message, action: (
            FarmersDiscordBot._handle_global_server_moderation(bot, message, action)
        )
        bot._build_global_moderation_audit_view = lambda action, user_id, executor_id, reason: (
            FarmersDiscordBot._build_global_moderation_audit_view(None, action, user_id, executor_id, reason)
        )
        author = SimpleNamespace(
            id=55,
            bot=False,
            guild_permissions=SimpleNamespace(administrator=True),
        )
        channel = DummyChannel()
        message = SimpleNamespace(
            content="!gsunban 123 appeal reviewed",
            guild=SimpleNamespace(id=303),
            author=author,
            channel=channel,
        )

        handled = asyncio.run(FarmersDiscordBot._handle_global_server_unban(bot, message))

        self.assertTrue(handled)
        self.assertEqual(len(channel.messages), 1)
        self.assertIn("User has been unbanned from **1**", channel.messages[0])
        self.assertIn("not banned in **1**", channel.messages[0])
        self.assertIn("Unbanning user from **2**", channel.sent_messages[0].initial_content)
        first_guild.unban.assert_awaited_once()
        second_guild.unban.assert_awaited_once()
        self.assertEqual(first_guild.unban.await_args.args[0].id, 123)
        self.assertEqual(len(audit_channel.messages), 1)
        audit_view = audit_channel.messages[0]["view"]
        self.assertIn("Global Server Unban", audit_view.children[0].children[0].content)

    def test_role_commands_save_remove_and_restore_roles_at_threshold(self):
        threshold_role = DummyRole(1554533334955069632, 10)
        higher_role = DummyRole(300, 20)
        lower_role = DummyRole(200, 9)
        member = SimpleNamespace(
            roles=[lower_role, threshold_role, higher_role],
            remove_roles=AsyncMock(),
            add_roles=AsyncMock(),
        )
        guild_roles = [lower_role, threshold_role, higher_role]
        guild = SimpleNamespace(
            id=303,
            roles=guild_roles,
            get_role=lambda role_id: threshold_role if role_id == threshold_role.id else None,
            get_member=lambda user_id: member,
            fetch_member=AsyncMock(),
        )
        audit_channel = DummyAuditChannel()
        saved_data = []
        bot = SimpleNamespace(
            handler=MessageHandler(settings={"prefix": "-"}, commands={}, responses={}),
            saved_roles={},
            saved_roles_store=SimpleNamespace(save=lambda data: saved_data.append(deepcopy(data))),
            get_channel=lambda channel_id: audit_channel,
            _build_global_moderation_audit_view=lambda action, user_id, executor_id, reason: (
                FarmersDiscordBot._build_global_moderation_audit_view(None, action, user_id, executor_id, reason)
            ),
        )
        author = SimpleNamespace(
            id=55,
            bot=False,
            guild_permissions=SimpleNamespace(administrator=True),
        )
        channel = DummyChannel()

        for action in ("sr", "tar", "gar"):
            message = SimpleNamespace(
                content=f"!{action} <@123>",
                guild=guild,
                author=author,
                channel=channel,
            )
            handled = asyncio.run(FarmersDiscordBot._handle_global_role_command(bot, message))
            self.assertTrue(handled)

            if action == "sr":
                self.assertEqual(bot.saved_roles["123"]["303"], [threshold_role.id, higher_role.id])
                self.assertIn("Number of roles: **2**", channel.sent_messages[-1].initial_content)
            elif action == "tar":
                member.remove_roles.assert_awaited_once_with(
                    threshold_role,
                    higher_role,
                    reason="Global role removal by namespace(id=55, bot=False, guild_permissions=namespace(administrator=True)) (55)",
                )
                member.roles = [lower_role]
            else:
                member.add_roles.assert_awaited_once_with(
                    threshold_role,
                    higher_role,
                    reason="Global role restore by namespace(id=55, bot=False, guild_permissions=namespace(administrator=True)) (55)",
                )

            self.assertEqual(len(channel.messages), len(channel.sent_messages))
            self.assertTrue(channel.sent_messages[-1].edits)
            self.assertIn("<a:loading:1554695304152875038>", channel.sent_messages[-1].initial_content)
            audit_view = audit_channel.messages[-1]["view"]
            expected_title = {
                "sr": "# Save all Roles Audit Logs",
                "tar": "# Take All Roles Audit Logs",
                "gar": "# Give all roles Audit Logs",
            }[action]
            audit_text = "\n".join(item.content for item in audit_view.children[0].children if isinstance(item, discord.ui.TextDisplay))
            self.assertIn(expected_title, audit_text)
            self.assertNotIn("***Reason:***", audit_text)

        self.assertEqual(len(saved_data), 2)
        self.assertEqual(len(audit_channel.messages), 3)

    def test_clear_saves_transcript_logs_and_retrieves_by_id(self):
        now = datetime.now(timezone.utc)
        author = SimpleNamespace(
            id=55,
            bot=False,
            guild_permissions=SimpleNamespace(administrator=False, manage_messages=True),
        )
        command_message = DummyPurgeMessage(1234, "!clear 2", author, now)
        earlier_messages = [
            DummyPurgeMessage(1001, "first deleted", SimpleNamespace(id=71), now),
            DummyPurgeMessage(1002, "second deleted", SimpleNamespace(id=72), now),
        ]
        channel = DummyPurgeChannel([command_message, *earlier_messages])
        guild = SimpleNamespace(id=303, name="Test Server", me=SimpleNamespace(id=999))
        channel_message = SimpleNamespace(
            id=command_message.id,
            content="!clear 2",
            guild=guild,
            channel=channel,
            author=author,
        )
        audit_channel = DummyAuditChannel()
        saved_transcripts = []
        bot = SimpleNamespace(
            handler=MessageHandler(settings={"prefix": "-"}, commands={}, responses={}),
            clear_transcripts={},
            clear_transcripts_store=SimpleNamespace(save=lambda data: saved_transcripts.append(deepcopy(data))),
            _matches_prefix_command=lambda token, command: (
                FarmersDiscordBot._matches_prefix_command(bot, token, command)
            ),
            get_channel=lambda channel_id: audit_channel,
            _build_clear_audit_view=lambda executor_id, count, transcript_id: (
                FarmersDiscordBot._build_clear_audit_view(None, executor_id, count, transcript_id)
            ),
        )

        handled = asyncio.run(FarmersDiscordBot._handle_clear_command(bot, channel_message))

        self.assertTrue(handled)
        self.assertEqual(channel.purge_limit, 4)
        self.assertEqual(len(channel.messages), 1)
        self.assertIn("**2** messages have been cleared", channel.messages[0])
        self.assertIn("<a:loading:1554695304152875038>", channel.sent_messages[0].initial_content)
        self.assertIn("first deleted", bot.clear_transcripts["1234"]["transcript"])
        self.assertEqual(bot.clear_transcripts["1234"]["message_count"], 2)
        self.assertEqual(len(saved_transcripts), 1)
        audit_text = "\n".join(
            item.content
            for item in audit_channel.messages[0]["view"].children[0].children
            if isinstance(item, discord.ui.TextDisplay)
        )
        self.assertIn("# Clear Audit Log", audit_text)
        self.assertIn("1234", audit_text)

        transcript_request = SimpleNamespace(
            content="!cleartranscript 1234",
            guild=guild,
            channel=channel,
            author=author,
        )
        retrieved = asyncio.run(FarmersDiscordBot._handle_clear_transcript_command(bot, transcript_request))
        self.assertTrue(retrieved)
        self.assertIn("clear-transcript-1234.txt", channel.send_kwargs[-1]["file"].filename)

    def test_build_winner_announcement_mentions_all_winners(self):
        base_path = Path(__file__).resolve().parents[1]
        bot = FarmersDiscordBot(base_path=base_path)
        giveaway = {"prize": "a Steam gift card"}
        winners = [101, 202]

        announcement = bot._build_winner_announcement(giveaway, winners)

        self.assertIn("<@101>", announcement)
        self.assertIn("<@202>", announcement)
        self.assertIn("a Steam gift card", announcement)
        self.assertIn("Congrats!", announcement)

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
            async def sync(self, guild=None):
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
