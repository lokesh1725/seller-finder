import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import {
  buildWebsiteMessage,
  copyText,
  nativeShare,
  websiteUrl,
  whatsappShareUrl,
} from "../utils/share.js";
import { SITE_NAME } from "../constants.js";

export default function Header() {
  const [toast, setToast] = useState("");

  function flash(message) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2500);
  }

  async function handleShare() {
    const message = buildWebsiteMessage();
    const shared = await nativeShare({
      title: SITE_NAME,
      text: message,
      url: websiteUrl(),
    });
    if (!shared) {
      window.open(whatsappShareUrl(message), "_blank", "noopener");
    }
  }

  async function handleCopy() {
    await copyText(websiteUrl());
    flash("Website link copied");
  }

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link to="/" className="brand" aria-label={`${SITE_NAME} home`}>
          <span className="brand-mark">SF</span>
          <span className="brand-text">
            <strong>Seller Finder</strong>
            <small>India business intelligence</small>
          </span>
        </Link>

        <nav className="main-nav" aria-label="Main">
          <NavLink to="/" end>
            Search
          </NavLink>
          <NavLink to="/saved">Saved Leads</NavLink>
        </nav>

        <div className="header-actions">
          <button type="button" className="btn btn-ghost" onClick={handleCopy}>
            Copy Link
          </button>
          <button type="button" className="btn btn-primary" onClick={handleShare}>
            Share Website
          </button>
        </div>
      </div>
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </header>
  );
}
