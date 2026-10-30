"""台指期（TX）逐筆成交 → 5分K / 60分K（含夜盤）。資料來源：期交所『前30個交易日期貨每筆成交資料』。"""
import io, glob, zipfile
import pandas as pd

URLS = ['https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Daily_{y}_{m}_{d}.zip',
        'https://www.taifex.com.tw/DailyDownload/Daily_{y}_{m}_{d}.zip']

def fetch_zip(date, offline):
    if offline:
        for p in glob.glob(f'sample/futures/Daily_{date:%Y_%m_%d}.zip'):
            return open(p, 'rb').read()
        return None
    import requests
    for u in URLS:
        url = u.format(y=f'{date:%Y}', m=f'{date:%m}', d=f'{date:%d}')
        for _ in range(2):
            try:
                r = requests.get(url, timeout=90, headers={'User-Agent': 'Mozilla/5.0'})
                if r.status_code == 200 and r.content[:2] == b'PK': return r.content
                break
            except Exception: pass
    return None

def parse(raw):
    z = zipfile.ZipFile(io.BytesIO(raw)); b = z.read(z.namelist()[0])
    for enc in ('cp950', 'utf-8-sig'):
        try: txt = b.decode(enc); break
        except UnicodeDecodeError: pass
    df = pd.read_csv(io.StringIO(txt), dtype=str, usecols=range(6))
    df.columns = ['d', 'p', 'm', 't', 'px', 'q']
    df = df.apply(lambda s: s.str.strip())
    df = df[(df.p == 'TX') & df.m.str.fullmatch(r'\d{6}', na=False)].copy()
    if df.empty: return df
    df['px'] = pd.to_numeric(df.px, errors='coerce'); df['q'] = pd.to_numeric(df.q, errors='coerce').fillna(0)
    df = df.dropna(subset=['px'])
    df = df[df.m == df.groupby('m').q.sum().idxmax()]          # 取成交量最大的月份合約（近月）
    d = pd.to_datetime(df.d, format='%Y%m%d'); t = df.t.str.zfill(6)
    hh, mm, ss = t.str[:2].astype(int), t.str[2:4].astype(int), t.str[4:6].astype(int)
    night, post = (hh >= 15) | (hh < 6), hh < 6
    pre = night & ~post
    dayd = d[~night].max() if (~night).any() else d.max()
    # 成交日期若是「交易日」（盤後列與日盤同日），跨午夜列要 +1 天；若已是實際日曆日（夜盤前段早一天）則不動
    trading_label = bool(pre.any() and d[pre].max() >= dayd) or (not pre.any() and bool((post & (d == dayd)).any()))
    ts = d + pd.to_timedelta(hh * 3600 + mm * 60 + ss, unit='s') + pd.to_timedelta((post & trading_label).astype(int), unit='D')
    tdate = (ts - pd.to_timedelta(post.astype(int), unit='D')).dt.normalize()   # 場次開始日（夜盤跨午夜列歸前一日曆日）
    start = tdate + pd.to_timedelta(night.map({True: 15 * 3600, False: 8 * 3600 + 45 * 60}), unit='s')
    return pd.DataFrame({'ts': ts, 'px': df.px, 'q': df.q, 'night': night, 'tdate': tdate, 'start': start}).sort_values('ts', kind='stable')

def bars(ticks, minutes):
    g = ((ticks.ts - ticks.start).dt.total_seconds() // (minutes * 60)).clip(lower=0)
    ticks = ticks.assign(bt=ticks.start + pd.to_timedelta(g * minutes, unit='m'))
    b = ticks.groupby('bt', sort=True).agg(Open=('px', 'first'), High=('px', 'max'), Low=('px', 'min'),
                                           Close=('px', 'last'), Vol=('q', 'sum'), night=('night', 'first'), tdate=('tdate', 'first'))
    b.index.name = 'bt'
    return b

def load(dates, offline):
    parts = []
    for dt in dates:
        raw = fetch_zip(dt, offline)
        if raw is None: print('futures: no file', f'{dt:%Y-%m-%d}'); continue
        p = parse(raw); print('futures:', f'{dt:%Y-%m-%d}', len(p), 'ticks'); parts.append(p)
    if not parts: raise RuntimeError('取不到任何期貨逐筆檔（網址或網路問題）')
    t = pd.concat(parts).drop_duplicates(['ts', 'px', 'q']).sort_values('ts', kind='stable')
    return bars(t, 5), bars(t, 60)

def load_1m(dates, offline):
    """逐筆檔 → 1 分K（供回補歷史用，格式與 mis.py 的 store 相同）。"""
    parts = []
    for dt in dates:
        raw = fetch_zip(dt, offline)
        if raw is None: continue
        p = parse(raw)
        if len(p): parts.append(p)
    if not parts: return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
    t = pd.concat(parts).drop_duplicates(['ts', 'px', 'q']).sort_values('ts', kind='stable')
    g = t.groupby(t.ts.dt.floor('min')).agg(open=('px', 'first'), high=('px', 'max'), low=('px', 'min'), close=('px', 'last'), volume=('q', 'sum'))
    g.index.name = 'datetime'
    return g
