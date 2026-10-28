import json, sys
from datetime import datetime
from zoneinfo import ZoneInfo
from string import Template
import os
import numpy as np, pandas as pd
os.makedirs('docs', exist_ok=True)
NOW = datetime.now(ZoneInfo('Asia/Taipei'))
C = json.load(open('config.json', encoding='utf-8'))
OFF = '--offline' in sys.argv
TZ = 'Asia/Taipei'

def clean(df, intra):
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df[['Open', 'High', 'Low', 'Close']].dropna()
    ix = pd.to_datetime(df.index)
    if intra: ix = (ix.tz_localize('UTC') if ix.tz is None else ix).tz_convert(TZ).tz_localize(None)
    elif ix.tz is not None: ix = ix.tz_localize(None)
    df.index = ix
    return df[~df.index.duplicated()].sort_index()

def csv(name):
    d = pd.read_csv('sample/' + name, skiprows=[1, 2])
    d = d.rename(columns={d.columns[0]: 'Date'}).set_index('Date')
    d.index = pd.to_datetime(d.index, utc=True)
    return d

def get(kind):
    if OFF:
        fs = {'1d': ['twii_1d.csv'], '60m': ['twii_60m.csv'], '5m': ['twii_5m.csv', 'twii_5m__1_.csv']}[kind]
        df = pd.concat([csv(f) for f in fs]); df = df[~df.index.duplicated()]
    else:
        import yfinance as yf
        p = {'1d': ('3y', '1d'), '60m': ('2y', '60m'), '5m': ('30d', '5m')}[kind]
        df = yf.download('^TWII', period=p[0], interval=p[1], auto_adjust=False, progress=False)
    return clean(df, kind != '1d')

def verdict(c, ma60):
    v = C['v']
    if c > v['invalid']: return '計數失效', '收盤站上 B 浪高點，需重新計數'
    if c > v['alt']: return '替代路徑', '站回 48,341 以上，轉強情境'
    if c > v['w4']: return '⑤浪失敗，反彈延續', '站回 ④/② 高點，看 48,005、48,469'
    if c < v['main']: return '接近主目標', '進入 41,100～41,250'
    if c <= v['t1hi']: return '第一目標區', '已到 43,500～44,500'
    if c < v['plat']: return 'C③ 主跌段', '收破平台下緣，看 44,500、41,200'
    if c < C['ref_low']: return '跌破⑤浪低點', '看 45,460、半年線'
    if c < ma60: return '季線下方整理', '⑤浪低點觀察中，站回季線才轉強'
    return '站回季線，反彈延續', '下一站 46,585、47,300'

