import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function SearchBar({
  initialValue = "",
  autoFocus = false,
  onSubmit,
  size = "large",
}) {
  const [value, setValue] = useState(initialValue);
  const navigate = useNavigate();

  function handleSubmit(event) {
    event.preventDefault();
    const query = value.trim();
    if (!query) return;
    if (onSubmit) {
      onSubmit(query);
    } else {
      navigate(`/results?q=${encodeURIComponent(query)}`);
    }
  }

  return (
    <form className={`search-bar search-bar-${size}`} onSubmit={handleSubmit} role="search">
      <label htmlFor="seller-search" className="visually-hidden">
        Search for a seller, brand, company or manufacturer
      </label>
      <input
        id="seller-search"
        type="search"
        name="q"
        value={value}
        autoFocus={autoFocus}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Enter seller, brand, company or manufacturer name..."
        autoComplete="off"
        aria-label="Search seller, brand, company or manufacturer"
      />
      <button type="submit" className="btn btn-primary">
        Search
      </button>
    </form>
  );
}
