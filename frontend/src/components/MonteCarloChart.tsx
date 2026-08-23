"use client";

import { useEffect, useRef } from "react";
import {
  AreaSeries,
  LineSeries,
  PriceScaleMode,
  createChart,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";

import { sequentialBlue, status, chartInk } from "@/lib/chart-colors";
import { useChartTheme } from "@/hooks/use-chart-theme";
import type { MonteCarloResult } from "@/lib/api";
import { TRADING_DAYS_PER_YEAR, formatGrowthMultiple } from "@/lib/format";

// canvas needs a literal color, not a CSS var - matches the --card token
const CHART_SURFACE = { light: "#ffffff", dark: "#232329" };

// fake epoch so the time scale has real timestamps to work with; we
// relabel ticks as "Yr N" below instead of showing calendar dates
const AXIS_EPOCH = Math.floor(Date.now() / 1000);
const SECONDS_PER_DAY = 86_400;

function dayToTime(day: number): UTCTimestamp {
  return (AXIS_EPOCH + day * SECONDS_PER_DAY) as UTCTimestamp;
}

function timeToYears(time: UTCTimestamp): number {
  return (Number(time) - AXIS_EPOCH) / SECONDS_PER_DAY / TRADING_DAYS_PER_YEAR;
}

export function MonteCarloChart({ result }: { result: MonteCarloResult }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const mode = useChartTheme();

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const ramp = sequentialBlue[mode];
    const outerBand = ramp[0];
    const innerBand = ramp[2];
    const medianColor = ramp[4];
    const surface = CHART_SURFACE[mode];
    const ink = chartInk.secondary[mode];
    const grid = chartInk.gridline[mode];

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 320,
      layout: {
        background: { color: surface },
        textColor: ink,
        fontFamily: "var(--font-inter), system-ui, sans-serif",
        // was colliding with the VaR price-line label
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: grid },
      },
      rightPriceScale: {
        borderVisible: false,
        ticksVisible: false,
        // linear scale flattens the lower bands into a sliver over long horizons
        mode: PriceScaleMode.Logarithmic,
      },
      timeScale: {
        borderVisible: false,
        tickMarkFormatter: (time: UTCTimestamp) => `Yr ${timeToYears(time).toFixed(0)}`,
      },
      localization: {
        priceFormatter: formatGrowthMultiple,
      },
      crosshair: { horzLine: { labelBackgroundColor: medianColor }, vertLine: { labelBackgroundColor: ink } },
    });
    chartRef.current = chart;

    // draw p5-p95 fill, then mask everything below p5 with a surface-colored
    // area on top - leaves just the band colored. same trick for p25-p75.
    const p95Series = chart.addSeries(AreaSeries, {
      topColor: outerBand,
      bottomColor: outerBand,
      lineVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const p5MaskSeries = chart.addSeries(AreaSeries, {
      topColor: surface,
      bottomColor: surface,
      lineVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const p75Series = chart.addSeries(AreaSeries, {
      topColor: innerBand,
      bottomColor: innerBand,
      lineVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const p25MaskSeries = chart.addSeries(AreaSeries, {
      topColor: surface,
      bottomColor: surface,
      lineVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const medianSeries = chart.addSeries(LineSeries, {
      color: medianColor,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const p95Data = result.bands.map((b) => ({ time: dayToTime(b.day), value: b.p95 }));
    const p5Data = result.bands.map((b) => ({ time: dayToTime(b.day), value: b.p5 }));
    const p75Data = result.bands.map((b) => ({ time: dayToTime(b.day), value: b.p75 }));
    const p25Data = result.bands.map((b) => ({ time: dayToTime(b.day), value: b.p25 }));
    const p50Data = result.bands.map((b) => ({ time: dayToTime(b.day), value: b.p50 }));

    p95Series.setData(p95Data);
    p5MaskSeries.setData(p5Data);
    p75Series.setData(p75Data);
    p25MaskSeries.setData(p25Data);
    medianSeries.setData(p50Data);

    medianSeries.createPriceLine({
      price: 1 - result.value_at_risk_95,
      color: status.critical[mode],
      lineWidth: 2,
      lineStyle: 2, // dashed
      axisLabelVisible: true,
      title: `1yr 95% VaR: -${(result.value_at_risk_95 * 100).toFixed(1)}%`,
    });

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (container.clientWidth > 0) chart.applyOptions({ width: container.clientWidth });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [result, mode]);

  return <div ref={containerRef} className="h-80 w-full overflow-hidden rounded-lg" />;
}
