import logging
import socket
import faulthandler

from telegram.ext import Updater as tgUpdater
from qbittorrentapi import Client as qbClient
from aria2p import API as ariaAPI, Client as ariaClient
from os import remove as osremove, path as ospath, environ
from requests import get as rget
from json import loads as jsnloads
from subprocess import Popen, run as srun, check_output
from time import sleep, time
from threading import Thread, Lock
from pyrogram import Client
from dotenv import load_dotenv
import random

class FileHandler:
    def __init__(self, fname, verbose=True):
        self.fname = fname
        self.verbose = verbose
        open(self.fname, 'a').close()

    @property
    def list(self):
        with open(self.fname, 'r') as f:
            lines = [x.strip('\n') for x in f.readlines()]
            return [x for x in lines if x]

    @property
    def set(self):
        return set(self.list)

    def __iter__(self):
        for i in self.list:
            yield next(iter(i))

    def __len__(self):
        return len(self.list)

    def append(self, item, allow_duplicates=False):
        if self.verbose:
            msg = "Adding '{}' to `{}`.".format(item, self.fname)
            # print(msg)

        if not allow_duplicates and str(item) in self.list:
            msg = "'{}' already in `{}`.".format(item, self.fname)
            # print(msg)
            return

        with open(self.fname, 'a') as f:
            f.write('{item}\n'.format(item=item))

    def remove(self, x):
        x = str(x)
        items = self.list
        if x in items:
            items.remove(x)
            msg = "Removing '{}' from `{}`.".format(x, self.fname)
            # print(msg)
            self.save_list(items)

    def random(self):
        return random.choice(self.list)

    def save_list(self, items):
        with open(self.fname, 'w') as f:
            for item in items:
                f.write('{item}\n'.format(item=item))

faulthandler.enable()

socket.setdefaulttimeout(600)

botStartTime = time()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
                    level=logging.INFO)

LOGGER = logging.getLogger(__name__)

load_dotenv('config.env', override=True)

def getConfig(name: str):
    return environ[name]

try:
    NETRC_URL = getConfig('NETRC_URL')
    if len(NETRC_URL) == 0:
        raise KeyError
    try:
        res = rget(NETRC_URL)
        if res.status_code == 200:
            with open('.netrc', 'wb+') as f:
                f.write(res.content)
        else:
            logging.error(f"Failed to download .netrc {res.status_code}")
    except Exception as e:
        logging.error(f"NETRC_URL: {e}")
except KeyError:
    pass
try:
    SERVER_PORT = getConfig('SERVER_PORT')
    if len(SERVER_PORT) == 0:
        raise KeyError
except KeyError:
    SERVER_PORT = 80

LOGGER.info('Initializing the processes')
PORT = environ.get('PORT', SERVER_PORT)
web = Popen([f"gunicorn web.wserver:app --bind 0.0.0.0:{PORT}"], shell=True)
alive = Popen(["python3", "alive.py"])
srun(["qbittorrent-nox", "-d", "--profile=."])
if not ospath.exists('.netrc'):
    srun(["touch", ".netrc"])
srun(["cp", ".netrc", "/root/.netrc"])
srun(["chmod", "600", ".netrc"])
srun(["chmod", "+x", "aria.sh"])
a2c = Popen(["./aria.sh"], shell=True)
LOGGER.info('Initializing finished... Going to sleep for 1 sec')
sleep(1)


Interval = []
DRIVES_NAMES = []
DRIVES_IDS = []
INDEX_URLS = []

try:
    if bool(getConfig('_____REMOVE_THIS_LINE_____')):
        logging.error('The README.md file there to be read! Exiting now!')
        exit()
except KeyError:
    pass

aria2 = ariaAPI(
    ariaClient(
        host="http://localhost",
        port=6800,
        secret="",
    )
)

def get_client():
    return qbClient(host="localhost", port=8090)

trackers = check_output(["curl -Ns https://raw.githubusercontent.com/XIU2/TrackersListCollection/master/all.txt https://ngosang.github.io/trackerslist/trackers_all_http.txt https://newtrackon.com/api/all | awk '$0'"], shell=True).decode('utf-8')
trackerslist = set(trackers.split("\n"))
trackerslist.remove("")
trackerslist = "\n\n".join(trackerslist)
# get_client().application.set_preferences({"add_trackers": f"{trackerslist}"})

