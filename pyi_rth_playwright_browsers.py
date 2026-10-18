import os
import sys

local_app_data = os.environ.get("LOCALAPPDATA", "")
ms_playwright = os.path.join(local_app_data, "ms-playwright") if local_app_data else ""
if ms_playwright and os.path.exists(ms_playwright):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_playwright
