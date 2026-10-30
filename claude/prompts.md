# Claude案「4人目は、あなた。」— プロンプトと設定の全記録

コンテストのルール「制作時のプロンプトや参照画像を保存」のための記録。
NovelAI の生成画像（PNG）には、プロンプト・seed・設定が埋め込まれている（原本は制作者のローカルに保存）。

## 使ったツール
| 工程 | ツール | 商用利用 |
|---|---|---|
| 生成・2倍拡大 | NovelAI Image Generation（V4.5 Curated） | 利用規約 §1.3「生成物の権利と所有権は利用者に帰属」。生成物の利用を制限する条項なし（2026-10-30 確認） |
| 4:5 切り出し・3200×4000 への拡大と描き直し | ComfyUI ＋ Animagine XL 4.0 opt ＋ ControlNet Union SDXL promax（tile） | Animagine XL 4.0 は CreativeML Open RAIL++-M（生成物の商用利用可） |

**参照画像：なし。** 文章（プロンプト）だけで生成した。作品名・作家名・既存キャラ名・実在の人物名は使っていない。

## 採用した画像
- seed **1357159947**、896×1152、ステップ 28、ガイダンス（正確度）5、サンプラー Euler Ancestral、品質タグ「標準」、UC プリセット「強い」
- キャラクターの位置：カスタム（5×5 のマス。おじいちゃん＝中央の上から2段目、女の子＝左の3段目、男の子＝右の3段目）

### ベースプロンプト
```
3people, grandfather, teenage girl and boy playing video games together, everyone holding a game controller, everyone wears glasses, 2::boy sitting in a wheelchair, wheelchair push handles, wheelchair wheel beside him::, looking at viewer, inviting viewer to play, 2::pov hands holding a black lacquered game controller at the bottom::, 2::two round gold maki-e circles on the controller connected like eyeglasses::, happy, one red panda waving, warm lighting, golden rim light, 2::large vermilion red lacquer circle behind them with subtle gold azalea maki-e pattern, black background::, japanese lacquerware, 2::ornate gold pattern::, gold lines turning into circuit board traces radiating, glowing gold particles, red and black and gold theme, anime coloring, vibrant, highly detailed, detailed shading, depth of field, no text
```

### 除外したい要素（ネガティブ）
```
monitor, television, computer, laptop, screen, table, text, watermark, logo
```

### キャラクタープロンプト
| # | プロンプト |
|---|---|
| 1 | `old man, grey hair, wrinkles, round glasses, warm smile, knit cardigan, holding a game controller, red panda on shoulder` |
| 2 | `teenage girl, black hair, bob cut, glasses, hoodie, gaming headset, holding a game controller, grin` |
| 3 | `boy, child, short brown hair, glasses, sitting in a wheelchair, wheelchair wheels, holding a game controller, open mouth, excited, plain blue t-shirt` |

## 仕上げ
1. NovelAI の「拡大」（2倍、1 アンラス）→ 1792×2304
2. 上下 32px を切って 4:5（1792×2240）→ Lanczos で 3200×4000
3. ComfyUI でタイル（1024px、重なり 192px）ごとに弱く描き直す（`upscale_claude.py`）
   - Animagine XL 4.0 opt、ControlNet tile（強さ 0.85、終了 0.9）、denoise 0.22、24 ステップ、CFG 4.5、Euler Ancestral
   - 正：`masterpiece, best quality, anime illustration, clean line art, sharp lines, flat color, detailed, vivid colors`
   - 色味は元の絵に固定（ぼかした色の面だけ元の絵から戻す）
4. 顔（3人とレッサーパンダ）は、描き直しで目の向きが少し動くので、描き直し前に戻した（`face_keep.py`）

## 試行の経緯（要点）
| 段階 | 変えたこと | 分かったこと |
|---|---|---|
| 1 | 黒地に金の回路、3人がこちらを向く | 金の放射線は強い。画面（モニター）が手前に出てしまう → ネガティブに monitor 等 |
| 2 | `pov` を入れる | **見た人の手がコントローラーを持つ構図**が出た → 「4人目は、あなた」の着想 |
| 3 | キャラクタープロンプトで3人の位置を指定 | 3人とレッサーパンダが安定して入る |
| 4 | コントローラーを漆塗り＋金の蒔絵に | 伝統の物を「見た人の手」に持たせられる |
| 5 | 蒔絵の丸2つを「めがねのように」つなぐ | **コントローラーがめがねになった**（鯖江） |
| 6 | 車いすの押し手と車輪を明記 | 車いすが見えるようになった |
| 7 | 朱の丸に金のつつじの蒔絵 | 漆の質感が出た → 採用 |

途中の画像は `process/` に置いた（JPEG）。
