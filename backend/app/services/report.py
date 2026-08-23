"""CSV/PDF report generation. Formats an already-computed AnalyzeResponse, no re-fetching."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import AnalyzeResponse

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M UTC"

# ai_insights/tickers/labels ultimately trace back to client input (export requests
# aren't tied to a prior real /analyze call). Prefix formula-trigger characters so
# Excel/Sheets can't execute them as formulas when someone opens the export.
_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    return f"'{value}" if value.startswith(_CSV_FORMULA_TRIGGERS) else value


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime(_TIMESTAMP_FORMAT)


def generate_csv(analysis: AnalyzeResponse, ai_insights: list[str] | None = None) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["PortfolioLens Report", _timestamp()])
    writer.writerow([f"Lookback: {analysis.lookback_years} years"])
    writer.writerow([])

    writer.writerow(["Portfolio Summary"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Annual Return", f"{analysis.portfolio.annual_return:.4f}"])
    writer.writerow(["Annual Volatility", f"{analysis.portfolio.annual_volatility:.4f}"])
    writer.writerow(["Sharpe Ratio", f"{analysis.portfolio.sharpe_ratio:.4f}"])
    writer.writerow(["1yr 95% VaR", f"{analysis.portfolio.value_at_risk_95:.4f}"])
    writer.writerow([])

    writer.writerow(["Holdings"])
    writer.writerow(["Ticker", "Weight", "Annual Return", "Annual Volatility", "Sharpe Ratio"])
    for h in analysis.holdings:
        writer.writerow([_csv_safe(h.ticker), f"{h.weight:.4f}", f"{h.annual_return:.4f}", f"{h.annual_volatility:.4f}", f"{h.sharpe_ratio:.4f}"])
    writer.writerow([])

    writer.writerow(["Sector Breakdown"])
    writer.writerow(["Sector", "Weight"])
    for s in analysis.factor_breakdown.sector:
        writer.writerow([_csv_safe(s.label), f"{s.weight:.4f}"])
    writer.writerow([])

    writer.writerow(["Market Cap Breakdown"])
    writer.writerow(["Tier", "Weight"])
    for s in analysis.factor_breakdown.market_cap:
        writer.writerow([_csv_safe(s.label), f"{s.weight:.4f}"])

    if analysis.skipped_tickers:
        writer.writerow([])
        writer.writerow(["Skipped tickers (no usable price data)", _csv_safe(", ".join(analysis.skipped_tickers))])

    if ai_insights:
        writer.writerow([])
        writer.writerow(["AI Assistant Insights"])
        for line in ai_insights:
            writer.writerow([_csv_safe(line)])

    return buf.getvalue().encode("utf-8")


_ACCENT = colors.HexColor("#059669")  # frontend's accent green
_MUTED = colors.HexColor("#6b7280")
_BORDER = colors.HexColor("#e5e7eb")


def _stat_table(analysis: AnalyzeResponse) -> Table:
    rows = [
        ["Annual Return", f"{analysis.portfolio.annual_return:.1%}"],
        ["Annual Volatility", f"{analysis.portfolio.annual_volatility:.1%}"],
        ["Sharpe Ratio", f"{analysis.portfolio.sharpe_ratio:.2f}"],
        ["1yr 95% VaR", f"-{analysis.portfolio.value_at_risk_95:.1%}"],
    ]
    table = Table(rows, colWidths=[2.2 * inch, 2.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, _BORDER),
            ]
        )
    )
    return table


def _holdings_table(analysis: AnalyzeResponse) -> Table:
    header = ["Ticker", "Weight", "Return", "Volatility", "Sharpe"]
    rows = [header] + [
        [h.ticker, f"{h.weight:.0%}", f"{h.annual_return:.1%}", f"{h.annual_volatility:.1%}", f"{h.sharpe_ratio:.2f}"]
        for h in sorted(analysis.holdings, key=lambda h: -h.weight)
    ]
    table = Table(rows, colWidths=[1.1 * inch, 0.9 * inch, 0.9 * inch, 1.0 * inch, 0.9 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ]
        )
    )
    return table


def _breakdown_table(rows_data: list[tuple[str, float]], header_label: str) -> Table:
    rows = [[header_label, "Weight"]] + [[label, f"{weight:.0%}"] for label, weight in rows_data]
    table = Table(rows, colWidths=[2.6 * inch, 1.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
            ]
        )
    )
    return table


def generate_pdf(analysis: AnalyzeResponse, ai_insights: list[str] | None = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch, leftMargin=0.75 * inch, rightMargin=0.75 * inch
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PLTitle", parent=styles["Title"], textColor=colors.HexColor("#111827"))
    heading_style = ParagraphStyle("PLHeading", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8)
    muted_style = ParagraphStyle("PLMuted", parent=styles["Normal"], textColor=_MUTED, fontSize=9)
    body_style = ParagraphStyle("PLBody", parent=styles["Normal"], fontSize=10, spaceAfter=4)

    story = [
        Paragraph("PortfolioLens", title_style),
        Paragraph(f"Generated {_timestamp()} &middot; {analysis.lookback_years}-year lookback", muted_style),
        Spacer(1, 0.25 * inch),
        Paragraph("Portfolio Summary", heading_style),
        _stat_table(analysis),
        Paragraph("Holdings", heading_style),
        _holdings_table(analysis),
    ]

    if analysis.factor_breakdown.sector:
        story.append(Paragraph("Sector Breakdown", heading_style))
        story.append(_breakdown_table([(s.label, s.weight) for s in analysis.factor_breakdown.sector], "Sector"))

    if analysis.factor_breakdown.market_cap:
        story.append(Paragraph("Market Cap Breakdown", heading_style))
        story.append(_breakdown_table([(s.label, s.weight) for s in analysis.factor_breakdown.market_cap], "Tier"))

    if analysis.skipped_tickers:
        story.append(Paragraph("Notes", heading_style))
        skipped = xml_escape(", ".join(analysis.skipped_tickers))
        story.append(Paragraph(f"Skipped (no usable price data): {skipped}", body_style))

    if ai_insights:
        story.append(Paragraph("AI Assistant Insights", heading_style))
        for line in ai_insights:
            story.append(Paragraph(f"&bull; {xml_escape(line)}", body_style))

    doc.build(story)
    return buf.getvalue()
