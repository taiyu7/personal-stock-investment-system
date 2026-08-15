# ASR Phase A：Breeze-ASR-25 保準確度加速可行性評估

## 結論先行

Phase A 的目標不是換掉 Breeze-ASR-25，而是在保留它對繁體中文、台灣語境、台股專有名詞優勢的前提下，找出是否有安全的加速路線。

目前 repo 已完成的穩定主線是：

```text
本機音訊檔
  -> whisper CLI + breeze-asr-25
  -> JSON timestamp transcript
  -> personal_stock_investment_system.research.asr
  -> ResearchSourceImportResult
```

本階段決策：

- Phase A 採用 **OpenVINO GPU FP32** 作為 Breeze-ASR-25 加速方向。
- CPU fallback 必須保留，但只作為保底路線，不作為日常長音檔處理主線。
- PyTorch XPU 不採用；它可以跑，但比 CPU 慢。
- OpenVINO FP16 不採用；它沒有比 FP32 更快。
- 不做 INT8、Vulkan、替代 ASR 模型或研究報告流程重寫。

## 十歲小孩版

Breeze-ASR-25 是目前比較會聽台灣中文的聽打員。這張單不是要換掉聽打員，而是檢查三件事：

1. 原本的桌子能不能整理得更順，讓同一個聽打員用 CPU 跑快一點。
2. 能不能讓同一個聽打員去 Intel Arc 顯卡上工作。
3. 能不能把同一個聽打員的工具轉成 OpenVINO 格式，讓 Intel 的工具箱幫忙加速。

如果這三條路會讓它比較聽不懂台灣中文，就先不要。慢一點但聽得準，比快但亂聽更重要。

## 驗收資料現況

本 repo 目前沒有提交任何真實音檔，符合資料安全邊界：

- `data/raw/`：只保留 `.gitkeep`。
- `data/processed/`：只保留 `.gitkeep`。
- `data/local/`：只保留 `.gitkeep`。

因此本文件先建立可重複的 benchmark 方法與決策表。真實數字要等本機放入台股音檔後填寫，不在 Git 中保存音檔或逐字稿。

## 2026-08-15 至 2026-08-16 實測摘要

### 最終決策

本單決定先用 **OpenVINO GPU FP32**。

原因：

- 它保留 Breeze-ASR-25 模型，沒有換成其他 ASR。
- 15 秒與 60 秒投顧 clip 的輸出文字正常，未見立即專有名詞退步。
- 60 秒投顧 clip 耗時 `101.92 秒`，RTF 約 `1.70`，明顯優於 Windows CPU、Docker CPU 與 PyTorch XPU。
- FP16 沒有比 FP32 更快，因此先不採用 FP16。

目前保留的本機產物：

- OpenVINO venv：`data/local/openvino-venv`
- OpenVINO FP32 模型：`data/local/openvino/breeze-asr-25-fp32`
- Hugging Face cache：`data/local/hf-cache`
- Breeze-ASR-25 cache：`data/local/asr-cache`
- 60 秒測試 clip：`data/raw/asr-samples/sample2-60s-16k-mono.wav`
- 60 秒 OpenVINO GPU FP32 輸出：`data/processed/asr-transcripts/openvino-gpu-fp32-60s`

已清理的淘汰路線產物：

- `data/local/xpu-venv`
- Windows CPU / XPU benchmark transcripts
- Docker CPU benchmark transcripts
- OpenVINO CPU / FP16 / 15 秒 benchmark transcripts
- 歌曲前處理測試檔與 15 秒短 clip

### 為什麼不選其他路線

