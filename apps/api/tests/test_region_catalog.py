import unittest

from app.domain.saju.services.region_catalog import find_region_by_id, search_regions


class RegionCatalogTests(unittest.TestCase):
    def test_search_regions_supports_korean_city_name(self) -> None:
        items = search_regions(query="수원", limit=5)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0]["id"], "kr-gyeonggi-suwon")

    def test_search_regions_supports_korean_compound_query(self) -> None:
        items = search_regions(query="경기 수원", limit=5)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0]["id"], "kr-gyeonggi-suwon")

    def test_search_regions_supports_legacy_province_name_alias(self) -> None:
        items = search_regions(query="전라북도 전주", limit=5)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0]["id"], "kr-jeonbuk-jeonju")

    def test_search_regions_supports_new_csv_localities(self) -> None:
        items = search_regions(query="의왕", limit=5)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0]["id"], "kr-gyeonggi-uiwang")

    def test_search_regions_supports_special_city_alias(self) -> None:
        items = search_regions(query="서울시", limit=5)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0]["id"], "kr-seoul-special")

    def test_search_regions_does_not_match_all_korean_regions_by_timezone_name(self) -> None:
        items = search_regions(query="Seoul", limit=10)
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0]["id"], "kr-seoul-special")
        self.assertNotIn("kr-busan-metropolitan", [item["id"] for item in items])

    def test_find_region_by_id_includes_longitude_and_regional_offset(self) -> None:
        region = find_region_by_id("kr-seoul")

        self.assertEqual(region.id, "kr-seoul-special")
        self.assertEqual(region.longitude, 126.991824)
        self.assertEqual(region.regional_time_offset_minutes, -32.033)
        self.assertEqual(region.correction_basis, "광역자치단체 중심점")


if __name__ == "__main__":
    unittest.main()
