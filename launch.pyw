import webview
import threading
import subprocess
import sys, time, os, ctypes
import atexit

# === 配置区域 ===
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 900
RIGHT_PADDING = 0  # 离屏幕右边缘的距离
TOP_PADDING = 300    # 离屏幕上边缘的距离

def get_screen_width():
    try:
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0)
    except: return 1920

def start_streamlit(port):
    global proc
    cmd = [
        sys.executable, "-m", "streamlit", "run", "stapp.py",
        "--server.port", str(port),
        "--server.headless", "true",
        "--theme.base", "dark" #以此默认开启暗黑模式，更有极客感
    ]
    proc = subprocess.Popen(cmd)
    atexit.register(proc.kill)


def inject(text):
    window.evaluate_js(f"""
        const textarea = document.querySelector('textarea[data-testid="stChatInputTextArea"]');
        if (textarea) {{
            // 1. 用原生 setter 设置值（绕过 React）
            const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value'
            ).set;
            nativeTextAreaValueSetter.call(textarea, {repr(text)});
            // 2. 触发 React 的 input 事件
            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
            // 3. 触发 change 事件（有些组件需要）
            textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
            // 4. 延迟提交
            setTimeout(() => {{
                const btn = document.querySelector('[data-testid="stChatInputSubmitButton"]');
                if (btn) {{
                    btn.click();
                    console.log('Submitted:', {repr(text)});
                }}
            }}, 200);
        }}
    """)

def get_last_reply_time():
    last = window.evaluate_js("""
        const el = document.getElementById('last-reply-time');
        el ? parseInt(el.textContent) : 0;
    """) or 0
    return last or int(time.time())

def idle_monitor():
    last_trigger_time = 0
    while True:
        time.sleep(5)
        try:
            now = time.time()
            if now - last_trigger_time < 120: continue
            last_reply = get_last_reply_time()
            if now - last_reply > 1800:
                print('[Idle Monitor] Detected idle state, injecting task...')
                inject("[AUTO]🤖 用户已经离开超过30分钟，作为自主智能体，请阅读自动化sop，执行自动任务。")
                last_trigger_time = now
        except Exception as e:
            print(f'[Idle Monitor] Error: {e}')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('port', nargs='?', default='8501')
    parser.add_argument('--no-tg', action='store_true', help='不启动 Telegram Bot')
    parser.add_argument('--no-scheduler', action='store_true', help='不启动计划任务调度器')
    args = parser.parse_args()
    port = args.port
    t = threading.Thread(target=start_streamlit, args=(port,), daemon=True)
    t.start()

    if not args.no_tg:
        tgproc = subprocess.Popen([sys.executable, "tgapp.py"], creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        atexit.register(tgproc.kill)
        print('[Launch] Telegram Bot started')
    else: print('[Launch] Telegram Bot disabled (--no-tg)')
    
    if not args.no_scheduler:
        # 使用假端口检测单例
        import socket
        scheduler_port = 65432
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', scheduler_port))
            sock.listen(1)
            # 绑定成功，启动调度器
            scheduler_proc = subprocess.Popen([sys.executable, "agentmain.py"], creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            atexit.register(lambda: (scheduler_proc.kill(), sock.close()))
            print('[Launch] Task Scheduler started')
        except OSError:
            print('[Launch] Task Scheduler already running (port occupied)')
    else: print('[Launch] Task Scheduler disabled (--no-scheduler)')

    monitor_thread = threading.Thread(target=idle_monitor, daemon=True)
    monitor_thread.start()
    if os.name == 'nt':
        screen_width = get_screen_width()
        x_pos = screen_width - WINDOW_WIDTH - RIGHT_PADDING
    else: x_pos = 100
    time.sleep(2) 
    window = webview.create_window(
        title='GenericAgent', 
        url=f'http://localhost:{port}',
        width=WINDOW_WIDTH, height=WINDOW_HEIGHT,
        x=x_pos, y=TOP_PADDING,
        resizable=True, text_select=True
    )
    webview.start()