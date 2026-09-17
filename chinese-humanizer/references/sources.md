# 素材出处与可信度

这个 skill 的规则来自四类资料。下面记出处、许可与需要留意的地方；研读用的工作底稿（仓库克隆、论文 PDF、文章文本、精读摘要）保存在仓库之外的本地目录，不随技能发布。

## 一、中文 skill 仓库

星数为 2026-09 读取的快照，会随时间变化，只作粗略的流行度参考，不当作质量指标。

| 仓库 | 星数 | 许可 | 用它什么 |
| --- | --- | --- | --- |
| [LifelongLazyLearner/qu-ai-wei](https://github.com/LifelongLazyLearner/qu-ai-wei) | 576 | MIT | 症状目录的分层与字段设计（骨架 / 触发 / 保护 / 动作 / 复扫）、证据分级、保护边界 |
| [Hyacehila/humanizer-zh-next](https://github.com/Hyacehila/humanizer-zh-next) | 103 | MIT | 体裁矩阵、误判清单、「改写而非删除」的等量覆盖原则 |
| [op7418/humanizer-zh](https://github.com/op7418/humanizer-zh) | 17,391 | MIT | blader/humanizer 的中译，模式分类；中文场景中已标注不适用的条目（标题大写、弯引号） |
| [0xtresser/cn-humanizer](https://github.com/0xtresser/cn-humanizer) | 13 | 声明 MIT 但仓库无 LICENSE 文件 | 12 条翻译腔修正、中文 AI 词表；**引用时注意**：样本改写里出现过补造事实的内容（把「B 轮融了 2 亿」补进原文），与「不新增事实」原则冲突，这里只取它的词表与翻译腔对照 |

上游关系：humanizer-zh 译自 blader/humanizer，humanizer-zh-next 是它的维护分支；qu-ai-wei 与 cn-humanizer 是独立的中文旁支，本地化规则最细。

## 二、英文 skill 仓库

| 仓库 | 星数 | 许可 | 用它什么 |
| --- | --- | --- | --- |
| [blader/humanizer](https://github.com/blader/humanizer) | 49,115 | MIT | 模式编号制、强度分级（一见即改 / weak alone）、自检步骤、不动作清单、声音校准、三种输出契约 |
| [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop) | 17,237 | MIT | 交付前 Quick Checks 清单、五维评分与重写线 |
| [AIScientists-Dev/academic-humanizer](https://github.com/AIScientists-Dev/academic-humanizer) | 1,580 | NOASSERTION | 领域分层结构、保留清单、「原五段改后也五段」的等量原则、论断与证据匹配 |
| [brandonwise/humanizer](https://github.com/brandonwise/humanizer) | 118 | MIT | 词汇三档分级、正面写法篇与禁令篇并列 |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 87,671 | MIT | 把「少用」改成可机械验证的硬约束、交付前逐项打勾的 Pre-Flight |
| [alchaincyf/nuwa-skill](https://github.com/alchaincyf/nuwa-skill) | 32,765 | MIT | 声音校准的六个维度、独立评分不可自评、迭代上限 |

英文侧的模式只能取机制，形态不能照搬：连字符复合词、Title Case、弯引号、-ly 副词、Wh- 句首都是英文产物；中文的弯引号反过来是规范写法。

## 三、论文

| 文献 | 用途 |
| --- | --- |
| [CCL 2023（2023.ccl-1.46）](https://aclanthology.org/2023.ccl-1.46/) | 中文人机文本的句长、用词、句法、衔接差异，159 项特征 + 判别力排序。本 skill 数字的主要来源 |
| [CCL 2025（2025.ccl-1.64）](https://aclanthology.org/2025.ccl-1.64/) | 中文社媒短评的风格差异与检测性能 |
| [ACL 2024（2024.acl-long.298）](https://aclanthology.org/2024.acl-long.298/) | 篇章结构（motif）能否区分人机，英文语料 |
| [EMNLP 2024（2024.emnlp-main.368）](https://aclanthology.org/2024.emnlp-main.368/) | 句法模板复用，英文语料；作者声明不用于检测 |
| [EMNLP 2024（2024.emnlp-main.885）](https://aclanthology.org/2024.emnlp-main.885/) | 检测方法与改写攻击下的鲁棒性对比 |
| [arXiv 2304.02819](https://arxiv.org/abs/2304.02819) | 商用检测器对非母语写作者的系统性偏见 |
| [arXiv 2402.01158](https://arxiv.org/abs/2402.01158) | 中文文档级与句级检测；人机混合文本的失效区间 |

论文只提供「哪些特征有统计支持」，不提供写作规范。均值差异不等于「人类都这样」，见 `evidence.md`。

## 四、文章与词条

- 余光中《怎样改进英式中文——论中文的常态与变态》，原刊《明报月刊》1987 年 10 月号。本机存了四个转载版本：dotblogs（繁体，最完整，含原刊编者注两处）、pixnet（繁体，用字经校订最干净）、chinadaily（简体，仅前半）、translators（简体，仅前四分之一）。**引用时用繁体两份**，简体版缺副词语、形容词、被动语气、结论等小节。
- 中文维基《[AI 生成文的特征](https://zh.wikipedia.org/wiki/Wikipedia:AI%E7%94%9F%E6%88%90%E6%96%87%E7%9A%84%E7%89%B9%E5%BE%B5)》：英文页的删节译本，缺 Ineffective indicators 与人类写作信号两节。页面自称「这是描述，不是规定」。
- 中文维基《[欧化中文](https://zh.wikipedia.org/wiki/%E6%AD%90%E5%8C%96%E4%B8%AD%E6%96%87)》《[翻译腔](https://zh.wikipedia.org/wiki/%E7%BF%BB%E8%AF%91%E8%85%94)》：用语定义与实例。
- 英文维基 [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) 与 [WikiProject AI Cleanup](https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup)：模式分类法的源头，明确限定是维基场景的检测指南。
- [去 AI 味完全指南 2026](https://www.aiposthub.com/remove-ai-flavor-complete-guide-2026/)：把中文 AI 味拆成公文腔与翻译腔两层，与本节结论一致；其中的工具清单未逐一核实。
- [去 AI 味十大 Agent skill](https://www.cnblogs.com/wintersun/p/20693837)：工具盘点，其列出的 GitHub 地址有占位嫌疑，未采用。

## 五、需要留意的引用问题

- 中文维基提到余光中分「善性欧化 / 恶性欧化」，1987 年原文只有「缓慢而适度的西化」「高妙的西化」与「恶性西化」，wiki 的术语是后人归纳，引用时不要挂到原文名下。
- 中文维基说余光中点名了朱自清《荷塘月色》与何其芳《雨前》，四版原文里没有这两处点名。
- 英文维基把 one of the best、is the only 列为**人类**写作信号，余光中把「最…之一」列为**病症**。两者不冲突（一个指绝对陈述，一个指回避绝对），但不要混用。
- 余光中原文的英文动词对照第三例在四个版本里都缺字，无法校补。
- 中文维基《欧化中文》记录了对余光中的反对意见：符合语法的欧化表达可以接受，很多已经融入日常汉语。本 skill 采纳的是「成簇且读着不顺才改」这个较弱的版本，不是「一切欧化都要改」。

## 六、怎么更新

- 新增模式时，在 `symptoms.md` 对应层里加条目，写明触发条件与保护项，并标证据等级。
- 新增中文实证研究时，把数字抄进 `evidence.md`，注明样本与年份；不要只写结论。
- 词表更新放进 `vocabulary.md`，注明是哪个来源收录的。
- 任何来源如果无法核实，标出来，别混进正文。
