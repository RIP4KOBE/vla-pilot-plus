# N28 闭轮数值 lineage reader：准备交付

**准备完成，未读取任何 tensor 内容，未执行 reader。** 本次只做静态 schema/身份绑定、代码编写和 AST 语法检查，不把这些检查写成数值或运行时测试通过。

覆盖本轮 N28 cohort 的 tasks0..3 × N27/N28 全部8格；首 guided均可绑定。八容器 stat 总94,315,816字节，未来必须分别一次整容器weights_only解码，不能称只读取所选 tensor 字节。独立终态/同进程审计身份及原receipt refs纳入固定清单；原索引/metrics仅读首完整行，整文件hash仍为原receipt attestation。无旧cohort样本、未按N27 task2成功或数值活动挑选。

11个 witness 是每首guided每slot首active call：并非N27全部19调用、N28全部14调用，更非整episode。N27 initial/rollout、N28 initial/parent明确分开。固定公式包括实际assigned delta与proposed operand区别，原生精确±1内外/边界转移，CPU FP64 norm/roughness/cumulative proxy，centered16×24 SVD与固定rank容差，delta能量的经验行空间残差，以及delta norm/原before分布RMS半径（零spread=null）。N28 parent→child仅在精确已记录身份映射成立时描述差值和内积，绝不称因果attenuation/survival。

未来执行限制：单进程、2CPU/线程、AS8GiB在Torch导入前设置；CPU120s、完整wall120s（root需外层硬超时及进程计时）；8容器各一次。ZIP单容器64MiB、decoded storage单容器64MiB/合计512MiB、输入合计128MiB。8GiB依赖导入兼容性及guard实际运行**未在本准备测试**；若失败，保留marker、partial/log/Unknown读计数，不自动加额重跑。正常Python/Torch依赖只读，精确self/maps与字符设备/dev/null为拟定启动例外；没有模型/生产helper导入或网络子进程。

文件：`reader-v1.py`、`protocol-v1.md`、`static-schema-v1.json`、`input-bindings.frozen.v1.json`、`execution-release.template-v1.json`（disabled），另保留原draft与准备来源/资源记录。新root review须按协议schema绑定三个hash，后续release另给明确CPU_NUMERICAL_LINEAGE_ONLY；冻结输入自身仍executable=false。无GPU/API/model/sim/episode或算法授权。

- reader SHA256：`f121c1f7d7ea9c1e56f0bc56e382bfeca024d00feb9426979e4320f124022380`
- protocol SHA256：`6cb47ff3fe58ee0ec0219ab448d080f4e2af7ea3ca3620d0945febace86cd001`
- frozen inputs SHA256：`242c0038fe1a2b952ffb59a6093acb24c38eb96f3110539e8ce7897b4602336b`

原closed-linkage审计误输出numeric vectors的偏差继续保留；本次只输出精确白名单身份/类型/大小等，未再输出完整decision/成本向量，也不使用误见数值拟合任何阈值。最后一项小收口仅让失败的payload读尝试在字节/次数尚不能确认时保留null，避免错误报告0；未执行该路径。交付后停止供root审阅。
