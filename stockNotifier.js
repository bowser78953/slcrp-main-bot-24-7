const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('stock notifier set up')
        .setDescription('Sets up the stock notifier in your server'),

        .addSubcommand(
            subcommand
                .setName('setup')
                .setDescription('Sets up the stock notifier')
                .addStringOption(option =>
                    option
                        .setName('channel')
                        .setDescription('The channel to send stock notifications to')
                        .setRequired(true)
                )
                .addRoleOption(option =>
                    option
                        .setName('ping_role_for_carrot')
                        .setDescription('The role to ping for carrot notifications')
                        .setRequired(false)
                )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_strawberry')
                        .setDescription('The role to ping for strawberry notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_blueberry')
                        .setDescription('The role to ping for blueberry notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_apple')
                        .setDescription('The role to ping for apple notifications')
                        .setRequired(false)
                        )
                            .addRoleOption(option =>
                    option
                        .setName('ping_role_for_tomato')
                        .setDescription('The role to ping for tomato notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_tulip')
                        .setDescription('The role to ping for tulip notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_bamboo')
                        .setDescription('The role to ping for bamboo notifications')
                        .setRequired(false)
                        )
                       .addRoleOption(option =>
                    option
                        .setName('ping_role_for_cactus')
                        .setDescription('The role to ping for cactus notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_corn')
                        .setDescription('The role to ping for corn notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_pineapple')
                        .setDescription('The role to ping for pineapple notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_cactus')
                        .setDescription('The role to ping for cactus notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_mango')
                        .setDescription('The role to ping for mango notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_bamboo')
                        .setDescription('The role to ping for bamboo notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_coconut')
                        .setDescription('The role to ping for coconut notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_grape')
                        .setDescription('The role to ping for grape notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_green_bean')
                        .setDescription('The role to ping for green bean notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_mushroom')
                        .setDescription('The role to ping for mushroom notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_acorn')
                        .setDescription('The role to ping for acorn notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_cherry')
                        .setDescription('The role to ping for cherry notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_dragon_fruit')
                        .setDescription('The role to ping for dragon fruit notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_fire_fern')
                        .setDescription('The role to ping for fire fern notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_sunflower')
                        .setDescription('The role to ping for sunflower notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_poison_apple')
                        .setDescription('The role to ping for poison apple notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_pomegranate')
                        .setDescription('The role to ping for pomegranate notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_venom_spitter')
                        .setDescription('The role to ping for venom spitter notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_venus_fly_trap')
                        .setDescription('The role to ping for venus fly trap notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_dragons_breath')
                        .setDescription('The role to ping for dragon\'s breath notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_hypno_bloom')
                        .setDescription('The role to ping for hypno bloom notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_moon_bloom')
                        .setDescription('The role to ping for moon bloom notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_sun_bloom')
                        .setDescription('The role to ping for sun bloom notifications')
                        .setRequired(false)
                        )
                        .addRoleOption(option =>
                    option
                        .setName('ping_role_for_star_fruit')
                        .setDescription('The role to ping for star fruit notifications')
                        .setRequired(false)
                        )
             
             
             
        ),
    }

     execute(interaction) {
        const channel = interaction.options.getChannel("channel");
        const carrotRole = interaction.options.getRole("carrot_ping_role");
        const strawberryRole = interaction.options.getRole("strawberry_ping_role");
        const blueberryRole = interaction.options.getRole("blueberry_ping_role");
        const appleRole = interaction.options.getRole("apple_ping_role");
        const tomatoRole = interaction.options.getRole("tomato_ping_role");
        const tulipRole = interaction.options.getRole("tulip_ping_role");
        const bambooRole = interaction.options.getRole("bamboo_ping_role");
        const cactusRole = interaction.options.getRole("cactus_ping_role");
        const cornRole = interaction.options.getRole("corn_ping_role");
        const pineappleRole = interaction.options.getRole("pineapple_ping_role");
        const mangoRole = interaction.options.getRole("mango_ping_role");
        const coconutRole = interaction.options.getRole("coconut_ping_role");
        const grapeRole = interaction.options.getRole("grape_ping_role");
        const greenBeanRole = interaction.options.getRole("green_bean_ping_role");
        const mushroomRole = interaction.options.getRole("mushroom_ping_role");
        const acornRole = interaction.options.getRole("acorn_ping_role");
        const cherryRole = interaction.options.getRole("cherry_ping_role");
        const dragonFruitRole = interaction.options.getRole("dragon_fruit_ping_role");
        const fireFernRole = interaction.options.getRole("fire_fern_ping_role");
        const sunflowerRole = interaction.options.getRole("sunflower_ping_role");
        const poisonAppleRole = interaction.options.getRole("poison_apple_ping_role");
        const pomegranateRole = interaction.options.getRole("pomegranate_ping_role");
        const venomSpitterRole = interaction.options.getRole("venom_spitter_ping_role");
        const venusFlyTrapRole = interaction.options.getRole("venus_fly_trap_ping_role");
        const dragonsBreathRole = interaction.options.getRole("dragons_breath_ping_role");
        const hypnoBloomRole = interaction.options.getRole("hypno_bloom_ping_role");
        const moonBloomRole = interaction.options.getRole("moon_bloom_ping_role");
        const sunBloomRole = interaction.options.getRole("sun_bloom_ping_role");
        const starFruitRole = interaction.options.getRole("star_fruit_ping_role");
     

        await interaction.reply(
            `Setup complete!\n` +
            `Channel: ${channel}\n` +
            `Carrot Role: ${carrotRole}\n` +
            `Strawberry Role: ${strawberryRole}\n` +
            `Blueberry Role: ${blueberryRole}\n` +
            `Apple Role: ${appleRole}\n` +
            `Tomato Role: ${tomatoRole}\n` +
            `Tulip Role: ${tulipRole}\n` +
            `Bamboo Role: ${bambooRole}\n` +
            `Cactus Role: ${cactusRole}\n` +
            `Corn Role: ${cornRole}\n` +
            `Pineapple Role: ${pineappleRole}\n` +
            `Mango Role: ${mangoRole}\n` +
            `Coconut Role: ${coconutRole}\n` +
            `Grape Role: ${grapeRole}\n` +
            `Green Bean Role: ${greenBeanRole}\n` +
            `Mushroom Role: ${mushroomRole}\n` +
            `Acorn Role: ${acornRole}\n` +
            `Cherry Role: ${cherryRole}\n` +
            `Dragon Fruit Role: ${dragonFruitRole}\n` +
            `Fire Fern Role: ${fireFernRole}\n` +
            `Sunflower Role: ${sunflowerRole}\n` +
            `Poison Apple Role: ${poisonAppleRole}\n` +
            `Pomegranate Role: ${pomegranateRole}\n` +
            `Venom Spitter Role: ${venomSpitterRole}\n` +
            `Venus Fly Trap Role: ${venusFlyTrapRole}\n` +
            `Dragon's Breath Role: ${dragonsBreathRole}\n` +
            `Hypno Bloom Role: ${hypnoBloomRole}\n` +
            `Moon Bloom Role: ${moonBloomRole}\n` +
            `Sun Bloom Role: ${sunBloomRole}\n` +
            `Star Fruit Role: ${starFruitRole}\n`
        );
    }



         
