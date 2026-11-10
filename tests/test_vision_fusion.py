"""Geometry, independent view support, and class disagreement contracts."""
import unittest

from backend.config.vision import parse_rotations
from backend.model.vision_fusion import fuse_detections, restore_box, select_cars


def evidence(angle, label="car", score=0.9, box=(10, 20, 40, 70)):
    return {"rotation": angle, "class_name": label, "confidence": score, "box": list(box)}


class FusionTests(unittest.TestCase):
    def test_inverse_quarter_turns_preserve_non_square_image_coordinates(self):
        for angle, box in [(0, [10, 20, 40, 70]), (90, [20, 160, 70, 190]),
                           (180, [160, 30, 190, 80]), (270, [30, 10, 80, 40])]:
            with self.subTest(angle=angle):
                self.assertEqual(restore_box(box, angle, 200, 100), [10, 20, 40, 70])

    def test_duplicate_boxes_from_one_view_cannot_satisfy_consensus(self):
        fused = fuse_detections([evidence(0) for _ in range(4)])
        accepted, rejected = select_cars(fused, 0.75, (200, 100))
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]["reason"], "insufficient_views")
        self.assertEqual(fused[0]["support_views"], 1)

    def test_class_vote_can_outweigh_a_single_strong_car_score(self):
        fused = fuse_detections([evidence(0, "car", 0.95), evidence(90, "motorcycle", 0.90),
                                 evidence(180, "motorcycle", 0.90)])
        self.assertEqual(fused[0]["class_name"], "motorcycle")
        self.assertEqual(select_cars(fused, 0.75, (200, 100))[0], [])

    def test_trucks_remain_trucks(self):
        fused = fuse_detections([evidence(a, "truck") for a in (0, 90, 180, 270)])
        self.assertEqual(fused[0]["class_name"], "truck")
        self.assertEqual(select_cars(fused, 0.35, (200, 100))[0], [])

    def test_equal_class_evidence_is_ambiguous(self):
        fused = fuse_detections([evidence(0), evidence(90), evidence(180, "truck"), evidence(270, "truck")])
        accepted, rejected = select_cars(fused, 0.75, (200, 100))
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]["reason"], "ambiguous_class")

    def test_vote_sum_is_not_used_as_confidence(self):
        fused = fuse_detections([evidence(0, score=0.74), evidence(90, score=0.74)])
        self.assertEqual(fused[0]["confidence"], 0.74)
        self.assertEqual(select_cars(fused, 0.75, (200, 100))[1][0]["reason"], "below_confidence")

    def test_distinct_objects_and_explicit_border_policy(self):
        fused = fuse_detections([evidence(a, box=box) for a in (0, 90)
                                 for box in ((10, 20, 40, 70), (180, 20, 200, 70))])
        self.assertEqual(len(select_cars(fused, 0.75, (200, 100), edge_margin=0)[0]), 2)
        accepted, rejected = select_cars(fused, 0.75, (200, 100), edge_margin=1)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(rejected[0]["reason"], "truncated_at_border")

    def test_empty_views_and_rotation_configuration(self):
        self.assertEqual(fuse_detections([]), [])
        self.assertEqual(parse_rotations("0, 90,180,270"), (0, 90, 180, 270))
        self.assertEqual(parse_rotations("0"), (0,))
        for value in ("", "0,0", "0,45", "x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_rotations(value)


if __name__ == "__main__":
    unittest.main()
