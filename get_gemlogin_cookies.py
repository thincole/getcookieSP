import json
import urllib.request
import urllib.error
import subprocess
import re
import time
import csv
import sys
import os
from datetime import datetime

# Reconfigure stdout/stderr to support Unicode (Vietnamese prints) on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


# Import websocket (required for CDP communication)
try:
    import websocket
except ImportError:
    print("Error: 'websocket-client' package is required. Please install it using: pip install websocket-client")
    sys.exit(1)

# API Config
GEMLOGIN_API = "http://127.0.0.1:1010"

def find_gemlogin_executable():
    """Tìm đường dẫn thực thi của Gemlogin trên máy tính"""
    candidates = [
        r'C:\Program Files\Gemlogin\Gemlogin.exe',
        os.path.expandvars(r'%PROGRAMFILES%\Gemlogin\Gemlogin.exe'),
        os.path.expandvars(r'%PROGRAMFILES(X86)%\Gemlogin\Gemlogin.exe'),
        os.path.expandvars(r'%LOCALAPPDATA%\Programs\Gemlogin\Gemlogin.exe'),
        os.path.expandvars(r'%LOCALAPPDATA%\Gemlogin\Gemlogin.exe'),
        r'C:\Gemlogin\Gemlogin.exe',
        r'D:\Gemlogin\Gemlogin.exe',
        r'E:\Gemlogin\Gemlogin.exe',
        r'F:\Gemlogin\Gemlogin.exe',
    ]
    for p in candidates:
        if p and os.path.exists(p) and os.path.isfile(p):
            return p
            
    shortcuts = [
        os.path.expandvars(r'%PUBLIC%\Desktop\Gemlogin.lnk'),
        os.path.expandvars(r'%USERPROFILE%\Desktop\Gemlogin.lnk'),
        os.path.expandvars(r'%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Gemlogin\Gemlogin.lnk'),
    ]
    for sc in shortcuts:
        if os.path.exists(sc):
            return sc
            
    return None

def is_gemlogin_running():
    """Kiểm tra xem tiến trình Gemlogin.exe có đang chạy không"""
    try:
        res = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Gemlogin.exe', '/NH'], capture_output=True, text=True, errors='ignore')
        return 'gemlogin.exe' in res.stdout.lower()
    except Exception:
        return False

def is_gemlogin_api_ready():
    """Kiểm tra API cục bộ của Gemlogin (127.0.0.1:1010) đã sẵn sàng nhận kết nối và trả về dữ liệu hợp lệ chưa"""
    try:
        req = urllib.request.Request(f"{GEMLOGIN_API}/api/profiles?per_page=1", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode('utf-8'))
                return body.get('success') is True
    except Exception:
        return False
    return False

def ensure_gemlogin_running(logger_callback=None):
    """
    Tự động quét xem Gemlogin đã chạy chưa:
    - Nếu đã chạy và API sẵn sàng: bỏ qua
    - Nếu tiến trình đang chạy nhưng API chưa mở: đợi API sẵn sàng
    - Nếu chưa chạy: tự động khởi chạy Gemlogin và đợi API sẵn sàng
    """
    def _log(msg):
        if logger_callback:
            logger_callback(msg)
        else:
            print(msg)

    # 1. Nếu API đã sẵn sàng: Bỏ qua
    if is_gemlogin_api_ready():
        _log("ℹ️ Gemlogin đã mở và API sẵn sàng.")
        return True, "Gemlogin đã chạy sẵn và API đã mở."

    # 2. Kiểm tra xem tiến trình Gemlogin.exe có đang chạy không
    process_running = is_gemlogin_running()
    
    if not process_running:
        exe_path = find_gemlogin_executable()
        if not exe_path:
            _log("⚠️ Không tìm thấy file Gemlogin.exe. Vui lòng mở Gemlogin thủ công.")
            return False, "Không tìm thấy file Gemlogin.exe."
            
        _log(f"🚀 Phát hiện Gemlogin chưa chạy. Đang tự động mở: {exe_path}...")
        try:
            if exe_path.endswith('.lnk'):
                os.startfile(exe_path)
            else:
                subprocess.Popen([exe_path], close_fds=True)
        except Exception as e:
            _log(f"❌ Không thể khởi động Gemlogin: {e}")
            return False, f"Lỗi khởi chạy: {e}"
    else:
        _log("ℹ️ Tiến trình Gemlogin đang mở. Đang chờ API sẵn sàng...")

    # 3. Đợi Gemlogin và API cục bộ (cổng 1010) khởi động hoàn tất
    _log("⏳ Đang đợi Gemlogin khởi động và kích hoạt API cục bộ (127.0.0.1:1010)...")
    max_wait = 45  # tối đa 45 giây cho các máy khởi động chậm
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if is_gemlogin_api_ready():
            _log("✅ Gemlogin đã khởi động và API (cổng 1010) đã sẵn sàng!")
            # Nghỉ thêm 2 giây để SQLite và giao diện Gemlogin ổn định hoàn toàn
            time.sleep(2)
            return True, "Gemlogin đã sẵn sàng."
        time.sleep(1.5)

    _log("⚠️ Đã khởi động Gemlogin nhưng API chưa phản hồi kịp. Bạn có thể bấm nút '🔄 TẢI LẠI PROFILE' sau khi Gemlogin load xong.")
    return False, "Hết thời gian chờ API Gemlogin."

# Target Shopee domains
SHOPEE_DOMAINS = [
    "shopee.vn",
    "shopee.com.my",
    "shopee.ph",
    "shopee.tw",
    "shopee.co.th",
    "shopee.co.id"
]

# Additional app info cookies from extension popup.js (v3.0 - 26.08.2026)
ADDITIONAL_COOKIES = '; language=vi; SPC_RNBV=6081003; shopee_app_version=29531; shopee_rn_bundle_version=6081003; shopee_rn_version=1763129064'

# Mobile User-Agent Presets (9 devices from extension v3.0)
import random
UA_PRESETS = {
    "iphone_ios18": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6 Mobile/15E148 Safari/604.1",
    "iphone_ios17": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "iphone_ios16": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7_10 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "ipad_ios17": "Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "android_s21": "Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "android_s23": "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "android_pixel8": "Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "android_xiaomi": "Mozilla/5.0 (Linux; Android 13; 2201123G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "android_oppo": "Mozilla/5.0 (Linux; Android 13; CPH2451) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
}

def random_ua_string():
    """Trả về UA string Mobile ngẫu nhiên từ 9 thiết bị preset"""
    return random.choice(list(UA_PRESETS.values()))

# Đường dẫn mặc định của Extension Shopee Cookie
import hashlib
EXTENSION_PATH = r'E:\reup SP mơi\Cookie Shopee 26.08.2026'
if not os.path.exists(EXTENSION_PATH):
    for _candidate in [r'E:\reup SP moi\Cookie Shopee 26.08.2026', r'E:\Extension shopee af']:
        if os.path.exists(_candidate):
            EXTENSION_PATH = _candidate
            break

def get_chromium_extension_id(path_str):
    """Tính toán Extension ID chuẩn Chromium cho unpacked extension từ đường dẫn"""
    raw_sha = hashlib.sha256(path_str.encode('utf-16le')).digest()[:16]
    return ''.join(chr(ord('a') + (b >> 4)) + chr(ord('a') + (b & 0x0F)) for b in raw_sha)

