import os
import sys
import time
import webbrowser
import subprocess
import signal
import threading
import requests
import argparse

BACKEND_PORT = 8000
BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')

def start_backend():
    python_path = sys.executable
    print(f"Starting backend with Python: {python_path}")
    print(f"Backend directory: {BACKEND_DIR}")
    
    env = os.environ.copy()
    env['PYTHONPATH'] = BACKEND_DIR + (env.get('PYTHONPATH', '') and ':' + env['PYTHONPATH'])
    
    process = subprocess.Popen(
        [python_path, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(BACKEND_PORT)],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    return process

def wait_for_backend(timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(f'http://127.0.0.1:{BACKEND_PORT}/api/health', timeout=2)
            if resp.status_code == 200:
                print("Backend is ready!")
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def stop_backend(process):
    print("\nStopping backend...")
    try:
        process.terminate()
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass

def enter_demo_mode(user_id=None):
    try:
        url = f'http://127.0.0.1:{BACKEND_PORT}/api/demo/enter'
        if user_id:
            url += f'?user_id={user_id}'
        resp = requests.post(url, timeout=5)
        data = resp.json()
        if data.get('success'):
            user_name = data.get('user', {}).get('name', '')
            cards_count = data.get('cards_count', 0)
            print(f"  ✓ 已进入演示模式")
            if user_name:
                print(f"  ✓ 当前用户: {user_name}")
            print(f"  ✓ 加载卡片: {cards_count} 张")
            return True
        else:
            print(f"  ✗ 进入演示模式失败: {data.get('error', '未知错误')}")
            return False
    except Exception as e:
        print(f"  ✗ 进入演示模式失败: {e}")
        return False

def get_demo_users():
    try:
        resp = requests.get(f'http://127.0.0.1:{BACKEND_PORT}/api/demo/users', timeout=5)
        data = resp.json()
        return data.get('users', [])
    except Exception:
        return []

def main():
    parser = argparse.ArgumentParser(description='朝花夕拾 Flower Dance')
    parser.add_argument('--demo', action='store_true', help='启动后自动进入演示模式')
    parser.add_argument('--demo-user', type=str, help='指定演示用户 (demo_user_a/demo_user_b/demo_user_c)')
    parser.add_argument('--list-demo-users', action='store_true', help='列出可用的演示用户')
    args = parser.parse_args()
    
    if args.list_demo_users:
        print("=" * 50)
        print("  可用演示用户")
        print("=" * 50)
        print()
        
        backend_process = start_backend()
        if wait_for_backend():
            users = get_demo_users()
            if users:
                for user in users:
                    print(f"  ID: {user['id']}")
                    print(f"    姓名: {user['name']}")
                    print(f"    描述: {user['description']}")
                    print(f"    标签: {', '.join(user['tags'])}")
                    print(f"    卡片数: {user['card_count']}")
                    print()
            else:
                print("  未找到演示用户")
            stop_backend(backend_process)
        else:
            print("  无法连接到后端服务")
            stop_backend(backend_process)
        sys.exit(0)
    
    print("=" * 50)
    print("  朝花夕拾 Flower Dance")
    print("=" * 50)
    print()
    
    if args.demo:
        print("[演示模式] 启动后将自动加载演示数据")
        if args.demo_user:
            print(f"[演示模式] 指定用户: {args.demo_user}")
        print()
    
    backend_process = None
    
    def signal_handler(sig, frame):
        if backend_process:
            stop_backend(backend_process)
        print("\nGoodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        backend_process = start_backend()
        
        print("Waiting for backend to start...")
        if not wait_for_backend():
            print("Error: Backend failed to start within timeout")
            if backend_process:
                stop_backend(backend_process)
            sys.exit(1)
        
        if args.demo:
            print("\n[演示模式] 正在加载演示数据...")
            enter_demo_mode(args.demo_user)
        
        print(f"\nOpening app in default browser...")
        webbrowser.open(f'http://127.0.0.1:{BACKEND_PORT}')
        
        if args.demo:
            print("\n演示模式已启动！按 Ctrl+C 退出并停止后端服务。")
        else:
            print("\nApp is running! Press Ctrl+C to quit.")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    finally:
        if backend_process:
            stop_backend(backend_process)

if __name__ == '__main__':
    main()