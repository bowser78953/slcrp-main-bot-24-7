const { Client, Intents } = require("discord.js");
const client = new Client({ intents: [Intents.FLAGS.GUILDS, Intents.FLAGS.GUILD_MESSAGES] });

// Load commands
// Load events

// Start services
require("./services/stockNotifier")(client);
require("./services/weatherNotifier")(client);
require("./services/giveawayManager")(client);
require("./services/reminders")(client);

// Log in
const config = require("./config");
client.login(config.token);
