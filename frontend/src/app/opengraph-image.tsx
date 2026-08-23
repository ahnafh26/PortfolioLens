import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// data-URI img since Satori's flexbox renderer doesn't support raw svg JSX well
const logoSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="160" height="160" fill="none">
<circle cx="10" cy="10" r="6.25" stroke="#c79968" stroke-width="1.75"/>
<line x1="14.42" y1="14.42" x2="19.5" y2="19.5" stroke="#c79968" stroke-width="1.75" stroke-linecap="round"/>
<polyline points="4.5,13 11,11.5 16,4" stroke="#f4f1ec" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="16" cy="4" r="1.5" fill="#f4f1ec"/>
</svg>`;

const logoDataUri = `data:image/svg+xml;base64,${btoa(logoSvg)}`;

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#2c3e50",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- ImageResponse requires a plain <img>, not next/image */}
        <img src={logoDataUri} width={160} height={160} alt="" />
        <div style={{ display: "flex", marginTop: 32, fontSize: 72, fontWeight: 600, color: "#ecf0f1" }}>
          PortfolioLens
        </div>
        <div style={{ display: "flex", marginTop: 12, fontSize: 30, color: "#bdc3c7" }}>
          Portfolio risk &amp; optimization analyzer
        </div>
      </div>
    ),
    { ...size },
  );
}
