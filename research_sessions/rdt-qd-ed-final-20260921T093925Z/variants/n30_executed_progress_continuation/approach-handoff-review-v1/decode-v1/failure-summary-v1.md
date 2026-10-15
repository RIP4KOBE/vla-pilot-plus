# 单次执行未进入数据读取

**FAILED_BEFORE_PAYLOAD，exit1。** 外部wall 0.043986201秒，child CPU 0.042491秒；timeout进程PID3856346/start_ticks93676756已回收。冻结reader、精确argv和原release均保持不变。

错误来自执行器外部wrapper：为了行政包装≤30CPU秒而将自身RLIMIT_CPU软/硬限均设为30，子进程继承硬限，reader在第7行设置冻结120秒时抛出 `ValueError: not allowed to raise maximum limit`。这是启动配置缺陷，不是输入、科学或手头decoder分析失败。

失败发生在AS设置、guard安装、授权检查、Torch导入及任何payload读取之前；无invocation/progress/partial/result/resource产物。零payload read/hash/load，未取得两格step16→24的运动、Stage或夹爪新结论，全部Unknown。因为guard和CUDA探测未运行，denied probes/CUDAinitialized字段为null，不伪写guard-clean或测得false。

保留execution-v1.log、external-execution-v1.json与execution-closure-v1.json，未自动重试、未改reader、未触碰源/state/budget。研究Goal未完成；后续是否允许一次修正launcher执行由root另行冻结，不由本失败隐式授权。
