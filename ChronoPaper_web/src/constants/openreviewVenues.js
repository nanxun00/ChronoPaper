/** OpenReview venue invitation（免费公开 API；抓取时自动过滤投稿中/拒稿，仅保留已接收） */
export const OPENREVIEW_VENUE_GROUPS = [
  {
    label: 'ICLR',
    options: [
      { value: 'ICLR.cc/2025/Conference/-/Submission', label: 'ICLR 2025（已接收）' },
      { value: 'ICLR.cc/2024/Conference/-/Submission', label: 'ICLR 2024（已接收）' },
      { value: 'ICLR.cc/2023/Conference/-/Submission', label: 'ICLR 2023（已接收）' },
    ],
  },
  {
    label: 'NeurIPS',
    options: [
      { value: 'NeurIPS.cc/2024/Conference/-/Submission', label: 'NeurIPS 2024（已接收）' },
      { value: 'NeurIPS.cc/2023/Conference/-/Submission', label: 'NeurIPS 2023（已接收）' },
    ],
  },
  {
    label: 'ICML',
    options: [
      { value: 'ICML.cc/2024/Conference/-/Submission', label: 'ICML 2024（已接收）' },
      { value: 'ICML.cc/2023/Conference/-/Submission', label: 'ICML 2023（已接收）' },
    ],
  },
  {
    label: 'ACL / EMNLP',
    options: [
      { value: 'ACL.org/2024/Conference/-/Submission', label: 'ACL 2024（已接收）' },
      { value: 'EMNLP/2024/Conference/-/Submission', label: 'EMNLP 2024（已接收）' },
    ],
  },
]

export const OPENREVIEW_VENUE_OPTIONS = OPENREVIEW_VENUE_GROUPS.flatMap((g) => g.options)

export const ACCEPTANCE_STATUS_LABELS = {
  accepted: '已接收',
  oral: 'Oral',
  spotlight: 'Spotlight',
  poster: 'Poster',
  submitted: '投稿中',
  rejected: '拒稿',
  desk_rejected: 'Desk Reject',
  withdrawn: '撤回',
  unknown: '未知',
}

export const SOURCE_LABELS = {
  arxiv: 'arXiv',
  openreview: 'OpenReview',
  openalex: 'OpenAlex',
}