def install_extension_to_profile(profile_path, ext_path=EXTENSION_PATH):
    """
    Cài đặt và ghim Extension vào thư mục dữ liệu của 1 profile Gemlogin:
    1. Sao chép các tệp extension vào thư mục 'Default/Extensions/<ext_id>/<ver>_0/'
    2. Ghi cấu hình extension, embedded manifest & quyền hạn vào 'Secure Preferences' và 'Preferences' (location=1, state=1)
    3. Bật chế độ nhà phát triển (developer_mode=True) trong 'Preferences'
    4. Ghim extension lên thanh công cụ của Chrome trong 'Preferences'
    """
    if not os.path.exists(profile_path):
        return False, f"Thư mục profile không tồn tại: {profile_path}"
    
    ext_path = os.path.abspath(ext_path)
    default_dir = os.path.join(profile_path, 'Default')
    os.makedirs(default_dir, exist_ok=True)
    
    # Đọc manifest.json
    manifest_file = os.path.join(ext_path, 'manifest.json')
    if not os.path.exists(manifest_file):
        return False, f"Không tìm thấy file manifest.json tại: {ext_path}"
        
    try:
        with open(manifest_file, 'r', encoding='utf-8') as mf:
            manifest = json.load(mf)
    except Exception as e:
        return False, f"Lỗi đọc manifest.json: {e}"
        
    ext_id = get_chromium_extension_id(ext_path)
    manifest_ver = manifest.get('version', '3.0')
    ver_dir = f"{manifest_ver}_0"
    
    # 1. Sao chép tệp extension vào thư mục Default/Extensions/<ext_id>/<ver>_0/
    dest_ext_dir = os.path.join(default_dir, 'Extensions', ext_id, ver_dir)
    os.makedirs(dest_ext_dir, exist_ok=True)
    for item in os.listdir(ext_path):
        s = os.path.join(ext_path, item)
        d = os.path.join(dest_ext_dir, item)
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
            
    # 2. Tạo cấu hình extension
    scriptable_hosts = []
    for s in manifest.get('content_scripts', []):
        if s.get('matches'):
            scriptable_hosts.extend(s.get('matches'))
            
    ext_config = {
        'account_extension_type': 0,
        'ack_prompt_count': 1,
        'active_bit': True,
        'active_permissions': {
            'api': manifest.get('permissions', []),
            'explicit_host': manifest.get('host_permissions', []),
            'manifest_permissions': [],
            'scriptable_host': scriptable_hosts
        },
        'commands': {'_execute_action': {'was_assigned': True}},
        'content_settings': [],
        'creation_flags': 38,
        'disable_reasons': [],
        'first_install_time': '13424969468222703',
        'from_webstore': False,
        'granted_permissions': {
            'api': manifest.get('permissions', []),
            'explicit_host': manifest.get('host_permissions', []),
            'manifest_permissions': [],
            'scriptable_host': scriptable_hosts
        },
        'incognito_content_settings': [],
        'incognito_preferences': {},
        'last_update_time': '13424969468222703',
        'location': 1,
        'manifest': manifest,
        'newAllowFileAccess': True,
        'path': f"{ext_id}\\{ver_dir}",
        'preferences': {},
        'regular_only_preferences': {},
        'service_worker_registration_info': {'version': manifest_ver},
        'serviceworkerevents': [
            'runtime.onInstalled', 'runtime.onStartup', 'tabs.onUpdated', 'webRequest.onBeforeSendHeaders/s1'
        ],
        'state': 1,
        'was_installed_by_default': False,
        'was_installed_by_oem': False,
        'withholding_permissions': False
    }
    
    # 3. Cập nhật Secure Preferences
    sec_pref_path = os.path.join(default_dir, 'Secure Preferences')
    sec_data = {}
    if os.path.exists(sec_pref_path):
        try:
            with open(sec_pref_path, 'r', encoding='utf-8') as f:
                sec_data = json.load(f)
        except Exception:
            sec_data = {}
            
    if 'extensions' not in sec_data:
        sec_data['extensions'] = {}
    if 'settings' not in sec_data['extensions']:
        sec_data['extensions']['settings'] = {}
    sec_data['extensions']['settings'][ext_id] = ext_config
    
    with open(sec_pref_path, 'w', encoding='utf-8') as f:
        json.dump(sec_data, f, indent=2)
        
    # 4. Cập nhật Preferences (Ghim extension & bật developer mode)
    pref_path = os.path.join(default_dir, 'Preferences')
    pref_data = {}
    if os.path.exists(pref_path):
        try:
            with open(pref_path, 'r', encoding='utf-8') as f:
                pref_data = json.load(f)
        except Exception:
            pref_data = {}
            
    if 'extensions' not in pref_data:
        pref_data['extensions'] = {}
    if 'pinned_extensions' not in pref_data['extensions']:
        pref_data['extensions']['pinned_extensions'] = []
    if ext_id not in pref_data['extensions']['pinned_extensions']:
        pref_data['extensions']['pinned_extensions'].append(ext_id)
        
    if 'ui' not in pref_data['extensions']:
        pref_data['extensions']['ui'] = {}
    pref_data['extensions']['ui']['developer_mode'] = True
    
    if 'settings' not in pref_data['extensions']:
        pref_data['extensions']['settings'] = {}
    pref_data['extensions']['settings'][ext_id] = ext_config
        
    with open(pref_path, 'w', encoding='utf-8') as f:
        json.dump(pref_data, f, indent=2)
        
    return True, f"Đã cài đặt & ghim Extension [{ext_id}]"

import sqlite3
import shutil

