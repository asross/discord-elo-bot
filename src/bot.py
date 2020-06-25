"""Bot core."""


import os
import _pickle as pickle
import discord
from discord.ext import commands
from discord.ext.commands import has_permissions, MissingPermissions
from dotenv import load_dotenv
from player import Player
from game import Game
from decorators import is_arg_in_modes
from decorators import check_category
from decorators import check_channel

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')


BOT = commands.Bot(command_prefix='!')
GAMES = {}


def load_file_to_game(guild_id):
    """Load the file from ./data/guild_id to Game if exists, return True."""
    try:
        with open(f'./data/{guild_id}.data', "rb") as file:
            return pickle.load(file)
    except IOError:
        print("The file couldn't be loaded")


@BOT.event
async def on_ready():
    """On ready event."""
    print(f'{BOT.user} has connected\n')
    guild = BOT.get_guild(int(GUILD))
    GAMES[guild.id] = load_file_to_game(guild.id)
    if GAMES[guild.id] is not None:
        print(f"The file from data/{guild.id}.data was correctly loaded.")
        return

    GAMES[guild.id] = Game(guild.id)


@BOT.event
async def on_command_completion(ctx):
    """Save the data after every command."""
    GAMES[ctx.guild.id].save_to_file()
    print(f"The data has been saved after the command: {ctx.message.content}")


@BOT.event
async def on_guild_channel_create(channel):
    """Save the data when a channel is created."""

    if channel.name[0].isdigit():
        GAMES[int(channel.guild.id)].save_to_file()
        print("Data has been saved since a new mode was added.")


@BOT.command()
@has_permissions(manage_roles=True)
async def init_elo_by_anddy(ctx):
    """Initialize the bot to be ready on a guild.

    This command creates every channel needed for the Bot to work.
    This also build two categories Elo by Anddy and Modes
    Can be used anywhere. No alias, Need to have manage_roles
    """
    guild = ctx.guild
    if not discord.utils.get(guild.roles, name="Elo Admin"):
        await guild.create_role(name="Elo Admin",
                                permissions=discord.Permissions.all_channel())
        print("Elo admin created")

    if not discord.utils.get(guild.categories, name='Elo by Anddy'):
        perms_secret_chan = {
            guild.default_role:
                discord.PermissionOverwrite(read_messages=False),
            guild.me:
                discord.PermissionOverwrite(read_messages=True),
            discord.utils.get(guild.roles, name="Elo Admin"):
                discord.PermissionOverwrite(read_messages=True)
        }

        base_cat = await guild.create_category(name="Elo by Anddy")
        await guild.create_text_channel(name="Init",
                                        category=base_cat,
                                        overwrites=perms_secret_chan)
        await guild.create_text_channel(name="Moderators",
                                        category=base_cat,
                                        overwrites=perms_secret_chan)
        await guild.create_text_channel(name="Info_chat", category=base_cat)
        await guild.create_text_channel(name="Register", category=base_cat)
        await guild.create_text_channel(name="Submit", category=base_cat)
        await guild.create_text_channel(name="Game_announcement",
                                        category=base_cat)
        await guild.create_text_channel(name="Staff_application",
                                        category=base_cat)
        await guild.create_text_channel(name="Suggestions",
                                        category=base_cat)
        await guild.create_text_channel(name="Bans",
                                        category=base_cat)
        await guild.create_text_channel(name="bye",
                                        category=base_cat)

        await guild.create_category(name="Modes")

        print("Elo by Anddy created, init done, use !help !")


@BOT.command(pass_context=True, aliases=['j'])
@check_category('Modes')
async def join(ctx):
    """Let the player join a queue.

    When using it on a channel in Modes category, the user will join the
    current queue, meaning that he'll be in the list to play the next match.
    Can't be used outside Modes category.
    The user can leave afterward by using !l.
    The user needs to have previously registered in this mode."""
    game = GAMES[BOT.get_guild(int(GUILD)).id]
    mode = int(ctx.channel.name[0])
    name = '_'.join(ctx.author.name.split())
    if name in game.leaderboards[mode]:
        player = game.leaderboards[mode][name]
        await ctx.send(game.queues[mode].add_player(player, game))
        if game.queues[mode].is_finished():
            await ctx.send(game.add_game_to_be_played(game.queues[mode]))

    else:
        await ctx.send("Make sure you register before joining the queue.")


