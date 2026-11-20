from pathlib import Path
import unittest

from ai_model.prepare_camera8_finetune import parent_dates, split_frames


class Camera8SplitTests(unittest.TestCase):
    def test_parent_exclusion_uses_every_camera_and_both_splits(self):
        manifest = {"train_paths": ["SUNNY/2015-11-12/camera1/a.jpg"],
                    "val_paths": ["RAINY/2016-01-08/camera8/b.jpg"]}
        self.assertEqual(parent_dates(manifest), {"2015-11-12", "2016-01-08"})

    def test_test_dates_unseen_by_parent_and_no_day_crosses_splits(self):
        frames = []
        for day in range(1, 16):
            weather = ["SUNNY", "RAINY", "OVERCAST"][day % 3]
            for index in range(4):
                frames.append(Path(f"{weather}/2015-11-{day:02d}/camera8/frame{index}.jpg"))
        seen = {f"2015-11-{day:02d}" for day in range(1, 13)}
        split = split_frames(frames, seen)
        dates = {key: {p.parent.parent.name for p in values} for key, values in split.items()}
        self.assertFalse(dates["test"] & seen)
        self.assertFalse(dates["train"] & dates["val"])
        self.assertFalse(dates["train"] & dates["test"])
        self.assertFalse(dates["val"] & dates["test"])
        self.assertEqual(sum(map(len, split.values())), len(frames))
        for key in ("train", "val"):
            self.assertEqual({p.parent.parent.parent.name for p in split[key]}, {"SUNNY", "RAINY", "OVERCAST"})


if __name__ == "__main__":
    unittest.main()