def clear_shopee_site_data(profile_path, domain="shopee.ph", debug_addr=None):
    """
    Xoá cookie và toàn bộ dữ liệu trang web (Site Data: IndexedDB, Cache, LocalStorage) CHỈ cho trang shopee.ph (hoặc domain chỉ định):
    1. Xoá cookies trong SQLite Cookies database khớp với host_key LIKE '%shopee.ph%' (hoặc domain được chọn)
    2. Xoá dữ liệu IndexedDB của riêng domain đó
    3. Xoá CacheStorage / ServiceWorker của riêng domain đó
    4. Nếu trình duyệt đang chạy (debug_addr), gửi lệnh CDP Storage.clearDataForOrigin cho domain đó
    """
    if not os.path.exists(profile_path):
        return False, f"Thư mục profile không tồn tại: {profile_path}"
        
    target_domain = domain.strip() if domain else "shopee.ph"
    if target_domain == "shopee" or target_domain == "Tất cả (All)":
        target_domain = "shopee.ph"
        
    default_dir = os.path.join(profile_path, 'Default')
    cleaned_items = []
    
    # 1. Xoá Cookies từ SQLite DB CHỈ cho target_domain (ví dụ: shopee.ph)
    cookie_db = os.path.join(default_dir, 'Network', 'Cookies')
    if os.path.exists(cookie_db):
        try:
            conn = sqlite3.connect(cookie_db)
            cur = conn.cursor()
            query = f"DELETE FROM cookies WHERE host_key LIKE '%{target_domain}%'"
            cur.execute(query)
            deleted_cookies = cur.rowcount
            conn.commit()
            conn.close()
            if deleted_cookies > 0:
                cleaned_items.append(f"Xoá {deleted_cookies} cookies ({target_domain})")
        except Exception as e:
            cleaned_items.append(f"Lỗi cookies db: {e}")
            
    # 2. Xoá IndexedDB folders của riêng target_domain
    indexed_db_dir = os.path.join(default_dir, 'IndexedDB')
    if os.path.exists(indexed_db_dir):
        try:
            deleted_idb = 0
            for item in os.listdir(indexed_db_dir):
                if target_domain.lower() in item.lower():
                    item_path = os.path.join(indexed_db_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                        deleted_idb += 1
            if deleted_idb > 0:
                cleaned_items.append(f"Xoá {deleted_idb} IndexedDB ({target_domain})")
        except Exception as e:
            cleaned_items.append(f"Lỗi IndexedDB: {e}")
            
    # 3. Xoá Service Worker CacheStorage
    sw_dir = os.path.join(default_dir, 'Service Worker')
    if os.path.exists(sw_dir):
        try:
            cache_storage = os.path.join(sw_dir, 'CacheStorage')
            if os.path.exists(cache_storage):
                for item in os.listdir(cache_storage):
                    if target_domain.lower() in item.lower():
                        shutil.rmtree(os.path.join(cache_storage, item), ignore_errors=True)
        except Exception:
            pass

    # 4. Nếu trình duyệt đang mở (qua debug_addr), gửi lệnh CDP dọn dẹp riêng target_domain
    if debug_addr:
        try:
            req = urllib.request.Request(f"http://{debug_addr}/json")
            with urllib.request.urlopen(req, timeout=3) as r:
                tabs = json.loads(r.read().decode('utf-8'))
                pages = [t for t in tabs if t.get('type') == 'page']
                if pages:
                    ws_url = pages[0].get('webSocketDebuggerUrl')
                    ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=5)
                    ws.send(json.dumps({'id': 1, 'method': 'Network.enable'}))
                    ws.recv()
                    
                    origins = [
                        f"https://{target_domain}",
                        f"https://seller.{target_domain}",
                        f"https://affiliate.{target_domain}",
                        f"https://banhang.{target_domain}",
                    ]
                    for idx, orig in enumerate(origins, start=10):
                        ws.send(json.dumps({
                            'id': idx,
                            'method': 'Storage.clearDataForOrigin',
                            'params': {'origin': orig, 'storageTypes': 'all'}
                        }))
                        ws.recv()
                    ws.close()
                    cleaned_items.append(f"Dọn RAM CDP ({target_domain})")
        except Exception:
            pass

    msg = ", ".join(cleaned_items) if cleaned_items else f"Đã sạch dữ liệu {target_domain}"
    return True, msg

def open_profile_with_extension(profile_path, browser_version=140, ext_path=EXTENSION_PATH, clear_site_data=False, domain="shopee.ph"):
    """
    Mở trực tiếp trình duyệt Chrome của profile kèm cờ --load-extension
    để nạp Extension Cookie Shopee ngay lập tức lên thanh công cụ.
    Tùy chọn clear_site_data=True sẽ dọn sạch cookies & site data trước khi mở.
    """
    if clear_site_data:
        clear_shopee_site_data(profile_path, domain=domain)

    ext_path = os.path.abspath(ext_path)
    
    # Tìm file thực thi chrome.exe của Gemlogin
    candidates = [
        rf"C:\Users\{os.getlogin()}\.gemlogin\browser\{browser_version}\Chrome-bin\chrome.exe",
        rf"C:\Users\{os.getlogin()}\.gemlogin\browser\140\Chrome-bin\chrome.exe",
        rf"C:\Users\{os.getlogin()}\.gemlogin\browser\141\Chrome-bin\chrome.exe",
    ]
    
    chrome_exe = None
    for c in candidates:
        if os.path.exists(c):
            chrome_exe = c
            break
            
def suppress_chrome_restore_popups(profile_path):
    """
    Sửa file Preferences của Profile để xóa cờ Crash, ngăn chặn hoàn toàn thông báo 'Restore pages?'.
    """
    targets = [
        os.path.join(profile_path, "Preferences"),
        os.path.join(profile_path, "Default", "Preferences")
    ]
    for p in targets:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                modified = False
                if 'profile' in data:
                    if data['profile'].get('exit_type') != 'Normal':
                        data['profile']['exit_type'] = 'Normal'
                        modified = True
                    if data['profile'].get('exited_cleanly') is not True:
                        data['profile']['exited_cleanly'] = True
                        modified = True
                if modified:
                    with open(p, 'w', encoding='utf-8') as f:
                        json.dump(data, f)
            except Exception:
                pass

def open_profile_with_extension(profile_path, browser_version=140, ext_path=EXTENSION_PATH, clear_site_data=False, domain="shopee.ph"):
    """
    Mở trực tiếp profile Gemlogin bằng chrome.exe kèm cờ --load-extension
    để nạp Extension Cookie Shopee ngay lập tức lên thanh công cụ.
    Tùy chọn clear_site_data=True sẽ dọn sạch cookies & site data trước khi mở.
    """
    if clear_site_data:
        clear_shopee_site_data(profile_path, domain=domain)

    suppress_chrome_restore_popups(profile_path)
    ext_path = os.path.abspath(ext_path)
    
    # Tìm file thực thi chrome.exe của Gemlogin
    candidates = [
        rf"C:\Users\{os.getlogin()}\.gemlogin\browser\{browser_version}\Chrome-bin\chrome.exe",
        rf"C:\Users\{os.getlogin()}\.gemlogin\browser\140\Chrome-bin\chrome.exe",
        rf"C:\Users\{os.getlogin()}\.gemlogin\browser\141\Chrome-bin\chrome.exe",
    ]
    
    chrome_exe = None
    for c in candidates:
        if os.path.exists(c):
            chrome_exe = c
            break
            
    if not chrome_exe:
        return False, "Không tìm thấy chrome.exe của Gemlogin"
        
    cmd = [
        chrome_exe,
        f"--user-data-dir={profile_path}",
        f"--load-extension={ext_path}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--disable-infobars",
        "--disable-notifications",
        "--noerrdialogs",
        "--disable-features=Translate,OptimizationHints,MediaRouter",
        f"https://{domain}"
    ]
    
    try:
        subprocess.Popen(cmd)
        return True, f"Đã mở profile kèm extension từ: {ext_path}"
    except Exception as e:
        return False, f"Lỗi khởi động trình duyệt: {e}"

def open_profile_with_extension_and_cdp(profile_path, port=52000, ext_path=EXTENSION_PATH, initial_url=None):
    """
    Khởi chạy Chrome trực tiếp kèm Extension và mở cổng Remote Debugging (CDP).
    Đảm bảo 100% Extension hoạt động và tự động ép giao diện sang Mobile.
    Trả về (proc, debug_addr) hoặc (None, None).
    """
    suppress_chrome_restore_popups(profile_path)
    ext_path = os.path.abspath(ext_path)
    
    candidates = [
        rf"C:\Users\{os.getlogin()}\.gemlogin\browser\140\Chrome-bin\chrome.exe",
        rf"C:\Users\{os.getlogin()}\.gemlogin\browser\141\Chrome-bin\chrome.exe",
    ]
    
    chrome_exe = None
    for c in candidates:
        if os.path.exists(c):
            chrome_exe = c
            break
            
    if not chrome_exe:
        return None, None
        
    cmd = [
        chrome_exe,
        f"--user-data-dir={profile_path}",
        f"--load-extension={ext_path}",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--disable-infobars",
        "--disable-notifications",
        "--noerrdialogs",
        "--disable-features=Translate,OptimizationHints,MediaRouter"
    ]
    if initial_url:
        cmd.append(initial_url)
        
    try:
        proc = subprocess.Popen(cmd)
        return proc, f"127.0.0.1:{port}"
    except Exception as e:
        print(f"Error launching chrome with ext & cdp: {e}")
        return None, None

