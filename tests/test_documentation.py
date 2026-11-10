from html.parser import HTMLParser

from observatory.build import build
from observatory.documentation import generate

from conftest import seed


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []
        self.ids = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag in ("script", "img", "link", "iframe"):
            self.assets.append((tag, values))
        if tag == "a" and values.get("href", "").startswith("#"):
            self.links.append(values["href"][1:])


def test_manual_is_standalone_consistent_and_has_working_anchors(lake, legacy_source, tmp_path):
    seed(lake, legacy_source, [{"name": "Teste"}])
    result = build(lake, output=tmp_path / "dist")
    path = generate(lake.root / "gold" / result["build_id"], tmp_path / "manual.html")
    text = path.read_text(encoding="utf-8")
    inventory = Inventory()
    inventory.feed(text)
    assert "@@" not in text
    assert len(inventory.ids) == len(set(inventory.ids))
    assert set(inventory.links).issubset(set(inventory.ids))
    assert not any("src" in attrs or (tag == "link" and "href" in attrs) for tag, attrs in inventory.assets)
    assert all(key in inventory.ids for key in ("solution-svg", "flow-svg", "er-svg", "search"))
    assert result["build_id"] in text
    assert "effective_minimum" in text
    assert (tmp_path / "dist" / "manual.html").exists()


def test_dashboard_links_to_stable_documentation(lake, legacy_source, tmp_path):
    from urllib.parse import urljoin
    seed(lake, legacy_source, [{"name": "Teste"}])
    output = tmp_path / "site"
    build(lake, output=output)
    release = next((output / "releases").iterdir())
    text = (release / "index.html").read_text(encoding="utf-8")
    assert 'href="../../documentacao.html"' in text
    assert (release / "../../documentacao.html").resolve().read_bytes() == (release / "manual.html").read_bytes()
    assert urljoin('https://example.github.io/project/releases/old/index.html', '../../documentacao.html') == 'https://example.github.io/project/documentacao.html'
    recovery = (output / "404.html").read_text(encoding="utf-8")
    assert 'location.replace' in recovery
    assert 'documentacao.html' in recovery
