import logging

from os import remove as osremove, walk, path as ospath, rename as osrename
from time import time, sleep
from pyrogram.errors import FloodWait, RPCError
from pyrogram.enums import ParseMode
from PIL import Image
from threading import RLock

from bot import app, DOWNLOAD_DIR, AS_DOCUMENT, AS_DOC_USERS, AS_MEDIA_USERS, CUSTOM_FILENAME, client_app
from bot.helper.ext_utils.fs_utils import take_ss, get_media_info, get_video_resolution, get_path_size
from bot.helper.ext_utils.bot_utils import get_readable_file_size

LOGGER = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

VIDEO_SUFFIXES = ('3GP', 'ASF', 'AVI', 'DIVX', 'DV', 'DAT', 'FLV', 'GXF', 'M2P', 'M2TS', 'M2V', 'M4V', 'MKV', 'MOOV', 'MOV', 'MP4', 'MPEG', 'MPEG1', 'MPEG2', 'MPEG4', 'MPG', 'MPV', 'MT2S', 'TS', 'MTS', 'MXF', 'OGM', 'OGV', 'PS', 'QT', 'RM', 'RMVB', 'VOB', 'WEBM', 'WM', 'WMV')
AUDIO_SUFFIXES = ("MP3", "M4A", "M4B", "FLAC", "WAV", "AIF", "OGG", "AAC", "DTS", "MID", "AMR", "MKA")
IMAGE_SUFFIXES = ("JPG", "JPX", "PNG", "WEBP", "CR2", "TIF", "BMP", "JXR", "PSD", "ICO", "HEIC", "JPEG")


def change_name(fname):
    splited_name, ext = ospath.splitext(fname)
    splited_name = splited_name.replace(' ', '.').replace('-', '.').replace(',', '').replace('[', '.').replace(']', '.').replace('..', '.')
    corrected = []
    for n in splited_name.split('.')[1:]:
        if len('.'.join(corrected) + '.' + n) > 64 - (len(ext)+1):
            break
        corrected.append(n)
    
    return '.'.join(corrected) + ext


