import asyncio
import re
import json
import os
import time
from telethon import TelegramClient, events, functions, errors

API_ID = pass
API_HASH = pass
SESSION = 'anti_login_session'
CFG_FILE = 'anti_cfg.json'

DEFAULT = {"anti_login_enabled": True, "last_reset": 0.0, "min_reset_interval": 3.0}

def load_cfg():
    if not os.path.exists(CFG_FILE):
        return DEFAULT.copy()
    try:
        c = json.load(open(CFG_FILE, 'r', encoding='utf-8'))
        cfg = DEFAULT.copy()
        cfg.update(c)
        return cfg
    except:
        return DEFAULT.copy()

def save_cfg(c):
    try:
        json.dump(c, open(CFG_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    except:
        pass

cfg = load_cfg()
client = TelegramClient(SESSION, API_ID, API_HASH)

CODE_RE = re.compile(r'(\d{4,8})')
BASE_RE = re.compile(r'(?:\banti[\s\-]*logg?in\b|\bantilogg?in\b)', re.IGNORECASE)
CMD_RE = re.compile(r'\b(enable|disable|status|on|off)\b', re.IGNORECASE)
auth_hashes = set()

async def refresh_whitelist():
    global auth_hashes
    try:
        res = await client(functions.account.GetAuthorizationsRequest())
        hs = set()
        for a in getattr(res, 'authorizations', []) or []:
            h = getattr(a, 'hash', None)
            if h is not None:
                try:
                    hs.add(int(h))
                except:
                    hs.add(h)
        auth_hashes = hs
    except:
        auth_hashes = set()

@client.on(events.NewMessage(from_users=777000))
async def on_777(event):
    text = (event.raw_text or "")
    if not text:
        return
    codes = [m.group(1) for m in CODE_RE.finditer(text)]
    if not codes:
        return
    if not cfg.get("anti_login_enabled"):
        try:
            await client.send_message('me', f"Login code received but anti-login is disabled. Message: {text[:200]}")
        except:
            pass
        return
    try:
        await client.send_message('me', "Login code detected. Attempting to invalidate sign-in codes...")
    except:
        pass
    try:
        await client(functions.account.InvalidateSignInCodesRequest(codes=codes))
    except Exception as e:
        try:
            await client.send_message('me', f"Failed to invalidate sign-in codes: {e}")
        except:
            pass
    await asyncio.sleep(0.6)
    try:
        res = await client(functions.account.GetAuthorizationsRequest())
        new_hashes = []
        for a in getattr(res, 'authorizations', []) or []:
            h = getattr(a, 'hash', None)
            if h is None:
                continue
            try:
                h_int = int(h)
            except:
                h_int = h
            if h_int not in auth_hashes:
                new_hashes.append(h_int)
        for h in new_hashes:
            try:
                await client(functions.account.ResetAuthorizationRequest(hash=h))
            except errors.RPCError:
                try:
                    await client.send_message('me', f"Could not reset authorization for hash {h}")
                except:
                    pass
            except:
                pass
        if new_hashes:
            cfg['last_reset'] = time.time()
            save_cfg(cfg)
    except:
        pass
    await refresh_whitelist()

@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    raw = (event.raw_text or "").lower()
    if not raw:
        return
    text = re.sub(r'\s+', ' ', raw.replace('-', ' ')).strip()
    if not BASE_RE.search(text):
        return
    m = CMD_RE.search(text)
    cmd = m.group(1).lower() if m else None
    if cmd is None:
        state = "on" if cfg.get("anti_login_enabled") else "off"
        new = f"Anti-login service is {state}."
    elif cmd in ("enable", "on"):
        cfg["anti_login_enabled"] = True
        save_cfg(cfg)
        new = "Anti-login service enabled"
    elif cmd in ("disable", "off"):
        cfg["anti_login_enabled"] = False
        save_cfg(cfg)
        new = "Anti-login service disabled"
    elif cmd == "status":
        s = "on" if cfg.get("anti_login_enabled") else "off"
        last = time.ctime(cfg.get("last_reset", 0))
        new = f"Anti-login status: {s}\nLast reset: {last}"
    else:
        return
    try:
        await event.edit(new)
    except:
        try:
            await event.respond(new)
        except:
            pass

async def main():
    await client.start()
    await refresh_whitelist()
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
