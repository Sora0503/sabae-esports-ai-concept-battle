r"""NovelAI 研究・AI漫画づくりの共通ツール（Python / Pillow / numpy / OpenCV）。
実行は ComfyUI 付属の Python を使う：
    D:\AI\ComfyUI_windows_portable\python_embeded\python.exe D:\AI\NovelAI研究\tools\naitools.py <命令> ...

命令の一覧（詳しくは tools\README.md）
  meta     <png...>                         NovelAI の PNG に埋め込まれた設定（プロンプト・seed・参照・種類）を表示
  catalog  <フォルダ> [出力.md]              フォルダ内の PNG の設定を一覧表（Markdown）にする
  collect  <実験フォルダ> [分数=60]          Downloads から、直近 N 分の NovelAI 画像を実験フォルダへ移す（重複は消す）
  sheet    <出力.png> <列数> <png...>        縮小して名前つきで並べた一覧画像を作る
  diff     <前.png> <後.png> [出力.png]      2枚の差（変わった割合・範囲）と、変わった所の白黒マスクを出す
  cutout   <入力.png> <出力.png>            白背景を抜いて透過PNGにする（髪の細い線のすき間の白も抜く）
  compose  <背景.png> <人物透過.png> <出力.png> [--x 40] [--y -1] [--scale 0.7] [--match 0.18] [--light right|left|none] [--shadow 0.35]
                                            人物を背景に置く。色合わせ・光の向き・足元の影・境目のマスク（<出力>_mask.png）
  page     <出力.png> <レイアウト> <png...> [--anchor 0.2]  漫画のページ（コマ割り）。レイアウト：4koma / 2x2 / 1+2 / 3row。
                                            画像の順番＝読む順番（右上から）
  inset    <基準.png> <出力.png> [--side left]  リファレンス・インペイント用の白キャンバス（端に基準の人物）
  prompt   <キャラ表.json> "<このコマの場面>" [--style …]  固定ブロックでプロンプトを組み立てる
  bubble   <入力.png> <出力.png> "<セリフ>" <x> <y> [--w 0=自動] [--tail x,y] [--size 34] [--vertical]
                                            吹き出しとセリフ（日本語）を重ねる
"""
import glob, hashlib, json, os, shutil, sys, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT = r'C:\Windows\Fonts\BIZ-UDGothicB.ttc'
if not os.path.exists(FONT): FONT = r'C:\Windows\Fonts\meiryo.ttc'
DL = os.path.expanduser('~/Downloads')


def _cv2():
    import cv2
    return cv2


def read_meta(path):
    im = Image.open(path); info = {k: v for k, v in im.info.items() if isinstance(v, str)}; size = im.size; im.close()
    c = info.get('Comment', '')
    try: cj = json.loads(c)
    except Exception: cj = {}
    out = {'file': os.path.basename(path), 'size': '%dx%d' % size, 'source': info.get('Source', ''), 'kind': cj.get('req_type') or cj.get('request_type') or ('generate' if cj.get('prompt') else ''),
           'seed': cj.get('seed', ''), 'prompt': cj.get('prompt', ''), 'uc': (cj.get('uc') or '')[:200], 'steps': cj.get('steps', ''), 'scale': cj.get('scale', ''),
           'strength': cj.get('strength', ''), 'ref_strength': cj.get('director_reference_strengths'), 'ref_secondary': cj.get('director_reference_secondary_strengths'),
           'ref_desc': cj.get('director_reference_descriptions')}
    v4 = cj.get('v4_prompt') or {}
    chars = (v4.get('caption') or {}).get('char_captions') or []
    out['characters'] = [(c.get('char_caption'), c.get('centers')) for c in chars]
    return out


def cmd_meta(paths):
    for p in paths:
        m = read_meta(p); print('=' * 60); [print('%-14s %s' % (k, v)) for k, v in m.items() if v not in ('', None, [], {})]


def cmd_catalog(folder, out=None):
    fs = sorted(glob.glob(os.path.join(folder, '*.png')))
    rows = ['| ファイル | 種類 | サイズ | seed | 参照 | プロンプト（先頭） |', '|---|---|---|---|---|---|']
    for f in fs:
        m = read_meta(f)
        ref = '' if not m['ref_strength'] else 'あり %s/%s' % (m['ref_strength'], m['ref_secondary'])
        rows.append('| %s | %s | %s | %s | %s | %s |' % (m['file'], m['kind'], m['size'], m['seed'], ref, (m['prompt'] or '').replace('|', '/')[:120]))
    txt = '\n'.join(rows); print(txt)
    if out: open(out, 'w', encoding='utf-8').write(txt + '\n')


