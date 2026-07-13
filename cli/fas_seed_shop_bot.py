import os

# Dedicated Seed Shop bot entrypoint.
os.environ["FAS_BOT_MODE"] = "seed"

from fas_farmers_bot import bot, TOKEN


if __name__ == "__main__":
    bot.run(TOKEN)