DOWNLOAD_DIR = None
BOT_TOKEN = None

download_dict_lock = Lock()
status_reply_dict_lock = Lock()
# Key: update.effective_chat.id
# Value: telegram.Message
status_reply_dict = {}
# Key: update.message.message_id
# Value: An object of Status
download_dict = {}
# key: rss_title
# value: [rss_feed, last_link, last_title, filter]
rss_dict = {}

AUTHORIZED_CHATS = set()
SUDO_USERS = set()
AS_DOC_USERS = set()
AS_MEDIA_USERS = set()
if ospath.exists('authorized_chats.txt'):
    with open('authorized_chats.txt', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            AUTHORIZED_CHATS.add(int(line.split()[0]))
if ospath.exists('sudo_users.txt'):
    with open('sudo_users.txt', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            SUDO_USERS.add(int(line.split()[0]))
try:
    achats = getConfig('AUTHORIZED_CHATS')
    achats = achats.split(" ")
    for chats in achats:
        AUTHORIZED_CHATS.add(int(chats))
except:
    pass
try:
    schats = getConfig('SUDO_USERS')
    schats = schats.split(" ")
    for chats in schats:
        SUDO_USERS.add(int(chats))
except:
    pass
try:
    BOT_TOKEN = getConfig('BOT_TOKEN')
    parent_id = getConfig('GDRIVE_FOLDER_ID')
    DOWNLOAD_DIR = getConfig('DOWNLOAD_DIR')
    if not DOWNLOAD_DIR.endswith("/"):
        DOWNLOAD_DIR = DOWNLOAD_DIR + '/'
    DOWNLOAD_STATUS_UPDATE_INTERVAL = int(getConfig('DOWNLOAD_STATUS_UPDATE_INTERVAL'))
    OWNER_ID = int(getConfig('OWNER_ID'))
    AUTO_DELETE_MESSAGE_DURATION = int(getConfig('AUTO_DELETE_MESSAGE_DURATION'))
    TELEGRAM_API = getConfig('TELEGRAM_API')
    TELEGRAM_HASH = getConfig('TELEGRAM_HASH')
except KeyError as e:
    LOGGER.error("One or more env variables missing! Exiting now")
    exit(1)

LOGGER.info("Generating BOT_STRING_SESSION")
app = Client('pyrogram', api_id=int(TELEGRAM_API), api_hash=TELEGRAM_HASH, bot_token=BOT_TOKEN, no_updates=True)
client_app = Client('pyrogram_client', api_id=int(TELEGRAM_API), api_hash=TELEGRAM_HASH, phone_number='+6282155017625')
try:
    USER_STRING_SESSION = getConfig('USER_STRING_SESSION')
    if len(USER_STRING_SESSION) == 0:
        raise KeyError
except KeyError:
    USER_STRING_SESSION = None

if USER_STRING_SESSION is not None:
    rss_session = Client(USER_STRING_SESSION, api_id=int(TELEGRAM_API), api_hash=TELEGRAM_HASH)
else:
    rss_session = None

def aria2c_init():
    try:
        logging.info("Initializing Aria2c")
        link = "https://releases.ubuntu.com/21.10/ubuntu-21.10-desktop-amd64.iso.torrent"
        dire = DOWNLOAD_DIR.rstrip("/")
        aria2.add_uris([link], {'dir': dire})
        sleep(3)
        downloads = aria2.get_downloads()
        sleep(10)
        for download in downloads:
            aria2.remove([download], force=True, files=True)
            # download_dict['']
    except Exception as e:
        logging.error(f"Aria2c initializing error: {e}")
        pass

if not ospath.isfile(".restartmsg"):
    sleep(1)
    Thread(target=aria2c_init).start()
    sleep(1.5)

try:
    DB_URI = getConfig('DATABASE_URL')
    if len(DB_URI) == 0:
        raise KeyError
except KeyError:
    DB_URI = None
try:
    TG_SPLIT_SIZE = getConfig('TG_SPLIT_SIZE')
    # 2097151000
    if len(TG_SPLIT_SIZE) == 0 or int(TG_SPLIT_SIZE) > 4000 * 1024 * 1024:
        raise KeyError
    else:
        TG_SPLIT_SIZE = int(TG_SPLIT_SIZE)
except KeyError:
    TG_SPLIT_SIZE = 4000 * 1024 * 1024
try:
    STATUS_LIMIT = getConfig('STATUS_LIMIT')
    if len(STATUS_LIMIT) == 0:
        raise KeyError
    else:
        STATUS_LIMIT = int(STATUS_LIMIT)
except KeyError:
    STATUS_LIMIT = None
try:
    MEGA_API_KEY = getConfig('MEGA_API_KEY')
    if len(MEGA_API_KEY) == 0:
        raise KeyError
except KeyError:
    logging.warning('MEGA API KEY not provided!')
    MEGA_API_KEY = None
try:
    MEGA_EMAIL_ID = getConfig('MEGA_EMAIL_ID')
    MEGA_PASSWORD = getConfig('MEGA_PASSWORD')
    if len(MEGA_EMAIL_ID) == 0 or len(MEGA_PASSWORD) == 0:
        raise KeyError
except KeyError:
    logging.warning('MEGA Credentials not provided!')
    MEGA_EMAIL_ID = None
    MEGA_PASSWORD = None
try:
    UPTOBOX_TOKEN = getConfig('UPTOBOX_TOKEN')
    if len(UPTOBOX_TOKEN) == 0:
        raise KeyError
except KeyError:
    UPTOBOX_TOKEN = None
try:
    INDEX_URL = getConfig('INDEX_URL').rstrip("/")
    if len(INDEX_URL) == 0:
        raise KeyError
    else:
        INDEX_URLS.append(INDEX_URL)
except KeyError:
    INDEX_URL = None
    INDEX_URLS.append(None)
try:
    SEARCH_API_LINK = getConfig('SEARCH_API_LINK').rstrip("/")
    if len(SEARCH_API_LINK) == 0:
        raise KeyError
except KeyError:
    SEARCH_API_LINK = None
try:
    SEARCH_LIMIT = getConfig('SEARCH_LIMIT')
    if len(SEARCH_LIMIT) == 0:
        raise KeyError
    else:
        SEARCH_LIMIT = int(SEARCH_LIMIT)
except KeyError:
    SEARCH_LIMIT = 0
try:
    RSS_COMMAND = getConfig('RSS_COMMAND')
    if len(RSS_COMMAND) == 0:
        raise KeyError
except KeyError:
    RSS_COMMAND = None
try:
    CMD_INDEX = getConfig('CMD_INDEX')
    if len(CMD_INDEX) == 0:
        raise KeyError
except KeyError:
    CMD_INDEX = ''
try:
    TORRENT_DIRECT_LIMIT = getConfig('TORRENT_DIRECT_LIMIT')
    if len(TORRENT_DIRECT_LIMIT) == 0:
        raise KeyError
    else:
        from bot.helper.ext_utils.db_handler import DbManger
        TORRENT_DIRECT_LIMIT = float(TORRENT_DIRECT_LIMIT)
        try:
            if DbManger().get_setting('TORRENT_DIRECT_LIMIT'):
                DbManger().setting_update(name='TORRENT_DIRECT_LIMIT', value=TORRENT_DIRECT_LIMIT)
            else:
                DbManger().setting_add(name='TORRENT_DIRECT_LIMIT', value=TORRENT_DIRECT_LIMIT)
        except Exception as e:
            LOGGER.error(f"Adding seting TORRENT_DIRECT_LIMIT [{e}]")
except KeyError:
    TORRENT_DIRECT_LIMIT = None
try:
    CLONE_LIMIT = getConfig('CLONE_LIMIT')
    if len(CLONE_LIMIT) == 0:
        raise KeyError
    else:
        CLONE_LIMIT = float(CLONE_LIMIT)
except KeyError:
    CLONE_LIMIT = None
try:
    MEGA_LIMIT = getConfig('MEGA_LIMIT')
    if len(MEGA_LIMIT) == 0:
        raise KeyError
    else:
        MEGA_LIMIT = float(MEGA_LIMIT)
except KeyError:
    MEGA_LIMIT = None
try:
    STORAGE_THRESHOLD = getConfig('STORAGE_THRESHOLD')
    if len(STORAGE_THRESHOLD) == 0:
        raise KeyError
    else:
        STORAGE_THRESHOLD = float(STORAGE_THRESHOLD)
except KeyError:
    STORAGE_THRESHOLD = None
try:
    ZIP_UNZIP_LIMIT = getConfig('ZIP_UNZIP_LIMIT')
    if len(ZIP_UNZIP_LIMIT) == 0:
        raise KeyError
    else:
        ZIP_UNZIP_LIMIT = float(ZIP_UNZIP_LIMIT)
except KeyError:
    ZIP_UNZIP_LIMIT = None
try:
    RSS_CHAT_ID = getConfig('RSS_CHAT_ID')
    if len(RSS_CHAT_ID) == 0:
        raise KeyError
    else:
        RSS_CHAT_ID = int(RSS_CHAT_ID)
except KeyError:
    RSS_CHAT_ID = None
try:
    RSS_DELAY = getConfig('RSS_DELAY')
    if len(RSS_DELAY) == 0:
        raise KeyError
    else:
        RSS_DELAY = int(RSS_DELAY)
except KeyError:
    RSS_DELAY = 900
try:
    QB_TIMEOUT = getConfig('QB_TIMEOUT')
    if len(QB_TIMEOUT) == 0:
        raise KeyError
    else:
        QB_TIMEOUT = int(QB_TIMEOUT)
except KeyError:
    QB_TIMEOUT = None
try:
    BUTTON_FOUR_NAME = getConfig('BUTTON_FOUR_NAME')
    BUTTON_FOUR_URL = getConfig('BUTTON_FOUR_URL')
    if len(BUTTON_FOUR_NAME) == 0 or len(BUTTON_FOUR_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_FOUR_NAME = None
    BUTTON_FOUR_URL = None
try:
    BUTTON_FIVE_NAME = getConfig('BUTTON_FIVE_NAME')
    BUTTON_FIVE_URL = getConfig('BUTTON_FIVE_URL')
    if len(BUTTON_FIVE_NAME) == 0 or len(BUTTON_FIVE_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_FIVE_NAME = None
    BUTTON_FIVE_URL = None
try:
    BUTTON_SIX_NAME = getConfig('BUTTON_SIX_NAME')
    BUTTON_SIX_URL = getConfig('BUTTON_SIX_URL')
    if len(BUTTON_SIX_NAME) == 0 or len(BUTTON_SIX_URL) == 0:
        raise KeyError
except KeyError:
    BUTTON_SIX_NAME = None
    BUTTON_SIX_URL = None
try:
    STOP_DUPLICATE = getConfig('STOP_DUPLICATE')
    STOP_DUPLICATE = STOP_DUPLICATE.lower() == 'true'
except KeyError:
    STOP_DUPLICATE = False
try:
    VIEW_LINK = getConfig('VIEW_LINK')
    VIEW_LINK = VIEW_LINK.lower() == 'true'
except KeyError:
    VIEW_LINK = False
try:
    IS_TEAM_DRIVE = getConfig('IS_TEAM_DRIVE')
    IS_TEAM_DRIVE = IS_TEAM_DRIVE.lower() == 'true'
except KeyError:
    IS_TEAM_DRIVE = False
try:
    USE_SERVICE_ACCOUNTS = getConfig('USE_SERVICE_ACCOUNTS')
    USE_SERVICE_ACCOUNTS = USE_SERVICE_ACCOUNTS.lower() == 'true'
except KeyError:
    USE_SERVICE_ACCOUNTS = False
try:
    BLOCK_MEGA_FOLDER = getConfig('BLOCK_MEGA_FOLDER')
    BLOCK_MEGA_FOLDER = BLOCK_MEGA_FOLDER.lower() == 'true'
except KeyError:
    BLOCK_MEGA_FOLDER = False
try:
    BLOCK_MEGA_LINKS = getConfig('BLOCK_MEGA_LINKS')
    BLOCK_MEGA_LINKS = BLOCK_MEGA_LINKS.lower() == 'true'
except KeyError:
    BLOCK_MEGA_LINKS = False
try:
    WEB_PINCODE = getConfig('WEB_PINCODE')
    WEB_PINCODE = WEB_PINCODE.lower() == 'true'
except KeyError:
    WEB_PINCODE = False
try:
    SHORTENER = getConfig('SHORTENER')
    SHORTENER_API = getConfig('SHORTENER_API')
    if len(SHORTENER) == 0 or len(SHORTENER_API) == 0:
        raise KeyError
except KeyError:
    SHORTENER = None
    SHORTENER_API = None
try:
    IGNORE_PENDING_REQUESTS = getConfig("IGNORE_PENDING_REQUESTS")
    IGNORE_PENDING_REQUESTS = IGNORE_PENDING_REQUESTS.lower() == 'true'
except KeyError:
    IGNORE_PENDING_REQUESTS = False
try:
    BASE_URL = getConfig('BASE_URL_OF_BOT').rstrip("/")
    if len(BASE_URL) == 0:
        raise KeyError
except KeyError:
    logging.warning('BASE_URL_OF_BOT not provided!')
    BASE_URL = None
try:
    AS_DOCUMENT = getConfig('AS_DOCUMENT')
    AS_DOCUMENT = AS_DOCUMENT.lower() == 'true'
except KeyError:
    AS_DOCUMENT = False
try:
    EQUAL_SPLITS = getConfig('EQUAL_SPLITS')
    EQUAL_SPLITS = EQUAL_SPLITS.lower() == 'true'
except KeyError:
    EQUAL_SPLITS = False
try:
    QB_SEED = getConfig('QB_SEED')
    QB_SEED = QB_SEED.lower() == 'true'
except KeyError:
    QB_SEED = False
try:
    CUSTOM_FILENAME = getConfig('CUSTOM_FILENAME')
    if len(CUSTOM_FILENAME) == 0:
        raise KeyError
except KeyError:
    CUSTOM_FILENAME = None
try:
    CRYPT = getConfig('CRYPT')
    if len(CRYPT) == 0:
        raise KeyError
except KeyError:
    CRYPT = None
try:
    TOKEN_PICKLE_URL = getConfig('TOKEN_PICKLE_URL')
    if len(TOKEN_PICKLE_URL) == 0:
        raise KeyError
    try:
        res = rget(TOKEN_PICKLE_URL)
        if res.status_code == 200:
            with open('token.pickle', 'wb+') as f:
                f.write(res.content)
        else:
            logging.error(f"Failed to download token.pickle, link got HTTP response: {res.status_code}")
    except Exception as e:
        logging.error(f"TOKEN_PICKLE_URL: {e}")
except KeyError:
    pass
try:
    ACCOUNTS_ZIP_URL = getConfig('ACCOUNTS_ZIP_URL')
    if len(ACCOUNTS_ZIP_URL) == 0:
        raise KeyError
    else:
        try:
            res = rget(ACCOUNTS_ZIP_URL)
            if res.status_code == 200:
                with open('accounts.zip', 'wb+') as f:
                    f.write(res.content)
            else:
                logging.error(f"Failed to download accounts.zip, link got HTTP response: {res.status_code}")
        except Exception as e:
            logging.error(f"ACCOUNTS_ZIP_URL: {e}")
            raise KeyError
        srun(["unzip", "-q", "-o", "accounts.zip"])
        srun(["chmod", "-R", "777", "accounts"])
        osremove("accounts.zip")
except KeyError:
    pass
try:
    MULTI_SEARCH_URL = getConfig('MULTI_SEARCH_URL')
    if len(MULTI_SEARCH_URL) == 0:
        raise KeyError
    try:
        res = rget(MULTI_SEARCH_URL)
        if res.status_code == 200:
            with open('drive_folder', 'wb+') as f:
                f.write(res.content)
        else:
            logging.error(f"Failed to download drive_folder, link got HTTP response: {res.status_code}")
    except Exception as e:
        logging.error(f"MULTI_SEARCH_URL: {e}")
except KeyError:
    pass
try:
    YT_COOKIES_URL = getConfig('YT_COOKIES_URL')
    if len(YT_COOKIES_URL) == 0:
        raise KeyError
    try:
        res = rget(YT_COOKIES_URL)
        if res.status_code == 200:
            with open('cookies.txt', 'wb+') as f:
                f.write(res.content)
        else:
            logging.error(f"Failed to download cookies.txt, link got HTTP response: {res.status_code}")
    except Exception as e:
        logging.error(f"YT_COOKIES_URL: {e}")
except KeyError:
    pass

DRIVES_NAMES.append("Main")
DRIVES_IDS.append(parent_id)
if ospath.exists('drive_folder'):
    with open('drive_folder', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            try:
                temp = line.strip().split()
                DRIVES_IDS.append(temp[1])
                DRIVES_NAMES.append(temp[0].replace("_", " "))
            except:
                pass
            try:
                INDEX_URLS.append(temp[2])
            except IndexError as e:
                INDEX_URLS.append(None)
try:
    SEARCH_PLUGINS = getConfig('SEARCH_PLUGINS')
    if len(SEARCH_PLUGINS) == 0:
        raise KeyError
    SEARCH_PLUGINS = jsnloads(SEARCH_PLUGINS)
except KeyError:
    SEARCH_PLUGINS = None
    
try:
    FINISHED_PROGRESS_STR = getConfig('FINISHED_PROGRESS_STR') 
    UN_FINISHED_PROGRESS_STR = getConfig('UN_FINISHED_PROGRESS_STR')
except:
    FINISHED_PROGRESS_STR = '●' # '■'
    UN_FINISHED_PROGRESS_STR = '○' # '□'

try:
    UPDATE_EVERYTHING_WHEN_RESTART = getConfig('UPDATE_EVERYTHING_WHEN_RESTART').lower() == 'true'
except KeyError:
    UPDATE_EVERYTHING_WHEN_RESTART = True

try:
    VIRUSTOTAL_API = getConfig('VIRUSTOTAL_API')
    if len(VIRUSTOTAL_API) < 4: raise KeyError
except KeyError:
    logging.warning('VIRUSTOTAL_API not provided.')
    VIRUSTOTAL_API = None

try:
    VIRUSTOTAL_FREE = getConfig('VIRUSTOTAL_FREE').lower() == 'true'
except KeyError:
    VIRUSTOTAL_FREE = True

try:
    HEROKU_API_KEY = getConfig('HEROKU_API_KEY')
    HEROKU_APP_NAME = getConfig('HEROKU_APP_NAME')
    if len(HEROKU_API_KEY) == 0 or len(HEROKU_APP_NAME) == 0:
        raise KeyError
except KeyError:
    LOGGER.warning("Heroku details not entered.")
    HEROKU_API_KEY = None
    HEROKU_APP_NAME = None

try:
    SPAMWATCH_ANTISPAM_API = getConfig('SPAMWATCH_ANTISPAM_API')
    if len(SPAMWATCH_ANTISPAM_API) == 0: raise KeyError
    else: logging.info('Using SPAMWATCH_ANTISPAM_API')
except KeyError:
    logging.info('Not using SPAMWATCH_ANTISPAM_API')
    SPAMWATCH_ANTISPAM_API = None

try:
    USERGE_ANTISPAM_API = getConfig('USERGE_ANTISPAM_API')
    if len(USERGE_ANTISPAM_API) == 0: raise KeyError
    else: logging.info('Using USERGE_ANTISPAM_API')
except KeyError:
    logging.info('Not using USERGE_ANTISPAM_API')
    USERGE_ANTISPAM_API = None

try:
    COMBOT_CAS_ANTISPAM = getConfig('COMBOT_CAS_ANTISPAM').lower() == 'true'
    logging.info('Using COMBOT_CAS_ANTISPAM')
except KeyError:
    logging.info('No using COMBOT_CAS_ANTISPAM')
    COMBOT_CAS_ANTISPAM = None

try:
    INTELLIVOID_ANTISPAM = getConfig('INTELLIVOID_ANTISPAM').lower() == 'true'
    logging.info('Using INTELLIVOID_ANTISPAM')
except KeyError:
    logging.info('No using INTELLIVOID_ANTISPAM')
    INTELLIVOID_ANTISPAM = None

updater = tgUpdater(token=BOT_TOKEN, request_kwargs={'read_timeout': 20, 'connect_timeout': 15})
bot = updater.bot
dispatcher = updater.dispatcher
job_queue = updater.job_queue

threshold_limit_links = FileHandler('threshold_limi_links')