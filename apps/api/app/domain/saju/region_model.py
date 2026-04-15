"""이 파일은 지역 정보를 담는 불변 도메인 모델을 정의한다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class RegionRecord:
    id: str
    display_name: str
    country: str
    province: str
    city: str
    tzid: str
    longitude: float
    regional_time_offset_minutes: float
    correction_basis: str
    aliases: Tuple[str, ...]
    latitude: Optional[float] = None
    admin_code: Optional[str] = None
    source: str = "csv_seed"
    is_active: bool = True

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RegionRecord":
        """mapping 관련 값을 반환하거나 처리한다."""
        aliases = tuple(str(alias) for alias in payload.get("aliases", []))
        latitude = payload.get("latitude")
        return cls(
            id=str(payload["id"]),
            display_name=str(payload["display_name"]),
            country=str(payload["country"]),
            province=str(payload["province"]),
            city=str(payload["city"]),
            tzid=str(payload["tzid"]),
            longitude=float(payload["longitude"]),
            regional_time_offset_minutes=float(payload["regional_time_offset_minutes"]),
            correction_basis=str(payload["correction_basis"]),
            aliases=aliases,
            latitude=float(latitude) if latitude is not None else None,
            admin_code=str(payload["admin_code"]) if payload.get("admin_code") else None,
            source=str(payload.get("source", "csv_seed")),
            is_active=bool(payload.get("is_active", True)),
        )

    def to_public_dict(self) -> Dict[str, object]:
        """공개용 dict 관련 값을 반환하거나 처리한다."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "country": self.country,
            "province": self.province,
            "city": self.city,
            "tzid": self.tzid,
            "longitude": self.longitude,
            "regional_time_offset_minutes": self.regional_time_offset_minutes,
            "correction_basis": self.correction_basis,
            "aliases": list(self.aliases),
            "latitude": self.latitude,
            "admin_code": self.admin_code,
            "source": self.source,
            "is_active": self.is_active,
        }
