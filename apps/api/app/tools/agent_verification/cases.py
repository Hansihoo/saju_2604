"""Fixed synthetic questions; preparing one case needs no other agent."""

from .contracts import CaseSpec

DEFAULT_AS_OF = "2026-10-05T12:00:00+09:00"


def cases():
    seoul = {"birth_date": "1997-09-18", "birth_time": "14:30", "gender": "female", "region_id": "kr-seoul"}
    busan = {"birth_date": "1990-01-01", "birth_time": "10:30", "gender": "male", "region_id": "kr-busan"}
    rows = [
        ("S1", "ko", "today", "today.action", "오늘 무엇부터 하는 게 좋을까?", seoul),
        ("S2", "ko", "love", "love.meeting_window", "연인은 언제쯤 만날 수 있을까?", busan),
        ("S3", "ko", "work_money", "career.reward_window", "책임을 맡으면 좋은 평가와 보상도 따라올까?", seoul),
        ("S4", "en", "core", "fortune.population_comparison", "Is my fortune better than other people's?", busan),
        ("S5", "ko", "luck_flow", "luck.current_pattern", "출생 시간을 모르는데 지금 운의 흐름도 알 수 있을까?",
         dict(seoul, birth_time="00:00", is_birth_time_estimated=True)),
        ("S6", "ko", "love", "love.pattern", "어떤 관계에서 편할까?",
         dict(busan, calendar_type="lunar", birth_date="1990-02-30")),
    ]
    return {row[0]: CaseSpec(case_id=row[0], locale=row[1], topic=row[2], question_id=row[3],
                            question=row[4], persona=("모바일에서 빠르게 읽고 친구에게 공유할지 고민하는 사용자."
                            if row[1] == "ko" else "A mobile reader deciding whether this is useful enough to share."),
                            birth_input=dict(row[5], locale=row[1], accuracy_mode="legacy")) for row in rows}
