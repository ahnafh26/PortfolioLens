"use client";

// Shock diffusion canvas. Nodes laid out in rings by BFS hop-distance from
// the origin, edges are React Flow "floating" edges since nodes aren't in
// a tree.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  BaseEdge,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  getBezierPath,
  useEdgesState,
  useInternalNode,
  useNodesState,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type InternalNode,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AlertTriangle, Info, Loader2, Radio, TrendingDown, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/InfoTooltip";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ErrorState } from "@/components/ErrorState";
import { useChartTheme } from "@/hooks/use-chart-theme";
import { correlationColor, status as statusPalette } from "@/lib/chart-colors";
import { formatPercent, formatSignedPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  ApiError,
  simulateShock,
  type ContagionStatus,
  type GraphNode as ContagionGraphNode,
  type ShockSimulationResponse,
} from "@/lib/api";

const RING_SPACING = 165;
const DEFAULT_NODE_SIZE = 64;

function nodeDiameter(weight: number): number {
  return Math.round(Math.min(48 + weight * 220, 132));
}

function computeRadialLayout(nodes: ContagionGraphNode[]): Record<string, { x: number; y: number }> {
  const byRing = new Map<number, ContagionGraphNode[]>();
  let maxHop = 0;
  for (const n of nodes) {
    if (n.hop_distance !== null) maxHop = Math.max(maxHop, n.hop_distance);
  }
  const unreachedRing = maxHop + 1;

  for (const n of nodes) {
    const ring = n.hop_distance ?? unreachedRing;
    const bucket = byRing.get(ring);
    if (bucket) bucket.push(n);
    else byRing.set(ring, [n]);
  }

  const positions: Record<string, { x: number; y: number }> = {};
  for (const [ring, ringNodes] of byRing) {
    if (ring === 0) {
      positions[ringNodes[0].ticker] = { x: 0, y: 0 };
      continue;
    }
    const radius = ring * RING_SPACING;
    ringNodes.forEach((n, i) => {
      const angle = (i / ringNodes.length) * Math.PI * 2 - Math.PI / 2;
      positions[n.ticker] = { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
    });
  }
  return positions;
}

// connection point = intersection of the line between two node centers
// with each node's bounding box, recomputed from live positions every render
function getNodeIntersection(intersectionNode: InternalNode<Node>, targetNode: InternalNode<Node>) {
  const w = (intersectionNode.measured.width ?? DEFAULT_NODE_SIZE) / 2;
  const h = (intersectionNode.measured.height ?? DEFAULT_NODE_SIZE) / 2;
  const intersectionPos = intersectionNode.internals.positionAbsolute;
  const targetPos = targetNode.internals.positionAbsolute;

  const x2 = intersectionPos.x + w;
  const y2 = intersectionPos.y + h;
  const x1 = targetPos.x + (targetNode.measured.width ?? DEFAULT_NODE_SIZE) / 2;
  const y1 = targetPos.y + (targetNode.measured.height ?? DEFAULT_NODE_SIZE) / 2;

  const xx1 = (x1 - x2) / (2 * w) - (y1 - y2) / (2 * h);
  const yy1 = (x1 - x2) / (2 * w) + (y1 - y2) / (2 * h);
  const a = 1 / (Math.abs(xx1) + Math.abs(yy1) || 1);

  return { x: w * (a * xx1 + a * yy1) + x2, y: h * (-a * xx1 + a * yy1) + y2 };
}

function getEdgePosition(node: InternalNode<Node>, intersection: { x: number; y: number }): Position {
  const nx = Math.round(node.internals.positionAbsolute.x);
  const ny = Math.round(node.internals.positionAbsolute.y);
  const nw = node.measured.width ?? DEFAULT_NODE_SIZE;
  const nh = node.measured.height ?? DEFAULT_NODE_SIZE;
  const px = Math.round(intersection.x);
  const py = Math.round(intersection.y);

  if (px <= nx + 1) return Position.Left;
  if (px >= nx + nw - 1) return Position.Right;
  if (py <= ny + 1) return Position.Top;
  if (py >= ny + nh - 1) return Position.Bottom;
  return Position.Top;
}

interface ContagionEdgeData extends Record<string, unknown> {
  correlation: number;
  revealed: boolean;
}
type ContagionRFEdge = Edge<ContagionEdgeData, "floating">;

function FloatingEdge({ id, source, target, data, animated }: EdgeProps<ContagionRFEdge>) {
  const mode = useChartTheme();
  const sourceNode = useInternalNode(source);
  const targetNode = useInternalNode(target);
  if (!sourceNode || !targetNode || !data) return null;

  const sourceIntersection = getNodeIntersection(sourceNode, targetNode);
  const targetIntersection = getNodeIntersection(targetNode, sourceNode);
  const [path] = getBezierPath({
    sourceX: sourceIntersection.x,
    sourceY: sourceIntersection.y,
    sourcePosition: getEdgePosition(sourceNode, sourceIntersection),
    targetX: targetIntersection.x,
    targetY: targetIntersection.y,
    targetPosition: getEdgePosition(targetNode, targetIntersection),
  });

  return (
    <BaseEdge
      id={id}
      path={path}
      className={cn(animated && "animated")}
      style={{
        stroke: correlationColor(data.correlation, mode),
        strokeWidth: 1.5 + Math.abs(data.correlation) * 4.5,
        opacity: data.revealed ? 0.85 : 0,
        transition: "opacity 0.35s ease-out",
      }}
    />
  );
}

const edgeTypes = { floating: FloatingEdge };

const HANDLE_STYLE: React.CSSProperties = { opacity: 0, width: 1, height: 1, minWidth: 0, minHeight: 0, border: "none" };

const AT_RISK_HEX = statusPalette.warning.light;

function statusStyle(status: ContagionStatus): React.CSSProperties {
  if (status === "at_risk") {
    return { borderColor: AT_RISK_HEX, backgroundColor: `${AT_RISK_HEX}26`, color: AT_RISK_HEX };
  }
  return {};
}

function statusClassName(status: ContagionStatus): string {
  switch (status) {
    case "critical":
      return "border-negative bg-negative/15 text-negative";
    case "at_risk":
      return "";
    default:
      return "border-positive/50 bg-positive/10 text-positive";
  }
}

interface ContagionNodeData extends Record<string, unknown> {
  graphNode: ContagionGraphNode;
  isOrigin: boolean;
  revealed: boolean;
}
type ContagionRFNode = Node<ContagionNodeData, "contagion">;

function ContagionNode({ data }: NodeProps<ContagionRFNode>) {
  const { graphNode, isOrigin, revealed } = data;
  const size = nodeDiameter(graphNode.weight);

  return (
    <>
      <Handle type="target" id="target" position={Position.Top} style={HANDLE_STYLE} isConnectable={false} />
      <Handle type="source" id="source" position={Position.Top} style={HANDLE_STYLE} isConnectable={false} />
      <div
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-full border-2 text-center transition-[opacity,transform] duration-[350ms] ease-out",
          revealed ? "scale-100 opacity-100" : "scale-[0.6] opacity-20",
          statusClassName(graphNode.status),
          isOrigin && "ring-[3px] ring-accent ring-offset-2 ring-offset-background",
        )}
        style={{ width: size, height: size, ...statusStyle(graphNode.status) }}
        title={`${graphNode.ticker}, ${graphNode.sector}`}
      >
        <span className="font-mono text-xs font-semibold leading-none">{graphNode.ticker}</span>
        <span className="mt-1 font-mono text-[10px] leading-none opacity-80">{formatPercent(graphNode.weight, 0)}</span>
        {graphNode.price_drawdown !== 0 && (
          <span className="mt-1 font-mono text-[10px] font-medium leading-none tabular-nums">
            {formatSignedPercent(graphNode.price_drawdown)}
          </span>
        )}
      </div>
    </>
  );
}

