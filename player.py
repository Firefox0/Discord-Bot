
import sqlite3
import discord 
import os 
import sys
import youtube_dl
import asyncio
import requests 
import lyricsgenius
import datetime
from discord import FFmpegPCMAudio
from bs4 import BeautifulSoup
import subprocess
import json
from youtube_api import YoutubeDataApi

blue = 0x006bff
red = 0xec1717
default_stream = "( ͡° ͜ʖ ͡°)"
user_agent = {"Accept-Language": "en-US,en;q=0.5"}

TITLE = 0
LINK = 1
FILE = 2
TIME = 2
VIEWS = 3

size = 2048

class DiscordPlayer:

    info_container = [] 
    anti_duplicates = set()
    displayed_songs = 5
    volume = 0.3
    autoplay = 0
    loop = 0
    restricted_characters = ["/", ":", "*", "?", '"', "<", ">", "|", "\\", "'"]
    playing = 0
    number_emotes = [":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:",
                    ":one::zero:", ":one::one:", ":one::two:", ":one::three:", ":one::four:", ":one::five:"]
    voice_client = None
    playlist_queue = []
    invisible = 0
    requests = requests.Session()
    history = []
    ytdl = youtube_dl.YoutubeDL()
    ytdl_arguments = {
            "format": "m4a",
            "quiet": 0
    }

    def __init__(self, bot, db=None, genius_token=None, youtube_token=None):
        self.bot = bot
        if db:
            self.connection = sqlite3.connect(db)
            self.cursor = self.connection.cursor()
        if genius_token:
            self.Genius = lyricsgenius.Genius(genius_token)
        if youtube_token:
            self.yt = YoutubeDataApi(youtube_token)
            
    async def cleanup(self, channel, main_file=0):
        if self.playing: 
            await self.stop_music(channel, True)
        if self.connection:
            self.connection.close()
        if main_file:
            os.startfile(main_file)
        await self.bot.logout()

    async def is_playing(self):
        return self.playing

    async def get_history(self, channel):
        history = "\n".join(self.history)
        if history:
            await channel.send(embed=discord.Embed(title=f"History", description=history, color=blue))
        else:
            await channel.send(embed=discord.Embed(title=f"History is empty", color=red))
        return history

    async def clear_history(self, channel):
        del self.history[:]
        await channel.send(embed=discord.Embed(title=f"Successfully cleared history", color=blue))

    async def get_lyrics(self, channel, song=0):
        if not song:
            song = self.info_container[0][TITLE]
        formatted_song = " ".join(e.capitalize() for e in song.split())

        try:
            song_ = self.Genius.search_song(formatted_song)
        except:
            await channel.send(embed=discord.Embed(title="Error. Is the token valid?", color=red))
            return 0
        try:
            lyrics = song_.lyrics
        except AttributeError:
            await channel.send(embed=discord.Embed(title="No lyrics available", color=red)) 
            return 0

        length = len(lyrics)
        if length > 2048:
            formatted_lyrics = [lyrics[i:i+size]
                                for i in range(0, length, size)]
            formatted_lyrics_len = len(formatted_lyrics)
            for i in range(formatted_lyrics_len):
                await channel.send(embed=discord.Embed(
                    title=f"{formatted_song} ({i+1}/{formatted_lyrics_len})", description=formatted_lyrics[i], color=blue))
        else:
            await channel.send(embed=discord.Embed(title=formatted_song, description=lyrics, color=blue))
        return lyrics

    async def playlist_init(self, id):
        try:
            cursor.execute(
                f"CREATE TABLE a{id} (id INTEGER PRIMARY KEY, title TEXT, link TEXT)")
        except:
            pass

    async def playlist_play(self, msg):
        info = self.cursor.execute(f"SELECT title, link FROM a{msg.author.id}")
        for row in info:
            self.playlist_queue.append(row)
        tmp_song = self.playlist_queue[0][1]
        del self.playlist_queue[0]
        await self.retrieve_data(msg, tmp_song)
        await self.download_music(msg)
        await self.play_music(msg)

    async def playlist_add(self, msg, args, direct=1):
        try:
            title, link = await self.retrieve_data(msg, args, direct, 1)
            self.cursor.execute(f"INSERT INTO a{msg.author.id} (title, link) VALUES (?, ?)", (title, link))
        except IndexError as e:
            print(e)
            await msg.channel.send(embed=discord.Embed(title="Error", description="I need a link", color=red))
        else:
            self.connection.commit()
            await msg.channel.send(embed=discord.Embed(title="Successfully added", color=blue))

    async def playlist_show(self, msg):
        info = self.cursor.execute(f"SELECT title, link FROM a{msg.author.id}")
        stringContainer = []
        for i, e in enumerate(info):
            stringContainer.append(f"{i+1}: [{e[0]}]({e[1]})")
        if len(stringContainer) != 0:
            await msg.channel.send(embed=discord.Embed(title="Your playlist", description="\n".join(stringContainer), color=blue))
        else:
            await msg.channel.send(embed=discord.Embed(title="Your playlist is empty", color=red))

    async def playlist_delete(self, msg, arg):
        try:
            self.cursor.execute(f"DELETE FROM a{msg.author.id} WHERE id = ?", arg)
        except IndexError:
            await msg.channel.send(embed=discord.Embed(
                title="Error", description="I need a number to delete the song", color=red))
        else:
            self.cursor.execute(
                f"UPDATE a{msg.author.id} SET id = id-1 WHERE id > ?", arg)
            self.connection.commit()
            await msg.channel.send(embed=discord.Embed(title="Song successfully deleted", color=blue))

    async def playlist_move(self, msg, args):
        arg1 = int(args[0])
        arg2 = int(args[1])
        try:
            min_ = min(arg1, arg2)
            rows = list(self.cursor.execute(f"SELECT title, link FROM a{msg.author.id} WHERE id >=?", str(min_)))
            if arg1 < arg2:
                rows.insert(arg2-arg1+1, rows[0])
                del rows[0]
            else:
                rows.insert(0, rows[arg1-arg2])
                del rows[arg1-arg2+1]

            def my_generator():
                for e in rows:
                    yield e
            self.cursor.execute(f"DELETE FROM a{msg.author.id} WHERE id>=?", str(min_))
            self.cursor.executemany(f"INSERT INTO a{msg.author.id}(title, link) VALUES(?, ?)", my_generator())
            self.connection.commit()
        except Exception as e:
            print(e)
            await msg.channel.send(embed=discord.Embed(title="Error while moving", color=red))
        else:
            await msg.channel.send(embed=discord.Embed(title="Successfully moved", color=blue))

    async def playlist_clear(self, msg):
        try:
            self.cursor.execute(
                f"DROP TABLE a{msg.author.id}")
        except:
            await msg.channel.send(embed=discord.Embed(title="Error while clearing", color=red))
        else:
            self.connection.commit()
            await msg.channel.send(embed=discord.Embed(title="Successfully cleared", color=blue))

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

    async def stop_music(self, channel, restart):
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
                    try:
                        os.remove(f"{sys.path[0]}\\{song}")
                    except PermissionError as e:
                        print(e)
                        break
            if not restart and not self.invisible:
                await self.bot.change_presence(activity=discord.Streaming(name=default_stream, url=f"https://twitch.tv/{default_stream}"))
        except AttributeError:
            if not restart:
                await channel.send(embed=discord.Embed(title="I'm not connected to a voice channel", color=red))

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

    async def retrieve_data(self, msg, args, direct=1, playlist_add=0):
        try:
            if ("youtube." in args):
                stdout = subprocess.check_output(["youtube-dl", args, "-j"])
            else:
                stdout = subprocess.check_output(["youtube-dl", f'ytsearch:"{args}"', "-j"])
        except subprocess.CalledProcessError:
            await msg.channel.send(embed=discord.Embed(title=f"Couldn't find {args}", color=red))
            return 0
        infos = json.loads(stdout)
        title = infos["title"]
        link = f"https://www.youtube.com/watch?v={infos['id']}"
        if playlist_add:
            return title, link
        self.info_container.append(
            (title.replace(' - YouTube', ''), link, f"{''.join(character.replace(character, ' ') if character in self.restricted_characters else character for character in title)}.m4a"))
        return 1

    async def download_music(self, msg, output=True):
        self.ytdl_arguments["outtmpl"] = self.info_container[-1][FILE]
        try:
            with youtube_dl.YoutubeDL(self.ytdl_arguments) as ytdl:
                ytdl.download([self.info_container[-1][LINK]])
        except youtube_dl.utils.DownloadError as e:
            await msg.channel.send(embed=discord.Embed(title="Download failed. Youtube probably did some changes. Shutting down.", color=red))
            await self.cleanup(msg.channel)
            return -1
        if output:
            # appending to queue
            if len(self.info_container) > 1:
                await msg.channel.send(embed=discord.Embed(title="Added", description=f"[{self.info_container[-1][TITLE]}]({self.info_container[-1][LINK]})", color=blue))
        self.anti_duplicates.add(self.info_container[-1][TITLE])
        return 1

    async def delete_current_song(self):
        try:
            os.remove(
                f"{sys.path[0]}\\{self.info_container[0][FILE]}")
        except IndexError as e:
            return 0
        else:
            del self.info_container[0]
            return 1

    async def connect_bot(self, msg):
        try:
            self.voice_client = await msg.author.voice.channel.connect(reconnect=1)
        except discord.errors.ClientException as e:
            if e == "Already connected to a voice channel.":
                return 1
        except AttributeError:
            await msg.channel.send(embed=discord.Embed(title="Can't connect to voice channel", color=red))
            return 0
        else:
            return 1

    async def get_next_recommended(self, msg):
        """ download the next recommended video """
        elements = self.yt.get_recommended_videos(self.info_container[0][LINK].split("?v=")[1], max_results=20)
        break_ = 0
        for element in elements:
            if break_:
                break
            title = element["video_title"]
            if title not in self.anti_duplicates:
                self.info_container.append((title, f"https://www.youtube.com/watch?v={element['video_id']}",
                                            f"{''.join(character.replace(character, ' ') if character in self.restricted_characters else character for character in title)}.m4a"))
                self.anti_duplicates.add(title)
                await self.download_music(msg, False)
                break_ = 1

    async def prepare_playlist_song(self, msg):
        """ download the first song in playlist """
        if self.playlist_queue:
            tmp_song = self.playlist_queue[0][1]
            del self.playlist_queue[0]
            await self.retrieve_data(msg, tmp_song)
            await self.download_music(msg, False)

    async def start_player(self): 
        """ attempt to start player, true if or already started """
        try:
            self.voice_client.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
                f"{sys.path[0]}\\{self.info_container[0][FILE]}"), self.volume))
        except discord.errors.ClientException as e:
            if e == "Already playing audio.":
                return 1
        except AttributeError as e:
            print(e)
            return 0
        else:
            return 1

    async def play_music(self, msg):
        if not self.voice_client:
            if not await self.connect_bot(msg):
                return
        if not await self.start_player():
            return
        self.playing = 1
        title = self.info_container[0][TITLE]
        link = self.info_container[0][LINK]
        date = datetime.datetime.now()
        self.history.append(
            f"{date.hour:02}:{date.minute:02}:{date.second:02} {'-'} [{title}]({link})")
        if not self.invisible:
            await self.bot.change_presence(activity=discord.Streaming(name=self.info_container[0][TITLE], url=f"https://twitch.tv/{default_stream}"))
        await msg.channel.send(embed=discord.Embed(title="Now Playing", description=f"[{title}]({link})", color=blue)
                                .set_image(url=f"https://img.youtube.com/vi/{self.info_container[0][LINK].split('=', 1)[1]}/mqdefault.jpg"))
        while self.voice_client.is_playing() or self.voice_client.is_paused():
            await self.prepare_playlist_song(msg)
            await asyncio.sleep(1)
        if self.voice_client.is_connected():
            if self.autoplay and len(self.info_container) == 1:
                await self.get_next_recommended(msg)
            if not self.loop:
                await self.delete_current_song()
            if len(self.info_container) == 0:
                await msg.channel.send(embed=discord.Embed(title="Queue is empty", color=red))
                if not self.invisible:
                    await self.bot.change_presence(activity=discord.Streaming(name=default_stream, url=f"https://twitch.tv/{default_stream}"))
            else:
                await self.play_music(msg)
        self.playing = 0