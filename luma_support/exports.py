"""Shared CSV-export mixin for portal list views.

Any ``ListView`` subclass can opt in by adding ``CsvExportMixin``,
declaring ``csv_columns`` (a list of ``(header, accessor)`` tuples
where ``accessor`` is either a string attribute name / dotted path or
a callable taking the object) and ``csv_filename`` (a base name,
without extension). Requesting ``?export=csv`` then short-circuits the
HTML render and streams a CSV.

Scope is respected — the mixin uses ``self.get_queryset()`` so the
existing per-user filtering, search, and tag filters all carry through.
The result is paginated-free (no ``paginate_by``) so an export contains
every row matching the active filters.
"""
from __future__ import annotations

import csv
from typing import Any, Callable, Iterable

from django.http import HttpResponse
from django.utils import timezone


def _resolve(obj: Any, accessor: str | Callable[[Any], Any]) -> Any:
    if callable(accessor):
        return accessor(obj)
    value: Any = obj
    for part in accessor.split("."):
        if value is None or value == "":
            return ""
        value = getattr(value, part, "")
    # Methods (e.g. ``get_priority_display``) get called with no args.
    if callable(value):
        try:
            value = value()
        except TypeError:
            value = ""
    return "" if value is None else value


class CsvExportMixin:
    csv_columns: Iterable[tuple[str, str | Callable[[Any], Any]]] = ()
    csv_filename: str = "export"

    def render_to_response(self, context, **response_kwargs):  # type: ignore[override]
        if self.request.GET.get("export") == "csv":
            return self._export_csv()
        return super().render_to_response(context, **response_kwargs)  # type: ignore[misc]

    def _export_csv(self) -> HttpResponse:
        stamp = timezone.now().strftime("%Y%m%d-%H%M")
        filename = f"{self.csv_filename}-{stamp}.csv"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow([header for header, _ in self.csv_columns])
        # Drop pagination for the export — we want every row that matches.
        qs = self.get_queryset()  # type: ignore[attr-defined]
        for obj in qs:
            writer.writerow([_resolve(obj, accessor) for _, accessor in self.csv_columns])
        return response
