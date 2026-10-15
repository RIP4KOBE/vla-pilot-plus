# 文档交付说明（维护者审阅，不作为产品页）

仅在本目录准备文稿；未改仓库、运行中的 cohort 或依赖环境，未调用GPU/API/模型。文字中的已验证事实来自现有代码与真实报告；未实施项均为pending。

## 建议放置

| 草稿文件 | 最终位置 |
| --- | --- |
| README.md | 根 README.md；如原仓库还需支持其他策略，请保留必要总导航，不默默删除其他能力说明 |
| CONTRIBUTING.md | 根 CONTRIBUTING.md |
| docs/steering/architecture.md | 同相对位置 |
| docs/steering/installation.md | 同相对位置 |
| validated-inputs/steering-requirements-validated.txt | 拟替换 requirements-steering.txt |
| validated-inputs/steering-constraints-validated.txt | 拟新增 constraints-steering.txt |
| validated-inputs/steering-lerobot-base-validated.txt | 拟新增 requirements-steering-lerobot.txt |

三个安装输入按原文件字节复制，没有改pin。最终文件名与目录由整合owner决定；同步修改安装文档。此目录的REVIEW_NOTES与validated-inputs是审阅材料，不要求以当前布局发布。

## 合入前必须更新

1. 仅在完整EDS gate结案后更新其状态/成绩，并放入最终证据。不能由CPU通过或部分任务外推。
2. common Stage getter与VLS能力检查实施/验证后，重新核对architecture的“待实施”段，补实际接口、reset与parity证据；保持EDS科学行为。
3. 公共VLS profile显式处理effective guide80与逐任务表覆盖；QD待接入方案用sparse_priority，不能误抄当前关闭archive的uniform_cells值。最终profile与CLI名称由root冻结后复核文案。
4. 当前已有CLI已按代码读取核对；本轮文档没有重新执行它们。完整资产verifier与更细离线contract审计仍是待接入功能，其候选测试通过不能写成主线已通过。
5. 目前模型包获取位置、最终归档链接和最终三模式结果保留空缺。确有共享位置后才填写；不编造公开模型revision、资产可下载性或视频。
6. 真实clean环境完整安装曾先装v1、补future后形成v2最终输入；已验证最终环境，未声称按最终合并文件在第二个空环境重装。headless必须最后安装；新增包安装后复核active variant。
7. README范围聚焦RDT steering，不应删掉原仓库仍需协作支持的其他策略入口；可将本稿作为总README的一个主区块，保留原导航。

## 本轮核对来源（逻辑位置）

- 当前公共runner/config/worker和RDT policy/controller源码。
- 已完成干净安装报告与真实完整CPU日志；实际62依赖import、processor身份/行为、worker配置、pipcheck结果。
- 独立资产验证器的最终214文件与3归一化文件SHA报告；34个synthetic CPU用例。
- 已审阅的统一Stage接口parity设计、三模式profile设计及离线contract自包含fixture方案。

机器绝对路径与具体来源版本/研究目录映射仅保留README provenance。此目录没有运行新实验或产生新的性能结果。
