# 検証用ツール（naitools.py）

NovelAI で作った画像を、**記録・比較・切り抜き・合成・コマ割り・吹き出し**まで、ローカルで処理するためのツール。画像生成はしない（アンラスを使わない）。
実行：
```
D:\AI\ComfyUI_windows_portable\python_embeded\python.exe D:\AI\NovelAI研究\tools\naitools.py <命令> ...
```
（Git Bash では `PYTHONIOENCODING=utf-8` を付けると日本語が化けない）

| 命令 | 何をするか | 例 |
|---|---|---|
| `meta` | PNG に埋め込まれた NovelAI の設定を表示（プロンプト、UC、seed、参照の強度・忠実度、キャラクタープロンプトと位置、道具の種類） | `meta 画像\R1-1_….png` |
| `catalog` | フォルダの PNG の設定を Markdown の表にする（研究ログに貼れる） | `catalog 画像\K_画風カタログ 実験\K.md` |
| `collect` | Downloads から直近 N 分の NovelAI 画像を、実験フォルダへ移す。重複は消す。名前は `時刻_種類_s<seed>_<ハッシュ>.png` | `collect 実験\E01_フォーカスインペイント 30` |
| `sheet` | 名前つきの一覧画像 | `sheet 一覧.png 4 a.png b.png …` |
| `diff` | 2枚の差：変わった割合、変わった範囲、白黒マスク（インペイントが効いたかの判定に使う） | `diff 前.png 後.png 差.png` |
| `cutout` | 白背景を抜いて透過 PNG にする。髪のまわりの白いふちが出ないように、細い線を一度ふさいでから外周の白を抜く | `cutout 人物.png 人物_透過.png` |
| `compose` | 背景に透過キャラを置く。色合わせ（`--match`）、光の向き（`--light right/left/none`）、足元の影（`--shadow`、人物の足が画面内にあるとき）。**境目の帯のマスク** `<出力>_mask.png` も出す | `compose 背景.png 人物_透過.png 合成.png --x 120 --scale 0.75` |
| `page` | 漫画のページを作る（B5 縦 1600×2260）。レイアウト：`4koma` `2x2` `1+2` `3row`。画像の順番＝読む順番（右上から）。縦にはみ出す画像は上から `--anchor`（既定 0.2）の位置で切る | `page p1.png 1+2 a.png b.png c.png` |
| `bubble` | 楕円の吹き出しと日本語のセリフ。幅は自動。`--vertical` で縦書き、`--tail x,y` でしっぽ。行頭に「、。！？」が来ないよう折り返す | `bubble p1.png p1.png "えええっ！？" 120 1250 --size 44 --tail 300,1450` |
| `inset` | リファレンス・インペイント用の白キャンバス（端に基準の人物を黒枠つきで置く）と、塗る所のマスク（研究 E06 用） | `inset 基準.png canvas.png --side left` |
| `prompt` | キャラ表（JSON）から、ベース・キャラごと・UC のプロンプトを固定ブロックで組み立てる。コマごとに人物の言葉がぶれない | `prompt tools\キャラ表_見本.json "upper body, from side, …"` |

キャラ表の見本：`tools\キャラ表_見本.json`（name / sex（girl・boy）/ look / ref / forbidden）

動作確認の結果：`D:\AI\NovelAI研究\実験\動作確認\`（`ページ_吹き出し.png` がページ＋縦書き・横書きの吹き出しの見本）

## まだできないこと（次に作るなら）
- 吹き出しを、顔や手に重ならない位置に自動で置く（今は座標を手で指定）
- 集中線・効果線の描画（今は NovelAI の言葉で描かせる）
- コマの形を斜めにする、コマからはみ出す人物
