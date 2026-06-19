/** G6 知识图谱可视化共享配置 */

export const DEFAULT_SAMPLE_COUNT = 30

export function truncateLabel(text, maxLen = 14) {
  const s = String(text || '').trim()
  if (!s) return 'unknown'
  if (s.length <= maxLen) return s
  return `${s.slice(0, maxLen)}…`
}

export function formatGraphPayload(graphData, options = {}) {
  const { showEdgeLabels = false, maxLabelLen = 14 } = options
  const nodes = graphData?.nodes || []
  const edges = graphData?.edges || []

  return {
    nodes: nodes.map((node) => {
      const fullLabel = node.name || node.id || 'unknown'
      return {
        id: node.id,
        data: {
          label: fullLabel,
          shortLabel: truncateLabel(fullLabel, maxLabelLen),
          nodeType: node.type || '',
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

export const CITE_REL_TYPES = new Set(['CITE', '引用'])

export function isCiteEdge(edge) {
  const raw = String(edge?.rel_type || '').toUpperCase()
  if (raw === 'CITE') return true
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

export function createGraphOptions(container, options = {}) {
  const {
    showEdgeLabels = false,
    maxLabelLen = 14,
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
    node: {
      type: 'circle',
      style: {
        size: 32,
        labelText: (d) => d.data.shortLabel || truncateLabel(d.data.label, maxLabelLen),
        labelFontSize: 11,
        labelPlacement: 'bottom',
        labelOffsetY: 6,
        labelBackground: true,
        labelBackgroundFill: '#ffffff',
        labelBackgroundOpacity: 0.9,
        labelPadding: [2, 4, 2, 4],
        labelMaxWidth: 96,
        labelWordWrap: true,
        labelLineHeight: 14,
        opacity: 1,
      },
      state: {
        active: {
          size: 40,
          labelFontSize: 12,
          labelText: (d) => d.data.label || d.data.shortLabel,
          lineWidth: 2,
          opacity: 1,
        },
        inactive: {
          fillOpacity: 0.2,
          strokeOpacity: 0.25,
          labelOpacity: 0.15,
          opacity: 1,
        },
      },
      palette: {
        field: (d) => d.data.nodeType || d.data.shortLabel,
        color: 'tableau',
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