@BOT.command(pass_context=True, aliases=['l'])
@check_category('Modes')
async def leave(ctx):
    """Remove the player from the queue.

    As opposite to the !join, the leave will remove the player from the
    queue if he was in.
    Can't be used outside Modes category.
    The user needs to be in the queue for using this command.
    The user can't leave a queue after it went full."""
    game = GAMES[BOT.get_guild(int(GUILD)).id]
    mode = int(ctx.channel.name[0])
    name = '_'.join(ctx.author.name.split())

    if name in game.leaderboards[mode]:
        await ctx.send(game.queues[mode].
                       remove_player(game.leaderboards[mode]
                                     [name]))
    else:
        await ctx.send("You didn't even register lol.")


@BOT.command(aliases=['r', 'reg'])
@check_channel('register')
@check_category('Elo by Anddy')
@is_arg_in_modes(GAMES)
async def register(ctx, *args):
    """Register the player to the elo leaderboard from the mode in arg.

    Example: !r N
    This command will register the user into the game mode set in argument.
    The game mode needs to be the N in NvsN, and it needs to already exist.
    This command can be used only in the register channel.
    The command will fail if the mode doesn't exist (use !modes to check)."""

    game = GAMES[BOT.get_guild(int(GUILD)).id]
    mode = int(args[0])
    name = '_'.join(ctx.author.name.split())
    if name in game.leaderboards[mode]:
        await ctx.send(f"There's already a played called {name}.")
        return
    game.leaderboards[mode][name] = Player(name)
    await ctx.send(f"{name} has been registered.")


@BOT.command(aliases=['quit'])
@check_category('Elo by Anddy')
@check_channel('bye')
async def quit_elo(ctx):
    """Delete the user from the registered players.

    The user will lose all of his data after the command.
    Can be used only in Bye channel.
    Can't be undone."""
    game = GAMES[BOT.get_guild(int(GUILD)).id]
    name = '_'.join(ctx.author.name.split())

    for g_queue in game.queues:
        g_queue.remove_player(name)
    for ld_board in game.leaderboards:
        ld_board.pop(name, None)

    await ctx.send(f'{name} has been removed from the rankings')


@BOT.command()
@has_permissions(kick_members=True)
@check_category('Elo by Anddy')
@check_channel('bye')
async def force_quit(ctx, *args):
    """Delete the seized user from the registered players.

    Example: !force_quit "Anddy"
    The command is the same than quit_elo except that the user has to make
    someone else quit the Elo.
    This can be used only in Bye channel.
    Can't be undone."""
    if args == ():
        await ctx.send("Missing the name of the player you want to remove")
        return
    game = GAMES[BOT.get_guild(int(GUILD)).id]

    for g_queue in game.queues:
        g_queue.remove_player(args[0])
    for ld_board in game.leaderboards:
        ld_board.pop(args[0], None)
    await ctx.send(f'{args[0]} has been removed from the rankings')


@BOT.command(aliases=['lb'])
@is_arg_in_modes(GAMES)
@check_category('Elo by Anddy')
@check_channel('info_chat')
async def leaderboard(ctx, *args):
    """Show current leaderboard: !lb [mode] [stats key].

    Example: !lb 1 wins
    Will show the leaderboard of the mode 1vs1 based on the wins.
    [mode] can be any mode in !modes.
    [stats key] can be any stat in !info. e.g:
    name, elo, wins, losses, nb_matches, wlr
    most_wins_in_a_row, most_losses_in_a_row.
    By default, if the stats key is missing, the bot will show the elo lb.
    """
    game = GAMES[BOT.get_guild(int(GUILD)).id]
    if len(args) != 2:
        args = (args[0], "elo")
    await ctx.send(game.leaderboard(int(args[0]), args[1]))


@BOT.command(aliases=['q'])
@check_category('Modes')
async def queue(ctx):
    """Show the current queue.

    When using it on a channel in Modes category, the user will see the
    current queue with everyone's Elo.
    Can't be used outside Modes category.
    """
    game = GAMES[BOT.get_guild(int(GUILD)).id]
    mode = int(ctx.channel.name[0])
    await ctx.send(game.queues[int(mode)])


