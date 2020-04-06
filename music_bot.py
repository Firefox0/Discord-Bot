import discord, asyncio, requests, sqlite3,\
        os, sys
from bs4 import BeautifulSoup
from discord.ext import commands
from discord.voice_client import VoiceClient
from discord.utils import get
from music_lib import Discord_Player

bot = commands.Bot(command_prefix=">")

class Client(discord.Client):

    @bot.event
    async def on_ready():
        print("Logged in.\n\nLogs: ")
        await bot.change_presence(activity=discord.Streaming(name=default_stream, url=f"https://twitch.tv/{default_stream}"))

    @bot.command()
    async def play(self, *args):
        Player.leave = False
        await Player.retrieve_data(self.message, " ".join(arg for arg in args))

    @bot.command()
    async def remove(self, content):
        try:
            await Player.removeMusic(self.message, int(content))
        except:
            await self.message.channel.send(embed=discord.Embed(title="You can't remove that", color=red))

    @bot.command()
    async def pause(self):
        await Player.pauseMusic(self.message)

    @bot.command()
    async def resume(self):
        await Player.resumeMusic(self.message)

    @bot.command()
    async def stop(self):
        Player.leave = True
        await Player.stopMusic(self.message, False)

    @bot.command()
    async def skip(self):
        await Player.skipMusic(self.message)

    @bot.command()
    async def loop(self):
        await Player.loopMusic(self.message)

    @bot.command()
    async def stoploop(self):
        await Player.stopLoopMusic(self.message)

    @bot.command()
    async def queue(self):
        await Player.showQueue(self.message)

    @bot.command()
    async def display(self, content):
        await Player.changeDisplayedSongs(self.message, content)

    @bot.command()
    async def volume(self, volume):
        await Player.volumeMusic(self.message, volume)

    @bot.command()
    async def currentvolume(self):
        await Player.currentVolume(self.message)

    @bot.command()
    async def autoplay(self):
        await Player.autoplay_music(self.message)

    @bot.command()
    async def stopautoplay(self):
        await Player.stopAutoplay_music(self.message)

    @bot.command()
    async def q(self):
        if self.message.author.id == owner_id:
            connection.close()
            await bot.logout()

    @bot.command()
    async def r(self):
        if self.message.author.id == owner_id:
            await Player.stopMusic(self.message, True)
            connection.close()
            os.startfile(__file__)
            await bot.logout()
            
    @bot.command()
    # table cant start with a number
    async def playlist(self, *args):
        try:
            cursor.execute("CREATE TABLE {} (id INTEGER PRIMARY KEY, title TEXT, link TEXT)".format(
                f"a{self.message.author.id}"))
        except:
            pass

    @bot.command()
    async def playlistplay(self):
        await Player.playlist_play(self.message)

    @bot.command()
    async def playlistadd(self, arg):
        await Player.playlist_add(self.message, arg)
    
    @bot.command()
    async def playlistshow(self):
        await Player.playlist_show(self.message)

    @bot.command()
    async def playlistdelete(self, arg):
        await Player.playlist_delete(self.message, arg)

    @bot.command()
    async def playlistmove(self, arg):
        await Player.playlist_move(self.message, arg)

    @bot.command()
    async def playlistclear(self):
        await Player.playlist_clear(self.message)

if __name__ == "__main__":

    print("Loading...")

    # set token and prefix so the bot can run
    try:
        f = open("TOKEN.txt", "r")
    except IOError:
        with open("TOKEN.txt", "a", encoding="utf-8") as f:
            f.write(input("Looks like you are running this for the first time.\nEnter your token: ") +
                    "\n" + input("Choose a prefix: "))
        os.startfile(__file__)
        sys.exit()
    else:
        TOKEN = f.readline().strip()
        prefix = f.readline().strip()
        f.close()

    # sqlite 3
    connection = sqlite3.connect("playlists.db")
    cursor = connection.cursor()

    default_stream = "( ͡° ͜ʖ ͡°)"

    owner_id = 609337374480269352

    user_agent = {"Accept-Language": "en-US,en;q=0.5"}

    # creating instances
    Player = Discord_Player("playlists.db", bot)

    print("Logging in...")

    bot.run(TOKEN)