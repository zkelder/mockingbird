import pytest

from mockingbird.motion.activity_crop import plan_activity_crop, plan_activity_crop_bounds


def test_activity_crop_pads_and_clamps_to_image_bounds() -> None:
    plan = plan_activity_crop(
        source_media_asset_id="media-asset-1",
        image_width=100,
        image_height=80,
        left=0.80,
        top=0.70,
        right=0.95,
        bottom=0.95,
        crop_reason="user_zone",
    )

    assert plan.source_media_asset_id == "media-asset-1"
    assert plan.crop_reason == "user_zone"
    assert plan.is_full_frame_fallback is False
    assert plan.crop_box_normalized.left == pytest.approx(0.725)
    assert plan.crop_box_normalized.top == pytest.approx(0.575)
    assert plan.crop_box_normalized.right == 1.0
    assert plan.crop_box_normalized.bottom == 1.0
    assert plan.crop_box_pixels.left == 72
    assert plan.crop_box_pixels.top == 46
    assert plan.crop_box_pixels.right == 100
    assert plan.crop_box_pixels.bottom == 80
    assert plan.crop_box_pixels.width == 28
    assert plan.crop_box_pixels.height == 34
    assert plan.derived_crop_media_asset_id is None


def test_activity_crop_invalid_bounds_fall_back_to_full_frame() -> None:
    plan = plan_activity_crop(
        source_media_asset_id="media-asset-2",
        image_width=12,
        image_height=8,
        left=None,
        top=0.2,
        right=0.6,
        bottom=0.8,
        crop_reason="auto_region_cluster",
    )

    assert plan.source_media_asset_id == "media-asset-2"
    assert plan.crop_reason == "full_frame_fallback"
    assert plan.is_full_frame_fallback is True
    assert plan.warning
    assert plan.crop_box_normalized.left == 0.0
    assert plan.crop_box_normalized.top == 0.0
    assert plan.crop_box_normalized.right == 1.0
    assert plan.crop_box_normalized.bottom == 1.0
    assert plan.crop_box_pixels.left == 0
    assert plan.crop_box_pixels.top == 0
    assert plan.crop_box_pixels.right == 12
    assert plan.crop_box_pixels.bottom == 8


def test_activity_crop_bounds_plan_without_frame_dimensions() -> None:
    plan = plan_activity_crop_bounds(
        left=0.36,
        top=0.24,
        right=0.64,
        bottom=0.56,
    )

    assert plan.is_full_frame_fallback is False
    assert plan.crop_box_normalized.left == pytest.approx(0.22)
    assert plan.crop_box_normalized.top == pytest.approx(0.08)
    assert plan.crop_box_normalized.right == pytest.approx(0.78)
    assert plan.crop_box_normalized.bottom == pytest.approx(0.72)
    assert plan.warning is None