def get_running_profiles():
    """
    Detects which profiles are already running on the system
    by scanning chrome.exe command lines.
    Returns a set of running profile IDs.
    """
    running_ids = set()
    try:
        # Run PowerShell command to get chrome.exe command lines
        cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \\"name=\'chrome.exe\'\\" | Select-Object CommandLine | ConvertTo-Json"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        
        stdout = result.stdout.strip()
        if not stdout:
            return running_ids
            
        data = json.loads(stdout)
        if isinstance(data, dict):
            data = [data]
            
        for item in data:
            cmdline = item.get('CommandLine') or ''
            # Matches F:\gemlogin\profiles\1 or similar path format
            match = re.search(r'--user-data-dir=["\']?.*profiles[\\/](\d+)["\']?', cmdline)
            if match:
                running_ids.add(int(match.group(1)))
    except Exception as e:
        print(f"Warning: Could not detect running profiles via PowerShell: {e}")
        print("Falling back to assuming all profiles started by this script should be closed.")
    return running_ids

def api_get_profiles(retries=3, delay=1.5, logger_callback=None):
    """
    Fetches ALL profiles from Gemlogin local API with pagination and automatic retries.
    """
    def _log(msg):
        if logger_callback:
            logger_callback(msg)
        else:
            print(msg)

    for attempt in range(1, retries + 1):
        all_profiles = []
        seen_ids = set()

        # Cách 1: Gọi trực tiếp /api/profiles với phân trang (Gemlogin trả về profiles của tất cả groups)
        try:
            page = 1
            while True:
                url = f"{GEMLOGIN_API}/api/profiles?per_page=500&page={page}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    res = json.loads(response.read().decode('utf-8'))
                    if not res.get('success'):
                        break
                    data = res.get('data', [])
                    if not data:
                        break
                    for p in data:
                        pid = p.get('id')
                        if pid not in seen_ids:
                            seen_ids.add(pid)
                            all_profiles.append(p)
                    if len(data) < 500:
                        break
                    page += 1
        except Exception as e:
            if attempt < retries:
                _log(f"⏳ Đang kết nối lại Gemlogin API (lần {attempt}/{retries})...")

        if all_profiles:
            return all_profiles

        # Cách 2: Nếu cách 1 chưa có dữ liệu, thử quét theo từng group (dự phòng)
        try:
            group_ids = [None]
            req = urllib.request.Request(f"{GEMLOGIN_API}/api/groups", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode('utf-8'))
                if res.get('success'):
                    for g in res.get('data', []):
                        group_ids.append(g['id'])
            
            for gid in group_ids:
                page = 1
                while True:
                    url = f"{GEMLOGIN_API}/api/profiles?per_page=500&page={page}"
                    if gid is not None:
                        url += f"&group_id={gid}"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        res = json.loads(response.read().decode('utf-8'))
                        if not res.get('success'):
                            break
                        data = res.get('data', [])
                        if not data:
                            break
                        for p in data:
                            pid = p.get('id')
                            if pid not in seen_ids:
                                seen_ids.add(pid)
                                all_profiles.append(p)
                        if len(data) < 500:
                            break
                        page += 1
        except Exception:
            pass

        if all_profiles:
            return all_profiles

        if attempt < retries:
            time.sleep(delay)

    if not all_profiles:
        _log(f"⚠️ Không tìm thấy profile nào từ Gemlogin API tại {GEMLOGIN_API}")
    return all_profiles

def api_start_profile(profile_id):
    """
    Starts a profile via Gemlogin API.
    Returns (remote_debugging_address, driver_path) on success, or None.
    """
    url = f"{GEMLOGIN_API}/api/profiles/start/{profile_id}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as response:
            res = json.loads(response.read().decode('utf-8'))
            if res.get('success') and 'data' in res:
                return res['data'].get('remote_debugging_address'), res['data'].get('driver_path')
    except Exception as e:
        print(f"Error starting profile {profile_id}: {e}")
    return None, None

def api_close_profile(profile_id):
    """
    Closes a profile via Gemlogin API
    """
    url = f"{GEMLOGIN_API}/api/profiles/close/{profile_id}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res.get('success', False)
    except Exception as e:
        print(f"Error closing profile {profile_id}: {e}")
    return False

def get_websocket_url(debug_addr):
    """
    Queries /json to get the active target list and webSocketDebuggerUrl
    """
    url = f"http://{debug_addr}/json"
    for attempt in range(5):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as response:
                targets = json.loads(response.read().decode('utf-8'))
                for target in targets:
                    if target.get('type') == 'page':
                        return target.get('webSocketDebuggerUrl')
        except Exception:
            time.sleep(1)
    return None

def override_navigator_via_cdp(ws_url, ua_string):
    """
    Giả lập Mobile UA 2 lớp qua CDP (tương đương extension v3.0):
    Lớp 1: Network.setUserAgentOverride (HTTP Header)
    Lớp 2: Runtime.evaluate ghi đè navigator.* (JS context)
    """
    try:
        ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
        
        # Lớp 1: Ghi đè HTTP Header User-Agent
        is_apple = 'iPhone' in ua_string or 'iPad' in ua_string
        platform = 'iPhone' if 'iPhone' in ua_string else ('iPad' if 'iPad' in ua_string else 'Linux armv8l')
        
        ws.send(json.dumps({
            "id": 20,
            "method": "Network.setUserAgentOverride",
            "params": {
                "userAgent": ua_string,
                "platform": platform
            }
        }))
        ws.recv()
        
        # Lớp 2: Ghi đè navigator.* trong JavaScript context (giống inject.js overrideNavigator)
        vendor = "Apple Computer, Inc." if is_apple else "Google Inc."
        app_version = ua_string.replace("Mozilla/", "")
        
        js_override = """
        (function() {
            var defineProp = function(propName, propValue) {
                try {
                    Object.defineProperty(navigator, propName, {
                        get: function() { return propValue; },
                        configurable: true
                    });
                } catch(e) {}
            };
            defineProp('userAgent', %s);
            defineProp('appVersion', %s);
            defineProp('platform', %s);
            defineProp('maxTouchPoints', 5);
            defineProp('vendor', %s);
        })();
        """ % (json.dumps(ua_string), json.dumps(app_version), json.dumps(platform), json.dumps(vendor))
        
        ws.send(json.dumps({
            "id": 21,
            "method": "Runtime.evaluate",
            "params": {"expression": js_override}
        }))
        ws.recv()
        
        ws.close()
        return True
    except Exception as e:
        print(f"    ⚠️ Mobile UA override error: {e}")
        return False

