import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import time
import os
import csv
import json
import sys
import subprocess
import urllib.request
from datetime import datetime

# Import local modules
import get_gemlogin_cookies as extractor

# Reconfigure stdout/stderr to support Unicode
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Constants for Styling
BG_DARK = "#121212"
BG_CARD = "#1e1e1e"
BG_HOVER = "#2a2a2a"
ACCENT_ORANGE = "#ee4d2d"  # Shopee Orange
TEXT_WHITE = "#ffffff"
TEXT_GRAY = "#aaaaaa"
STATUS_READY = "#888888"
STATUS_RUNNING = "#ffaa00"
STATUS_WARNING = "#ff9800"
STATUS_SUCCESS = "#4caf50"
STATUS_ERROR = "#f44336"

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")
VERSION_FILE = os.path.join(ROOT_DIR, "version.txt")
GITHUB_REPO_URL = "https://github.com/thincole/getcookieSP"
GITHUB_RAW_VERSION_URL = "https://raw.githubusercontent.com/thincole/getcookieSP/main/version.txt"

def parse_version_tuple(v_str):
    if not v_str:
        return (0, 0, 0)
    v_str = str(v_str).strip().lstrip('v').split('-')[0]
    parts = []
    for p in v_str.split('.'):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)

def get_current_version():
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass
    return "1.0.2"

