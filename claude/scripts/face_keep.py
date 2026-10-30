r"""描き直しで目の向きが少し動くので、顔だけ「描き直し前」（NovelAI の2倍拡大を Lanczos で拡大したもの）に戻す。
入力: 完成\Claude案_3200x4000.png（描き直し後）、作業\up\base_3200x4000.png（描き直し前）
出力: 完成\Claude案_3200x4000_顔保持.png と、顔まわりの比較 作業\face_keep_比較.png
顔の範囲は 896x1152 の生成画像での座標（4:5 に切り出すため上 16px を引いてから 3200/896 倍する）。
"""
import os
import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
S = 3200 / 896
# (x0, y0, x1, y1) 896x1152 の生成画像で
FACES = {
    'おじいちゃん': (372, 80, 545, 305),
    '女の子': (238, 330, 425, 490),
    '男の子': (500, 372, 670, 535),
    'レッサーパンダ': (165, 180, 365, 315),
}


def mask(w, h):
    m = np.zeros((h, w), np.float32)
    for x0, y0, x1, y1 in FACES.values():
        X0, X1 = int(x0 * S), int(x1 * S)
        Y0, Y1 = int((y0 - 16) * S), int((y1 - 16) * S)
        cx, cy, rx, ry = (X0 + X1) // 2, (Y0 + Y1) // 2, (X1 - X0) // 2, (Y1 - Y0) // 2
        cv2.ellipse(m, (cx, cy), (rx, ry), 0, 0, 360, 1.0, -1)
    return cv2.GaussianBlur(m, (0, 0), 28)


def main():
    up = np.asarray(Image.open(os.path.join(HERE, '完成', 'Claude案_3200x4000.png')).convert('RGB'), np.float32)
    base = np.asarray(Image.open(os.path.join(HERE, '作業', 'up', 'base_3200x4000.png')).convert('RGB'), np.float32)
    h, w = up.shape[:2]
    m = mask(w, h)[..., None]
    out = up * (1 - m) + base * m
    out = np.clip(out, 0, 255).astype(np.uint8)
    dst = os.path.join(HERE, '完成', 'Claude案_3200x4000_顔保持.png')
    Image.fromarray(out).save(dst)
    # 比較：女の子の顔（左：描き直し、右：顔保持）
    x0, y0, x1, y1 = FACES['女の子']
    box = (int(x0 * S) - 80, int((y0 - 16) * S) - 80, int(x1 * S) + 80, int((y1 - 16) * S) + 80)
    a = Image.fromarray(up.astype(np.uint8)).crop(box); b = Image.fromarray(out).crop(box)
    sh = Image.new('RGB', (a.width * 2 + 10, a.height), 'white'); sh.paste(a, (0, 0)); sh.paste(b, (a.width + 10, 0))
    sh.save(os.path.join(HERE, '作業', 'face_keep_比較.png'))
    print('saved', dst)


if __name__ == '__main__':
    main()
