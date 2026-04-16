import os
from datetime import date

APP_ID = "WindowsFixer"
APP_VERSION = "v1.1.0"
BUILD_DATE = os.environ.get("BUILD_DATE", date.today().isoformat())

DONATE_PAGE = "https://buymeacoffee.com/ilukezippo"
GITHUB_PAGE_ORIGINAL = "https://github.com/ilukezippo/Windows_Fixer"
GITHUB_PAGE_FORK = "https://github.com/khalidelmerrah/Windows_Fixer"
GITHUB_API_LATEST = "https://api.github.com/repos/khalidelmerrah/Windows_Fixer/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/khalidelmerrah/Windows_Fixer/releases"

WIN_W = 1280
WIN_H = 980
