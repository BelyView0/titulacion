from django.urls import path, include

app_name = 'api'

urlpatterns = [
    path('auth/', include('api.authentication.urls')),
    path('alumnos/', include('api.alumnos.urls')),
]