"""Portal routes for the lead pipeline (mounted at the project root)."""
from django.urls import path

from . import portal_views as views
from .public import ContactFormView

urlpatterns = [
    # Public, unauthenticated — sits at the project root.
    path("contact/", ContactFormView.as_view(), name="contact"),
    path("leads/", views.LeadListView.as_view(), name="lead_list"),
    path("leads/new/", views.LeadCreateView.as_view(), name="lead_create"),
    path("leads/<int:pk>/", views.LeadDetailView.as_view(), name="lead_detail"),
    path(
        "leads/<int:pk>/edit/",
        views.LeadUpdateView.as_view(),
        name="lead_edit",
    ),
    path(
        "leads/<int:pk>/activity/",
        views.LeadActivityCreateView.as_view(),
        name="lead_activity_create",
    ),
    path(
        "leads/<int:pk>/stage/",
        views.LeadStageUpdateView.as_view(),
        name="lead_stage",
    ),
    path(
        "leads/<int:pk>/convert/",
        views.LeadConvertView.as_view(),
        name="lead_convert",
    ),
]
