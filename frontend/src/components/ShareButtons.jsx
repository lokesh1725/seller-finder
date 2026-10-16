import { useState } from "react";
import {
  buildBusinessMessage,
  copyText,
  nativeShare,
  businessUrl,
  whatsappShareUrl,
} from "../utils/share.js";

export default function ShareButtons({ business }) {
  const [toast, setToast] = useState("");

  function flash(message) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2500);
  }

  async function handleShare() {
    const message = buildBusinessMessage(business);
    const shared = await nativeShare({
      title: business?.company_name || "Business profile",
      text: message,
      url: businessUrl(business?.slug),
    });
    if (!shared) {
      window.open(whatsappShareUrl(message), "_blank", "noopener");
    }
  }

  async function handleCopy() {
    await copyText(businessUrl(business?.slug));
    flash("Profile link copied");
  }

  return (
    <div className="share-buttons">
      <button type="button" className="btn btn-primary" onClick={handleShare}>
        Share Business
      </button>
      <button type="button" className="btn btn-ghost" onClick={handleCopy}>
        Copy Link
      </button>
      {toast && (
        <span className="inline-toast" role="status">
          {toast}
        </span>
      )}
    </div>
  );
}