def cmd_collect(folder, minutes=60):
    os.makedirs(folder, exist_ok=True); now = time.time(); seen = set(); n = 0
    for f in sorted(glob.glob(os.path.join(folder, '*.png'))): seen.add(hashlib.md5(open(f, 'rb').read()).hexdigest())
    for f in sorted(glob.glob(os.path.join(DL, '*.png')), key=os.path.getmtime):
        if now - os.path.getmtime(f) > minutes * 60: continue
        m = read_meta(f)
        if m['source'].find('NovelAI') < 0 and not m['kind']: continue
        h = hashlib.md5(open(f, 'rb').read()).hexdigest()
        if h in seen: os.remove(f); continue
        seen.add(h); n += 1
        tag = m['kind'] if m['kind'] not in ('', 'generate', 'PromptGenerateRequest') else 'gen'
        dst = os.path.join(folder, '%s_%s_s%s_%s.png' % (time.strftime('%H%M%S', time.localtime(os.path.getmtime(f))), tag, m['seed'] or 'x', h[:6]))
        shutil.move(f, dst); print('->', os.path.basename(dst))
    print(n, 'files')


def cmd_sheet(out, cols, paths, w=300):
    ims = [Image.open(p).convert('RGB') for p in paths]
    h = int(max(im.height * w / im.width for im in ims)); rows = (len(ims) + cols - 1) // cols
    sh = Image.new('RGB', (w * cols, (h + 22) * rows), (255, 255, 255)); d = ImageDraw.Draw(sh); font = ImageFont.truetype(FONT, 14)
    for i, (p, im) in enumerate(zip(paths, ims)):
        x, y = (i % cols) * w, (i // cols) * (h + 22)
        sh.paste(im.resize((w, int(im.height * w / im.width)), Image.LANCZOS), (x, y + 22)); d.text((x + 4, y + 3), os.path.basename(p)[:36], fill=(0, 0, 0), font=font)
    sh.save(out); print('saved', out, sh.size)


def cmd_diff(a, b, out=None, thr=20):
    A = Image.open(a).convert('RGB'); B = Image.open(b).convert('RGB')
    if A.size != B.size: B = B.resize(A.size, Image.LANCZOS); print('note: size differs, resized B')
    d = np.abs(np.asarray(A, np.int16) - np.asarray(B, np.int16)).max(-1)
    m = d > thr; ys, xs = np.nonzero(m)
    print('changed %.2f%%' % (m.mean() * 100), 'bbox', (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else None, 'max', int(d.max()))
    if out: Image.fromarray((m * 255).astype(np.uint8)).save(out); print('mask ->', out)


def cutout_white(rgb, gap=22):
    """白背景を抜く（v2）。
    1) 外周から、白だけをたどって背景を決める（線は越えない）→ 白い服の内側に穴があかない
    2) 人物の中に残った白のうち「背景に接していて、細い（最大の太さが gap px 以下、既定 22）」ものだけを背景に足す
       → 髪の毛先のすき間の白（ハロー）は消え、白いブラウスなど太い白は残る
    v1 は細い線を通り抜けて背景を広げたため、白い服に穴があいた（E02 で発覚）"""
    cv2 = _cv2(); im = rgb.astype(np.int16)
    nearwhite = ((im.min(-1) >= 228) & ((im.max(-1) - im.min(-1)) <= 16)).astype(np.uint8)
    n, lab = cv2.connectedComponents(nearwhite, connectivity=4)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(edge)).astype(np.uint8)
    inner = nearwhite & (1 - bg)                                         # 人物の中に残った白
    dist = cv2.distanceTransform(inner, cv2.DIST_L2, 3)
    n2, lab2, st, _ = cv2.connectedComponentsWithStats(inner, connectivity=4)
    near_bg = cv2.dilate(bg, np.ones((5, 5), np.uint8))
    add = np.zeros_like(bg)
    for i in range(1, n2):
        comp = lab2 == i
        if not (near_bg[comp].any()): continue                          # 背景に接していない白（白目・服の中）は残す
        if dist[comp].max() <= gap: add[comp] = 1                        # 細いすき間だけ抜く
    bg = np.maximum(bg, add)
    fg = (1 - bg).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return cv2.GaussianBlur(fg.astype(np.float32), (0, 0), 0.8)


def cmd_cutout(inp, out):
    rgb = np.asarray(Image.open(inp).convert('RGB')); a = cutout_white(rgb)
    Image.fromarray(np.dstack([rgb, (a * 255).astype(np.uint8)]), 'RGBA').save(out); print('saved', out, 'fg %.1f%%' % (a.mean() * 100))


def cmd_compose(bgp, chp, out, x=40, y=-1, scale=0.7, match=0.18, light='right', shadow=0.35):
    cv2 = _cv2()
    bg = Image.open(bgp).convert('RGB'); W, H = bg.size
    ch = Image.open(chp).convert('RGBA'); ch = ch.resize((int(ch.width * scale), int(ch.height * scale)), Image.LANCZOS)
    if y < 0: y = H - ch.height
    A = np.asarray(ch, np.float32); rgb, al = A[..., :3], A[..., 3:4] / 255
    bgm = np.asarray(bg, np.float32).reshape(-1, 3).mean(0); fgm = (rgb * al).reshape(-1, 3).sum(0) / max(al.sum(), 1)
    rgb = rgb * (1 - match) + (rgb * (bgm / np.maximum(fgm, 1))) * match                       # 色合わせ
    if light in ('right', 'left'):
        xx = np.linspace(0, 1, A.shape[1])[None, :, None]; xx = xx if light == 'right' else 1 - xx
        rgb = rgb * (0.94 + 0.10 * xx)                                                          # 光の向き
    ch2 = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), A[..., 3:]]).astype(np.uint8), 'RGBA')
    base = bg.convert('RGBA')
    if shadow > 0:                                                                              # 足元の影（人物が画面の下端に切れていないときだけ意味がある）
        sh = np.zeros((H, W), np.float32); a8 = (A[..., 3] > 128).astype(np.float32)
        cols = np.nonzero(a8.any(0))[0]
        if len(cols) and y + ch.height < H - 4:
            cx = x + (cols.min() + cols.max()) / 2; cy = y + ch.height; rx = (cols.max() - cols.min()) / 2 * 0.9
            cv2.ellipse(sh, (int(cx), int(cy)), (int(rx), max(4, int(rx * 0.12))), 0, 0, 360, 1.0, -1)
            sh = cv2.GaussianBlur(sh, (0, 0), 6) * shadow
            arr = np.asarray(base, np.float32); arr[..., :3] *= (1 - sh[..., None]); base = Image.fromarray(arr.astype(np.uint8), 'RGBA')
    base.alpha_composite(ch2, (x, y)); base.convert('RGB').save(out)
    m = np.zeros((H, W), np.uint8); sub = (np.asarray(ch)[..., 3] > 128).astype(np.uint8) * 255
    y0, x0 = max(y, 0), max(x, 0); y1, x1 = min(y + ch.height, H), min(x + ch.width, W)
    m[y0:y1, x0:x1] = sub[y0 - y:y1 - y, x0 - x:x1 - x]
    band = cv2.dilate(m, np.ones((15, 15), np.uint8)) - cv2.erode(m, np.ones((9, 9), np.uint8))
    Image.fromarray(band).save(out[:-4] + '_mask.png'); print('saved', out, '+ mask (境目の帯：インペイントで塗る範囲の目安)')