| 路線 | 實測結果 | 不採用原因 |
| --- | --- | --- |
| Docker CPU | 4 分鐘中文歌 RTF 約 `3.71`；13 分 55 秒投顧節目跑到約 25% 已花約 18 分鐘，外推約 70 分鐘級 | 容器曾使用約 10 到 11 個 CPU thread，慢不是因為沒吃 CPU，而是 Breeze-ASR-25 CPU 推論成本太高。 |
| Windows CPU | 60 秒投顧 clip 耗時 `360.82 秒`，RTF 約 `6.01`；15 秒 clip 最佳 `--threads 8` 耗時 `59.90 秒`，RTF 約 `3.99` | `--threads 8` 有改善，但仍不適合作為長音檔主線，只能當 fallback。 |
| PyTorch XPU | Windows 本機可偵測 `Intel(R) Arc(TM) Graphics`，最小 tensor 測試成功；但 60 秒投顧 clip 耗時 `560.46 秒`，RTF 約 `9.34` | Arc 有被 PyTorch 使用，但 Breeze-ASR-25 whisper patch 的 XPU 路徑沒有有效加速，可能受 XPU runtime warm-up、部分 op fallback、Whisper patch 未針對 XPU 最佳化、模型/資料搬移成本影響。 |
| PyTorch XPU FP16 | 15 秒投顧 clip 耗時 `330.55 秒`，RTF 約 `22.04` | FP16 也沒有改善，表示瓶頸不只是 FP32 精度。 |
| OpenVINO CPU FP32 | 15 秒投顧 clip 耗時 `178.91 秒`，RTF 約 `11.93` | 輸出正常，但 CPU device 太慢。 |
| OpenVINO GPU FP16 | 15 秒投顧 clip 耗時 `47.66 秒`，RTF 約 `3.18` | 輸出與 FP32 一致，但沒有比 OpenVINO GPU FP32 快，因此先保留 FP32，降低精度變動風險。 |

採用 OpenVINO GPU FP32 的理由：

- 60 秒投顧 clip 耗時 `101.92 秒`，RTF 約 `1.70`，是目前最好的長度延伸結果。
- 輸出包含投信、外資、被動元件等投顧語境，未見立即退步。
- 保留 Breeze-ASR-25 模型，只轉執行格式，不換 ASR 模型。
- 相比 PyTorch XPU，OpenVINO runtime 能直接看到 `CPU`、`GPU`、`NPU`，且 GPU 路線確實帶來加速。

### 測試環境

- Runtime：Docker `asr-tools` profile。
- ASR command：`whisper ... --model breeze-asr-25 --device cpu --fp16 False --verbose False --output_format json --language Chinese`。
- Docker ASR image 內套件狀態：`torch 2.13.0+cu130`，`whisper` 可 import。
- Docker XPU 狀態：`torch.xpu.is_available()` 回傳 `False`。
- Windows 本機 XPU venv：`data/local/xpu-venv`。
- Windows 本機 XPU 套件：Python `3.13.3`、`torch 2.13.0+xpu`、Breeze-ASR-25 whisper patch。
- Windows 本機 XPU device：`Intel(R) Arc(TM) Graphics`，最小 tensor 測試成功。

### CPU 原路線結果

| sample id | 類型 | 音檔長度 | 路線 | 前處理 | 轉錄時間 | real-time factor | 結論 |
| --- | --- | ---: | --- | --- | ---: | ---: | --- |
| sample | 中文歌 | 243.62 秒 | Docker CPU | 原 MP3 | 903.27 秒 | 3.71 | 可跑，但很慢；歌曲不適合判斷台股準確度。 |
| sample | 中文歌 | 243.62 秒 | Docker CPU | 16k mono WAV | 912.33 秒 | 3.75 | 對這段樣本沒有加速。 |
| sample2 | 投顧節目 | 834.67 秒 | Docker CPU | 原 MP3 | 中止於約 25%，已跑約 18 分鐘 | 外推約 5.2 | 不可接受；完整轉錄粗估約 70 分鐘級。 |

`sample-16k-mono.wav` 是由 `sample.mp3` 轉出的前處理測試檔：

```powershell
ffmpeg -y -i data\raw\asr-samples\sample.mp3 -vn -ac 1 -ar 16000 data\raw\asr-samples\sample-16k-mono.wav
```

本輪觀察到 Docker Desktop 顯示 ASR 容器約使用 `1094% / 2200%` CPU，等同約 10 到 11 個 CPU thread。因此慢的主因不是 CPU 沒被使用，而是 Breeze-ASR-25 在 CPU 上對長音檔推論成本太高。

### PyTorch XPU 結果