class TgUploader:

    def __init__(self, name=None, listener=None):
        self.name = name
        self.uploaded_bytes = 0
        self._last_uploaded = 0
        self.__listener = listener
        self.uid = listener.uid
        self.__start_time = time()
        self.__is_cancelled = False
        self.__as_doc = AS_DOCUMENT
        self.__thumb = f"Thumbnails/{listener.message.from_user.id}.jpg"
        self.__sent_msg = app.get_messages(self.__listener.message.chat.id, self.__listener.uid)
        self.__msgs_dict = {}
        self.__corrupted = 0
        self.__resource_lock = RLock()
        self.__user_settings()

    def upload(self):
        path = f"{DOWNLOAD_DIR}{self.__listener.uid}"
        size = get_readable_file_size(get_path_size(path))
        for dirpath, subdir, files in sorted(walk(path)):
            for file_ in sorted(files):
                if self.__is_cancelled:
                    return
                if file_.endswith('.torrent'):
                    continue
                up_path = ospath.join(dirpath, file_)
                fsize = ospath.getsize(up_path)
                if fsize == 0:
                    LOGGER.error(f"{up_path} size is zero, telegram don't upload zero size files")
                    self.__corrupted += 1
                    continue
                self.__upload_file(up_path, file_, dirpath)
                if self.__is_cancelled:
                    return
                if file_.upper().endswith(VIDEO_SUFFIXES):
                    self.__msgs_dict[file_] = self.__sent_msg.id
                self._last_uploaded = 0
                sleep(1)
        if len(self.__msgs_dict) <= self.__corrupted:
            return self.__listener.onUploadError('Files Corrupted. Check logs')
        LOGGER.info(f"Leech Completed: {self.name}")
        self.__listener.onUploadComplete(None, size, self.__msgs_dict, None, self.__corrupted, self.name)

    def __upload_file(self, up_path, file_, dirpath):
        org_file_ = file_
        if CUSTOM_FILENAME is not None:
            cap_mono = f"{CUSTOM_FILENAME} <code>{file_}</code>"
            file_ = f"{CUSTOM_FILENAME}.{file_}"
            if len(file_) > 64:
                file_ = change_name(file_)
            new_path = ospath.join(dirpath, file_)
            osrename(up_path, new_path)
            up_path = new_path
        else:
            cap_mono = f"<code>{file_}</code>"
        notMedia = False
        thumb = self.__thumb
        try:
            if not self.__as_doc:
                duration = 0
                if file_.upper().endswith(VIDEO_SUFFIXES):
                    duration = get_media_info(up_path)[0]
                    if thumb is None:
                        thumb = take_ss(up_path)
                        if self.__is_cancelled:
                            if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
                                osremove(thumb)
                            return
                    if thumb is not None:
                        img = Image.open(thumb)
                        width, height = img.size
                    else:
                        width, height = get_video_resolution(up_path)
                    if not file_.upper().endswith(("MKV", "MP4")):
                        file_ = ospath.splitext(file_)[0] + '.mp4'
                        file_ = file_.replace('_', '.').replace(' ', '.')
                        new_path = ospath.join(dirpath, file_)
                        osrename(up_path, new_path)
                        up_path = new_path
                    fsize = ospath.getsize(up_path)
                    if fsize >= 2000 * 1024 * 1024:
                        older_msg = self.__sent_msg
                        self.__sent_msg = client_app.send_video(
                            chat_id=-1001674924703,
                            video=up_path,
                            # quote=True,
                            caption=cap_mono,
                            parse_mode=ParseMode.HTML,
                            duration=duration,
                            width=width,
                            height=height,
                            thumb=thumb,
                            supports_streaming=True,
                            disable_notification=True,
                            progress=self.__upload_progress
                        )
                        self.__listener.bot.send_message(chat_id=older_msg.chat.id,
                            reply_to_message_id=older_msg.id,
                            text='File sent to the channel\n\n<a href="https://t.me/c/1674924703/{}">link</a>'.format(self.__sent_msg.id),
                            allow_sending_without_reply=True,
                            parse_mode='HTMl', disable_web_page_preview=True
                            # reply_markup=reply_markup
                            )
                    else:
                        self.__sent_msg = self.__sent_msg.reply_video(video=up_path,
                                                                    quote=True,
                                                                    caption=cap_mono,
                                                                    parse_mode=ParseMode.HTML,
                                                                    duration=duration,
                                                                    width=width,
                                                                    height=height,
                                                                    thumb=thumb,
                                                                    supports_streaming=True,
                                                                    disable_notification=True,
                                                                    progress=self.__upload_progress)
                        self.__listener.bot.copy_message(chat_id=-1001674924703,
                            from_chat_id=self.__sent_msg.chat.id,
                            message_id=self.__sent_msg.id
                            # reply_markup=reply_markup
                            )
                elif file_.upper().endswith(AUDIO_SUFFIXES):
                    duration , artist, title = get_media_info(up_path)
                    self.__sent_msg = self.__sent_msg.reply_audio(audio=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              parse_mode=ParseMode.HTML,
                                                              duration=duration,
                                                              performer=artist,
                                                              title=title,
                                                              thumb=thumb,
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
                elif file_.upper().endswith(IMAGE_SUFFIXES):
                    self.__sent_msg = self.__sent_msg.reply_photo(photo=up_path,
                                                              quote=True,
                                                              caption=cap_mono,
                                                              parse_mode=ParseMode.HTML,
                                                              disable_notification=True,
                                                              progress=self.__upload_progress)
                else:
                    notMedia = False
            LOGGER.info(f'Sending as Doc [{org_file_}]')
            if self.__as_doc or notMedia or file_.upper().endswith('ZIP'):
                LOGGER.info(f'Uploading doc [{org_file_}]')
                if file_.upper().endswith(VIDEO_SUFFIXES) and thumb is None:
                    thumb = take_ss(up_path)
                    if self.__is_cancelled:
                        if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
                            osremove(thumb)
                self.__sent_msg = self.__sent_msg.reply_document(document=up_path,
                                                             quote=True,
                                                             thumb=thumb,
                                                             caption=cap_mono,
                                                             parse_mode=ParseMode.HTML,
                                                             disable_notification=True,
                                                             progress=self.__upload_progress)
        except FloodWait as f:
            LOGGER.warning(str(f))
            sleep(f.x)
        except RPCError as e:
            LOGGER.error(f"RPCError: {e} File: {up_path}")
            self.__corrupted += 1
        except Exception as err:
            LOGGER.error(f"{err} File: {up_path}")
            self.__corrupted += 1
        if self.__thumb is None and thumb is not None and ospath.lexists(thumb):
            osremove(thumb)
        if not self.__is_cancelled:
            osremove(up_path)

    def __upload_progress(self, current, total):
        if self.__is_cancelled:
            app.stop_transmission()
            return
        with self.__resource_lock:
            chunk_size = current - self._last_uploaded
            self._last_uploaded = current
            self.uploaded_bytes += chunk_size

    def __user_settings(self):
        if self.__listener.message.from_user.id in AS_DOC_USERS:
            self.__as_doc = True
        elif self.__listener.message.from_user.id in AS_MEDIA_USERS:
            self.__as_doc = False
        if not ospath.lexists(self.__thumb):
            self.__thumb = None

    @property
    def speed(self):
        with self.__resource_lock:
            try:
                return self.uploaded_bytes / (time() - self.__start_time)
            except ZeroDivisionError:
                return 0

    def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self.name}")
        self.__listener.onUploadError('your upload has been stopped!')

    def send_message(self, text):
        app.send_message(chat_id='GemAIOBot', text=text)