LAYOUTS = {   # (x0, y0, x1, y1) の比率。B5 相当の縦長ページ（1600x2260）
    '4koma': [(0.06, 0.05 + i * 0.225, 0.94, 0.05 + i * 0.225 + 0.205) for i in range(4)],
    '2x2': [(0.05, 0.05, 0.49, 0.49), (0.51, 0.05, 0.95, 0.49), (0.05, 0.51, 0.49, 0.95), (0.51, 0.51, 0.95, 0.95)],
    '1+2': [(0.05, 0.05, 0.95, 0.52), (0.51, 0.54, 0.95, 0.95), (0.05, 0.54, 0.49, 0.95)],         # 日本の漫画は右から読むので、下段は右が先
    '3row': [(0.05, 0.05, 0.95, 0.34), (0.05, 0.36, 0.95, 0.65), (0.05, 0.67, 0.95, 0.95)],
}


def fit_cover(im, w, h, anchor=0.2):
    """コマを埋めるように拡大して切る。縦にはみ出すときは上から anchor の位置を基準にする（顔は上の方にあることが多いので、既定 0.2）"""
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l = (im.width - w) // 2; t = int((im.height - h) * anchor)
    return im.crop((l, t, l + w, t + h))


def cmd_page(out, layout, paths, W=1600, H=2260, line=6, anchor=0.2):
    page = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(page)
    for (fx0, fy0, fx1, fy1), p in zip(LAYOUTS[layout], paths):
        x0, y0, x1, y1 = int(fx0 * W), int(fy0 * H), int(fx1 * W), int(fy1 * H)
        page.paste(fit_cover(Image.open(p).convert('RGB'), x1 - x0, y1 - y0, anchor), (x0, y0))
        d.rectangle([x0, y0, x1, y1], outline=(0, 0, 0), width=line)
    page.save(out); print('saved', out, '（縦にはみ出す画像は上から %d%% の位置で切る。--anchor 0〜1 で調整。コマの縦横比で生成するのが一番きれい）' % int(anchor * 100))


