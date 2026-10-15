# N24 task0：终轮 full8 与原 eligibility 成员关系

两例未选 full8（step304、408）都是原 `eligible_indices=[]`：full8候选没有通过原 eligibility 门，并不存在“合格full8被其他候选压过”的记录。二者最终选择恰为原记录的 native_argmin_index。本结论只说明原记录的成员关系，不解释具体哪项几何条件失败，也不推断物理抓握或成功率。

## 全部14个决策

full8是先前已关闭诊断中的终轮iter9候选前8步gripper均为正命令的行索引；本次只复用已有符号记录。selected index、fingerprint、occurrence_id逐条与本attempt的原metrics匹配。

| step | full8 indices | 原eligible indices | full8∩eligible | selected | native argmin | 实选正命令/8 | 分类 |
|---:|---|---|---|---:|---:|---:|---|
| 0 | [] | [] | [] | 5 | 5 | 0 | 终轮无full8 |
| 8 | [] | [] | [] | 1 | 1 | 0 | 终轮无full8 |
| 16 | [] | [] | [] | 6 | 6 | 0 | 终轮无full8 |
| 160 | [] | [] | [] | 1 | 1 | 0 | 终轮无full8 |
| 232 | [] | [] | [] | 1 | 1 | 0 | 终轮无full8 |
| 240 | [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15] | [2,5,10,14] | [2,5,10,14] | 5 | 5 | 8 | 选中合格full8 |
| 304 | [14] | [] | [] | 8 | 8 | 3 | full8均不合格 |
| 312 | [0,1,2,3,4,5,6,8,9,10,11,12,13,14,15] | [1,3,11,14] | [1,3,11,14] | 3 | 3 | 8 | 选中合格full8 |
| 320 | [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15] | [0,3,7,9,11] | [0,3,7,9,11] | 9 | 9 | 8 | 选中合格full8 |
| 328 | [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15] | [0,1,2,3,4,5,7,8,9,15] | [0,1,2,3,4,5,7,8,9,15] | 9 | 9 | 8 | 选中合格full8 |
| 392 | [] | [] | [] | 11 | 11 | 0 | 终轮无full8 |
| 400 | [] | [] | [] | 0 | 0 | 0 | 终轮无full8 |
| 408 | [5] | [] | [] | 2 | 2 | 0 | full8均不合格 |
| 416 | [6,7,8,14,15] | [6] | [6] | 6 | 3 | 8 | 选中合格full8 |

完整分母：7/14终轮没有full8；5/14选中full8且属于原eligible集合；2/14有full8但全部不eligible；0/14出现“存在eligible full8却未选中full8”。

- step304：full8仅row14；eligible为空；选row8，等于native argmin，原记录3/8正命令。
- step408：full8仅row5；eligible为空；选row2，等于native argmin，原记录0/8正命令。
- step416：full8为[6,7,8,14,15]，eligible仅[6]，最终选6；原native argmin为3。这是已有selector记录中与native argmin不同的一例。这里没有重算排序、成本或替代动作，也不能将它归因于某个早先rescue后代。
- 全14条原记录 `target_index=0`，`recognition_reason=recognized_weighted_distance_template`。这是原记录的模板识别标签，不是额外provider核验、物理目标真实性或几何正确性证据。

## 输入、执行与边界

本次读取metrics payload 1,474,424 bytes，仅1次，同一读取bytes验证SHA后解析。没有读取.pt、其他attempt、运行中或保护数据。已关闭命令结果和审查记录按冻结SHA绑定；审查记录仅做hash关联，未扩取其他结果字段。提取耗时0.031653691秒，低于30秒。
CPU环境线程上限2，实际为stdlib单线程；CUDA不可见、torch/numpy/runtime均未导入，network/process/import/read/write guard拦截0。精确输入清单及extractor在首次metrics读取前冻结。14份partial记录、完整结果、CSV和原运行日志保留，没有失败重跑。
未查看geometry、distance、cost、quality、provider returns/prompts/images；未重算eligibility、ranking或门槛。eligibility为空只支持“不属于原eligible集合”，无法细分是哪一距离/高度/其他子条件造成。不能以本诊断判定门槛正确或错误。
JSON文件在解析时包含其他字段，程序只投影scope许可的字段；没有分析未授权字段值。没有修改I/V/W源码、当前实验规则、state、ledger、预算或权限。没有新候选实现或保护集放行。

## 哈希索引

- Scope: `064f5674a25da0e52514d840ca958a1c4ac593b2d8d2ef753d6cf452363cacad`
- Input manifest: `ff4769e730d8ce64420789227e886889deb15e13d94d1c8a27dd68d21aa604bf`
- Extractor（含guard）: `f8515f0c4248df76a56550c8867f65f356b04da453332cfefea8ad9d70b7065b`
- Metrics原输入: `b80ca4ebc9ae17e19db06dde1756045e7523dc33611c695cda1eb4df078d12f7`
- 闭合命令诊断: `a64c5dca8291ec2846e75fe25170e4b8da158294eebe2ee7b68fe0b543bdee4d`
- 原诊断root review: `8701cca41b4994c1abd7139de5d645bec98f9c132bbcab38cdf49a37d1147774`
- 本次结果: `d08a0af18c79ee1a4bc9f7f3d5f9f30af5f3568d23e91358cdbf4d6ae2e251a4`

全部输出由output-manifest-v1.json绑定。本次读取范围已关闭，不继续扩大读取或修改算法。
