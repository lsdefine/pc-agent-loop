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
        # GetSystemMetrics(0) 获取主屏幕宽度
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0)
    except:
        # 如果不是 Windows 或者出错了，返回一个兜底值 (比如 1920)
        return 1920

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

if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else "8501"
    t = threading.Thread(target=start_streamlit, args=(port,), daemon=True)
    t.start()
    if os.name == 'nt':
        screen_width = get_screen_width()
        x_pos = screen_width - WINDOW_WIDTH - RIGHT_PADDING
    else: x_pos = 100
    time.sleep(2) 
    webview.create_window(
        title='GenericAgent', 
        url=f'http://localhost:{port}',
        width=WINDOW_WIDTH, 
        height=WINDOW_HEIGHT,
        x=x_pos, y=TOP_PADDING,
        resizable=True,
        text_select=True
    )
    webview.start()