NO_HEAD = set('、。！？!?ー」）)…っゃゅょァィゥェォッャュョ')


def wrap_jp(d, text, font, maxw):
    """日本語の折り返し。行頭に「、。！？」などが来ないようにする"""
    lines, cur = [], ''
    for ch in text:
        if d.textlength(cur + ch, font=font) > maxw and cur:
            if ch in NO_HEAD: cur += ch; continue          # 句読点・！？は前の行にぶら下げる
            lines.append(cur); cur = ch
        else: cur += ch
    if cur: lines.append(cur)
    return lines


def cmd_bubble(inp, out, text, x, y, w=0, tail=None, size=34, vertical=False, per_col=7):
    """楕円の吹き出し。w=0 なら文字の長さから幅を決める。--vertical で縦書き（右の列から）"""
    im = Image.open(inp).convert('RGB'); d = ImageDraw.Draw(im); font = ImageFont.truetype(FONT, size)
    if vertical:
        cols = []; cur = ''
        for ch in text:
            if len(cur) >= per_col and ch not in NO_HEAD: cols.append(cur); cur = ch
            else: cur += ch
        if cur: cols.append(cur)
        tw, th = size * 1.15 * len(cols), size * max(len(c) for c in cols)
    else:
        maxw = w - 0 if w else min(d.textlength(text, font=font), size * 9)
        lines = wrap_jp(d, text, font, maxw)
        tw, th = max(d.textlength(l, font=font) for l in lines), size * 1.3 * len(lines)
    if vertical: bw, bh = int(tw * 2.0 + size * 1.3), int(th * 1.25 + size * 1.2)   # 縦書きは横に広めにとる
    else: bw, bh = int(tw * 1.45 + size * 1.2), int(th * 1.35 + size * 1.0)        # 楕円の中に文字の四角が収まるよう、余白を足す
    box = [x, y, x + bw, y + bh]; cx, cy = x + bw / 2, y + bh / 2
    if tail:
        tx, ty = tail; ang = np.arctan2(ty - cy, tx - cx); px, py = -np.sin(ang), np.cos(ang); half = size * 0.45
        # しっぽは短く：楕円のふちから最大 size*1.6 まで（遠い指定でも、話し手の方向を指すだけにする）
        rx_, ry_ = bw / 2, bh / 2; edge = 1.0 / np.sqrt((np.cos(ang) / rx_) ** 2 + (np.sin(ang) / ry_) ** 2)
        dist = np.hypot(tx - cx, ty - cy); maxd = edge + size * 1.6
        if dist > maxd: tx, ty = cx + np.cos(ang) * maxd, cy + np.sin(ang) * maxd; tail = (tx, ty)
        base = [(cx + px * half, cy + py * half), (cx - px * half, cy - py * half)]
        d.polygon(base + [(tx, ty)], fill=(255, 255, 255), outline=(0, 0, 0), width=4)
    d.ellipse(box, fill=(255, 255, 255), outline=(0, 0, 0), width=4)
    if tail: d.polygon(base + [(cx + (tx - cx) * 0.55, cy + (ty - cy) * 0.55)], fill=(255, 255, 255))
    if vertical:
        x_start = cx + tw / 2 - size * 0.575
        for li, col in enumerate(cols):
            colx = x_start - li * size * 1.15; y_start = cy - th / 2
            for ci, ch in enumerate(col):
                gx = colx - d.textlength(ch, font=font) / 2; gy = y_start + ci * size
                if ch in 'ー〜…': ch_im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); ImageDraw.Draw(ch_im).text((0, 0), ch, fill=(0, 0, 0), font=font); im.paste(ch_im.rotate(-90), (int(colx - size / 2), int(gy)), ch_im.rotate(-90))
                elif ch in '、。': d.text((gx + size * 0.45, gy - size * 0.45), ch, fill=(0, 0, 0), font=font)
                else: d.text((gx, gy), ch, fill=(0, 0, 0), font=font)
    else:
        for li, ln in enumerate(lines):
            lw = d.textlength(ln, font=font); d.text((cx - lw / 2, cy - th / 2 + li * size * 1.3), ln, fill=(0, 0, 0), font=font)
    im.save(out); print('saved', out, 'bubble', box)


