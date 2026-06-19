/** G6 知识图谱可视化共享配置（A/B/C/D 方案） */

export const DEFAULT_SAMPLE_COUNT = 30

const DOMAIN_COLORS = [
  '#5B8FF9', '#5AD8A6', '#5D7092', '#F6BD16', '#E8684A',
  '#6DC8EC', '#9270CA', '#FF9D4D', '#269A99', '#FF99C3',
]

const domainColorMap = new Map()

export function truncateLabel(text, maxLen = 14) {
  const s = String(text || '').trim()
  if (!s) return 'unknown'
  if (s.length <= maxLen) return s
  return `${s.slice(0, maxLen)}…`
}

export function truncateText(text, maxLen = 120) {
  const s = String(text || '').trim()
  if (!s) return ''
  if (s.length <= maxLen) return s
  return `${s.slice(0, maxLen)}…`
}

const NODE_TYPE_COLORS = {
  Paper: '#5B8FF9',
  Model: '#5AD8A6',
  Dataset: '#F6BD16',
  Metric: '#E8684A',
  Venue: '#9270CA',
  Author: '#6DC8EC',
  Entity: '#C2C8D5',
}

export function getNodeTypeColor(type) {
  return NODE_TYPE_COLORS[type] || '#C2C8D5'
}

export function resolveNodeFill(node, options = {}) {
  const { colorByDomain = false } = options
  const taskDomain = node?.task_domain || ''
  if (colorByDomain && taskDomain) {
    return getDomainColor(taskDomain)
  }
  return getNodeTypeColor(node?.type)
}

export function getDomainColor(domain) {
  const key = String(domain || '').trim().toLowerCase()
  if (!key) return '#C2C8D5'
  if (!domainColorMap.has(key)) {
    domainColorMap.set(key, DOMAIN_COLORS[domainColorMap.size % DOMAIN_COLORS.length])
  }
  return domainColorMap.get(key)
}

export function buildNodeSubtitle(node) {
  const type = node?.type || ''
  if (type === 'Paper' && node?.task_domain) {
    return truncateLabel(node.task_domain, 18)
  }
  return ''
}

export function buildMetaLine(node) {
  const parts = []
  if (node?.venue) parts.push(node.venue)
  if (node?.year) parts.push(String(node.year))
  if (node?.type === 'Venue' && node?.ccf_rank && node.ccf_rank !== 'None') {
    parts.push(node.ccf_rank)
  }
  return parts.join(' · ')
}

