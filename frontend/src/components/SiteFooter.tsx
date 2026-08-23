import { IconGithub, IconLinkedin } from "@/components/icons";

export function SiteFooter() {
  return (
    <footer className="border-t border-border py-4">
      <p className="mx-auto max-w-6xl px-4 pb-2 text-center text-[11px] text-muted-foreground/80 sm:px-6">
        Portfolio data is processed for analysis and isn&apos;t saved by PortfolioLens. If you
        request AI insights or research, your holdings and computed stats are sent to the
        configured LLM provider to generate that response.
      </p>
      <div className="mx-auto flex max-w-6xl items-center justify-center gap-3 px-4 text-xs text-muted-foreground sm:px-6">
        <span>Built by Ahnaf Hanif</span>
        <div className="flex items-center gap-2.5">
          <a
            href="https://github.com/ahnafh26"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub"
            className="hover:text-foreground"
          >
            <IconGithub className="size-3.5" />
          </a>
          <a
            href="https://www.linkedin.com/in/ahnafhanif1/"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="LinkedIn"
            className="hover:text-foreground"
          >
            <IconLinkedin className="size-3.5" />
          </a>
        </div>
      </div>
    </footer>
  );
}
