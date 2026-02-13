import os, sys, re, threading, asyncio, queue as Q, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agentmain import GeneraticAgent
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import mykey

agent = GeneraticAgent()
agent.verbose = False
ALLOWED = set(getattr(mykey, 'tg_allowed_users', []))

_TAG_PATS = [r'<' + t + r'>.*?</' + t + r'>' for t in ('thinking', 'summary', 'tool_use')]
_TAG_PATS.append(r'<file_content>.*?</file_content>')

def _clean(t):
    for p in _TAG_PATS:
        t = re.sub(p, '', t, flags=re.DOTALL)
    return re.sub(r'\n{3,}', '\n\n', t).strip() or '...'

import html as _html
def _inline_md(s):
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s
def _to_html(t):
    parts, pos = [], 0
    for m in re.finditer(r'(`{3,})(?:\w*\n)?([\s\S]*?)\1', t):
        parts.append(_inline_md(_html.escape(t[pos:m.start()])))
        parts.append('<pre><code>' + _html.escape(m.group(2)) + '</code></pre>')
        pos = m.end()
    parts.append(_inline_md(_html.escape(t[pos:])))
    return ''.join(parts)

async def _stream(dq, msg):
    last_text = ""
    while True:
        await asyncio.sleep(3)
        item = None
        try:
            while True: item = dq.get_nowait()
        except Q.Empty: pass
        if item is None: continue
        raw = item.get("done") or item.get("next", "")
        done = "done" in item
        show = _clean(raw)
        if len(show) > 4000:
            # freeze current msg, start a new one
            try: msg = await msg.reply_text("(continued...)")
            except Exception: pass
            last_text = ""
            show = show[-3900:]
        display = show if done else show + " ⏳"
        if display != last_text:
            try: await msg.edit_text(_to_html(display), parse_mode='HTML')
            except Exception:
                try: await msg.edit_text(display)
                except Exception: pass
            last_text = display
        if done: break

async def handle_msg(update, ctx):
    uid = update.effective_user.id
    if ALLOWED and uid not in ALLOWED:
        return await update.message.reply_text("no")
    msg = await update.message.reply_text("thinking...")
    dq = agent.put_task(update.message.text, source="telegram")
    await _stream(dq, msg)

async def cmd_abort(update, ctx):
    agent.abort()
    await update.message.reply_text("Aborted")

async def cmd_llm(update, ctx):
    args = (update.message.text or '').split()
    if len(args) > 1:
        try:
            n = int(args[1])
            agent.next_llm(n)
            await update.message.reply_text(f"Switched to [{agent.llm_no}] {agent.get_llm_name()}")
        except (ValueError, IndexError):
            await update.message.reply_text(f"Usage: /llm <0-{len(agent.list_llms())-1}>")
    else:
        lines = [f"{'→' if cur else '  '} [{i}] {name}" for i, name, cur in agent.list_llms()]
        await update.message.reply_text("LLMs:\n" + "\n".join(lines))

if __name__ == '__main__':
    # Single instance lock using socket
    try:
        _lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); _lock_sock.bind(('127.0.0.1', 19527))
    except OSError: sys.exit('Another instance is already running.')
    if not ALLOWED: sys.exit('ERROR: tg_allowed_users in mykey.py is empty or missing. Set it to avoid unauthorized access.')
    threading.Thread(target=agent.run, daemon=True).start()
    proxy = vars(mykey).get('proxy', 'http://127.0.0.1:2082')
    app = ApplicationBuilder().token(mykey.tg_bot_token).proxy(proxy).get_updates_proxy(proxy).build()
    app.add_handler(CommandHandler("stop", cmd_abort))
    app.add_handler(CommandHandler("llm", cmd_llm))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    print("TG bot running...")
    app.run_polling()
