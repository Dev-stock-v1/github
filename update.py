import json, sys
from datetime import datetime
from string import Template
import os
import numpy as np, pandas as pd
os.makedirs('docs', exist_ok=True)
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

def chart(df, cf, ma60=None):
    n, ah = cf['n'], cf['ahead']; x = df.tail(n).reset_index()
    W, H, L, R, T, B = 400, 430, 6, 58, 12, 34
    tot = n + ah; X = lambda i: L + (i + .5) / tot * (W - L - R)
    last = float(x.Close.iloc[-1])
    pr = [x.High.max(), x.Low.min()] + [p for _, p in cf['main'] + cf['alt']]
    lo, hi = min(pr) - 80, max(pr) + 80
    Y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    t0 = x.iloc[:, 0]
    s = ''
    lv = list(cf['levels']) + ([[ma60, '季線']] if ma60 else [])
    for p, nm in lv:
        if lo < p < hi:
            s += f'<line x1="{L}" x2="{W-R}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="var(--line)" stroke-dasharray="3 3"/><text x="{W-R+3}" y="{Y(p)+3:.1f}" font-size="9" fill="var(--mut)">{p:,.0f} {nm}</text>'
    for i, r in x.iterrows():
        c = 'var(--up)' if r.Close >= r.Open else 'var(--dn)'
        s += f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r.High):.1f}" y2="{Y(r.Low):.1f}" stroke="{c}" stroke-width=".8"/><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r.Open,r.Close)):.1f}" y2="{Y(min(r.Open,r.Close))+.6:.1f}" stroke="{c}" stroke-width="{max(1.2,(W-L-R)/tot*.7):.1f}"/>'
    days = [i for i in range(len(x)) if i == 0 or t0[i].date() != t0[i-1].date()]
    ev = cf.get('tick_every', 1); pm = None
    for k, i in enumerate(days):
        s += f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{T}" y2="{H-B}" stroke="var(--line)" stroke-width=".6"/>'
        if (len(days) - 1 - k) % ev: continue
        s += f'<text x="{X(i):.1f}" y="{H-19}" font-size="10" fill="var(--mut)" text-anchor="middle">{t0[i].day}</text>'
        if t0[i].month != pm:
            pm = t0[i].month
            s += f'<text x="{max(X(i), 16):.1f}" y="{H-6}" font-size="10" font-weight="700" fill="var(--tx)" text-anchor="middle">{pm}月</text>'
    xn = X(len(x) - 1)
    s += f'<line x1="{xn:.1f}" x2="{xn:.1f}" y1="{T}" y2="{H-B}" stroke="var(--mut)" stroke-dasharray="2 3"/>'
    for pts, col in ((cf['main'], 'var(--main)'), (cf['alt'], 'var(--alt)')):
        q = [(len(x) - 1, last)] + [(len(x) - 1 + k, p) for k, p in pts]
        s += f'<polyline fill="none" stroke="{col}" stroke-width="2" stroke-dasharray="5 4" points="' + ' '.join(f'{X(i):.1f},{Y(p):.1f}' for i, p in q) + '"/>'
    w = []
    for t, p, nm in cf['waves']:
        t = pd.Timestamp(t)
        if t0.iloc[0] <= t <= t0.iloc[-1]: w.append((int(t0.searchsorted(t)), p, nm))
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
html = Template(open('template.html', encoding='utf-8').read()).substitute(
    vt=vt, vx=vx, price=f'{price:,.0f}', upd=datetime.now().strftime('%Y-%m-%d %H:%M'),
    c60=chart(H, C['chart60'], ma60), c5=chart(M, C['chart5'], ma60),
    n60=' ／ '.join(C['chart60']['names']), n5=' ／ '.join(C['chart5']['names']))
open('docs/index.html', 'w', encoding='utf-8').write(html)
json.dump({'price': price, 'verdict': vt, 'updated': datetime.now().isoformat()}, open('docs/data.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('ok', vt, round(price))
