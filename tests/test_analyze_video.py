"""Phase B7 — analyze_video.py unit tests."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest


def test_extract_features_shape():
    from analyze_video import extract_features, N_FEATURES
    frame = np.random.RandomState(0).randint(0, 256, (180, 320, 3), dtype=np.uint8)
    feat = extract_features(frame)
    assert feat.shape == (N_FEATURES,), f"Expected {N_FEATURES}-dim feature, got {feat.shape}"
    assert feat.dtype.kind == "f"
    assert not np.isnan(feat).any()


def test_extract_features_in_range():
    """All features should be normalized to [0, 1]."""
    from analyze_video import extract_features
    frame = np.random.RandomState(1).randint(0, 256, (180, 320, 3), dtype=np.uint8)
    feat = extract_features(frame)
    # Allow small overshoot from float ops
    assert (feat >= -0.01).all() and (feat <= 1.01).all(), \
        f"Features out of range: min={feat.min()}, max={feat.max()}"


def test_extract_features_distinguishes_styles():
    """Two visually different frames should produce different feature vectors
    on average. (Internal KMeans on dominant colors is non-deterministic so
    we average over multiple runs.)"""
    from analyze_video import extract_features

    a = np.zeros((180, 320, 3), dtype=np.uint8)
    a[:, :, 1] = 255
    cv2.rectangle(a, (50, 50), (150, 150), (255, 0, 255), -1)

    b = np.full((180, 320, 3), 30, dtype=np.uint8)

    diffs = []
    for _ in range(5):
        fa = extract_features(a)
        fb = extract_features(b)
        diffs.append(float(np.linalg.norm(fa - fb)))
    avg_diff = sum(diffs) / len(diffs)
    assert avg_diff > 0.5, f"Features too similar (avg diff {avg_diff:.3f})"


def test_infer_category_returns_tuple():
    """infer_category expects a dict with _raw suffixed keys + dominant_colors."""
    from analyze_video import infer_category
    sig = {
        "edge_density_raw":   0.4,
        "brightness_raw":     0.8,
        "saturation_raw":     0.7,
        "color_variance_raw": 0.6,
        "dominant_colors":    [(255, 0, 255), (0, 255, 255), (255, 255, 0)],
    }
    cat, mapping = infer_category(sig)
    assert isinstance(cat, str) and isinstance(mapping, str)
    assert len(cat) > 0
    assert "→" in mapping or "->" in mapping


def test_infer_category_branches_smoke():
    """Cover several heuristic branches to confirm none crash."""
    from analyze_video import infer_category
    test_sigs = [
        # neon edge
        {"edge_density_raw": 0.3, "brightness_raw": 0.2, "saturation_raw": 0.5, "color_variance_raw": 0.2, "dominant_colors": []},
        # monochrome contour
        {"edge_density_raw": 0.3, "brightness_raw": 0.2, "saturation_raw": 0.05, "color_variance_raw": 0.1, "dominant_colors": []},
        # film grain
        {"edge_density_raw": 0.05, "brightness_raw": 0.2, "saturation_raw": 0.05, "color_variance_raw": 0.1, "dominant_colors": []},
        # high energy burst
        {"edge_density_raw": 0.05, "brightness_raw": 0.8, "saturation_raw": 0.7, "color_variance_raw": 0.5, "dominant_colors": []},
        # fallback
        {"edge_density_raw": 0.1, "brightness_raw": 0.5, "saturation_raw": 0.2, "color_variance_raw": 0.2, "dominant_colors": []},
    ]
    for sig in test_sigs:
        cat, mapping = infer_category(sig)
        assert cat and mapping


@pytest.mark.integration
def test_preflight_check_missing_video(tmp_path):
    from analyze_video import preflight_check
    bogus = tmp_path / "nope.mp4"
    res = preflight_check(bogus, clusters=20)
    assert res["ok"] is False
    assert any("not found" in e.lower() for e in res["errors"])


@pytest.mark.integration
def test_preflight_check_synthetic_video(tmp_path):
    """Build a tiny synthetic video and verify preflight returns a structured result."""
    from analyze_video import preflight_check
    vid_path = tmp_path / "synth.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(vid_path), fourcc, 30.0, (320, 180))
    for i in range(90):
        f = np.full((180, 320, 3), i % 255, dtype=np.uint8)
        writer.write(f)
    writer.release()
    assert vid_path.exists() and vid_path.stat().st_size > 0

    res = preflight_check(vid_path, clusters=3)
    assert "ok" in res
    assert "errors" in res
    assert "estimates" in res