def cmd_inset(ref, out, W=1216, H=768, side='left', frac=0.32):
    """リファレンス・インペイント用のキャンバス（公式の上級テクニック）：白い画面の端に、基準の人物を黒い枠つきで置く。
    出力 <out> と、塗る範囲（白い所）のマスク <out>_mask.png。NovelAI では i2i →「画像をインペイントする」で白い所を塗り、ベースに reference inset を入れる"""
    cv = Image.new('RGB', (W, H), (255, 255, 255)); r = Image.open(ref).convert('RGB')
    rw = int(W * frac); rh = int(r.height * rw / r.width)
    if rh > H - 20: rh = H - 20; rw = int(r.width * rh / r.height)
    r = r.resize((rw, rh), Image.LANCZOS); x = 10 if side == 'left' else W - rw - 10; y = (H - rh) // 2
    cv.paste(r, (x, y)); d = ImageDraw.Draw(cv); d.rectangle([x - 4, y - 4, x + rw + 4, y + rh + 4], outline=(0, 0, 0), width=6)
    cv.save(out); m = Image.new('L', (W, H), 255); ImageDraw.Draw(m).rectangle([x - 8, y - 8, x + rw + 8, y + rh + 8], fill=0); m.save(out[:-4] + '_mask.png')
    print('saved', out, '+ mask（白＝塗る所）')


def cmd_prompt(charfile, scene, style='', extra=''):
    """固定ブロックでプロンプトを組み立てる（コマごとに人物の言葉がぶれないように）。
    charfile：キャラ表の JSON（tools\キャラ表_見本.json）。scene：このコマで何をするか（画角・表情・動作・場所）。
    出力：ベースプロンプトと、UC に足す言葉（forbidden）"""
    c = json.load(open(charfile, encoding='utf-8'))
    people = c['characters']; n_f = sum(1 for p in people if p['sex'] == 'girl'); n_m = sum(1 for p in people if p['sex'] == 'boy')
    count = ', '.join(x for x in [('%dgirl' % n_f + ('s' if n_f > 1 else '')) if n_f else '', ('%dboy' % n_m + ('s' if n_m > 1 else '')) if n_m else ''] if x)
    base = ', '.join(x for x in [count, 'solo' if len(people) == 1 else '%d people' % len(people), scene, style or c.get('style', ''), 'no text'] if x)
    print('[BASE]\n' + base)
    for i, p in enumerate(people, 1): print('[CHARACTER %d] (%s)\n%s, %s' % (i, p['name'], p['sex'], p['look']))
    print('[UC に足す]\n' + ', '.join(c.get('forbidden', []) + ([extra] if extra else [])))
    if len(people) > 1: print('※ 2人以上は横長 1216x768。キャラクタープロンプトの欄を上の順で作る（左から並ぶ）')


def main(a):
    if not a: print(__doc__); return
    c, r = a[0], a[1:]
    def opt(name, default, typ=str):
        if '--' + name in r: i = r.index('--' + name); v = r[i + 1]; del r[i:i + 2]; return typ(v)
        return default
    if c == 'meta': cmd_meta(r)
    elif c == 'catalog': cmd_catalog(r[0], r[1] if len(r) > 1 else None)
    elif c == 'collect': cmd_collect(r[0], float(r[1]) if len(r) > 1 else 60)
    elif c == 'sheet': cmd_sheet(r[0], int(r[1]), r[2:])
    elif c == 'diff': cmd_diff(r[0], r[1], r[2] if len(r) > 2 else None)
    elif c == 'cutout': cmd_cutout(r[0], r[1])
    elif c == 'compose':
        kw = dict(x=opt('x', 40, int), y=opt('y', -1, int), scale=opt('scale', 0.7, float), match=opt('match', 0.18, float), light=opt('light', 'right'), shadow=opt('shadow', 0.35, float))
        cmd_compose(r[0], r[1], r[2], **kw)
    elif c == 'inset': cmd_inset(r[0], r[1], side=opt('side', 'left'))
    elif c == 'prompt': cmd_prompt(r[0], r[1], opt('style', ''), opt('extra', ''))
    elif c == 'page':
        anc = opt('anchor', 0.2, float); cmd_page(r[0], r[1], r[2:], anchor=anc)
    elif c == 'bubble':
        w = opt('w', 0, int); size = opt('size', 34, int); tail = opt('tail', None); vert = '--vertical' in r
        if vert: r.remove('--vertical')
        cmd_bubble(r[0], r[1], r[2], int(r[3]), int(r[4]), w=w, tail=tuple(map(int, tail.split(','))) if tail else None, size=size, vertical=vert)
    else: print(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