Docker `asr-tools` 中已有 `torch.xpu` 屬性，但 `torch.xpu.is_available()` 為 `False`。因此目前 Docker 路線不能使用 Intel Arc / XPU 加速。

Windows 本機 XPU 曾建立隔離環境並成功啟動，且 PyTorch 最小 tensor 測試成功：

```powershell
data\local\xpu-venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.xpu.is_available()); print(torch.xpu.get_device_name(0))"
```

實測結果：

| sample id | 音檔長度 | 路線 | 轉錄時間 | real-time factor | 輸出 | 結論 |
| --- | ---: | --- | ---: | ---: | --- | --- |
| sample2-60s-16k-mono | 60.00 秒 | Windows CPU | 360.82 秒 | 6.01 | JSON | 可跑，但慢。 |
| sample2-60s-16k-mono | 60.00 秒 | Windows XPU | 560.46 秒 | 9.34 | JSON | 可跑，但比 CPU 慢約 55%，不採用。 |
| sample2-15s-16k-mono | 15.00 秒 | Windows XPU FP16 | 330.55 秒 | 22.04 | JSON | FP16 也沒有改善，推測 bottleneck 不只在 FP32 精度。 |

XPU 不是完全不能跑；問題是目前 Breeze-ASR-25 whisper patch 透過 `--device xpu` 跑 60 秒投顧 clip 時，速度比 Windows CPU 更慢。這可能來自 XPU runtime warm-up、部分 op fallback、Whisper patch 對 XPU path 未最佳化，或模型/資料搬移成本過高。

本階段結論：Windows PyTorch XPU 可作為技術驗證成立，但不符合 #43 的採用門檻，不應接進 adapter config。

### 本輪判定

- Docker CPU 原路線可作為 fallback，但不適合 13 分鐘以上投顧節目的日常使用。
- 對 4 分鐘中文歌，16k mono WAV 沒有帶來速度改善；對投顧音檔是否有幫助仍需短 clip 重測。
- Docker XPU 目前不可用，不應繼續往 Docker XPU 硬接。
- Windows XPU 可跑但更慢，不應採用。
- #43 接下來應進入 OpenVINO FP32 / FP16 評估。

### CPU threads 短 clip 實測

用 `sample2-15s-16k-mono.wav` 測 Windows 本機 CPU，固定 `--device cpu --fp16 False --verbose False`，只調整 `--threads`：

| threads | 音檔長度 | 轉錄時間 | real-time factor | 結論 |
| ---: | ---: | ---: | ---: | --- |
| 0 | 15.00 秒 | 78.47 秒 | 5.23 | torch 自動值，不是最佳。 |
| 4 | 15.00 秒 | 73.22 秒 | 4.88 | 比自動值略快。 |
| 8 | 15.00 秒 | 59.90 秒 | 3.99 | 本輪最佳。 |
| 12 | 15.00 秒 | 70.34 秒 | 4.69 | 回落。 |
| 16 | 15.00 秒 | 66.50 秒 | 4.43 | 比 12 好，但仍輸 8。 |

初步採用建議：在這台 Windows 本機上，Breeze-ASR-25 CPU fallback 可先使用 `--threads 8` 作為候選設定。這只是小幅優化，不能解決 13 分鐘投顧節目仍然過慢的根本問題。

## CPU baseline

### 測試目標

CPU baseline 至少要回答：

- 音檔長度是多少。
- Docker `asr-tools` 跑多久。
- Windows 本機 Python / whisper CLI 跑多久。
- 輸出格式是否仍是 Whisper JSON。
- 台股公司名、人名、中文斷詞、英文縮寫是否有明顯錯字。

### 建議測試音檔

用同一批台股研究來源音檔測試，每段先控制在 3 到 10 分鐘：

| sample id | 類型 | 長度 | 內容重點 | 是否可提交 |
| --- | --- | ---: | --- | --- |
| tw-stock-short-01 | 投顧 / 研究短片音訊 | 待填 | 公司名、產業詞、數字 | 否 |
| tw-stock-short-02 | 台股訪談音訊 | 待填 | 人名、英文縮寫、中文斷詞 | 否 |
| tw-stock-long-01 | 較長研究影片音訊 | 待填 | 長段落與時間戳穩定度 | 否 |