CIRC = {'①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5}
WARN = []

def wave_check(wl, start=None):
    """規則1：③不能比①、⑤短。規則2：①>③>⑤（大中小）→ 易拉回至少到①高～②低區間，可破②低。"""
    lab = [CIRC.get(nm) for _, _, nm in wl]
    if 1 not in lab: return None
    i1 = lab.index(1)
    p0 = wl[i1 - 1][1] if i1 > 0 else start
    if p0 is None: return None
    pr = {}
    for i, k in enumerate(lab):
        if k and k not in pr and i >= i1: pr[k] = wl[i][1]
    g = lambda a, b: abs(pr[a] - pr[b]) if a in pr and b in pr else None
    L1 = abs(pr[1] - p0); L3 = g(3, 2); L5 = g(5, 4)
    v1 = L3 is not None and L5 is not None and L3 < L1 and L3 < L5
    z = (pr[1], pr[2]) if 2 in pr and L3 is not None and L5 is not None and L1 > L3 > L5 else None
    return {'v1': v1, 'z': z}

def chart(df, cf, ma60=None, shift=0, proj=True, alt_op=0.4):
    n, ah = cf['n'], cf['ahead']; x = df.tail(n).reset_index()
    W, H, L, R, T, B = 400, 430, 6, 58, 12, 34
    tot = n + ah; X = lambda i: L + (i + .5) / tot * (W - L - R)
    last = float(x.Close.iloc[-1])
    pr = [x.High.max(), x.Low.min()] + ([p + shift for _, p in cf['main'] + cf['alt']] if proj else [])
    lo, hi = min(pr) - 80, max(pr) + 80
    Y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    t0 = x.iloc[:, 0]
    s = ''
    if 'night' in x:
        i = 0
        while i < len(x):
            if x.night[i]:
                j = i
                while j + 1 < len(x) and x.night[j + 1]: j += 1
                s += f'<rect x="{X(i)-.7:.1f}" y="{T}" width="{X(j)-X(i)+1.4:.1f}" height="{H-B-T}" fill="var(--mut)" opacity=".13"/>'
                i = j
            i += 1
    lv = [[p + shift, nm] for p, nm in cf['levels']] + ([[ma60 + shift, '季線']] if ma60 else [])
    for p, nm in lv:
        if lo < p < hi:
            s += f'<line x1="{L}" x2="{W-R}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="var(--line)" stroke-dasharray="3 3"/><text x="{W-R+3}" y="{Y(p)+3:.1f}" font-size="9" fill="var(--mut)">{p:,.0f} {nm}</text>'
    for i, r in x.iterrows():
        c = 'var(--up)' if r.Close >= r.Open else 'var(--dn)'
        s += f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r.High):.1f}" y2="{Y(r.Low):.1f}" stroke="{c}" stroke-width=".8"/><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r.Open,r.Close)):.1f}" y2="{Y(min(r.Open,r.Close))+.6:.1f}" stroke="{c}" stroke-width="{max(1.2,(W-L-R)/tot*.7):.1f}"/>'
    dk = pd.to_datetime(x['tdate']) if 'tdate' in x else t0.dt.normalize()
    if cf.get('xmode') == 'month':
        for i in range(len(x)):
            if i == 0 or dk[i].month != dk[i-1].month:
                s += f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{T}" y2="{H-B}" stroke="var(--line)" stroke-width=".6"/>'
                s += f'<text x="{max(X(i), 14):.1f}" y="{H-12}" font-size="10" font-weight="700" fill="var(--tx)" text-anchor="middle">{dk[i].month}月</text>'
    else:
        days = [i for i in range(len(x)) if i == 0 or dk[i] != dk[i-1]]
        ev = cf.get('tick_every', 1); pm = None
        for k, i in enumerate(days):
            s += f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{T}" y2="{H-B}" stroke="var(--line)" stroke-width=".6"/>'
            if (len(days) - 1 - k) % ev: continue
            s += f'<text x="{X(i):.1f}" y="{H-19}" font-size="10" fill="var(--mut)" text-anchor="middle">{dk[i].day}</text>'
            if dk[i].month != pm:
                pm = dk[i].month
                s += f'<text x="{max(X(i), 16):.1f}" y="{H-6}" font-size="10" font-weight="700" fill="var(--tx)" text-anchor="middle">{pm}月</text>'
    xn = X(len(x) - 1)
    s += f'<line x1="{xn:.1f}" x2="{xn:.1f}" y1="{T}" y2="{H-B}" stroke="var(--mut)" stroke-dasharray="2 3"/>'
    for pts, col, op in (((cf['alt'], 'var(--gray)', alt_op), (cf['main'], 'var(--main)', 1)) if proj else ()):
        q = [(len(x) - 1, last)] + [(len(x) - 1 + k, p) for k, p in pts]
        s += f'<polyline fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="2" stroke-dasharray="5 4" points="' + ' '.join(f'{X(i):.1f},{Y(p):.1f}' for i, p in q) + '"/>'
    wl = cf['waves_big'] if cf.get('show_big') and cf.get('waves_big') else cf['waves']
    ck = wave_check([(t, p, nm) for t, p, nm in wl], cf.get('w_start'))
    if ck and ck['v1']: WARN.append(f"{cf.get('title', '')}：③短於①與⑤，違反規則")
    if ck and ck['z']:
        y1, y2 = Y(max(ck['z']) + shift), Y(min(ck['z']) + shift)
        s += f'<rect x="{L}" y="{y1:.1f}" width="{W-L-R}" height="{y2-y1:.1f}" fill="var(--gray)" opacity=".18"/><text x="{L+3}" y="{y1+11:.1f}" font-size="9" fill="var(--mut)">拉回區（①高～②低，可破②低）</text>'
    w = []
    for t, p, nm in (cf['waves_big'] if cf.get('show_big') and cf.get('waves_big') else cf['waves']):
        t = pd.Timestamp(t)
        if t0.iloc[0] <= t <= t0.iloc[-1] + pd.Timedelta(minutes=30): w.append((max(0, int(t0.searchsorted(t, side='right')) - 1), p + shift, nm))
    if w:
        s += '<polyline fill="none" stroke="var(--tx)" stroke-width="1.6" points="' + ' '.join(f'{X(i):.1f},{Y(p):.1f}' for i, p, _ in w) + '"/>'
        for k, (i, p, nm) in enumerate(w):
            nb = [w[j][1] for j in (k - 1, k + 1) if 0 <= j < len(w)]
            up = all(p >= v for v in nb)
            s += f'<text x="{X(i):.1f}" y="{Y(p)+(-6 if up else 13):.1f}" font-size="12" font-weight="700" fill="var(--tx)" text-anchor="middle">{nm}</text>'
    s += f'<circle cx="{xn:.1f}" cy="{Y(last):.1f}" r="3" fill="var(--main)"/>'
    return f'<svg viewBox="0 0 {W} {H}" role="img">{s}</svg>'

