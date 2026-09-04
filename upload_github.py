# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(ROOT_DIR, 'version.txt')
REPO_URL = 'https://github.com/thincole/getcookieSP'

def run_cmd(cmd, cwd=ROOT_DIR, check=False):
    print(f"[*] Chạy lệnh: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip() and result.returncode != 0:
        print(f"[!] stderr: {result.stderr.strip()}")
    if check and result.returncode != 0:
        raise RuntimeError(f"Lệnh thất bại với mã {result.returncode}: {cmd}")
    return result

def get_current_version():
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, 'r', encoding='utf-8') as f:
                v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass
    return '1.0.1'

def bump_version(ver_str):
    parts = ver_str.strip().split('.')
    try:
        if len(parts) >= 3:
            parts[-1] = str(int(parts[-1]) + 1)
            return '.'.join(parts)
        elif len(parts) == 2:
            return f"{parts[0]}.{parts[1]}.1"
        elif len(parts) == 1:
            return f"{parts[0]}.0.1"
    except ValueError:
        pass
    return ver_str + '.1'

def save_version(ver_str):
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(ver_str.strip() + '\n')

def main():
    parser = argparse.ArgumentParser(description='Auto Git Push & Version Bumper for getcookieSP')
    parser.add_argument('--init', action='store_true', help='Giữ nguyên version hiện tại (không tự động tăng)')
    parser.add_argument('--auto', '-y', action='store_true', help='Tự động tăng version mà không cần hỏi')
    parser.add_argument('--version', type=str, default=None, help='Chỉ định version cụ thể')
    parser.add_argument('--message', '-m', type=str, default=None, help='Commit message')
    args = parser.parse_args()

    print('=' * 60)
    print('       GEMLOGIN SHOPEE COOKIE - GITHUB UPLOADER')
    print('=' * 60)

    # 1. Kiểm tra Git
    check_git = subprocess.run('git --version', shell=True, capture_output=True, text=True)
    if check_git.returncode != 0:
        print('[x] LỖI: Không tìm thấy Git trên hệ thống! Vui lòng cài đặt Git: https://git-scm.com/')
        sys.exit(1)

    cur_ver = get_current_version()
    next_ver = bump_version(cur_ver)

    chosen_ver = cur_ver
    if args.version:
        chosen_ver = args.version.strip()
    elif args.init:
        chosen_ver = cur_ver
    elif args.auto:
        chosen_ver = next_ver
    else:
        print(f"\n[+] Phiên bản hiện tại : {cur_ver}")
        print(f"[+] Phiên bản tiếp theo: {next_ver}")
        print('-' * 60)
        try:
            user_input = input(f"Nhấn ENTER để tăng lên v{next_ver} (hoặc gõ 'k' để giữ nguyên v{cur_ver}, hoặc nhập version): ").strip()
        except EOFError:
            user_input = ""
            
        if not user_input:
            chosen_ver = next_ver
        elif user_input.lower() in ('k', 'keep', 'same'):
            chosen_ver = cur_ver
        else:
            chosen_ver = user_input

    save_version(chosen_ver)
    print(f"\n[*] Xác nhận phiên bản sẽ đẩy lên: v{chosen_ver}")

    # 2. Khởi tạo Git repo nếu chưa có
    if not os.path.exists(os.path.join(ROOT_DIR, '.git')):
        print('[*] Khởi tạo Git repository...')
        run_cmd('git init', check=True)

    # Kiểm tra git user
    check_user = subprocess.run('git config user.name', shell=True, capture_output=True, text=True).stdout.strip()
    if not check_user:
        run_cmd('git config user.name "thincole"')
        run_cmd('git config user.email "thincole@users.noreply.github.com"')

    # Chuyển branch sang main
    run_cmd('git branch -M main')

    # Cấu hình Remote
    remotes = subprocess.run('git remote', shell=True, capture_output=True, text=True).stdout.strip().split()
    if 'origin' in remotes:
        run_cmd(f'git remote set-url origin {REPO_URL}')
    else:
        run_cmd(f'git remote add origin {REPO_URL}')

    # 3. Add & Commit
    print('\n[*] Đang stage file vào Git (git add .)...')
    run_cmd('git add .')

    commit_msg = args.message if args.message else f"Release v{chosen_ver}"
    status_check = subprocess.run('git status --porcelain', shell=True, capture_output=True, text=True).stdout.strip()
    if status_check:
        print(f'[*] Đang commit với thông điệp: "{commit_msg}"...')
        run_cmd(f'git commit -m "{commit_msg}"')
    else:
        print('[*] Không có file nào thay đổi nội dung commit mới.')

    # 4. Tag version
    tag_name = f"v{chosen_ver}"
    print(f'[*] Đang tạo tag: {tag_name}...')
    run_cmd(f'git tag -f -a "{tag_name}" -m "Release {tag_name}"')

    # 5. Push lên GitHub
    print(f'\n[*] Đang đẩy code lên GitHub ({REPO_URL})...')
    push_res = run_cmd('git push -u origin main --tags')
    if push_res.returncode == 0:
        print('\n' + '=' * 60)
        print(f' [OK] THÀNH CÔNG! Đã đẩy code phiên bản v{chosen_ver} lên GitHub!')
        print(f' [->] Xem tại: {REPO_URL}')
        print('=' * 60)
    else:
        print('\n' + '!' * 60)
        print('[x] PUSH THẤT BẠI! Vui lòng kiểm tra quyền truy cập GitHub hoặc Internet.')
        print('!' * 60)
        sys.exit(push_res.returncode)

if __name__ == '__main__':
    main()