### 音訊前處理

第一輪先保留原檔，第二輪再測試統一格式是否加速：

```powershell
ffmpeg -y -i data\raw\asr-samples\sample-input.mp4 -vn -ac 1 -ar 16000 data\raw\asr-samples\sample-16k-mono.wav
```

這個設定只改音訊容器與取樣格式，不改 ASR 模型。若轉成 mono / 16kHz WAV 後速度變快且輸出沒有退步，可以納入後續 pipeline 的前處理候選。

### Docker baseline

```powershell
Measure-Command {
  docker compose --profile asr-tools run --rm asr-tools sh -lc "whisper data/raw/asr-samples/sample-16k-mono.wav --model breeze-asr-25 --output_format json --output_dir data/processed/asr-transcripts --language Chinese"
}
```

### Windows 本機 baseline

```powershell
Measure-Command {
  whisper C:\Users\taiyu\personal-stock-investment-system\data\raw\asr-samples\sample-16k-mono.wav --model breeze-asr-25 --output_format json --output_dir C:\Users\taiyu\personal-stock-investment-system\data\processed\asr-transcripts --language Chinese
}
```

### CPU baseline 記錄表

| sample id | 音檔長度 | 路線 | 前處理 | 轉錄時間 | real-time factor | 輸出格式 | 明顯錯字 / 專有名詞問題 |
| --- | ---: | --- | --- | ---: | ---: | --- | --- |
| sample | 243.62 秒 | Docker CPU | 原 MP3 | 903.27 秒 | 3.71 | JSON | 中文歌，不作為台股準確度判定。 |
| sample | 243.62 秒 | Docker CPU | 16k mono wav | 912.33 秒 | 3.75 | JSON | 中文歌，不作為台股準確度判定。 |
| sample2 | 834.67 秒 | Docker CPU | 原 MP3 | 中止於約 25%，已跑約 18 分鐘 | 外推約 5.2 | 未產生完整 JSON | 速度不可接受，未完成準確度檢查。 |
| tw-stock-short-01 | 待填 | Windows CPU | 16k mono wav | 待填 | 待填 | JSON | 待填 |

real-time factor 計算方式：

```text
real-time factor = 轉錄秒數 / 音檔秒數
```

數字小於 1 代表轉錄比音檔播放還快；大於 1 代表轉錄比播放慢。

## 路線一：Breeze-ASR-25 原路線優化

這條路不換模型、不轉格式，風險最低。

可調整項目：

- 比較 Docker 和 Windows 本機跑法。
- 先將音訊轉成 `mono / 16kHz / wav`。
- 檢查 `whisper --help` 中是否有安全參數，例如 threads、device、temperature、beam size、chunk 或 segment 相關設定。
- 記錄 CPU 使用率與記憶體使用量。
- 維持輸出為 Whisper JSON，避免破壞 `BreezeAsrCliTranscriber`。

初步判定：

- 可行性：高。
- 準確度風險：低，因為不換模型。
- 實作風險：低到中，主要風險在前處理是否改變音訊品質。
- 建議：先完成這條 baseline，再進 XPU / OpenVINO。

## 路線二：Breeze-ASR-25 + PyTorch XPU

PyTorch 官方文件已提供 Intel GPU 的 `torch.xpu` 路線，且 Intel Arc A-Series 在 Windows 11 與 Ubuntu 24.04/25.10 屬於 client GPU 支援範圍。最小程式概念是確認：

```python
import torch

print(torch.xpu.is_available())
```

若為 `False`，代表驅動、PyTorch binary、作業系統或環境尚未就緒，不應繼續硬接到 ASR pipeline。

### 評估重點

- 優先確認 Breeze-ASR-25 使用的 whisper patch 是否能指定 XPU device。
- 優先走 Windows 本機實驗，因為 Docker GPU passthrough 到 Intel Arc 的風險較高。
- 不改 `ResearchSource`、LLM 分析流程或報告 renderer。
- 若需要修改 adapter，只能新增 backend config，不把 XPU 寫成唯一選項。

