import discord, asyncio, requests, sqlite3,\
        os, sys
from bs4 import BeautifulSoup
from discord.ext import commands
from discord.utils import get
from player import DiscordPlayer

bot = commands.Bot(command_prefix=">")

class Client(discord.Client):

    @bot.event
    async def on_ready():
        print("Logged in\n\nLogs: ")
        await bot.change_presence(activity=discord.Streaming(name=default_stream, url=f"https://twitch.tv/{default_stream}"))

    @bot.command()
    async def play(self, *args):
        if not await Player.connect_bot(self.message):
            return
        if await Player.retrieve_data(self.message, " ".join(arg for arg in args)):
            await Player.download_music(self.message)
            await Player.play_music(self.message)
    
    @bot.command()
    async def remove(self, content):
        await Player.remove_music(self.message, int(content))

    @bot.command()
    async def pause(self):
        await Player.pause_music(self.message)

    @bot.command()
    async def resume(self):
        await Player.resume_music(self.message)

    @bot.command()
    async def stop(self):
        Player.leave = True
        await Player.stop_music(self.message, False)

    @bot.command()
    async def skip(self):
        await Player.skip_music(self.message)

    @bot.command()
    async def loop(self):
        await Player.start_loop(self.message)

    @bot.command()
    async def stoploop(self):
        await Player.stop_loop(self.message)

    @bot.command()
    async def queue(self):
        await Player.show_queue(self.message)

    @bot.command()
    async def display(self, content):
        await Player.set_displayed_songs(self.message, content)

    @bot.command()
    async def volume(self, volume):
        await Player.set_volume(self.message, volume)

    @bot.command()
    async def currentvolume(self):
        await Player.current_volume(self.message)

    @bot.command()
    async def autoplay(self):
        await Player.start_autoplay(self.message)

    @bot.command()
    async def stopautoplay(self):
        await Player.stop_autoplay(self.message)

    @bot.command()
    async def q(self):
        await Player.cleanup(self.message.channel)

    @bot.command()
    async def r(self):
        await Player.cleanup(self.message.channel, __file__)
    
    @bot.command()
    async def playlist(self, *args):
        await Player.playlist_init(self.message.author.id)

    @bot.command()
    async def playlistplay(self):
        await Player.playlist_play(self.message)

    @bot.command()
    async def playlistadd(self, *args):
        await Player.playlist_add(self.message, " ".join(args))
    
    @bot.command()
    async def playlistshow(self):
        await Player.playlist_show(self.message)

    @bot.command()
    async def playlistdelete(self, arg):
        await Player.playlist_delete(self.message, arg)

    @bot.command()
    async def playlistmove(self, *args):
        await Player.playlist_move(self.message, args)

    @bot.command()
    async def playlistclear(self):
        await Player.playlist_clear(self.message)

    @bot.command() 
    async def lyrics(self, *args):
        await Player.get_lyrics(self.message.channel, " ".join(args))

    @bot.command()
    async def direct(self, arg):
        await Player.set_direct(self.message.channel, int(arg))
    
    @bot.command()
    async def history(self):
        await Player.get_history(self.message.channel)
    
    @bot.command()
    async def clearhistory(self):
        await Player.clear_history(self.message.channel)

def restart():
    os.startfile(__file__)
    sys.exit()

if __name__ == "__main__":

    print("Loading...")

    try:
        f = open("TOKEN.txt", "r")
    except IOError:
        with open("TOKEN.txt", "w+", encoding="utf-8") as f:
            f.write(input("Looks like you are running this for the first time.\n\nEnter your Discord ID: ") + 
                    input("\nEnter your discord token: ") +
                    input("\nEnter the name of the database you want to create (you can leave this blank): ") + 
                    input("\nEnter a genius token to access song lyrics (you can leave this blank): ") +
                    input("\nEnter a Youtube Data API key (you can leave this blank): "))
        restart()
    else:
        owner_id = f.readline().strip()
        discord_token = f.readline().strip()
        db_name = f.readline().strip()
        genius_token = f.readline().strip()
        youtube_token = f.readline().strip()
        f.close()
    if not owner_id or not discord_token:
        input("Error: Owner ID and/or discord token missing. Retry.")
        os.remove("TOKEN.txt")
        restart()
    if not db_name:
        print("Warning: Couldn't find database, playlists won't be available.")
    if not genius_token: 
        print("Warning: Couldn't find genius token, song lyrics won't be available.")
    if not youtube_token:
        print("Warning: Couldn't find youtube token, autoplay feature won't be supported.")
    default_stream = "( ͡° ͜ʖ ͡°)"
    Player = DiscordPlayer(bot, db_name, genius_token, youtube_token)
    print("Logging in...")
    bot.run(discord_token)