def extract_csrf_5_steps(ws_url, shopee_domain):
    """
    Trích xuất CSRF Token theo pipeline 5 bước (giống extension v3.0 inject.js):
    1. document.cookie regex csrftoken
    2. meta[name="csrf-token"]
    3. input[name="csrfmiddlewaretoken"]
    4. window.csrftoken / window.csrf_token
    5. fetch API ngầm /api/v4/homepage/campaign_modules (buộc Shopee cấp csrftoken mới)
    Trả về csrf_token string hoặc None
    """
    csrf_token = None
    
    try:
        ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
        
        # Bước 1-4: Trích xuất CSRF từ nhiều nguồn trong DOM (giống extractCsrfData())
        js_extract = """
        (function() {
            var csrfFromCookie = '';
            var match = document.cookie.match(/csrftoken=([^;]+)/);
            if (match) csrfFromCookie = match[1];
            
            var metaTag = document.querySelector('meta[name="csrf-token"]');
            var csrfFromMeta = metaTag ? metaTag.getAttribute('content') : '';
            
            var inputTag = document.querySelector('input[name="csrfmiddlewaretoken"]');
            var csrfFromInput = inputTag ? inputTag.value : '';
            
            var csrfFromWindow = window.csrftoken || window.csrf_token || '';
            
            return csrfFromCookie || csrfFromMeta || csrfFromInput || csrfFromWindow || '';
        })()
        """
        
        ws.send(json.dumps({
            "id": 30,
            "method": "Runtime.evaluate",
            "params": {"expression": js_extract, "returnByValue": True}
        }))
        res = json.loads(ws.recv())
        csrf_token = res.get('result', {}).get('result', {}).get('value', '')
        
        if csrf_token:
            ws.close()
            return csrf_token
        
        # Bước 5: Gọi API ngầm buộc Shopee cấp csrftoken mới (giống fetchWithCreds())
        js_fetch = """
        (async function() {
            try {
                await fetch('https://%s/api/v4/homepage/campaign_modules', {
                    method: 'GET', 
                    credentials: 'include'
                });
                // Đợi 1 giây cho cookie được set
                await new Promise(r => setTimeout(r, 1000));
                var match = document.cookie.match(/csrftoken=([^;]+)/);
                return match ? match[1] : '';
            } catch(e) {
                return '';
            }
        })()
        """ % shopee_domain
        
        ws.send(json.dumps({
            "id": 31,
            "method": "Runtime.evaluate",
            "params": {"expression": js_fetch, "returnByValue": True, "awaitPromise": True}
        }))
        res2 = json.loads(ws.recv())
        csrf_token = res2.get('result', {}).get('result', {}).get('value', '')
        
        ws.close()
    except Exception as e:
        print(f"    ⚠️ CSRF 5-step pipeline error: {e}")
    