### 建議實驗命令

先在 Windows 本機 Python 環境檢查：

```powershell
python -c "import torch; print(torch.__version__); print(torch.xpu.is_available())"
```

若 XPU 可用，再檢查 whisper patch 是否支援 device 參數：

```powershell
whisper --help
```

若 CLI 沒有可靠 XPU 入口，停止於文件結論，不要為了 Phase A 重寫 Breeze-ASR-25 推論流程。

### PyTorch XPU 記錄表

| sample id | OS / runtime | torch version | XPU available | Breeze-ASR-25 是否保留 | 轉錄時間 | 準確度差異 | 結論 |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| sample2-60s-16k-mono | Windows 本機 | 2.13.0+xpu | True | 是 | 560.46 秒 | 比 Windows CPU 慢約 55% | 可跑但不採用 |
| sample2-60s-16k-mono | Docker | 2.13.0+cu130 | False | 是 | 未測 | XPU 不可用 | 不採用 |

初步判定：

- 可行性：低到中；PyTorch XPU 可用，但目前 whisper patch 的 XPU 轉錄速度不佳。
- 準確度風險：低到中，若仍使用 Breeze-ASR-25 原模型，理論上風險較低；但 device / dtype 差異仍需實測。
- 實作風險：中，Windows 本機可啟動，Docker 路線不可用。
- 建議：暫不接 adapter config；除非後續找到明確改善 XPU path 的方式，否則維持 CPU fallback 並轉向 OpenVINO FP32 / FP16。

## 路線三：Breeze-ASR-25 轉 OpenVINO FP32 / FP16

OpenVINO 官方文件提供 Whisper 透過 Hugging Face Optimum Intel 匯出 OpenVINO IR 的路線，並可用 OpenVINO Generate API / Whisper pipeline 做推論。Phase A 只評估 FP32 / FP16，不做 INT8。

### 評估重點

- 先確認 Breeze-ASR-25 是否能作為 Hugging Face model id 或本機 model directory 被 `optimum-cli export openvino` 接受。
- 只做 FP32 / FP16，不做 NNCF / INT8 量化。
- 與 CPU baseline 使用同一批音檔。
- 專門檢查台股公司名、人名、英文縮寫、數字、中文斷詞。
- 若 OpenVINO pipeline 輸出格式不同，要在 adapter 邊界轉成 `AsrTranscriptSegment`，不能讓下游知道格式差異。

### 建議轉換命令草案

實際參數要以 Breeze-ASR-25 model id / 本機模型目錄為準：

```powershell
optimum-cli export openvino --model <breeze-asr-25-model-or-local-path> --task automatic-speech-recognition-with-past data\local\openvino\breeze-asr-25-fp32
```

FP16 路線需等 FP32 可跑後再試，並把準確度差異寫入表格。若 FP16 造成台股專有名詞明顯退步，即使速度更快也不採用。

### OpenVINO 記錄表

| sample id | 精度 | device | 轉錄時間 | real-time factor | 與 CPU 輸出差異 | 專有名詞退步 | 結論 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| sample2-15s-16k-mono | FP32 | CPU | 178.91 秒 | 11.93 | 輸出文字正常 | 未見立即退步 | 可跑但太慢 |
| sample2-15s-16k-mono | FP32 | GPU | 47.02 秒 | 3.13 | 與 FP32 CPU 一致 | 未見立即退步 | 目前最快候選 |
| sample2-15s-16k-mono | FP16 | GPU | 47.66 秒 | 3.18 | 與 FP32 GPU 一致 | 未見立即退步 | 沒有比 FP32 快 |
| sample2-60s-16k-mono | FP32 | GPU | 101.92 秒 | 1.70 | 輸出包含投信、外資、被動元件等投顧語境 | 未見立即退步 | 速度優勢可延伸到 60 秒 clip |

最終判定：

