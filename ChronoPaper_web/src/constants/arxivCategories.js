/** arXiv 计算机科学（cs.*）常用分类，用于抓取任务多选 */
export const ARXIV_CATEGORY_GROUPS = [
  {
    label: '人工智能与机器学习',
    options: [
      { value: 'cs.AI', label: 'cs.AI — 人工智能' },
      { value: 'cs.LG', label: 'cs.LG — 机器学习' },
      { value: 'cs.NE', label: 'cs.NE — 神经与进化计算' },
      { value: 'cs.CL', label: 'cs.CL — 计算语言学 / NLP' },
      { value: 'cs.IR', label: 'cs.IR — 信息检索' },
      { value: 'cs.MA', label: 'cs.MA — 多智能体系统' },
    ],
  },
  {
    label: '视觉与多媒体',
    options: [
      { value: 'cs.CV', label: 'cs.CV — 计算机视觉' },
      { value: 'cs.MM', label: 'cs.MM — 多媒体' },
      { value: 'cs.GR', label: 'cs.GR — 图形学' },
      { value: 'cs.SD', label: 'cs.SD — 音频 / 语音' },
    ],
  },
  {
    label: '系统、网络与数据',
    options: [
      { value: 'cs.DB', label: 'cs.DB — 数据库' },
      { value: 'cs.DC', label: 'cs.DC — 分布式计算' },
      { value: 'cs.DS', label: 'cs.DS — 数据结构与算法' },
      { value: 'cs.NI', label: 'cs.NI — 网络与互联网架构' },
      { value: 'cs.PF', label: 'cs.PF — 性能' },
      { value: 'cs.SI', label: 'cs.SI — 社交与信息网络' },
    ],
  },
  {
    label: '软件、安全与人机',
    options: [
      { value: 'cs.SE', label: 'cs.SE — 软件工程' },
      { value: 'cs.CR', label: 'cs.CR — 密码与安全' },
      { value: 'cs.HC', label: 'cs.HC — 人机交互' },
      { value: 'cs.RO', label: 'cs.RO — 机器人' },
      { value: 'cs.PL', label: 'cs.PL — 编程语言' },
    ],
  },
  {
    label: '其他',
    options: [
      { value: 'cs.CY', label: 'cs.CY — 计算机与社会' },
      { value: 'cs.ET', label: 'cs.ET — 新兴技术' },
      { value: 'cs.IT', label: 'cs.IT — 信息论' },
      { value: 'cs.OH', label: 'cs.OH — 其他计算机科学' },
    ],
  },
]

/** 扁平列表，供搜索过滤 */
export const ARXIV_CATEGORY_OPTIONS = ARXIV_CATEGORY_GROUPS.flatMap((g) => g.options)
