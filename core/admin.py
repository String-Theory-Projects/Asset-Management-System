from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(DefaultUserAdmin):
    model = User
    fieldsets = DefaultUserAdmin.fieldsets + (
        (None, {'fields': ('avatar', 'account_number', 'bank')}),
    )
    add_fieldsets = DefaultUserAdmin.add_fieldsets + (
        (None, {'fields': ('avatar', 'account_number', 'bank')}),
    )
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff')
