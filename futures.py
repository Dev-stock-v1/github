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
    ts = d + pd.to_timedelta(hh * 3600 + mm * 60 + ss, unit='s')
    night, post = (hh >= 15) | (hh < 6), hh < 6
    dayd = d[~night].max() if (~night).any() else d.min()
    shift = post & (d == dayd)                                  # 盤後跨午夜列若沿用交易日標示，實際日期要 +1 天
    ts = ts + pd.to_timedelta(shift.astype(int), unit='D')
    tdate = d - pd.to_timedelta((post & ~shift).astype(int), unit='D')
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
