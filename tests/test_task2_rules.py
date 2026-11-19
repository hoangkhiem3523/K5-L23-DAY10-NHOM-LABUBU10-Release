
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import struct
import zlib
from validator.validate import (
    check_metadata_rules,
    check_panoptic_rules,
)


class TestTask2Rules(unittest.TestCase):

    def test_scene_leak(self):
        metadata = {
            "items": [
                {
                    "image": "img_001",
                    "scene_id": "scene_A",
                    "split": "train",
                },
                {
                    "image": "img_002",
                    "scene_id": "scene_A",
                    "split": "val",
                },
            ]
        }

        with TemporaryDirectory() as tmp:
            errors = check_metadata_rules(Path(tmp), metadata)

        self.assertIn(
            {"type": "scene_leak", "target": "scene_A"},
            errors,
        )

    def test_invalid_category_id(self):
        panoptic = {
            "categories": [{"id": 1, "isthing": 1}],
            "annotations": [
                {
                    "file_name": "img_001.png",
                    "segments_info": [
                        {"id": 100, "category_id": 999}
                    ],
                }
            ],
        }

        with TemporaryDirectory() as tmp:
            errors = check_panoptic_rules(Path(tmp), panoptic)

        self.assertIn(
            {"type": "invalid_category_id", "target": "img_001"},
            errors,
        )


    def test_guideline_mismatch(self):
        metadata = {
            "items": [
                {
                    "image": "img_003",
                    "job_id": "J001",
                    "guideline_version": "v1",
                }
            ]
        }

        with TemporaryDirectory() as tmp:
            delivery = Path(tmp)

            (delivery / "jobs.csv").write_text(
                "job_id,guideline\n"
                "J001,v2\n",
                encoding="utf-8",
            )

            errors = check_metadata_rules(delivery, metadata)

        self.assertIn(
            {
                "type": "guideline_mismatch",
                "target": "img_003",
            },
            errors,
        )

    def test_thing_overlap(self):
        # Tạo PNG RGB 10x10, toàn bộ 100 pixel có segment ID = 261.
        width, height = 10, 10
        segment_id = 261

        rgb = bytes((
            segment_id & 255,
            (segment_id >> 8) & 255,
            (segment_id >> 16) & 255,
        ))

        # Mỗi dòng PNG bắt đầu bằng filter byte = 0.
        raw = b"".join(
            b"\x00" + rgb * width
            for _ in range(height)
        )

        def chunk(tag, data):
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        png_data = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(
                b"IHDR",
                struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
            )
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )

        with TemporaryDirectory() as tmp:
            delivery = Path(tmp)
            (delivery / "masks").mkdir()

            (delivery / "masks" / "img_004.png").write_bytes(png_data)

            panoptic = {
                "categories": [{"id": 1, "isthing": 1}],
                "annotations": [
                    {
                        "file_name": "img_004.png",
                        "segments_info": [
                            {
                                "id": segment_id,
                                "category_id": 1,
                                "area": 150,
                                "iscrowd": 0,
                            }
                        ],
                    }
                ],
            }

            errors = check_panoptic_rules(delivery, panoptic)

        self.assertIn(
            {"type": "thing_overlap", "target": "img_004"},
            errors,
        )

    def test_scene_no_leak(self):
        metadata = {
            "items": [
                {
                    "image": "img_001",
                    "scene_id": "scene_A",
                    "split": "train",
                },
                {
                    "image": "img_002",
                    "scene_id": "scene_A",
                    "split": "train",
                },
                {
                    "image": "img_003",
                    "scene_id": "scene_B",
                    "split": "val",
                },
            ]
        }

        with TemporaryDirectory() as tmp:
            errors = check_metadata_rules(Path(tmp), metadata)

        self.assertFalse(
            any(e["type"] == "scene_leak" for e in errors)
        )

    def test_valid_category(self):
        panoptic = {
            "categories": [
                {"id": 1, "isthing": 1}
            ],
            "annotations": [
                {
                    "file_name": "img_005.png",
                    "segments_info": [
                        {"id": 100, "category_id": 1}
                    ],
                }
            ],
        }

        with TemporaryDirectory() as tmp:
            errors = check_panoptic_rules(Path(tmp), panoptic)

        self.assertFalse(
            any(e["type"] == "invalid_category_id" for e in errors)
        )

if __name__ == "__main__":
    unittest.main()