def perform_auto_facebook_login(ws_url, domain="shopee.ph", debug_addr=None):
    """
    Tự động đợi trang Shopee tải hoàn chỉnh, dùng tín hiệu Trusted CDP Mouse Click bấm nút Facebook và nút Continue.
    """
    target_domain = domain if domain else "shopee.ph"
    
    try:
        ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=20)
        
        # 1. Đợi trang Shopee Mobile tải hoàn tất toàn bộ script & React (8 giây)
        time.sleep(8)
        
        # 2. Tìm tọa độ nút 'Login with Facebook'
        get_fb_coords_js = """
        (() => {
            for (const el of document.querySelectorAll('button, a, div[role="button"], div')) {
                if (el.closest('footer') || el.closest('.footer')) continue;
                const t = (el.innerText || '').trim().toLowerCase();
                if (t === 'facebook' || t === 'login with facebook') {
                    el.scrollIntoView({block: 'center'});
                    const rect = el.getBoundingClientRect();
                    return {
                        success: true,
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2)
                    };
                }
            }
            return {success: false};
        })()
        """
        
        fb_coords = None
        for sec in range(1, 16):
            ws.send(json.dumps({'id': 110 + sec, 'method': 'Runtime.evaluate', 'params': {'expression': get_fb_coords_js, 'returnByValue': True}}))
            res_fb = json.loads(ws.recv()).get('result', {}).get('result', {}).get('value', {})
            if res_fb.get('success'):
                fb_coords = res_fb
                break
            time.sleep(1)
            
        if not fb_coords:
            ws.close()
            return False, "Không tìm thấy nút Facebook trên trang"
            
        # 3. Gửi Trusted Mouse Click vào nút Facebook
        x, y = fb_coords['x'], fb_coords['y']
        ws.send(json.dumps({'id': 130, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mouseMoved', 'x': x, 'y': y}}))
        ws.recv()
        ws.send(json.dumps({'id': 131, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}}))
        ws.recv()
        time.sleep(0.08)
        ws.send(json.dumps({'id': 132, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}}))
        ws.recv()
        
        # 4. Đợi cửa sổ Facebook OAuth mở ra (5 giây)
        time.sleep(5)
        
        ws_fb = ws
        fb_tab = None
        if debug_addr:
            try:
                req_t = urllib.request.Request(f"http://{debug_addr}/json")
                with urllib.request.urlopen(req_t, timeout=4) as rt:
                    tabs = json.loads(rt.read().decode('utf-8'))
                for t in tabs:
                    if 'facebook.com' in t.get('url', '').lower():
                        fb_tab = t
                        break
                if fb_tab and fb_tab.get('webSocketDebuggerUrl') != ws_url:
                    ws_fb = websocket.create_connection(fb_tab.get('webSocketDebuggerUrl'), suppress_origin=True, timeout=10)
            except Exception:
                pass
                
        # 5. Tìm tọa độ nút 'Continue' trên Facebook
        get_cont_coords_js = """
        (() => {
            for (const el of document.querySelectorAll('button, div[role="button"], a, input[type="submit"], span, div')) {
                const t = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                if (t === 'continue' || t.startsWith('continue as') || t.includes('tiếp tục') || t.includes('dưới tên')) {
                    el.scrollIntoView({block: 'center'});
                    const rect = el.getBoundingClientRect();
                    return {
                        success: true,
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2)
                    };
                }
            }
            const confirmBtn = document.querySelector('[name="__CONFIRM__"], button[name="__CONFIRM__"]');
            if (confirmBtn) {
                confirmBtn.scrollIntoView({block: 'center'});
                const rect = confirmBtn.getBoundingClientRect();
                return {
                    success: true,
                    x: Math.round(rect.left + rect.width / 2),
                    y: Math.round(rect.top + rect.height / 2)
                };
            }
            return {success: false};
        })()
        """
        
        cont_coords = None
        for sec in range(1, 16):
            ws_fb.send(json.dumps({'id': 140 + sec, 'method': 'Runtime.evaluate', 'params': {'expression': get_cont_coords_js, 'returnByValue': True}}))
            res_cont = json.loads(ws_fb.recv()).get('result', {}).get('result', {}).get('value', {})
            if res_cont.get('success'):
                cont_coords = res_cont
                break
            time.sleep(1)
            
        if cont_coords:
            cx, cy = cont_coords['x'], cont_coords['y']
            ws_fb.send(json.dumps({'id': 160, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mouseMoved', 'x': cx, 'y': cy}}))
            ws_fb.recv()
            ws_fb.send(json.dumps({'id': 161, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mousePressed', 'x': cx, 'y': cy, 'button': 'left', 'clickCount': 1}}))
            ws_fb.recv()
            time.sleep(0.08)
            ws_fb.send(json.dumps({'id': 162, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mouseReleased', 'x': cx, 'y': cy, 'button': 'left', 'clickCount': 1}}))
            ws_fb.recv()
        else:
            # Fallback
            ws_fb.send(json.dumps({'id': 163, 'method': 'Runtime.evaluate', 'params': {'expression': 'var b = document.querySelector("[name=\'__CONFIRM__\']"); if(b) b.click();'}}))
            try: ws_fb.recv()
            except Exception: pass
            
        if ws_fb != ws:
            try: ws_fb.close()
            except Exception: pass
            
        # 6. Đợi Shopee nhận phiên đăng nhập và chuyển hướng (6-8 giây)
        time.sleep(6)
        ws.close()
        return True, "Đã tự động bấm Login with Facebook và Continue thành công"
    except Exception as e:
        return False, f"Lỗi tự động Login FB: {e}"

def parse_google_sheet_url_to_csv_url(sheet_url):
    import re
    sheet_url = (sheet_url or '').strip()
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', sheet_url)
    if not m:
        return sheet_url
    sheet_id = m.group(1)
    gid_m = re.search(r'[#&?]gid=([0-9]+)', sheet_url)
    gid = gid_m.group(1) if gid_m else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

def col_letter_to_index(col):
    if isinstance(col, int):
        return col
    col = str(col).strip().upper()
    if not col:
        return -1
    idx = 0
    for ch in col:
        if 'A' <= ch <= 'Z':
            idx = idx * 26 + (ord(ch) - ord('A') + 1)
        else:
            return -1
    return idx - 1

def fetch_accounts_from_google_sheet(sheet_url, user_col="E", profile_col="G"):
    """
    Tải danh sách tài khoản từ Google Sheet theo cột cấu hình.
    user_col: Cột chứa Username Shopee (mặc định E)
    profile_col: Cột chứa Tên Profile Gemlogin (mặc định G)
    Trả về (account_map {profile_name_upper: username}, message).
    """
    csv_url = parse_google_sheet_url_to_csv_url(sheet_url)
    account_map = {}
    if not csv_url:
        return account_map, "Link Google Sheet không hợp lệ"
        
    u_idx = col_letter_to_index(user_col)
    p_idx = col_letter_to_index(profile_col)
    if u_idx < 0: u_idx = 4  # Default E
    if p_idx < 0: p_idx = 6  # Default G
    max_idx = max(u_idx, p_idx)
    
    try:
        req = urllib.request.Request(
            csv_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode('utf-8', errors='ignore')
            
        import io
        reader = csv.reader(io.StringIO(content))
        for row in reader:
            if len(row) > max_idx:
                username = row[u_idx].strip()
                p_name = row[p_idx].strip().upper()
                if username and p_name and username.lower() != 'ph' and not p_name.startswith('TÊN') and not username.lower().startswith('user'):
                    account_map[p_name] = username
                    
        return account_map, f"Đã nạp {len(account_map)} tài khoản từ Google Sheet (Cột {str(user_col).upper()}: User, Cột {str(profile_col).upper()}: Profile)."
    except Exception as e:
        return account_map, f"Lỗi tải Google Sheet: {e}"

def perform_auto_form_login(ws_url, domain="shopee.ph", username="", password="Khoa01@c"):
    """
    Tự động điền Username (Cột E) & Mật khẩu (mặc định Khoa01@c), rồi click nút LOG IN trên Shopee Mobile.
    """
    try:
        ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=20)
        
        # 1. Điền Username và Password vào Form
        fill_form_js = """
        ((user, pass) => {
            function setInput(input, value) {
                input.focus();
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(input, value);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            const userInputs = Array.from(document.querySelectorAll('input')).filter(i => i.type !== 'password' && i.type !== 'hidden');
            const passInputs = Array.from(document.querySelectorAll('input[type="password"]'));
            
            let userFilled = false;
            let passFilled = false;
            
            if (userInputs.length > 0) {
                setInput(userInputs[0], user);
                userFilled = true;
            }
            if (passInputs.length > 0) {
                setInput(passInputs[0], pass);
                passFilled = true;
            }
            
            return {
                success: userFilled && passFilled,
                userFilled: userFilled,
                passFilled: passFilled
            };
        })(%s, %s)
        """ % (json.dumps(username), json.dumps(password))
        
        ws.send(json.dumps({'id': 302, 'method': 'Runtime.evaluate', 'params': {'expression': fill_form_js, 'returnByValue': True}}))
        fill_res = json.loads(ws.recv()).get('result', {}).get('result', {}).get('value', {})
        time.sleep(1)
        
        # 2. Tìm tọa độ nút LOG IN và gửi Trusted Mouse Click
        get_login_btn_js = """
        (() => {
            const allElements = Array.from(document.querySelectorAll('button, div[role="button"], a, input[type="submit"]'));
            for (const el of allElements) {
                if (el.closest('footer') || el.closest('.footer')) continue;
                const t = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                if (t === 'login' || t === 'log in' || t === 'đăng nhập') {
                    el.scrollIntoView({block: 'center'});
                    const rect = el.getBoundingClientRect();
                    return {
                        success: true,
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2)
                    };
                }
            }
            return {success: false};
        })()
        """
        ws.send(json.dumps({'id': 303, 'method': 'Runtime.evaluate', 'params': {'expression': get_login_btn_js, 'returnByValue': True}}))
        login_btn_coords = json.loads(ws.recv()).get('result', {}).get('result', {}).get('value', {})
        
        if login_btn_coords.get('success'):
            lx, ly = login_btn_coords['x'], login_btn_coords['y']
            ws.send(json.dumps({'id': 310, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mouseMoved', 'x': lx, 'y': ly}}))
            ws.recv()
            ws.send(json.dumps({'id': 311, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mousePressed', 'x': lx, 'y': ly, 'button': 'left', 'clickCount': 1}}))
            ws.recv()
            time.sleep(0.08)
            ws.send(json.dumps({'id': 312, 'method': 'Input.dispatchMouseEvent', 'params': {'type': 'mouseReleased', 'x': lx, 'y': ly, 'button': 'left', 'clickCount': 1}}))
            ws.recv()
            
        # 3. Đợi nhận phiên đăng nhập (8 giây)
        time.sleep(8)
        ws.close()
        return True, "Đã gửi thông tin đăng nhập tài khoản & mật khẩu"
    except Exception as e:
        return False, f"Lỗi đăng nhập bằng tài khoản: {e}"

def check_captcha_or_otp_presence(ws_url):
    """
    Kiểm tra xem trang hiện tại có đang hiển thị Captcha kéo mảnh ghép, mã OTP, hoặc màn hình xác minh không.
    (Không coi màn hình traffic/error hay Page Unavailable là Captcha).
    """
    try:
        ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=5)
        check_js = """
        (() => {
            const url = window.location.href.toLowerCase();
            if (url.includes('/traffic/error') || url.includes('error?home_url')) {
                return { isVerification: false, isTrafficError: true };
            }
            if (url.includes('/captcha') || url.includes('/otp') || url.includes('/security')) {
                return { isVerification: true, type: 'url' };
            }
            const hasCaptchaEl = document.querySelector('iframe[src*="captcha"], div[class*="captcha"], div[class*="puzzle"], div[class*="security"], div[class*="vcode"], input[placeholder*="OTP"], input[placeholder*="code"], input[placeholder*="mã"], input[type="tel"]');
            if (hasCaptchaEl) {
                return { isVerification: true, type: 'element' };
            }
            const bodyText = (document.body.innerText || '').toLowerCase();
            if (bodyText.includes('page unavailable') || bodyText.includes('something went wrong')) {
                return { isVerification: false, isTrafficError: true };
            }
            if (bodyText.includes('xác minh') || bodyText.includes('verification') || bodyText.includes('captcha') || bodyText.includes('kéo mảnh ghép') || bodyText.includes('mã xác thực') || bodyText.includes('enter the code') || bodyText.includes('puzzle') || bodyText.includes('please slide') || bodyText.includes('drag the slider') || bodyText.includes('slide to complete')) {
                return { isVerification: true, type: 'text' };
            }
            return { isVerification: false };
        })()
        """
        ws.send(json.dumps({'id': 501, 'method': 'Runtime.evaluate', 'params': {'expression': check_js, 'returnByValue': True}}))
        res = json.loads(ws.recv()).get('result', {}).get('result', {}).get('value', {})
        ws.close()
        return res.get('isVerification', False)
    except Exception:
        return False

def extract_cookies_via_cdp(ws_url, target_domain=None, mobile_ua=False):
    """
    Kết nối CDP lấy cookie & User Agent.
    Sử dụng Network.getAllCookies để lấy trọn vẹn toàn bộ cookie của Shopee (kể cả khi ở trang traffic error).
    Sử dụng CSRF Pipeline 5 bước để đảm bảo luôn có csrftoken.
    """
    cookies_list = []
    user_agent = None
    
    try:
        # Nếu bật Mobile UA, ghi đè navigator trước
        if mobile_ua:
            ua_str = random_ua_string()
            override_navigator_via_cdp(ws_url, ua_str)
            bg_domain = target_domain if target_domain else "shopee.vn"
            try:
                ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
                ws.send(json.dumps({
                    "id": 22,
                    "method": "Page.navigate",
                    "params": {"url": f"https://{bg_domain}"}
                }))
                ws.recv()
                ws.close()
                time.sleep(4)
            except Exception:
                pass
        
        # 1. Lấy toàn bộ cookie qua CDP Network.getAllCookies
        ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
        try:
            ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
            res = json.loads(ws.recv())
            cookies_list = res.get('result', {}).get('cookies', [])
        except Exception:
            cookies_list = []
            
        if not cookies_list:
            shopee_urls = [f"https://{domain}" for domain in SHOPEE_DOMAINS]
            cmd = {
                "id": 2,
                "method": "Network.getCookies",
                "params": {"urls": shopee_urls}
            }
            ws.send(json.dumps(cmd))
            res = json.loads(ws.recv())
            cookies_list = res.get('result', {}).get('cookies', [])
        ws.close()
        
        # CSRF Pipeline 5 bước (giống extension v3.0)
        has_csrf = any(c.get('name') == 'csrftoken' for c in cookies_list)
        if not has_csrf:
            # Xác định domain Shopee đang hoạt động
            bg_domain = target_domain if target_domain else "shopee.vn"
            if not target_domain:
                for c in cookies_list:
                    d = c.get('domain', '').lstrip('.')
                    for shopee_d in SHOPEE_DOMAINS:
                        if d == shopee_d or d.endswith('.' + shopee_d):
                            bg_domain = shopee_d
                            break
            
            # Thử trích xuất CSRF từ DOM/API trước (Bước 1-5)
            csrf_from_pipeline = extract_csrf_5_steps(ws_url, bg_domain)
            
            if csrf_from_pipeline:
                # Thêm csrf cookie thủ công vào danh sách
                cookies_list.append({
                    'name': 'csrftoken',
                    'value': csrf_from_pipeline,
                    'domain': f'.{bg_domain}'
                })
            else:
                # Fallback: Mở tab nền để buộc Shopee cấp cookie (cách cũ)
                try:
                    ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
                    create_cmd = {
                        "id": 10,
                        "method": "Target.createTarget",
                        "params": {"url": f"https://{bg_domain}"}
                    }
                    ws.send(json.dumps(create_cmd))
                    res_create = json.loads(ws.recv())
                    tab_target_id = res_create.get('result', {}).get('targetId')
                    
                    if tab_target_id:
                        time.sleep(5)
                        ws.send(json.dumps({
                            "id": 11,
                            "method": "Target.closeTarget",
                            "params": {"targetId": tab_target_id}
                        }))
                        ws.recv()
                        
                        # Re-fetch cookies
                        ws.send(json.dumps(cmd))
                        res_refetch = json.loads(ws.recv())
                        cookies_list = res_refetch.get('result', {}).get('cookies', [])
                    ws.close()
                except Exception as e:
                    print(f"    Fallback csrftoken via background tab error: {e}")
                
    except Exception as e:
        print(f"CDP cookie extraction error: {e}")
        
    try:
        # Get User Agent
        ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
        cmd_ua = {
            "id": 2,
            "method": "Browser.getVersion",
            "params": {}
        }
        ws.send(json.dumps(cmd_ua))
        res_ua = json.loads(ws.recv())
        user_agent = res_ua.get('result', {}).get('userAgent')
        ws.close()
    except Exception:
        pass
        
    return cookies_list, user_agent

# Danh sách các cookie thiết yếu của Shopee (chuẩn theo mẫu PH3001 upload thành công cho Tool MLS)
ESSENTIAL_COOKIE_KEYS = [
    'csrftoken',
    'SPC_F',
    'REC_T_ID',
    'SPC_SI',
    'SPC_SEC_SI',
    'AC_CERT_D',
    'SPC_ST',
    'SPC_U',
    'SPC_R_T_ID',
    'SPC_R_T_IV',
    'SPC_T_ID',
    'SPC_T_IV'
]

def get_country_code(domain):
    domain = (domain or "").lower()
    if "shopee.vn" in domain: return "vn"
    if "shopee.ph" in domain: return "ph"
    if "shopee.com.my" in domain or "shopee.my" in domain: return "my"
    if "shopee.co.id" in domain or "shopee.id" in domain: return "id"
    if "shopee.co.th" in domain or "shopee.th" in domain: return "th"
    if "shopee.tw" in domain: return "tw"
    if "shopee.sg" in domain: return "sg"
    return "ph"

def format_cookies(cookies_list, target_domain=None, clean_mode=True):
    """
    Nhóm cookie theo tên miền và định dạng chuỗi cookie.
    Trả về dictionary {domain: (cookie_string, is_logged_in)}.
    - target_domain: Chỉ lấy cookie của tên miền được chọn (hoặc None/ALL để lấy tất cả).
    - clean_mode=True: Chế độ tinh gọn (chuẩn PH3001), chỉ giữ lại các token cốt lõi và app signature,
      loại bỏ toàn bộ cookie rác (_ga, _fbp, ds, shopee_webUnique_ccd...) giúp tránh lỗi HTTP 403 trên Tool MLS.
    """
    domain_cookies = {}
    
    for cookie in cookies_list:
        domain = cookie.get('domain', '')
        # Normalize domain (.shopee.vn -> shopee.vn)
        norm_domain = domain.lstrip('.')
        
        # Check if domain belongs to shopee
        matched_domain = None
        for d in SHOPEE_DOMAINS:
            if norm_domain == d or norm_domain.endswith('.' + d):
                matched_domain = d
                break
                
        if not matched_domain:
            continue
            
        if target_domain and target_domain != "ALL" and matched_domain != target_domain:
            continue
            
        if matched_domain not in domain_cookies:
            domain_cookies[matched_domain] = []
            
        domain_cookies[matched_domain].append(cookie)
        
    formatted_results = {}
    for domain, cookies in domain_cookies.items():
        cookie_map = {}
        is_logged_in = False
        
        for c in cookies:
            name = c.get('name')
            value = c.get('value')
            if name and value:
                cookie_map[name] = value
                
            # Logged in indicators
            if name in ['SPC_EC', 'SPC_U', 'SPC_ST']:
                is_logged_in = True
                
        cookie_parts = []
        
        # 1. csrftoken luôn đặt ở đầu tiên
        if 'csrftoken' in cookie_map:
            cookie_parts.append(f"csrftoken={cookie_map['csrftoken']}")
            
        if clean_mode:
            # Chế độ tinh gọn: chỉ lấy các token cần thiết theo thứ tự chuẩn PH3001
            for k in ESSENTIAL_COOKIE_KEYS:
                if k != 'csrftoken' and k in cookie_map:
                    cookie_parts.append(f"{k}={cookie_map[k]}")
        else:
            # Chế độ đầy đủ: lấy toàn bộ cookie
            for k, v in cookie_map.items():
                if k != 'csrftoken':
                    cookie_parts.append(f"{k}={v}")
                    
        cookie_str = "; ".join(cookie_parts)
        if cookie_str:
            cookie_str += ADDITIONAL_COOKIES
        else:
            cookie_str = ADDITIONAL_COOKIES.lstrip('; ')
            
        formatted_results[domain] = (cookie_str, is_logged_in)
        
    return formatted_results

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tự động trích xuất Cookie Shopee từ các profile Gemlogin.")
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số lượng profile xử lý (0 = tất cả).")
    parser.add_argument("--batch", type=int, default=5, help="Số lượng profile mở đồng thời tối đa.")
    parser.add_argument("--country", type=str, default="ALL", help="Quốc gia lấy cookie (VN, PH, MY, ID, TH, TW hoặc ALL).")
    parser.add_argument("--mobile-ua", action="store_true", default=False, help="Bật giả lập Mobile UA (bypass anti-bot Shopee).")
    parser.add_argument("--full-cookies", action="store_true", default=False, help="Lấy toàn bộ cookie thô (mặc định là lấy tinh gọn chuẩn PH3001 cho Tool MLS).")
    parser.add_argument("--output", type=str, default="shopee_cookies.txt", help="Tên file lưu kết quả (.txt hoặc .csv).")
    args = parser.parse_args()

    country_map = {
        "ALL": None,
        "VN": "shopee.vn",
        "PH": "shopee.ph",
        "MY": "shopee.com.my",
        "ID": "shopee.co.id",
        "TH": "shopee.co.th",
        "TW": "shopee.tw"
    }
    target_domain = country_map.get(args.country.upper(), None)

    print("=== Tool Lấy Cookie Shopee tự động từ Gemlogin ===")
    print(f"Quét API Gemlogin tại: {GEMLOGIN_API}")
    if target_domain:
        print(f"Lọc cookie cho quốc gia: {args.country.upper()} ({target_domain})")
    else:
        print("Lấy cookie cho tất cả quốc gia (Shopee domains)")
    
    # 1. Lấy danh sách profile từ API
    profiles = api_get_profiles()
    if not profiles:
        print("Không có profile nào được tìm thấy hoặc không thể kết nối tới Gemlogin API.")
        return
        
    print(f"Đã tìm thấy tổng cộng {len(profiles)} profile.")
    
    # Giới hạn số lượng profile nếu có tham số limit
    if args.limit > 0:
        profiles = profiles[:args.limit]
        print(f"Chỉ xử lý giới hạn {args.limit} profile đầu tiên.")
        
    # 2. Phát hiện các profile đang chạy sẵn trên máy để không đóng sau khi xong
    running_before = get_running_profiles()
    print(f"Phát hiện {len(running_before)} profile đang chạy sẵn trên máy: {list(running_before)}")
    
    # Chuẩn bị file kết quả (hỗ trợ .txt và .csv)
    is_txt = args.output.endswith('.txt')
    file_exists = os.path.exists(args.output)
    
    if is_txt:
        txt_file = open(args.output, mode="w", encoding="utf-8")
    else:
        csv_file = open(args.output, mode="w", encoding="utf-8", newline="")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["Profile ID", "Profile Name", "Domain", "Status", "Cookie", "User Agent", "Exported At"])

    processed_count = 0
    success_count = 0
    
    # Xử lý theo đợt (Batching)
    batch_size = args.batch
    for i in range(0, len(profiles), batch_size):
        batch = profiles[i:i+batch_size]
        print(f"\n--- Đang xử lý nhóm profile {i+1} đến {min(i+batch_size, len(profiles))} ---")
        
        opened_in_batch = []
        
        # 1. Khởi động tất cả các profile trong đợt này
        for p in batch:
            p_id = p['id']
            p_name = p['name']
            
            is_already_running = p_id in running_before
            status_str = "đang chạy sẵn" if is_already_running else "đang đóng, đang mở..."
            print(f"Profile [{p_id}] {p_name} ({status_str})")
            
            addr, _ = api_start_profile(p_id)
            if addr:
                opened_in_batch.append({
                    "id": p_id,
                    "name": p_name,
                    "addr": addr,
                    "already_running": is_already_running
                })
            else:
                print(f"❌ Không thể khởi động profile [{p_id}] {p_name}")
                
        # Đợi một chút để trình duyệt của các profile khởi động hoàn chỉnh
        time.sleep(2)
        
        # 2. Kết nối và lấy cookie cho các profile đã mở thành công
        for item in opened_in_batch:
            p_id = item['id']
            p_name = item['name']
            addr = item['addr']
            
            print(f"-> Đang kết nối tới [{p_id}] {p_name} ({addr})...")
            ws_url = get_websocket_url(addr)
            if not ws_url:
                print(f"❌ Không lấy được WebSocket cho [{p_id}] {p_name}")
                continue
                
            cookies_list, ua = extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=args.mobile_ua)
            if not cookies_list:
                print(f"⚠️ Không tìm thấy cookie Shopee nào trong [{p_id}] {p_name}")
                continue
                
            formatted = format_cookies(cookies_list, target_domain=target_domain, clean_mode=not args.full_cookies)
            if not formatted:
                print(f"⚠️ Không tìm thấy cookie khớp tên miền Shopee trong [{p_id}] {p_name}")
                continue
                
            # Lưu các cookie tìm được vào file
            for domain, (cookie_str, logged_in) in formatted.items():
                if is_txt:
                    txt_file.write(f"{p_name}|{cookie_str}\n")
                    print(f"   ✅ Đã lấy cookie [{domain}] -> Dạng text ({p_name}|...)")
                else:
                    login_status = "Logged In" if logged_in else "Not Logged In"
                    csv_writer.writerow([
                        p_id,
                        p_name,
                        domain,
                        login_status,
                        cookie_str,
                        ua or "",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ])
                    print(f"   ✅ Đã lấy cookie [{domain}] [{login_status}]")
                
            success_count += 1
            if is_txt:
                txt_file.flush()
            else:
                csv_file.flush() # Đẩy dữ liệu xuống đĩa ngay lập tức
            
        # 3. Đóng các profile được mở bởi script (không đóng các profile chạy sẵn)
        for item in opened_in_batch:
            p_id = item['id']
            p_name = item['name']
            if not item['already_running']:
                print(f"<- Đang tự động đóng profile [{p_id}] {p_name}...")
                api_close_profile(p_id)
                time.sleep(0.5)
                
        processed_count += len(batch)
        
    if is_txt:
        txt_file.close()
    else:
        csv_file.close()
    print(f"\n=== Hoàn thành! ===")
    print(f"Đã xử lý: {processed_count} profile.")
    print(f"Thành công trích xuất: {success_count} profile.")
    print(f"Kết quả được lưu tại: {os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
