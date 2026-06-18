import { CURRENT_YEAR } from '@/constants/openalexVenues'

/** @typedef {'latest'|'explore'|'smart'|'manual'} CrawlMode */

export const CRAWL_MODE_OPTIONS = [
  {
    value: 'latest',
    label: '最新文献跟踪',
    description: '以 arXiv 预印本为主，低语义门槛、不启用质量过滤，按关键词检索最新相关稿件',
  },
  {
    value: 'explore',
    label: '领域探索',
    description: 'OpenReview 顶会录用 + OpenAlex CCF A/B，启用质量分过滤；会议/分类仅作质量偏好',
  },
  {
    value: 'smart',
    label: '智能规划',
    description: '由大模型根据领域描述自动选择数据源、分类与关键词，并核验推荐论文标题',
  },
]

export const CRAWL_MODE_LABELS = {
  latest: '最新文献跟踪',
  explore: '领域探索',
  smart: '智能规划',
  manual: '手动设计',
}

/** @returns {Record<string, unknown>} */
export function getCrawlModePreset(mode) {
  switch (mode) {
    case 'latest':
      return {
        enable_smart_planning: false,
        sources: ['arxiv'],
        categories: ['cs.AI', 'cs.LG', 'cs.CL', 'cs.CV'],
        openreview_venues: [],
        openalex_venue_types: ['conference', 'journal'],
        openalex_ccf_ranks: ['A', 'B', 'C'],
        openalex_year_from: CURRENT_YEAR - 1,
        openalex_year_to: CURRENT_YEAR,
        openalex_venue_names: '',
        enable_quality_filter: false,
        min_semantic_score: 48,
        min_quality_score: 50,
        max_papers_per_run: 30,
      }
    case 'explore':
      return {
        enable_smart_planning: false,
        sources: ['openreview', 'openalex'],
        categories: [],
        openreview_venues: [
          'ICLR.cc/2025/Conference/-/Submission',
          'NeurIPS.cc/2024/Conference/-/Submission',
          'ICML.cc/2024/Conference/-/Submission',
          'ACL.org/2024/Conference/-/Submission',
        ],
        openalex_venue_types: ['conference', 'journal'],
        openalex_ccf_ranks: ['A', 'B'],
        openalex_year_from: CURRENT_YEAR - 3,
        openalex_year_to: CURRENT_YEAR,
        openalex_venue_names: '',
        enable_quality_filter: true,
        min_semantic_score: 50,
        min_quality_score: 50,
        max_papers_per_run: 30,
      }
    case 'smart':
      return {
        enable_smart_planning: true,
        sources: ['arxiv'],
        categories: [],
        openreview_venues: [],
        openalex_venue_types: ['conference', 'journal'],
        openalex_ccf_ranks: ['A', 'B', 'C'],
        openalex_year_from: CURRENT_YEAR - 2,
        openalex_year_to: CURRENT_YEAR,
        openalex_venue_names: '',
        keywords: '',
        enable_quality_filter: false,
        min_semantic_score: 50,
        min_quality_score: 50,
        max_papers_per_run: 50,
      }
    default:
      return {}
  }
}

export function applyCrawlModePreset(form, mode) {
  const preset = getCrawlModePreset(mode)
  return {
    ...form,
    ...preset,
    crawl_mode: mode,
  }
}

export function crawlModeSummary(mode) {
  const opt = CRAWL_MODE_OPTIONS.find((o) => o.value === mode)
  return opt?.description || ''
}
