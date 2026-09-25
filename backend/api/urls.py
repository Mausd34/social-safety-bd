from django.urls import path
from . import views

urlpatterns = [
    path("hotels/", views.hotels, name="hotels"),
    path("hotels/reviews/", views.hotel_review_create, name="hotel-review-create"),
    path("hotels/<int:hotel_id>/", views.hotel_detail, name="hotel-detail"),
    path("admin/hotels/reviews/", views.admin_hotel_reviews, name="admin-hotel-reviews"),
    path("upazilas/", views.upazilas, name="upazilas"),
    path("chat/threads/", views.chat_thread_create, name="chat-thread-create"),
    path("chat/threads/<int:thread_id>/", views.chat_thread_detail, name="chat-thread-detail"),
    path("admin/chat/", views.admin_chat_threads, name="admin-chat"),
    path("health/", views.health, name="health"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("me/", views.me, name="me"),
    path("logout/", views.logout_view, name="logout"),
    path("cities/", views.cities, name="cities"),
    path("areas/", views.areas, name="areas"),
    path("cases/", views.cases, name="cases"),
    path("cases/<str:case_id>/", views.case_detail, name="case-detail"),
    path("statistics/", views.statistics, name="statistics"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("reports/", views.report_create, name="report-create"),
    path("admin/reports/", views.admin_reports, name="admin-reports"),
]
