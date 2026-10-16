import { SITE_NAME } from "../constants.js";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <p>
          {SITE_NAME} aggregates publicly available business information. Contact
          details are shown with their sources and verification status. Nothing is
          guessed or fabricated.
        </p>
        <p className="footer-meta">
          Always respect website terms, API limits and applicable privacy laws when
          reaching out.
        </p>
      </div>
    </footer>
  );
}
