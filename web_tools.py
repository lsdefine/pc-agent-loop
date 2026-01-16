import sys, os, re
import pyperclip
import json, time
import subprocess
import tempfile
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simphtml import get_main_block, start_temp_monitor, get_temp_texts, find_changed_elements, optimize_html_for_tokens
from simphtml import js_findMainContent, js_findMainList
from bs4 import BeautifulSoup

def get_html(driver, cutlist=False, maxchars=28000, instruction=""):
    page = get_main_block(driver)
    soup = optimize_html_for_tokens(page)
    html = str(soup)
    if not cutlist or len(html) <= maxchars: return html
    rr = driver.execute_js(js_findMainList + js_findMainContent + """
        return findMainList(findMainContent(document.body));""")
    sel = rr.get("selector", None)
    if not sel: return html[:maxchars]
    s = BeautifulSoup(str(soup), "html.parser"); items = s.select(sel)
    hit = [it for it in items if instruction and instruction.strip() and instruction in it.get_text(" ",strip=True)]
    keep = hit[:6] if hit else items[:3]
    for it in items:
        if it not in keep: it.decompose()
    s = optimize_html_for_tokens(s)
    return str(s)[:maxchars]

def execute_js_rich(script, driver):
    start_temp_monitor(driver) 
    curr_session = driver.default_session_id
    last_html = get_html(driver)
    result = None;  error_msg = None
    new_tab = False;  reloaded = False
    try:
        print(f"⚡ Executing: {script[:250]} ...")
        result = driver.execute_js(script, auto_switch_newtab=True)
        if type(result) is dict and result.get('closed', 0) == 1: reloaded = True
        time.sleep(2) 
    except Exception as e:
        error = e.args[0] if e.args else str(e)
        if isinstance(error, dict): error.pop('stack', None)
        error_msg = str(error)
        print(f"❌ Error: {error_msg}")

    transients = get_temp_texts(driver)

    if driver.default_session_id != curr_session:
        curr_session = driver.latest_session_id
        print('Session changed')
        new_tab = True
    
    current_html = get_html(driver)
    diff_summary = "无需对比 (报错)"
    is_significant_change = False
    if not error_msg:
        diff_data = find_changed_elements(last_html, current_html)
        change_count = diff_data.get('changed', 0)
        diff_summary = f"DOM变化量: {change_count}"
        if change_count < 5 and not transients and not new_tab:
            diff_summary += " (页面几乎无静默变化)"
        else:
            is_significant_change = True
    return {
        "status": "failed" if error_msg else "success",
        "js_return": result,
        "error": error_msg,
        "transients": transients, 
        "environment": {
            "new_tab": new_tab,
            "reloaded": reloaded
        },
        "diff": diff_summary,
        "suggestion": "" if is_significant_change else "页面无明显变化"
    }
