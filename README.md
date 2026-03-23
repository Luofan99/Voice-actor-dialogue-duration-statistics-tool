# 配音演员台词时长统计工具

这是一个给非技术人员也能直接使用的小工具。

把需要统计的音频或视频文件放进 [`input`](/c:/Users/Frank/Desktop/py_test/input)，双击运行 [`run_all.bat`](/c:/Users/Frank/Desktop/py_test/run_all.bat)，结果会自动输出到 [`output`](/c:/Users/Frank/Desktop/py_test/output)。

## 使用步骤

1. 安装 Python 依赖：

```bash
pip install -r requirements.txt
```

2. 安装 `ffmpeg`，并确认 `ffmpeg`、`ffprobe` 已加入系统 `PATH`

3. 把要统计的文件放进 [`input`](/c:/Users/Frank/Desktop/py_test/input)

4. 双击运行 [`run_all.bat`](/c:/Users/Frank/Desktop/py_test/run_all.bat)

5. 到 [`output`](/c:/Users/Frank/Desktop/py_test/output) 查看结果

## 支持格式

- 音频：`wav` `mp3` `m4a` `aac` `flac` `ogg` `wma`
- 视频：`mp4` `mov` `mkv` `avi` `wmv` `m4v`

## 输出内容

每个文件都会生成两份明细：

- `{文件名}_segments.csv`
- `{文件名}_segments.json`

此外还会生成一个总表：

- [`output/all_files_summary.csv`](/c:/Users/Frank/Desktop/py_test/output/all_files_summary.csv)

总表会记录：

- 文件名
- 文件类型
- 文件路径
- 总时长
- 有效发声片段数
- 有效发声总时长
- 有效发声占比
- 对应的明细 CSV 路径
- 对应的明细 JSON 路径
- 处理状态
- 错误信息

## 默认规则

- 默认扫描整个 `input` 文件夹
- 默认递归扫描子文件夹
- 默认把结果写入 `output`
- 使用 `pydub.silence.detect_nonsilent` 检测非静音片段
- 默认静音阈值为 `-40 dBFS`

## 命令行用法

如果你仍然想手动执行，也可以直接运行：

```bash
python voice_duration_tool.py
```

它会默认处理 `input` 文件夹。

如果要自定义参数，例如：

```bash
python voice_duration_tool.py input --outdir output --silence-thresh -38 --min-silence-len 300 --keep-silence 50
```

## 常见问题

### 提示没有 ffmpeg/ffprobe

说明系统里没有安装 ffmpeg，或没有加入 `PATH`。

### 提示没有找到可处理文件

说明 [`input`](/c:/Users/Frank/Desktop/py_test/input) 里还没有支持格式的音频或视频。

### 为什么笑声、喘气声也会被算进去

这个工具统计的是“有效发声”，不是“带台词的语音文本”。只要声音强度高于阈值，就可能被计入。
