import json, threading, time, uuid, queue, socket, requests
from typing import Dict, Any, Optional, List  
from simple_websocket_server import WebSocketServer, WebSocket  
from bs4 import BeautifulSoup  
import bottle, random
from bottle import route, template, request, response

class Session:
    def __init__(self, session_id, info, client=None):
        self.id = session_id
        self.info = info
        self.connect_at = time.time()
        self.disconnect_at = None
        self.type = info.get('type', 'ws')
        self.ws_client = client if self.type == 'ws' else None
        self.http_queue = client if self.type == 'http' else None
    @property
    def url(self): return self.info.get('url', '')
    def is_active(self):
        return self.disconnect_at is None
    def reconnect(self, client, info):
        self.info = info
        self.type = info.get('type', 'ws')
        if self.type == 'ws':
            self.ws_client = client
            self.http_queue = None
        elif self.type == 'http':
            self.http_queue = client
        self.connect_at = time.time()
        self.disconnect_at = None
    def mark_disconnected(self):
        self.disconnect_at = time.time()


class TMWebDriver:  
    def __init__(self, host: str = 'localhost', port: int = 18765):  
        self.host = host  
        self.port = port  
        self.sessions = {}
        self.results = {}

        self.default_session_id = None  
        self.latest_session_id = None  
        self.last_cmd_time = 0
        self.is_remote = socket.socket().connect_ex((host, port+1)) == 0
        if not self.is_remote:  
            self.start_ws_server()  
            self.start_http_server()
        else:
            self.remote = f'http://{self.host}:{self.port+1}/link'

    def start_http_server(self):
        self.app = app = bottle.Bottle()

        @app.route('/api/longpoll', method=['GET', 'POST'])
        def long_poll():
            data = request.json
            session_id = data.get('sessionId')  
            session_info = {'url': data.get('url'), 'title': data.get('title', ''), 'type': 'http'}  
            if session_id not in self.sessions: 
                session = Session(session_id, session_info, queue.Queue())
                print(f"Browser http connected: {session.url} (Session: {session_id})")  
                self.sessions[session_id] = session
            session = self.sessions[session_id]
            session.disconnect_at = None
            if session.type == 'http': msgQ = session.http_queue
            else: return json.dumps({"id": "", "ret": "use ws"})
            start_time = time.time()
            while time.time() - start_time < 5:
                try: return msgQ.get(timeout=0.2)
                except queue.Empty: continue
            return json.dumps({"id": "", "ret": "next long-poll"})

        @app.route('/api/result', method=['GET','POST'])
        def result():
            data = request.json
            if data.get('type') == 'result':  
                self.results[data.get('id')] = {'success': True, 'data': data.get('result'), 'newTabs': data.get('newTabs', [])}  
            elif data.get('type') == 'error':  
                self.results[data.get('id')] = {'success': False, 'data': data.get('error')}  
            return 'ok'

        @app.route('/link', method=['GET','POST'])
        def link():
            data = request.json
            if data.get('cmd') == 'get_all_sessions': return json.dumps({'r': self.get_all_sessions()}, ensure_ascii=False)  
            if data.get('cmd') == 'find_session': 
                url_pattern = data.get('url_pattern', '')
                return json.dumps({'r': self.find_session(url_pattern)}, ensure_ascii=False)
            if data.get('cmd') == 'execute_js':
                session_id = data.get('sessionId')
                code = data.get('code')
                timeout = float(data.get('timeout', 10.0))
                auto_switch_newtab = data.get('auto_switch_newtab', False)
                try:
                    result = self.execute_js(code, timeout=timeout, session_id=session_id, auto_switch_newtab=auto_switch_newtab)
                    print('remote', result)
                    newTabs = result.get('newTabs', []) if isinstance(result, dict) else []
                    return json.dumps({'result': result, 'newTabs': newTabs}, ensure_ascii=False)
                except Exception as e:
                    return json.dumps({'error': str(e)}, ensure_ascii=False)
            return 'ok'

        def run(): 
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            bottle.run(app, host=self.host, port=self.port+1, server='tornado', threads=20)

        http_thread = threading.Thread(target=run)  
        http_thread.daemon = True  
        http_thread.start()  

    def clean_sessions(self):
        sids = list(self.sessions.keys())
        for sid in sids:
            session = self.sessions[sid]
            if not session.is_active() and time.time() - session.disconnect_at > 600:
                del self.sessions[sid]
    
    def start_ws_server(self) -> None:  
        driver = self  
        class JSExecutor(WebSocket):  
            def handle(self) -> None:  
                try:  
                    data = json.loads(self.data)  
                    if data.get('type') == 'ready':  
                        session_id = data.get('sessionId')  
                        session_info = {'url': data.get('url'), 'title': data.get('title', ''),
                            'connected_at': time.time(), 'type': 'ws'}  
                        driver._register_client(session_id, self, session_info)  
                    elif data.get('type') in 'result':  
                        driver.results[data.get('id')] = {'success': True, 'data': data.get('result'), 'newTabs': data.get('newTabs', [])}  
                    elif data.get('type') == 'error':  
                        driver.results[data.get('id')] = {'success': False, 'data': data.get('error')}  
                except Exception as e:  
                    print(f"Error handling message: {e}")  
                    if hasattr(self, 'data'): print(self.data)  
            def connected(self): (f"New connection from {self.address}")  
            def handle_close(self): driver._unregister_client(self)  
        
        self.server = WebSocketServer(self.host, self.port, JSExecutor)  
        server_thread = threading.Thread(target=self.server.serve_forever)  
        server_thread.daemon = True  
        server_thread.start()  
        print(f"WebSocket server running on ws://{self.host}:{self.port}")  
    
    def _register_client(self, session_id: str, client: WebSocket, session_info) -> None:  
        is_new_session = session_id not in self.sessions

        if is_new_session:
            session = Session(session_id, session_info, client)
            self.sessions[session_id] = session            
            print(f"New tab connected: {session.url} (Session: {session_id})")  
        else:
            session = self.sessions[session_id]
            session.reconnect(client, session_info)
            print(f"Tab reconnected: {session.url} (Session: {session_id})")  

        self.latest_session_id = session_id
        if self.default_session_id is None: 
            self.default_session_id = session_id  
        elif is_new_session:  
            if time.time() - self.last_cmd_time < 5.0:  
                print(f"检测到脚本触发的新窗口，自动切换焦点: {session_id}")
                self.default_session_id = session_id

    
    def _unregister_client(self, client: WebSocket) -> None:  
        for session in self.sessions.values():
            if session.ws_client == client:
                session.mark_disconnected()
                break  
    
    def execute_js(self, code, timeout=10.0, session_id=None, auto_switch_newtab=False) -> Any:  
        if session_id is None: session_id = self.default_session_id  
        if self.is_remote:
            print('remote_execute_js')
            response = self._remote_cmd({"cmd": "execute_js", "sessionId": session_id, 
                                         "code": code, "timeout": str(timeout), 
                                         "auto_switch_newtab": auto_switch_newtab})
            if response.get('error'): raise Exception(response['error'])
            if auto_switch_newtab and 'newTabs' in response:
                newtabs = response.get('newTabs', [])
                if len(newtabs) > 0:
                    new_session_id = newtabs[0]['sessionId']
                    self.default_session_id = new_session_id
                    print(f"自动切换到新标签会话: {new_session_id}")
            return response.get('result', None)
 
        session = self.sessions.get(session_id)
        if not session or not session.is_active(): 
            time.sleep(3)
            session = self.sessions.get(session_id)
            if not session or not session.is_active(): 
                alive_sessions = [s for s in self.sessions.values() if s.is_active()]
                if alive_sessions:
                    session = alive_sessions[0]  
                    print(f"会话 {session_id} 未连接，自动切换到最新活动会话: {session.id}")
                    session_id = self.default_session_id = session.id
                if not session or not session.is_active(): 
                    breakpoint()
                    raise ValueError(f"会话ID {session_id} 未连接")  

        tp = session.type
        assert tp in ['ws', 'http'], f"Unsupported session type: {tp}"
        exec_id = str(uuid.uuid4())  
        payload = json.dumps({'id': exec_id, 'code': code, 'auto_switch_newtab': auto_switch_newtab})

        if tp == 'ws':        
            session.ws_client.send_message(payload)  
        elif tp == 'http':
            session.http_queue.put(payload)

        start_time = time.time()  
        self.clean_sessions() 
        hasjump = False

        while exec_id not in self.results:  
            time.sleep(0.1)  
            if tp == 'ws':
                if not session.is_active(): hasjump = True
                if hasjump and session.is_active():
                    if not self.is_remote and auto_switch_newtab: self.last_cmd_time = time.time()
                    return {"result": f"Session {session_id} reloaded.", "closed":1}
            if time.time() - start_time > timeout + 10:  
                if tp == 'ws':
                    return {"result": f"No response data in {timeout}s"}
                elif tp == 'http':
                    return {"result": f"Session {session_id} no response."}
        
        result = self.results.pop(exec_id)  
        if not result['success']: raise Exception(result['data'])  
        if not self.is_remote and auto_switch_newtab:
            newtabs = result.get('newTabs', [])
            if len(newtabs) > 0:
                new_session_id = newtabs[0]['sessionId']
                self.default_session_id = new_session_id
                print(f"自动切换到新标签会话: {new_session_id}")
        elif not self.is_remote:
            self.last_cmd_time = time.time()
        return result['data']  
    
    def _remote_cmd(self, cmd):
        resp = requests.post(self.remote, 
            headers={"Content-Type": "application/json"},
            json=cmd).json()
        return resp

    def get_all_sessions(self):  
        if self.is_remote:
            return self._remote_cmd({"cmd": "get_all_sessions"}).get('r', [])
        return [{'id': session.id, **session.info} for session in self.sessions.values()
                if session.is_active()]  

    def get_session_dict(self):
        return {session.id: session.url for session in self.sessions.values() if session.is_active()}
        
    def find_session(self, url_pattern: str):
        if url_pattern == '': 
            session = self.sessions.get(self.latest_session_id)
            return [(session.id, session.info)] if session else []
        matching_sessions = []  
        for session in self.sessions.values():
            if not session.is_active(): continue
            if 'url' in session.info and url_pattern in session.info['url']:  
                matching_sessions.append((session.id, session.info))  
        return matching_sessions

    def set_session(self, url_pattern: str) -> bool:  
        if self.is_remote:
            matched = self._remote_cmd({"cmd": "find_session", "url_pattern": url_pattern}).get('r', [])
        else:
            matched = self.find_session(url_pattern)
        if not matched: return print(f"警告: 未找到URL包含 '{url_pattern}' 的会话")  
        if len(matched) > 1: print(f"警告: 找到多个URL包含 '{url_pattern}' 的会话，选择第一个")  
        self.last_cmd_time = 0
        self.default_session_id, info = matched[0]
        print(f"成功设置默认会话: {self.default_session_id}: {info['url']}")  
        return self.default_session_id  
    
    def jump(self, url, timeout=10): self.execute_js(f"window.location.href='{url}'", timeout=timeout)
    def page_source(self): return self.execute_js("document.documentElement.outerHTML")
    def body(self): return self.execute_js("document.body.outerHTML")
    def newtab(self, url=None):
        if url is None: url = "http://www.baidu.com/robots.txt"
        return self.execute_js(f'GM_openInTab("{url}");', auto_switch_newtab=True)
    
if __name__ == "__main__":
    driver = TMWebDriver(host='localhost', port=18765)