@BOT.command(aliases=['stats'])
@check_category('Elo by Anddy')
@check_channel('info_chat')
@is_arg_in_modes(GAMES)
async def info(ctx, *args):
    """Show the info of a player. !info [mode], !info [mode] [player]

    Example: !info 1 Anddy
    With no argument, the !info will show the user's stats.
    With a player_name as argument, if the player exists, this will show
    is stats in the seized mode.
    Can be used only in info_chat channel.
    """
    game = GAMES[BOT.get_guild(int(GUILD)).id]
    mode = int(args[0])
    name = args[1] if len(args) == 2 else ctx.author.name
    name = '_'.join(name.split())

    if name in game.leaderboards[mode]:
        await ctx.send(game.leaderboards[mode][name])
    else:
        await ctx.send(f"No player called {name}")


@BOT.command(aliases=['s', 'game'])
@has_permissions(manage_roles=True)
@check_category('Elo by Anddy')
@check_channel('submit')
async def submit(ctx, *args):
    """Expect a format !s [mode] [id_game] [winner].

    Example: !s 1 7 1
    in the mode 1vs1, in the 7th game, the team 1 (red) won.
    This will update the rankings.
    """
    game = GAMES[BOT.get_guild(int(GUILD)).id]

    if args == () or any(arg.isdigit() or int(arg) < 0 for arg in args) or \
            int(args[2]) not in [0, 1] or \
            int(args[1]) not in game.undecided_games or \
            int(args[0]) not in game.available_modes:
        await ctx.send("Error, the format wasn't correct.")


@BOT.command(aliases=['c', 'clear'])
@has_permissions(manage_roles=True)
@check_category('Elo by Anddy')
@check_channel('submit')
@is_arg_in_modes(GAMES)
async def cancel(ctx, *args):
    """Cancel the game given in arg. !c [mode] [game_id]

    Example: !cancel 1 3
    will cancel the game with the id 3 in the mode 1vs1.
    """
    game = GAMES[BOT.get_guild(int(GUILD)).id]
    mode = int(args[0])
    id = int(args[1])
    if game.cancel(mode, id):
        await ctx.send(f"The game {id} has been canceled")
    else:
        await ctx.send(f"Couldn't find the game {id} in the current games.")


@BOT.command()
@has_permissions(manage_roles=True)
@check_category('Elo by Anddy')
@check_channel('init')
async def add_mode(ctx, *args):
    """Add a mode to the game modes.

    Example: !add_mode 4
    Will add the mode 4vs4 into the available modes, a channel will be
    created and the leaderboard will now have a 4 key.
    Can be used only in init channel by a manage_roles having user."""
    if args != () and args[0].isdigit() and int(args[0]) > 0:
        nb_p = int(args[0])
        if GAMES[BOT.get_guild(int(GUILD)).id].add_mode(nb_p):
            guild = ctx.message.guild
            category = discord.utils.get(guild.categories, name="Modes")
            await guild.create_text_channel(f'{nb_p}vs{nb_p}',
                                            category=category)
            await ctx.send("The game mode has been added.")
            return

    await ctx.send("Couldn't add the game mode.")


@BOT.command()
@has_permissions(manage_roles=True)
@check_category('Elo by Anddy')
@check_channel('init')
@is_arg_in_modes(GAMES)
async def delete_mode(ctx, *args):
    mode = int(args[0])
    GAMES[BOT.get_guild(int(GUILD)).id].remove_mode(mode)
    await ctx.send("The mode has been deleted, please delete the channel.")


@BOT.command()
@check_category('Elo by Anddy')
@check_channel('info_chat')
async def modes(ctx):
    """Print available modes."""
    await ctx.send(GAMES[BOT.get_guild(int(GUILD)).id].available_modes)


@submit.error
@add_mode.error
async def role_perm_error(ctx, error):
    """Force to have manage_roles to submit the score."""
    if isinstance(error, MissingPermissions):
        await ctx.send("You must have manage_roles permission to run that.")


@join.error
@register.error
@leaderboard.error
@queue.error
@info.error
# @submit.error
@add_mode.error
@modes.error
async def wrong_mode_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send("You used this command with either a wrong channel or \
a wrong argument.")
    else:
        print(error)


@force_quit.error
async def force_quit_error(error, ctx):
    """Missing permissions."""
    if isinstance(error, MissingPermissions):
        await ctx.send("Missing permissions to remove him snif.")

BOT.run(TOKEN)
