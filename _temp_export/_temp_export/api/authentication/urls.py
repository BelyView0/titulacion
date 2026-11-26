from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    LogoutView,
    MeView,
    ChangePasswordView,
    ForcePasswordChangeView,
    RequestPasswordChangeOTPView,
    ForgotPasswordView,
    VerifyResetOTPView,
    ResetPasswordView,
)


app_name = 'authentication'


urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('force-change-password/', ForcePasswordChangeView.as_view(), name='force-change-password'),
    path('change-password/otp/', RequestPasswordChangeOTPView.as_view(), name='change-password-otp'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('verify-reset-otp/', VerifyResetOTPView.as_view(), name='verify-reset-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]
