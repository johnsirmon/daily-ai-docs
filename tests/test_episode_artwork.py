"""Optional RSS art is public display metadata, never immutable audio provenance."""

import io
import sys
import xml.etree.ElementTree as ET

import pytest
from PIL import Image, PngImagePlugin

from pipeline.podcast import load_episodes, render_feed, validate_episode_image_url, write_feed
from pipeline.publish import PublicationError, validate_episode_artwork, validate_feed_file
from scripts.generate_artwork import create_episode_artwork, export_episode_artwork, main

IMAGE = "https://johnsirmon.github.io/daily-ai-docs/assets/episodes/parallel-agents-v1.jpg"
ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def _episode():
    return {
        "guid": "legacy-guid", "title": "Topic", "description": "Reviewed notes.",
        "mp3_url": "https://example.com/immutable.mp3", "file_size_bytes": 12345,
        "pub_date": "2026-09-20", "duration_secs": 60,
    }


@pytest.mark.parametrize("url", [
    "", None, 123, False, IMAGE + "?key=secret", IMAGE + "#fragment",
    IMAGE.replace("https://", "http://"), IMAGE.replace("github.io", "github.io.evil.test"),
    IMAGE.replace("johnsirmon.github.io", "name:secret@johnsirmon.github.io"),
    IMAGE.replace("johnsirmon.github.io", "localhost"),
    IMAGE.replace("johnsirmon.github.io", "johnsirmon.github.io:443"),
    IMAGE.replace("parallel-agents-v1.jpg", "../outside.jpg"),
    IMAGE.replace("parallel-agents-v1.jpg", "%2e%2e%2foutside.jpg"),
    IMAGE.replace("parallel-agents-v1.jpg", "folder/image.jpg"),
    IMAGE.replace("parallel-agents-v1.jpg", "Image.JPG"),
    IMAGE.replace(".jpg", ".png"), IMAGE.replace(".jpg", ".jpg.exe"),
    IMAGE.replace("parallel-agents", "parallel.agents"),
    IMAGE.replace("parallel-agents", r"parallel\agents"),
    "data:image/jpeg;base64,aW1hZ2U=", r"C:\private\image.jpg", IMAGE + "\n",
])
def test_unsafe_image_urls_fail_explicitly(url):
    with pytest.raises(ValueError, match="image_url"):
        validate_episode_image_url(url)
    with pytest.raises(ValueError, match="image_url"):
        render_feed([{**_episode(), "image_url": url}])


@pytest.mark.parametrize("images", [
    [{"href": "https://example.com/private.jpg"}], [{}], [{"href": ""}],
    [{"href": IMAGE}, {"href": IMAGE}], [{"href": IMAGE, "secret": "no"}],
])
def test_invalid_rss_image_is_not_silently_dropped(tmp_path, images):
    root = ET.fromstring(render_feed([_episode()]))
    item = root.find("channel/item")
    for attributes in images:
        ET.SubElement(item, ITUNES + "image", attributes)
    path = tmp_path / "podcast.xml"
    path.write_bytes(ET.tostring(root))
    with pytest.raises(ValueError):
        load_episodes(str(path))
    with pytest.raises(PublicationError):
        validate_feed_file(path)


def test_old_feed_without_item_art_keeps_show_fallback(tmp_path):
    path = tmp_path / "podcast.xml"
    write_feed([_episode()], str(path))
    assert "image_url" not in load_episodes(str(path))[0]
    assert ET.parse(path).find("channel/item/" + ITUNES + "image") is None
    assert ET.parse(path).find("channel/" + ITUNES + "image") is not None
    assert validate_feed_file(path, artwork_root=tmp_path)["episodes"] == 1


@pytest.mark.parametrize("size,mode,format", [
    ((1400, 1401), "RGB", "JPEG"), ((1399, 1399), "RGB", "JPEG"),
    ((3001, 3001), "RGB", "JPEG"), ((1400, 1400), "L", "JPEG"),
    ((1400, 1400), "CMYK", "JPEG"), ((1400, 1400), "RGBA", "PNG"),
    ((1400, 1400), "RGB", "PNG"),
])
def test_unsupported_asset_bytes_fail(size, mode, format):
    data = io.BytesIO()
    Image.new(mode, size).save(data, format=format)
    with pytest.raises(PublicationError, match="RGB JPEG"):
        validate_episode_artwork(data.getvalue())


def test_export_is_image_only_square_rgb_jpeg_without_source_metadata(tmp_path, monkeypatch):
    source = tmp_path / "browser-export.png"
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("prompt", "private browser generation details")
    Image.new("RGB", (1254, 1254), (12, 45, 80)).save(source, pnginfo=metadata)
    image = create_episode_artwork(source)
    assert image.size == (3000, 3000) and image.mode == "RGB"
    assert image.getpixel((1500, 1500)) == (12, 45, 80)
    assert not image.info
    output = tmp_path / "public" / "topic-v1.jpg"
    monkeypatch.setattr(sys, "argv", ["generate_artwork.py", "--episode-source", str(source), "--output", str(output)])
    main()
    content = output.read_bytes()
    assert validate_episode_artwork(content) == "3000x3000 RGB JPEG"
    assert b"private browser" not in content
    with Image.open(output) as saved:
        assert not saved.getexif()
    with pytest.raises(FileExistsError):
        export_episode_artwork(source, output)
    assert output.read_bytes() == content


@pytest.mark.parametrize("fault", ["nonsquare", "transparent", "not-image", "wrong-extension"])
def test_export_rejects_invalid_source_or_destination_without_writing(tmp_path, fault):
    source = tmp_path / "source.png"
    output = tmp_path / ("final.png" if fault == "wrong-extension" else "final.jpg")
    if fault == "not-image":
        source.write_bytes(b"<html>Sign in</html>")
    else:
        image = Image.new("RGBA" if fault == "transparent" else "RGB",
                          (100, 120) if fault == "nonsquare" else (100, 100))
        image.save(source)
    with pytest.raises((ValueError, OSError)):
        export_episode_artwork(source, output)
    assert not output.exists()


def test_export_requires_episode_destination(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["generate_artwork.py", "--episode-source", "unused.png"])
    with pytest.raises(SystemExit, match="2"):
        main()


def test_export_accepts_opaque_alpha_source(tmp_path):
    source = tmp_path / "opaque.png"
    Image.new("RGBA", (100, 100), (10, 20, 30, 255)).save(source)
    assert create_episode_artwork(source).mode == "RGB"


def test_export_fails_size_budget_without_writing(tmp_path, monkeypatch):
    from scripts import generate_artwork

    source = tmp_path / "source.png"
    Image.new("RGB", (100, 100)).save(source)
    output = tmp_path / "topic-v1.jpg"

    def oversized_save(self, stream, **kwargs):
        assert kwargs == {"format": "JPEG", "quality": 85, "optimize": True, "subsampling": 2}
        stream.write(b"x" * 1_000_000)

    monkeypatch.setattr(generate_artwork.Image.Image, "save", oversized_save)
    with pytest.raises(ValueError, match="exceeds 1 MB"):
        export_episode_artwork(source, output)
    assert not output.exists()
