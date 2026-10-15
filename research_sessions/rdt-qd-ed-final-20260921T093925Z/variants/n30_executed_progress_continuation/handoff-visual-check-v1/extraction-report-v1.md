# N30 固定视频帧提取闭合

两份视频各完成一次 CPU ffmpeg 提取，无解码重试。每视频固定零基帧 16、20、24、28、32、40，共 12 张 640×640 PNG，总计 6,163,405 bytes。路径、原始帧号和逐张 SHA256 见 `frames-manifest-v1.json`；解码前冻结输入见 `input-manifest-v1.json`。两输入各完整编码哈希一次，共 13,331,924 bytes，另各一次 header-only ffprobe 和一次 ffmpeg。

|视频|解码帧数|读取 packets|导出 PNG|退出码|
|---|---:|---:|---:|---:|
|task0|44|46|6|0|
|task1|44|46|6|0|

`trim=end_frame=41` 后选择固定帧；codec 参考帧、线程缓冲和 read-ahead 导致各解码 44 帧，不能声称仅六帧或仅 41 帧。41–43 未导出或分析。没有裁剪、空间缩放、增强或新增 overlay；保持编码视频 640×640 尺寸和已有 overlay。FFmpeg 正常进行 yuv420p→rgb24 PNG 色彩转换，不声称编码像素字节不变。日志有 `-vsync` 弃用提示，无报告的解码错误；未因此重跑。

Main 每 episode 清空 recorder（1496），在 `adapter.step`（2141）前 `add_frame`（2133）；vis_utils 按 append 顺序保存（656–682、758–765）。静态映射 frame24 为 step23 后、step24 前，frame32 为 step31 后、step32 前。来源哈希及窗口见 `source-mapping-inputs-v1.json`。Executor 未看图，实际 overlay Step 核验留给 root；不一致须保留 Unknown。header 声明 720帧/72秒/10fps，不是全流解码核验，视频秒数不等同 20Hz 环境时间。save_video 将终局 FAIL 覆盖到所有帧（vis_utils 726–752），不能视作该帧失败证据。

提取 parent+child CPU 1.236989708000 秒，外层工作 wall 1.300373162958 秒；affinity [0,1]、线程2、CUDA_VISIBLE_DEVICES 空、hwaccel none。六条 version/probe/decode 命令全部 exit0，精确 argv/PID/限额/日志见 `extraction-resource-v1.json`。静态来源核验另计 0.003160021 CPU秒；行政封装保守上界少于30CPU秒，见 `administrative-packaging-v1.json`。一次行政日志措辞断言失败单独保留于 `packaging-failure-v1.txt`；没有再次打开视频或执行decoder。

Executor 未解释图片，未判断接触、抓握、目标身份或 handoff 因果。无新模型、API、GPU、仿真、tensor/Stage 读取或源码/状态/预算变更。输出现冻结，等待 root 看图；本任务结束。
