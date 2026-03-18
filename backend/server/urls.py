from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken import views
from solutions import views as solutions_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/reports/aggregate/', solutions_views.AggregateReportView.as_view(), name='aggregate-report'),
    path('api/', include('solutions.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/token-auth/', views.obtain_auth_token),
]
