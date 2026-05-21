from django.contrib import admin
from django.utils.text import slugify

from .models import (
    Attachment,
    Ticket,
    TicketNote,
    TicketTag,
    TicketTemplate,
    TimeEntry,
)


class TimeEntryInline(admin.TabularInline):
    model = TimeEntry
    extra = 0
    fields = ("user", "minutes", "description", "billable", "created_at")
    readonly_fields = ("created_at",)


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ("file", "filename", "uploaded_by", "uploaded_at")
    readonly_fields = ("uploaded_at",)


class TicketNoteInline(admin.TabularInline):
    model = TicketNote
    extra = 0
    fields = ("author", "body", "internal", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "subject",
        "client",
        "priority",
        "status",
        "assigned_to",
        "sla_deadline",
        "created_at",
    )
    list_filter = ("status", "priority", "assigned_to", "tags")
    search_fields = ("subject", "description", "client__name")
    autocomplete_fields = ("client", "system", "assigned_to", "created_by")
    filter_horizontal = ("tags",)
    readonly_fields = (
        "sla_deadline",
        "resolved_at",
        "closed_at",
        "created_at",
        "updated_at",
    )
    inlines = [TimeEntryInline, AttachmentInline, TicketNoteInline]


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ("ticket", "user", "minutes", "billable", "created_at")
    list_filter = ("billable",)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "filename", "uploaded_by", "uploaded_at")


@admin.register(TicketTemplate)
class TicketTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "public_default", "updated_at")
    search_fields = ("name", "body")
    list_filter = ("public_default",)


@admin.register(TicketTag)
class TicketTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "color")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            obj.slug = slugify(obj.name)
        super().save_model(request, obj, form, change)
