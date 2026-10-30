"""台指期近月 1 分K 批次收集（期交所 MIS）。排程每次執行抓一次，累積存到 data/txf_1m.csv。
已確認（使用者實測）：POST /futures/api/getChartData1M_mem，Payload {"SymbolID": "TXFK6-F"}；
日盤尾碼 -F、夜盤 -M；Ticks 每筆 [HHMMSS, 開, 高, 低, 收, 量]，為 1 分K，標籤是 K 棒終點（讀入時減 1 分鐘）；
_mem 只回最新 2 根。未驗證：getChartData1M（無 _mem）是否回傳整段場次歷史。"""
import os
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd, requests

BASE = 'https://mis.taifex.com.tw/futures/api/'
HEAD = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json;charset=UTF-8', 'Referer': 'https://mis.taifex.com.tw/futures/'}
STORE, MC, STALE_MIN, KEEP_DAYS = 'data/txf_1m.csv', 'ABCDEFGHIJKL', 150, 40
COLS = ['open', 'high', 'low', 'close', 'volume']

def third_wed(y, m):
    d = datetime(y, m, 1); w = d + timedelta(days=(2 - d.weekday()) % 7)
    return (w + timedelta(days=14)).date()

def symbol(now, sess):
    y, m = now.year, now.month; s = third_wed(y, m)
    if now.date() > s or (now.date() == s and now.time() >= dtime(13, 30)):
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"TXF{MC[m - 1]}{y % 10}-{'M' if sess == 'night' else 'F'}"

def label_to_start(t, now):
    hh, mm, ss = int(t[:2]), int(t[2:4]), int(t[4:])
    secs = hh * 3600 + mm * 60 + ss                    # 整點可能寫成 HH6000、午夜 240000，用秒數相加自動進位
    best = None
    for dl in (-1, 0, 1):
        d = (now + timedelta(days=dl)).date()
        c = datetime(d.year, d.month, d.day) + timedelta(seconds=secs)
        if c <= now + timedelta(seconds=90) and (best is None or c > best): best = c
    return pd.Timestamp(best - timedelta(minutes=1))

def fetch(api, sym):
    r = requests.post(BASE + api, json={'SymbolID': sym}, headers=HEAD, timeout=15)
    r.raise_for_status(); j = r.json()
    if j.get('RtCode') != '0': raise RuntimeError(f"{api}: {j.get('RtMsg')}")
    return j['RtData']['Ticks']

def collect(now=None, log=print):
    now = now or datetime.now(ZoneInfo('Asia/Taipei')).replace(tzinfo=None)
    parts = []
    for sess in ('day', 'night'):
        sym = symbol(now, sess)
        for api in ('getChartData1M', 'getChartData1M_mem'):
            try: ticks = fetch(api, sym)
            except Exception as e: log(f'mis: {api} {sym} 失敗：{e}'); continue
            rows = []
            for tk in ticks:
                try: rows.append({'datetime': label_to_start(str(tk[0]).zfill(6), now), 'open': float(tk[1]), 'high': float(tk[2]), 'low': float(tk[3]), 'close': float(tk[4]), 'volume': float(tk[5])})
                except Exception: pass
            if not rows: log(f'mis: {api} {sym} 無資料'); continue
            df = pd.DataFrame(rows).set_index('datetime')
            log(f'mis: {api} {sym} {len(df)} 筆 {df.index.min():%m-%d %H:%M}~{df.index.max():%m-%d %H:%M}')
            if now - df.index.max() > timedelta(minutes=STALE_MIN): log('mis: 資料過舊（休市或已收盤超過2.5小時），略過'); continue
            parts.append(df)
    return pd.concat(parts) if parts else pd.DataFrame(columns=COLS)

def load_store():
    if os.path.exists(STORE): return pd.read_csv(STORE, parse_dates=['datetime'], index_col='datetime')[COLS]
    return pd.DataFrame(columns=COLS)

def merge(old, new):
    x = pd.concat([old[COLS], new[COLS]]); x = x[~x.index.duplicated(keep='last')].sort_index()
    return x[x.index >= x.index.max() - pd.Timedelta(days=KEEP_DAYS)]

def save_store(df):
    os.makedirs(os.path.dirname(STORE), exist_ok=True); df.to_csv(STORE)

def sessions(df):
    if not len(df): return 0
    n, t, _ = _sess(df.index)
    return len(set(zip(t, n)))

def _sess(ix):
    h = ix.hour; night = (h >= 15) | (h < 6); post = h < 6
    tdate = (ix - pd.to_timedelta(post.astype(int), unit='D')).normalize()
    start = tdate + pd.to_timedelta(np.where(night, 15 * 3600, 8 * 3600 + 45 * 60), unit='s')
    return night, tdate, start

def bars(df, minutes):
    night, tdate, start = _sess(df.index)
    g = np.clip(np.asarray(((df.index - start).total_seconds() // (minutes * 60))), 0, None)
    x = df.assign(night=night, tdate=tdate, bt=start + pd.to_timedelta(g * minutes, unit='m'))
    b = x.groupby('bt').agg(Open=('open', 'first'), High=('high', 'max'), Low=('low', 'min'), Close=('close', 'last'),
                            Vol=('volume', 'sum'), night=('night', 'first'), tdate=('tdate', 'first'))
    b.index.name = 'bt'
    return b
