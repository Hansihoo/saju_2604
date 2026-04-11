import unittest

from app.domain.saju.engine import PillarData
from app.domain.saju.services.calculate_special_stars import build_special_stars


def make_pillar(gan_zhi: str, *, xun_kong: str = "") -> PillarData:
    return PillarData(
        gan_zhi=gan_zhi,
        stem=gan_zhi[0],
        branch=gan_zhi[1],
        stem_five_element="",
        branch_five_element="",
        five_elements="",
        stem_ten_god="",
        branch_ten_god="",
        branch_ten_gods=[],
        hidden_stems=[],
        twelve_fortune="",
        na_yin="",
        xun="",
        xun_kong=xun_kong,
    )


class SpecialStarCalculationTests(unittest.TestCase):
    def test_builds_metadata_rich_special_star_registry(self) -> None:
        pillars = {
            "year": make_pillar("乙酉"),
            "month": make_pillar("庚辰"),
            "day": make_pillar("壬子", xun_kong="寅卯"),
            "time": make_pillar("戊午"),
        }

        stars = build_special_stars(
            pillars=pillars,
            visible_pillar_keys=["year", "month", "day", "time"],
        )
        star_map = {star.key: star for star in stars}

        self.assertEqual(len(stars), 34)
        self.assertEqual(star_map["cheondeok-gwiin"].method_id, "month-branch-trigram-conversion-common-kr")
        self.assertEqual(star_map["cheondeok-gwiin"].tier, "A")
        self.assertEqual(star_map["cheondeok-gwiin"].scope, "expanded")
        self.assertEqual(star_map["cheondeok-gwiin"].count, 1)
        self.assertEqual(star_map["cheondeok-gwiin"].matches[0].pillar_key, "day")
        self.assertEqual(star_map["cheondeok-gwiin"].matches[0].matched_field, "stem")

        self.assertTrue(star_map["woldeok-gwiin"].active)
        self.assertEqual(star_map["woldeok-gwiin"].matches[0].pillar_key, "day")
        self.assertEqual(star_map["woldeok-gwiin"].matches[0].matched_field, "stem")

        self.assertFalse(star_map["yeokma-year-branch"].active)

        self.assertTrue(star_map["hwagae-day-branch"].active)
        self.assertEqual(
            [match.pillar_key for match in star_map["hwagae-day-branch"].matches],
            ["month"],
        )

        self.assertFalse(star_map["gojin-day-branch"].active)

        self.assertFalse(star_map["wonjin"].active)
        self.assertEqual(star_map["wonjin"].count, 0)

        self.assertTrue(star_map["gwimungwan"].active)
        self.assertEqual(star_map["gwimungwan"].count, 2)

        self.assertFalse(star_map["hyeonchim"].active)
        self.assertEqual(star_map["hyeonchim"].count, 0)
        self.assertEqual(star_map["hyeonchim"].tier, "A")

        self.assertFalse(star_map["gwaegang"].active)
        self.assertTrue(star_map["dohwa-year-branch"].active)
        self.assertEqual(star_map["dohwa-year-branch"].label, "함지도화")
        self.assertTrue(star_map["dohwa-day-branch"].active)
        self.assertTrue(star_map["wangji-dohwa"].active)
        self.assertEqual(star_map["wangji-dohwa"].count, 3)
        self.assertTrue(star_map["mokyok-dohwa"].active)
        self.assertEqual(star_map["mokyok-dohwa"].count, 1)
        self.assertTrue(star_map["hongyeom"].active)
        self.assertEqual(star_map["hongyeom"].label, "홍염도화")
        self.assertEqual(star_map["hongyeom"].tier, "A")
        self.assertTrue(star_map["byeongnae-dohwa"].active)
        self.assertTrue(star_map["byeokoe-dohwa"].active)
        self.assertEqual(
            [match.pillar_key for match in star_map["byeokoe-dohwa"].matches],
            ["time"],
        )

    def test_adds_cheonmun_seong_from_previous_month_branch_rule(self) -> None:
        pillars = {
            "year": make_pillar("甲亥"),
            "month": make_pillar("丙子"),
            "day": make_pillar("乙卯"),
            "time": make_pillar("丁未"),
        }

        stars = build_special_stars(
            pillars=pillars,
            visible_pillar_keys=["year", "month", "day", "time"],
        )
        star_map = {star.key: star for star in stars}

        self.assertEqual(len(stars), 34)
        self.assertEqual(star_map["cheonmun-seong"].tier, "B")
        self.assertEqual(star_map["cheonmun-seong"].scope, "optional")
        self.assertEqual(star_map["cheonmun-seong"].category, "auspicious")
        self.assertEqual(star_map["cheonmun-seong"].method_id, "month-prev-branch-common-kr")
        self.assertEqual(star_map["cheonmun-seong"].anchor_value, "子")
        self.assertEqual(star_map["cheonmun-seong"].target_values, ["亥"])
        self.assertTrue(star_map["cheonmun-seong"].active)
        self.assertEqual(
            [match.pillar_key for match in star_map["cheonmun-seong"].matches],
            ["year"],
        )

    def test_distinguishes_hamji_and_wangji_dohwa_counts(self) -> None:
        pillars = {
            "year": make_pillar("乙酉"),
            "month": make_pillar("庚辰"),
            "day": make_pillar("丙子"),
            "time": make_pillar("癸巳"),
        }

        stars = build_special_stars(
            pillars=pillars,
            visible_pillar_keys=["year", "month", "day", "time"],
        )
        star_map = {star.key: star for star in stars}

        self.assertFalse(star_map["dohwa-year-branch"].active)
        self.assertTrue(star_map["dohwa-day-branch"].active)
        self.assertEqual(star_map["dohwa-day-branch"].count, 1)
        self.assertTrue(star_map["wangji-dohwa"].active)
        self.assertEqual(star_map["wangji-dohwa"].count, 2)
        self.assertEqual(
            [match.pillar_key for match in star_map["wangji-dohwa"].matches],
            ["year", "day"],
        )
        self.assertTrue(star_map["byeongnae-dohwa"].active)
        self.assertEqual(
            [match.pillar_key for match in star_map["byeongnae-dohwa"].matches],
            ["year"],
        )
        self.assertFalse(star_map["byeokoe-dohwa"].active)

    def test_hidden_time_policy_removes_time_based_matches(self) -> None:
        pillars = {
            "year": make_pillar("乙酉"),
            "month": make_pillar("庚辰"),
            "day": make_pillar("壬子", xun_kong="寅卯"),
            "time": make_pillar("戊午"),
        }

        stars = build_special_stars(
            pillars=pillars,
            visible_pillar_keys=["year", "month", "day"],
        )
        star_map = {star.key: star for star in stars}

        self.assertFalse(star_map["yeokma-year-branch"].active)
        self.assertFalse(star_map["gojin-day-branch"].active)
        self.assertFalse(star_map["hyeonchim"].active)
        self.assertFalse(star_map["byeokoe-dohwa"].active)
        self.assertFalse(star_map["gongmang"].active)
        self.assertEqual(star_map["gongmang"].count, 0)

    def test_splits_baekho_methods_by_method_id(self) -> None:
        classic_case = {
            "year": make_pillar("甲辰"),
            "month": make_pillar("乙丑"),
            "day": make_pillar("庚午"),
            "time": make_pillar("丙寅"),
        }
        classic_map = {
            star.key: star
            for star in build_special_stars(
                pillars=classic_case,
                visible_pillar_keys=["year", "month", "day", "time"],
            )
        }
        self.assertTrue(classic_map["baekho-daesal-classic"].active)
        self.assertFalse(classic_map["baekho-daesal-modern-kr"].active)

        modern_case = {
            "year": make_pillar("庚午"),
            "month": make_pillar("戊丑"),
            "day": make_pillar("甲辰"),
            "time": make_pillar("壬寅"),
        }
        modern_map = {
            star.key: star
            for star in build_special_stars(
                pillars=modern_case,
                visible_pillar_keys=["year", "month", "day", "time"],
            )
        }
        self.assertFalse(modern_map["baekho-daesal-classic"].active)
        self.assertTrue(modern_map["baekho-daesal-modern-kr"].active)


if __name__ == "__main__":
    unittest.main()
