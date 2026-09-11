import cv2
import numpy as np

from app.models.segmentation import OpenCVIrisSegmenter


def test_degrain_reduces_noise_without_losing_primary_edge() -> None:
    rng = np.random.default_rng(42)
    image = np.full((120, 120, 3), 75, dtype=np.int16)
    image[:, 60:] = 135
    noise = rng.normal(0, 8, image.shape)
    noisy = np.uint8(np.clip(image + noise, 0, 255))

    degrained = OpenCVIrisSegmenter._degrain(noisy)
    noisy_gray = cv2.cvtColor(noisy, cv2.COLOR_BGR2GRAY)
    degrained_gray = cv2.cvtColor(degrained, cv2.COLOR_BGR2GRAY)

    assert np.std(degrained_gray[:, :50]) < np.std(noisy_gray[:, :50])
    assert np.mean(degrained_gray[:, 70:]) - np.mean(degrained_gray[:, :50]) > 50


def test_iris_enhancement_boosts_light_contrast_and_detail() -> None:
    gradient = np.tile(np.arange(55, 115, dtype=np.uint8), (120, 2))
    image = cv2.merge((gradient, gradient, gradient))

    enhanced = OpenCVIrisSegmenter._enhance_iris(image)
    original_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    enhanced_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)

    assert np.mean(enhanced_gray) > np.mean(original_gray)
    assert np.std(enhanced_gray) > np.std(original_gray)
    assert cv2.Laplacian(enhanced_gray, cv2.CV_64F).var() > 0


def test_iris_enhancement_preserves_strong_color() -> None:
    image = np.full((80, 80, 3), (65, 95, 135), dtype=np.uint8)

    enhanced = OpenCVIrisSegmenter._enhance_iris(image)
    original_saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    enhanced_saturation = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)[:, :, 1]

    assert np.mean(enhanced_saturation) > np.mean(original_saturation) * 1.1


def test_iris_enhancement_restores_muted_color() -> None:
    image = np.full((80, 80, 3), (75, 82, 90), dtype=np.uint8)

    enhanced = OpenCVIrisSegmenter._enhance_iris(image)
    original_saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    enhanced_saturation = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)[:, :, 1]

    assert np.mean(enhanced_saturation) > np.mean(original_saturation) * 1.25


def test_limbus_enhancement_sharpens_and_saturates_only_outer_iris() -> None:
    size = 180
    center = size // 2
    yy, xx = np.ogrid[:size, :size]
    distance = np.sqrt((xx - center) ** 2 + (yy - center) ** 2)
    image = np.full((size, size, 3), (70, 95, 125), dtype=np.uint8)
    texture = np.uint8(12 * (1 + np.sin(np.arctan2(yy - center, xx - center) * 24)))
    image = np.uint8(np.clip(image.astype(np.int16) + texture[:, :, np.newaxis], 0, 255))

    enhanced = OpenCVIrisSegmenter._enhance_limbus(image, center, center, 80)
    ring = (distance >= 62) & (distance <= 76)
    inner = distance <= 48
    original_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    enhanced_hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
    original_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    enhanced_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)

    assert np.mean(enhanced_hsv[:, :, 1][ring]) > (
        np.mean(original_hsv[:, :, 1][ring]) * 1.1
    )
    enhanced_detail = cv2.Laplacian(enhanced_gray, cv2.CV_64F)[ring].var()
    original_detail = cv2.Laplacian(original_gray, cv2.CV_64F)[ring].var()

    assert enhanced_detail > original_detail
    assert np.mean(np.abs(enhanced.astype(int) - image.astype(int))[inner]) < 1


def test_limbus_refinement_excludes_desaturated_outer_halo() -> None:
    image = np.full((320, 320, 3), (190, 195, 200), dtype=np.uint8)
    cv2.circle(image, (160, 160), 112, (55, 95, 145), thickness=-1)
    cv2.circle(image, (160, 160), 35, (8, 8, 8), thickness=-1)

    refined = OpenCVIrisSegmenter._refine_limbus_radius(
        image,
        center_x=160,
        center_y=160,
        pupil_radius=35,
        detected_radius=135,
    )

    assert 112 <= refined <= 120


def test_limbus_refinement_uses_luminance_for_gray_iris() -> None:
    image = np.full((320, 320, 3), (195, 198, 200), dtype=np.uint8)
    cv2.circle(image, (160, 160), 112, (62, 66, 70), thickness=-1)
    cv2.circle(image, (160, 160), 35, (8, 8, 8), thickness=-1)

    refined = OpenCVIrisSegmenter._refine_limbus_radius(
        image,
        center_x=160,
        center_y=160,
        pupil_radius=35,
        detected_radius=135,
    )

    assert 108 <= refined <= 120


def test_pupil_refinement_uses_dark_core_edge() -> None:
    gray = np.full((220, 220), 70, dtype=np.uint8)
    cv2.circle(gray, (110, 110), 38, 24, thickness=-1)

    refined = OpenCVIrisSegmenter._refine_pupil_radius(
        gray,
        center_x=110,
        center_y=110,
        detected_radius=68,
    )

    assert 36 <= refined <= 42


