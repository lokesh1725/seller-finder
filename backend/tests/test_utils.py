from app import utils


def test_normalize_name_case_and_punctuation():
    assert utils.normalize_name(" Gulabo Jaipur ") == "gulabo jaipur"
    assert utils.normalize_name("A N Knitwear") == "a n knitwear"
    assert utils.normalize_name("Bunaai (now trading as Bunai)") == "bunaai now trading as bunai"


def test_normalize_name_ignores_company_suffixes():
    assert utils.normalize_name("Bummer Pvt Ltd") == utils.normalize_name("Bummer")


def test_slugify():
    assert utils.slugify("Gulabo Jaipur") == "gulabo-jaipur"
    assert utils.slugify("K.V. Knits") == "k-v-knits"
    assert utils.slugify("") == "business"


def test_extract_parenthetical_aliases():
    base, aliases = utils.extract_parenthetical_aliases("Bunaai (now trading as Bunai)")
    assert base == "Bunaai"
    assert aliases == ["Bunai"]


def test_extract_emails_multiple_and_dedup():
    emails = utils.extract_emails("hi@x.com; HI@x.com ; manan@x.com (press)")
    assert emails == ["hi@x.com", "manan@x.com"]


def test_extract_urls():
    urls = utils.extract_urls("Amazon: https://a.com/x ; Myntra: https://b.com/y")
    assert urls == ["https://a.com/x", "https://b.com/y"]


def test_extract_phones():
    phones = utils.extract_phones("+91 86901 67971 (business); +91 99285 94699")
    assert "+91 86901 67971" in phones
    assert "+91 99285 94699" in phones


def test_extract_pincode():
    assert utils.extract_pincode("388 Bhojpura, Jaipur 302015") == "302015"
    assert utils.extract_pincode("no pin here") is None


def test_is_missing_markers():
    for marker in ["Not found", "N/A", "", None, "  ", "-"]:
        assert utils.is_missing(marker)
    assert not utils.is_missing("Bummer")


def test_clean_url_and_domain():
    assert utils.clean_url("example.com") == "https://example.com"
    assert utils.clean_url("javascript:alert(1)") is None
    assert utils.domain_from_url("https://www.bummer.in/pages") == "bummer.in"


def test_ssrf_blocks_private_targets():
    assert not utils.is_safe_public_url("http://localhost:5000")
    assert not utils.is_safe_public_url("http://127.0.0.1")
    assert not utils.is_safe_public_url("http://169.254.169.254/latest/meta-data")
    assert not utils.is_safe_public_url("ftp://example.com")


def test_merge_non_empty_preserves_existing():
    merged, changed = utils.merge_non_empty(
        {"a": "keep", "b": None}, {"a": "new", "b": "fill", "c": ""}
    )
    assert merged["a"] == "keep"
    assert merged["b"] == "fill"
    assert "c" not in changed
