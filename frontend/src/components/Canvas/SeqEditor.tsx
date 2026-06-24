/**
 * Sequence Diagram Editor — lifelines + messages powered by AntV X6.
 * Reuses the same X6 patterns as UMLEditor (isInternalUpdate, sync effect, etc.)
 */

import React, { useRef, useEffect, useCallback } from 'react';
import { Graph, Node, Edge } from '@antv/x6';
import { History } from '@antv/x6-plugin-history';
import { Transform } from '@antv/x6-plugin-transform';
import { Selection } from '@antv/x6-plugin-selection';
import { Snapline } from '@antv/x6-plugin-snapline';
import { useDiagramStore } from '../../stores/diagramStore';
import { useUiStore } from '../../stores/uiStore';
import type { SeqLifeline, SeqMessage, MessageType } from '../../types/sequence';
import { MESSAGE_TYPE_LABELS } from '../../types/sequence';
import './SeqEditor.css';

// ── Register X6 shapes (once) ────────────────────────

let shapesRegistered = false;
function ensureShapesRegistered() {
  if (shapesRegistered) return;
  shapesRegistered = true;

  // Lifeline: header rect + dashed body line
  Graph.registerNode('seq-lifeline', {
    inherit: 'rect',
    markup: [
      { tagName: 'rect', selector: 'body' },
      {
        tagName: 'foreignObject',
        selector: 'fo',
        children: [
          {
            tagName: 'div',
            ns: 'http://www.w3.org/1999/xhtml',
            selector: 'content',
            style: {
              width: '100%', height: '100%',
              fontFamily: 'Consolas, Monaco, monospace',
              fontSize: '12px', lineHeight: '1.5',
              overflow: 'hidden',
            },
          },
        ],
      },
    ],
    attrs: {
      body: {
        stroke: '#333', strokeWidth: 2, fill: '#ffe6cc',
        rx: 4, ry: 4,
      },
      fo: { refWidth: '100%', refHeight: '100%' },
      content: { html: '' },
    },
    ports: {},
  });

  console.debug('[SeqEditor] X6 sequence shapes registered');
}

// ── HTML builders ────────────────────────────────────

function buildLifelineHTML(lifeline: SeqLifeline, selected: boolean): string {
  const selClass = selected ? 'selected' : '';
  const bars = (lifeline.activations || []).map((y, i) =>
    `<div class="seq-activation" style="top:${y - 6}px" title="激活条 #${i + 1}"></div>`
  ).join('');
  const hint = selected
    ? '<div class="seq-click-hint">▼ 已选中，点击另一生命线创建消息 ▼</div>'
    : '';
  return `<div class="seq-lifeline-node ${selClass}">
    <div class="seq-lifeline-name">${lifeline.name}</div>
    <div class="seq-lifeline-body">
      <div class="seq-lifeline-dash"></div>
      ${bars}
      ${hint}
    </div>
  </div>`;
}

// ── Component ────────────────────────────────────────

const LIFELINE_WIDTH = 140;
const LIFELINE_HEIGHT = 400;
const LIFELINE_Y = 120;  // give top padding so lifelines aren't cut off

