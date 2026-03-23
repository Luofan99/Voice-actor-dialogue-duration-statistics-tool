# Voice Duration Tool

一个可直接运行的 Python 命令行工具，用于统计“单人声源音频文件”的有效发声总时长。

它适用于：
- 单人声源音频
- 基于音量阈值的 MVP 统计方案
- 不仅统计正常台词，也会把笑声、喘气、叹气、语气词、哭声等非语言但属于人声表演的发声纳入统计

它不做：
- 说话人分离
- 声纹识别
- 复杂 AI 语音活动检测

当前版本基于 `pydub.silence.detect_nonsilent`，用“非静音区间”近似表示“有效发声片段”。

## 重要说明

本工具中的阈值单位使用 `dBFS`。

- `dBFS` 是数字音频中的相对电平单位
- 它不是现实世界声压级里的 `dB`
- 默认阈值为 `-40 dBFS`

这意味着：程序里“低于 -40 dBFS 视为静音或弱音”的判断，是基于数字音频信号强度，而不是现实物理环境中的分贝值。

## 功能特性

- 支持输入单个音频文件：`wav`、`mp3`、`m4a`
- 支持输入目录
- 支持 `--recursive` 递归扫描目录中的音频文件
- 输出控制台汇总
- 导出片段明细 `CSV`
- 导出结构化结果 `JSON`
- 目录模式下额外导出 `batch_summary.csv`
- 支持完全静音文件，不报错
- 对 `ffmpeg` 缺失、文件不存在、格式不支持等情况有基础报错提示

## 依赖安装

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

`requirements.txt` 当前内容：

```txt
pydub>=0.25.1
```

### 2. 安装 ffmpeg

如果你要处理 `mp3` 或 `m4a`，通常需要安装 `ffmpeg`，并确保 `ffmpeg` / `ffprobe` 已加入系统 `PATH`。

Windows 常见做法：
- 下载 ffmpeg 预编译版本
- 解压后把 `bin` 目录加入系统环境变量 `PATH`
- 在终端执行 `ffmpeg -version` 验证

如果只处理部分 `wav` 文件，有时也能工作，但推荐仍然安装 ffmpeg，兼容性最好。

## 使用方法

### 单文件模式

```bash
python voice_duration_tool.py input.wav --outdir ./output
```

### 指定参数

```bash
python voice_duration_tool.py input.wav --outdir ./output --silence-thresh -38 --min-silence-len 300 --seek-step 1 --keep-silence 50
```

### 目录模式

```bash
python voice_duration_tool.py ./audios --outdir ./output
```

### 目录递归模式

```bash
python voice_duration_tool.py ./audios --outdir ./output --recursive
```

Windows 路径示例：

```bash
python voice_duration_tool.py "C:\audio\data\sample.wav" --outdir "C:\audio\output"
```

## 命令行参数

```bash
python voice_duration_tool.py INPUT_PATH [options]
```

参数说明：

- `input_path`
  输入音频文件或目录路径

- `--outdir`
  输出目录，默认 `./output`

- `--silence-thresh`
  静音阈值，单位 `dBFS`，默认 `-40`

- `--min-silence-len`
  最短静音长度，单位毫秒，默认 `400`

- `--seek-step`
  扫描步长，单位毫秒，默认 `1`

- `--keep-silence`
  对每个检测到的非静音片段，两侧额外保留的静音长度，单位毫秒，默认 `0`

- `--recursive`
  当输入为目录时，递归扫描目录下所有支持的音频文件

## 统计逻辑

程序核心流程如下：

1. 读取音频文件
2. 使用 `pydub.silence.detect_nonsilent` 检测全部非静音区间
3. 将这些区间视为“有效发声片段”
4. 如果设置了 `--keep-silence`，则在片段两侧扩展对应时长
5. 计算每个片段的起止时间、时长
6. 汇总全部片段的总有效发声时长

这个定义下，只要声音强度高于阈值，就可能被计入，包括：
- 正常说话
- 笑声
- 喘气
- 叹气
- 哭声
- 语气词

同时，长时间静音或明显过弱的声音一般不会计入。

## 输出说明

### 控制台输出

每个文件会打印：

- 文件名
- 音频总时长
- 检测到的有效发声片段数
- 有效发声总时长
- 有效发声占比
- 导出的 CSV 路径
- 导出的 JSON 路径

示例：

```text
文件名: input.wav
音频总时长: 12.345 秒
检测到的有效发声片段数: 4
有效发声总时长: 5.678 秒
有效发声占比: 0.4599
CSV 明细: C:\...\output\input_segments.csv
JSON 明细: C:\...\output\input_segments.json
------------------------------------------------------------
```