def test_iris_mask_fits_elliptical_boundary() -> None:
    image = np.full((280, 320, 3), (205, 208, 210), dtype=np.uint8)
    cv2.ellipse(image, (160, 140), (110, 88), 0, 0, 360, (55, 70, 82), thickness=-1)
    cv2.circle(image, (160, 140), 32, (8, 8, 8), thickness=-1)

    mask = OpenCVIrisSegmenter._build_iris_mask(
        image,
        center_x=160,
        center_y=140,
        radius=112,
    )

    assert mask[140, 160] == 255
    assert mask[140, 265] == 255
    assert mask[20, 160] == 0
    points = cv2.findNonZero(np.uint8(mask > 127))
    assert points is not None
    _, _, mask_width, mask_height = cv2.boundingRect(points)
    assert max(mask_width, mask_height) / min(mask_width, mask_height) <= 1.04


def test_opencv_segmenter_returns_transparent_png() -> None:
    image = np.full((480, 640, 3), 220, dtype=np.uint8)
    cv2.circle(image, (320, 240), 110, (95, 125, 135), thickness=-1)
    cv2.circle(image, (320, 240), 42, (8, 8, 8), thickness=-1)
    cv2.circle(image, (295, 210), 10, (245, 245, 245), thickness=-1)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok

    result = OpenCVIrisSegmenter().segment(encoded.tobytes())
    decoded = cv2.imdecode(np.frombuffer(result.png, np.uint8), cv2.IMREAD_UNCHANGED)

    assert decoded is not None
    assert decoded.shape[2] == 4
    assert decoded[:, :, 3].min() < 255
    assert decoded[:, :, 3].max() == 255
    assert not np.any(decoded[0, :, 3])
    assert not np.any(decoded[-1, :, 3])
    assert not np.any(decoded[:, 0, 3])
    assert not np.any(decoded[:, -1, 3])
    center = decoded[decoded.shape[0] // 2, decoded.shape[1] // 2]
    assert center[3] == 255
    assert np.max(center[:3]) < 20
    assert 0.0 <= result.confidence <= 1.0


def test_opencv_segmenter_finds_an_off_center_iris() -> None:
    image = np.full((600, 900, 3), 220, dtype=np.uint8)
    cv2.circle(image, (285, 320), 125, (90, 115, 125), thickness=-1)
    cv2.circle(image, (285, 320), 46, (12, 12, 12), thickness=-1)
    cv2.circle(image, (470, 300), 65, (100, 100, 100), thickness=5)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    result = OpenCVIrisSegmenter().segment(encoded.tobytes())
    decoded = cv2.imdecode(np.frombuffer(result.png, np.uint8), cv2.IMREAD_UNCHANGED)

    assert decoded is not None
    assert 190 <= decoded.shape[0] <= 280
    assert decoded.shape[0] == decoded.shape[1]
    assert not np.any(decoded[0, :, 3])
    assert not np.any(decoded[-1, :, 3])
    assert not np.any(decoded[:, 0, 3])
    assert not np.any(decoded[:, -1, 3])
    center = decoded[decoded.shape[0] // 2, decoded.shape[1] // 2]
    assert center[3] == 255
    assert np.max(center[:3]) < 20


def test_opencv_segmenter_ignores_specular_reflections_during_detection() -> None:
    image = np.full((600, 900, 3), 220, dtype=np.uint8)
    cv2.circle(image, (450, 300), 130, (80, 110, 125), thickness=-1)
    cv2.circle(image, (450, 300), 45, (8, 8, 8), thickness=-1)
    cv2.rectangle(image, (420, 245), (440, 285), (255, 255, 255), thickness=-1)
    cv2.circle(image, (470, 270), 8, (255, 255, 255), thickness=-1)
    cv2.rectangle(image, (505, 275), (525, 295), (190, 190, 190), thickness=-1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    result = OpenCVIrisSegmenter().segment(encoded.tobytes())
    decoded = cv2.imdecode(np.frombuffer(result.png, np.uint8), cv2.IMREAD_UNCHANGED)

    assert decoded is not None
    assert 240 <= decoded.shape[0] <= 280
    assert 240 <= decoded.shape[1] <= 280
    center = decoded[decoded.shape[0] // 2, decoded.shape[1] // 2]
    assert center[3] == 255
    assert np.max(center[:3]) < 20
    crop_center_y, crop_center_x = decoded.shape[0] // 2, decoded.shape[1] // 2
    bright_reflection = decoded[
        crop_center_y - 55: crop_center_y - 15,
        crop_center_x - 30: crop_center_x - 10,
        :3,
    ]
    muted_reflection = decoded[
        crop_center_y - 25: crop_center_y - 5,
        crop_center_x + 55: crop_center_x + 75,
        :3,
    ]
    assert np.max(bright_reflection) < 180
    assert np.max(muted_reflection) < 180


def test_opencv_segmenter_rejects_invalid_bytes() -> None:
    try:
        OpenCVIrisSegmenter().segment(b"not-an-image")
    except ValueError as error:
        assert "decoded" in str(error)
    else:
        raise AssertionError("Invalid image bytes must be rejected")