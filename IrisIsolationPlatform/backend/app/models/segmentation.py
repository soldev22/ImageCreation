from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np


@dataclass(frozen=True)
class SegmentationOutput:
    png: bytes
    confidence: float
    width: int
    height: int


class IrisSegmenter(Protocol):
    def segment(self, image_bytes: bytes) -> SegmentationOutput: ...


class OpenCVIrisSegmenter:
    @staticmethod
    def _reflection_mask(
        image: np.ndarray,
        center_x: int,
        center_y: int,
        radius: int,
    ) -> np.ndarray:
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        yy, xx = np.ogrid[:height, :width]
        iris_region = (xx - center_x) ** 2 + (yy - center_y) ** 2 <= (radius * 0.94) ** 2
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        local_saturation = cv2.GaussianBlur(saturation, (0, 0), max(radius * 0.08, 3))
        local_value = cv2.GaussianBlur(value, (0, 0), max(radius * 0.08, 3))
        bright_glare = (saturation < 80) & (value > 185) & (gray > 180)
        muted_panel = (
            saturation.astype(np.int16) + 28 < local_saturation.astype(np.int16)
        ) & (value.astype(np.int16) > local_value.astype(np.int16) - 8)
        bright_mask = np.uint8(iris_region & bright_glare) * 255
        bright_mask = cv2.morphologyEx(
            bright_mask,
            cv2.MORPH_CLOSE,
            np.ones((5, 5), dtype=np.uint8),
        )

        filtered = np.zeros_like(bright_mask)
        max_area = np.pi * radius**2 * 0.12
        contours, _ = cv2.findContours(
            bright_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        for contour in contours:
            area = cv2.contourArea(contour)
            if 2 <= area <= max_area:
                x, y, width, height = cv2.boundingRect(contour)
                padding = max(4, int(radius * 0.05))
                cv2.rectangle(
                    filtered,
                    (max(0, x - padding), max(0, y - padding)),
                    (
                        min(width + x + padding, image.shape[1] - 1),
                        min(height + y + padding, image.shape[0] - 1),
                    ),
                    255,
                    thickness=-1,
                )

        muted_mask = np.uint8(iris_region & muted_panel) * 255
        muted_mask = cv2.morphologyEx(
            muted_mask,
            cv2.MORPH_CLOSE,
            np.ones((5, 5), dtype=np.uint8),
        )
        minimum_panel_area = np.pi * radius**2 * 0.003
        contours, _ = cv2.findContours(
            muted_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        for contour in contours:
            area = cv2.contourArea(contour)
            x, y, width, height = cv2.boundingRect(contour)
            rectangularity = area / max(width * height, 1)
            if minimum_panel_area <= area <= max_area and rectangularity >= 0.55:
                padding = max(3, int(radius * 0.02))
                cv2.rectangle(
                    filtered,
                    (max(0, x - padding), max(0, y - padding)),
                    (
                        min(width + x + padding, image.shape[1] - 1),
                        min(height + y + padding, image.shape[0] - 1),
                    ),
                    255,
                    thickness=-1,
                )

        join_size = max(9, int(radius * 0.06)) | 1
        filtered = cv2.morphologyEx(
            filtered,
            cv2.MORPH_CLOSE,
            np.ones((join_size, join_size), dtype=np.uint8),
        )
        filtered = cv2.dilate(filtered, np.ones((7, 7), dtype=np.uint8))
        return filtered

    @classmethod
    def _remove_reflections(
        cls,
        image: np.ndarray,
        center_x: int,
        center_y: int,
        radius: int,
    ) -> np.ndarray:
        reflection_mask = cls._reflection_mask(image, center_x, center_y, radius)
        if not reflection_mask.any():
            return image.copy()
        return cv2.inpaint(image, reflection_mask, 5, cv2.INPAINT_TELEA)

    @classmethod
    def _restore_iris_texture(
        cls,
        image: np.ndarray,
        center_x: int,
        center_y: int,
        radius: int,
    ) -> np.ndarray:
        reflection_mask = cls._reflection_mask(image, center_x, center_y, radius)
        if not reflection_mask.any():
            return image.copy()

        height, width = image.shape[:2]
        samples = []
        for angle in (45, 90, 135, 180, 225, 270, 315):
            transform = cv2.getRotationMatrix2D((center_x, center_y), angle, 1.0)
            samples.append(
                cv2.warpAffine(
                    image,
                    transform,
                    (width, height),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT_101,
                )
            )
        sample_stack = np.stack(samples)
        saturation_stack = np.stack(
            [cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)[:, :, 1] for sample in samples]
        )
        donor_indices = np.argmax(saturation_stack, axis=0)
        texture = np.take_along_axis(
            sample_stack,
            donor_indices[np.newaxis, :, :, np.newaxis],
            axis=0,
        )[0]
        x, y, mask_width, mask_height = cv2.boundingRect(reflection_mask)
        clone_center = (x + mask_width // 2, y + mask_height // 2)
        return cv2.seamlessClone(
            texture,
            image,
            reflection_mask,
            clone_center,
            cv2.NORMAL_CLONE,
        )

    @staticmethod
    def _sharpen(image: np.ndarray) -> np.ndarray:
        softened = cv2.GaussianBlur(image, (0, 0), 1.5)
        return cv2.addWeighted(image, 1.45, softened, -0.45, 0)

    @staticmethod
    def _degrain(image: np.ndarray) -> np.ndarray:
        return cv2.fastNlMeansDenoisingColored(
            image,
            None,
            h=4,
            hColor=4,
            templateWindowSize=7,
            searchWindowSize=21,
        )

    @staticmethod
    def _enhance_iris(image: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        luminance, channel_a, channel_b = cv2.split(lab)
        local_contrast = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8),
        ).apply(luminance)
        luminance = cv2.addWeighted(luminance, 0.4, local_contrast, 0.6, 6)
        enhanced = cv2.cvtColor(
            cv2.merge((luminance, channel_a, channel_b)),
            cv2.COLOR_LAB2BGR,
        )
        softened = cv2.GaussianBlur(enhanced, (0, 0), 1.2)
        sharpened = cv2.addWeighted(enhanced, 1.6, softened, -0.6, 0)
        hsv = cv2.cvtColor(sharpened, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1].astype(float)
        muted_color_boost = 0.55 * np.clip((80 - saturation) / 80, 0, 1) ** 2
        vibrance_gain = 1.38 - 0.12 * saturation / 255 + muted_color_boost
        hsv[:, :, 1] = np.uint8(np.clip(saturation * vibrance_gain, 0, 255))
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    @staticmethod
    def _enhance_limbus(
        image: np.ndarray,
        center_x: int,
        center_y: int,
        radius: int,
    ) -> np.ndarray:
        height, width = image.shape[:2]
        yy, xx = np.ogrid[:height, :width]
        normalized = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2) / max(radius, 1)
        inner_fade = np.clip((normalized - 0.72) / 0.1, 0, 1)
        outer_fade = np.clip((1.0 - normalized) / 0.05, 0, 1)
        ring_weight = inner_fade * outer_fade
        ring_weight = cv2.GaussianBlur(
            ring_weight.astype(np.float32),
            (0, 0),
            max(radius * 0.008, 0.8),
        )

        softened = cv2.GaussianBlur(image, (0, 0), 0.9)
        candidate = cv2.addWeighted(image, 1.85, softened, -0.85, 0)
        hsv = cv2.cvtColor(candidate, cv2.COLOR_BGR2HSV)
        hsv[:, :, 1] = np.uint8(np.clip(hsv[:, :, 1].astype(float) * 1.22, 0, 255))
        hsv[:, :, 2] = np.uint8(np.clip(hsv[:, :, 2].astype(float) * 0.94, 0, 255))
        candidate = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        weight = ring_weight[:, :, np.newaxis]
        return np.uint8(np.clip(image * (1 - weight) + candidate * weight, 0, 255))

    @staticmethod
    def _build_iris_mask(
        image: np.ndarray,
        center_x: int,
        center_y: int,
        radius: int,
    ) -> np.ndarray:
        height, width = image.shape[:2]
        yy, xx = np.ogrid[:height, :width]
        search_region = (xx - center_x) ** 2 + (yy - center_y) ** 2 <= (radius * 1.06) ** 2
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        threshold, _ = cv2.threshold(
            gray[search_region].reshape(-1, 1),
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        dark_region = np.uint8((gray <= threshold) & search_region) * 255
        kernel_size = max(7, radius // 18) | 1
        dark_region = cv2.morphologyEx(
            dark_region,
            cv2.MORPH_CLOSE,
            np.ones((kernel_size, kernel_size), dtype=np.uint8),
        )
        contours, _ = cv2.findContours(
            dark_region,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        candidates = [
            contour
            for contour in contours
            if len(contour) >= 5
            and cv2.pointPolygonTest(
                contour,
                (float(center_x), float(center_y)),
                False,
            )
            >= 0
        ]

        mask = np.zeros((height, width), dtype=np.uint8)
        if candidates:
            (ellipse_x, ellipse_y), axes, angle = cv2.fitEllipse(
                max(candidates, key=cv2.contourArea)
            )
            maximum_axis = float(radius * 2)
            minimum_axis = float(radius * 1.55)
            axis_width = float(np.clip(axes[0], minimum_axis, maximum_axis))
            axis_height = float(np.clip(axes[1], minimum_axis, maximum_axis))
            major_axis = max(axis_width, axis_height)
            minimum_rounded_axis = major_axis * 0.97
            axis_width = max(axis_width, minimum_rounded_axis)
            axis_height = max(axis_height, minimum_rounded_axis)
            center_shift = np.hypot(ellipse_x - center_x, ellipse_y - center_y)
            if center_shift <= radius * 0.1:
                cv2.ellipse(
                    mask,
                    ((ellipse_x, ellipse_y), (axis_width, axis_height), angle),
                    255,
                    thickness=-1,
                    lineType=cv2.LINE_AA,
                )
        if not mask.any():
            cv2.circle(
                mask,
                (center_x, center_y),
                radius,
                255,
                thickness=-1,
                lineType=cv2.LINE_AA,
            )
        return cv2.GaussianBlur(mask, (3, 3), 0)

    @staticmethod
    def _render_pupil(
        image: np.ndarray,
        center_x: int,
        center_y: int,
        radius: int,
    ) -> np.ndarray:
        height, width = image.shape[:2]
        yy, xx = np.ogrid[:height, :width]
        distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
        normalized = np.clip(distance / max(radius, 1), 0, 1)
        luminance = np.uint8(3 + 9 * normalized**2)
        pupil = np.empty_like(image)
        pupil[:, :, 0] = luminance
        pupil[:, :, 1] = luminance
        pupil[:, :, 2] = np.uint8(luminance * 0.9)

        pupil_mask = np.uint8(distance <= radius) * 255
        pupil_mask = cv2.GaussianBlur(pupil_mask, (9, 9), 0).astype(float) / 255
        pupil_mask = pupil_mask[:, :, np.newaxis]
        blended = image.astype(float) * (1 - pupil_mask) + pupil.astype(float) * pupil_mask
        return np.uint8(
            np.clip(blended, 0, 255)
        )

    @staticmethod
    def _find_iris(gray: np.ndarray) -> tuple[int, int, int, float]:
        height, width = gray.shape
        min_dimension = min(width, height)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        search_mask = np.zeros_like(gray)
        margin_x, margin_y = int(width * 0.12), int(height * 0.12)
        search_mask[margin_y:height - margin_y, margin_x:width - margin_x] = 255
        threshold = float(np.percentile(blurred[search_mask > 0], 15))
        dark = np.uint8((blurred <= threshold) & (search_mask > 0)) * 255
        kernel_size = max(5, int(min_dimension * 0.015)) | 1
        dark = cv2.morphologyEx(
            dark,
            cv2.MORPH_CLOSE,
            np.ones((kernel_size, kernel_size), dtype=np.uint8),
        )
        dark = cv2.morphologyEx(
            dark,
            cv2.MORPH_OPEN,
            np.ones((5, 5), dtype=np.uint8),
        )

        center_x, center_y = width / 2, height / 2
        candidates: list[tuple[float, int, int, int]] = []
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        yy, xx = np.ogrid[:height, :width]
        for contour in contours:
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if area <= 0 or perimeter <= 0:
                continue
            (candidate_x, candidate_y), enclosing_radius = cv2.minEnclosingCircle(contour)
            equivalent_radius = np.sqrt(area / np.pi)
            radius = int(round(np.sqrt(equivalent_radius * enclosing_radius)))
            if not min_dimension * 0.07 <= radius <= min_dimension * 0.32:
                continue

            circularity = float(4 * np.pi * area / (perimeter * perimeter))
            fill = float(area / (np.pi * enclosing_radius * enclosing_radius))
            distance = np.hypot(candidate_x - center_x, candidate_y - center_y) / min_dimension
            distance_squared = (xx - candidate_x) ** 2 + (yy - candidate_y) ** 2
            inner_ring = (distance_squared <= radius**2) & (
                distance_squared >= (radius * 0.72) ** 2
            )
            outer_ring = (distance_squared <= (radius * 1.2) ** 2) & (
                distance_squared >= (radius * 1.04) ** 2
            )
            contrast = 0.0
            if inner_ring.any() and outer_ring.any():
                contrast = float(np.mean(gray[outer_ring]) - np.mean(gray[inner_ring])) / 128
            score = 2.2 * circularity + 1.4 * fill + 2.5 * max(contrast, 0) - 1.2 * distance
            candidates.append(
                (score, int(round(candidate_x)), int(round(candidate_y)), radius)
            )

        if candidates:
            score, iris_x, iris_y, iris_radius = max(candidates)
            return iris_x, iris_y, iris_radius, score

        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        circles = cv2.HoughCircles(
            enhanced,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=min_dimension / 3,
            param1=90,
            param2=28,
            minRadius=max(8, int(min_dimension * 0.04)),
            maxRadius=max(16, int(min_dimension * 0.28)),
        )
        if circles is None:
            raise ValueError("No iris boundary was detected; use a closer, well-lit eye photograph")
        iris_x, iris_y, iris_radius = min(
            np.round(circles[0]).astype(int),
            key=lambda circle: (circle[0] - center_x) ** 2 + (circle[1] - center_y) ** 2,
        )
        return int(iris_x), int(iris_y), int(iris_radius), 0.0

    @staticmethod
    def _find_pupil(
        gray: np.ndarray,
        iris_x: int,
        iris_y: int,
        iris_radius: int,
    ) -> tuple[int, int, int]:
        height, width = gray.shape
        yy, xx = np.ogrid[:height, :width]
        iris_mask = (xx - iris_x) ** 2 + (yy - iris_y) ** 2 <= (iris_radius * 0.72) ** 2
        threshold = float(np.percentile(gray[iris_mask], 9))
        dark = np.uint8((gray <= threshold) & iris_mask) * 255
        kernel_size = max(5, int(iris_radius * 0.08)) | 1
        dark = cv2.morphologyEx(
            dark,
            cv2.MORPH_CLOSE,
            np.ones((kernel_size, kernel_size), dtype=np.uint8),
        )
        contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates: list[tuple[float, int, int, int]] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area <= 0:
                continue
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue
            pupil_x = int(round(moments["m10"] / moments["m00"]))
            pupil_y = int(round(moments["m01"] / moments["m00"]))
            (_, _), enclosing_radius = cv2.minEnclosingCircle(contour)
            equivalent_radius = np.sqrt(area / np.pi)
            pupil_radius = int(round(np.sqrt(equivalent_radius * enclosing_radius)))
            if not iris_radius * 0.08 <= pupil_radius <= iris_radius * 0.5:
                continue
            distance = np.hypot(pupil_x - iris_x, pupil_y - iris_y) / iris_radius
            score = equivalent_radius / iris_radius - 2.0 * distance
            candidates.append((score, pupil_x, pupil_y, pupil_radius))

        if not candidates:
            return iris_x, iris_y, max(3, iris_radius // 3)
        _, pupil_x, pupil_y, pupil_radius = max(candidates)
        pupil_radius = min(int(round(pupil_radius * 1.35)), int(iris_radius * 0.55))
        return pupil_x, pupil_y, pupil_radius

    @staticmethod
    def _refine_pupil_radius(
        gray: np.ndarray,
        center_x: int,
        center_y: int,
        detected_radius: int,
    ) -> int:
        height, width = gray.shape
        yy, xx = np.ogrid[:height, :width]
        distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
        core = distance <= max(4, detected_radius * 0.25)
        if not core.any():
            return detected_radius

        baseline = float(np.median(gray[core]))
        threshold = baseline + max(10, baseline * 0.35)
        bin_width = max(2, detected_radius // 25)
        bright_bins = 0
        for radius in range(max(4, detected_radius // 4), detected_radius, bin_width):
            sample = (distance >= radius) & (distance < radius + bin_width)
            if sample.any() and float(np.median(gray[sample])) >= threshold:
                bright_bins += 1
                if bright_bins >= 2:
                    return max(3, radius - bin_width)
            else:
                bright_bins = 0
        return detected_radius

    @staticmethod
    def _find_limbus_radius(
        gray: np.ndarray,
        pupil_x: int,
        pupil_y: int,
        pupil_radius: int,
    ) -> int:
        height, width = gray.shape
        min_dimension = min(width, height)
        minimum_radius = max(int(pupil_radius * 1.8), int(min_dimension * 0.12))
        maximum_radius = int(min_dimension * 0.46)
        edge_radii: list[int] = []

        angles = list(range(-35, 36, 3)) + list(range(145, 216, 3))
        for angle_degrees in angles:
            angle = np.deg2rad(angle_degrees)
            radii = np.arange(minimum_radius, maximum_radius)
            sample_x = np.rint(pupil_x + np.cos(angle) * radii).astype(int)
            sample_y = np.rint(pupil_y + np.sin(angle) * radii).astype(int)
            valid = (
                (sample_x >= 5)
                & (sample_x < width - 5)
                & (sample_y >= 5)
                & (sample_y < height - 5)
            )
            radii = radii[valid]
            if len(radii) < 30:
                continue
            samples = gray[sample_y[valid], sample_x[valid]].astype(float)
            smoothed = np.convolve(samples, np.ones(9) / 9, mode="same")
            gradient = np.zeros_like(smoothed)
            gradient[5:-5] = smoothed[10:] - smoothed[:-10]
            indices = np.arange(10, len(radii) - 10)
            if not len(indices):
                continue
            weighted = gradient[indices] * (radii[indices] / min_dimension) ** 0.7
            edge_radii.append(int(radii[indices[np.argmax(weighted)]]))

        if len(edge_radii) < 8:
            raise ValueError("No iris boundary was detected; use a closer, well-lit eye photograph")
        return int(round(np.percentile(edge_radii, 25)))

    @staticmethod
    def _refine_limbus_radius(
        image: np.ndarray,
        center_x: int,
        center_y: int,
        pupil_radius: int,
        detected_radius: int,
    ) -> int:
        height, width = image.shape[:2]
        yy, xx = np.ogrid[:height, :width]
        offset_x = xx - center_x
        offset_y = yy - center_y
        distance = np.sqrt(offset_x**2 + offset_y**2)
        horizontal = np.abs(offset_y) <= np.maximum(np.abs(offset_x) * 0.7, 1)
        saturation = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
        bin_width = max(3, detected_radius // 50)
        baseline_region = (
            (distance >= max(pupil_radius * 1.8, detected_radius * 0.52))
            & (distance <= detected_radius * 0.68)
            & horizontal
        )
        if not baseline_region.any():
            return detected_radius

        baseline = float(np.median(saturation[baseline_region]))
        start = max(int(detected_radius * 0.68), pupil_radius * 2)
        stop = int(detected_radius * 0.95)
        if baseline < 35:
            value = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2]
            baseline_value = float(np.median(value[baseline_region]))
            threshold = max(baseline_value + 18, baseline_value * 1.3)
            low_bins = 0
            for radius in range(start, stop, bin_width):
                sample = (
                    (distance >= radius)
                    & (distance < radius + bin_width)
                    & horizontal
                )
                if sample.any() and float(np.median(value[sample])) >= threshold:
                    low_bins += 1
                    if low_bins >= 2:
                        crossing = radius - bin_width
                        margin = int(round(detected_radius * 0.03))
                        return min(detected_radius, crossing + margin)
                else:
                    low_bins = 0
            return detected_radius
        threshold = baseline * 0.5
        low_bins = 0
        for radius in range(start, stop, bin_width):
            sample = (
                (distance >= radius)
                & (distance < radius + bin_width)
                & horizontal
            )
            if sample.any() and float(np.median(saturation[sample])) <= threshold:
                low_bins += 1
                if low_bins >= 2:
                    crossing = radius - bin_width
                    refined = crossing + int(round(detected_radius * 0.05))
                    return min(detected_radius, max(refined, crossing))
            else:
                low_bins = 0
        return detected_radius

    def segment(self, image_bytes: bytes) -> SegmentationOutput:
        encoded = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Image could not be decoded")
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        min_dimension = min(width, height)
        center_x, center_y = width / 2, height / 2
        coarse_x, coarse_y, coarse_radius, detection_score = self._find_iris(gray)
        pupil_x, pupil_y, pupil_radius = self._find_pupil(
            gray,
            coarse_x,
            coarse_y,
            coarse_radius,
        )
        pupil_radius = self._refine_pupil_radius(
            gray,
            pupil_x,
            pupil_y,
            pupil_radius,
        )
        analysis = self._remove_reflections(
            image,
            coarse_x,
            coarse_y,
            int(coarse_radius * 1.35),
        )
        analysis = self._sharpen(analysis)
        analysis_gray = cv2.cvtColor(analysis, cv2.COLOR_BGR2GRAY)
        iris_radius = self._find_limbus_radius(
            analysis_gray,
            pupil_x,
            pupil_y,
            pupil_radius,
        )
        iris_radius = self._refine_limbus_radius(
            image,
            pupil_x,
            pupil_y,
            pupil_radius,
            iris_radius,
        )
        iris_x, iris_y = pupil_x, pupil_y
        reflection_free = self._restore_iris_texture(
            image,
            iris_x,
            iris_y,
            iris_radius,
        )
        degrained = self._degrain(reflection_free)
        sharpened = self._enhance_iris(degrained)
        sharpened = self._enhance_limbus(
            sharpened,
            iris_x,
            iris_y,
            iris_radius,
        )
        rendered = self._render_pupil(
            sharpened,
            pupil_x,
            pupil_y,
            pupil_radius,
        )

        mask = self._build_iris_mask(
            image,
            iris_x,
            iris_y,
            iris_radius,
        )
        output = cv2.cvtColor(rendered, cv2.COLOR_BGR2BGRA)
        output[:, :, 3] = mask

        crop_padding = max(3, int(round(iris_radius * 0.04)))
        alpha_bounds = cv2.boundingRect(cv2.findNonZero(mask))
        mask_x, mask_y, mask_width, mask_height = alpha_bounds
        crop_size = max(mask_width, mask_height) + crop_padding * 2
        crop_center_x = mask_x + mask_width // 2
        crop_center_y = mask_y + mask_height // 2
        x1 = max(0, crop_center_x - crop_size // 2)
        y1 = max(0, crop_center_y - crop_size // 2)
        x2 = min(width, x1 + crop_size)
        y2 = min(height, y1 + crop_size)
        x1 = max(0, x2 - crop_size)
        y1 = max(0, y2 - crop_size)
        cropped = output[y1:y2, x1:x2]
        ok, png = cv2.imencode(".png", cropped, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        if not ok:
            raise RuntimeError("Transparent PNG encoding failed")

        center_distance = np.hypot(iris_x - center_x, iris_y - center_y) / max(
            min_dimension,
            1,
        )
        roi = gray[
            max(0, iris_y - iris_radius): iris_y + iris_radius,
            max(0, iris_x - iris_radius): iris_x + iris_radius,
        ]
        contrast = float(np.std(roi) / 64) if roi.size else 0.0
        region_quality = float(np.clip(detection_score / 4, 0, 0.18))
        confidence = float(
            np.clip(0.78 - center_distance + min(contrast, 0.12) + region_quality, 0.35, 0.98)
        )
        return SegmentationOutput(png.tobytes(), confidence, width, height)