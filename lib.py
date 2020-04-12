import sqlite3, discord, os, sys,\
    youtube_dl, asyncio, requests,\
    lyricsgenius
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

size = 2048 

class Discord_Player:

    info_container = []  # structure ["title", "link", "file"]
    anti_duplicates = set()  # init. set for lookup (faster), = {} would be dict
    displayed_songs = 5
    volume = 0.3
    autoplay = 0
    loop = 0
    restricted_characters = ["/", ":", "*", "?", '"', "<", ">", "|", "\\", "'"]
    playing = 0
    number_emotes = [
        ":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:",
        ":one::zero:", ":one::one:", ":one::two:", ":one::three:", ":one::four:", ":one::five:"
    ]
    voice_client = None
    playlist_queue = []
    invisible = 0
    requests = requests.Session()
    direct = 1 

    def __init__(self, db, bot):
        self.connection = sqlite3.connect(db)
        self.cursor = self.connection.cursor()
        self.bot = bot
        self.Genius = lyricsgenius.Genius("")
    

    async def is_playing(self):
        return self.playing

    async def set_direct(self, channel, value):
        self.direct = value
        if self.direct:
            await channel.send(embed=discord.Embed(title=f"Successfully changed mode to DIRECT MODE", color=blue))
        else:
            await channel.send(embed=discord.Embed(title=f"Successfully changed mode to SEARCH MODE", color=blue))

    async def get_direct(self, channel):
        if self.direct:
            await channel.send(embed=discord.Embed(title=f"Current mode: DIRECT", color=blue))
        else:
            await channel.send(embed=discord.Embed(title=f"Current mode: SEARCH", color=blue))
        return self.direct

    async def get_history(self, channel): 
        history = "\n".join(self.anti_duplicates)
        if history:
            await channel.send(embed=discord.Embed(title=f"History", description=history, color=blue))
        else:
            await channel.send(embed=discord.Embed(title=f"History is empty", color=red))
        return self.anti_duplicates
    
    async def clear_history(self, channel):
        self.anti_duplicates.clear()
        await channel.send(embed=discord.Embed(title=f"Successfully cleared history", color=blue))

    async def get_lyrics(self, channel, song):
        song = " ".join(e.capitalize() for e in song.split())
        try:
            song_ = self.Genius.search_song(song)
        except:
            await channel.send(embed=discord.Embed(title="Error", color=red))
            return 0
        else:
            lyrics = song_.lyrics
            length = len(lyrics)
            if length > 2048:
                formatted_lyrics = (lyrics[i:i+size] for i in range(0, length, size))
                for e in formatted_lyrics:
                    await channel.send(embed=discord.Embed(title=song.capitalize(), description=e, color=blue))
            else:
                await channel.send(embed=discord.Embed(title=song.capitalize(), description=lyrics, color=blue))
            return lyrics

    async def playlist_play(self, msg): 
        info = self.cursor.execute("SELECT title, link from {}".format(
            f"a{msg.author.id}"))
        for row in info:
            self.playlist_queue.append(row)
        await self.retrieve_and_download(self.playlist_queue[0][1])
        del self.playlist_queue[0]

    async def playlist_add(self, msg, args):
        try:
            title, link = await self.retrieve_data(self.msg, " ".join(arg for arg in args[1:]), 1)
            self.cursor.execute("INSERT INTO {}(title, link) VALUES (?, ?)".format(
                f"a{self.msg.author.id}"), (title, link))
        except IndexError:
            await self.channel.send(embed=discord.Embed(title="Error", description="I need a link", color=red))
        self.connection.commit()
        await self.channel.send(embed=discord.Embed(title="Successfully added", color=blue))

    async def playlist_show(self, msg):
        info = self.cursor.execute("SELECT title, link from {}".format(msg.author.id))
        stringContainer = []
        for i, e in enumerate(info):
            stringContainer.append(f"{i+1}: [{e[0]}]({e[1]})")
        if len(stringContainer) != 0:
            await msg.channel.send(embed=discord.Embed(title="Your playlist", description="\n".join(stringContainer), color=blue))
        await msg.channel.send(embed=discord.Embed(title="Your playlist is empty", color=red))

    async def playlist_delete(self, msg, args): 
        try:
            self.cursor.execute("DELETE from {} where id = (?)".format(
                f"a{self.msg.author.id}"), (args[1],))
        except IndexError:
            await self.channel.send(embed=discord.Embed(title="Error", description="I need a number to delete the song", color=red))
        else:
            self.connection.commit()
            self.cursor.execute(
                "UPDATE {} SET id = id-1 WHERE id > (?)".format(f"a{self.msg.author.id}"), (args[1],))
            await self.channel.send(embed=discord.Embed(title="Song successfully deleted", color=blue))

    async def playlist_move(self, msg, args):
        try:
            min_ = min([int(args[1]), int(args[2])])
            rows = list(self.cursor.execute("SELECT title, link FROM {} WHERE id>=?".format(f"a{msg.author.id}"), (min_,)))
            if args[1] < args[2]:
                rows.insert(int(args[2])-min_+1, rows[0])
                del rows[0]
            else:
                rows.insert(0, rows[int(args[1])-min_])
                del rows[int(args[1])-min_+1]

            def my_generator():
                for e in rows:
                    yield e

            self.cursor.execute("DELETE FROM {} WHERE id>=?".format(f"a{self.msg.author.id}"), (min_,))
            self.cursor.executemany("INSERT INTO {}(title, link) VALUES(?, ?)".format(f"a{self.msg.author.id}"), my_generator())
            self.connection.commit()
        except:
            await self.channel.send(embed=discord.Embed(title="Error while moving", color=red))
        else:
            await self.channel.send(embed=discord.Embed(title="Successfully moved", color=blue))

    async def playlist_clear(self, msg):
        try:
            self.cursor.execute("DROP TABLE {}".format(f"a{self.msg.author.id}"))
        except:
            await self.channel.send(embed=discord.Embed(title="Error while clearing", color=red))
        else:
            await self.channel.send(embed=discord.Embed(title="Successfully cleared", color=blue))

    async def remove_music(self, msg, content):
        if 0 < content < len(self.info_container):
            await msg.channel.send(embed=discord.Embed(title="Removed", description=f"[{self.info_container[content][TITLE]}]({self.info_container[content][LINK]})", color=blue))
            del self.info_container[content]
        else:
            await msg.channel.send(embed=discord.Embed(title="You can't remove that.", color=red))

    async def set_displayed_songs(self, msg, content):
        if int(content) > 15:
            await msg.channel.send(embed=discord.Embed(title="Maximum amount is 15", color=red))
        else:
            self.displayed_songs = int(content)
            await msg.channel.send(embed=discord.Embed(title=f"Amount of displayed songs changed to: {self.displayed_songs}", color=blue))

    async def show_queue(self, msg):
        queueContainer = f"Currently playing: [{self.info_container[0][TITLE]}]({self.info_container[0][LINK]})\n\n"
        for index in range(1, len(self.info_container)):
            queueContainer += f"{index}: [{self.info_container[index][TITLE]}]({self.info_container[index][LINK]})\n"
        await msg.channel.send(embed=discord.Embed(title="Queue", description=queueContainer, color=blue))

    async def start_loop(self, msg):
        if self.loop:
            await msg.channel.send(embed=discord.Embed(title="Loop is already enabled", color=red))
        else:
            self.loop = 1
            if self.autoplay:
                self.autoplay = 0
                await msg.channel.send(embed=discord.Embed(title="Loop enabled", description="Autoplay has been disabled so Loop can work properly.", color=blue))
            else:
                await msg.channel.send(embed=discord.Embed(title="Loop enabled", color=blue))

    async def stop_loop(self, msg):
        if self.loop:
            self.loop = 0
            await msg.channel.send(embed=discord.Embed(title="Loop disabled", color=blue))
        else:
            await msg.channel.send(embed=discord.Embed(title="Loop is already disabled", color=red))

    async def stop_music(self, msg, restart):
        try:
            if self.voice_client.is_playing():
                self.voice_client.stop()
                await self.voice_client.disconnect()
            self.autoplay = 0
            self.loop = 0
            del self.info_container[:]
            self.anti_duplicates.clear()
            for song in os.listdir():
                if song.endswith(".m4a"):
                    os.remove(f"{sys.path[0]}\\{song}")
            if not self.invisible:
                await self.bot.change_presence(activity=discord.Streaming(name=default_stream, url=f"https://twitch.tv/{default_stream}"))
        except AttributeError:
            if not restart:
                await msg.channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

    async def pause_music(self, msg):
        try:
            if self.voice_client.is_playing():
                self.voice_client.pause()
                await msg.channel.send(embed=discord.Embed(title="Music paused", color=blue))
            else:
                await msg.channel.send(embed=discord.Embed(title="Music is not playing", color=red))
        except AttributeError:
            await msg.channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

    async def resume_music(self, msg):
        try:
            if self.voice_client.is_paused():
                self.voice_client.resume()
            else:
                await msg.channel.send(embed=discord.Embed(title="Music was not paused.", color=red))
        except AttributeError:
            await msg.channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

    async def skip_music(self, msg):
        try:
            self.voice_client.stop()
        except AttributeError:
            await msg.channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

    async def start_autoplay(self, msg):

        if self.autoplay:
            await msg.channel.send(embed=discord.Embed(title="Auto play is already enabled", color=red))
        else:
            self.autoplay = 1
            if self.loop:
                self.loop = 0
                await msg.channel.send(embed=discord.Embed(title="Autoplay enabled", description="Loop has been disabled so Autoplay can work properly.", color=blue))
            else:
                await msg.channel.send(embed=discord.Embed(title="Autoplay enabled", color=blue))

    async def stop_autoplay(self, msg):
        if self.autoplay:
            self.autoplay = 0
            await msg.channel.send(embed=discord.Embed(title="Autoplay disabled", color=blue))
        else:
            await msg.channel.send(embed=discord.Embed(title="Autoplay is already disabled", color=red))

    async def set_volume(self, msg, volume):
        self.volume = float(volume) / 100

        try:
            if self.voice_client.is_connected():
                self.voice_client.source.volume = self.volume
        except AttributeError:
            pass

        await msg.channel.send(embed=discord.Embed(title=f"Changed volume to: {volume}", color=blue))

    async def current_volume(self, msg):
        await msg.channel.send(embed=discord.Embed(title=f"Current volume is: {self.volume*100}", color=blue))

    async def scrape_videos(self, channel, page_source):
            elements = page_source.findAll("div", attrs={
                "class": "yt-lockup yt-lockup-tile yt-lockup-video vve-check clearfix"})

            # no search result
            if len(elements) == 0:
                await channel.send(embed=discord.Embed(title="That does not exist", color=red))
                return -1

            music_list = []

            range_ = self.displayed_songs
            if self.direct: 
                range_ = 1

            for index in range(range_):
                element = elements[index]

                temp_element = element.find("a", attrs={"class": "yt-uix-tile-link yt-ui-ellipsis yt-ui-ellipsis-2 yt-uix-sessionlink spf-link "})
                temp_title = temp_element["title"]
                temp_href = f"https://www.youtube.com{temp_element['href']}"

                # livestreams dont have time
                try:
                    temp_length = element.find("span", attrs={"class": "style-scope ytd-thumbnail-overlay-time-status-renderer"}).text
                except AttributeError:
                    temp_length = "LIVE"
                    pass

                temp_view = ""
                for element in element.findAll("span", attrs={"class": "style-scope ytd-video-meta-block"}):
                    formatted = element.text.split(' ')[0]
                    text = element.text
                    if "views" in text:
                        temp_view = f"{formatted} Views"
                        break
                    elif "watching" in text:
                        temp_view = f"{formatted} Viewers"
                        break

                music_list.append(
                    (temp_title, temp_href, temp_length, temp_view))

            return music_list

    async def offer_music(self, channel, music_list):
        if not self.direct:
            l = []
            for index in range(len(music_list)):
                l.append(
                    f"{self.number_emotes[index]}: [{music_list[index][TITLE]}]({music_list[index][LINK]}) ({music_list[index][TIME]}) {music_list[index][VIEWS]}\n")
            await channel.send(embed=discord.Embed(title="Pick a song", description=f"{''.join(l)}\n:regional_indicator_c: : Cancel", color=blue))

            while 1:
                msg = await self.bot.wait_for("msg")
                if msg.author.id == self.bot.user.id:
                    continue

                try:
                    if msg.content.lower() == "c":
                        await channel.send(embed=discord.Embed(title="Canceled", color=blue))
                        return -1
                    elif int(msg.content) > 0 and int(msg.content) <= self.displayed_songs:
                        break
                    else:
                        raise Exception
                except:
                    await channel.send(embed=discord.Embed(title="Did you pick a song from the list? Retry.", color=red))

            # -1 to get correct list index
            chosenMusic = int(msg.content)-1
        else:
            chosenMusic = 0

        title = music_list[chosenMusic][TITLE]
        link = music_list[chosenMusic][LINK]

        return title, link

    async def retrieve_data(self, msg, args, playlist_add=0):

        if ("youtube." in args):
            page_source = BeautifulSoup(self.requests.get(
                args, headers=user_agent).text, "html.parser")
            title = page_source.find("title").text
            link = args

        else:
            page_source = BeautifulSoup(self.requests.get(
                f"https://www.youtube.com/results?search_query={args.replace(' ', '+')}", headers=user_agent).text, "html.parser")
            scraped = await self.scrape_videos(msg.channel, page_source)
            title, link = await self.offer_music(msg.channel, scraped)

        if playlist_add:
            return title, link

        self.info_container.append(
            (title.replace(' - YouTube', ''), link, f"{''.join(character.replace(character, ' ') if character in self.restricted_characters else character for character in title)}.m4a"))

        try:
            await self.download_music(msg)
        except youtube_dl.utils.DownloadError:
            await msg.channel.send(embed=discord.Embed(title="This video is unavailable", color=red))

    async def download_music(self, msg):

        ytdl_arguments = {
            "format": "m4a",
            "outtmpl": self.info_container[-1][FILE],
            "quiet": 0
        }

        with youtube_dl.YoutubeDL(ytdl_arguments) as ytdl:
            ytdl.download([self.info_container[-1][LINK]])

        if not self.autoplay and len(self.info_container) > 1:
            await msg.channel.send(embed=discord.Embed(title="Added", description=f"[{self.info_container[-1][TITLE]}]({self.info_container[-1][LINK]})", color=blue))

        await self.play_music(msg)

    async def play_music(self, msg):
        try:
            self.voice_client = await msg.author.voice.channel.connect(reconnect=1)
        except discord.errors.ClientException as e:
            if e == "Already connected to a voice channel.":
                pass
        except AttributeError as e:
            pass
        
        try:
            self.voice_client.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                f"{sys.path[0]}\\{self.info_container[0][FILE]}"), self.volume))
        except discord.errors.ClientException as e: 
            if e == "Already playing audio.":
                return 0 
        else:
            self.playing = 1
            self.anti_duplicates.add(self.info_container[0][TITLE])
            await msg.channel.send(embed=discord.Embed(title="Now Playing", description=f"[{self.info_container[0][TITLE]}]({self.info_container[0][LINK]})", color=blue)
                                        # get video id from url and use that to get thumbnail in mqdefault
                                        .set_image(url=f"https://img.youtube.com/vi/{self.info_container[0][LINK].split('=', 1)[1]}/mqdefault.jpg"))
            if not self.invisible:
                await self.bot.change_presence(activity=discord.Streaming(name=self.info_container[0][TITLE], url=f"https://twitch.tv/{default_stream}"))

        # check every second if song is still playing or paused
        while self.voice_client.is_playing() or self.voice_client.is_paused():
            # playlist function, keeps adding new music from playlist_queue while playing a song
            if len(self.playlist_queue) > 0:
                await self.retrieve_data(msg, self.playlist_queue[0][1])
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
                    if title not in self.anti_duplicates:
                        self.info_container.append((title, f"https://www.youtube.com{element['href']}",
                                                    f"{''.join(character.replace(character, ' ') if character in self.restricted_characters else character for character in title)}.m4a"))
                        del self.info_container[0]
                        await self.download_music(msg)
                        return
            
            if not self.loop:
                try:
                    os.remove(
                        f"{sys.path[0]}\\{self.info_container[0][FILE]}")
                except IndexError as e:
                    print(e)
                
                del self.info_container[0]
                
            if len(self.info_container) == 0:
                await msg.channel.send(embed=discord.Embed(title="Queue is empty", color=red))
                if not self.invisible:
                    await self.bot.change_presence(activity=discord.Streaming(name=default_stream, url=f"https://twitch.tv/{default_stream}"))
            else:
                await self.play_music(msg)

        else:
            if self.playing:
                self.voice_client = await self.author.voice.channel.connect(reconnect=1)
                await self.play_music(msg)
        
        self.playing = 0