D, H, M = get('1d'), get('60m'), get('5m')
if OFF:
    h = M.resample('1h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
    H = pd.concat([H, h[h.index > H.index[-1]]])
ma60 = float(D.Close.rolling(60).mean().iloc[-1])
price = float(M.Close.iloc[-1]) if len(M) else float(D.Close.iloc[-1])
vt, vx = verdict(price, ma60)
if C.get('alt_strength') is not None: alt_s = float(C['alt_strength'])
else:
    alt_s = 0.2 + 0.15 * (price > ma60) + 0.15 * (price > C.get('alt_t1', 46585)) + 0.25 * (price > C['v']['w4']) + 0.25 * (price > C['v']['alt'])
alt_s = min(1.0, alt_s); alt_op = round(0.25 + 0.75 * alt_s, 2)
try:
    import mis, futures
    st = mis.load_store()
    if not OFF:
        st = mis.merge(st, mis.collect(log=print))
        if mis.sessions(st) < 6:                                  # 歷史不足時，用逐筆檔回補（失敗不影響）
            try: st = mis.merge(mis.merge(st.iloc[0:0], futures.load_1m(list(D.index[-C.get('tick_days', 8):]), False)), st)
            except Exception as e: print('futures 回補失敗：', e)
        if len(st): mis.save_store(st)
    if st.empty: raise RuntimeError('尚無期貨資料（MIS 與逐筆檔都取不到）')
    f5, f60 = mis.bars(st, 5), mis.bars(st, 60)
    td = f5[f5.night].tdate.max(); dd = f5[(f5.tdate == td) & ~f5.night]; nn = f5[(f5.tdate == td) & f5.night]
    try: basis = float(dd.Close.iloc[-1] - D.Close.loc[td]) if len(dd) and td in D.index else 0.0
    except Exception: basis = 0.0
    strip = f'最新 {f5.Close.iloc[-1]:,.0f}｜期現價差約 {basis:+,.0f}（圖上價位已平移）'
    if len(nn) and len(dd): strip += f'｜{td:%m/%d} 夜盤 收 {nn.Close.iloc[-1]:,.0f}（較日盤收 {nn.Close.iloc[-1]-dd.Close.iloc[-1]:+,.0f}），高 {nn.High.max():,.0f} 低 {nn.Low.max() and nn.Low.min():,.0f}'
    cf60 = {**C['chart60'], **C.get('chartF60', {})}; cf5 = {**C['chart5'], **C.get('chartF5', {})}
    cf60 = chart(f60, cf60, ma60, basis, False); cf5 = chart(f5, cf5, ma60, basis, False)
except Exception as e:
    strip = f'期貨資料暫時取不到：{e}'; cf60 = cf5 = '<p class="m">尚無資料</p>'
html = Template(open('template.html', encoding='utf-8').read()).substitute(
    vt=vt, vx=vx, price=f'{price:,.0f}', upd=NOW.strftime('%Y-%m-%d %H:%M'),
    c60=chart(H, C['chart60'], ma60, alt_op=alt_op), cd=chart(D, C['chartD'], ma60, alt_op=alt_op), alt=f'{alt_s*100:.0f}',
    n60=C['chart60']['names'][0] + '（橘色）／' + C['chart60']['names'][1] + '（灰色）', nd=C['chartD']['names'][0] + '（橘色）／' + C['chartD']['names'][1] + '（灰色）',
    strip=strip, f60=cf60, f5=cf5, warn=''.join(f'　⚠ {w}' for w in WARN))
open('docs/index.html', 'w', encoding='utf-8').write(html)
json.dump({'price': price, 'verdict': vt, 'updated': NOW.isoformat()}, open('docs/data.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('ok', vt, round(price))