- 可行性：中到高；Breeze-ASR-25 可透過 Optimum Intel 匯出 OpenVINO FP32 / FP16，OpenVINO runtime 可看到 `CPU`、`GPU`、`NPU`，其中 GPU 是 `Intel(R) Arc(TM) Graphics (iGPU)`。
- 準確度風險：中；15 秒 clip 中 FP32 CPU、FP32 GPU、FP16 GPU 文字一致，60 秒 FP32 GPU 輸出也涵蓋投信、外資、被動元件等投顧語境。仍需在後續 adapter prototype 用更長音檔驗證。
- 實作風險：中；OpenVINO pipeline 輸出與 Whisper CLI JSON 不同，需要新增 OpenVINO-specific adapter 才能回到 `AsrTranscriptSegment`。
- 建議：採用 OpenVINO GPU FP32 作為下一步實作方向，整理成 OpenVINO-specific adapter prototype；CPU 只保留 fallback。

## 暫不做

- 不做 Vulkan / whisper.cpp / CrispASR 實作。
- 不做 OpenVINO INT8 或其他量化。
- 不做替代 ASR 模型選型。
- 不重寫研究報告分析流程。
- 不導入 RAG。

這些項目不是不好，而是它們會把問題從「保留 Breeze-ASR-25 加速」變成「換 backend、換格式、甚至換模型」。Phase A 先不要把範圍打開。

## Adapter fallback 原則

未來若新增 backend config，建議維持這個行為：

```text
preferred backend
  -> 成功：回傳 available，記錄 backend / device / elapsed_seconds
  -> 失敗：記錄錯誤，退回 Breeze-ASR-25 CPU
  -> CPU 也失敗：回傳 transcript_unavailable 或 unsupported_source
```

下游只應看到：

- `ResearchSourceImportResult.status`
- `ResearchSource.markdown_text`
- `ResearchSource.raw_text`
- `ResearchSource.notes`

下游不應該知道底層是 CPU、XPU 或 OpenVINO。

## Phase A 採用門檻

候選路線只有同時符合以下條件，才可以進入實作：

- 使用同一個 Breeze-ASR-25 模型或可證明等價的 OpenVINO FP32 / FP16 轉換結果。
- 對同一批台股音檔，專有名詞沒有明顯退步。
- 轉錄時間有穩定改善，而不是單次偶然變快。
- 失敗時可以自動或明確退回 CPU。
- 不破壞 `tests/test_asr_research.py` 既有 fake/mock 測試。

## 本階段結論

#43 的 Phase A 結論是：**採用 OpenVINO GPU FP32，放棄 PyTorch XPU 與 OpenVINO FP16，保留 CPU fallback。**

下一步不再繼續比較這三條路線，而是進入實作：

1. 新增 OpenVINO-specific ASR adapter prototype。
2. 將 OpenVINO 輸出轉回 `AsrTranscriptSegment` / `AsrTranscriptionResult`。
3. 保留 Breeze-ASR-25 CPU CLI adapter 作為 fallback。
4. 用 `sample2` 或更長投顧音檔驗證 OpenVINO GPU FP32 的長音檔穩定性。

實作追蹤：[#45 新增 OpenVINO ASR adapter：支援 Breeze-ASR-25 GPU FP32 轉錄](https://github.com/taiyu7/personal-stock-investment-system/issues/45)

## 參考資料

- GitHub issue：[#43 ASR Phase A：Breeze-ASR-25 保準確度加速可行性評估](https://github.com/taiyu7/personal-stock-investment-system/issues/43)
- 既有整合文件：[Breeze-ASR-25 安裝與整合流程](breeze-asr-25-setup.md)
- Obsidian 方法筆記：`C:\Users\taiyu\Obsidian\個人理財資訊系統\05-knowledge\methods\ASR 硬體加速 adapter 設定.md`
- PyTorch 官方文件：[Getting Started on Intel GPU](https://docs.pytorch.org/docs/stable/notes/get_start_xpu.html)
- Intel Extension for PyTorch 官方文件：[Retirement Plan](https://intel.github.io/intel-extension-for-pytorch/)
- OpenVINO 官方文件：[Automatic speech recognition using Whisper and OpenVINO with Generate API](https://docs.openvino.ai/2024/notebooks/whisper-asr-genai-with-output.html)
