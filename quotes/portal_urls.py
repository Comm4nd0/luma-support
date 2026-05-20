"""Portal routes for quotes (mounted at the project root)."""
from django.urls import path

from . import portal_views as views

urlpatterns = [
    # Public — tokenised accept link.
    path(
        "q/<str:token>/",
        views.QuotePublicView.as_view(),
        name="quote_public",
    ),
    # Staff CRUD.
    path("quotes/", views.QuoteListView.as_view(), name="quote_list"),
    path("quotes/new/", views.QuoteCreateView.as_view(), name="quote_create"),
    path("quotes/<int:pk>/", views.QuoteDetailView.as_view(), name="quote_detail"),
    path(
        "quotes/<int:pk>/edit/",
        views.QuoteUpdateView.as_view(),
        name="quote_edit",
    ),
    path(
        "quotes/<int:pk>/send/",
        views.QuoteSendView.as_view(),
        name="quote_send",
    ),
    path(
        "quotes/<int:pk>/print/",
        views.QuotePrintView.as_view(),
        name="quote_print",
    ),
]
