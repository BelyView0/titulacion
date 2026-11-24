from django.urls import path

from .views import (
    LoginView,
    MeView,
    ChangePasswordView,
    ForgotPasswordView,
    VerifyResetOTPView,
    ResetPasswordView,
)


app_name = 'authentication'


urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('me/', MeView.as_view(), name='me'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('verify-reset-otp/', VerifyResetOTPView.as_view(), name='verify-reset-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]
