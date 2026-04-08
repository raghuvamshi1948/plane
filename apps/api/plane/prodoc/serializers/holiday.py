"""
Serializer for HolidayCalendar.

Validation contract (lives here, not on the model — see the model
docstring at plane/prodoc/models/holiday.py for the rationale):

- `holidays` must be a list (not a dict, not a string).
- Each entry must be a non-empty string in ISO `YYYY-MM-DD` format.
- Duplicates are rejected at write time so the stored list is canonical.
- The list is sorted ascending on save so reads are stable.
"""

from datetime import date

from rest_framework import serializers

from plane.prodoc.models import HolidayCalendar


class HolidayCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = HolidayCalendar
        fields = [
            "id",
            "workspace",
            "name",
            "holidays",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "workspace",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]

    def validate_holidays(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "holidays must be a list of ISO date strings."
            )

        seen = set()
        parsed = []
        for entry in value:
            if not isinstance(entry, str):
                raise serializers.ValidationError(
                    f"Each holiday must be a string in YYYY-MM-DD format; got {entry!r}."
                )
            try:
                d = date.fromisoformat(entry)
            except ValueError:
                raise serializers.ValidationError(
                    f"Invalid date {entry!r}; expected YYYY-MM-DD."
                )
            if d in seen:
                raise serializers.ValidationError(
                    f"Duplicate holiday {entry!r}."
                )
            seen.add(d)
            parsed.append(d)

        # Canonicalize: sort and re-emit as ISO strings.
        return [d.isoformat() for d in sorted(parsed)]