export function buildTooltipHtml(node, options = {}) {
  const d = node || {}
  const nodeId = options.nodeId || ''
  const type = d.nodeType || d.type || ''
  const lines = []

  if (type !== 'Paper' && d.taskDomain) {
    lines.push(`<div class="g6-tooltip-tag">领域：${escapeHtml(d.taskDomain)}</div>`)
  }

  if (type !== 'Paper' && d.description) {
    lines.push(`<div class="g6-tooltip-desc">描述：${escapeHtml(truncateText(d.description, 200))}</div>`)
  }

  if (type === 'Paper') {
    const meta = buildMetaLine({
      venue: d.venue,
      year: d.year,
      type,
      ccf_rank: d.ccfRank,
    })
    if (meta) {
      lines.push(`<div class="g6-tooltip-meta">${escapeHtml(meta)}</div>`)
    }
    if (d.innovationSummary) {
      lines.push(`<div class="g6-tooltip-innov">${escapeHtml(truncateText(d.innovationSummary, 160))}</div>`)
      if (nodeId) {
        lines.push(
          `<button type="button" class="g6-tooltip-hint g6-tooltip-open-paper" data-node-id="${escapeHtml(nodeId)}">点击查看完整创新点</button>`,
        )
      } else {
        lines.push('<div class="g6-tooltip-hint">点击节点查看完整创新点</div>')
      }
    }
  } else if (type === 'Venue') {
    const bits = []
    if (d.ccfRank && d.ccfRank !== 'None') bits.push(`等级：${d.ccfRank}`)
    if (d.venueType) bits.push(d.venueType)
    if (bits.length) {
      lines.push(`<div class="g6-tooltip-meta">${escapeHtml(bits.join(' · '))}</div>`)
    }
  } else if (!d.taskDomain) {
    lines.push('<div class="g6-tooltip-meta">暂无领域信息</div>')
  }

  if (!lines.length) {
    lines.push(`<div class="g6-tooltip-meta">${escapeHtml(d.label || '')}</div>`)
  }

  const title = d.label
    ? `<div class="g6-tooltip-title">${escapeHtml(d.label)}</div>`
    : ''
  return `${title}<div class="g6-tooltip-inner">${lines.join('')}</div>`
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function nodeMatchesHighlight(node, query) {
  const q = String(query || '').trim().toLowerCase()
  if (!q) return true
  const hay = [
    node?.name,
    node?.task_domain,
    node?.description,
    node?.innovation_summary,
    node?.venue,
    node?.type,
  ].filter(Boolean).join(' ').toLowerCase()
  return hay.includes(q)
}

export function filterGraphByDomain(graphData, domain) {
  const d = String(domain || '').trim()
  if (!d) return graphData

  const domainLower = d.toLowerCase()
  const matched = new Set()
  for (const n of graphData?.nodes || []) {
    if ((n.task_domain || '').toLowerCase().includes(domainLower)) {
      matched.add(n.id)
    }
  }
  for (const e of graphData?.edges || []) {
    if (matched.has(e.source_id)) matched.add(e.target_id)
    if (matched.has(e.target_id)) matched.add(e.source_id)
  }

  const nodes = (graphData?.nodes || []).filter((n) => matched.has(n.id))
  const nodeIds = new Set(nodes.map((n) => n.id))
  const edges = (graphData?.edges || []).filter(
    (e) => nodeIds.has(e.source_id) && nodeIds.has(e.target_id),
  )
  return { nodes, edges }
}

export const CITE_REL_TYPES = new Set(['CITE', '引用'])

/** 左下角 Toggle Switch：节点类型过滤项 */
export const GRAPH_NODE_TYPE_TOGGLES = [
  { key: 'Paper', label: '论文' },
  { key: 'Model', label: '模型' },
  { key: 'Dataset', label: '数据集' },
  { key: 'Metric', label: '评测指标' },
  { key: 'Venue', label: '会议期刊' },
]

/** 左下角 Toggle Switch：关系类型过滤项 */
export const GRAPH_REL_TYPE_TOGGLES = [
  { key: 'USE_DATASET', label: '使用数据集' },
  { key: 'DIFFERENT_WITH', label: '对比差异' },
  { key: 'EVALUATE_BY', label: '评测关系' },
  { key: 'IMPROVE_FROM', label: '改进自' },
  { key: 'EXTEND_FROM', label: '延伸自' },
  { key: 'PROPOSE', label: '提出' },
  { key: 'PUBLISH_AT', label: '发表于' },
]

const REL_LABEL_ZH_TO_KEY = {
  提出: 'PROPOSE',
  改进自: 'IMPROVE_FROM',
  对比差异: 'DIFFERENT_WITH',
  使用数据集: 'USE_DATASET',
  评测指标: 'EVALUATE_BY',
  评测关系: 'EVALUATE_BY',
  延伸自: 'EXTEND_FROM',
  发表于: 'PUBLISH_AT',
  引用: 'CITE',
  作者: 'WRITTEN_BY',
  关联: 'RELATION',
}

export function createDefaultNodeTypeFilters() {
  return Object.fromEntries(GRAPH_NODE_TYPE_TOGGLES.map(({ key }) => [key, true]))
}

export function createDefaultRelTypeFilters() {
  return Object.fromEntries(GRAPH_REL_TYPE_TOGGLES.map(({ key }) => [key, true]))
}

export function normalizeRelTypeKey(edge) {
  const raw = String(edge?.rel_type || '').trim()
  if (raw) return raw.toUpperCase()
  const label = String(edge?.type || '').trim()
  return REL_LABEL_ZH_TO_KEY[label] || label.toUpperCase()
}

export function findFocalNodeIds(graphData, query) {
  const q = String(query || '').trim().toLowerCase()
  if (!q) return new Set()
  const ids = new Set()
  for (const node of graphData?.nodes || []) {
    const hay = [
      node?.name,
      node?.id,
      node?.paper_id,
      node?.title,
    ].filter(Boolean).join(' ').toLowerCase()
    if (hay.includes(q)) ids.add(node.id)
  }
  return ids
}

export function isCiteEdge(edge) {
  const relKey = normalizeRelTypeKey(edge)
  if (relKey === 'CITE') return true
  return CITE_REL_TYPES.has(edge?.type)
}

export function filterGraphData(graphData, options = {}) {
  const { includeCite = false, relTypes = null } = options
  const nodes = graphData?.nodes || []
  const edges = (graphData?.edges || []).filter((edge) => {
    if (!includeCite && isCiteEdge(edge)) return false
    const rel = edge.rel_type || edge.type || ''
    if (relTypes?.length && !relTypes.includes(rel) && !relTypes.includes(edge.type)) return false
    return true
  })

  const nodeIds = new Set()
  for (const edge of edges) {
    nodeIds.add(edge.source_id)
    nodeIds.add(edge.target_id)
  }
  const filteredNodes = nodes.filter((node) => nodeIds.has(node.id))
  return { nodes: filteredNodes, edges }
}

export function filterGraphByRelTypes(graphData, relTypeFilters = {}, options = {}) {
  const { includeCite = false } = options
  const enabled = new Set(
    Object.entries(relTypeFilters)
      .filter(([, on]) => on)
      .map(([key]) => key.toUpperCase()),
  )

  const edges = (graphData?.edges || []).filter((edge) => {
    if (!includeCite && isCiteEdge(edge)) return false
    const relKey = normalizeRelTypeKey(edge)
    if (relKey === 'CITE') return includeCite
    return enabled.has(relKey)
  })

  return { nodes: graphData?.nodes || [], edges }
}

export function filterGraphByNodeTypes(graphData, nodeTypeFilters = {}, focalNodeIds = new Set()) {
  const focal = focalNodeIds instanceof Set ? focalNodeIds : new Set(focalNodeIds)
  const enabled = new Set()
  for (const [type, on] of Object.entries(nodeTypeFilters || {})) {
    if (on) enabled.add(type)
  }

  const nodes = (graphData?.nodes || []).filter(
    (node) => enabled.has(node.type) || focal.has(node.id),
  )
  const nodeIds = new Set(nodes.map((node) => node.id))
  const edges = (graphData?.edges || []).filter(
    (edge) => nodeIds.has(edge.source_id) && nodeIds.has(edge.target_id),
  )
  return { nodes, edges }
}

export function pruneDisconnectedNodes(graphData, protectedNodeIds = new Set()) {
  const protectedIds = protectedNodeIds instanceof Set
    ? protectedNodeIds
    : new Set(protectedNodeIds)
  const connected = new Set(protectedIds)
  for (const edge of graphData?.edges || []) {
    connected.add(edge.source_id)
    connected.add(edge.target_id)
  }
  const nodes = (graphData?.nodes || []).filter((node) => connected.has(node.id))
  const nodeIds = new Set(nodes.map((node) => node.id))
  const edges = (graphData?.edges || []).filter(
    (edge) => nodeIds.has(edge.source_id) && nodeIds.has(edge.target_id),
  )
  return { nodes, edges }
}

export function applyGraphViewFilters(graphData, options = {}) {
  const {
    includeCite = false,
    domain = '',
    highlightQuery = '',
    nodeTypeFilters = null,
    relTypeFilters = null,
    focalNodeIds = null,
  } = options

  const focal = focalNodeIds instanceof Set
    ? focalNodeIds
    : new Set(focalNodeIds || [])

  let data = graphData
  if (relTypeFilters) {
    data = filterGraphByRelTypes(data, relTypeFilters, { includeCite })
  } else {
    data = filterGraphData(data, { includeCite })
  }
  if (nodeTypeFilters) {
    data = filterGraphByNodeTypes(data, nodeTypeFilters, focal)
  }
  data = pruneDisconnectedNodes(data, focal)
  data = filterGraphByDomain(data, domain)

  const hasHighlight = Boolean(String(highlightQuery || '').trim())
  const nodes = data.nodes.map((node) => ({
    ...node,
    _highlighted: hasHighlight ? nodeMatchesHighlight(node, highlightQuery) : true,
  }))
  return { nodes, edges: data.edges }
}

export function formatGraphPayload(graphData, options = {}) {
  const {
    showEdgeLabels = false,
    maxLabelLen = 14,
    colorByDomain = false,
    highlightQuery = '',
    focalNodeIds = null,
  } = options
  const focal = focalNodeIds instanceof Set
    ? focalNodeIds
    : new Set(focalNodeIds || [])
  const nodes = graphData?.nodes || []
  const edges = graphData?.edges || []
  const hasHighlight = Boolean(String(highlightQuery || '').trim())

  return {
    nodes: nodes.map((node) => {
      const fullLabel = node.name || node.id || 'unknown'
      const subtitle = buildNodeSubtitle(node)
      const highlighted = node._highlighted !== false
      const dimmed = hasHighlight && !highlighted
      const taskDomain = node.task_domain || ''
      const fill = resolveNodeFill(node, { colorByDomain })
      const isFocal = focal.has(node.id)
      return {
        id: node.id,
        data: {
          label: fullLabel,
          shortLabel: truncateLabel(fullLabel, maxLabelLen),
          subtitle,
          nodeType: node.type || '',
          taskDomain,
          description: node.description || '',
          innovationSummary: node.innovation_summary || '',
          year: node.year,
          venue: node.venue || '',
          paperId: node.paper_id || '',
          ccfRank: node.ccf_rank || '',
          venueType: node.venue_type || '',
          dimmed,
          isFocal,
          rawNode: node,
        },
        style: {
          fill,
          fillOpacity: dimmed ? 0.18 : 1,
          strokeOpacity: dimmed ? 0.2 : 1,
          labelOpacity: dimmed ? 0.25 : 1,
          lineWidth: isFocal ? 3 : (highlighted && hasHighlight ? 3 : 1),
          stroke: isFocal ? '#fa8c16' : (highlighted && hasHighlight ? '#1677ff' : '#fff'),
        },
      }
    }),
    edges: edges.map((edge) => ({
      source: edge.source_id,
      target: edge.target_id,
      data: {
        label: edge.type || '',
        relType: edge.rel_type || edge.type || '',
        showLabel: showEdgeLabels,
      },
    })),
  }
}

export function createGraphOptions(container, options = {}) {
  const {
    showEdgeLabels = false,
    maxLabelLen = 14,
    colorByDomain = false,
    width = container?.offsetWidth || container?.clientWidth || 800,
    height = container?.offsetHeight || container?.clientHeight || 600,
  } = options

  return {
    container,
    width,
    height,
    autoFit: 'view',
    autoResize: true,
    padding: 24,
    animation: false,
    layout: {
      type: 'd3-force',
      preventOverlap: true,
      animated: false,
      link: {
        distance: (edge) => (isCiteEdge({ rel_type: edge?.data?.relType, type: edge?.data?.label }) ? 90 : 130),
      },
      manyBody: {
        strength: -280,
      },
      collide: {
        strength: 0.9,
        radius: 36,
      },
    },
    plugins: [
      {
        type: 'tooltip',
        trigger: 'hover',
        enterable: true,
        enable: (_event, items) => Boolean(items?.[0]?.data?.nodeType),
        getContent: (_event, items) => {
          const item = items?.[0]
          const data = item?.data
          if (!data?.nodeType) return ''
          return buildTooltipHtml(data, { nodeId: item?.id })
        },
        style: {
          '.tooltip': {
            background: '#fff',
            borderRadius: '8px',
            boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
            padding: '8px 10px',
            maxWidth: '280px',
          },
        },
      },
    ],
    node: {
      type: 'circle',
      style: {
        size: 32,
        labelText: (d) => {
          const main = d.data.shortLabel || truncateLabel(d.data.label, maxLabelLen)
          if (d.data.subtitle) return `${main}\n${d.data.subtitle}`
          return main
        },
        labelFontSize: (d) => (d.data.subtitle ? 10 : 11),
        labelFill: '#333',
        labelPlacement: 'bottom',
        labelOffsetY: 6,
        labelBackground: true,
        labelBackgroundFill: '#ffffff',
        labelBackgroundOpacity: 0.9,
        labelPadding: [2, 4, 2, 4],
        labelMaxWidth: 110,
        labelWordWrap: true,
        labelLineHeight: 14,
        opacity: 1,
      },
      state: {
        active: {
          size: 40,
          labelFontSize: 12,
          labelText: (d) => {
            const main = d.data.label || d.data.shortLabel
            if (d.data.subtitle) return `${main}\n${d.data.subtitle}`
            return main
          },
          lineWidth: 2,
          opacity: 1,
          fillOpacity: 1,
          labelOpacity: 1,
        },
        inactive: {
          fillOpacity: 0.2,
          strokeOpacity: 0.25,
          labelOpacity: 0.15,
          opacity: 1,
        },
      },
    },
    edge: {
      type: 'line',
      style: {
        labelText: (d) => (d.data.showLabel || showEdgeLabels ? d.data.label : ''),
        labelFontSize: 10,
        labelBackground: true,
        labelBackgroundFill: '#fff',
        labelBackgroundOpacity: 0.85,
        labelPadding: [1, 3],
        stroke: '#c8c8c8',
        lineWidth: 1,
        endArrow: true,
        opacity: 0.75,
      },
      state: {
        active: {
          stroke: '#1677ff',
          lineWidth: 2,
          labelText: (d) => d.data.label,
          opacity: 1,
        },
        inactive: {
          strokeOpacity: 0.12,
          labelOpacity: 0,
          opacity: 0.2,
        },
      },
    },
    behaviors: [
      {
        type: 'hover-activate',
        degree: 1,
        direction: 'both',
        state: 'active',
        inactiveState: 'inactive',
      },
      'drag-element',
      'zoom-canvas',
      'drag-canvas',
    ],
  }
}

export function bindPaperNodeClick(graph, onPaperClick, container = null) {
  if (!graph || typeof onPaperClick !== 'function') return () => {}

  const resolvePaperData = (nodeId) => {
    if (!nodeId) return null
    const nodeData = graph.getNodeData?.(nodeId)
    const data = nodeData?.data
    return data?.nodeType === 'Paper' ? data : null
  }

  const onNodeClick = (event) => {
    const nodeId = event?.target?.id
    const data = resolvePaperData(nodeId)
    if (data) onPaperClick(data)
  }

  const onHintClick = (event) => {
    const btn = event.target?.closest?.('.g6-tooltip-open-paper')
    if (!btn) return
    event.preventDefault()
    event.stopPropagation()
    const data = resolvePaperData(btn.dataset.nodeId)
    if (data) onPaperClick(data)
  }

  graph.on('node:click', onNodeClick)
  const root = container || document
  root.addEventListener('click', onHintClick)

  return () => {
    graph.off?.('node:click', onNodeClick)
    root.removeEventListener('click', onHintClick)
  }
}