### CSV 明细

文件名格式：

```text
{音频文件名去后缀}_segments.csv
```

字段：

```csv
segment_id,start_ms,end_ms,duration_ms,start_seconds,end_seconds,duration_seconds
```

### JSON 明细

文件名格式：

```text
{音频文件名去后缀}_segments.json
```

结构示例：

```json
{
  "input_file": "C:\\path\\to\\input.wav",
  "audio_duration_ms": 12345,
  "audio_duration_seconds": 12.345,
  "parameters": {
    "silence_thresh_dbfs": -40.0,
    "min_silence_len_ms": 400,
    "seek_step_ms": 1,
    "keep_silence_ms": 0
  },
  "summary": {
    "segment_count": 4,
    "total_voiced_ms": 5678,
    "total_voiced_seconds": 5.678,
    "voiced_ratio": 0.4599
  },
  "segments": [
    {
      "segment_id": 1,
      "start_ms": 1000,
      "end_ms": 1800,
      "duration_ms": 800,
      "start_seconds": 1.0,
      "end_seconds": 1.8,
      "duration_seconds": 0.8
    }
  ]
}
```

### 批量汇总 CSV

当输入为目录时，会额外生成：

```text
batch_summary.csv
```

字段：

```csv
file_name,file_path,audio_duration_seconds,segment_count,total_voiced_seconds,voiced_ratio
```

## 完全静音文件

如果输入文件完全静音，程序不会报错。

结果会是：

- `segment_count = 0`
- `total_voiced_seconds = 0`
- `voiced_ratio = 0`

对应的 CSV 会只有表头，JSON 中 `segments` 会是空数组。

## 参数调优建议

不同录音环境下，推荐按实际情况调整参数。

### 1. 漏检较多

如果轻声、气声、叹气、弱笑声没有被统计进去，可以尝试：

- 把 `--silence-thresh` 调低，例如从 `-40` 改为 `-45`

示例：

```bash
python voice_duration_tool.py input.wav --outdir ./output --silence-thresh -45
```

### 2. 环境噪声被误算

如果底噪、空调声、房间噪声被当成发声，可以尝试：

- 把 `--silence-thresh` 调高，例如从 `-40` 改为 `-35`

示例：

```bash
python voice_duration_tool.py input.wav --outdir ./output --silence-thresh -35
```

### 3. 片段切得太碎

如果一句话中间轻微停顿就被切开，可以尝试：

- 增大 `--min-silence-len`，例如从 `400` 改为 `600`

### 4. 希望片段边界更自然

如果希望导出的片段前后留一点余量，可以尝试：

- 设置 `--keep-silence 50` 或 `--keep-silence 100`

这会扩展导出的片段边界，但不会超出音频总长度，也不会小于 `0 ms`。

## 常见问题

### 1. 报错：未检测到 ffmpeg/ffprobe

原因：
- 系统没有安装 ffmpeg
- 已安装但没有加入 `PATH`

处理方式：
- 安装 ffmpeg
- 重开终端
- 执行 `ffmpeg -version` 检查是否生效

### 2. 报错：No module named 'pydub'

说明没有安装 Python 依赖。

执行：

```bash
pip install -r requirements.txt
```

### 3. 为什么“笑声、喘气”也会被统计进去？

因为本工具的目标是统计“有效发声”，而不是“有台词的语音内容”。

只要这些声音在音量上高于阈值，它们就会被视为有效发声片段。

### 4. 为什么很弱的人声没有被算进去？

因为当前版本是基于阈值的 MVP 方案。

如果人声太弱，低于设定的 `dBFS` 阈值，就会被当成静音或弱音忽略。此时可以调低：

```bash
--silence-thresh
```

### 5. 为什么有些背景噪声会被算进去？

因为当前不是 AI 语音活动检测，也不区分“人声”和“非人声”，只看是否属于非静音区间。

如果背景噪声较大，可以：

- 调高 `--silence-thresh`
- 增大 `--min-silence-len`
- 先做降噪或清洗音频

## 文件说明

- [voice_duration_tool.py](/c:/Users/Frank/Desktop/py_test/voice_duration_tool.py)
  主程序

- [requirements.txt](/c:/Users/Frank/Desktop/py_test/requirements.txt)
  Python 依赖

- `README.md`
  使用说明

## 快速开始

```bash
pip install -r requirements.txt
python voice_duration_tool.py input.wav --outdir ./output
```

如果你处理的是 `mp3` 或 `m4a`，请先确认 ffmpeg 可用。