def check_remote_version():
    """Lấy phiên bản mới nhất từ GitHub repository"""
    # 1. Thử tải qua raw.githubusercontent.com (nhanh & không bị rate-limit)
    try:
        req = urllib.request.Request(
            GITHUB_RAW_VERSION_URL,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            v = resp.read().decode('utf-8', errors='ignore').strip()
            if v:
                return v
    except Exception:
        pass
        
    # 2. Thử git ls-remote nếu có kết nối git
    try:
        res = subprocess.run(f"git ls-remote --tags {GITHUB_REPO_URL}", shell=True, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            tags = []
            for line in res.stdout.splitlines():
                if 'refs/tags/' in line:
                    t = line.split('refs/tags/')[-1].replace('^{}', '').strip().lstrip('v')
                    tags.append(t)
            if tags:
                tags.sort(key=parse_version_tuple)
                return tags[-1]
    except Exception:
        pass
        
    return None

class ProfileRow:
    def __init__(self, parent, profile, on_change_callback):
        self.profile = profile
        self.id = profile['id']
        self.name = profile['name']
        self.profile_path = profile.get('profile_path', '')
        
        self.frame = tk.Frame(parent, bg=BG_CARD, height=35)
        self.frame.pack(fill=tk.X, pady=1)
        self.frame.pack_propagate(False)
        
        # Checkbox variable
        self.var = tk.BooleanVar(value=False)
        self.cb = tk.Checkbutton(
            self.frame, 
            variable=self.var, 
            bg=BG_CARD, 
            activebackground=BG_CARD,
            selectcolor="#ffffff",
            command=on_change_callback
        )
        self.cb.pack(side=tk.LEFT, padx=10)
        
        # ID label
        self.id_lbl = tk.Label(
            self.frame, 
            text=f"#{self.id}", 
            fg=TEXT_GRAY, 
            bg=BG_CARD, 
            font=("Arial", 10, "bold"),
            width=6,
            anchor="w"
        )
        self.id_lbl.pack(side=tk.LEFT, padx=5)
        
        # Name label
        self.name_lbl = tk.Label(
            self.frame, 
            text=self.name, 
            fg=TEXT_WHITE, 
            bg=BG_CARD, 
            font=("Arial", 10),
            anchor="w"
        )
        self.name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # System running state label (whether it was running before we started)
        self.sys_status = "Đóng"
        self.sys_lbl = tk.Label(
            self.frame,
            text=self.sys_status,
            fg=STATUS_READY,
            bg=BG_DARK,
            font=("Arial", 9),
            padx=6,
            pady=2
        )
        self.sys_lbl.pack(side=tk.RIGHT, padx=10)
        
        # Extract status label
        self.status = "Sẵn sàng"
        self.status_lbl = tk.Label(
            self.frame, 
            text=self.status, 
            fg=STATUS_READY, 
            bg=BG_CARD, 
            font=("Arial", 9, "bold"),
            width=12,
            anchor="center"
        )
        self.status_lbl.pack(side=tk.RIGHT, padx=10)
        
        # Hover effect
        self.frame.bind("<Enter>", lambda e: self.on_hover(True))
        self.frame.bind("<Leave>", lambda e: self.on_hover(False))
        
    def on_hover(self, is_hover):
        color = BG_HOVER if is_hover else BG_CARD
        self.frame.config(bg=color)
        self.cb.config(bg=color, activebackground=color)
        self.id_lbl.config(bg=color)
        self.name_lbl.config(bg=color)
        self.status_lbl.config(bg=color)
        
    def set_status(self, text, color):
        self.status = text
        self.status_lbl.config(text=text, fg=color)
        
    def set_sys_status(self, is_running):
        if is_running:
            self.sys_lbl.config(text="Đang Chạy", fg=STATUS_RUNNING, bg="#332200")
        else:
            self.sys_lbl.config(text="Đóng", fg=STATUS_READY, bg=BG_DARK)

class GemloginCookieGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GemLogin Cookie Extractor - Shopee Edition")
        self.root.geometry("1200x820")
        self.root.minsize(1050, 680)
        self.root.configure(bg=BG_DARK)
        
        self.profiles = []
        self.profile_rows = {}
        self.groups = []  # Danh sách group từ Gemlogin
        self.running_ids_before = set()
        self.is_extracting = False
        self.stop_requested = False
        self.ui_update_queue = queue.Queue()
        
        # Configure overall style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure(".", background=BG_DARK, foreground=TEXT_WHITE)
        self.style.configure("TProgressbar", thickness=15, troughcolor=BG_CARD, background=ACCENT_ORANGE)
        
        self.setup_ui()
        self.load_config()
        self.load_profiles()
        
        # Setup Queue processing loop
        self.root.after(100, self.process_ui_queue)
        
        # Save config when closing window
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Check for updates in background (sau khi UI đã hiển thị 1s)
        self.root.after(1000, lambda: threading.Thread(target=self.check_for_updates_background, daemon=True).start())
        
    def setup_ui(self):
        # Top banner with Shopee branding
        self.banner = tk.Frame(self.root, bg=ACCENT_ORANGE, height=60)
        self.banner.pack(fill=tk.X)
        self.banner.pack_propagate(False)
        
        banner_title = tk.Label(
            self.banner, 
            text="GEMLOGIN COOKIE EXTRACTOR", 
            fg=TEXT_WHITE, 
            bg=ACCENT_ORANGE, 
            font=("Arial", 16, "bold")
        )
        banner_title.pack(side=tk.LEFT, padx=20, pady=15)
        
        # Right container for version and update button
        self.right_banner_frame = tk.Frame(self.banner, bg=ACCENT_ORANGE)
        self.right_banner_frame.pack(side=tk.RIGHT, padx=20, pady=12)
        
        cur_version = get_current_version()
        self.version_lbl = tk.Label(
            self.right_banner_frame, 
            text=f"Phiên bản: v{cur_version}", 
            fg="#ffd2cc", 
            bg=ACCENT_ORANGE, 
            font=("Arial", 10, "bold")
        )
        self.version_lbl.pack(side=tk.LEFT, padx=(0, 10))
        
        self.update_btn = tk.Button(
            self.right_banner_frame,
            text="🔄 Kiểm tra Cập nhật",
            bg="#b73215",
            fg=TEXT_WHITE,
            activebackground="#962810",
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.check_for_updates_interactive
        )
        self.update_btn.pack(side=tk.LEFT)
        
        # Main container with two columns
        self.container = tk.Frame(self.root, bg=BG_DARK)
        self.container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # --- LEFT PANEL: Scrollable Control & Configuration ---
        self.left_container = tk.Frame(self.container, bg=BG_CARD, width=340)
        self.left_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.left_container.pack_propagate(False)

        self.left_canvas = tk.Canvas(self.left_container, bg=BG_CARD, highlightthickness=0, borderwidth=0)
        self.left_scrollbar = ttk.Scrollbar(self.left_container, orient="vertical", command=self.left_canvas.yview)
        
        self.left_panel = tk.Frame(self.left_canvas, bg=BG_CARD, padx=8, pady=8)
        self.left_panel_window = self.left_canvas.create_window((0, 0), window=self.left_panel, anchor="nw", width=320)
        
        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)
        self.left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _update_left_scrollregion(event=None):
            self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        self.left_panel.bind("<Configure>", _update_left_scrollregion)
        self.left_canvas.bind('<Configure>', lambda event: self.left_canvas.itemconfig(self.left_panel_window, width=event.width))

        # 1. Config Section
        config_title = tk.Label(
            self.left_panel, 
            text="CẤU HÌNH BATCH", 
            fg=ACCENT_ORANGE, 
            bg=BG_CARD, 
            font=("Arial", 11, "bold")
        )
        config_title.pack(anchor="w", pady=(0, 6))
        
        # Row 1: Batch Size & Delay
        row_batch_delay = tk.Frame(self.left_panel, bg=BG_CARD)
        row_batch_delay.pack(fill=tk.X, pady=(0, 5))
        
        b_box = tk.Frame(row_batch_delay, bg=BG_CARD)
        b_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Label(b_box, text="Số luồng chạy:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.batch_entry = tk.Entry(b_box, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9), justify="center")
        self.batch_entry.insert(0, "5")
        self.batch_entry.pack(fill=tk.X, ipady=3)
        
        d_box = tk.Frame(row_batch_delay, bg=BG_CARD)
        d_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        tk.Label(d_box, text="Độ trễ (giây):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.delay_entry = tk.Entry(d_box, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9), justify="center")
        self.delay_entry.insert(0, "1")
        self.delay_entry.pack(fill=tk.X, ipady=3)
        
        # Country Selection
        tk.Label(self.left_panel, text="Quốc gia (Thị trường Shopee):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.country_var = tk.StringVar(value="PH (Philippines)")
        self.country_options = [
            "Tất cả (All)",
            "VN (Việt Nam)",
            "PH (Philippines)",
            "MY (Malaysia)",
            "ID (Indonesia)",
            "TH (Thái Lan)",
            "TW (Đài Loan)"
        ]
        self.country_menu = tk.OptionMenu(self.left_panel, self.country_var, *self.country_options)
        self.country_menu.config(
            bg="#2d2d2d", fg=TEXT_WHITE, activebackground=BG_HOVER, activeforeground=TEXT_WHITE,
            highlightthickness=0, borderwidth=0, font=("Arial", 9)
        )
        self.country_menu["menu"].config(bg=BG_CARD, fg=TEXT_WHITE, activebackground=ACCENT_ORANGE, activeforeground=TEXT_WHITE, font=("Arial", 9))
        self.country_menu.pack(fill=tk.X, pady=(1, 5))
        
        # Checkboxes: Mobile UA & Clean Cookie
        cb_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        cb_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.mobile_ua_var = tk.BooleanVar(value=False)
        self.mobile_ua_check = tk.Checkbutton(
            cb_frame,
            text="📱 Giả lập Mobile UA",
            variable=self.mobile_ua_var,
            bg=BG_CARD, fg=TEXT_WHITE, selectcolor="#2d2d2d",
            activebackground=BG_CARD, activeforeground=TEXT_WHITE,
            font=("Arial", 8),
            anchor="w"
        )
        self.mobile_ua_check.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.clean_cookie_var = tk.BooleanVar(value=True)
        self.clean_cookie_check = tk.Checkbutton(
            cb_frame,
            text="✨ Cookie tinh gọn",
            variable=self.clean_cookie_var,
            bg=BG_CARD, fg=TEXT_WHITE, selectcolor="#2d2d2d",
            activebackground=BG_CARD, activeforeground=TEXT_WHITE,
            font=("Arial", 8),
            anchor="w"
        )
        self.clean_cookie_check.pack(side=tk.LEFT, fill=tk.X, expand=True)

        cb_frame2 = tk.Frame(self.left_panel, bg=BG_CARD)
        cb_frame2.pack(fill=tk.X, pady=(2, 6))

        self.no_proxy_var = tk.BooleanVar(value=True)
        self.no_proxy_check = tk.Checkbutton(
            cb_frame2,
            text="⚡ Không fake IP (Dùng IP mạng chính)",
            variable=self.no_proxy_var,
            bg=BG_CARD, fg="#4ade80", selectcolor="#2d2d2d",
            activebackground=BG_CARD, activeforeground="#4ade80",
            font=("Arial", 8, "bold"),
            anchor="w"
        )
        self.no_proxy_check.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Clear site data var
        self.clear_site_data_var = tk.BooleanVar(value=False)
        
        # Output File Path
        tk.Label(self.left_panel, text="File xuất kết quả (TXT/CSV):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        file_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        file_frame.pack(fill=tk.X, pady=(1, 5))
        
        self.output_entry = tk.Entry(file_frame, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9))
        self.output_entry.insert(0, "shopee_cookies.txt")
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        
        browse_btn = tk.Button(
            file_frame, 
            text="...", 
            bg="#3d3d3d", 
            fg=TEXT_WHITE, 
            activebackground=BG_HOVER, 
            activeforeground=TEXT_WHITE, 
            borderwidth=0, 
            padx=8, 
            command=self.browse_output
        )
        browse_btn.pack(side=tk.RIGHT, padx=(4, 0), ipady=2)
        
        # Output TXT Format Selection
        tk.Label(self.left_panel, text="Định dạng dòng xuất (TXT):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.export_format_var = tk.StringVar(value="Profile|Cookie|User|Pass|Proxy (EZAff)")
        self.export_format_combo = ttk.Combobox(
            self.left_panel,
            textvariable=self.export_format_var,
            values=[
                "Profile|Cookie|User|Pass|Proxy (EZAff)",
                "Tên|Cookie",
                "Chỉ Cookie"
            ],
            state="readonly",
            font=("Arial", 9)
        )
        self.export_format_combo.pack(fill=tk.X, pady=(1, 5))
        
        # Extension Path Configuration
        tk.Label(self.left_panel, text="Đường dẫn Extension Cookie:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        ext_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        ext_frame.pack(fill=tk.X, pady=(1, 5))
        
        self.ext_path_entry = tk.Entry(ext_frame, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9))
        default_ext = extractor.EXTENSION_PATH
        if not os.path.exists(default_ext):
            for candidate in [r"E:\reup SP mơi\Cookie Shopee 26.08.2026", r"E:\reup SP moi\Cookie Shopee 26.08.2026", r"E:\Extension shopee af"]:
                if os.path.exists(candidate):
                    default_ext = candidate
                    break
        self.ext_path_entry.insert(0, default_ext)
        self.ext_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        
        ext_browse_btn = tk.Button(
            ext_frame, 
            text="📁 ...", 
            bg="#3a3a3a", 
            fg=TEXT_WHITE, 
            activebackground=BG_HOVER, 
            activeforeground=TEXT_WHITE, 
            borderwidth=0, 
            padx=8, 
            command=self.browse_extension_path
        )
        ext_browse_btn.pack(side=tk.RIGHT, padx=(4, 0), ipady=2)
        
        # Google Sheet Configuration
        tk.Label(self.left_panel, text="Link Google Sheet:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        sheet_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        sheet_frame.pack(fill=tk.X, pady=(1, 5))
        
        self.sheet_url_entry = tk.Entry(sheet_frame, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9))
        self.sheet_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        
        load_sheet_btn = tk.Button(
            sheet_frame, 
            text="📥 Nạp Sheet", 
            bg="#1e5f74", 
            fg=TEXT_WHITE, 
            activebackground="#133b5c", 
            activeforeground=TEXT_WHITE, 
            borderwidth=0, 
            padx=8, 
            command=self.load_google_sheet_accounts
        )
        load_sheet_btn.pack(side=tk.RIGHT, padx=(4, 0), ipady=2)
        
        # Column Setting & Default Pass: User, Profile, Password in 1 compact row
        acc_config_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        acc_config_frame.pack(fill=tk.X, pady=(1, 6))
        
        u_box = tk.Frame(acc_config_frame, bg=BG_CARD)
        u_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        tk.Label(u_box, text="Cột User:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.user_col_entry = tk.Entry(u_box, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9, "bold"), justify="center")
        self.user_col_entry.insert(0, "E")
        self.user_col_entry.pack(fill=tk.X, ipady=2)
        
        p_box = tk.Frame(acc_config_frame, bg=BG_CARD)
        p_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 2))
        tk.Label(p_box, text="Cột Profile:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.profile_col_entry = tk.Entry(p_box, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9, "bold"), justify="center")
        self.profile_col_entry.insert(0, "G")
        self.profile_col_entry.pack(fill=tk.X, ipady=2)
        
        pw_box = tk.Frame(acc_config_frame, bg=BG_CARD)
        pw_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        tk.Label(pw_box, text="Mật khẩu:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.default_pass_entry = tk.Entry(pw_box, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9), justify="center")
        self.default_pass_entry.insert(0, "Khoa01@c")
        self.default_pass_entry.pack(fill=tk.X, ipady=2)
        
        self.account_map = {}
        
        # Divider
        tk.Frame(self.left_panel, bg="#2d2d2d", height=1).pack(fill=tk.X, pady=(6, 6))
        
        # 2. Control Buttons Section
        control_title = tk.Label(
            self.left_panel, 
            text="ĐIỀU KHIỂN CHẠY", 
            fg=ACCENT_ORANGE, 
            bg=BG_CARD, 
            font=("Arial", 11, "bold")
        )
        control_title.pack(anchor="w", pady=(0, 6))
        
        self.start_btn = tk.Button(
            self.left_panel, 
            text="🚀 BẮT ĐẦU TRÍCH XUẤT", 
            bg=ACCENT_ORANGE, 
            fg=TEXT_WHITE, 
            activebackground="#d63d1e", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=7, 
            command=self.on_start_or_stop_click
        )
        self.start_btn.pack(fill=tk.X, pady=2)
        
        self.stop_btn = None
        self.refresh_btn = None
        
        self.install_ext_btn = tk.Button(
            self.left_panel, 
            text="🧩 CÀI EXTENSION VÀO PROFILE ĐÃ CHỌN", 
            bg="#1e5f74", 
            fg=TEXT_WHITE, 
            activebackground="#133b5c", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=6, 
            command=self.install_extension_to_selected
        )
        self.install_ext_btn.pack(fill=tk.X, pady=2)
        
        self.open_with_ext_btn = tk.Button(
            self.left_panel, 
            text="🌐 MỞ PROFILE KÈM EXTENSION COOKIE", 
            bg="#2a5298", 
            fg=TEXT_WHITE, 
            activebackground="#1e3c72", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=6, 
            command=self.open_selected_profiles_with_ext
        )
        self.open_with_ext_btn.pack(fill=tk.X, pady=2)
        
        self.clear_data_btn = tk.Button(
            self.left_panel, 
            text="🧹 XOÁ COOKIE & SITE DATA (SHOPEE.PH)", 
            bg="#802b2b", 
            fg=TEXT_WHITE, 
            activebackground="#5a1d1d", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=6, 
            command=self.clear_site_data_for_selected
        )
        self.clear_data_btn.pack(fill=tk.X, pady=2)
        
        self.auto_fb_login_btn = tk.Button(
            self.left_panel, 
            text="🔑 TỰ ĐỘNG LOGIN FB & LẤY COOKIE", 
            bg="#5e35b1", 
            fg=TEXT_WHITE, 
            activebackground="#4527a0", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=6, 
            command=self.auto_login_fb_and_extract
        )
        self.auto_fb_login_btn.pack(fill=tk.X, pady=2)
        
        # Divider
        tk.Frame(self.left_panel, bg="#2d2d2d", height=1).pack(fill=tk.X, pady=(8, 6))
        
        # Stat Panel
        self.stat_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        self.stat_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.stat_title = tk.Label(
            self.stat_frame, 
            text="THỐNG KÊ", 
            fg=ACCENT_ORANGE, 
            bg=BG_CARD, 
            font=("Arial", 10, "bold")
        )
        self.stat_title.pack(anchor="w")
        
        self.stat_total_lbl = tk.Label(self.stat_frame, text="Tổng số profile: 0", fg=TEXT_WHITE, bg=BG_CARD, font=("Arial", 9), anchor="w")
        self.stat_total_lbl.pack(fill=tk.X, pady=1)
        
        self.stat_selected_lbl = tk.Label(self.stat_frame, text="Đã chọn: 0", fg=TEXT_WHITE, bg=BG_CARD, font=("Arial", 9), anchor="w")
        self.stat_selected_lbl.pack(fill=tk.X, pady=1)
        
        self.stat_running_lbl = tk.Label(self.stat_frame, text="Đang chạy sẵn trên máy: 0", fg=TEXT_WHITE, bg=BG_CARD, font=("Arial", 9), anchor="w")
        self.stat_running_lbl.pack(fill=tk.X, pady=1)
        
        self.progress_lbl = tk.Label(self.stat_frame, text="Tiến độ: 0 / 0", fg=TEXT_WHITE, bg=BG_CARD, font=("Arial", 9, "bold"), anchor="w")
        self.progress_lbl.pack(fill=tk.X, pady=(6, 1))
        
        self.progress_bar = ttk.Progressbar(self.stat_frame, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=2)
        
        # --- RIGHT COLUMN: Profile Selector & Logs ---
        self.right_column = tk.Frame(self.container, bg=BG_DARK)
        self.right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.right_column.rowconfigure(0, weight=5)
        self.right_column.rowconfigure(1, weight=1)
        self.right_column.columnconfigure(0, weight=1)
        
        # Profile list frame
        self.profile_list_frame = tk.LabelFrame(
            self.right_column, 
            text=" Danh sách Profile Gemlogin ", 
            fg=ACCENT_ORANGE, 
            bg=BG_DARK, 
            font=("Arial", 11, "bold"),
            padx=10, 
            pady=10
        )
        self.profile_list_frame.grid(row=0, column=0, sticky="nsew")
        
        # Row 1: Group filter & Search
        filter_row1 = tk.Frame(self.profile_list_frame, bg=BG_DARK)
        filter_row1.pack(fill=tk.X, pady=(0, 5))
        
        # Group filter dropdown
        tk.Label(filter_row1, text="📁 Nhóm:", fg=TEXT_GRAY, bg=BG_DARK, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 5))
        self.group_var = tk.StringVar(value="Tất cả nhóm")
        self.group_menu = tk.OptionMenu(filter_row1, self.group_var, "Tất cả nhóm")
        self.group_menu.config(
            bg=BG_CARD, fg=TEXT_WHITE, activebackground=BG_HOVER, activeforeground=TEXT_WHITE,
            highlightthickness=0, borderwidth=0, font=("Arial", 9), width=18
        )
        self.group_menu["menu"].config(bg=BG_CARD, fg=TEXT_WHITE, activebackground=ACCENT_ORANGE, activeforeground=TEXT_WHITE, font=("Arial", 9))
        self.group_menu.pack(side=tk.LEFT, padx=(0, 15))
        self.group_var.trace_add("write", self.on_filter_change)
        
        # Nút Tải lại profile đặt tại thanh công cụ profile
        self.refresh_btn = tk.Button(
            filter_row1, 
            text="🔄 Tải lại", 
            bg="#2d2d2d", 
            fg=TEXT_WHITE, 
            activebackground=BG_HOVER, 
            activeforeground=TEXT_WHITE, 
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            padx=10, 
            command=lambda: self.load_profiles(is_manual=True)
        )
        self.refresh_btn.pack(side=tk.RIGHT, padx=(6, 0), ipady=2)
        
        # Search Entry
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_filter_change)
        
        tk.Label(filter_row1, text="🔍 Tìm:", fg=TEXT_GRAY, bg=BG_DARK, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = tk.Entry(
            filter_row1, 
            textvariable=self.search_var, 
            bg=BG_CARD, 
            fg=TEXT_WHITE, 
            insertbackground=TEXT_WHITE,
            borderwidth=0, 
            font=("Arial", 10)
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        
        # Row 2: Quick action buttons & Range selection
        filter_row2 = tk.Frame(self.profile_list_frame, bg=BG_DARK)
        filter_row2.pack(fill=tk.X, pady=(0, 10))
        
        select_all_btn = tk.Button(
            filter_row2, text="Chọn tất cả", bg="#2d2d2d", fg=TEXT_WHITE, 
            borderwidth=0, padx=10, command=self.select_all_profiles
        )
        select_all_btn.pack(side=tk.LEFT, padx=(0, 2), ipady=2)
        
        select_none_btn = tk.Button(
            filter_row2, text="Bỏ chọn", bg="#2d2d2d", fg=TEXT_WHITE, 
            borderwidth=0, padx=10, command=self.select_none_profiles
        )
        select_none_btn.pack(side=tk.LEFT, padx=2, ipady=2)
        
        select_running_btn = tk.Button(
            filter_row2, text="Chọn Đang Chạy", bg="#2d2d2d", fg=TEXT_WHITE, 
            borderwidth=0, padx=10, command=self.select_running_profiles
        )
        select_running_btn.pack(side=tk.LEFT, padx=2, ipady=2)
        
        # Range Selection: Từ ... Đến ...
        tk.Label(filter_row2, text="│", fg="#444444", bg=BG_DARK).pack(side=tk.LEFT, padx=6)
        tk.Label(filter_row2, text="Từ:", fg=TEXT_GRAY, bg=BG_DARK, font=("Arial", 9)).pack(side=tk.LEFT, padx=(2, 2))
        self.range_from_entry = tk.Entry(
            filter_row2, bg=BG_CARD, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9), width=5, justify="center"
        )
        self.range_from_entry.pack(side=tk.LEFT, padx=2, ipady=2)
        self.range_from_entry.bind("<Return>", lambda e: self.select_range_profiles())
        
        tk.Label(filter_row2, text="Đến:", fg=TEXT_GRAY, bg=BG_DARK, font=("Arial", 9)).pack(side=tk.LEFT, padx=(4, 2))
        self.range_to_entry = tk.Entry(
            filter_row2, bg=BG_CARD, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9), width=5, justify="center"
        )
        self.range_to_entry.pack(side=tk.LEFT, padx=2, ipady=2)
        self.range_to_entry.bind("<Return>", lambda e: self.select_range_profiles())
        
        select_range_btn = tk.Button(
            filter_row2, text="Chọn từ đến", bg="#2d2d2d", fg=TEXT_WHITE, activebackground=BG_HOVER, activeforeground=TEXT_WHITE,
            borderwidth=0, padx=10, command=self.select_range_profiles
        )
        select_range_btn.pack(side=tk.LEFT, padx=(4, 2), ipady=2)
        
        # Scrollable Canvas for profile list
        self.canvas_frame = tk.Frame(self.profile_list_frame, bg=BG_DARK)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg=BG_DARK, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.canvas, bg=BG_DARK)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Configure canvas window width to resize dynamically with the canvas
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfig(self.canvas_window, width=event.width))
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Add mouse wheel support for both left and right panels
        self.left_canvas.bind("<Enter>", lambda e: self.root.bind_all("<MouseWheel>", self.on_left_mousewheel))
        self.left_panel.bind("<Enter>", lambda e: self.root.bind_all("<MouseWheel>", self.on_left_mousewheel))
        self.canvas.bind("<Enter>", lambda e: self.root.bind_all("<MouseWheel>", self.on_mousewheel))
        self.scrollable_frame.bind("<Enter>", lambda e: self.root.bind_all("<MouseWheel>", self.on_mousewheel))
        self.root.bind_all("<MouseWheel>", self.on_mousewheel)
        
        # Log frame at the bottom of the right column
        self.log_frame = tk.LabelFrame(
            self.right_column, 
            text=" Tiến trình thực thi / Log chi tiết ", 
            fg=ACCENT_ORANGE, 
            bg=BG_DARK, 
            font=("Arial", 11, "bold"),
            padx=10, 
            pady=10
        )
        self.log_frame.grid(row=1, column=0, sticky="nsew", pady=(15, 0))
        
        self.log_text = tk.Text(
            self.log_frame, 
            bg=BG_DARK, 
            fg="#00ff00",  # Green code-like text
            insertbackground=TEXT_WHITE,
            font=("Courier New", 10),
            borderwidth=0
        )
        self.log_scrollbar = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_scrollbar.pack(side="right", fill="y")
        
        # Make log text read-only
        self.log_text.config(state=tk.DISABLED)
        
    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def on_left_mousewheel(self, event):
        self.left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def browse_output(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Lưu file kết quả cookie"
        )
        if filename:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, filename)
            self.save_config()

    def browse_extension_path(self):
        cur = self.ext_path_entry.get().strip() if hasattr(self, 'ext_path_entry') else r"E:\\"
        initial_dir = cur if os.path.isdir(cur) else os.path.dirname(cur)
        folder = filedialog.askdirectory(
            initialdir=initial_dir if os.path.exists(initial_dir) else r"E:\\",
            title="Chọn thư mục chứa Extension Cookie Shopee (có manifest.json)"
        )
        if folder:
            self.ext_path_entry.delete(0, tk.END)
            self.ext_path_entry.insert(0, os.path.normpath(folder))
            self.save_config()

    def save_config(self):
        """Lưu lại toàn bộ cấu hình cài đặt của người dùng vào file config.json"""
        try:
            config = {
                "batch_size": self.batch_entry.get().strip() if hasattr(self, 'batch_entry') else "5",
                "delay": self.delay_entry.get().strip() if hasattr(self, 'delay_entry') else "1",
                "country": self.country_var.get() if hasattr(self, 'country_var') else "PH (Philippines)",
                "mobile_ua": self.mobile_ua_var.get() if hasattr(self, 'mobile_ua_var') else False,
                "clean_cookie": self.clean_cookie_var.get() if hasattr(self, 'clean_cookie_var') else True,
                "no_proxy": self.no_proxy_var.get() if hasattr(self, 'no_proxy_var') else True,
                "output_file": self.output_entry.get().strip() if hasattr(self, 'output_entry') else "shopee_cookies.txt",
                "export_format": self.export_format_var.get() if hasattr(self, 'export_format_var') else "Tên|Cookie",
                "ext_path": self.ext_path_entry.get().strip() if hasattr(self, 'ext_path_entry') else "",
                "sheet_url": self.sheet_url_entry.get().strip() if hasattr(self, 'sheet_url_entry') else "",
                "user_col": self.user_col_entry.get().strip() if hasattr(self, 'user_col_entry') else "E",
                "profile_col": self.profile_col_entry.get().strip() if hasattr(self, 'profile_col_entry') else "G",
                "default_pass": self.default_pass_entry.get().strip() if hasattr(self, 'default_pass_entry') else "Khoa01@c"
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def load_config(self):
        """Khôi phục lại toàn bộ cấu hình đã cài từ phiên trước trong config.json"""
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            if "batch_size" in config and hasattr(self, 'batch_entry'):
                self.batch_entry.delete(0, tk.END)
                self.batch_entry.insert(0, str(config["batch_size"]))
                
            if "delay" in config and hasattr(self, 'delay_entry'):
                self.delay_entry.delete(0, tk.END)
                self.delay_entry.insert(0, str(config["delay"]))
                
            if "country" in config and hasattr(self, 'country_var'):
                if config["country"] in getattr(self, 'country_options', []):
                    self.country_var.set(config["country"])
                    
            if "mobile_ua" in config and hasattr(self, 'mobile_ua_var'):
                self.mobile_ua_var.set(bool(config["mobile_ua"]))
                
            if "clean_cookie" in config and hasattr(self, 'clean_cookie_var'):
                self.clean_cookie_var.set(bool(config["clean_cookie"]))

            if "no_proxy" in config and hasattr(self, 'no_proxy_var'):
                self.no_proxy_var.set(bool(config["no_proxy"]))
                
            if "output_file" in config and hasattr(self, 'output_entry'):
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, str(config["output_file"]))
                
            if "export_format" in config and hasattr(self, 'export_format_var'):
                self.export_format_var.set(str(config["export_format"]))
                
            if "ext_path" in config and hasattr(self, 'ext_path_entry'):
                self.ext_path_entry.delete(0, tk.END)
                self.ext_path_entry.insert(0, str(config["ext_path"]))
                
            if "sheet_url" in config and hasattr(self, 'sheet_url_entry'):
                self.sheet_url_entry.delete(0, tk.END)
                self.sheet_url_entry.insert(0, str(config["sheet_url"]))
                
            if "user_col" in config and hasattr(self, 'user_col_entry'):
                self.user_col_entry.delete(0, tk.END)
                self.user_col_entry.insert(0, str(config["user_col"]))
                
            if "profile_col" in config and hasattr(self, 'profile_col_entry'):
                self.profile_col_entry.delete(0, tk.END)
                self.profile_col_entry.insert(0, str(config["profile_col"]))
                
            if "default_pass" in config and hasattr(self, 'default_pass_entry'):
                self.default_pass_entry.delete(0, tk.END)
                self.default_pass_entry.insert(0, str(config["default_pass"]))
                
        except Exception as e:
            print(f"Error loading config: {e}")

    def on_closing(self):
        """Lưu cấu hình khi đóng phần mềm"""
        self.save_config()
        self.root.destroy()

    def check_for_updates_background(self):
        """Kiểm tra phiên bản mới từ GitHub trong tiến trình ngầm khi mở app"""
        try:
            remote_ver = check_remote_version()
            if not remote_ver:
                return
            cur_ver = get_current_version()
            if parse_version_tuple(remote_ver) > parse_version_tuple(cur_ver):
                self.new_version_available = remote_ver
                self.ui_update_queue.put(('update_available', remote_ver))
        except Exception:
            pass

    def check_for_updates_interactive(self):
        """Bấm nút Kiểm tra Cập nhật / Tải bản cập nhật mới"""
        cur_ver = get_current_version()
        remote_ver = getattr(self, 'new_version_available', None)
        
        if not remote_ver:
            self.update_btn.config(text="⏳ Đang kiểm tra...")
            self.root.update_idletasks()
            remote_ver = check_remote_version()
            self.update_btn.config(text="🔄 Kiểm tra Cập nhật")
            
        if not remote_ver:
            messagebox.showinfo(
                "Kiểm tra cập nhật",
                "Không thể kết nối đến GitHub để kiểm tra phiên bản mới.\nVui lòng kiểm tra lại kết nối mạng."
            )
            return
            
        if parse_version_tuple(remote_ver) > parse_version_tuple(cur_ver):
            self.new_version_available = remote_ver
            self.update_btn.config(
                text=f"🔥 Có bản mới v{remote_ver}! Bấm Cập nhật",
                bg="#28a745",
                activebackground="#218838"
            )
            confirm = messagebox.askyesno(
                "Phát hiện bản cập nhật mới",
                f"🎉 Đã có phiên bản mới: v{remote_ver} trên GitHub!\n"
                f"Phiên bản hiện tại của bạn: v{cur_ver}\n\n"
                f"Bạn có muốn tự động tải và cập nhật lên v{remote_ver} ngay bây giờ không?"
            )
            if confirm:
                self.perform_auto_update(remote_ver)
        else:
            messagebox.showinfo(
                "Kiểm tra cập nhật",
                f"Bạn đang sử dụng phiên bản mới nhất (v{cur_ver})!\nKhông có bản cập nhật nào mới hơn trên GitHub."
            )

    def perform_auto_update(self, new_ver):
        """Tự động kéo mã nguồn mới nhất từ GitHub và khởi động lại app"""
        self.save_config()
        self.log(f"🚀 Đang tiến hành cập nhật lên phiên bản v{new_ver} từ GitHub...")
        
        # 1. Sao lưu nội dung config.json hiện tại của người dùng
        cfg_backup = None
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg_backup = f.read()
            except Exception:
                pass
                
        # 2. Chạy lệnh git fetch và pull
        try:
            subprocess.run("git fetch origin main", shell=True, capture_output=True, text=True, cwd=ROOT_DIR)
            pull_res = subprocess.run("git pull origin main", shell=True, capture_output=True, text=True, cwd=ROOT_DIR)
            
            if pull_res.returncode != 0:
                # Nếu có xung đột working directory, thử reset về origin/main
                subprocess.run("git reset --hard origin/main", shell=True, capture_output=True, text=True, cwd=ROOT_DIR)
                
            # Khôi phục lại config.json người dùng đã cài đặt
            if cfg_backup and os.path.exists(CONFIG_PATH):
                try:
                    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                        f.write(cfg_backup)
                except Exception:
                    pass
                    
            self.log(f"✅ Đã cập nhật thành công lên phiên bản v{new_ver}!")
            restart = messagebox.askyesno(
                "Cập nhật thành công",
                f"Đã nâng cấp thành công lên phiên bản v{new_ver}!\n\n"
                f"Bạn có muốn khởi động lại phần mềm ngay bây giờ để áp dụng phiên bản mới không?"
            )
            if restart:
                python_exe = sys.executable
                subprocess.Popen([python_exe, os.path.join(ROOT_DIR, "gui.py")])
                self.root.destroy()
            else:
                self.version_lbl.config(text=f"Phiên bản: v{new_ver}")
                self.update_btn.config(text="🔄 Kiểm tra Cập nhật", bg="#b73215", activebackground="#962810")
                self.new_version_available = None
                
        except Exception as e:
            self.log(f"❌ Lỗi trong quá trình cập nhật: {e}")
            messagebox.showerror(
                "Lỗi cập nhật", 
                f"Không thể tự động cập nhật: {e}\n\nBạn có thể tải bản mới nhất tại:\n{GITHUB_REPO_URL}"
            )
            
    def on_filter_change(self, *args):
        search_query = self.search_var.get().lower().strip()
        selected_group = self.group_var.get()
        
        # Scroll back to top when filtering
        self.canvas.yview_moveto(0)
        
        for p_id, row in self.profile_rows.items():
            # Lọc theo nhóm
            group_match = True
            if selected_group == "Tất cả nhóm":
                group_match = True
            elif selected_group == "Không có nhóm":
                group_match = (row.profile.get('group_id', 'noGroup') == 'noGroup')
            else:
                # Tìm group_id từ tên group
                group_match = False
                for g in self.groups:
                    if g['name'] == selected_group and str(row.profile.get('group_id', '')) == str(g['id']):
                        group_match = True
                        break
            
            # Lọc theo từ khóa tìm kiếm
            search_match = True
            if search_query:
                search_match = (search_query in str(p_id) or search_query in row.name.lower())
            
            if group_match and search_match:
                row.frame.pack(fill=tk.X, pady=1)
            else:
                row.frame.pack_forget()
                
    def select_all_profiles(self):
        for row in self.profile_rows.values():
            if row.frame.winfo_ismapped(): # Only select visible ones
                row.var.set(True)
        self.update_stats()
        
    def select_none_profiles(self):
        for row in self.profile_rows.values():
            row.var.set(False)
        self.update_stats()
        
    def select_running_profiles(self):
        for p_id, row in self.profile_rows.items():
            if p_id in self.running_ids_before:
                row.var.set(True)
            else:
                row.var.set(False)
        self.update_stats()
        
    def select_range_profiles(self):
        from_str = self.range_from_entry.get().strip()
        to_str = self.range_to_entry.get().strip()
        
        if not from_str or not to_str:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập giá trị 'Từ' và 'Đến' (theo số thứ tự hoặc ID profile).")
            return
            
        try:
            from_val = int(from_str)
            to_val = int(to_str)
        except ValueError:
            messagebox.showerror("Lỗi", "Giá trị 'Từ' và 'Đến' phải là số nguyên.")
            return
            
        if from_val > to_val:
            from_val, to_val = to_val, from_val
            
        visible_rows = [row for row in self.profile_rows.values() if row.frame.winfo_ismapped()]
        if not visible_rows:
            return
            
        # Kiểm tra xem người dùng nhập khoảng theo ID profile (ví dụ 161 đến 170) hay theo STT (ví dụ 1 đến 20)
        all_visible_ids = [row.id for row in visible_rows if isinstance(row.id, int) or (isinstance(row.id, str) and row.id.isdigit())]
        int_ids = [int(x) for x in all_visible_ids]
        
        matched_by_id = False
        if int_ids and max(int_ids) >= from_val >= min(int_ids):
            for row in visible_rows:
                try:
                    rid = int(row.id)
                    if from_val <= rid <= to_val:
                        row.var.set(True)
                        matched_by_id = True
                    else:
                        row.var.set(False)
                except ValueError:
                    pass
                    
        # Nếu không khớp theo ID (hoặc người dùng chọn theo STT thứ 1 đến thứ N trong danh sách hiển thị)
        if not matched_by_id:
            for idx, row in enumerate(visible_rows, start=1):
                if from_val <= idx <= to_val:
                    row.var.set(True)
                else:
                    row.var.set(False)
                    
        self.update_stats()
        
    def update_stats(self):
        total = len(self.profiles)
        selected = sum(1 for row in self.profile_rows.values() if row.var.get())
        running = len(self.running_ids_before)
        
        self.stat_total_lbl.config(text=f"Tổng số profile: {total}")
        self.stat_selected_lbl.config(text=f"Đã chọn: {selected}")
        self.stat_running_lbl.config(text=f"Đang chạy sẵn trên máy: {running}")
        
    def load_profiles(self, is_manual=False):
        # Đổi trạng thái nút làm mới sang đang tải
        if hasattr(self, 'refresh_btn') and self.refresh_btn:
            self.refresh_btn.config(state=tk.DISABLED, text="⏳ Đang tải...")
        
        # Xóa danh sách profile cũ trên giao diện
        for row in self.profile_rows.values():
            row.frame.destroy()
        self.profile_rows.clear()
        self.profiles = []
        self.update_stats()

        def _worker():
            try:
                # 1. Tự động kiểm tra Gemlogin đã chạy chưa (chưa chạy thì tự mở, chạy rồi thì bỏ qua)
                extractor.ensure_gemlogin_running(logger_callback=self.log)
                
                self.log("Đang tải danh sách profile từ API cục bộ Gemlogin (127.0.0.1:1010)...")
                
                # Get groups from API (thử lại tối đa 3 lần)
                groups = []
                for _ in range(3):
                    try:
                        import urllib.request
                        req = urllib.request.Request(f"{extractor.GEMLOGIN_API}/api/groups", headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=5) as response:
                            res = json.loads(response.read().decode('utf-8'))
                            if res.get('success'):
                                groups = res.get('data', [])
                                break
                    except Exception:
                        time.sleep(1)
                
                # Get profiles from API với tự động retry (4 lần, cách nhau 2 giây)
                profiles = extractor.api_get_profiles(
                    retries=4, 
                    delay=2.0, 
                    logger_callback=self.log
                )
                
                running_ids = set()
                if profiles:
                    self.log(f"Tải thành công {len(profiles)} profile.")
                    self.log("Đang kiểm tra các profile đang mở sẵn trên máy...")
                    running_ids = extractor.get_running_profiles()
                    self.log(f"Phát hiện {len(running_ids)} profile đang mở sẵn.")
                else:
                    self.log("⚠️ Không thể kết nối tới Gemlogin API cục bộ trên cổng 1010.")
                    self.log("💡 Vui lòng đảm bảo phần mềm Gemlogin đang mở và bấm nút '🔄 Tải lại' để thử lại.")
                
                # Cập nhật kết quả lên giao diện chính
                self.root.after(0, lambda: self._on_profiles_loaded(profiles, groups, running_ids, is_manual))
            except Exception as e:
                self.log(f"❌ Lỗi nạp profile: {e}")
                self.root.after(0, lambda: self._on_profiles_loaded([], [], set(), is_manual))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_profiles_loaded(self, profiles, groups, running_ids, is_manual):
        if hasattr(self, 'refresh_btn') and self.refresh_btn:
            self.refresh_btn.config(state=tk.NORMAL, text="🔄 Tải lại")
        self.groups = groups
        self.profiles = profiles
        self.running_ids_before = running_ids
        
        # Update group dropdown
        menu = self.group_menu["menu"]
        menu.delete(0, "end")
        group_options = ["Tất cả nhóm", "Không có nhóm"]
        for g in self.groups:
            group_options.append(g['name'])
        for opt in group_options:
            menu.add_command(label=opt, command=lambda v=opt: self.group_var.set(v))
        self.group_var.set("Tất cả nhóm")
        if self.groups:
            self.log(f"Tìm thấy {len(self.groups)} nhóm: {', '.join(g['name'] for g in self.groups)}")
        
        if not self.profiles:
            if is_manual:
                messagebox.showerror("Lỗi", "Không thể kết nối tới Gemlogin API cục bộ trên cổng 1010. Vui lòng mở phần mềm Gemlogin và thử lại.")
            self.update_stats()
            return
            
        # Create row widgets in UI
        for p in self.profiles:
            p_id = p['id']
            row = ProfileRow(self.scrollable_frame, p, self.update_stats)
            self.profile_rows[p_id] = row
            
            # Check running state
            is_running = p_id in self.running_ids_before
            row.set_sys_status(is_running)
            
        self.update_stats()
        
    def log(self, message):
        """Thread-safe logging helper"""
        self.ui_update_queue.put(('log', message))
        
    def write_log_to_widget(self, message):
        time_str = datetime.now().strftime("[%H:%M:%S] ")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{time_str}{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def process_ui_queue(self):
        try:
            while True:
                msg_type, data = self.ui_update_queue.get_nowait()
                if msg_type == 'log':
                    self.write_log_to_widget(data)
                elif msg_type == 'progress':
                    current, total = data
                    self.progress_lbl.config(text=f"Tiến độ: {current} / {total}")
                    self.progress_bar.config(maximum=total, value=current)
                elif msg_type == 'status':
                    p_id, text, color = data
                    if p_id in self.profile_rows:
                        self.profile_rows[p_id].set_status(text, color)
                elif msg_type == 'finished':
                    self.on_extraction_finished(data)
                elif msg_type == 'update_available':
                    new_ver = data
                    self.new_version_available = new_ver
                    self.update_btn.config(
                        text=f"🔥 Có bản mới v{new_ver}! Bấm Cập nhật",
                        bg="#28a745",
                        activebackground="#218838"
                    )
                    self.write_log_to_widget(f"📢 [CẬP NHẬT] Đã có phiên bản mới: v{new_ver} trên GitHub (Bản hiện tại: v{get_current_version()}).")
                    self.write_log_to_widget(f"   👉 Hãy nhấp nút '🔥 Có bản mới v{new_ver}!' trên góc phải tiêu đề để cập nhật.")
        except queue.Empty:
            pass
        self.root.after(100, self.process_ui_queue)
        
    def on_start_or_stop_click(self):
        if self.is_extracting:
            self.stop_extraction()
        else:
            self.start_extraction()

    def start_extraction(self):
        if self.is_extracting:
            return
            
        selected_ids = [p_id for p_id, row in self.profile_rows.items() if row.var.get()]
        if not selected_ids:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 profile để lấy cookie.")
            return
            
        # Get and validate config values
        try:
            batch_size = int(self.batch_entry.get())
            if batch_size <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Lỗi", "Số luồng chạy đồng thời (Batch Size) phải là số nguyên lớn hơn 0.")
            return
            
        try:
            delay = float(self.delay_entry.get())
            if delay < 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Lỗi", "Độ trễ phải là số lớn hơn hoặc bằng 0.")
            return
            
        output_file = self.output_entry.get().strip()
        if not output_file:
            messagebox.showerror("Lỗi", "Vui lòng chọn hoặc nhập tên file kết quả.")
            return
            
        self.save_config()
            
        # Reset statuses of selected rows
        for p_id in selected_ids:
            self.profile_rows[p_id].set_status("Sẵn sàng", STATUS_READY)
            
        # Update UI state
        self.is_extracting = True
        self.stop_requested = False
        self.start_btn.config(state=tk.NORMAL, text="🛑 DỪNG TIẾN TRÌNH", bg="#c0392b", activebackground="#962d22")
        if hasattr(self, 'auto_fb_login_btn') and self.auto_fb_login_btn:
            self.auto_fb_login_btn.config(state=tk.DISABLED)
        if self.stop_btn:
            self.stop_btn.config(state=tk.NORMAL)
        if hasattr(self, 'refresh_btn') and self.refresh_btn:
            self.refresh_btn.config(state=tk.DISABLED)
        self.search_entry.config(state=tk.DISABLED)
        
        # Clear log screen for clean run
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # Update progress UI
        self.progress_lbl.config(text=f"Tiến độ: 0 / {len(selected_ids)}")
        self.progress_bar.config(maximum=len(selected_ids), value=0)
        
        # Map country selection to domain
        country_domain_map = {
            "Tất cả (All)": None,
            "VN (Việt Nam)": "shopee.vn",
            "PH (Philippines)": "shopee.ph",
            "MY (Malaysia)": "shopee.com.my",
            "ID (Indonesia)": "shopee.co.id",
            "TH (Thái Lan)": "shopee.co.th",
            "TW (Đài Loan)": "shopee.tw"
        }
        target_domain = country_domain_map.get(self.country_var.get())
        mobile_ua = self.mobile_ua_var.get()
        clean_cookie = self.clean_cookie_var.get()

        # Start background extraction thread
        t = threading.Thread(
            target=self.run_extraction_thread, 
            args=(selected_ids, batch_size, delay, output_file, target_domain, mobile_ua, clean_cookie),
            daemon=True
        )
        t.start()
        
    def stop_extraction(self):
        if not self.is_extracting or self.stop_requested:
            return
            
        self.stop_requested = True
        self.log("🛑 Đang gửi yêu cầu dừng tiến trình... vui lòng đợi hoàn thành đợt hiện tại.")
        self.start_btn.config(state=tk.DISABLED, text="⏳ Đang dừng...")
        if self.stop_btn:
            self.stop_btn.config(state=tk.DISABLED, text="⏳ Đang dừng...")
        
    def install_extension_to_selected(self):
        """Cài đặt và ghim Extension Cookie Shopee vào tất cả profile đang được tích chọn"""
        selected_ids = [p_id for p_id, row in self.profile_rows.items() if row.var.get()]
        if not selected_ids:
            messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 profile để cài extension.")
            return
            
        ext_path = self.ext_path_entry.get().strip() if hasattr(self, 'ext_path_entry') else extractor.EXTENSION_PATH
        if not ext_path or not os.path.exists(ext_path):
            messagebox.showerror("Lỗi", f"Không tìm thấy thư mục extension tại:\n{ext_path}\n\nVui lòng kiểm tra lại ô 'Đường dẫn Extension Cookie' ở khung Cấu hình bên trái hoặc bấm nút [📁 ...] để chọn lại thư mục.")
            return
            
        confirm = messagebox.askyesno(
            "Xác nhận cài Extension", 
            f"Bạn có chắc muốn cài đặt & ghim Extension Cookie Shopee vào {len(selected_ids)} profile đã chọn không?\n\nThư mục nguồn:\n{ext_path}"
        )
        if not confirm:
            return
            
        threading.Thread(
            target=self.run_install_extension_thread, 
            args=(selected_ids, ext_path), 
            daemon=True
        ).start()

    def run_install_extension_thread(self, selected_ids, ext_path):
        self.log(f"=== Bắt đầu cài đặt Extension Cookie Shopee cho {len(selected_ids)} profile ===")
        self.log(f"Thư mục Extension: {ext_path}")
        success_count = 0
        error_count = 0
        
        p_lookup = {p['id']: p for p in self.profiles}
        
        for idx, p_id in enumerate(selected_ids, start=1):
            p_info = p_lookup.get(p_id)
            p_name = p_info.get('name', f'Profile #{p_id}') if p_info else f'Profile #{p_id}'
            p_path = p_info.get('profile_path') if p_info else None
            
            if not p_path:
                p_path = f"F:\\gemlogin\\profiles\\{p_id}"
                
            ok, msg = extractor.install_extension_to_profile(p_path, ext_path)
            if ok:
                success_count += 1
                self.log(f"[{idx}/{len(selected_ids)}] ✅ [{p_id}] {p_name}: Đã cài đặt & ghim Extension thành công")
                self.ui_update_queue.put(('status', (p_id, "Đã cài Ext", STATUS_READY)))
            else:
                error_count += 1
                self.log(f"[{idx}/{len(selected_ids)}] ❌ [{p_id}] {p_name}: Lỗi cài đặt ({msg})")
                self.ui_update_queue.put(('status', (p_id, "Lỗi cài Ext", STATUS_ERROR)))
                
        self.log(f"=== Hoàn tất: Cài thành công {success_count}/{len(selected_ids)} profile (Lỗi: {error_count}) ===")
        messagebox.showinfo(
            "Hoàn tất cài đặt", 
            f"Đã cài đặt Extension thành công cho {success_count}/{len(selected_ids)} profile!\n\nKhi mở trình duyệt trên Gemlogin, Extension Cookie Shopee sẽ tự động xuất hiện và được ghim sẵn trên thanh công cụ."
        )

    def open_selected_profiles_with_ext(self):
        """Mở các profile đang chọn kèm cờ --load-extension để Extension xuất hiện 100% trên thanh công cụ"""
        selected_ids = [p_id for p_id, row in self.profile_rows.items() if row.var.get()]
        if not selected_ids:
            messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 profile để mở.")
            return
            
        ext_path = self.ext_path_entry.get().strip() if hasattr(self, 'ext_path_entry') else extractor.EXTENSION_PATH
        if not ext_path or not os.path.exists(ext_path):
            messagebox.showerror("Lỗi", f"Không tìm thấy thư mục extension tại:\n{ext_path}\n\nVui lòng kiểm tra lại ô 'Đường dẫn Extension Cookie' ở khung Cấu hình bên trái hoặc bấm nút [📁 ...] để chọn lại thư mục.")
            return
            
        country_domain_map = {
            "Tất cả (All)": "shopee.ph",
            "VN (Việt Nam)": "shopee.vn",
            "PH (Philippines)": "shopee.ph",
            "MY (Malaysia)": "shopee.com.my",
            "ID (Indonesia)": "shopee.co.id",
            "TH (Thái Lan)": "shopee.co.th",
            "TW (Đài Loan)": "shopee.tw"
        }
        target_domain = country_domain_map.get(self.country_var.get(), "shopee.ph")
        clear_data = self.clear_site_data_var.get()
        if clear_data:
            self.log(f"🧹 Tuỳ chọn 'Xoá cookie & Site Data Shopee' đang BẬT: Đang dọn sạch data ({target_domain}) trước khi mở trình duyệt...")
            
        no_proxy = self.no_proxy_var.get() if hasattr(self, 'no_proxy_var') else True
        p_lookup = {p['id']: p for p in self.profiles}
        for p_id in selected_ids:
            p_info = p_lookup.get(p_id)
            p_name = p_info.get('name', f'Profile #{p_id}') if p_info else f'Profile #{p_id}'
            p_path = p_info.get('profile_path') if p_info else f"F:\\gemlogin\\profiles\\{p_id}"
            if not p_path or not os.path.exists(p_path):
                p_path = f"F:\\gemlogin\\profiles\\{p_id}"
            b_ver = p_info.get('browser_version', 140) if p_info else 140
            p_proxy = extractor.extract_profile_proxy(p_info) if not no_proxy else None
            
            ok, msg = extractor.open_profile_with_extension(
                p_path, 
                browser_version=b_ver, 
                ext_path=ext_path, 
                clear_site_data=clear_data, 
                domain=target_domain,
                no_proxy=no_proxy,
                proxy=p_proxy
            )
            if ok:
                self.log(f"🌐 [{p_id}] {p_name}: {msg}")
                self.ui_update_queue.put(('status', (p_id, "Đang mở", STATUS_RUNNING)))
            else:
                self.log(f"❌ [{p_id}] {p_name}: {msg}")
                self.ui_update_queue.put(('status', (p_id, "Lỗi mở", STATUS_ERROR)))

    def clear_site_data_for_selected(self):
        """Xoá sạch Cookie và toàn bộ Site Data (IndexedDB, LocalStorage, Cache) của Shopee cho các profile được chọn"""
        selected_ids = [p_id for p_id, row in self.profile_rows.items() if row.var.get()]
        if not selected_ids:
            messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 profile để xoá dữ liệu.")
            return
            
        country_domain_map = {
            "Tất cả (All)": "shopee.ph",
            "VN (Việt Nam)": "shopee.vn",
            "PH (Philippines)": "shopee.ph",
            "MY (Malaysia)": "shopee.com.my",
            "ID (Indonesia)": "shopee.co.id",
            "TH (Thái Lan)": "shopee.co.th",
            "TW (Đài Loan)": "shopee.tw"
        }
        target_domain = country_domain_map.get(self.country_var.get(), "shopee.ph")
        
        confirm = messagebox.askyesno(
            "Xác nhận xoá Cookie & Site Data", 
            f"Bạn có chắc muốn xoá toàn bộ Cookie và Site Data (IndexedDB, Cache, LocalStorage) của {target_domain} cho {len(selected_ids)} profile đã chọn không?\n\nSau khi xoá, profile sẽ ở trạng thái trắng để đăng nhập lại từ đầu."
        )
        if not confirm:
            return
            
        threading.Thread(
            target=self.run_clear_site_data_thread, 
            args=(selected_ids, target_domain), 
            daemon=True
        ).start()

    def run_clear_site_data_thread(self, selected_ids, target_domain):
        self.log(f"=== Bắt đầu xoá Cookie & Site Data ({target_domain}) cho {len(selected_ids)} profile ===")
        success_count = 0
        error_count = 0
        
        p_lookup = {p['id']: p for p in self.profiles}
        for idx, p_id in enumerate(selected_ids, start=1):
            p_info = p_lookup.get(p_id)
            p_name = p_info.get('name', f'Profile #{p_id}') if p_info else f'Profile #{p_id}'
            p_path = p_info.get('profile_path') if p_info else f"F:\\gemlogin\\profiles\\{p_id}"
            if not p_path or not os.path.exists(p_path):
                p_path = f"F:\\gemlogin\\profiles\\{p_id}"
            
            ok, msg = extractor.clear_shopee_site_data(p_path, domain=target_domain)
            if ok:
                success_count += 1
                self.log(f"[{idx}/{len(selected_ids)}] 🧹 [{p_id}] {p_name}: {msg}")
                self.ui_update_queue.put(('status', (p_id, "Đã xoá Data", STATUS_READY)))
            else:
                error_count += 1
                self.log(f"[{idx}/{len(selected_ids)}] ❌ [{p_id}] {p_name}: {msg}")
                self.ui_update_queue.put(('status', (p_id, "Lỗi xoá Data", STATUS_ERROR)))
                
        self.log(f"=== Hoàn tất: Xoá Site Data thành công cho {success_count}/{len(selected_ids)} profile ===")
        messagebox.showinfo(
            "Hoàn tất xoá dữ liệu", 
            f"Đã xoá Cookie & Site Data thành công cho {success_count}/{len(selected_ids)} profile!\n\nBây giờ bạn có thể mở profile và đăng nhập lại từ đầu."
        )

    def load_google_sheet_accounts(self):
        """Nạp danh sách tài khoản từ link Google Sheet theo cột User & Profile cấu hình"""
        url = self.sheet_url_entry.get().strip()
        if not url:
            messagebox.showwarning("Cảnh báo", "Vui lòng dán Link Google Sheet trước khi nạp.")
            return
            
        user_col = self.user_col_entry.get().strip() if hasattr(self, 'user_col_entry') else "E"
        profile_col = self.profile_col_entry.get().strip() if hasattr(self, 'profile_col_entry') else "G"
        
        self.log(f"📥 Đang tải danh sách tài khoản từ Google Sheet (Cột {user_col.upper()}: User, Cột {profile_col.upper()}: Profile)...")
        accs, msg = extractor.fetch_accounts_from_google_sheet(url, user_col=user_col, profile_col=profile_col)
        self.account_map = accs
        self.save_config()
        self.log(f"ℹ️ {msg}")
        if accs:
            messagebox.showinfo("Thành công", msg)
        else:
            messagebox.showerror("Lỗi", msg)

    def auto_login_fb_and_extract(self):
        """Tự động mở từng profile, bấm Login with Facebook, bấm Continue (hoặc Fallback tài khoản Google Sheet) và trích xuất Cookie sạch chuẩn MLS"""
        if self.is_extracting:
            messagebox.showwarning("Cảnh báo", "Một tiến trình khác đang chạy. Vui lòng đợi hoặc dừng lại trước.")
            return
            
        selected_ids = [p_id for p_id, row in self.profile_rows.items() if row.var.get()]
        if not selected_ids:
            messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 profile để thực hiện.")
            return
            
        self.save_config()
            
        country_domain_map = {
            "Tất cả (All)": "shopee.ph",
            "VN (Việt Nam)": "shopee.vn",
            "PH (Philippines)": "shopee.ph",
            "MY (Malaysia)": "shopee.com.my",
            "ID (Indonesia)": "shopee.co.id",
            "TH (Thái Lan)": "shopee.co.th",
            "TW (Đài Loan)": "shopee.tw"
        }
        target_domain = country_domain_map.get(self.country_var.get(), "shopee.ph")
        output_file = self.output_entry.get().strip() or "shopee_cookies.txt"
        clean_cookie = self.clean_cookie_var.get()
        no_proxy = self.no_proxy_var.get() if hasattr(self, 'no_proxy_var') else True
        
        try:
            batch_size = int(self.batch_entry.get().strip())
            if batch_size <= 0:
                batch_size = 1
        except ValueError:
            batch_size = 3

        try:
            delay = int(self.delay_entry.get().strip())
            if delay < 0:
                delay = 1
        except ValueError:
            delay = 1
            
        net_mode_confirm = "⚡ Dùng IP mạng chính (Không fake IP)" if no_proxy else "🌐 Dùng Proxy của Profile"
        confirm = messagebox.askyesno(
            "Xác nhận Tự động Đăng nhập Đa Luồng",
            f"Bạn có chắc muốn tự động Đăng nhập (FB / Google Sheet) & Lấy Cookie cho {len(selected_ids)} profile đã chọn không?\n\nSố luồng chạy đồng thời: {batch_size}\nĐộ trễ giãn cách: {delay} giây\nChế độ mạng: {net_mode_confirm}\nDomain: {target_domain}\nFile lưu: {output_file}"
        )
        if not confirm:
            return
            
        self.is_extracting = True
        self.stop_requested = False
        self.start_btn.config(state=tk.NORMAL, text="🛑 DỪNG TIẾN TRÌNH", bg="#c0392b", activebackground="#962d22")
        if hasattr(self, 'auto_fb_login_btn') and self.auto_fb_login_btn:
            self.auto_fb_login_btn.config(state=tk.DISABLED)
        if self.stop_btn:
            self.stop_btn.config(state=tk.NORMAL)
        if hasattr(self, 'refresh_btn') and self.refresh_btn:
            self.refresh_btn.config(state=tk.DISABLED)
        self.progress_lbl.config(text=f"Tiến độ: 0 / {len(selected_ids)}")
        self.progress_bar.config(maximum=len(selected_ids), value=0)
        
        threading.Thread(
            target=self.run_auto_fb_login_thread, 
            args=(selected_ids, target_domain, output_file, clean_cookie, batch_size, delay, no_proxy), 
            daemon=True
        ).start()

    def run_auto_fb_login_thread(self, selected_ids, target_domain, output_file, clean_cookie, batch_size=3, delay=1, no_proxy=True):
        net_mode_label = "⚡ Không fake IP (Dùng IP mạng chính)" if no_proxy else "🌐 Dùng Proxy của Profile"
        self.log(f"=== Bắt đầu Tự động Đăng nhập ĐA LUỒNG cho {len(selected_ids)} profile (Số luồng: {batch_size} | Độ trễ: {delay}s | Mạng: {net_mode_label}) ===")
        self.log(f"Thị trường: {target_domain} | File lưu: {os.path.abspath(output_file)}")
        
        # Tự động nạp Google Sheet nếu có link nhưng chưa bấm nút Nạp
        sheet_url = self.sheet_url_entry.get().strip() if hasattr(self, 'sheet_url_entry') else ''
        user_col = self.user_col_entry.get().strip() if hasattr(self, 'user_col_entry') else 'E'
        profile_col = self.profile_col_entry.get().strip() if hasattr(self, 'profile_col_entry') else 'G'
        
        if sheet_url and not getattr(self, 'account_map', None):
            accs, msg = extractor.fetch_accounts_from_google_sheet(sheet_url, user_col=user_col or 'E', profile_col=profile_col or 'G')
            self.account_map = accs
            self.log(f"📥 {msg}")
            
        default_pass = self.default_pass_entry.get().strip() if hasattr(self, 'default_pass_entry') else 'Khoa01@c'
        if not default_pass:
            default_pass = 'Khoa01@c'
        
        self.running_ids_before = extractor.get_running_profiles()
        is_txt = output_file.endswith('.txt')
        file_lock = threading.Lock()
        
        try:
            if is_txt:
                txt_file = open(output_file, mode="w", encoding="utf-8")
            else:
                csv_file = open(output_file, mode="w", encoding="utf-8", newline="")
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(["Profile ID", "Profile Name", "Domain", "Status", "Cookie", "User Agent", "Exported At"])
        except Exception as e:
            self.log(f"❌ Không thể mở file kết quả để ghi: {e}")
            self.ui_update_queue.put(('finished', (0, 0)))
            return
            
        success_count = 0
        processed_count = 0
        total_selected = len(selected_ids)
        p_lookup = {p['id']: p for p in self.profiles}
        
        from concurrent.futures import ThreadPoolExecutor
        
        def worker_process_profile(p_id):
            nonlocal success_count, processed_count
            if self.stop_requested:
                return
                
            p_info = p_lookup.get(p_id)
            p_name = p_info.get('name', f'Profile #{p_id}') if p_info else f'Profile #{p_id}'
            p_path = p_info.get('profile_path') if p_info else f"F:\\gemlogin\\profiles\\{p_id}"
            if not p_path or not os.path.exists(p_path):
                p_path = f"F:\\gemlogin\\profiles\\{p_id}"
            
            self.ui_update_queue.put(('status', (p_id, "Đang mở...", STATUS_RUNNING)))
            self.log(f"🚀 [{p_id}] {p_name}: Đang mở trình duyệt...")
            
            cdp_port = 52000 + (p_id % 5000)
            initial_url = f"https://{target_domain}/buyer/login?from=%2F&next=%2F"
            current_ext = self.ext_path_entry.get().strip() if hasattr(self, 'ext_path_entry') else extractor.EXTENSION_PATH
            p_proxy = extractor.extract_profile_proxy(p_info) if not no_proxy else None
            proc, debug_addr = extractor.open_profile_with_extension_and_cdp(
                p_path, 
                port=cdp_port, 
                ext_path=current_ext, 
                initial_url=initial_url,
                no_proxy=no_proxy,
                proxy=p_proxy
            )
            if not debug_addr:
                debug_addr, driver = extractor.api_start_profile(p_id)
                
            if not debug_addr:
                self.log(f"❌ [{p_id}] {p_name}: Không thể khởi động profile")
                self.ui_update_queue.put(('status', (p_id, "Lỗi khởi động", STATUS_ERROR)))
                with file_lock:
                    processed_count += 1
                    self.ui_update_queue.put(('progress', (processed_count, total_selected)))
                return
                
            try:
                time.sleep(2.0)
                ws_url = extractor.get_websocket_url(debug_addr)
                if not ws_url:
                    self.log(f"❌ [{p_id}] {p_name}: Không tìm thấy cổng CDP")
                    self.ui_update_queue.put(('status', (p_id, "Lỗi CDP", STATUS_ERROR)))
                    with file_lock:
                        processed_count += 1
                        self.ui_update_queue.put(('progress', (processed_count, total_selected)))
                    return
                    
                is_logged_in = False
                cookie_tuple = None
                
                # 0. Kiểm tra trước: Profile đã login Shopee sẵn chưa?
                cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=False)
                formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                cookie_tuple = formatted.get(target_domain)
                if cookie_tuple and cookie_tuple[1]:
                    is_logged_in = True
                    self.log(f"✨ [{p_id}] {p_name}: Profile đã có phiên đăng nhập Shopee hợp lệ từ trước!")
                    
                # 1. BƯỚC 1 (ƯU TIÊN): Kiểm tra tài khoản lưu sẵn (autofill / Login Data) trong trình duyệt
                if not is_logged_in:
                    self.log(f"🔐 [{p_id}] {p_name}: Đợi trang đăng nhập tải & kiểm tra tài khoản lưu sẵn...")
                    self.ui_update_queue.put(('status', (p_id, "Kiểm tra login lưu sẵn...", STATUS_RUNNING)))
                    
                    # Kiểm tra xem trình duyệt đã mở trang login hay chưa, chỉ navigate nếu chưa ở trang login
                    try:
                        ws_chk = websocket.create_connection(ws_url, suppress_origin=True, timeout=5)
                        ws_chk.send(json.dumps({'id': 100, 'method': 'Runtime.evaluate', 'params': {'expression': 'window.location.href', 'returnByValue': True}}))
                        curr_url = json.loads(ws_chk.recv()).get('result', {}).get('result', {}).get('value', '')
                        if 'buyer/login' not in curr_url:
                            ws_chk.send(json.dumps({'id': 101, 'method': 'Page.navigate', 'params': {'url': f"https://{target_domain}/buyer/login?from=%2F&next=%2F"}}))
                            ws_chk.recv()
                        ws_chk.close()
                    except Exception:
                        pass

                    res_saved = extractor.perform_auto_saved_account_login(ws_url, domain=target_domain, default_password=default_pass, profile_path=p_path)
                    ok_saved = res_saved[0] if isinstance(res_saved, (tuple, list)) else bool(res_saved)
                    msg_saved = res_saved[1] if isinstance(res_saved, (tuple, list)) and len(res_saved) > 1 else str(res_saved)
                    saved_user = res_saved[2] if isinstance(res_saved, (tuple, list)) and len(res_saved) > 2 else ""
                    
                    self.log(f"👉 [{p_id}] {p_name}: {msg_saved}")
                    
                    if ok_saved:
                        # Chờ kiểm tra kết quả đăng nhập (tối đa 14 giây)
                        for _ in range(7):
                            if self.stop_requested:
                                break
                            time.sleep(2)
                            cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=False)
                            formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                            cookie_tuple = formatted.get(target_domain)
                            if cookie_tuple and cookie_tuple[1]:
                                is_logged_in = True
                                user_display = f" '{saved_user}'" if saved_user else ""
                                self.log(f"🎉 [{p_id}] {p_name}: Đăng nhập tài khoản lưu sẵn{user_display} thành công!")
                                break
                                
                        # Bắt Captcha/OTP nếu có
                        if not is_logged_in and extractor.check_captcha_or_otp_presence(ws_url):
                            self.log(f"⚠️ [{p_id}] {p_name}: Phát hiện Captcha/OTP! Đang chờ bạn thao tác giải (tối đa 90 giây)...")
                            self.ui_update_queue.put(('status', (p_id, "Chờ giải Captcha/OTP", STATUS_WARNING)))
                            start_wait = time.time()
                            while time.time() - start_wait < 90:
                                if self.stop_requested:
                                    break
                                time.sleep(3)
                                cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=False)
                                formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                                cookie_tuple = formatted.get(target_domain)
                                if cookie_tuple and cookie_tuple[1]:
                                    is_logged_in = True
                                    self.log(f"🎉 [{p_id}] {p_name}: Đã phát hiện giải Captcha/OTP thành công!")
                                    break

                # 2. BƯỚC 2: Nếu chưa login được -> Đăng nhập bằng Username & Mật khẩu từ Google Sheet (nếu có)
                if not is_logged_in:
                    acc_map = getattr(self, 'account_map', {}) or {}
                    p_key = p_name.strip().upper()
                    username = acc_map.get(p_key)
                    
                    if username:
                        self.log(f"🔑 [{p_id}] {p_name}: Đang đăng nhập tài khoản '{username}' (Mật khẩu: {default_pass})...")
                        ok_form, msg_form = extractor.perform_auto_form_login(ws_url, domain=target_domain, username=username, password=default_pass)
                        
                        # Trích xuất kiểm tra sau khi login bằng tài khoản
                        cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=False)
                        formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                        cookie_tuple = formatted.get(target_domain)
                        is_logged_in = cookie_tuple[1] if cookie_tuple else False
                        
                        # Nếu gặp Captcha / OTP -> Đứng yên chờ người dùng giải (tối đa 90 giây)
                        if not is_logged_in and extractor.check_captcha_or_otp_presence(ws_url):
                            self.log(f"⚠️ [{p_id}] {p_name}: Phát hiện Captcha/OTP! Đang đứng yên chờ bạn thao tác giải (tối đa 90 giây)...")
                            self.ui_update_queue.put(('status', (p_id, "Chờ giải Captcha/OTP", STATUS_WARNING)))
                            start_wait = time.time()
                            while time.time() - start_wait < 90:
                                if self.stop_requested:
                                    break
                                time.sleep(3)
                                cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=False)
                                formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                                cookie_tuple = formatted.get(target_domain)
                                if cookie_tuple and cookie_tuple[1]:
                                    is_logged_in = True
                                    self.log(f"🎉 [{p_id}] {p_name}: Đã phát hiện giải Captcha/OTP thành công!")
                                    break
                        
                # 3. BƯỚC 3 (FALLBACK): Nếu vẫn chưa login được -> Bơm script tự động bấm "Tiếp tục dưới tên..." hoặc điền User/Password nếu phiên Facebook bị đăng xuất
                if not is_logged_in:
                    self.log(f"🔄 [{p_id}] {p_name}: Bơm script tự động bấm 'Tiếp tục dưới tên...' hoặc đăng nhập lại Facebook...")
                    ok_fb, msg_fb = extractor.perform_auto_facebook_login(ws_url, domain=target_domain, debug_addr=debug_addr)
                    
                    # Trích xuất lại cookie sau khi login Facebook
                    cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=False)
                    formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                    cookie_tuple = formatted.get(target_domain)
                    is_logged_in = cookie_tuple[1] if cookie_tuple else False
                    
                    # Nếu Facebook gặp Captcha / OTP -> Đứng yên chờ giải
                    if not is_logged_in and extractor.check_captcha_or_otp_presence(ws_url):
                        self.log(f"⚠️ [{p_id}] {p_name}: Phát hiện Captcha/OTP từ Facebook/Shopee! Đang đứng yên chờ bạn giải...")
                        self.ui_update_queue.put(('status', (p_id, "Chờ giải Captcha/OTP", STATUS_WARNING)))
                        start_wait = time.time()
                        while time.time() - start_wait < 90:
                            if self.stop_requested:
                                break
                            time.sleep(3)
                            cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=False)
                            formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                            cookie_tuple = formatted.get(target_domain)
                            if cookie_tuple and cookie_tuple[1]:
                                is_logged_in = True
                                self.log(f"🎉 [{p_id}] {p_name}: Đã phát hiện giải Captcha/OTP thành công!")
                                break
                    
                # 4. Kiểm tra bổ sung nếu Shopee cần thêm 2-3s để ghi session cookie hoặc chuyển hướng
                if not is_logged_in:
                    time.sleep(3)
                    try:
                        ws_chk = websocket.create_connection(ws_url, suppress_origin=True, timeout=5)
                        ws_chk.send(json.dumps({'id': 401, 'method': 'Page.navigate', 'params': {'url': f"https://{target_domain}/"}}))
                        ws_chk.recv()
                        ws_chk.close()
                        time.sleep(3)
                    except Exception:
                        pass
                    cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=False)
                    formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                    cookie_tuple = formatted.get(target_domain)
                    is_logged_in = cookie_tuple[1] if cookie_tuple else False
                
                cookie_str = ""
                # Ưu tiên 1: Lấy Cookie trực tiếp từ Extension Tiger 10 đã cài đặt
                ext_cookie = extractor.extract_cookie_from_extension(debug_addr, domain=target_domain)
                if ext_cookie and any(k in ext_cookie for k in ['SPC_EC=', 'SPC_ST=', 'SPC_U=']):
                    cookie_str = ext_cookie
                    is_logged_in = True
                    self.log(f"📦 [{p_id}] {p_name}: Đã lấy Cookie trực tiếp qua Extension Tiger 10!")
                elif cookie_tuple:
                    cookie_str = cookie_tuple[0]
                    if cookie_tuple[1]:
                        is_logged_in = True
                
                if cookie_str and is_logged_in:
                    fmt = self.export_format_var.get() if hasattr(self, 'export_format_var') else "Profile|Cookie|User|Pass|Proxy (EZAff)"
                    proxy_str = extractor.extract_profile_proxy(p_info)
                    uname = saved_user or ""
                    if not uname:
                        uname = extractor.extract_saved_username_from_profile_db(p_path, domain=target_domain)
                    if ("User|Pass" in fmt or "EZAff" in fmt) and not uname:
                        uname = extractor.fetch_shopee_username(cookie_str, domain=target_domain, ws_url=ws_url, profile_path=p_path)
                        if not uname:
                            acc_map = getattr(self, 'account_map', {}) or {}
                            uname = acc_map.get(p_name.strip().upper(), "")
                    out_line = extractor.build_export_line(
                        fmt, p_name, cookie_str,
                        username=uname,
                        password=default_pass,
                        proxy=proxy_str
                    )
                        
                    with file_lock:
                        success_count += 1
                        if is_txt:
                            txt_file.write(f"{out_line}\n")
                            txt_file.flush()
                        else:
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            csv_writer.writerow([p_id, p_name, target_domain, "Đã đăng nhập", cookie_str, ua, now_str])
                            csv_file.flush()
                    status_text = "Đã lấy Cookie (Đã login)"
                    status_color = STATUS_SUCCESS
                    self.log(f"✅ [{p_id}] {p_name}: Trích xuất thành công! (User: {uname or 'N/A'} | Pass: {default_pass} | Proxy: {proxy_str or 'Không'})")
                elif cookie_str:
                    status_text = "Chưa login Shopee"
                    status_color = STATUS_READY
                    self.log(f"⚠️ [{p_id}] {p_name}: Chưa nhận phiên đăng nhập")
                else:
                    status_text = "Không có cookie"
                    status_color = STATUS_ERROR
                    self.log(f"❌ [{p_id}] {p_name}: Không tìm thấy cookie")
                    
                self.ui_update_queue.put(('status', (p_id, status_text, status_color)))
                with file_lock:
                    processed_count += 1
                    self.ui_update_queue.put(('progress', (processed_count, total_selected)))
            finally:
                # Đóng profile sạch sẽ 100% bằng CDP Browser.close + psutil diệt tiến trình
                extractor.force_close_profile_browser(p_id, debug_addr=debug_addr, proc=proc, profile_path=p_path)
                if delay > 0:
                    time.sleep(delay)

        # Chạy đa luồng theo batch_size
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            executor.map(worker_process_profile, selected_ids)
            
        try:
            if is_txt:
                txt_file.close()
            else:
                csv_file.close()
        except Exception:
            pass
            
        self.ui_update_queue.put(('finished', (success_count, total_selected)))
        
    def run_extraction_thread(self, selected_ids, batch_size, delay, output_file, target_domain=None, mobile_ua=False, clean_cookie=True):
        self.log(f"=== Bắt đầu tiến trình trích xuất cho {len(selected_ids)} profile ===")
        country_label = self.country_var.get()
        ua_label = "📱 Mobile UA BẬT" if mobile_ua else "💻 Desktop UA"
        clean_label = "✨ Lọc tinh gọn (Chuẩn MLS/EZAff): BẬT" if clean_cookie else "📦 Lấy đầy đủ cookie thô"
        fmt = self.export_format_var.get() if hasattr(self, 'export_format_var') else "Profile|Cookie|User|Pass|Proxy (EZAff)"
        self.log(f"Quốc gia: {country_label} | Định dạng: {fmt} | Lô: {batch_size}")
        self.log(f"File lưu kết quả: {os.path.abspath(output_file)}")
        
        # Tự động nạp Google Sheet nếu dùng định dạng EZAff để dự phòng ánh xạ Username
        sheet_url = self.sheet_url_entry.get().strip() if hasattr(self, 'sheet_url_entry') else ''
        user_col = self.user_col_entry.get().strip() if hasattr(self, 'user_col_entry') else 'E'
        profile_col = self.profile_col_entry.get().strip() if hasattr(self, 'profile_col_entry') else 'G'
        if ("User|Pass" in fmt or "EZAff" in fmt) and sheet_url and not getattr(self, 'account_map', None):
            accs, msg = extractor.fetch_accounts_from_google_sheet(sheet_url, user_col=user_col or 'E', profile_col=profile_col or 'G')
            self.account_map = accs
            self.log(f"📥 {msg}")
            
        default_pass = self.default_pass_entry.get().strip() if hasattr(self, 'default_pass_entry') else 'Khoa01@c'
        if not default_pass:
            default_pass = 'Khoa01@c'
        p_lookup = {p['id']: p for p in self.profiles}
        
        # Quét lại các profile đang chạy sẵn trước khi bắt đầu thực hiện để tránh đóng
        self.running_ids_before = extractor.get_running_profiles()
        
        # Prepare output file
        is_txt = output_file.endswith('.txt')
        file_exists = os.path.exists(output_file)
        try:
            if is_txt:
                txt_file = open(output_file, mode="w", encoding="utf-8")
            else:
                csv_file = open(output_file, mode="w", encoding="utf-8", newline="")
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(["Profile ID", "Profile Name", "Domain", "Status", "Cookie", "User Agent", "Exported At"])
        except Exception as e:
            self.log(f"❌ Không thể mở file kết quả để ghi: {e}")
            self.ui_update_queue.put(('finished', (0, 0)))
            return
            
        success_count = 0
        total_selected = len(selected_ids)
        
        for i in range(0, total_selected, batch_size):
            if self.stop_requested:
                self.log("🛑 Tiến trình đã dừng theo yêu cầu của người dùng.")
                break
                
            batch_ids = selected_ids[i:i+batch_size]
            self.log(f"\n--- Đang xử lý đợt {i//batch_size + 1}: Profile {i+1} đến {min(i+batch_size, total_selected)} ---")
            
            opened_in_batch = []
            
            # 1. Start all profiles in this batch
            for p_id in batch_ids:
                if self.stop_requested:
                    break
                row = self.profile_rows[p_id]
                p_name = row.name
                
                is_already_running = p_id in self.running_ids_before
                status_str = "đang chạy sẵn" if is_already_running else "đang mở trình duyệt..."
                self.log(f"Profile [{p_id}] {p_name} ({status_str})")
                self.ui_update_queue.put(('status', (p_id, "Đang mở...", STATUS_RUNNING)))
                
                addr, _ = extractor.api_start_profile(p_id)
                if addr:
                    opened_in_batch.append({
                        "id": p_id,
                        "name": p_name,
                        "addr": addr,
                        "already_running": is_already_running
                    })
                else:
                    self.log(f"❌ Không thể khởi động profile [{p_id}] {p_name}")
                    self.ui_update_queue.put(('status', (p_id, "Lỗi khởi động", STATUS_ERROR)))
                    
            if not opened_in_batch:
                # Update progress even if failed
                self.ui_update_queue.put(('progress', (min(i + batch_size, total_selected), total_selected)))
                continue
                
            # Allow time for browser instances to load
            time.sleep(2)
            
            # 2. Connect and extract cookies for started profiles
            for item in opened_in_batch:
                if self.stop_requested:
                    break
                p_id = item['id']
                p_name = item['name']
                addr = item['addr']
                p_info = p_lookup.get(p_id, {})
                
                self.log(f"-> Đang kết nối tới [{p_id}] {p_name} ({addr})...")
                self.ui_update_queue.put(('status', (p_id, "Đang lấy cookie", STATUS_RUNNING)))
                
                ws_url = extractor.get_websocket_url(addr)
                if not ws_url:
                    self.log(f"❌ Không lấy được WebSocket cho [{p_id}] {p_name}")
                    self.ui_update_queue.put(('status', (p_id, "Lỗi kết nối", STATUS_ERROR)))
                    continue
                    
                cookies_list, ua = extractor.extract_cookies_via_cdp(ws_url, target_domain=target_domain, mobile_ua=mobile_ua)
                if not cookies_list:
                    self.log(f"⚠️ Không tìm thấy cookie Shopee nào trong [{p_id}] {p_name}")
                    self.ui_update_queue.put(('status', (p_id, "Không có cookie", STATUS_READY)))
                    continue
                    
                formatted = extractor.format_cookies(cookies_list, target_domain=target_domain, clean_mode=clean_cookie)
                if not formatted:
                    self.log(f"⚠️ Không có cookie khớp quốc gia được chọn trong [{p_id}] {p_name}")
                    self.ui_update_queue.put(('status', (p_id, "Trống cookie", STATUS_READY)))
                    continue
                    
                # Save cookies to output file
                proxy_str = extractor.extract_profile_proxy(p_info)
                wrote_profile = False
                for domain, (cookie_str, logged_in) in formatted.items():
                    if not logged_in:
                        self.log(f"   ⚠️ [{p_id}] {p_name}: Chưa đăng nhập Shopee ({domain}) — Bỏ qua không xuất")
                        continue
                        
                    uname = ""
                    if "User|Pass" in fmt or "EZAff" in fmt:
                        p_path = p_info.get('profile_path') if isinstance(p_info, dict) else f"F:\\gemlogin\\profiles\\{p_id}"
                        uname = extractor.fetch_shopee_username(cookie_str, domain=domain, ws_url=ws_url, profile_path=p_path)
                        if not uname:
                            acc_map = getattr(self, 'account_map', {}) or {}
                            uname = acc_map.get(p_name.strip().upper(), "")
                            
                    out_line = extractor.build_export_line(
                        fmt, p_name, cookie_str,
                        username=uname,
                        password=default_pass,
                        proxy=proxy_str
                    )
                        
                    if is_txt:
                        txt_file.write(f"{out_line}\n")
                        self.log(f"   ✅ Đã xuất [{domain}] -> {p_name} | User: {uname or '(trống)'} | Pass: {default_pass} | Proxy: {proxy_str or 'Không'}")
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
                        self.log(f"   ✅ Đã trích xuất cookie [{domain}] [{login_status}] thành công.")
                    wrote_profile = True
                    
                if wrote_profile:
                    success_count += 1
                    if is_txt:
                        txt_file.flush()
                    else:
                        csv_file.flush() # Ensure data is written
                    self.ui_update_queue.put(('status', (p_id, "Thành công", STATUS_SUCCESS)))
                else:
                    self.ui_update_queue.put(('status', (p_id, "Chưa login", STATUS_WARNING)))
                
            # 3. Auto-close profiles opened by this script (keep the ones that were running before)
            for item in opened_in_batch:
                p_id = item['id']
                p_name = item['name']
                if not item['already_running']:
                    self.log(f"<- Đang tự động đóng profile [{p_id}] {p_name}...")
                    extractor.force_close_profile_browser(p_id, debug_addr=item.get('addr'))
                    time.sleep(delay)
                    
            # Update progress bar
            self.ui_update_queue.put(('progress', (min(i + batch_size, total_selected), total_selected)))
            
        if is_txt:
            txt_file.close()
        else:
            csv_file.close()
        self.ui_update_queue.put(('finished', (success_count, total_selected)))
        
    def on_extraction_finished(self, stats):
        success, total = stats
        self.is_extracting = False
        
        # Reset UI controls
        self.start_btn.config(state=tk.NORMAL, text="🚀 BẮT ĐẦU TRÍCH XUẤT", bg=ACCENT_ORANGE, activebackground="#d63d1e")
        if hasattr(self, 'auto_fb_login_btn') and self.auto_fb_login_btn:
            self.auto_fb_login_btn.config(state=tk.NORMAL)
        if self.stop_btn:
            self.stop_btn.config(state=tk.DISABLED, text="🛑 DỪNG TIẾN TRÌNH")
        if hasattr(self, 'refresh_btn') and self.refresh_btn:
            self.refresh_btn.config(state=tk.NORMAL, text="🔄 Tải lại")
        self.search_entry.config(state=tk.NORMAL)
        
        # Scan again to see current state
        self.running_ids_before = extractor.get_running_profiles()
        for p_id, row in self.profile_rows.items():
            row.set_sys_status(p_id in self.running_ids_before)
            
        self.update_stats()
        
        self.log(f"\n=== Tiến trình kết thúc! ===")
        self.log(f"Hoàn thành lấy cookie cho {success} / {total} profile đã chọn.")
        
        messagebox.showinfo("Hoàn thành", f"Hoàn thành lấy cookie thành công cho {success} / {total} profile đã chọn!")

if __name__ == "__main__":
    root = tk.Tk()
    app = GemloginCookieGUI(root)
    root.mainloop()
