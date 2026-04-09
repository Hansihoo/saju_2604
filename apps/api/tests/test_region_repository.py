import unittest

from app.domain.saju.region_repository import (
    get_region_by_id,
    load_region_payloads,
    load_region_records,
    resolve_region_id,
)


class RegionRepositoryTests(unittest.TestCase):
    def test_load_region_records_returns_typed_records(self) -> None:
        records = load_region_records()

        self.assertGreater(len(records), 0)
        seoul = next(region for region in records if region.id == "kr-seoul-special")
        self.assertEqual(seoul.display_name, "서울특별시")
        self.assertEqual(seoul.source, "csv_seed")
        self.assertTrue(seoul.is_active)
        self.assertIsNone(seoul.latitude)
        self.assertIn("서울", seoul.aliases)

    def test_load_region_payloads_exposes_future_metadata_slots(self) -> None:
        payloads = load_region_payloads()

        seoul = next(region for region in payloads if region["id"] == "kr-seoul-special")
        self.assertIn("source", seoul)
        self.assertIn("latitude", seoul)
        self.assertIn("admin_code", seoul)
        self.assertIn("is_active", seoul)

    def test_resolve_region_id_keeps_legacy_mapping(self) -> None:
        self.assertEqual(resolve_region_id("kr-seoul"), "kr-seoul-special")
        self.assertEqual(resolve_region_id("kr-gyeonggi-suwon"), "kr-gyeonggi-suwon")

    def test_get_region_by_id_supports_legacy_ids(self) -> None:
        region = get_region_by_id("kr-seoul")

        self.assertIsNotNone(region)
        assert region is not None
        self.assertEqual(region.id, "kr-seoul-special")
        self.assertEqual(region.longitude, 126.991824)


if __name__ == "__main__":
    unittest.main()
