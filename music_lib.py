import sqlite3, discord, os, sys,\
    youtube_dl, asyncio, requests
from discord import FFmpegPCMAudio
from bs4 import BeautifulSoup 

blue = 0x006bff
red = 0xec1717
default_stream = "( ͡° ͜ʖ ͡°)"
user_agent = {"Accept-Language": "en-US,en;q=0.5"}

# constant variables to access elements in tuples in list
TITLE = 0
LINK = 1
FILE = 2
TIME = 2
VIEWS = 3


class Discord_Player:

    info_container = []  # structure ["title", "link", "file"]
    anti_duplicates = set()  # init. set for lookup (faster), = {} would be dict
    displayedSongs = 5  # amount of displayed songs when offering songs to user
    volume = 0.3
    autoplay = False
    loop = False
    # characters which are getting replaced by microsoft windows, cuz you cant use them for your file
    restricted_characters = ["/", ":", "*", "?", '"', "<", ">", "|", "\\", "'"]
    leave = False  # if owner made the bot leave
    # used when offering songs to user
    number_emotes = [
        ":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:",
        ":one::zero:", ":one::one:", ":one::two:", ":one::three:", ":one::four:", ":one::five:"
    ]
    voice_client = None
    playlist_queue = []
    invisible_bool = False # invisible status
    requests = requests.Session()
    direct = 1 

    def __init__(self, db, bot):
        self.connection = sqlite3.connect(db)
        self.cursor = self.connection.cursor()
        self.bot = bot

    async def is_playing(self):
        if self.playing:
            return 1
        return 0

    async def playlist_play(self, message): 
        info = self.cursor.execute("SELECT title, link from {}".format(
            f"a{message.author.id}"))
        for row in info:
            self.playlist_queue.append(row)
        await self.retrieve_and_download(self.playlist_queue[0][1])
        del self.playlist_queue[0]

    async def playlist_add(self, message, args):
        try:
            title, link = await self.retrieve_data(self.message, " ".join(arg for arg in args[1:]), True)
            self.cursor.execute("INSERT INTO {}(title, link) VALUES (?, ?)".format(
                f"a{self.message.author.id}"), (title, link))
        except IndexError:
            await self.channel.send(embed=discord.Embed(title="Error", description="I need a link", color=red))
        self.connection.commit()
        await self.channel.send(embed=discord.Embed(title="Successfully added", color=blue))

    async def playlist_show(self, message):
        info = self.cursor.execute("SELECT title, link from {}".format(message.author.id))
        stringContainer = []
        for i, e in enumerate(info):
            stringContainer.append(f"{i+1}: [{e[0]}]({e[1]})")
        if len(stringContainer) != 0:
            await message.channel.send(embed=discord.Embed(title="Your playlist", description="\n".join(stringContainer), color=blue))
        await message.channel.send(embed=discord.Embed(title="Your playlist is empty", color=red))

    async def playlist_delete(self, message, args): 
        try:
            self.cursor.execute("DELETE from {} where id = (?)".format(
                f"a{self.message.author.id}"), (args[1],))
        except IndexError:
            await self.channel.send(embed=discord.Embed(title="Error", description="I need a number to delete the song", color=red))
        else:
            self.connection.commit()
            self.cursor.execute(
                "UPDATE {} SET id = id-1 WHERE id > (?)".format(f"a{self.message.author.id}"), (args[1],))
            await self.channel.send(embed=discord.Embed(title="Song successfully deleted", color=blue))

    async def playlist_move(self, message, args):
        try:
            min_ = min([int(args[1]), int(args[2])])
            rows = list(self.cursor.execute("SELECT title, link FROM {} WHERE id>=?".format(f"a{message.author.id}"), (min_,)))
            if args[1] < args[2]:
                rows.insert(int(args[2])-min_+1, rows[0])
                del rows[0]
            else:
                rows.insert(0, rows[int(args[1])-min_])
                del rows[int(args[1])-min_+1]

            def my_generator():
                for e in rows:
                    yield e

            self.cursor.execute("DELETE FROM {} WHERE id>=?".format(f"a{self.message.author.id}"), (min_,))
            self.cursor.executemany("INSERT INTO {}(title, link) VALUES(?, ?)".format(f"a{self.message.author.id}"), my_generator())
            self.connection.commit()
        except:
            await self.channel.send(embed=discord.Embed(title="Error while moving", color=red))
        else:
            await self.channel.send(embed=discord.Embed(title="Successfully moved", color=blue))

    async def playlist_clear(self, message):
        try:
            self.cursor.execute("DROP TABLE {}".format(f"a{self.message.author.id}"))
        except:
            await self.channel.send(embed=discord.Embed(title="Error while clearing", color=red))
        else:
            await self.channel.send(embed=discord.Embed(title="Successfully cleared", color=blue))

    async def removeMusic(self, message, content):
        if 0 < content < len(self.info_container):
            await message.channel.send(embed=discord.Embed(title="Removed", description=f"[{self.info_container[content][TITLE]}]({self.info_container[content][LINK]})", color=blue))
            del self.info_container[content]
        else:
            await message.channel.send(embed=discord.Embed(title="You can't remove that.", color=red))

    async def changeDisplayedSongs(self, message, content):
        if int(content) > 15:
            await message.channel.send(embed=discord.Embed(title="Maximum amount is 15", color=red))
        else:
            self.displayedSongs = int(content)
            await message.channel.send(embed=discord.Embed(title=f"Amount of displayed songs changed to: {self.displayedSongs}", color=blue))

    async def showQueue(self, message):
        queueContainer = f"Currently playing: [{self.info_container[0][TITLE]}]({self.info_container[0][LINK]})\n\n"
        for index in range(1, len(self.info_container)):
            queueContainer += f"{index}: [{self.info_container[index][TITLE]}]({self.info_container[index][LINK]})\n"
        await message.channel.send(embed=discord.Embed(title="Queue", description=queueContainer, color=blue))

    async def loopMusic(self, message):
        if self.loop:
            await message.channel.send(embed=discord.Embed(title="Loop is already enabled", color=red))
        else:
            self.loop = True
            if self.autoplay:
                self.autoplay = False
                await message.channel.send(embed=discord.Embed(title="Loop enabled", description="Autoplay has been disabled so Loop can work properly.", color=blue))
            else:
                await message.channel.send(embed=discord.Embed(title="Loop enabled", color=blue))

    async def stopLoopMusic(self, message):
        if self.loop:
            self.loop = False
            await message.channel.send(embed=discord.Embed(title="Loop disabled", color=blue))
        else:
            await message.channel.send(embed=discord.Embed(title="Loop is already disabled", color=red))

    async def stopMusic(self, message, restart_bool):
        try:
            if self.voice_client.is_playing():
                self.voice_client.stop()
                await self.voice_client.disconnect()
            self.autoplay = False
            self.loop = False
            del self.info_container[:]
            self.anti_duplicates.clear()
            for song in os.listdir():
                if song.endswith(".m4a"):
                    os.remove(f"{sys.path[0]}\\{song}")
            if not self.invisible_bool:
                await self.bot.change_presence(activity=discord.Streaming(name=default_stream, url=f"https://twitch.tv/{default_stream}"))
        except AttributeError:
            # if restart gets called ignore this exception
            if not restart_bool:
                await message.channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

    async def pauseMusic(self, message):
        try:
            if self.voice_client.is_playing():
                self.voice_client.pause()
                await message.channel.send(embed=discord.Embed(title="Music paused", color=blue))
            else:
                await message.channel.send(embed=discord.Embed(title="Music is not playing", color=red))
        except AttributeError:
            await message.channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

    async def resumeMusic(self, message):
        try:
            if self.voice_client.is_paused():
                self.voice_client.resume()
            else:
                await message.channel.send(embed=discord.Embed(title="Music was not paused.", color=red))
        except AttributeError:
            await message.channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

    async def skipMusic(self, message):
        try:
            self.voice_client.stop()
        except AttributeError:
            await message.channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

    async def autoplay_music(self, message):

        if self.autoplay:
            await message.channel.send(embed=discord.Embed(title="Auto play is already enabled", color=red))
        else:
            self.autoplay = True
            if self.loop:
                self.loop = False
                await message.channel.send(embed=discord.Embed(title="Autoplay enabled", description="Loop has been disabled so Autoplay can work properly.", color=blue))
            else:
                await message.channel.send(embed=discord.Embed(title="Autoplay enabled", color=blue))

    async def stopAutoplay_music(self, message):
        if self.autoplay:
            self.autoplay = False
            await message.channel.send(embed=discord.Embed(title="Autoplay disabled", color=blue))
        else:
            await message.channel.send(embed=discord.Embed(title="Autoplay is already disabled", color=red))

    async def volumeMusic(self, message, volume):
        self.volume = float(volume) / 100
        # if voice_client was not connected yet
        try:
            if self.voice_client.is_connected():
                self.voice_client.source.volume = self.volume
        except AttributeError:
            pass

        await message.channel.send(embed=discord.Embed(title=f"Changed volume to: {volume}", color=blue))

    async def currentVolume(self, message):
        await message.channel.send(embed=discord.Embed(title=f"Current volume is: {self.volume*100}", color=blue))

    async def scrape_videos(self, channel, page_source):
            elements = page_source.findAll("div", attrs={
                "class": "yt-lockup yt-lockup-tile yt-lockup-video vve-check clearfix"})
            # no search result
            if len(elements) == 0:
                await channel.send(embed=discord.Embed(title="That does not exist", color=red))
                return -1

            music_list = []

            range_ = self.displayedSongs
            if self.direct: 
                range_ = 1

            for index in range(range_):
                temp_title = music_list.append([elements[index].find("a", attrs={
                    "class": "yt-uix-tile-link yt-ui-ellipsis yt-ui-ellipsis-2 yt-uix-sessionlink spf-link"})["title"]])
                temp_href = music_list[index].append(
                    f"https://www.youtube.com{elements[index].find('a', attrs={'class': 'yt-uix-tile-link yt-ui-ellipsis yt-ui-ellipsis-2 yt-uix-sessionlink spf-link'})['href']}")
                # livestreams dont have time
                try:
                    temp_length = music_list[index].append(
                        elements[index].find("span", attrs={"class": "video-time"}).text)
                except AttributeError:
                    temp_length = music_list[index].append("LIVE")
                    pass

                temp_view = ""
                for element in elements[index].findAll("li"):
                    if "views" in element.text:
                        temp_view = music_list[index].append(
                            f"{element.text.split(' ')[0]} Views")
                        break
                    elif "watching" in element.text:
                        temp_view = music_list[index].append(
                            f"{element.text.split(' ')[0]} Viewers")
                        break

                if temp_view == "":
                    temp_view = music_list[index].append("")

                music_list[index].append(
                    (temp_title, temp_href, temp_length, temp_view))
            
            return music_list

    async def offer_music(self, channel, music_list):
        # offer user some music
        if not self.direct:
            l = []
            for index in range(len(music_list)):
                l.append(
                    f"{self.number_emotes[index]}: [{music_list[index][TITLE]}]({music_list[index][LINK]}) ({music_list[index][TIME]}) {music_list[index][VIEWS]}\n")
            await channel.send(embed=discord.Embed(title="Pick a song", description=f"{''.join(l)}\n:regional_indicator_c: : Cancel", color=blue))

            # let user choose music
            while True:
                msg = await self.bot.wait_for("message")
                # ignore bot messages
                if msg.author.id == self.bot.user.id:
                    continue

                try:
                    if msg.content.lower() == "c":
                        await channel.send(embed=discord.Embed(title="Canceled", color=blue))
                        return -1
                    elif int(msg.content) > 0 and int(msg.content) <= self.displayedSongs:
                        break
                    else:
                        raise Exception
                except:
                    await channel.send(embed=discord.Embed(title="Did you pick a song from the list? Retry.", color=red))

            # -1 to get correct list index
            chosenMusic = int(msg.content)-1
        else:
            chosenMusic = 0

        # save music
        title = music_list[chosenMusic][TITLE]
        link = music_list[chosenMusic][LINK]

        return title, link

    async def retrieve_data(self, message, args, playlist_add=0):

        if ("youtube." in args):
            page_source = BeautifulSoup(self.requests.get(
                args, headers=user_agent).text, "html.parser")
            title = page_source.find("title").text
            link = args

        else:
            page_source = BeautifulSoup(self.requests.get(
                f"https://www.youtube.com/results?search_query={args.replace(' ', '+')}", headers=user_agent).text, "html.parser")
            scraped = await self.scrape_videos(message.channel, page_source)
            title, link = await self.offer_music(message.channel, scraped)

        # method got called by playlist add
        if playlist_add:
            return title, link

        self.info_container.append(
            (title.replace(' - YouTube', ''), link, f"{''.join(character.replace(character, ' ') if character in self.restricted_characters else character for character in title)}.m4a"))

        try:
            await self.downloadMusic(message, True)
        except youtube_dl.utils.DownloadError:
            await message.channel.send(embed=discord.Embed(title="This video is unavailable", color=red))

    async def downloadMusic(self, message, user_input):

        ytdl_arguments = {
            "format": "m4a",
            "outtmpl": self.info_container[-1][FILE],
            "quiet": False  # log output
        }

        with youtube_dl.YoutubeDL(ytdl_arguments) as ytdl:
            ytdl.download([self.info_container[-1][LINK]])

        # user_input tells if this method call was made from the user or autoplay
        if user_input and len(self.info_container) > 1:
            await message.channel.send(embed=discord.Embed(title="Added", description=f"[{self.info_container[-1][TITLE]}]({self.info_container[-1][LINK]})", color=blue))

        await self.play_music(message)

    async def play_music(self, message):
        try:
            self.voice_client = await message.author.voice.channel.connect(reconnect=True)
        except discord.errors.ClientException as e:
            if e == "Already connected to a voice channel.":
                pass
        except AttributeError:
            pass
        
        try:
            self.voice_client.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                f"{sys.path[0]}\\{self.info_container[0][FILE]}"), self.volume))
        except discord.errors.ClientException as e: 
            if e == "Already playing audio.":
                pass
        else:
            await message.channel.send(embed=discord.Embed(title="Now Playing", description=f"[{self.info_container[0][TITLE]}]({self.info_container[0][LINK]})", color=blue)
                                        # get video id from url and use that to get thumbnail in mqdefault
                                        .set_image(url=f"https://img.youtube.com/vi/{self.info_container[0][LINK].split('=', 1)[1]}/mqdefault.jpg"))
            if not self.invisible_bool:
                await self.bot.change_presence(activity=discord.Streaming(name=self.info_container[0][TITLE], url=f"https://twitch.tv/{default_stream}"))

        # check every second if song is still playing or paused
        while self.voice_client.is_playing() or self.voice_client.is_paused():
            # playlist function, keeps adding new music from playlist_queue while playing a song
            if len(self.playlist_queue) > 0:
                await self.retrieve_data(message, self.playlist_queue[0][1])
            await asyncio.sleep(1)

        if self.voice_client.is_connected():
            
            # autoplay last song only
            if self.autoplay and len(self.info_container) == 1:

                page_source = BeautifulSoup(self.requests.get(
                    self.info_container[0][LINK], headers=user_agent).text, "html.parser")
                elements = page_source.findAll(
                    "a", class_="content-link spf-link yt-uix-sessionlink spf-link")

                for element in elements:
                    title = element["title"]
                    if (title not in self.anti_duplicates):
                        self.info_container.append((title, f"https://www.youtube.com{element['href']}",
                                                    f"{''.join(character.replace(character, ' ') if character in self.restricted_characters else character for character in title)}.m4a"))
                        self.anti_duplicates.add(title)
                        del self.info_container[0]
                        await self.downloadMusic(message, False)
                        return
            
            if not self.loop:
                # bot stopped, everything was reset/deleted
                try:
                    os.remove(
                        f"{sys.path[0]}\\{self.info_container[0][FILE]}")
                except IndexError as e:
                    print(e)
                
                del self.info_container[0]
                
            if len(self.info_container) == 0:
                await message.channel.send(embed=discord.Embed(title="Queue is empty", color=red))
                if not self.invisible_bool:
                    await self.bot.change_presence(activity=discord.Streaming(name=default_stream, url=f"https://twitch.tv/{default_stream}"))
            else:
                await self.play_music(message)

        # bot disconnects
        else:
            # last check if there is still music, bot sometimes randomly disconnects (timeout?)
            if not self.leave:
                self.voice_client = await self.author.voice.channel.connect(reconnect=True)
                await self.play_music(message)