const SeqEditor: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const isInternalUpdate = useRef(false);
  const clipboard = useRef<any>(null);

  const {
    diagram, project, selectedLifelineId, selectedMessageId,
    addLifeline, removeLifeline, moveLifeline,
    selectLifeline, selectMessage,
    undo, redo,
  } = useDiagramStore();

  const { setRightPanelTab } = useUiStore();

  // ── Init graph ──────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || graphRef.current) return;
    ensureShapesRegistered();

    const d = useDiagramStore.getState().diagram;
    const graph = new Graph({
      container: containerRef.current,
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      background: { color: '#fafafa' },
      grid: {
        size: d.grid_size || 20, visible: d.grid_visible !== false,
        args: { color: d.grid_color || '#e0e0e0', thickness: d.grid_thickness || 1 },
      },
      mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'], minScale: 0.1, maxScale: 5 },
      panning: { enabled: true },
    });

    graph.use(new History({ enabled: true }));
    graph.use(new Transform({ resizing: false, rotating: false }));
    graph.use(new Selection({ enabled: true, rubberband: true, showNodeSelectionBox: true }));
    graph.use(new Snapline({ enabled: true, sharp: true }));

    // Click-to-click message creation
    graph.on('node:click', ({ node }) => {
      const store = useDiagramStore.getState();
      if (store.selectedLifelineId === node.id) {
        // Same lifeline clicked again → self-message
        store.addMessage(node.id, node.id);
        return;
      }
      if (store.selectedLifelineId) {
        // Second lifeline clicked → create message
        store.addMessage(store.selectedLifelineId, node.id);
        return;
      }
      // First click: select lifeline
      selectLifeline(node.id);
      setRightPanelTab('properties');
    });

    graph.on('blank:click', () => {
      selectLifeline(null);
      selectMessage(null);
    });

    graph.on('node:moved', ({ node }) => {
      moveLifeline(node.id, node.position().x);
    });

    graph.on('edge:click', ({ edge }) => {
      selectMessage(edge.id);
      setRightPanelTab('properties');
    });

    // Save edge Y position when dragged
    graph.on('edge:change:source', ({ edge, current }) => {
      if (typeof (current as any)?.y === 'number') {
        const store = useDiagramStore.getState();
        store.updateMessage(edge.id, { y: (current as any).y } as any);
      }
    });
    graph.on('edge:change:target', ({ edge, current }) => {
      if (typeof (current as any)?.y === 'number') {
        const store = useDiagramStore.getState();
        store.updateMessage(edge.id, { y: (current as any).y } as any);
      }
    });
    // Also capture vertex moves for self-messages
    graph.on('edge:change:vertices', ({ edge, current }) => {
      const store = useDiagramStore.getState();
      const src = edge.getSource();
      const srcY = typeof (src as any)?.y === 'number' ? (src as any).y : edge.getSourcePoint()?.y;
      if (typeof srcY === 'number') {
        store.updateMessage(edge.id, { y: srcY } as any);
      }
    });

    // Keyboard
    const handleKeyDown = (e: KeyboardEvent) => {
      const store = useDiagramStore.getState();
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if (e.ctrlKey && e.key === 'c') {
        if (store.selectedLifelineId) {
          const ll = (store.diagram.lifelines || []).find((l) => l.id === store.selectedLifelineId);
          if (ll) clipboard.current = JSON.parse(JSON.stringify(ll));
        }
      } else if (e.ctrlKey && e.key === 'v') {
        if (clipboard.current) {
          const c = clipboard.current;
          store.addLifeline(c.x + 30);
          // Apply copied name
          const store2 = useDiagramStore.getState();
          const lls = store2.diagram.lifelines || [];
          const pasted = lls[lls.length - 1];
          if (pasted) {
            store2.updateLifeline(pasted.id, {
              name: c.name, class_ref: c.class_ref,
              activations: [...(c.activations || [])],
            });
          }
        }
      } else if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
        e.preventDefault(); store.undo();
      } else if (e.ctrlKey && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault(); store.redo();
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        // Delete selected lifeline or message via store
        if (store.selectedMessageId) {
          e.preventDefault();
          store.removeMessage(store.selectedMessageId);
        } else if (store.selectedLifelineId) {
          e.preventDefault();
          store.removeLifeline(store.selectedLifelineId);
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);

    graphRef.current = graph;
    console.log('[SeqEditor] Graph initialized');
    console.log('[SeqEditor] Graph initialized');

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      try { graph.dispose(); } catch { /* ignore */ }
      graphRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Sync diagram → graph ───────────────────────────
  const prevLifelineIds = useRef<Set<string>>(new Set());
  const htmlCache = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    try {
      isInternalUpdate.current = true;
      const lifelines = diagram.lifelines || [];
      const messages = diagram.messages || [];
      const currentLIds = new Set(lifelines.map((l) => l.id));

      // Remove deleted lifelines
      prevLifelineIds.current.forEach((id) => {
        if (!currentLIds.has(id)) {
          try { graph.removeCell(id); } catch { /* ignore */ }
          htmlCache.current.delete(id);
        }
      });

      // Calculate needed height from message count
      const neededHeight = Math.max(LIFELINE_HEIGHT, 120 + messages.length * 40);

      // Add/update lifelines — auto-fix negative x (corrupted by clientToLocal)
      lifelines.forEach((ll) => {
        if (ll.x < 50) {
          const fixedX = 150 + Math.random() * 300;
          console.log('[SeqEditor] Fixing lifeline x:', ll.name, ll.x, '→', fixedX);
          useDiagramStore.getState().updateLifeline(ll.id, { x: fixedX });
          ll = { ...ll, x: fixedX };
        }
        const htmlContent = buildLifelineHTML(ll, ll.id === selectedLifelineId);
        const cached = htmlCache.current.get(ll.id);
        try {
          const existing = graph.getCellById(ll.id);
          if (existing && existing.isNode()) {
            const node = existing as Node;
            node.setPosition(ll.x, LIFELINE_Y);
            node.setSize({ width: LIFELINE_WIDTH, height: neededHeight });
            if (cached !== htmlContent) {
              node.setAttrByPath('content/html', htmlContent);
              htmlCache.current.set(ll.id, htmlContent);
            }
          } else {
            graph.addNode({
              id: ll.id,
              shape: 'seq-lifeline',
              x: ll.x, y: LIFELINE_Y,
              width: LIFELINE_WIDTH, height: neededHeight,
              attrs: { content: { html: htmlContent } },
            });
            htmlCache.current.set(ll.id, htmlContent);
          }
        } catch (e) {
          console.warn('[SeqEditor] Sync lifeline error:', ll.name, e);
        }
      });

      // Remove deleted messages (those in graph but not in data)
      const graphEdgeIds = new Set(graph.getEdges().map((e) => e.id));
      const dataMsgIds = new Set(messages.map((m) => m.id));
      graphEdgeIds.forEach((id) => {
        if (!dataMsgIds.has(id)) {
          try { graph.removeCell(id); } catch { /* ignore */ }
        }
      });

      // Add/update messages — use persisted msg.y, fall back to order-based calculation
      const lifelineMap = new Map(lifelines.map((l) => [l.id, l]));
      const MSG_Y_BASE = LIFELINE_Y + 30;
      messages.forEach((msg) => {
        const srcLL = lifelineMap.get(msg.from_lifeline);
        const tgtLL = lifelineMap.get(msg.to_lifeline);
        if (!srcLL || !tgtLL) return;

        const isSelf = msg.from_lifeline === msg.to_lifeline;
        const msgY = msg.y || MSG_Y_BASE + msg.order * 40;  // persisted Y takes priority

        // Connect from source lifeline edge → target lifeline edge
        // If source is left of target: source right edge → target left edge  (arrow →)
        // If source is right of target: source left edge → target right edge (arrow ←)
        const srcIsLeft = srcLL.x <= tgtLL.x;
        const fromX = srcIsLeft ? srcLL.x + LIFELINE_WIDTH : srcLL.x;
        const toX   = srcIsLeft ? tgtLL.x : tgtLL.x + LIFELINE_WIDTH;

        let strokeColor = '#1890ff';
        let strokeDash = '';
        if (msg.type === 'return') { strokeColor = '#888'; strokeDash = '6,3'; }
        else if (msg.type === 'simple') { strokeColor = '#333'; }
        else if (msg.type === 'async') { strokeColor = '#52c41a'; }

        const lineAttrs: Record<string, unknown> = {
          stroke: strokeColor,
          strokeWidth: 2,
          strokeDasharray: strokeDash,
          targetMarker: { name: 'block', width: 10, height: 6 },
        };

        try {
          const existing = graph.getCellById(msg.id);
          if (existing && existing.isEdge()) {
            // Update existing edge when type/label changes in property panel
            const edge = existing as Edge;
            edge.setLabels(msg.label ? [{
              attrs: {
                text: { text: msg.label, fontSize: 10, fill: strokeColor },
                rect: { fill: '#fff', stroke: 'none', rx: 2 },
              },
              position: { distance: 0.5, offset: -12 },
            }] : []);
            edge.setAttrByPath('line/stroke', strokeColor);
            edge.setAttrByPath('line/strokeDasharray', strokeDash);
            return;
          }

          // New edge
          const edgeLabel = msg.label
            ? [{
                attrs: {
                  text: { text: msg.label, fontSize: 10, fill: strokeColor },
                  rect: { fill: '#fff', stroke: 'none', rx: 2 },
                },
                position: { distance: 0.5, offset: -12 },
              }]
            : undefined;

          if (isSelf) {
            graph.addEdge({
              id: msg.id,
              source: { x: srcLL.x + LIFELINE_WIDTH, y: msgY },
              target: { x: srcLL.x + LIFELINE_WIDTH, y: msgY + 24 },
              vertices: [
                { x: srcLL.x + LIFELINE_WIDTH + 40, y: msgY },
                { x: srcLL.x + LIFELINE_WIDTH + 40, y: msgY + 24 },
              ],
              labels: edgeLabel,
              connector: { name: 'rounded' },
              attrs: { line: lineAttrs },
            });
          } else {
            graph.addEdge({
              id: msg.id,
              source: { x: fromX, y: msgY },
              target: { x: toX, y: msgY },
              labels: edgeLabel,
              attrs: { line: lineAttrs },
            });
          }
        } catch (e) {
          console.warn('[SeqEditor] Sync message error:', msg.id, e);
        }
      });

      prevLifelineIds.current = currentLIds;
      isInternalUpdate.current = false;

    } catch (err) {
      console.error('[SeqEditor] Sync error:', err);
      isInternalUpdate.current = false;
    }
  }, [diagram, selectedLifelineId]);

  // ── Sync grid settings ─────────────────────────────
  useEffect(() => {
    const graph = graphRef.current as any;
    if (!graph) return;
    try {
      if (diagram.grid_visible !== false) {
        graph.showGrid();
        graph.setGridSize(diagram.grid_size || 20);
        graph.drawGrid({ size: diagram.grid_size || 20,
          args: { color: diagram.grid_color || '#e0e0e0', thickness: diagram.grid_thickness || 1 } });
      } else {
        graph.hideGrid();
      }
    } catch (e) { /* ignore */ }
  }, [diagram.grid_visible, diagram.grid_size, diagram.grid_color, diagram.grid_thickness]);

  // ── Double-click: add lifeline ─────────────────────
  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    const graph = graphRef.current;
    if (!graph) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    try {
      const x = e.clientX - rect.left;
      // Use raw screen x for new lifeline — clientToLocal can give odd values
      addLifeline(Math.max(50, x - 70));
    } catch (err) {
      console.warn('[SeqEditor] DblClick error:', err);
    }
  }, [addLifeline]);

  return (
    <div
      ref={containerRef}
      className="seq-canvas-container"
      onDoubleClick={handleDoubleClick}
    />
  );
};

export default SeqEditor;
