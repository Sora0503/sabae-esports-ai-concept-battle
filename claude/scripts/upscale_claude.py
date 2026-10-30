r"""Claude案の拡大と仕上げ：NovelAI の2倍拡大（1792x2304）を 4:5 に切り出し（上下 32px）→ 3200x4000 に拡大
→ タイル(1024px)ごとに tile ControlNet で弱く描き直す → なだらかに混ぜる → 色味を元の絵に固定。
使い方（ComfyUI が起動している状態で）: python upscale_claude.py test | run
モデル: Animagine XL 4.0 opt（商用可の Open RAIL++-M）＋ ControlNet Union promax の tile。
"""
import glob, json, os, shutil, sys
import cv2
import numpy as np
from PIL import Image
sys.path.insert(0, r'D:\AI\style_recipes\shizuku_making\scripts')
import hw

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '生成', 'C_s1357159947_upscale2x.png')
WK = os.path.join(HERE, '作業', 'up'); os.makedirs(WK, exist_ok=True)
INDIR = r'D:\AI\ComfyUI_windows_portable\ComfyUI\input\up_cl1'; os.makedirs(INDIR, exist_ok=True)
OUTW, OUTH = 3200, 4000
T, OV = 1024, 192
DENOISE = 0.22; STEPS = 24; CFG = 4.5; CN_STRENGTH = 0.85; CN_END = 0.9
POS = 'masterpiece, best quality, anime illustration, clean line art, sharp lines, flat color, detailed, vivid colors'
NEG = hw.BASE_NEG + ', blurry, jpeg artifacts, noise, text, watermark, signature, extra fingers, bad hands, deformed, 3d, realistic'
SEED = hw.SEED0 + 270000


def graph(name):
    return {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': hw.CKPT}},
        '4': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': POS}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['1', 1], 'text': NEG}},
        '10': {'class_type': 'LoadImage', 'inputs': {'image': 'up_cl1/' + name}},
        '20': {'class_type': 'ControlNetLoader', 'inputs': {'control_net_name': 'controlnet-union-sdxl-promax.safetensors'}},
        '21': {'class_type': 'SetUnionControlNetType', 'inputs': {'control_net': ['20', 0], 'type': 'tile'}},
        '22': {'class_type': 'ControlNetApplyAdvanced', 'inputs': {'positive': ['4', 0], 'negative': ['5', 0], 'control_net': ['21', 0], 'image': ['10', 0],
                                                                   'strength': CN_STRENGTH, 'start_percent': 0.0, 'end_percent': CN_END, 'vae': ['1', 2]}},
        '12': {'class_type': 'VAEEncodeTiled', 'inputs': {'pixels': ['10', 0], 'vae': ['1', 2], 'tile_size': 512, 'overlap': 64, 'temporal_size': 64, 'temporal_overlap': 8}},
        '6': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['22', 0], 'negative': ['22', 1], 'latent_image': ['12', 0],
                                                  'seed': SEED, 'steps': STEPS, 'cfg': CFG, 'sampler_name': 'euler_ancestral', 'scheduler': 'normal', 'denoise': DENOISE}},
        '9': {'class_type': 'VAEDecodeTiled', 'inputs': {'samples': ['6', 0], 'vae': ['1', 2], 'tile_size': 512, 'overlap': 64, 'temporal_size': 64, 'temporal_overlap': 8}},
        '8': {'class_type': 'SaveImage', 'inputs': {'images': ['9', 0], 'filename_prefix': 'hw/up_cl1'}},
    }


def positions(total):
    n = int(np.ceil((total - OV) / (T - OV)))
    return [int(round(v)) for v in np.linspace(0, total - T, n)]


def base_image():
    p = os.path.join(WK, 'base_%dx%d.png' % (OUTW, OUTH))
    if not os.path.exists(p):
        Image.open(SRC).convert('RGB').crop((0, 32, 1792, 2272)).resize((OUTW, OUTH), Image.LANCZOS).save(p)
    return p


def tile_job(base, x0, y0):
    tag = 'x%04d_y%04d' % (x0, y0)
    raw = os.path.join(WK, 'raw_' + tag + '.png')
    if not os.path.exists(raw):
        src = os.path.join(INDIR, tag + '.png')
        Image.open(base).convert('RGB').crop((x0, y0, x0 + T, y0 + T)).save(src)
        hw.run(graph(tag + '.png'), {'8': raw}, 'up_' + tag)
    return raw


def merge(base, tiles):
    xs, ys = positions(OUTW), positions(OUTH)
    acc = np.zeros((OUTH, OUTW, 3), np.float32); wsum = np.zeros((OUTH, OUTW), np.float32)
    ramp = np.minimum(np.arange(T) + 1, np.arange(T)[::-1] + 1).astype(np.float32); ramp = np.clip(ramp / OV, 0.02, 1.0)
    win = np.outer(ramp, ramp)
    for (x0, y0), raw in tiles:
        r = np.asarray(Image.open(raw).convert('RGB'), np.float32)
        acc[y0:y0 + T, x0:x0 + T] += r * win[..., None]; wsum[y0:y0 + T, x0:x0 + T] += win
    out = acc / np.maximum(wsum[..., None], 1e-6)
    b = np.asarray(Image.open(base).convert('RGB'), np.float32)
    # 色味を元の絵に固定：低周波（色の面）は元の絵、高周波（線・質感）は描き直しの結果
    s = 14
    out = out + (cv2.GaussianBlur(b, (0, 0), s) - cv2.GaussianBlur(out, (0, 0), s))
    return np.clip(out, 0, 255).astype(np.uint8)


def main():
    mode = sys.argv[1]
    base = base_image(); xs, ys = positions(OUTW), positions(OUTH)
    if mode == 'test':
        x0, y0 = xs[1], ys[1]                                   # 中央付近（人物の顔と手のあたり）
        raw = tile_job(base, x0, y0)
        a = Image.open(base).convert('RGB').crop((x0, y0, x0 + T, y0 + T)); b = Image.open(raw).convert('RGB')
        sheet = Image.new('RGB', (T * 2 + 10, T), (255, 255, 255)); sheet.paste(a, (0, 0)); sheet.paste(b, (T + 10, 0)); sheet.save(os.path.join(HERE, '作業', 'up_test.png'))
        print('test tile', x0, y0, '->', os.path.join(HERE, '作業', 'up_test.png'))
        return
    tiles = []
    for y0 in ys:
        for x0 in xs:
            tiles.append(((x0, y0), tile_job(base, x0, y0)))
    out = merge(base, tiles)
    dst = os.path.join(HERE, '完成', 'Claude案_%dx%d.png' % (OUTW, OUTH)); Image.fromarray(out).save(dst)
    json.dump(dict(input=SRC, size=[OUTW, OUTH], tile=T, overlap=OV, denoise=DENOISE, steps=STEPS, cfg=CFG, controlnet='controlnet-union-sdxl-promax (tile)',
                   cn_strength=CN_STRENGTH, cn_end=CN_END, model=hw.CKPT, loras='なし', seed=SEED, positive=POS, negative=NEG, color_lock_sigma=14,
                   tiles=[list(t[0]) for t in tiles]), open(dst[:-4] + '_設定.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved', dst)


if __name__ == '__main__':
    main()
