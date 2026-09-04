import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import time
import os
import csv
import json
import sys
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

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt")

def get_current_version():
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r", encoding="utf-8") as f:
                v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass
    return "1.0.1"

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
        self.root.geometry("1100x750")
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
        
        cur_version = get_current_version()
        banner_subtitle = tk.Label(
            self.banner, 
            text=f"Shopee Auto-Extractor Edition v{cur_version}", 
            fg="#ffd2cc", 
            bg=ACCENT_ORANGE, 
            font=("Arial", 10, "italic")
        )
        banner_subtitle.pack(side=tk.RIGHT, padx=20, pady=20)
        
        # Main container with two columns
        self.container = tk.Frame(self.root, bg=BG_DARK)
        self.container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # --- LEFT PANEL: Control & Configuration ---
        self.left_panel = tk.Frame(self.container, bg=BG_CARD, width=320, padx=15, pady=15)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.left_panel.pack_propagate(False)
        
        # 1. Config Section
        config_title = tk.Label(
            self.left_panel, 
            text="CẤU HÌNH BATCH", 
            fg=ACCENT_ORANGE, 
            bg=BG_CARD, 
            font=("Arial", 11, "bold")
        )
        config_title.pack(anchor="w", pady=(0, 10))
        
        # Batch size
        tk.Label(self.left_panel, text="Số luồng chạy đồng thời (Batch Size):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 9)).pack(anchor="w")
        self.batch_entry = tk.Entry(self.left_panel, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 10))
        self.batch_entry.insert(0, "5")
        self.batch_entry.pack(fill=tk.X, pady=(2, 10), ipady=5)
        
        # Delay size
        tk.Label(self.left_panel, text="Độ trễ giữa các profile (Giây):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 9)).pack(anchor="w")
        self.delay_entry = tk.Entry(self.left_panel, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 10))
        self.delay_entry.insert(0, "1")
        self.delay_entry.pack(fill=tk.X, pady=(2, 10), ipady=5)
        
        # Country Selection
        tk.Label(self.left_panel, text="Quốc gia (Thị trường Shopee):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 9)).pack(anchor="w")
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
        self.country_menu.pack(fill=tk.X, pady=(2, 10))
        
        # Mobile UA emulation toggle
        self.mobile_ua_var = tk.BooleanVar(value=False)
        self.mobile_ua_check = tk.Checkbutton(
            self.left_panel,
            text="📱 Giả lập Mobile UA (bypass anti-bot)",
            variable=self.mobile_ua_var,
            bg=BG_CARD, fg=TEXT_WHITE, selectcolor="#2d2d2d",
            activebackground=BG_CARD, activeforeground=TEXT_WHITE,
            font=("Arial", 9),
            anchor="w"
        )
        self.mobile_ua_check.pack(fill=tk.X, pady=(0, 4))
        
        # Clean Cookie filter toggle (Chuẩn Tool MLS / PH3001)
        self.clean_cookie_var = tk.BooleanVar(value=True)
        self.clean_cookie_check = tk.Checkbutton(
            self.left_panel,
            text="✨ Lọc Cookie tinh gọn (Chuẩn MLS/PH3001)",
            variable=self.clean_cookie_var,
            bg=BG_CARD, fg=TEXT_WHITE, selectcolor="#2d2d2d",
            activebackground=BG_CARD, activeforeground=TEXT_WHITE,
            font=("Arial", 9),
            anchor="w"
        )
        self.clean_cookie_check.pack(fill=tk.X, pady=(0, 10))
        
        # Output File Path
        tk.Label(self.left_panel, text="File xuất kết quả (TXT/CSV):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 9)).pack(anchor="w")
        file_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        file_frame.pack(fill=tk.X, pady=(2, 8))
        
        self.output_entry = tk.Entry(file_frame, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9))
        self.output_entry.insert(0, "shopee_cookies.txt")
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        
        browse_btn = tk.Button(
            file_frame, 
            text="...", 
            bg="#3d3d3d", 
            fg=TEXT_WHITE, 
            activebackground=BG_HOVER, 
            activeforeground=TEXT_WHITE,
            borderwidth=0, 
            padx=10, 
            command=self.browse_output
        )
        browse_btn.pack(side=tk.RIGHT, padx=(5, 0), ipady=3)
        
        # Output TXT Format Selection
        tk.Label(self.left_panel, text="Định dạng dòng xuất (TXT):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 9)).pack(anchor="w")
        self.export_format_var = tk.StringVar(value="Tên|Cookie")
        self.export_format_combo = ttk.Combobox(
            self.left_panel,
            textvariable=self.export_format_var,
            values=[
                "Tên|Cookie",
                "Chỉ Cookie"
            ],
            state="readonly",
            font=("Arial", 9)
        )
        self.export_format_combo.pack(fill=tk.X, pady=(2, 10))
        
        # Google Sheet Configuration
        tk.Label(self.left_panel, text="Link Google Sheet:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 9)).pack(anchor="w")
        sheet_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        sheet_frame.pack(fill=tk.X, pady=(2, 6))
        
        self.sheet_url_entry = tk.Entry(sheet_frame, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9))
        self.sheet_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        
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
        load_sheet_btn.pack(side=tk.RIGHT, padx=(5, 0), ipady=3)
        
        # Column Setting: Cột User & Cột Profile
        cols_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        cols_frame.pack(fill=tk.X, pady=(2, 6))
        
        user_col_box = tk.Frame(cols_frame, bg=BG_CARD)
        user_col_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Label(user_col_box, text="Cột User:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.user_col_entry = tk.Entry(user_col_box, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9, "bold"), justify="center")
        self.user_col_entry.insert(0, "E")
        self.user_col_entry.pack(fill=tk.X, ipady=3)
        
        prof_col_box = tk.Frame(cols_frame, bg=BG_CARD)
        prof_col_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        tk.Label(prof_col_box, text="Cột Profile:", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 8)).pack(anchor="w")
        self.profile_col_entry = tk.Entry(prof_col_box, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9, "bold"), justify="center")
        self.profile_col_entry.insert(0, "G")
        self.profile_col_entry.pack(fill=tk.X, ipady=3)
        
        tk.Label(self.left_panel, text="Mật khẩu mặc định (User/Pass):", fg=TEXT_GRAY, bg=BG_CARD, font=("Arial", 9)).pack(anchor="w")
        self.default_pass_entry = tk.Entry(self.left_panel, bg="#2d2d2d", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, borderwidth=0, font=("Arial", 9))
        self.default_pass_entry.insert(0, "Khoa01@c")
        self.default_pass_entry.pack(fill=tk.X, pady=(2, 12), ipady=5)
        
        self.account_map = {}
        
        # Divider
        tk.Frame(self.left_panel, bg="#2d2d2d", height=1).pack(fill=tk.X, pady=15)
        
        # 2. Control Buttons Section
        control_title = tk.Label(
            self.left_panel, 
            text="ĐIỀU KHIỂN CHẠY", 
            fg=ACCENT_ORANGE, 
            bg=BG_CARD, 
            font=("Arial", 11, "bold")
        )
        control_title.pack(anchor="w", pady=(0, 10))
        
        self.start_btn = tk.Button(
            self.left_panel, 
            text="🚀 BẮT ĐẦU TRÍCH XUẤT", 
            bg=ACCENT_ORANGE, 
            fg=TEXT_WHITE, 
            activebackground="#d63d1e", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 10, "bold"),
            borderwidth=0, 
            pady=10, 
            command=self.start_extraction
        )
        self.start_btn.pack(fill=tk.X, pady=5)
        
        self.stop_btn = tk.Button(
            self.left_panel, 
            text="🛑 DỪNG TIẾN TRÌNH", 
            bg="#3d3d3d", 
            fg=TEXT_WHITE, 
            activebackground=BG_HOVER, 
            activeforeground=TEXT_WHITE,
            font=("Arial", 10, "bold"),
            borderwidth=0, 
            pady=10, 
            state=tk.DISABLED,
            command=self.stop_extraction
        )
        self.stop_btn.pack(fill=tk.X, pady=5)
        
        self.refresh_btn = tk.Button(
            self.left_panel, 
            text="🔄 TẢI LẠI PROFILE", 
            bg="#2d2d2d", 
            fg=TEXT_WHITE, 
            activebackground=BG_HOVER, 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9),
            borderwidth=0, 
            pady=8, 
            command=self.load_profiles
        )
        self.refresh_btn.pack(fill=tk.X, pady=(15, 5))
        
        self.install_ext_btn = tk.Button(
            self.left_panel, 
            text="🧩 CÀI EXTENSION VÀO PROFILE ĐÃ CHỌN", 
            bg="#1e5f74", 
            fg=TEXT_WHITE, 
            activebackground="#133b5c", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=8, 
            command=self.install_extension_to_selected
        )
        self.install_ext_btn.pack(fill=tk.X, pady=5)
        
        self.open_with_ext_btn = tk.Button(
            self.left_panel, 
            text="🌐 MỞ PROFILE KÈM EXTENSION COOKIE", 
            bg="#2a5298", 
            fg=TEXT_WHITE, 
            activebackground="#1e3c72", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=8, 
            command=self.open_selected_profiles_with_ext
        )
        self.open_with_ext_btn.pack(fill=tk.X, pady=5)
        
        self.clear_data_btn = tk.Button(
            self.left_panel, 
            text="🧹 XOÁ COOKIE & SITE DATA (SHOPEE.PH)", 
            bg="#802b2b", 
            fg=TEXT_WHITE, 
            activebackground="#5a1d1d", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=8, 
            command=self.clear_site_data_for_selected
        )
        self.clear_data_btn.pack(fill=tk.X, pady=5)
        
        self.auto_fb_login_btn = tk.Button(
            self.left_panel, 
            text="🔑 TỰ ĐỘNG LOGIN FB & LẤY COOKIE", 
            bg="#5e35b1", 
            fg=TEXT_WHITE, 
            activebackground="#4527a0", 
            activeforeground=TEXT_WHITE,
            font=("Arial", 9, "bold"),
            borderwidth=0, 
            pady=8, 
            command=self.auto_login_fb_and_extract
        )
        self.auto_fb_login_btn.pack(fill=tk.X, pady=5)
        
        # Divider
        tk.Frame(self.left_panel, bg="#2d2d2d", height=1).pack(fill=tk.X, pady=15)
        
        # Stat Panel
        self.stat_frame = tk.Frame(self.left_panel, bg=BG_CARD)
        self.stat_frame.pack(fill=tk.BOTH, expand=True)
        
        self.stat_title = tk.Label(
            self.stat_frame, 
            text="THỐNG KÊ", 
            fg=ACCENT_ORANGE, 
            bg=BG_CARD, 
            font=("Arial", 11, "bold")
        )
        self.stat_title.pack(anchor="w")
        
        self.stat_total_lbl = tk.Label(self.stat_frame, text="Tổng số profile: 0", fg=TEXT_WHITE, bg=BG_CARD, font=("Arial", 10), anchor="w")
        self.stat_total_lbl.pack(fill=tk.X, pady=2)
        
        self.stat_selected_lbl = tk.Label(self.stat_frame, text="Đã chọn: 0", fg=TEXT_WHITE, bg=BG_CARD, font=("Arial", 10), anchor="w")
        self.stat_selected_lbl.pack(fill=tk.X, pady=2)
        
        self.stat_running_lbl = tk.Label(self.stat_frame, text="Đang chạy sẵn trên máy: 0", fg=TEXT_WHITE, bg=BG_CARD, font=("Arial", 10), anchor="w")
        self.stat_running_lbl.pack(fill=tk.X, pady=2)
        
        self.progress_lbl = tk.Label(self.stat_frame, text="Tiến độ: 0 / 0", fg=TEXT_WHITE, bg=BG_CARD, font=("Arial", 10, "bold"), anchor="w")
        self.progress_lbl.pack(fill=tk.X, pady=(15, 2))
        
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
        
        # Add mouse wheel support
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        
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

    def save_config(self):
        """Lưu lại toàn bộ cấu hình cài đặt của người dùng vào file config.json"""
        try:
            config = {
                "batch_size": self.batch_entry.get().strip() if hasattr(self, 'batch_entry') else "5",
                "delay": self.delay_entry.get().strip() if hasattr(self, 'delay_entry') else "1",
                "country": self.country_var.get() if hasattr(self, 'country_var') else "PH (Philippines)",
                "mobile_ua": self.mobile_ua_var.get() if hasattr(self, 'mobile_ua_var') else False,
                "clean_cookie": self.clean_cookie_var.get() if hasattr(self, 'clean_cookie_var') else True,
                "output_file": self.output_entry.get().strip() if hasattr(self, 'output_entry') else "shopee_cookies.txt",
                "export_format": self.export_format_var.get() if hasattr(self, 'export_format_var') else "Tên|Cookie",
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
                
            if "output_file" in config and hasattr(self, 'output_entry'):
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, str(config["output_file"]))
                
            if "export_format" in config and hasattr(self, 'export_format_var'):
                self.export_format_var.set(str(config["export_format"]))
                
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
        
    def load_profiles(self):
        # Clear existing profile list UI
        for row in self.profile_rows.values():
            row.frame.destroy()
        self.profile_rows.clear()
        
        self.log("Đang tải danh sách profile từ API cục bộ Gemlogin (127.0.0.1:1010)...")
        
        # Get groups from API
        self.groups = []
        try:
            import urllib.request
            req = urllib.request.Request(f"{extractor.GEMLOGIN_API}/api/groups")
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode('utf-8'))
                if res.get('success'):
                    self.groups = res.get('data', [])
        except Exception:
            pass
        
        # Update group dropdown
        menu = self.group_menu["menu"]
        menu.delete(0, "end")
        group_options = ["Tất cả nhóm", "Không có nhóm"]
        for g in self.groups:
            group_options.append(g['name'])
        for opt in group_options:
            menu.add_command(label=opt, command=lambda v=opt: self.group_var.set(v))
        self.group_var.set("Tất cả nhóm")
        self.log(f"Tìm thấy {len(self.groups)} nhóm: {', '.join(g['name'] for g in self.groups) if self.groups else '(không có)'}")
        
        # Get profiles from API
        self.profiles = extractor.api_get_profiles()
        if not self.profiles:
            self.log("⚠️ Không thể tải danh sách profile. Đảm bảo phần mềm Gemlogin đang mở và tính năng API được bật.")
            messagebox.showerror("Lỗi", "Không thể kết nối tới Gemlogin API cục bộ trên cổng 1010. Vui lòng mở phần mềm Gemlogin và thử lại.")
            return
            
        self.log(f"Tải thành công {len(self.profiles)} profile.")
        
        # Get running profiles
        self.log("Đang kiểm tra các profile đang mở sẵn trên máy...")
        self.running_ids_before = extractor.get_running_profiles()
        self.log(f"Phát hiện {len(self.running_ids_before)} profile đang mở sẵn.")
        
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
        except queue.Empty:
            pass
        self.root.after(100, self.process_ui_queue)
        
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
        self.start_btn.config(state=tk.DISABLED, text="⚡ ĐANG CHẠY...")
        self.stop_btn.config(state=tk.NORMAL)
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
        self.stop_btn.config(state=tk.DISABLED, text="⏳ Đang dừng...")
        
    def install_extension_to_selected(self):
        """Cài đặt và ghim Extension Cookie Shopee vào tất cả profile đang được tích chọn"""
        selected_ids = [p_id for p_id, row in self.profile_rows.items() if row.var.get()]
        if not selected_ids:
            messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 profile để cài extension.")
            return
            
        ext_path = extractor.EXTENSION_PATH
        if not os.path.exists(ext_path):
            messagebox.showerror("Lỗi", f"Không tìm thấy thư mục extension tại:\n{ext_path}")
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
            
        ext_path = extractor.EXTENSION_PATH
        if not os.path.exists(ext_path):
            messagebox.showerror("Lỗi", f"Không tìm thấy thư mục extension tại:\n{ext_path}")
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
            
        p_lookup = {p['id']: p for p in self.profiles}
        for p_id in selected_ids:
            p_info = p_lookup.get(p_id)
            p_name = p_info.get('name', f'Profile #{p_id}') if p_info else f'Profile #{p_id}'
            p_path = p_info.get('profile_path') if p_info else f"F:\\gemlogin\\profiles\\{p_id}"
            b_ver = p_info.get('browser_version', 140) if p_info else 140
            
            ok, msg = extractor.open_profile_with_extension(
                p_path, 
                browser_version=b_ver, 
                ext_path=ext_path, 
                clear_site_data=clear_data, 
                domain=target_domain
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
        
        try:
            batch_size = int(self.batch_entry.get().strip())
            if batch_size <= 0:
                batch_size = 1
        except ValueError:
            batch_size = 3
            
        confirm = messagebox.askyesno(
            "Xác nhận Tự động Đăng nhập Đa Luồng",
            f"Bạn có chắc muốn tự động Đăng nhập (FB / Google Sheet) & Lấy Cookie cho {len(selected_ids)} profile đã chọn không?\n\nSố luồng chạy đồng thời: {batch_size}\nDomain: {target_domain}\nFile lưu: {output_file}"
        )
        if not confirm:
            return
            
        self.is_extracting = True
        self.stop_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_lbl.config(text=f"Tiến độ: 0 / {len(selected_ids)}")
        self.progress_bar.config(maximum=len(selected_ids), value=0)
        
        threading.Thread(
            target=self.run_auto_fb_login_thread, 
            args=(selected_ids, target_domain, output_file, clean_cookie, batch_size), 
            daemon=True
        ).start()

    def run_auto_fb_login_thread(self, selected_ids, target_domain, output_file, clean_cookie, batch_size=3):
        self.log(f"=== Bắt đầu Tự động Đăng nhập ĐA LUỒNG cho {len(selected_ids)} profile (Số luồng: {batch_size}) ===")
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
            
            self.ui_update_queue.put(('status', (p_id, "Đang mở...", STATUS_RUNNING)))
            self.log(f"🚀 [{p_id}] {p_name}: Đang mở trình duyệt...")
            
            cdp_port = 52000 + (p_id % 5000)
            initial_url = f"https://{target_domain}/buyer/login?from=%2F&next=%2F"
            proc, debug_addr = extractor.open_profile_with_extension_and_cdp(
                p_path, 
                port=cdp_port, 
                ext_path=extractor.EXTENSION_PATH, 
                initial_url=initial_url
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
                
            time.sleep(3)
            ws_url = extractor.get_websocket_url(debug_addr)
            if not ws_url:
                self.log(f"❌ [{p_id}] {p_name}: Không tìm thấy cổng CDP")
                if p_id not in self.running_ids_before:
                    if proc:
                        proc.terminate()
                        try: proc.wait(timeout=2)
                        except Exception: pass
                    else:
                        extractor.api_close_profile(p_id)
                self.ui_update_queue.put(('status', (p_id, "Lỗi CDP", STATUS_ERROR)))
                with file_lock:
                    processed_count += 1
                    self.ui_update_queue.put(('progress', (processed_count, total_selected)))
                return
                
            # 2. BƯỚC 1 (ƯU TIÊN): Đăng nhập bằng Username & Mật khẩu từ Google Sheet
            acc_map = getattr(self, 'account_map', {}) or {}
            p_key = p_name.strip().upper()
            username = acc_map.get(p_key)
            is_logged_in = False
            cookie_tuple = None
            
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
                
            # 3. BƯỚC 2 (FALLBACK): Nếu chưa login được hoặc không có user trong Sheet -> Đăng nhập bằng Facebook
            if not is_logged_in:
                if username:
                    self.log(f"🔄 [{p_id}] {p_name}: Đăng nhập tài khoản chưa xong -> Thử tiếp bằng Facebook...")
                else:
                    self.log(f"🔑 [{p_id}] {p_name}: Không có trong Sheet -> Đang đăng nhập bằng Facebook...")
                    
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
                    # Buộc nạp trang chủ Shopee nếu đang ở trang verify/traffic/error
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
            if cookie_tuple:
                cookie_str = cookie_tuple[0]
                if is_logged_in:
                    fmt = self.export_format_var.get() if hasattr(self, 'export_format_var') else "Tên|Cookie"
                    if "Chỉ Cookie" in fmt:
                        out_line = f"{cookie_str}"
                    else:
                        out_line = f"{p_name}|{cookie_str}"
                        
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
                    self.log(f"✅ [{p_id}] {p_name}: Đăng nhập & Trích xuất Cookie thành công!")
                else:
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
                
            # 4. Đóng profile sạch sẽ bằng CDP Browser.close để không bao giờ bị báo Restore pages
            if p_id not in self.running_ids_before:
                try:
                    ws_c = websocket.create_connection(ws_url, suppress_origin=True, timeout=2)
                    ws_c.send(json.dumps({'id': 999, 'method': 'Browser.close'}))
                    ws_c.close()
                except Exception:
                    pass
                if proc:
                    try:
                        proc.wait(timeout=2)
                    except Exception:
                        subprocess.run(f"taskkill /F /PID {proc.pid}", shell=True, capture_output=True)
                else:
                    extractor.api_close_profile(p_id)

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
        clean_label = "✨ Lọc tinh gọn (Chuẩn MLS/PH3001): BẬT" if clean_cookie else "📦 Lấy đầy đủ cookie thô"
        self.log(f"Quốc gia: {country_label} | {ua_label} | {clean_label} | Lô: {batch_size} | Trễ: {delay}s")
        self.log(f"File lưu kết quả: {os.path.abspath(output_file)}")
        
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
                for domain, (cookie_str, logged_in) in formatted.items():
                    fmt = self.export_format_var.get() if hasattr(self, 'export_format_var') else "Tên|Cookie"
                    if "Chỉ Cookie" in fmt:
                        out_line = f"{cookie_str}"
                    else:
                        out_line = f"{p_name}|{cookie_str}"
                        
                    if is_txt:
                        txt_file.write(f"{out_line}\n")
                        self.log(f"   ✅ Đã trích xuất [{domain}] -> Dạng text ({out_line[:40]}...)")
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
                    
                success_count += 1
                if is_txt:
                    txt_file.flush()
                else:
                    csv_file.flush() # Ensure data is written
                self.ui_update_queue.put(('status', (p_id, "Thành công", STATUS_SUCCESS)))
                
            # 3. Auto-close profiles opened by this script (keep the ones that were running before)
            for item in opened_in_batch:
                p_id = item['id']
                p_name = item['name']
                if not item['already_running']:
                    self.log(f"<- Đang tự động đóng profile [{p_id}] {p_name}...")
                    extractor.api_close_profile(p_id)
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
        self.start_btn.config(state=tk.NORMAL, text="🚀 BẮT ĐẦU TRÍCH XUẤT")
        self.stop_btn.config(state=tk.DISABLED, text="🛑 DỪNG TIẾN TRÌNH")
        self.refresh_btn.config(state=tk.NORMAL)
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