const nodeTypes = { contagion: ContagionNode };

function SourceBadge({ source }: { source: "llm" | "rule_based" }) {
  return (
    <Badge variant={source === "llm" ? "accent" : "outline"} className="text-[10px]">
      {source === "llm" ? "AI-generated" : "Rule-based"}
    </Badge>
  );
}

function statusBadgeVariant(status: ContagionStatus): "negative" | "outline" | "positive" {
  if (status === "critical") return "negative";
  if (status === "at_risk") return "outline";
  return "positive";
}

function ContagionSummaryPanel({ result }: { result: ShockSimulationResponse }) {
  const { summary } = result;
  return (
    <div className="flex h-full flex-col gap-4 rounded border border-border p-4">
      <div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <TrendingDown className="size-4" />
          Total portfolio impact
        </div>
        <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-negative">
          {formatSignedPercent(summary.total_portfolio_drawdown)}
        </p>
      </div>

      <div>
        <p className="text-xs font-medium text-muted-foreground">Top vulnerable holdings</p>
        <ul className="mt-2 space-y-2">
          {summary.highest_risk_secondary.length === 0 && (
            <li className="text-xs text-muted-foreground">No other holdings were meaningfully affected.</li>
          )}
          {summary.highest_risk_secondary.map((n) => (
            <li key={n.ticker} className="flex items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-medium">{n.ticker}</span>
                <Badge variant={statusBadgeVariant(n.status)} className="text-[10px]">
                  {n.hop_distance} hop{n.hop_distance === 1 ? "" : "s"}
                </Badge>
              </span>
              <span className="font-mono tabular-nums text-negative">{formatSignedPercent(n.price_drawdown)}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto space-y-2 border-t border-border pt-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground">Why it propagated</p>
          <SourceBadge source={summary.narrative_source} />
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">{summary.risk_narrative}</p>
      </div>
    </div>
  );
}

export interface ContagionGraphHolding {
  ticker: string;
  weight: number;
}

export interface ContagionGraphProps {
  holdings: ContagionGraphHolding[];
  lookbackYears?: number;
}

function ContagionGraphInner({ holdings, lookbackYears = 3 }: ContagionGraphProps) {
  const tickerKey = useMemo(() => holdings.map((h) => h.ticker).sort().join(","), [holdings]);
  const defaultOrigin = useMemo(
    () => holdings.reduce((max, h) => (h.weight > max.weight ? h : max), holdings[0])?.ticker ?? "",
    [holdings],
  );

  const [originTicker, setOriginTicker] = useState(defaultOrigin);
  const [shockMagnitudePct, setShockMagnitudePct] = useState(15);
  const [decayFactor, setDecayFactor] = useState(0.65);
  const [result, setResult] = useState<ShockSimulationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revealedHop, setRevealedHop] = useState(0);

  const { fitView } = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState<ContagionRFNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<ContagionRFEdge>([]);

  // re-pick origin if it dropped out of the portfolio
  const [prevTickerKey, setPrevTickerKey] = useState(tickerKey);
  if (tickerKey !== prevTickerKey) {
    setPrevTickerKey(tickerKey);
    setOriginTicker((prev) => (holdings.some((h) => h.ticker === prev) ? prev : defaultOrigin));
  }

  const runSimulation = useCallback(async () => {
    if (!originTicker || holdings.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const res = await simulateShock({
        holdings: holdings.map((h) => ({ ticker: h.ticker, weight: h.weight })),
        origin_ticker: originTicker,
        shock_magnitude: -shockMagnitudePct / 100,
        decay_factor: decayFactor,
        lookback_years: lookbackYears,
      });
      setResult(res);
      setRevealedHop(0);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong running the simulation.");
    } finally {
      setLoading(false);
    }
  }, [holdings, originTicker, shockMagnitudePct, decayFactor, lookbackYears]);

  // initial run when tickers change; slider tweaks wait for the Run button
  useEffect(() => {
    if (holdings.length < 2 || !originTicker) return;
    const controller = new AbortController();
    simulateShock(
      {
        holdings: holdings.map((h) => ({ ticker: h.ticker, weight: h.weight })),
        origin_ticker: originTicker,
        shock_magnitude: -shockMagnitudePct / 100,
        decay_factor: decayFactor,
        lookback_years: lookbackYears,
      },
      { signal: controller.signal },
    )
      .then((res) => {
        setResult(res);
        setRevealedHop(0);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Something went wrong running the simulation.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickerKey]);

  // reveal one hop at a time so it reads as a ripple
  useEffect(() => {
    if (!result) return;
    const maxHop = Math.max(0, ...result.nodes.map((n) => n.hop_distance ?? 0));
    if (maxHop === 0) return;
    let hop = 0;
    const id = setInterval(() => {
      hop += 1;
      setRevealedHop(hop);
      if (hop >= maxHop) clearInterval(id);
    }, 320);
    return () => clearInterval(id);
  }, [result]);

  useEffect(() => {
    if (!result) return;
    const t = setTimeout(() => fitView({ duration: 500, padding: 0.3 }), 60);
    return () => clearTimeout(t);
  }, [result, fitView]);

  useEffect(() => {
    if (!result) {
      setNodes([]);
      setEdges([]);
      return;
    }
    const positions = computeRadialLayout(result.nodes);
    const hopByTicker = new Map(result.nodes.map((n) => [n.ticker, n.hop_distance]));

    setNodes(
      result.nodes.map((n) => {
        const size = nodeDiameter(n.weight);
        return {
          id: n.ticker,
          type: "contagion",
          position: positions[n.ticker] ?? { x: 0, y: 0 },
          width: size,
          height: size,
          data: {
            graphNode: n,
            isOrigin: n.ticker === result.summary.origin_ticker,
            revealed: n.hop_distance === null || n.hop_distance <= revealedHop,
          },
        } satisfies ContagionRFNode;
      }),
    );

    const seenPairs = new Set<string>();
    const dedupedEdges: ContagionRFEdge[] = [];
    for (const e of result.edges) {
      const key = [e.source, e.target].sort().join("|");
      if (seenPairs.has(key)) continue;
      seenPairs.add(key);
      const hopS = hopByTicker.get(e.source) ?? Infinity;
      const hopT = hopByTicker.get(e.target) ?? Infinity;
      const farHop = Math.max(hopS, hopT);
      dedupedEdges.push({
        id: key,
        source: e.source,
        target: e.target,
        sourceHandle: "source",
        targetHandle: "target",
        type: "floating",
        animated: farHop === revealedHop && hopS !== hopT,
        data: { correlation: e.correlation, revealed: farHop <= revealedHop },
      });
    }
    setEdges(dedupedEdges);
  }, [result, revealedHop, setNodes, setEdges]);

  if (holdings.length < 2) {
    return (
      <div className="flex flex-col items-center gap-2 rounded border border-border bg-muted px-6 py-12 text-center text-sm text-muted-foreground">
        <Radio className="size-6" />
        Add at least 2 holdings to explore contagion pathways between them.
      </div>
    );
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Radio className="size-4 text-accent" />
          Contagion &amp; shock simulator
        </CardTitle>
        <CardDescription>
          Shock one holding and watch how the drop ripples across correlated positions.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-4 rounded border border-border bg-muted/40 p-4">
          <div className="min-w-40">
            <Label htmlFor="contagion-origin">Shock origin</Label>
            <Select value={originTicker} onValueChange={setOriginTicker}>
              <SelectTrigger id="contagion-origin" className="mt-1.5">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {holdings.map((h) => (
                  <SelectItem key={h.ticker} value={h.ticker}>
                    {h.ticker}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="min-w-48 flex-1">
            <Label htmlFor="contagion-magnitude">Shock magnitude: -{shockMagnitudePct}%</Label>
            <input
              id="contagion-magnitude"
              type="range"
              min={1}
              max={90}
              value={shockMagnitudePct}
              onChange={(e) => setShockMagnitudePct(Number(e.target.value))}
              className="mt-3 w-full accent-accent"
            />
          </div>

          <div className="min-w-40">
            <Label htmlFor="contagion-decay" className="flex items-center gap-1">
              Decay factor: {decayFactor.toFixed(2)}
              <InfoTooltip text="How much a shock's impact shrinks at each hop across correlated holdings. Closer to 1 means the ripple travels further before fading out.">
                <Info className="size-3.5" />
              </InfoTooltip>
            </Label>
            <input
              id="contagion-decay"
              type="range"
              min={10}
              max={95}
              value={Math.round(decayFactor * 100)}
              onChange={(e) => setDecayFactor(Number(e.target.value) / 100)}
              className="mt-3 w-full accent-accent"
            />
          </div>

          <Button onClick={() => runSimulation()} disabled={loading}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />}
            Run shock simulation
          </Button>
        </div>

        {error && <ErrorState message={error} onRetry={() => runSimulation()} />}

        {!error && result?.skipped_tickers && result.skipped_tickers.length > 0 && (
          <div className="flex items-center gap-2 rounded border border-border bg-muted px-4 py-3 text-xs text-muted-foreground">
            <AlertTriangle className="size-4 shrink-0" />
            Couldn&apos;t resolve {result.skipped_tickers.join(", ")}, excluded from the graph.
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <div className="h-[480px] overflow-hidden rounded border border-border bg-background">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={(_, node) => setOriginTicker(node.id)}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView
              minZoom={0.3}
              maxZoom={1.5}
              // xyflow gates hideAttribution behind a Pro subscription we don't have
              proOptions={{ hideAttribution: false }}
            >
              <Background variant={BackgroundVariant.Dots} gap={18} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>

          {result ? (
            <ContagionSummaryPanel result={result} />
          ) : (
            <div className="flex h-full items-center justify-center rounded border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
              Run a simulation to see the impact summary.
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full border-2 border-positive/50 bg-positive/10" /> Healthy
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full border-2" style={{ borderColor: AT_RISK_HEX, backgroundColor: `${AT_RISK_HEX}26` }} /> At risk
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full border-2 border-negative bg-negative/15" /> Primary shock / heavily impacted
          </span>
          <span>Node size = portfolio weight &middot; Edge thickness = correlation strength</span>
        </div>
      </CardContent>
    </Card>
  );
}

export function ContagionGraph(props: ContagionGraphProps) {
  return (
    <ReactFlowProvider>
      <ContagionGraphInner {...props} />
    </ReactFlowProvider>
  );
}
