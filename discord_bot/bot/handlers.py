from __future__ import annotations

from typing import Any

import discord


class MessageHandler:
    def __init__(self, settings: dict[str, Any], commands: dict[str, Any], responses: dict[str, str]):
        self.update_data(settings=settings, commands=commands, responses=responses)

    def update_data(self, settings: dict[str, Any], commands: dict[str, Any], responses: dict[str, str]) -> None:
        self.settings = settings
        self.commands = commands
        self.responses = responses
        self.prefix = settings.get("prefix", "!")

    def _candidate_prefixes(self) -> list[str]:
        configured_prefix = str(self.settings.get("prefix", "!")).strip() or "!"
        prefixes = [configured_prefix]
        if "-" not in prefixes:
            prefixes.append("-")
        return prefixes

    def help_text(self) -> str:
        lines = ["Available commands:"]
        for command_name, command_data in self.commands.items():
            aliases = command_data.get("aliases", [])
            description = command_data.get("description", "No description")
            alias_text = f" (aliases: {', '.join(aliases)})" if aliases else ""
            lines.append(f"- {self.prefix}{command_name}{alias_text}: {description}")
        return "\n".join(lines)

    def get_response_for(self, command_name: str) -> str | None:
        command_data = self.commands.get(command_name)
        if not command_data:
            return None

        response_key = command_data.get("response_key")
        if response_key == "_help":
            return self.help_text()

        if not response_key:
            return None

        return self.responses.get(response_key)

    def get_description_for(self, command_name: str) -> str:
        command_data = self.commands.get(command_name, {})
        description = str(command_data.get("description", "No description"))
        return description[:100]

    def command_names(self) -> list[str]:
        return list(self.commands.keys())

    def resolve_command(self, content: str) -> str | None:
        for prefix in self._candidate_prefixes():
            if not content.startswith(prefix):
                continue

            command_raw = content[len(prefix) :].strip().split(" ", maxsplit=1)[0].lower()
            for command_name, command_data in self.commands.items():
                aliases = [alias.lower() for alias in command_data.get("aliases", [])]
                if command_raw == command_name.lower() or command_raw in aliases:
                    return command_name
            return None
        return None

    async def handle_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        command_name = self.resolve_command(message.content)
        if not command_name:
            return

        response_text = self.get_response_for(command_name)
        if response_text:
            await message.channel.send(response_text)
